from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src import db, quiz
from src.card_history import (
    get_card_revision_entry_ids,
    get_current_card_identity,
    get_entry_card_revision_history,
    get_quiz_session_card_revision,
    reconcile_collection_card_history,
)
from src.collections import (
    CrossCardMoveConfirmationRequired,
    add_entries_to_collection,
    get_card_groups_for_collection,
    get_collection_by_id,
    get_entries_in_collection,
    move_entry_in_collection,
    remove_entries_from_collection,
    set_card_name,
    update_collection,
    update_entry_collections,
)
from src.entries import add_entry, delete_entries, get_entry_change_events, update_entry
from src.import_export import import_general_entry_rows
from src.migrations import (
    BASELINE_SCHEMA_VERSION,
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    get_schema_version,
    run_migrations,
)


class M113CardHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "m11_3_test.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _collection_with_entries(self, count: int, card_size: int = 3) -> tuple[int, list[int]]:
        now = "2026-08-11T12:00:00+00:00"
        with db.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO collections (name, description, card_size, created_at, updated_at)
                VALUES (?, '', ?, ?, ?)
                """,
                (f"Synthetic {count}-{card_size}", card_size, now, now),
            )
            collection_id = int(cursor.lastrowid)
            entry_ids = []
            for index in range(1, count + 1):
                cursor = conn.execute(
                    """
                    INSERT INTO entries (
                        language, explanation_language, entry_type, term, meaning,
                        example, notes, tags, source, status, created_at, updated_at
                    ) VALUES ('English', 'English', 'word', ?, ?, '', '', '', '', 'new', ?, ?)
                    """,
                    (f"term-{index}", f"meaning-{index}", now, now),
                )
                entry_id = int(cursor.lastrowid)
                entry_ids.append(entry_id)
                conn.execute(
                    """
                    INSERT INTO entry_collections (entry_id, collection_id, position, added_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (entry_id, collection_id, index, now),
                )
            reconcile_collection_card_history(
                conn,
                collection_id,
                change_reason="synthetic_baseline",
            )
        return collection_id, entry_ids

    def _revision_count(self, collection_id: int) -> int:
        with db.get_connection() as conn:
            return int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM card_revisions
                    JOIN cards ON cards.id = card_revisions.card_id
                    WHERE cards.collection_id = ?
                    """,
                    (collection_id,),
                ).fetchone()[0]
            )

    def test_fresh_schema_and_repeated_initialization_are_idempotent(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(5, 2)
        first_count = self._revision_count(collection_id)
        db.init_db()
        db.init_db()
        self.assertEqual(first_count, 3)
        self.assertEqual(self._revision_count(collection_id), first_count)
        with db.get_connection() as conn:
            self.assertEqual(get_schema_version(conn), CURRENT_SCHEMA_VERSION)
            cards = conn.execute(
                "SELECT COUNT(*) FROM cards WHERE collection_id = ? AND is_active = 1",
                (collection_id,),
            ).fetchone()[0]
            memberships = conn.execute(
                "SELECT COUNT(*) FROM card_revision_entries"
            ).fetchone()[0]
            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(cards, 3)
        self.assertEqual(memberships, len(entry_ids))
        self.assertEqual(foreign_key_errors, [])

    def test_legacy_quiz_remains_unknown_and_card_name_migrates(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        db.DB_PATH = legacy_path
        with sqlite3.connect(legacy_path) as conn:
            conn.executescript(
                """
                CREATE TABLE collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                    description TEXT, card_size INTEGER NOT NULL DEFAULT 8,
                    is_system INTEGER NOT NULL DEFAULT 0, system_type TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, language TEXT NOT NULL,
                    explanation_language TEXT NOT NULL, entry_type TEXT NOT NULL,
                    term TEXT NOT NULL, meaning TEXT NOT NULL, example TEXT, notes TEXT,
                    tags TEXT, source TEXT, status TEXT DEFAULT 'new', review_count INTEGER DEFAULT 0,
                    correct_count INTEGER DEFAULT 0, wrong_count INTEGER DEFAULT 0,
                    current_interval_days INTEGER DEFAULT 0, next_due_at TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE entry_collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER NOT NULL,
                    collection_id INTEGER NOT NULL, position INTEGER NOT NULL, added_at TEXT NOT NULL,
                    UNIQUE(entry_id, collection_id)
                );
                CREATE TABLE collection_card_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, collection_id INTEGER NOT NULL,
                    card_number INTEGER NOT NULL, name TEXT, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, UNIQUE(collection_id, card_number)
                );
                CREATE TABLE quiz_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, collection_id INTEGER NOT NULL,
                    card_number INTEGER NOT NULL, quiz_type TEXT NOT NULL, started_at TEXT NOT NULL,
                    completed_at TEXT, total_items INTEGER NOT NULL DEFAULT 0,
                    correct_count INTEGER NOT NULL DEFAULT 0, wrong_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active'
                );
                INSERT INTO collections VALUES (1, 'Legacy', '', 2, 0, NULL, '2026-01-01', '2026-01-01');
                INSERT INTO entries (
                    id, language, explanation_language, entry_type, term, meaning, created_at, updated_at
                ) VALUES (1, 'English', 'English', 'word', 'legacy', 'known', '2026-01-01', '2026-01-01');
                INSERT INTO entry_collections VALUES (1, 1, 1, 1, '2026-01-01');
                INSERT INTO collection_card_metadata VALUES (1, 1, 1, 'Legacy Card', '2026-01-01', '2026-01-01');
                INSERT INTO quiz_sessions (
                    id, collection_id, card_number, quiz_type, started_at, status
                ) VALUES (1, 1, 1, 'term_to_meaning', '2026-01-01', 'completed');
                """
            )
        db.init_db()
        db.init_db()
        groups = get_card_groups_for_collection(1)
        self.assertEqual(groups[0]["card_name"], "Legacy Card")
        with db.get_connection() as conn:
            legacy_session = get_quiz_session_card_revision(conn, 1)
            self.assertIsNone(legacy_session["card_id"])
            self.assertIsNone(legacy_session["card_revision_id"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM card_revisions").fetchone()[0], 1)

    def test_within_card_reorder_revises_only_affected_card(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(4, 3)
        before = get_card_groups_for_collection(collection_id)
        move_entry_in_collection(collection_id, entry_ids[0], 2)
        after = get_card_groups_for_collection(collection_id)
        self.assertEqual(before[0]["card_id"], after[0]["card_id"])
        self.assertEqual(before[1]["card_revision_id"], after[1]["card_revision_id"])
        self.assertNotEqual(before[0]["card_revision_id"], after[0]["card_revision_id"])

    def test_cross_card_reorder_requires_confirmation_and_is_atomic(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(5, 3)
        before = get_card_groups_for_collection(collection_id)
        with self.assertRaises(CrossCardMoveConfirmationRequired):
            move_entry_in_collection(collection_id, entry_ids[0], 5)
        self.assertEqual(get_card_groups_for_collection(collection_id), before)
        move_entry_in_collection(
            collection_id,
            entry_ids[0],
            5,
            confirm_cross_card=True,
        )
        after = get_card_groups_for_collection(collection_id)
        self.assertEqual([row["card_id"] for row in before], [row["card_id"] for row in after])
        self.assertNotEqual(before[0]["card_revision_id"], after[0]["card_revision_id"])
        self.assertNotEqual(before[1]["card_revision_id"], after[1]["card_revision_id"])

    def test_append_updates_only_last_card_then_creates_new_card(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(3, 2)
        before = get_card_groups_for_collection(collection_id)
        new_one = self._insert_detached_entry("append-one")
        add_entries_to_collection([new_one], collection_id)
        middle = get_card_groups_for_collection(collection_id)
        self.assertEqual(before[0]["card_revision_id"], middle[0]["card_revision_id"])
        self.assertNotEqual(before[1]["card_revision_id"], middle[1]["card_revision_id"])
        new_two = self._insert_detached_entry("append-two")
        add_entries_to_collection([new_two], collection_id)
        after = get_card_groups_for_collection(collection_id)
        self.assertEqual(len(after), 3)
        self.assertNotIn(after[2]["card_id"], [row["card_id"] for row in middle])

    def _insert_detached_entry(self, term: str) -> int:
        now = "2026-08-11T12:30:00+00:00"
        with db.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO entries (
                    language, explanation_language, entry_type, term, meaning,
                    created_at, updated_at
                ) VALUES ('English', 'English', 'word', ?, 'synthetic', ?, ?)
                """,
                (term, now, now),
            )
            return int(cursor.lastrowid)

    def test_removal_requires_confirmation_and_preserves_old_revision(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(4, 3)
        before = get_card_groups_for_collection(collection_id)
        old_revision_id = before[1]["card_revision_id"]
        with self.assertRaises(CrossCardMoveConfirmationRequired):
            remove_entries_from_collection([entry_ids[0]], collection_id)
        remove_entries_from_collection(
            [entry_ids[0]],
            collection_id,
            confirm_cross_card=True,
        )
        after = get_card_groups_for_collection(collection_id)
        self.assertEqual(len(after), 1)
        with db.get_connection() as conn:
            self.assertEqual(get_card_revision_entry_ids(conn, old_revision_id), [entry_ids[3]])

    def test_entry_hard_delete_reconciles_affected_cards_but_keeps_snapshot_ids(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(4, 3)
        old_revision_id = get_card_groups_for_collection(collection_id)[0]["card_revision_id"]
        with self.assertRaises(CrossCardMoveConfirmationRequired):
            delete_entries([entry_ids[0]])
        self.assertEqual(
            [row["id"] for row in get_entries_in_collection(collection_id)],
            entry_ids,
        )
        delete_entries([entry_ids[0]], confirm_cross_card=True)
        with db.get_connection() as conn:
            self.assertEqual(
                get_card_revision_entry_ids(conn, old_revision_id),
                entry_ids[:3],
            )
        self.assertEqual(
            [row["id"] for row in get_entries_in_collection(collection_id)],
            entry_ids[1:],
        )

    def test_card_size_retirement_reappearance_and_name_identity(self) -> None:
        collection_id, _ = self._collection_with_entries(3, 2)
        before = get_card_groups_for_collection(collection_id)
        retired_card_id = before[1]["card_id"]
        set_card_name(collection_id, 2, "Retired identity")
        with db.get_connection() as conn:
            collection = conn.execute(
                "SELECT name, description FROM collections WHERE id = ?",
                (collection_id,),
            ).fetchone()
        with self.assertRaises(CrossCardMoveConfirmationRequired):
            update_collection(
                collection_id,
                collection["name"],
                collection["description"] or "",
                3,
            )
        update_collection(
            collection_id,
            collection["name"],
            collection["description"] or "",
            3,
            confirm_cross_card=True,
        )
        self.assertEqual(len(get_card_groups_for_collection(collection_id)), 1)
        update_collection(
            collection_id,
            collection["name"],
            collection["description"] or "",
            2,
            confirm_cross_card=True,
        )
        after = get_card_groups_for_collection(collection_id)
        self.assertNotEqual(after[1]["card_id"], retired_card_id)
        self.assertEqual(after[1]["card_name"], "")
        with db.get_connection() as conn:
            retired = conn.execute("SELECT name, is_active FROM cards WHERE id = ?", (retired_card_id,)).fetchone()
        self.assertEqual(retired["name"], "Retired identity")
        self.assertEqual(retired["is_active"], 0)

    def test_quiz_binds_revision_and_study_activity_creates_no_revision_noise(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(4, 3)
        before = get_card_groups_for_collection(collection_id)
        original_revision = before[0]["card_revision_id"]
        revision_count = self._revision_count(collection_id)
        session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 1)
        for _ in range(10):
            get_card_groups_for_collection(collection_id)
            quiz.get_quiz_session(session_id)
        quiz.mark_quiz_session_cancelled(session_id)
        self.assertEqual(self._revision_count(collection_id), revision_count)
        move_entry_in_collection(collection_id, entry_ids[0], 2)
        later_session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 1)
        with db.get_connection() as conn:
            original = get_quiz_session_card_revision(conn, session_id)
            later = get_quiz_session_card_revision(conn, later_session_id)
            self.assertEqual(original["card_revision_id"], original_revision)
            self.assertNotEqual(later["card_revision_id"], original_revision)
            self.assertEqual(
                get_card_revision_entry_ids(conn, original_revision),
                entry_ids[:3],
            )

    def test_whole_collection_quiz_has_no_card_identity(self) -> None:
        collection_id, _ = self._collection_with_entries(3, 3)
        session_id = quiz.create_quiz_session(collection_id, 0, "matching", 3)
        session = quiz.get_quiz_session(session_id)
        self.assertIsNone(session["card_id"])
        self.assertIsNone(session["card_revision_id"])

    def test_entry_content_history_records_changes_and_skips_noop(self) -> None:
        entry_id = add_entry("English", "English", "word", "before", "meaning", notes="old")
        update_entry(
            entry_id,
            "English",
            "English",
            "word",
            "after",
            "meaning",
            notes="new",
        )
        events = get_entry_change_events(entry_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["entry_id"], entry_id)
        self.assertEqual(events[0]["changes"]["term"], {"old": "before", "new": "after"})
        self.assertIn("template.term", events[0]["changes"])
        update_entry(
            entry_id,
            "English",
            "English",
            "word",
            "after",
            "meaning",
            notes="new",
        )
        self.assertEqual(len(get_entry_change_events(entry_id)), 1)

    def test_mutation_and_history_roll_back_together_on_failure(self) -> None:
        collection_id, _ = self._collection_with_entries(2, 2)
        new_entry_id = self._insert_detached_entry("rollback")
        before_revisions = self._revision_count(collection_id)
        with patch(
            "src.collections.reconcile_collection_card_history",
            side_effect=RuntimeError("synthetic reconciliation failure"),
        ):
            with self.assertRaises(RuntimeError):
                add_entries_to_collection([new_entry_id], collection_id)
        with db.get_connection() as conn:
            membership = conn.execute(
                "SELECT COUNT(*) FROM entry_collections WHERE collection_id = ? AND entry_id = ?",
                (collection_id, new_entry_id),
            ).fetchone()[0]
        self.assertEqual(membership, 0)
        self.assertEqual(self._revision_count(collection_id), before_revisions)

    def test_entry_edit_collection_membership_and_import_append_reconcile(self) -> None:
        first_collection, entry_ids = self._collection_with_entries(4, 3)
        second_collection, _ = self._collection_with_entries(1, 3)
        with self.assertRaises(CrossCardMoveConfirmationRequired):
            update_entry_collections(
                entry_ids[0],
                [second_collection],
                [first_collection, second_collection],
            )
        update_entry_collections(
            entry_ids[0],
            [second_collection],
            [first_collection, second_collection],
            confirm_cross_card=True,
        )
        self.assertNotIn(
            entry_ids[0],
            [row["id"] for row in get_entries_in_collection(first_collection)],
        )
        before_revisions = self._revision_count(second_collection)
        result = import_general_entry_rows(
            [
                {
                    "row_number": 2,
                    "errors": [],
                    "data": {
                        "language": "English",
                        "explanation_language": "English",
                        "entry_type": "word",
                        "term": "imported-synthetic",
                        "meaning": "imported-meaning",
                        "status": "new",
                    },
                }
            ],
            target_collection_id=second_collection,
        )
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(self._revision_count(second_collection), before_revisions + 1)

    def test_migration_savepoint_rolls_back_partial_schema_on_failure(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row

        def failing_migration(conn: sqlite3.Connection) -> None:
            conn.execute("CREATE TABLE partial_m11_3_state (id INTEGER PRIMARY KEY)")
            raise RuntimeError("synthetic migration failure")

        original_function = MIGRATIONS[0]["function"]
        MIGRATIONS[0]["function"] = failing_migration
        try:
            with self.assertRaises(RuntimeError):
                run_migrations(connection)
            self.assertEqual(get_schema_version(connection), BASELINE_SCHEMA_VERSION)
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'partial_m11_3_state'"
            ).fetchone()
            self.assertIsNone(table)
        finally:
            MIGRATIONS[0]["function"] = original_function
            connection.close()

    def test_cross_card_reorder_apptest_requires_explicit_second_confirmation(self) -> None:
        from streamlit.testing.v1 import AppTest

        collection_id, entry_ids = self._collection_with_entries(4, 3)
        project_root = Path(__file__).resolve().parents[1]
        app = AppTest.from_file(str(project_root / "app.py")).run(timeout=30)
        app.sidebar.radio[0].set_value("Collections")
        app.run(timeout=30)
        next(widget for widget in app.radio if widget.label == "Collections section").set_value("Edit")
        app.run(timeout=30)
        view_selector = next(
            widget for widget in app.selectbox if widget.key == "view_collection_select"
        )
        view_selector.set_value(get_collection_by_id(collection_id))
        app.run(timeout=30)
        move_selector = next(
            widget for widget in app.selectbox if widget.label == "Select entry to move"
        )
        first_entry = next(
            value
            for value in get_entries_in_collection(collection_id)
            if int(value["id"]) == entry_ids[0]
        )
        move_selector.set_value(first_entry)
        next(widget for widget in app.number_input if widget.label == "New position").set_value(4)
        next(button for button in app.button if button.label == "Move Entry").click()
        app.run(timeout=30)
        app.run(timeout=30)
        self.assertIn(
            "Confirm move and Card reorganization",
            [button.label for button in app.button],
        )
        self.assertEqual(
            [row["id"] for row in get_entries_in_collection(collection_id)],
            entry_ids,
        )
        next(
            button
            for button in app.button
            if button.label == "Confirm move and Card reorganization"
        ).click()
        app.run(timeout=30)
        self.assertEqual(
            [row["id"] for row in get_entries_in_collection(collection_id)],
            entry_ids[1:] + [entry_ids[0]],
        )
        self.assertEqual(list(app.exception), [])

    def test_entry_revision_history_query_is_entry_id_based(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(3, 2)
        move_entry_in_collection(collection_id, entry_ids[0], 2)
        with db.get_connection() as conn:
            identity = get_current_card_identity(conn, collection_id, 1)
            history = get_entry_card_revision_history(conn, entry_ids[0])
        self.assertIsNotNone(identity)
        self.assertEqual({row["card_id"] for row in history}, {identity["card_id"]})
        self.assertEqual(len(history), 2)


if __name__ == "__main__":
    unittest.main()

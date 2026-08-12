from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src import db, quiz, statistics
from src.backup import BACKUP_TABLES, get_database_file_bytes
from src.card_history import get_card_revision_entry_ids
from src.collections import (
    COLLECTION_DELETE_CONFIRMATION,
    COLLECTION_DELETE_WARNING,
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    delete_collection,
    get_card_groups_for_collection,
    remove_entries_from_collection,
)
from src.entries import add_entry, get_entry_by_id, update_entry
from src.import_export import export_all_entries_to_rows
from src.learning_workflow import (
    get_card_learning_history,
    get_daily_quiz_candidates,
    get_review_focus_payload,
    get_study_cards,
)
from src.migrations import CURRENT_SCHEMA_VERSION, get_schema_version


class M114BaselineClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "m11_4_test.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _entry(self, term: str, meaning: str = "synthetic meaning") -> int:
        return add_entry("English", "English", "word", term, meaning)

    def _completed_quiz(
        self,
        collection_id: int,
        card_number: int,
        entry_id: int,
        *,
        correct: bool,
        timestamp: str = "2026-08-11T12:00:00+00:00",
    ) -> dict:
        with patch.object(quiz, "_now_iso", return_value=timestamp):
            session_id = quiz.create_quiz_session(
                collection_id,
                card_number,
                "term_to_meaning",
                1,
            )
            quiz.record_quiz_answer(
                session_id,
                entry_id,
                f"prompt-{entry_id}",
                f"answer-{entry_id}",
                f"answer-{entry_id}" if correct else "wrong answer",
                correct,
            )
            return quiz.complete_quiz_session(session_id)

    def test_current_card_views_do_not_inherit_retired_card_history(self) -> None:
        collection_id = create_collection("Stable history", card_size=1)
        first_id = self._entry("first")
        retired_entry_id = self._entry("retired")
        add_entries_to_collection([first_id, retired_entry_id], collection_id)

        original_cards = get_card_groups_for_collection(collection_id)
        retired_card_id = int(original_cards[1]["card_id"])
        retired_revision_id = int(original_cards[1]["card_revision_id"])
        completed = self._completed_quiz(
            collection_id,
            2,
            retired_entry_id,
            correct=True,
        )

        remove_entries_from_collection([retired_entry_id], collection_id)
        replacement_entry_id = self._entry("replacement")
        add_entries_to_collection([replacement_entry_id], collection_id)
        current_cards = get_card_groups_for_collection(collection_id)
        replacement_card = current_cards[1]

        self.assertNotEqual(int(replacement_card["card_id"]), retired_card_id)
        with db.get_connection() as conn:
            study_cards = get_study_cards(conn)
            current_history = get_card_learning_history(conn, collection_id, 2)
            overview = statistics.get_card_learning_overview_stats(conn)
            historical_sessions = statistics.get_card_learning_sessions_between_dates(
                conn,
                "2026-08-11",
                "2026-08-11",
            )
            original_membership = get_card_revision_entry_ids(conn, retired_revision_id)
            recommendations = get_daily_quiz_candidates(conn, "2026-08-11")
            retired_card = conn.execute(
                "SELECT is_active FROM cards WHERE id = ?",
                (retired_card_id,),
            ).fetchone()

        replacement_study = next(
            row for row in study_cards if int(row["card_id"]) == int(replacement_card["card_id"])
        )
        self.assertEqual(replacement_study["completion_count"], 0)
        self.assertIsNone(replacement_study["last_completed_at"])
        self.assertEqual(current_history, [])
        self.assertEqual(overview["completed_card_sessions"], 1)
        self.assertEqual(overview["cards_with_completion"], 0)
        self.assertEqual(overview["never_quizzed_cards"], 2)
        self.assertEqual(retired_card["is_active"], 0)
        self.assertEqual(original_membership, [retired_entry_id])
        self.assertEqual(historical_sessions[0]["session_id"], completed["id"])
        self.assertEqual(historical_sessions[0]["card_id"], retired_card_id)
        self.assertEqual(historical_sessions[0]["card_revision_id"], retired_revision_id)
        replacement_recommendation = next(
            row
            for row in recommendations
            if row.get("collection_id") == collection_id and row.get("card_number") == 2
        )
        self.assertEqual(
            replacement_recommendation["card_id"],
            int(replacement_card["card_id"]),
        )

    def test_entry_health_is_quiz_authoritative_and_m14_compatible(self) -> None:
        collection_id = create_collection("Entry health", card_size=8)
        never_id = self._entry("never-quizzed")
        strong_id = self._entry("strong")
        weak_id = self._entry("weak")
        risk_id = self._entry("at-risk")
        add_entries_to_collection(
            [never_id, strong_id, weak_id, risk_id],
            collection_id,
        )
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE entries SET review_count = 999, correct_count = 999 WHERE id = ?",
                (never_id,),
            )
            conn.execute(
                """
                INSERT INTO card_review_logs (
                    collection_id, card_number, reviewed_at, rating,
                    previous_interval_days, new_interval_days,
                    previous_due_at, next_due_at, entry_count
                ) VALUES (?, 1, '2026-08-11T09:00:00+00:00',
                          'manual_schedule_update', 0, 0, NULL, '2026-08-12', 4)
                """,
                (collection_id,),
            )

        for _ in range(3):
            self._completed_quiz(collection_id, 1, strong_id, correct=True)
        for _ in range(2):
            self._completed_quiz(collection_id, 1, weak_id, correct=False)
        self._completed_quiz(collection_id, 1, risk_id, correct=False)
        add_entries_to_system_collection([weak_id], "mistake_book")
        add_entries_to_system_collection([risk_id], "proficient_pool")

        with db.get_connection() as conn:
            performance = {
                row["entry_id"]: row
                for row in statistics.get_entry_performance_summary(conn)
            }
            strong_ids = {
                row["entry_id"] for row in statistics.get_strong_entries(conn)
            }
            weak_ids = {
                row["entry_id"] for row in statistics.get_weak_entries(conn)
            }
            neglected = {
                row["entry_id"]: row
                for row in statistics.get_neglected_entries(conn)
            }
            risk_ids = {
                row["entry_id"] for row in statistics.get_proficient_risk_entries(conn)
            }
            overview = statistics.get_entry_health_overview(conn)

        self.assertEqual(performance[never_id]["attempt_count"], 0)
        self.assertIsNone(performance[never_id]["last_quizzed_at"])
        self.assertNotIn(never_id, strong_ids)
        self.assertNotIn(never_id, neglected)
        self.assertNotIn(strong_id, strong_ids)
        self.assertNotIn(weak_id, weak_ids)
        self.assertNotIn(risk_id, risk_ids)
        self.assertEqual(overview["never_quizzed_entries"], 1)
        self.assertEqual(overview["insufficient_evidence"], 3)

    def test_collection_delete_contract_is_explicit_and_deterministic(self) -> None:
        self.assertIn("permanently deletes", COLLECTION_DELETE_WARNING)
        self.assertIn("Card identity/revision history", COLLECTION_DELETE_WARNING)
        self.assertIn("Quiz sessions/item logs", COLLECTION_DELETE_WARNING)
        self.assertIn("permanently deleted", COLLECTION_DELETE_CONFIRMATION)

        collection_id = create_collection("Destructive contract", card_size=8)
        entry_id = self._entry("kept-entry")
        add_entries_to_collection([entry_id], collection_id)
        self._completed_quiz(collection_id, 1, entry_id, correct=True)

        result = delete_collection(collection_id)

        self.assertTrue(result["deleted"])
        self.assertEqual(result["deleted_quiz_session_count"], 1)
        self.assertIsNotNone(get_entry_by_id(entry_id))
        with db.get_connection() as conn:
            counts = {
                table: conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE "
                    + (
                        "collection_id = ?"
                        if table in {"cards", "quiz_sessions", "card_review_logs", "card_review_states"}
                        else "1 = 1"
                    ),
                    (collection_id,)
                    if table in {"cards", "quiz_sessions", "card_review_logs", "card_review_states"}
                    else (),
                ).fetchone()[0]
                for table in ("cards", "quiz_sessions", "card_review_logs", "card_review_states")
            }
            log_count = conn.execute("SELECT COUNT(*) FROM quiz_item_logs").fetchone()[0]
            revision_count = conn.execute("SELECT COUNT(*) FROM card_revisions").fetchone()[0]
        self.assertEqual(counts, {key: 0 for key in counts})
        self.assertEqual(log_count, 0)
        self.assertEqual(revision_count, 0)

    def test_restart_backup_and_schema_baseline_are_stable(self) -> None:
        collection_id = create_collection("Restart", card_size=8)
        entry_id = self._entry("restart-entry")
        add_entries_to_collection([entry_id], collection_id)
        self._completed_quiz(collection_id, 1, entry_id, correct=True)

        with db.get_connection() as conn:
            before = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "cards",
                    "card_revisions",
                    "card_revision_entries",
                    "entry_change_events",
                    "quiz_sessions",
                    "quiz_item_logs",
                )
            }
            self.assertEqual(get_schema_version(conn), CURRENT_SCHEMA_VERSION)

        db.init_db()
        db.init_db()

        with db.get_connection() as conn:
            after = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in before
            }
            self.assertEqual(get_schema_version(conn), CURRENT_SCHEMA_VERSION)
        self.assertEqual(after, before)
        self.assertTrue(
            {
                "cards",
                "card_revisions",
                "card_revision_entries",
                "entry_change_events",
                "quiz_sessions",
                "quiz_item_logs",
            }.issubset(BACKUP_TABLES)
        )

        backup_bytes = get_database_file_bytes()
        backup_path = Path(self.temp_dir.name) / "readable-backup.sqlite3"
        backup_path.write_bytes(backup_bytes)
        with sqlite3.connect(backup_path) as restored:
            self.assertEqual(
                restored.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            self.assertEqual(
                restored.execute("SELECT COUNT(*) FROM quiz_item_logs").fetchone()[0],
                1,
            )

    def test_quiz_duplicate_protection_and_edit_snapshot_truth(self) -> None:
        collection_id = create_collection("Snapshot truth", card_size=8)
        entry_id = self._entry("before-edit", "before-meaning")
        add_entries_to_collection([entry_id], collection_id)
        session_id = quiz.create_quiz_session(
            collection_id,
            1,
            "term_to_meaning_mcq",
            1,
        )
        first = quiz.record_quiz_answer(
            session_id,
            entry_id,
            "before-edit",
            "before-meaning",
            "before-meaning",
            True,
        )
        duplicate = quiz.record_quiz_answer(
            session_id,
            entry_id,
            "before-edit",
            "before-meaning",
            "before-meaning",
            True,
        )
        completed = quiz.complete_quiz_session(session_id)

        update_entry(
            entry_id,
            "English",
            "English",
            "word",
            "after-edit",
            "after-meaning",
        )
        current = get_entry_by_id(entry_id)
        exported = next(
            row
            for row in export_all_entries_to_rows()
            if int(row["entry_id"]) == entry_id
        )
        with db.get_connection() as conn:
            log = conn.execute(
                """
                SELECT prompt, expected_answer, user_answer, is_correct
                FROM quiz_item_logs
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            log_count = conn.execute(
                "SELECT COUNT(*) FROM quiz_item_logs WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]

        self.assertTrue(first["logged"])
        self.assertFalse(duplicate["logged"])
        self.assertEqual(duplicate["reason"], "already_logged")
        self.assertEqual(log_count, 1)
        self.assertEqual(completed["correct_count"], 1)
        self.assertEqual(completed["wrong_count"], 0)
        self.assertEqual(current["term"], "after-edit")
        self.assertEqual(exported["term"], "after-edit")
        self.assertEqual(
            tuple(log),
            ("before-edit", "before-meaning", "before-meaning", 1),
        )

    def test_stable_focus_and_stale_queue_are_cleared_without_wrong_card(self) -> None:
        from streamlit.testing.v1 import AppTest

        collection_id = create_collection("Stale focus", card_size=8)
        entry_id = self._entry("stale-entry")
        add_entries_to_collection([entry_id], collection_id)
        card_id = int(get_card_groups_for_collection(collection_id)[0]["card_id"])
        with db.get_connection() as conn:
            payload = get_review_focus_payload(conn, collection_id, 1)
        self.assertEqual(payload["card_id"], card_id)
        delete_collection(collection_id)

        project_root = Path(__file__).resolve().parents[1]
        focus_app = AppTest.from_file(str(project_root / "app.py")).run(timeout=30)
        focus_app.session_state["quiz_focus_collection_id"] = collection_id
        focus_app.session_state["quiz_focus_card_number"] = 1
        focus_app.session_state["quiz_focus_card_id"] = card_id
        focus_app.session_state["quiz_focus_type"] = "mixed_mcq"
        focus_app.sidebar.radio[0].set_value("Quiz")
        focus_app.run(timeout=30)
        self.assertTrue(
            any("focus from Today is no longer available" in row.value for row in focus_app.warning)
        )
        self.assertEqual(list(focus_app.exception), [])

        review_app = AppTest.from_file(str(project_root / "app.py")).run(timeout=30)
        review_app.session_state["review_focus_collection_id"] = collection_id
        review_app.session_state["review_focus_card_number"] = 1
        review_app.session_state["review_focus_card_id"] = card_id
        review_app.sidebar.radio[0].set_value("Review")
        review_app.run(timeout=30)
        self.assertTrue(
            any("focused card from Today is no longer available" in row.value for row in review_app.warning)
        )
        self.assertEqual(list(review_app.exception), [])

        queue_app = AppTest.from_file(str(project_root / "app.py")).run(timeout=30)
        queue_app.session_state["quiz_queue"] = [
            {
                "collection_id": collection_id,
                "collection_name": "Stale focus",
                "card_number": 1,
                "card_id": card_id,
                "preferred_quiz_type": "mixed_mcq",
            }
        ]
        queue_app.session_state["quiz_queue_index"] = 0
        queue_app.sidebar.radio[0].set_value("Quiz")
        queue_app.run(timeout=30)
        self.assertTrue(
            any("unavailable Card(s)" in row.value for row in queue_app.warning)
        )
        self.assertEqual(list(queue_app.exception), [])


if __name__ == "__main__":
    unittest.main()

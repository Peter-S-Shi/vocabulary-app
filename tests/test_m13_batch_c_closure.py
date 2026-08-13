from __future__ import annotations

import io
from pathlib import Path
import sqlite3
import tempfile
import unittest

from openpyxl import Workbook

from src import db
from src.backup import get_database_file_bytes
from src.collections import create_collection, get_entries_in_collection
from src.entry_templates import create_entry_template, create_template_field
from src.import_export import (
    build_import_preview,
    import_collection_rows,
    import_general_entry_rows,
    import_template_entry_rows,
    rows_to_csv_bytes,
)
from src.linked_sources import (
    confirm_collection_source_link,
    confirm_linked_source_refresh,
    get_collection_source_link,
    preview_linked_source_refresh,
)
from src.migrations import (
    APP_DATA_VERSION,
    BASELINE_SCHEMA_VERSION,
    CURRENT_SCHEMA_VERSION,
    get_metadata,
    get_schema_version,
    run_migrations,
    set_metadata,
    set_schema_version,
)
from src.template_definitions import (
    export_template_definition_csv,
    import_template_definition_csv,
)


GENERAL_COLUMNS = [
    "language",
    "explanation_language",
    "entry_type",
    "term",
    "meaning",
    "status",
]


class M13BatchCClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m13_batch_c.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _general_row(self, term: str, meaning: str) -> dict:
        return {
            "language": "English",
            "explanation_language": "English",
            "entry_type": "word",
            "term": term,
            "meaning": meaning,
            "status": "new",
        }

    def _csv_bytes(self, rows: list[dict]) -> bytes:
        columns = list(dict.fromkeys(GENERAL_COLUMNS + [key for row in rows for key in row]))
        return rows_to_csv_bytes(rows, columns)

    def _write_csv(self, rows: list[dict], name: str) -> Path:
        path = self.root / name
        path.write_bytes(self._csv_bytes(rows))
        return path

    def _xlsx_bytes(self, rows: list[dict]) -> bytes:
        columns = list(dict.fromkeys(GENERAL_COLUMNS + [key for row in rows for key in row]))
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Vocabulary"
        sheet.append(columns)
        for row in rows:
            sheet.append([row.get(column, "") for column in columns])
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()

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
                    (int(collection_id),),
                ).fetchone()[0]
            )

    def test_template_definition_drives_template_aware_linked_source_end_to_end(self) -> None:
        source_template_id = create_entry_template(
            "Portable Linked Template",
            "Synthetic cross-capability definition",
            "English",
            "portable_linked",
        )
        create_template_field(source_template_id, "term", "Term", "text", True, 0)
        create_template_field(source_template_id, "meaning", "Meaning", "text", True, 0)
        definition_bytes = export_template_definition_csv(source_template_id)

        target_path = self.root / "compatible-target.sqlite3"
        db.DB_PATH = target_path
        db.init_db()
        imported = import_template_definition_csv(definition_bytes)
        imported_template_id = int(imported["template_id"])
        self.assertNotIn(
            "template_id",
            definition_bytes.decode("utf-8-sig").splitlines()[0].split(","),
        )
        self.assertEqual(imported["template"]["is_system"], 0)
        self.assertEqual(
            [(row["field_key"], row["display_order"]) for row in imported["fields"]],
            [("meaning", 0), ("term", 0)],
        )

        collection_id = create_collection("Portable Linked Target", card_size=8)
        linked_rows = [
            {
                "language": "English",
                "template_name": "Portable Linked Template",
                "template_type": "portable_linked",
                "field:term": "portable-term",
                "field:meaning": "portable-meaning",
            }
        ]
        linked_path = self._write_csv(linked_rows, "portable-linked-source.csv")
        preview = build_import_preview(
            linked_path.read_bytes(),
            linked_path.name,
            mode="template_aware",
        )
        self.assertEqual(preview["summary"]["valid_count"], 1)
        result = confirm_collection_source_link(
            collection_id,
            linked_path,
            "template_aware",
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["imported_count"], 1)
        entries = get_entries_in_collection(collection_id)
        self.assertEqual([row["term"] for row in entries], ["portable-term"])
        with db.get_connection() as conn:
            entry = conn.execute(
                "SELECT template_id FROM entries WHERE id = ?",
                (int(entries[0]["id"]),),
            ).fetchone()
            field_values = conn.execute(
                "SELECT COUNT(*) FROM entry_field_values WHERE entry_id = ?",
                (int(entries[0]["id"]),),
            ).fetchone()[0]
        self.assertEqual(int(entry["template_id"]), imported_template_id)
        self.assertEqual(field_values, 2)
        self.assertEqual(self._revision_count(collection_id), 1)
        self.assertEqual(confirm_linked_source_refresh(collection_id)["imported_count"], 0)
        self.assertEqual(self._revision_count(collection_id), 1)

    def test_general_entry_import_surface_remains_compatible(self) -> None:
        row = self._general_row("general", "meaning")
        preview = build_import_preview(
            self._csv_bytes([row]),
            "general.csv",
            mode="general_entry",
        )
        first = import_general_entry_rows(preview["valid_rows"])
        skipped = import_general_entry_rows(preview["valid_rows"], duplicate_handling="skip")
        forced = import_general_entry_rows(
            preview["valid_rows"], duplicate_handling="import_anyway"
        )
        self.assertEqual(first["imported_count"], 1)
        self.assertEqual(skipped["skipped_duplicate_count"], 1)
        self.assertEqual(forced["imported_count"], 1)
        with db.get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM entries WHERE term = 'general'").fetchone()[0],
                2,
            )

        collection_id = create_collection("Caller-owned Target", card_size=8)
        connection = db.get_connection()
        try:
            result = import_general_entry_rows(
                [
                    {
                        "row_number": 2,
                        "errors": [],
                        "data": self._general_row("rollbackable", "meaning"),
                    }
                ],
                target_collection_id=collection_id,
                connection=connection,
            )
            self.assertEqual(result["imported_count"], 1)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM card_revisions"
                ).fetchone()[0],
                1,
            )
            connection.rollback()
        finally:
            connection.close()
        self.assertEqual(get_entries_in_collection(collection_id), [])
        self.assertEqual(self._revision_count(collection_id), 0)

    def test_template_aware_import_required_fields_and_collection_history_remain_compatible(self) -> None:
        template_id = create_entry_template(
            "Closure Template",
            "Synthetic",
            "English",
            "closure_template",
        )
        create_template_field(template_id, "term", "Term", "text", True, 0)
        create_template_field(template_id, "meaning", "Meaning", "text", True, 0)
        invalid = build_import_preview(
            self._csv_bytes([
                {
                    "language": "English",
                    "template_name": "Closure Template",
                    "template_type": "closure_template",
                    "field:term": "missing-meaning",
                    "field:meaning": "",
                }
            ]),
            "template-invalid.csv",
            mode="template_aware",
        )
        self.assertEqual(invalid["summary"]["invalid_count"], 1)

        valid = build_import_preview(
            self._csv_bytes([
                {
                    "language": "English",
                    "template_name": "Closure Template",
                    "template_type": "closure_template",
                    "field:term": "template-term",
                    "field:meaning": "template-meaning",
                }
            ]),
            "template-valid.csv",
            mode="template_aware",
        )
        collection_id = create_collection("Template Target", card_size=8)
        result = import_template_entry_rows(
            valid["valid_rows"],
            target_collection_id=collection_id,
        )
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["field_value_count"], 2)
        self.assertEqual(self._revision_count(collection_id), 1)

    def test_collection_import_reconciles_once_and_csv_xlsx_preview_agree(self) -> None:
        rows = [
            self._general_row("one", "1"),
            self._general_row("two", "2"),
            self._general_row("three", "3"),
        ]
        csv_preview = build_import_preview(
            self._csv_bytes(rows),
            "collection.csv",
            mode="collection",
        )
        xlsx_preview = build_import_preview(
            self._xlsx_bytes(rows),
            "collection.xlsx",
            mode="collection",
            options={"sheet_name": "Vocabulary"},
        )
        self.assertEqual(csv_preview["summary"], xlsx_preview["summary"])
        collection_id = create_collection("Collection Import Target", card_size=8)
        result = import_collection_rows(
            csv_preview["valid_rows"],
            import_mode="append_to_existing",
            target_collection_id=collection_id,
        )
        self.assertEqual(result["imported_entry_count"], 3)
        self.assertEqual(result["added_to_collection_count"], 3)
        self.assertEqual(self._revision_count(collection_id), 1)

    def test_baseline_migration_chain_preserves_data_and_repeated_startup(self) -> None:
        baseline_path = self.root / "baseline.sqlite3"
        db.DB_PATH = baseline_path
        connection = sqlite3.connect(baseline_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute(db.CREATE_ENTRIES_TABLE_SQL)
            connection.execute(db.CREATE_COLLECTIONS_TABLE_SQL)
            connection.execute(db.CREATE_ENTRY_COLLECTIONS_TABLE_SQL)
            connection.execute(db.CREATE_CARD_REVIEW_STATES_TABLE_SQL)
            connection.execute(db.CREATE_CARD_REVIEW_LOGS_TABLE_SQL)
            connection.execute(db.CREATE_COLLECTION_CARD_METADATA_TABLE_SQL)
            connection.execute(db.CREATE_QUIZ_SESSIONS_TABLE_SQL)
            connection.execute(
                """
                CREATE TABLE quiz_item_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    entry_id INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    expected_answer TEXT NOT NULL,
                    user_answer TEXT,
                    is_correct INTEGER,
                    answered_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY(entry_id) REFERENCES entries(id) ON DELETE CASCADE
                )
                """
            )
            set_schema_version(connection, BASELINE_SCHEMA_VERSION)
            set_metadata(connection, "app_data_version", "10.6")
            collection_id = int(
                connection.execute(
                    "INSERT INTO collections (name, description, card_size, created_at, updated_at) VALUES ('Baseline', '', 8, 'now', 'now')"
                ).lastrowid
            )
            entry_id = int(
                connection.execute(
                    """
                    INSERT INTO entries (
                        language, explanation_language, entry_type, term, meaning,
                        status, created_at, updated_at
                    ) VALUES ('English', 'English', 'word', 'preserved', 'meaning', 'new', 'now', 'now')
                    """
                ).lastrowid
            )
            connection.execute(
                "INSERT INTO entry_collections (entry_id, collection_id, position, added_at) VALUES (?, ?, 1, 'now')",
                (entry_id, collection_id),
            )
            session_id = int(
                connection.execute(
                    """
                    INSERT INTO quiz_sessions (
                        collection_id, card_number, quiz_type, started_at,
                        completed_at, total_items, correct_count, wrong_count, status
                    ) VALUES (?, 1, 'self_graded', 'now', 'now', 1, 1, 0, 'completed')
                    """,
                    (collection_id,),
                ).lastrowid
            )
            connection.execute(
                """
                INSERT INTO quiz_item_logs (
                    session_id, entry_id, prompt, expected_answer,
                    user_answer, is_correct, answered_at
                ) VALUES (?, ?, 'prompt', 'answer', 'answer', 1, 'now')
                """,
                (session_id, entry_id),
            )
            applied = run_migrations(connection)
            connection.commit()
            self.assertEqual(
                applied,
                [
                    "m11.3_stable_card_identity_and_entry_history",
                    "m11.3_preserve_quiz_logs_after_entry_delete",
                    "m13_linked_append_source",
                    "m15.1_template_speech_semantics",
                ],
            )
            self.assertEqual(get_schema_version(connection), CURRENT_SCHEMA_VERSION)
            self.assertEqual(get_metadata(connection, "app_data_version"), APP_DATA_VERSION)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM quiz_item_logs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM card_revisions").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM collection_source_links").fetchone()[0], 0)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            connection.close()

        db.init_db()
        db.init_db()
        with db.get_connection() as reopened:
            self.assertEqual(get_schema_version(reopened), CURRENT_SCHEMA_VERSION)
            self.assertEqual(get_metadata(reopened, "app_data_version"), APP_DATA_VERSION)
            self.assertEqual(reopened.execute("SELECT COUNT(*) FROM cards").fetchone()[0], 1)
            self.assertEqual(reopened.execute("SELECT COUNT(*) FROM card_revisions").fetchone()[0], 1)
            self.assertEqual(reopened.execute("SELECT COUNT(*) FROM collection_source_links").fetchone()[0], 0)
            self.assertEqual(reopened.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_database_backup_reopens_and_unavailable_restored_path_is_safe(self) -> None:
        collection_id = create_collection("Restored Path Target", card_size=8)
        source_path = self._write_csv(
            [self._general_row("restored", "meaning")],
            "restored-source.csv",
        )
        linked = confirm_collection_source_link(
            collection_id,
            source_path,
            "general_entry",
        )
        self.assertTrue(linked["success"])
        backup_path = self.root / "restored-backup.sqlite3"
        backup_path.write_bytes(get_database_file_bytes())
        source_path.unlink()

        db.DB_PATH = backup_path
        db.init_db()
        link_before = get_collection_source_link(collection_id)
        revisions_before = self._revision_count(collection_id)
        entries_before = [row["term"] for row in get_entries_in_collection(collection_id)]
        with db.get_connection() as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(get_schema_version(conn), CURRENT_SCHEMA_VERSION)
        preview = preview_linked_source_refresh(collection_id)
        refresh = confirm_linked_source_refresh(collection_id)
        self.assertEqual(preview["errors"], ["Linked source is unavailable."])
        self.assertFalse(refresh["success"])
        self.assertEqual(get_collection_source_link(collection_id), link_before)
        self.assertEqual(
            [row["term"] for row in get_entries_in_collection(collection_id)],
            entries_before,
        )
        self.assertEqual(self._revision_count(collection_id), revisions_before)


if __name__ == "__main__":
    unittest.main()

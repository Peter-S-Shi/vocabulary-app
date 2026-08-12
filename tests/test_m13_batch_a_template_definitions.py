from __future__ import annotations

import csv
import io
from pathlib import Path
import tempfile
import unittest

from src import db
from src.entries import add_entry, get_entry_by_id
from src.entry_templates import (
    create_entry_template,
    create_template_field,
    get_entry_template,
    get_entry_template_by_name,
    get_template_fields,
)
from src.import_export import export_all_entries_to_rows, rows_to_csv_bytes
from src.template_definitions import (
    TEMPLATE_DEFINITION_COLUMNS,
    TemplateDefinitionError,
    export_template_definition_csv,
    export_template_definition_rows,
    import_template_definition_csv,
    preview_template_definition_csv,
)


class M13BatchATemplateDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        self.test_db_path = Path(self.temp_dir.name) / "m13_batch_a.sqlite3"
        db.DB_PATH = self.test_db_path
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _custom_template(self, name: str = "Portable Study") -> int:
        template_id = create_entry_template(
            name,
            "Synthetic portable definition",
            "French",
            "custom_portable",
        )
        create_template_field(
            template_id,
            "notes",
            "Notes",
            "long_text",
            False,
            3,
        )
        create_template_field(
            template_id,
            "term",
            "Term",
            "text",
            True,
            1,
        )
        create_template_field(
            template_id,
            "meaning",
            "Meaning",
            "long_text",
            True,
            2,
        )
        return template_id

    def _rows(self, *, name: str = "Imported Portable") -> list[dict]:
        metadata = {
            "definition_version": "1",
            "template_name": name,
            "template_description": "Synthetic imported definition",
            "language": "French",
            "template_type": "custom_portable",
        }
        return [
            {
                **metadata,
                "field_key": "term",
                "field_label": "Term",
                "field_type": "text",
                "required": "1",
                "display_order": "1",
            },
            {
                **metadata,
                "field_key": "meaning",
                "field_label": "Meaning",
                "field_type": "long_text",
                "required": "1",
                "display_order": "2",
            },
        ]

    def _csv(self, rows: list[dict], columns: list[str] | None = None) -> bytes:
        return rows_to_csv_bytes(rows, columns or TEMPLATE_DEFINITION_COLUMNS)

    def _counts(self) -> tuple[int, int, int]:
        with db.get_connection() as conn:
            return tuple(
                int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("entry_templates", "entry_template_fields", "entries")
            )

    def test_custom_template_export_is_deterministic(self) -> None:
        template_id = self._custom_template()
        first = export_template_definition_csv(template_id)
        second = export_template_definition_csv(template_id)
        self.assertEqual(first, second)
        self.assertEqual(
            [row["field_key"] for row in export_template_definition_rows(template_id)],
            ["term", "meaning", "notes"],
        )

    def test_export_uses_stable_header_and_field_order(self) -> None:
        exported = export_template_definition_csv(self._custom_template()).decode(
            "utf-8-sig"
        )
        reader = csv.DictReader(io.StringIO(exported))
        self.assertEqual(reader.fieldnames, TEMPLATE_DEFINITION_COLUMNS)
        self.assertEqual(
            [row["field_key"] for row in reader],
            ["term", "meaning", "notes"],
        )

    def test_system_template_export_excludes_privileged_metadata(self) -> None:
        with db.get_connection() as conn:
            template_id = int(
                conn.execute(
                    "SELECT id FROM entry_templates WHERE is_system = 1 ORDER BY id LIMIT 1"
                ).fetchone()[0]
            )
        rows = export_template_definition_rows(template_id)
        self.assertTrue(rows)
        self.assertNotIn("is_system", rows[0])
        self.assertNotIn("template_id", rows[0])
        self.assertNotIn("field_id", rows[0])

    def test_export_contains_no_entry_content_or_internal_ids(self) -> None:
        secret_term = "PRIVATE-SYNTHETIC-ENTRY-CONTENT"
        add_entry("English", "English", "word", secret_term, "private meaning")
        template_id = self._custom_template()
        exported = export_template_definition_csv(template_id).decode("utf-8-sig")
        self.assertNotIn(secret_term, exported)
        for forbidden in ("entry_id", "template_id", "field_id", "created_at", "updated_at"):
            self.assertNotIn(forbidden, exported.splitlines()[0].split(","))

    def test_valid_preview_is_repeatable_and_read_only(self) -> None:
        file_bytes = self._csv(self._rows())
        before = self._counts()
        first = preview_template_definition_csv(file_bytes)
        second = preview_template_definition_csv(file_bytes)
        self.assertTrue(first["can_import"])
        self.assertEqual(first, second)
        self.assertEqual(before, self._counts())

    def test_empty_and_missing_column_definitions_are_rejected(self) -> None:
        empty = preview_template_definition_csv(b"")
        self.assertFalse(empty["can_import"])
        columns = [column for column in TEMPLATE_DEFINITION_COLUMNS if column != "language"]
        missing = preview_template_definition_csv(self._csv(self._rows(), columns))
        self.assertFalse(missing["can_import"])
        self.assertTrue(any("Missing required columns" in error for error in missing["errors"]))

    def test_unknown_v1_column_is_rejected(self) -> None:
        rows = self._rows()
        for row in rows:
            row["future_attribute"] = "unsupported"
        preview = preview_template_definition_csv(
            self._csv(rows, TEMPLATE_DEFINITION_COLUMNS + ["future_attribute"])
        )
        self.assertFalse(preview["can_import"])
        self.assertTrue(any("Unsupported columns" in error for error in preview["errors"]))

    def test_unsupported_definition_version_is_rejected(self) -> None:
        rows = self._rows()
        for row in rows:
            row["definition_version"] = "2"
        preview = preview_template_definition_csv(self._csv(rows))
        self.assertFalse(preview["can_import"])
        self.assertIsNone(preview["definition_version"])

    def test_inconsistent_template_metadata_is_rejected(self) -> None:
        rows = self._rows()
        rows[1]["template_description"] = "Contradictory metadata"
        preview = preview_template_definition_csv(self._csv(rows))
        self.assertFalse(preview["can_import"])
        self.assertTrue(any("Inconsistent Template metadata" in error for error in preview["errors"]))

    def test_blank_template_name_and_field_label_are_rejected(self) -> None:
        rows = self._rows()
        for row in rows:
            row["template_name"] = ""
        rows[0]["field_label"] = ""
        preview = preview_template_definition_csv(self._csv(rows))
        self.assertFalse(preview["can_import"])
        self.assertTrue(any("Template name is required" in error for error in preview["errors"]))
        self.assertTrue(any("field label is required" in error for error in preview["errors"]))

    def test_invalid_field_type_and_field_key_are_rejected(self) -> None:
        rows = self._rows()
        rows[0]["field_type"] = "audio"
        rows[1]["field_key"] = "9 invalid key"
        preview = preview_template_definition_csv(self._csv(rows))
        self.assertFalse(preview["can_import"])
        self.assertTrue(any("Unsupported field type" in error for error in preview["errors"]))
        self.assertTrue(any("snake_case" in error for error in preview["errors"]))

    def test_duplicate_normalized_field_keys_are_rejected(self) -> None:
        rows = self._rows()
        rows[0]["field_key"] = "Study-Term"
        rows[1]["field_key"] = "study term"
        preview = preview_template_definition_csv(self._csv(rows))
        self.assertFalse(preview["can_import"])
        self.assertTrue(any("duplicate normalized field key" in error for error in preview["errors"]))

    def test_invalid_required_value_is_rejected(self) -> None:
        rows = self._rows()
        rows[0]["required"] = "yes"
        preview = preview_template_definition_csv(self._csv(rows))
        self.assertFalse(preview["can_import"])
        self.assertTrue(any("required must be 0 or 1" in error for error in preview["errors"]))

    def test_invalid_and_duplicate_display_order_are_rejected(self) -> None:
        rows = self._rows()
        rows[0]["display_order"] = "-1"
        invalid = preview_template_definition_csv(self._csv(rows))
        self.assertFalse(invalid["can_import"])
        rows = self._rows()
        rows[1]["display_order"] = "1"
        duplicate = preview_template_definition_csv(self._csv(rows))
        self.assertFalse(duplicate["can_import"])
        self.assertTrue(any("duplicate display_order" in error for error in duplicate["errors"]))

    def test_zero_field_template_export_fails_explicitly(self) -> None:
        template_id = create_entry_template("Empty Portable", "", "English", "custom")
        with self.assertRaisesRegex(TemplateDefinitionError, "at least one field"):
            export_template_definition_csv(template_id)

    def test_existing_name_conflict_blocks_import(self) -> None:
        create_entry_template("Imported Portable", "", "English", "custom")
        preview = preview_template_definition_csv(self._csv(self._rows()))
        self.assertFalse(preview["can_import"])
        self.assertTrue(preview["name_conflict"])
        with self.assertRaises(TemplateDefinitionError):
            import_template_definition_csv(self._csv(self._rows()))

    def test_valid_import_creates_one_user_template_and_all_fields(self) -> None:
        before_templates, before_fields, _ = self._counts()
        result = import_template_definition_csv(self._csv(self._rows()))
        after_templates, after_fields, _ = self._counts()
        self.assertEqual(after_templates, before_templates + 1)
        self.assertEqual(after_fields, before_fields + 2)
        self.assertEqual(result["field_count"], 2)
        self.assertEqual(result["template"]["is_system"], 0)
        self.assertEqual(
            [field["field_key"] for field in result["fields"]],
            ["term", "meaning"],
        )

    def test_field_creation_failure_rolls_back_entire_template(self) -> None:
        before = self._counts()
        with db.get_connection() as conn:
            conn.execute(
                """
                CREATE TRIGGER fail_meaning_field
                BEFORE INSERT ON entry_template_fields
                WHEN NEW.field_key = 'meaning'
                BEGIN
                    SELECT RAISE(ABORT, 'synthetic field failure');
                END
                """
            )
            with self.assertRaisesRegex(TemplateDefinitionError, "No changes were saved"):
                import_template_definition_csv(self._csv(self._rows()), conn)
            self.assertIsNone(
                conn.execute(
                    "SELECT id FROM entry_templates WHERE name = 'Imported Portable'"
                ).fetchone()
            )
        self.assertEqual(before, self._counts())

    def test_export_import_round_trip_is_semantically_equivalent(self) -> None:
        template_id = self._custom_template("Round Trip Portable")
        source_rows = export_template_definition_rows(template_id)
        exported = export_template_definition_csv(template_id)

        second_db_path = Path(self.temp_dir.name) / "m13_round_trip.sqlite3"
        db.DB_PATH = second_db_path
        try:
            db.init_db()
            preview = preview_template_definition_csv(exported)
            self.assertTrue(preview["can_import"])
            result = import_template_definition_csv(exported)
            imported_rows = export_template_definition_rows(result["template_id"])
        finally:
            db.DB_PATH = self.test_db_path

        self.assertEqual(imported_rows, source_rows)
        self.assertEqual(result["template"]["is_system"], 0)

    def test_existing_entry_and_import_export_workflows_still_work(self) -> None:
        entry_id = add_entry(
            "English", "English", "word", "synthetic term", "synthetic meaning"
        )
        self.assertEqual(get_entry_by_id(entry_id)["term"], "synthetic term")
        exported_rows = export_all_entries_to_rows()
        self.assertTrue(any(row["entry_id"] == entry_id for row in exported_rows))
        template_id = self._custom_template("Regression Portable")
        self.assertEqual(get_entry_template(template_id)["name"], "Regression Portable")
        self.assertEqual(len(get_template_fields(template_id)), 3)
        self.assertIsNotNone(get_entry_template_by_name("Regression Portable"))


if __name__ == "__main__":
    unittest.main()

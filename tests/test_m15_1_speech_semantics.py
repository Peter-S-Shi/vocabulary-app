from __future__ import annotations

import csv
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src import db
from src.entries import add_entry, create_entry_with_template
from src.entry_templates import (
    FRENCH_VERB_PRESENT_TEMPLATE_NAME,
    create_entry_template,
    create_template_field,
    get_entry_template_by_name,
    get_template_fields,
    inspect_template_speech_readiness,
    set_template_field_speech_language_role,
)
from src.import_export import rows_to_csv_bytes
from src.migrations import (
    APP_DATA_VERSION,
    CURRENT_SCHEMA_VERSION,
    LINKED_APPEND_SOURCE_SCHEMA_VERSION,
    MIGRATIONS,
    get_metadata,
    get_schema_version,
    run_migrations,
    set_metadata,
    set_schema_version,
)
from src.speech_semantics import build_entry_speech_plan
from src.template_definitions import (
    TEMPLATE_DEFINITION_COLUMNS,
    TEMPLATE_DEFINITION_V1_COLUMNS,
    export_template_definition_csv,
    export_template_definition_rows,
    import_template_definition_csv,
    preview_template_definition_csv,
)
from src.tts_providers import (
    FROZEN_PROVIDER_SPECS,
    ProviderAvailability,
    ProviderRegistry,
    SynthesisResult,
    normalize_supported_language,
)


class FakeProvider:
    def __init__(self, language: str, *, available: bool = True) -> None:
        self.spec = FROZEN_PROVIDER_SPECS[language]
        self.available = available

    def preflight(self) -> ProviderAvailability:
        if self.available:
            return ProviderAvailability(True, "available")
        return ProviderAvailability(False, "provider_unavailable", "Synthetic unavailable provider.")

    def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult:
        if not self.available:
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                None, None, None, "provider_unavailable", "Synthetic unavailable provider."
            )
        output_path.write_bytes(b"RIFF-synthetic")
        return SynthesisResult(
            self.spec.provider_id, self.spec.voice_id, self.spec.language,
            output_path, "audio/wav", 24000
        )


def available_registry(*, mandarin_available: bool = True) -> ProviderRegistry:
    return ProviderRegistry([
        FakeProvider("en"),
        FakeProvider("fr"),
        FakeProvider("zh-CN", available=mandarin_available),
    ])


class M151SpeechSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        self.test_db_path = Path(self.temp_dir.name) / "m15_1.sqlite3"
        db.DB_PATH = self.test_db_path
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_fresh_database_reaches_m15_1_schema_and_is_idempotent(self) -> None:
        with db.get_connection() as conn:
            self.assertEqual(get_schema_version(conn), CURRENT_SCHEMA_VERSION)
            self.assertEqual(get_metadata(conn, "app_data_version"), APP_DATA_VERSION)
            self.assertEqual(run_migrations(conn), [])
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(entry_template_fields)")}
            self.assertIn("speech_language_role", columns)

    def test_system_roles_and_french_required_fields_are_explicit(self) -> None:
        expected = {
            "General Entry": {"term": "entry", "meaning": "explanation"},
            "French Verb Present": {
                "infinitive": "entry", "meaning": "explanation", "je": "entry",
                "tu": "entry", "il_elle_on": "entry", "nous": "entry",
                "vous": "entry", "ils_elles": "entry",
            },
            "French Adjective Agreement": {
                "masculine_singular": "entry", "meaning": "explanation",
                "feminine_singular": "entry", "masculine_plural": "entry",
                "feminine_plural": "entry",
            },
            "French Noun Gender Plural": {
                "singular": "entry", "meaning": "explanation", "gender": "entry",
                "plural": "entry", "article": "entry",
            },
        }
        for template_name, roles in expected.items():
            template = get_entry_template_by_name(template_name)
            fields = {field["field_key"]: field for field in get_template_fields(int(template["id"]))}
            for key, role in roles.items():
                self.assertEqual(fields[key]["speech_language_role"], role)
                self.assertEqual(fields[key]["required"], 1)
            for field in fields.values():
                if not field["required"]:
                    self.assertEqual(field["speech_language_role"], "none")

    def test_migration_preserves_blank_values_and_learning_tables(self) -> None:
        template = get_entry_template_by_name(FRENCH_VERB_PRESENT_TEMPLATE_NAME)
        entry_id = create_entry_with_template(
            {"template_id": template["id"], "language": "French", "explanation_language": "English", "entry_type": "verb"},
            {"infinitive": "parler", "meaning": "to speak", "je": "je parle", "tu": "tu parles",
             "il_elle_on": "il parle", "nous": "nous parlons", "vous": "vous parlez", "ils_elles": "ils parlent"},
        )
        with db.get_connection() as conn:
            field_id = int(conn.execute(
                "SELECT id FROM entry_template_fields WHERE template_id = ? AND field_key = 'je'",
                (template["id"],),
            ).fetchone()[0])
            conn.execute("UPDATE entry_field_values SET field_value = '' WHERE entry_id = ? AND field_id = ?", (entry_id, field_id))
            before = tuple(int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in (
                "entries", "quiz_sessions", "quiz_item_logs", "card_revisions", "entry_change_events"
            ))
            set_schema_version(conn, LINKED_APPEND_SOURCE_SCHEMA_VERSION)
            set_metadata(conn, "app_data_version", "13.0")
            applied = run_migrations(conn)
            self.assertEqual(applied, ["m15.1_template_speech_semantics"])
            blank = conn.execute(
                "SELECT field_value FROM entry_field_values WHERE entry_id = ? AND field_id = ?", (entry_id, field_id)
            ).fetchone()[0]
            after = tuple(int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in (
                "entries", "quiz_sessions", "quiz_item_logs", "card_revisions", "entry_change_events"
            ))
            self.assertEqual(blank, "")
            self.assertEqual(after, before)

    def test_migration_savepoint_rolls_back_metadata_and_field_changes(self) -> None:
        with db.get_connection() as conn:
            field = conn.execute("SELECT id, speech_language_role FROM entry_template_fields ORDER BY id LIMIT 1").fetchone()
            set_schema_version(conn, LINKED_APPEND_SOURCE_SCHEMA_VERSION)
            set_metadata(conn, "app_data_version", "13.0")
            migration = MIGRATIONS[-1]
            original = migration["function"]
            def failing(connection):
                connection.execute("UPDATE entry_template_fields SET speech_language_role = 'none' WHERE id = ?", (field["id"],))
                set_metadata(connection, "app_data_version", APP_DATA_VERSION)
                raise RuntimeError("synthetic migration failure")
            migration["function"] = failing
            try:
                with self.assertRaisesRegex(RuntimeError, "synthetic migration failure"):
                    run_migrations(conn)
            finally:
                migration["function"] = original
            self.assertEqual(get_schema_version(conn), LINKED_APPEND_SOURCE_SCHEMA_VERSION)
            self.assertEqual(get_metadata(conn, "app_data_version"), "13.0")
            current_role = conn.execute("SELECT speech_language_role FROM entry_template_fields WHERE id = ?", (field["id"],)).fetchone()[0]
            self.assertEqual(current_role, field["speech_language_role"])

    def test_custom_required_role_is_unresolved_until_explicitly_configured(self) -> None:
        template_id = create_entry_template("Synthetic Custom", "", "English", "custom")
        field_id = create_template_field(template_id, "prompt", "Prompt", required=True)
        self.assertFalse(inspect_template_speech_readiness(template_id)["audio_ready"])
        set_template_field_speech_language_role(field_id, "entry")
        self.assertTrue(inspect_template_speech_readiness(template_id)["audio_ready"])
        with self.assertRaisesRegex(ValueError, "cannot use speech language role none"):
            set_template_field_speech_language_role(field_id, "none")
        with db.get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE entry_template_fields SET speech_language_role = 'invalid' WHERE id = ?",
                    (field_id,),
                )

    def test_english_entry_chinese_explanation_routes_in_template_order(self) -> None:
        entry_id = add_entry("English", "Chinese", "word", "study", "学习", example="optional")
        plan = build_entry_speech_plan(entry_id, providers=available_registry())
        self.assertTrue(plan.ready)
        self.assertEqual([unit.field_key for unit in plan.units], ["term", "meaning"])
        self.assertEqual([unit.language for unit in plan.units], ["en", "zh-CN"])
        self.assertEqual([unit.provider_id for unit in plan.units], ["kokoro", "windows-winrt"])

    def test_french_entry_english_explanation_routes_morphology(self) -> None:
        template = get_entry_template_by_name(FRENCH_VERB_PRESENT_TEMPLATE_NAME)
        entry_id = create_entry_with_template(
            {"template_id": template["id"], "language": "fr-FR", "explanation_language": "English", "entry_type": "verb"},
            {"infinitive": "parler", "meaning": "to speak", "je": "je parle", "tu": "tu parles",
             "il_elle_on": "il parle", "nous": "nous parlons", "vous": "vous parlez", "ils_elles": "ils parlent"},
        )
        plan = build_entry_speech_plan(entry_id, providers=available_registry())
        self.assertTrue(plan.ready)
        self.assertEqual([unit.field_key for unit in plan.units][:2], ["infinitive", "meaning"])
        self.assertEqual([unit.language for unit in plan.units], ["fr", "en", "fr", "fr", "fr", "fr", "fr", "fr"])
        self.assertEqual(plan.units[0].provider_id, "sherpa-onnx")
        self.assertEqual(plan.units[1].provider_id, "kokoro")

    def test_missing_value_unresolved_role_unsupported_language_and_yaoyao_unavailable_are_controlled(self) -> None:
        custom_id = create_entry_template("Unresolved Custom", "", "English", "custom")
        create_template_field(custom_id, "prompt", "Prompt", required=True)
        entry_id = create_entry_with_template(
            {"template_id": custom_id, "language": "English", "explanation_language": "English", "entry_type": "word"},
            {"prompt": "hello"}, manual_term="hello", manual_meaning="hello",
        )
        plan = build_entry_speech_plan(entry_id, providers=available_registry())
        self.assertEqual(plan.issues[0].code, "required_field_role_unresolved")

        unsupported = add_entry("German", "English", "word", "hallo", "hello")
        self.assertIn("unsupported_language", {issue.code for issue in build_entry_speech_plan(unsupported, providers=available_registry()).issues})

        mandarin = add_entry("English", "Chinese", "word", "learn", "学习")
        unavailable = build_entry_speech_plan(mandarin, providers=available_registry(mandarin_available=False))
        self.assertIn("provider_unavailable", {issue.code for issue in unavailable.issues})
        self.assertNotIn("windows-winrt", [unit.provider_id for unit in unavailable.units if unit.language == "zh-CN"])

    def test_language_normalization_is_deterministic(self) -> None:
        self.assertEqual(normalize_supported_language("English"), "en")
        self.assertEqual(normalize_supported_language("fr_CA"), "fr")
        self.assertEqual(normalize_supported_language("Mandarin Chinese"), "zh-CN")
        self.assertIsNone(normalize_supported_language("German"))

    def test_template_definition_v2_round_trip_and_v1_safe_import(self) -> None:
        template_id = create_entry_template("Portable Speech", "", "English", "custom")
        create_template_field(template_id, "term", "Term", required=True, display_order=1, speech_language_role="entry")
        create_template_field(template_id, "meaning", "Meaning", required=True, display_order=2, speech_language_role="explanation")
        exported = export_template_definition_csv(template_id)
        reader = csv.DictReader(io.StringIO(exported.decode("utf-8-sig")))
        self.assertEqual(reader.fieldnames, TEMPLATE_DEFINITION_COLUMNS)
        self.assertEqual({row["speech_language_role"] for row in reader}, {"entry", "explanation"})

        second_path = Path(self.temp_dir.name) / "roundtrip.sqlite3"
        db.DB_PATH = second_path
        try:
            db.init_db()
            imported = import_template_definition_csv(exported)
            self.assertEqual(
                [row["speech_language_role"] for row in export_template_definition_rows(imported["template_id"])],
                ["entry", "explanation"],
            )
        finally:
            db.DB_PATH = self.test_db_path

        v1_rows = [{
            "definition_version": "1", "template_name": "Legacy V1", "template_description": "",
            "language": "English", "template_type": "custom", "field_key": "prompt",
            "field_label": "Prompt", "field_type": "text", "required": "1", "display_order": "1",
        }]
        preview = preview_template_definition_csv(rows_to_csv_bytes(v1_rows, TEMPLATE_DEFINITION_V1_COLUMNS))
        self.assertTrue(preview["can_import"])
        self.assertEqual(preview["fields"][0]["speech_language_role"], "unresolved")

    def test_provider_failure_does_not_mutate_learning_state(self) -> None:
        entry_id = add_entry("English", "English", "word", "safe", "safe")
        provider = FakeProvider("en", available=False)
        with db.get_connection() as conn:
            before = tuple(int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in (
                "quiz_sessions", "quiz_item_logs", "card_review_logs", "entry_change_events"
            ))
        result = provider.synthesize_one("safe", Path(self.temp_dir.name) / "not-created.wav")
        self.assertFalse(result.succeeded)
        with db.get_connection() as conn:
            after = tuple(int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in (
                "quiz_sessions", "quiz_item_logs", "card_review_logs", "entry_change_events"
            ))
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()

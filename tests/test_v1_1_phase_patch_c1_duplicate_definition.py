from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import db
from src.collections import create_collection, get_entries_in_collection
from src.entries import add_entry
from src.entry_templates import ensure_french_verb_present_template
from src.import_export import (
    DEFAULT_DUPLICATE_DEFINITION,
    DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM,
    DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM_MEANING,
    SUPPORTED_DUPLICATE_DEFINITIONS,
    build_entry_duplicate_key,
    build_import_preview,
    detect_duplicate_candidates,
    get_existing_entry_keys,
    import_collection_rows,
    import_general_entry_rows,
    import_template_entry_rows,
    rows_to_csv_bytes,
    validate_import_rows,
)


class TestDuplicateDefinitionContract(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "test_import.db"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _reset_db(self) -> None:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM entry_collections")
            conn.execute("DELETE FROM entry_field_values")
            conn.execute("DELETE FROM entries")
            conn.commit()

    # -- 1. Contract Constants & Key Building Truth ------------------------

    def test_contract_constants_and_default(self) -> None:
        self.assertEqual(DEFAULT_DUPLICATE_DEFINITION, "same_language_term_meaning")
        self.assertEqual(DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM_MEANING, "same_language_term_meaning")
        self.assertEqual(DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM, "same_language_term")
        self.assertIn("same_language_term_meaning", SUPPORTED_DUPLICATE_DEFINITIONS)
        self.assertIn("same_language_term", SUPPORTED_DUPLICATE_DEFINITIONS)

    def test_build_entry_duplicate_key_semantics(self) -> None:
        # Default (language, term, meaning)
        key_default = build_entry_duplicate_key(
            language="English",
            term="Bank",
            meaning="Financial institution",
        )
        self.assertEqual(key_default, ("english", "bank", "financial institution"))

        # Polysemy with different meanings:
        key_poly_1 = build_entry_duplicate_key("English", "Bank", "Financial institution", "same_language_term_meaning")
        key_poly_2 = build_entry_duplicate_key("English", "Bank", "Side of river", "same_language_term_meaning")
        self.assertNotEqual(key_poly_1, key_poly_2)

        # Under same_language_term: polysemy shares the same key
        key_term_1 = build_entry_duplicate_key("English", "Bank", "Financial institution", "same_language_term")
        key_term_2 = build_entry_duplicate_key("English", "Bank", "Side of river", "same_language_term")
        self.assertEqual(key_term_1, ("english", "bank"))
        self.assertEqual(key_term_1, key_term_2)

        # Cross-language homographs are NEVER equal under either definition
        key_en = build_entry_duplicate_key("English", "Pain", "Ache", "same_language_term")
        key_fr = build_entry_duplicate_key("French", "Pain", "Bread", "same_language_term")
        self.assertNotEqual(key_en, key_fr)
        self.assertEqual(key_en[0], "english")
        self.assertEqual(key_fr[0], "french")

    def test_build_entry_duplicate_key_invalid_definition_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_entry_duplicate_key("English", "test", "test", "unsupported_def")

    # -- 2. Existing DB Keys & In-File Duplicate Detection -----------------

    def test_detect_duplicates_in_file_and_against_db(self) -> None:
        # Seed existing entry in DB: English bank (financial institution)
        add_entry(
            language="English",
            explanation_language="English",
            entry_type="word",
            term="bank",
            meaning="financial institution",
        )

        rows = [
            # Row 1: same term, different meaning
            {"row_number": 2, "data": {"language": "English", "term": "bank", "meaning": "side of river"}},
            # Row 2: exact match to DB
            {"row_number": 3, "data": {"language": "English", "term": "bank", "meaning": "financial institution"}},
            # Row 3: French homograph
            {"row_number": 4, "data": {"language": "French", "term": "bank", "meaning": "side of river"}},
            # Row 4: in-file duplicate of Row 1
            {"row_number": 5, "data": {"language": "English", "term": "bank", "meaning": "side of river"}},
        ]

        # 1. Under default definition (same_language_term_meaning):
        existing_keys_default = get_existing_entry_keys(duplicate_definition="same_language_term_meaning")
        dups_default = detect_duplicate_candidates(rows, existing_keys_default, duplicate_definition="same_language_term_meaning")
        # Row 3 (exact DB match) and Row 5 (in-file dup of Row 1) are duplicates.
        # Row 2 (bank / side of river) is NOT a duplicate against DB.
        # Row 4 (French bank) is NOT a duplicate.
        self.assertEqual(dups_default, {3, 5})

        # 2. Under same_language_term:
        existing_keys_term = get_existing_entry_keys(duplicate_definition="same_language_term")
        dups_term = detect_duplicate_candidates(rows, existing_keys_term, duplicate_definition="same_language_term")
        # Row 2 (matches DB English bank), Row 3 (matches DB English bank), Row 5 (matches DB English bank)
        # Row 4 (French bank) is NOT a duplicate because language is French.
        self.assertEqual(dups_term, {2, 3, 5})

    # -- 3. Preview Consistency with Duplicate Definition ------------------

    def test_build_import_preview_respects_duplicate_definition(self) -> None:
        add_entry(
            language="English",
            explanation_language="English",
            entry_type="word",
            term="bank",
            meaning="financial institution",
        )

        csv_content = [
            {"language": "English", "term": "bank", "meaning": "side of river"},
            {"language": "English", "term": "spring", "meaning": "season"},
        ]
        csv_bytes = rows_to_csv_bytes(csv_content)

        # Preview with default definition
        preview_default = build_import_preview(csv_bytes, "test.csv")
        self.assertEqual(preview_default["summary"]["duplicate_candidate_count"], 0)
        self.assertEqual(preview_default["summary"]["valid_count"], 2)

        # Preview with same_language_term in options
        preview_term = build_import_preview(
            csv_bytes,
            "test.csv",
            options={"duplicate_definition": "same_language_term"},
        )
        self.assertEqual(preview_term["summary"]["duplicate_candidate_count"], 1)
        self.assertTrue(preview_term["valid_rows"][0]["duplicate_candidate"])
        self.assertFalse(preview_term["valid_rows"][1]["duplicate_candidate"])

    # -- 4. General Entry Writer Respects Definition & duplicate_handling --

    def test_import_general_entry_rows_respects_definition(self) -> None:
        rows = [
            {"row_number": 2, "data": {"language": "English", "term": "bank", "meaning": "side of river"}},
            {"row_number": 3, "data": {"language": "English", "term": "spring", "meaning": "season"}},
        ]

        # 1. Default definition: bank / side of river is NOT duplicate -> both imported
        self._reset_db()
        add_entry(
            language="English",
            explanation_language="English",
            entry_type="word",
            term="bank",
            meaning="financial institution",
        )
        res_default = import_general_entry_rows(
            rows,
            duplicate_handling="skip",
            duplicate_definition="same_language_term_meaning",
        )
        self.assertEqual(res_default["imported_count"], 2)
        self.assertEqual(res_default["skipped_duplicate_count"], 0)

        # 2. same_language_term definition: bank / side of river IS duplicate -> skipped
        self._reset_db()
        add_entry(
            language="English",
            explanation_language="English",
            entry_type="word",
            term="bank",
            meaning="financial institution",
        )

        res_term_skip = import_general_entry_rows(
            rows,
            duplicate_handling="skip",
            duplicate_definition="same_language_term",
        )
        self.assertEqual(res_term_skip["imported_count"], 1)
        self.assertEqual(res_term_skip["skipped_duplicate_count"], 1)
        self.assertEqual(res_term_skip["warnings"][0]["message"], "Skipped duplicate entry")

        # 3. same_language_term definition with import_anyway -> imported anyway
        self._reset_db()
        add_entry(
            language="English",
            explanation_language="English",
            entry_type="word",
            term="bank",
            meaning="financial institution",
        )

        res_term_anyway = import_general_entry_rows(
            rows,
            duplicate_handling="import_anyway",
            duplicate_definition="same_language_term",
        )
        self.assertEqual(res_term_anyway["imported_count"], 2)
        self.assertEqual(res_term_anyway["skipped_duplicate_count"], 0)
        self.assertTrue(any("Imported duplicate entry by user choice" in w["message"] for w in res_term_anyway["warnings"]))

    # -- 5. Template & Collection Writers Respect Duplicate Definition -----

    def test_import_template_and_collection_rows_respect_definition(self) -> None:
        template_id = ensure_french_verb_present_template()

        seed_rows = [
            {
                "row_number": 2,
                "data": {
                    "language": "French",
                    "template_name": "French Verb Present",
                    "template_type": "french_verb_present",
                    "term": "parler",
                    "meaning": "to speak",
                    "field:meaning": "to speak",
                    "field:infinitive": "parler",
                    "field:je": "parle",
                    "field:tu": "parles",
                    "field:il_elle_on": "parle",
                    "field:nous": "parlons",
                    "field:vous": "parlez",
                    "field:ils_elles": "parlent",
                },
            }
        ]

        incoming_rows = [
            {
                "row_number": 2,
                "data": {
                    "language": "French",
                    "template_name": "French Verb Present",
                    "template_type": "french_verb_present",
                    "term": "parler",
                    "meaning": "to talk",
                    "field:meaning": "to talk",
                    "field:infinitive": "parler",
                    "field:je": "parle",
                    "field:tu": "parles",
                    "field:il_elle_on": "parle",
                    "field:nous": "parlons",
                    "field:vous": "parlez",
                    "field:ils_elles": "parlent",
                },
            }
        ]

        # 1. Under default definition (same_language_term_meaning) -> NOT duplicate
        self._reset_db()
        import_template_entry_rows(seed_rows)
        res_tpl_default = import_template_entry_rows(
            incoming_rows,
            duplicate_handling="skip",
            duplicate_definition="same_language_term_meaning",
        )
        self.assertEqual(res_tpl_default["imported_count"], 1)
        self.assertEqual(res_tpl_default["skipped_duplicate_count"], 0)

        # 2. Under same_language_term definition -> IS duplicate and skipped
        self._reset_db()
        import_template_entry_rows(seed_rows)
        res_tpl_term = import_template_entry_rows(
            incoming_rows,
            duplicate_handling="skip",
            duplicate_definition="same_language_term",
        )
        self.assertEqual(res_tpl_term["imported_count"], 0)
        self.assertEqual(res_tpl_term["skipped_duplicate_count"], 1)

        # 3. In Collection Writer:
        self._reset_db()
        import_template_entry_rows(seed_rows)
        col_id = create_collection("Test Col", "")
        res_col_term = import_collection_rows(
            incoming_rows,
            import_mode="append_to_existing",
            duplicate_handling="skip",
            target_collection_id=col_id,
            duplicate_definition="same_language_term",
        )
        self.assertEqual(res_col_term["imported_entry_count"], 0)
        self.assertEqual(res_col_term["skipped_duplicate_count"], 1)


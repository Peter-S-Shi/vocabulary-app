from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import db
from src.collections import create_collection, get_entries_in_collection
from src.entries import add_entry, search_entries
from src.entry_templates import ensure_french_verb_present_template
from src.import_export import (
    DEFAULT_DUPLICATE_DEFINITION,
    DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM,
    DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM_MEANING,
    rows_to_csv_bytes,
)
from src.ui_desktop.controllers.data_tools_controller import (
    DUPLICATE_DEFINITION_LABELS,
    DataToolsController,
)

try:
    from PySide6.QtWidgets import QApplication, QComboBox
    from src.ui_desktop.views.data_tools_view import _ImportDialog
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False


def _qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


class TestNativeDuplicateDefinitionUX(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "test_data_tools_duplicate.db"
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

    # -- 1. Controller Default State & Consistency -------------------------

    def test_controller_default_duplicate_definition(self) -> None:
        controller = DataToolsController()
        self.assertEqual(controller.duplicate_definition, DEFAULT_DUPLICATE_DEFINITION)
        self.assertEqual(controller.duplicate_definition, DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM_MEANING)
        self.assertEqual(controller.duplicate_handling, "skip")

    def test_controller_preview_and_confirm_use_same_definition_default(self) -> None:
        # Seed existing bank / financial institution
        add_entry(
            language="English",
            explanation_language="English",
            entry_type="word",
            term="bank",
            meaning="financial institution",
        )

        csv_bytes = rows_to_csv_bytes([
            {"language": "English", "term": "bank", "meaning": "side of river"},
        ])

        controller = DataToolsController()
        controller.load_file(csv_bytes, "entries.csv")
        controller.run_preview()

        # Under default same_language_term_meaning, different meaning is NOT duplicate
        self.assertIsNotNone(controller.preview)
        self.assertEqual(controller.preview["summary"]["duplicate_candidate_count"], 0)
        self.assertTrue(controller.can_confirm_import())

        result = controller.confirm_import()
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["skipped_duplicate_count"], 0)
        self.assertEqual(len(search_entries()), 2)

    # -- 2. Term-Only Mode Detection and Skip in Preview and Confirm -------

    def test_controller_term_only_mode_affects_preview_and_confirm(self) -> None:
        add_entry(
            language="English",
            explanation_language="English",
            entry_type="word",
            term="bank",
            meaning="financial institution",
        )

        csv_bytes = rows_to_csv_bytes([
            {"language": "English", "term": "bank", "meaning": "side of river"},
            {"language": "English", "term": "spring", "meaning": "season"},
        ])

        controller = DataToolsController()
        controller.set_duplicate_definition(DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM)
        controller.load_file(csv_bytes, "entries.csv")
        controller.run_preview()

        self.assertIsNotNone(controller.preview)
        self.assertEqual(controller.preview["summary"]["duplicate_candidate_count"], 1)
        self.assertEqual(controller.preview["summary"]["valid_count"], 2)

        result = controller.confirm_import()
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["skipped_duplicate_count"], 1)
        self.assertEqual(len(search_entries()), 2)  # bank (existing) + spring (imported)

    def test_cross_language_homograph_isolation(self) -> None:
        add_entry(
            language="English",
            explanation_language="English",
            entry_type="word",
            term="pain",
            meaning="physical suffering",
        )

        csv_bytes = rows_to_csv_bytes([
            {"language": "French", "term": "pain", "meaning": "bread"},
        ])

        controller = DataToolsController()
        controller.set_duplicate_definition(DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM)
        controller.load_file(csv_bytes, "entries.csv")
        controller.run_preview()

        self.assertEqual(controller.preview["summary"]["duplicate_candidate_count"], 0)
        result = controller.confirm_import()
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["skipped_duplicate_count"], 0)

    # -- 3. Preview State Invalidation on Definition Change ----------------

    def test_definition_change_invalidates_preview_and_confirm_readiness(self) -> None:
        csv_bytes = rows_to_csv_bytes([
            {"language": "English", "term": "bank", "meaning": "financial institution"},
        ])

        controller = DataToolsController()
        controller.load_file(csv_bytes, "entries.csv")
        controller.run_preview()

        self.assertIsNotNone(controller.preview)
        self.assertTrue(controller.can_confirm_import())

        emitted = []
        controller.import_state_changed.connect(lambda: emitted.append(True))

        # Changing duplicate definition MUST clear preview and disable confirm
        controller.set_duplicate_definition(DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM)
        self.assertTrue(len(emitted) > 0)
        self.assertIsNone(controller.preview)
        self.assertFalse(controller.can_confirm_import())

        # Calling confirm_import without re-previewing must raise ValueError
        with self.assertRaises(ValueError):
            controller.confirm_import()

        # Re-running preview re-enables confirm
        controller.run_preview()
        self.assertIsNotNone(controller.preview)
        self.assertTrue(controller.can_confirm_import())

        result = controller.confirm_import()
        self.assertEqual(result["imported_count"], 1)

    def test_handling_change_preserves_preview(self) -> None:
        csv_bytes = rows_to_csv_bytes([
            {"language": "English", "term": "bank", "meaning": "financial institution"},
        ])

        controller = DataToolsController()
        controller.load_file(csv_bytes, "entries.csv")
        controller.run_preview()

        self.assertIsNotNone(controller.preview)
        self.assertTrue(controller.can_confirm_import())

        # Changing duplicate handling must NOT clear preview
        controller.set_duplicate_handling("import_anyway")
        self.assertIsNotNone(controller.preview)
        self.assertTrue(controller.can_confirm_import())

    # -- 4. Multi-Mode Writer Definition Forwarding ------------------------

    def test_template_aware_and_collection_modes_forward_definition(self) -> None:
        ensure_french_verb_present_template()

        # Seed existing verb: parler / to speak
        seed_csv = rows_to_csv_bytes([
            {
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
            }
        ])

        incoming_csv = rows_to_csv_bytes([
            {
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
            }
        ])

        # 1. Seed DB
        ctrl_seed = DataToolsController()
        ctrl_seed.set_mode("template_aware")
        ctrl_seed.load_file(seed_csv, "seed.csv")
        ctrl_seed.run_preview()
        ctrl_seed.confirm_import()

        # 2. Template-aware mode with same_language_term -> skipped
        ctrl_tpl = DataToolsController()
        ctrl_tpl.set_mode("template_aware")
        ctrl_tpl.set_duplicate_definition(DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM)
        ctrl_tpl.load_file(incoming_csv, "incoming.csv")
        ctrl_tpl.run_preview()
        self.assertEqual(ctrl_tpl.preview["summary"]["duplicate_candidate_count"], 1)
        res_tpl = ctrl_tpl.confirm_import()
        self.assertEqual(res_tpl["imported_count"], 0)
        self.assertEqual(res_tpl["skipped_duplicate_count"], 1)

        # 3. Collection mode with same_language_term -> skipped
        col_id = create_collection("Verbs", "")
        ctrl_col = DataToolsController()
        ctrl_col.set_mode("collection")
        ctrl_col.set_target_collection(col_id)
        ctrl_col.set_duplicate_definition(DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM)
        ctrl_col.load_file(incoming_csv, "incoming.csv")
        ctrl_col.run_preview()
        self.assertEqual(ctrl_col.preview["summary"]["duplicate_candidate_count"], 1)
        res_col = ctrl_col.confirm_import()
        self.assertEqual(res_col["imported_entry_count"], 0)
        self.assertEqual(res_col["skipped_duplicate_count"], 1)

    # -- 5. Native View Structural Coverage --------------------------------

    @unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed")
    def test_import_dialog_has_two_separate_duplicate_controls(self) -> None:
        _qt_app()
        controller = DataToolsController()
        dialog = _ImportDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        # 1. Definition combo
        def_combo = dialog.findChild(QComboBox, "data-tools-duplicate-definition-combo")
        self.assertIsNotNone(def_combo)
        self.assertEqual(def_combo.count(), 2)
        self.assertEqual(def_combo.currentData(), DEFAULT_DUPLICATE_DEFINITION)
        self.assertEqual(def_combo.currentText(), "Same language + same term + same meaning")

        # 2. Handling combo
        hand_combo = dialog.findChild(QComboBox, "data-tools-duplicate-handling-combo")
        self.assertIsNotNone(hand_combo)
        self.assertEqual(hand_combo.count(), 2)
        self.assertEqual(hand_combo.currentData(), "skip")
        self.assertEqual(hand_combo.currentText(), "Skip duplicates")

        # 3. Changing definition via view updates controller and invalidates preview
        csv_bytes = rows_to_csv_bytes([{"language": "English", "term": "a", "meaning": "b"}])
        controller.load_file(csv_bytes, "test.csv")
        controller.run_preview()
        self.assertIsNotNone(controller.preview)

        def_combo.setCurrentIndex(1)
        self.assertEqual(controller.duplicate_definition, DUPLICATE_DEFINITION_SAME_LANGUAGE_TERM)
        self.assertIsNone(controller.preview)
        self.assertFalse(dialog._confirm_button.isEnabled())

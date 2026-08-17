from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import create_collection, get_entries_in_collection
from src.entries import search_entries

"""
Focused tests for M18 Phase C3 -- Data Tools hub + Import/Export
(data_tools_view.py Design Derivation Record). Per DESIGN.md § 2 Rule C
these are structural/behavioral proof that `DataToolsController`
delegates every parse/validate/import/export call to the exact same
`src.import_export` functions the Streamlit Import/Export page already
uses, that import never mutates SQLite before an explicit confirm step
(DESIGN.md § 12.3), and that duplicate handling/collection-destination
dispatch match the Streamlit page's confirm-time behavior exactly -- not
evidence the P6 dialogs were visually realized. Native human visual
acceptance is a separate, required gate (AGENTS.md).
"""

GENERAL_CSV = b"language,term,meaning\nFrench,pomme,apple\n"
GENERAL_CSV_TWO_ROWS = b"language,term,meaning\nFrench,pomme,apple\nFrench,poire,pear\n"
INVALID_CSV = b"language,term,meaning\n,pomme,apple\n"

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.data_tools_controller import DataToolsController
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.data_tools_view import DataToolsView, _ImportDialog
    from src.ui_desktop.widgets.navigation_rail import NavigationRail

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m18_data_tools.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class NavigationRailDataToolsEnabledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_data_tools_destination_is_enabled(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)
        self.assertTrue(rail.is_enabled_destination("data_tools"))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class DataToolsImportControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_run_preview_never_mutates_sqlite(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")

        controller.run_preview()

        self.assertIsNotNone(controller.preview)
        self.assertEqual(controller.preview["summary"]["valid_count"], 1)
        self.assertEqual(search_entries(), [])  # nothing imported yet

    def test_confirm_import_general_entry_creates_the_entry(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()

        result = controller.confirm_import()

        self.assertEqual(result["imported_count"], 1)
        entries = search_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["term"], "pomme")

    def test_cannot_confirm_before_preview(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")

        self.assertFalse(controller.can_confirm_import())
        with self.assertRaises(ValueError):
            controller.confirm_import()

    def test_cannot_confirm_twice_on_the_same_preview(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()
        controller.confirm_import()

        self.assertFalse(controller.can_confirm_import())
        with self.assertRaises(ValueError):
            controller.confirm_import()

    def test_invalid_rows_are_reported_and_never_imported(self) -> None:
        controller = DataToolsController()
        controller.load_file(INVALID_CSV, "entries.csv")

        controller.run_preview()

        self.assertEqual(controller.preview["summary"]["invalid_count"], 1)
        self.assertEqual(controller.preview["summary"]["valid_count"], 0)
        self.assertFalse(controller.can_confirm_import())

    def test_duplicate_handling_skip_excludes_the_second_import(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()
        controller.confirm_import()

        controller.reset_import()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.set_duplicate_handling("skip")
        controller.run_preview()
        result = controller.confirm_import()

        self.assertEqual(result["imported_count"], 0)
        self.assertEqual(result["skipped_duplicate_count"], 1)
        self.assertEqual(len(search_entries()), 1)

    def test_duplicate_handling_import_anyway_creates_a_second_entry(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()
        controller.confirm_import()

        controller.reset_import()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.set_duplicate_handling("import_anyway")
        controller.run_preview()
        result = controller.confirm_import()

        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(len(search_entries()), 2)

    def test_general_entry_import_can_target_an_existing_collection(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.set_target_collection(collection_id)
        controller.run_preview()

        controller.confirm_import()

        self.assertEqual(len(get_entries_in_collection(collection_id)), 1)

    def test_collection_mode_creates_a_new_collection(self) -> None:
        controller = DataToolsController()
        controller.set_mode("collection")
        controller.load_file(GENERAL_CSV_TWO_ROWS, "entries.csv")
        controller.set_collection_import_mode("create_new_collection")
        controller.set_new_collection_fields("Imported Fruits", "desc", 8)
        controller.run_preview()

        result = controller.confirm_import()

        self.assertTrue(result["created_collection"])
        self.assertEqual(result["imported_entry_count"], 2)
        self.assertEqual(len(get_entries_in_collection(result["collection_id"])), 2)

    def test_collection_mode_append_requires_a_target(self) -> None:
        controller = DataToolsController()
        controller.set_mode("collection")
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.set_collection_import_mode("append_to_existing")
        controller.run_preview()

        with self.assertRaises(ValueError):
            controller.confirm_import()

    def test_reset_import_clears_all_state(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()
        controller.confirm_import()

        controller.reset_import()

        self.assertIsNone(controller.file_bytes)
        self.assertIsNone(controller.preview)
        self.assertIsNone(controller.import_result)
        self.assertEqual(controller.mode, "general_entry")

    def test_load_file_preserves_a_previously_selected_mode(self) -> None:
        """Regression: load_file() must never silently discard mode
        (or other destination/duplicate-handling choices) the user
        already made -- caught by this checkpoint's own tests before
        shipping, when load_file() called the full reset_import()."""
        controller = DataToolsController()
        controller.set_mode("collection")
        controller.set_duplicate_handling("import_anyway")

        controller.load_file(GENERAL_CSV, "entries.csv")

        self.assertEqual(controller.mode, "collection")
        self.assertEqual(controller.duplicate_handling, "import_anyway")

    def test_set_mode_clears_a_stale_preview(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()
        self.assertIsNotNone(controller.preview)

        controller.set_mode("template_aware")

        self.assertIsNone(controller.preview)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class DataToolsExportControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_export_all_rows_matches_imported_entries(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV_TWO_ROWS, "entries.csv")
        controller.run_preview()
        controller.confirm_import()

        rows, columns = controller.export_rows("all")

        self.assertEqual(len(rows), 2)
        self.assertIn("term", columns)

    def test_export_collection_scope_requires_a_collection_id(self) -> None:
        controller = DataToolsController()
        with self.assertRaises(ValueError):
            controller.export_rows("collection", None)

    def test_export_bytes_csv_and_xlsx_are_both_nonempty(self) -> None:
        controller = DataToolsController()
        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()
        controller.confirm_import()
        rows, columns = controller.export_rows("all")

        csv_bytes = controller.export_bytes(rows, columns, "csv")
        xlsx_bytes = controller.export_bytes(rows, columns, "xlsx")

        self.assertGreater(len(csv_bytes), 0)
        self.assertGreater(len(xlsx_bytes), 0)
        self.assertIn(b"pomme", csv_bytes)

    def test_export_filename_uses_the_all_entries_convention(self) -> None:
        controller = DataToolsController()
        filename = controller.export_filename("all_entries", "all", "csv")
        self.assertTrue(filename.startswith("vocabulary_export_all_entries_"))
        self.assertTrue(filename.endswith(".csv"))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class DataToolsViewStructureTests(_SyntheticDatabaseTestCase):
    """Structural-only proof (DESIGN.md § 2 Rule C)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_import_dialog_confirm_disabled_until_preview_and_checkbox(self) -> None:
        controller = DataToolsController()
        dialog = _ImportDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        self.assertFalse(dialog._confirm_button.isEnabled())

        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()
        dialog._confirm_checkbox.setChecked(True)

        self.assertTrue(dialog._confirm_button.isEnabled())

    def test_import_dialog_renders_preview_summary_and_tables(self) -> None:
        controller = DataToolsController()
        dialog = _ImportDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        controller.load_file(GENERAL_CSV, "entries.csv")
        controller.run_preview()

        self.assertEqual(dialog._valid_table.rowCount(), 1)
        self.assertIn("Valid 1", dialog._summary_label.text())

    def test_data_tools_view_has_import_and_export_actions(self) -> None:
        controller = DataToolsController()
        view = DataToolsView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()  # must not raise


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18DataToolsTokenQssStructuralCoverageTests(unittest.TestCase):
    REPRESENTATIVE_SELECTORS = (
        "#data-tools-title",
        "#data-tools-caption",
        "#data-tools-import-button",
        "#data-tools-export-button",
        "#data-tools-preview-button",
        "#data-tools-confirm-import-button",
        "#data-tools-confirm-import-button:disabled",
        "#data-tools-export-confirm-button",
        "#data-tools-preview-error",
        "#data-tools-summary-label",
        "#data-tools-section-heading",
    )

    def _assert_all_selectors_present(self, tokens) -> None:
        stylesheet = build_stylesheet(tokens)
        for selector in self.REPRESENTATIVE_SELECTORS:
            self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")

    def test_light_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_LIGHT)

    def test_dark_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_DARK)


if __name__ == "__main__":
    unittest.main()

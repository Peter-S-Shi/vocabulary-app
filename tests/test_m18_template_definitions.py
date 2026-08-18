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
from src.entry_templates import create_entry_template, create_template_field, delete_entry_template, get_entry_templates
from src.template_definitions import TemplateDefinitionError

"""
Focused tests for M18 Phase C4 -- Template Definition CSV import/export
(data_tools_view.py's `_TemplateDefinitionDialog` Design Derivation
Record). Per DESIGN.md § 2 Rule C these are structural/behavioral proof
that `DataToolsController` delegates every export/preview/import call to
the exact same `src.template_definitions` functions, and that import
never creates a Template before an explicit confirm step -- not evidence
the P6 dialog was visually realized. Native human visual acceptance is a
separate, required gate (AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.data_tools_controller import DataToolsController
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.data_tools_view import _TemplateDefinitionDialog

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
        db.DB_PATH = self.root / "m18_template_definitions.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_source_template(self) -> int:
        template_id = create_entry_template(name="Weather Words", description="", language="French", template_type="custom")
        create_template_field(template_id, "condition", "Condition", "text", True, 0)
        return template_id


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class DataToolsTemplateDefinitionControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_export_round_trips_through_preview_and_import(self) -> None:
        source_id = self._make_source_template()
        controller = DataToolsController()

        csv_bytes = controller.export_template_definition(source_id)
        delete_entry_template(source_id)  # avoid a self-name-conflict on re-import
        controller.load_template_definition_file(csv_bytes, "weather_words_template_definition.csv")
        controller.run_template_definition_preview()

        self.assertTrue(controller.template_definition_preview["can_import"])
        self.assertEqual(controller.template_definition_preview["template"]["name"], "Weather Words")

    def test_confirm_creates_a_new_template_distinct_from_the_source(self) -> None:
        source_id = self._make_source_template()
        controller = DataToolsController()
        csv_bytes = controller.export_template_definition(source_id)
        delete_entry_template(source_id)  # avoid a self-name-conflict on re-import
        controller.load_template_definition_file(csv_bytes, "wwtd.csv")
        controller.run_template_definition_preview()

        result = controller.confirm_template_definition_import()

        self.assertEqual(result["field_count"], 1)
        template_names = {t["id"]: t["name"] for t in get_entry_templates()}
        self.assertEqual(template_names[result["template_id"]], "Weather Words")
        self.assertFalse(bool(result["template"]["is_system"]))

    def test_run_preview_never_creates_a_template(self) -> None:
        source_id = self._make_source_template()
        controller = DataToolsController()
        csv_bytes = controller.export_template_definition(source_id)
        controller.load_template_definition_file(csv_bytes, "wwtd.csv")
        before_count = len(get_entry_templates())

        controller.run_template_definition_preview()

        self.assertEqual(len(get_entry_templates()), before_count)

    def test_cannot_confirm_before_a_preview(self) -> None:
        controller = DataToolsController()
        controller.load_template_definition_file(b"not,a,valid,csv\n", "bad.csv")

        self.assertFalse(controller.can_confirm_template_definition_import())
        with self.assertRaises(TemplateDefinitionError):
            controller.confirm_template_definition_import()

    def test_cannot_confirm_twice_on_the_same_preview(self) -> None:
        source_id = self._make_source_template()
        controller = DataToolsController()
        csv_bytes = controller.export_template_definition(source_id)
        delete_entry_template(source_id)  # avoid a self-name-conflict on re-import
        controller.load_template_definition_file(csv_bytes, "wwtd.csv")
        controller.run_template_definition_preview()
        controller.confirm_template_definition_import()

        self.assertFalse(controller.can_confirm_template_definition_import())
        with self.assertRaises(TemplateDefinitionError):
            controller.confirm_template_definition_import()

    def test_name_conflict_is_reported_and_blocks_import(self) -> None:
        source_id = self._make_source_template()
        controller = DataToolsController()
        csv_bytes = controller.export_template_definition(source_id)

        # Re-importing the exact same definition without renaming
        # collides with the still-existing source Template's name.
        controller.load_template_definition_file(csv_bytes, "wwtd.csv")
        controller.run_template_definition_preview()

        self.assertFalse(controller.template_definition_preview["can_import"])
        self.assertTrue(controller.template_definition_preview["name_conflict"])
        self.assertFalse(controller.can_confirm_template_definition_import())

    def test_export_filename_uses_the_template_name(self) -> None:
        controller = DataToolsController()
        filename = controller.template_definition_export_filename("Weather Words")
        self.assertTrue(filename.endswith("_template_definition.csv"))
        self.assertIn("weather", filename.lower())

    def test_load_template_definition_file_resets_prior_state(self) -> None:
        source_id = self._make_source_template()
        controller = DataToolsController()
        csv_bytes = controller.export_template_definition(source_id)
        delete_entry_template(source_id)  # avoid a self-name-conflict on re-import
        controller.load_template_definition_file(csv_bytes, "wwtd.csv")
        controller.run_template_definition_preview()
        controller.confirm_template_definition_import()
        self.assertIsNotNone(controller.template_definition_result)

        controller.load_template_definition_file(csv_bytes, "wwtd2.csv")

        self.assertIsNone(controller.template_definition_preview)
        self.assertIsNone(controller.template_definition_result)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TemplateDefinitionDialogStructureTests(_SyntheticDatabaseTestCase):
    """Structural-only proof (DESIGN.md § 2 Rule C)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_confirm_disabled_until_valid_preview_and_checkbox(self) -> None:
        source_id = self._make_source_template()
        controller = DataToolsController()
        dialog = _TemplateDefinitionDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog._confirm_button.isEnabled())

        csv_bytes = controller.export_template_definition(source_id)
        delete_entry_template(source_id)  # avoid a self-name-conflict on re-import
        controller.load_template_definition_file(csv_bytes, "wwtd.csv")
        controller.run_template_definition_preview()
        dialog._confirm_checkbox.setChecked(True)

        self.assertTrue(dialog._confirm_button.isEnabled())

    def test_export_template_combo_lists_existing_templates(self) -> None:
        self._make_source_template()
        controller = DataToolsController()
        dialog = _TemplateDefinitionDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        names = {dialog._export_template_combo.itemText(i) for i in range(dialog._export_template_combo.count())}
        self.assertIn("Weather Words", names)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18TemplateDefinitionTokenQssStructuralCoverageTests(unittest.TestCase):
    REPRESENTATIVE_SELECTORS = (
        "#data-tools-template-definition-button",
        "#data-tools-template-definition-export-button",
        "#data-tools-template-definition-preview-button",
        "#data-tools-template-definition-confirm-button",
        "#data-tools-template-definition-confirm-button:disabled",
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

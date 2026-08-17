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
from src.entries import create_entry_with_template
from src.entry_templates import (
    create_entry_template,
    create_template_field,
    ensure_general_entry_template,
    get_entry_template,
    get_template_fields,
)

"""
Focused tests for M18.1 Template Manager + Template Editor
(templates_view.py Design Derivation Record). Per DESIGN.md § 2 Rule C
these are structural/behavioral proof that `TemplatesController` calls
the exact same `src.entry_templates` functions the Streamlit Templates
page already uses, including its in-use safety gates -- not evidence that
the P2/P5 dialogs were visually realized. Native human visual acceptance
is a separate, required gate (AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.templates_controller import TemplatesController
    from src.ui_desktop.state.app_state import Workspace
    from src.ui_desktop.views.templates_view import (
        TemplatesView,
        _TemplateEditorDialog,
        _TemplateFieldDialog,
    )
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
        db.DB_PATH = self.root / "m18_template_manager.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class NavigationRailTemplatesEnabledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_templates_destination_is_enabled(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)
        self.assertTrue(rail.is_enabled_destination("templates"))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TemplatesControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_create_new_template_selects_and_appears_in_list(self) -> None:
        controller = TemplatesController()
        controller.refresh()

        template_id = controller.create_new_template("Weather Words", "Weather vocab", "French", "custom")

        self.assertEqual(controller.selected_id, template_id)
        self.assertIn(template_id, {t["id"] for t in controller.templates})
        stored = get_entry_template(template_id)
        self.assertEqual(stored["name"], "Weather Words")
        self.assertFalse(stored["is_system"])

    def test_create_new_template_rejects_duplicate_name(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        controller.create_new_template("Animals", "", None, "custom")
        with self.assertRaises(ValueError):
            controller.create_new_template("Animals", "", None, "custom")

    def test_update_selected_template_persists(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        template_id = controller.create_new_template("Numbers", "", None, "custom")

        controller.update_selected_template("Numbers (renamed)", "Counting", "French", "custom")

        stored = get_entry_template(template_id)
        self.assertEqual(stored["name"], "Numbers (renamed)")
        self.assertEqual(stored["language"], "French")

    def test_update_selected_template_rejects_system_template(self) -> None:
        system_template_id = ensure_general_entry_template()
        controller = TemplatesController()
        controller.refresh()
        controller.select_template(system_template_id)

        with self.assertRaises(ValueError):
            controller.update_selected_template("New Name", "", None, "custom")

    def test_create_and_delete_field_round_trip(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        controller.create_new_template("Verbs", "", "French", "custom")

        field_id = controller.create_field("infinitive", "Infinitive", "text", True, 0)
        self.assertEqual(len(controller.selected_fields()), 1)

        deleted = controller.delete_field(field_id)
        self.assertTrue(deleted)
        self.assertEqual(len(controller.selected_fields()), 0)

    def test_create_field_rejects_duplicate_key(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        controller.create_new_template("Nouns", "", "French", "custom")
        controller.create_field("gender", "Gender", "text", True, 0)

        with self.assertRaises(ValueError):
            controller.create_field("gender", "Gender Again", "text", True, 1)

    def test_can_delete_selected_template_false_when_in_use(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        template_id = controller.create_new_template("Fruits", "", "French", "custom")
        controller.create_field("name", "Name", "text", True, 0)

        self.assertTrue(controller.can_delete_selected_template())

        create_entry_with_template(
            entry_data={
                "template_id": template_id,
                "language": "French",
                "explanation_language": "English",
                "entry_type": "word",
                "status": "new",
            },
            template_values={"name": "pomme"},
            manual_meaning="apple",
        )

        self.assertFalse(controller.can_delete_selected_template())

    def test_delete_field_blocked_when_field_has_values(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        template_id = controller.create_new_template("Colors", "", "French", "custom")
        field_id = controller.create_field("name", "Name", "text", True, 0)
        create_entry_with_template(
            entry_data={
                "template_id": template_id,
                "language": "French",
                "explanation_language": "English",
                "entry_type": "word",
                "status": "new",
            },
            template_values={"name": "rouge"},
            manual_meaning="red",
        )

        self.assertTrue(controller.field_has_values(field_id))
        deleted = controller.delete_field(field_id)
        self.assertFalse(deleted)
        self.assertEqual(len(controller.selected_fields()), 1)

    def test_system_template_field_writes_are_rejected(self) -> None:
        system_template_id = ensure_general_entry_template()
        controller = TemplatesController()
        controller.refresh()
        controller.select_template(system_template_id)

        with self.assertRaises(ValueError):
            controller.create_field("extra", "Extra", "text", False, 99)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TemplatesViewStructureTests(_SyntheticDatabaseTestCase):
    """Structural-only proof (DESIGN.md § 2 Rule C)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_view_table_lists_templates_after_refresh(self) -> None:
        create_entry_template(name="Places", description="", language="French", template_type="custom")
        controller = TemplatesController()
        view = TemplatesView(controller)
        self.addCleanup(view.deleteLater)

        view.refresh()

        self.assertGreaterEqual(view._table.rowCount(), 1)

    def test_editor_dialog_reflects_selected_template_and_fields(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        template_id = controller.create_new_template("Shapes", "", "French", "custom")
        controller.create_field("shape_name", "Shape Name", "text", True, 0)

        dialog = _TemplateEditorDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog._name_input.text(), "Shapes")
        self.assertEqual(dialog._fields_table.rowCount(), 1)
        self.assertTrue(dialog._delete_template_button.isEnabled())

    def test_editor_dialog_disables_writes_for_system_template(self) -> None:
        system_template_id = ensure_general_entry_template()
        controller = TemplatesController()
        controller.refresh()
        controller.select_template(system_template_id)

        dialog = _TemplateEditorDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        self.assertFalse(dialog._save_button.isEnabled())
        self.assertFalse(dialog._add_field_button.isEnabled())
        self.assertFalse(dialog._delete_template_button.isEnabled())

    def test_field_dialog_locks_key_on_edit(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        controller.create_new_template("Weather", "", "French", "custom")
        field_id = controller.create_field("condition", "Condition", "text", True, 0)
        field = get_template_fields(controller.selected_id)[0]
        self.assertEqual(int(field["id"]), field_id)

        dialog = _TemplateFieldDialog(controller, field=field, parent=None)
        self.addCleanup(dialog.deleteLater)

        self.assertFalse(dialog._key_input.isEnabled())
        self.assertEqual(dialog._key_input.text(), "condition")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QPushButton

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import create_collection
from src.entry_templates import create_entry_template

"""
Human Gate 1 corrective pass for M18.1 (Collection Manager / Card
Organization / Template Manager / Template Editor).

Native visual acceptance FAILed: in Light Mode, the new controls this
checkpoint added (New Collection, Edit, Organize Entries, Delete,
per-Card Rename, and every Templates workspace/Editor action) rendered
with effectively no discoverable/usable visual treatment, and the
Templates table exposed no discoverable entry point into an existing
Template besides an undocumented double-click.

Root cause (the same class of defect the M16.2 closure already
documented for Today/Entries navigation actions, and theme_manager.py's
own `QDialog {{` docstring warns about): every button/control this
checkpoint introduced had no explicit QSS coverage in
`theme_manager.py`, so once `QApplication.setStyleSheet()` is active
application-wide, those controls silently lost their QPalette-resolved
foreground instead of falling back to a native, legible appearance.

Per DESIGN.md § 2 Rule C, `TokenQssStructuralCoverageTests`-style
selector-presence checks are structural evidence only -- they prove the
corrective QSS rules exist and stay wired to real token values, not that
the fix reads correctly on a real screen. The `templates-open-button`
discoverability tests below are genuine behavioral coverage of the
missing-entry-point finding. Native re-acceptance in real Light and Dark
windows remains the closing gate (AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.collections_controller import CollectionsController
    from src.ui_desktop.controllers.templates_controller import TemplatesController
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.collections_view import CollectionsView, _CollectionEditorDialog
    from src.ui_desktop.views.templates_view import TemplatesView, _TemplateEditorDialog

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
        db.DB_PATH = self.root / "m18_contrast_corrective.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18TokenQssStructuralCoverageTests(unittest.TestCase):
    """Every new M18.1 control's object-name selector must be themed --
    checked once per Appearance, since the M16.2/M17 defect class only
    ever showed up in one Appearance at a time."""

    REPRESENTATIVE_SELECTORS = (
        "#collections-new-button",
        "#collections-edit-button",
        "#collections-organize-button",
        # collections-delete-button/collections-delete-confirm-button/
        # collections-organize-remove-button intentionally have no
        # dedicated ID rule -- they reuse the shared
        # `[destructive="true"]` property selector (DestructivePropertyWiringTests
        # below verifies the property is actually set on them).
        "#collections-card-rename-button",
        "#collections-editor-save-button",
        "#collections-organize-move-button",
        "#templates-title",
        "#templates-new-button",
        "#templates-open-button",
        "#templates-open-button:disabled",
        "#templates-new-create-button",
        "#templates-field-save-button",
        "#templates-editor-save-button",
        "#templates-editor-save-button:disabled",
        "#templates-editor-add-field-button",
        "#templates-editor-edit-field-button",
        "#templates-editor-fields-heading",
        "#templates-editor-system-notice",
        "QDialog QSpinBox",
        'QPushButton[destructive="true"]:disabled',
    )

    def _assert_all_selectors_present(self, tokens) -> None:
        stylesheet = build_stylesheet(tokens)
        for selector in self.REPRESENTATIVE_SELECTORS:
            self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")

    def test_light_calm_blue_covers_representative_m18_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_LIGHT)

    def test_dark_calm_blue_covers_representative_m18_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_DARK)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class DestructivePropertyWiringTests(_SyntheticDatabaseTestCase):
    """The shared `QPushButton[destructive="true"]` rule only applies if
    the property is actually set on each M18 delete/remove button -- a
    missing `setProperty` call would silently fall back to plain/invisible
    styling with no test failure unless checked directly."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_collection_delete_button_is_marked_destructive(self) -> None:
        collection_id = create_collection("Marked Destructive", "", card_size=8)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)

        delete_button = view.findChild(QPushButton, "collections-delete-button")
        self.assertIsNotNone(delete_button)
        self.assertEqual(delete_button.property("destructive"), "true")

    def test_template_editor_delete_buttons_are_marked_destructive(self) -> None:
        controller = TemplatesController()
        controller.refresh()
        controller.create_new_template("Marked Destructive Template", "", "French", "custom")
        dialog = _TemplateEditorDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog._delete_field_button.property("destructive"), "true")
        self.assertEqual(dialog._delete_template_button.property("destructive"), "true")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TemplatesDiscoverableEditAffordanceTests(_SyntheticDatabaseTestCase):
    """Human Gate 1 finding: 'existing Template editing is not adequately
    accessible... do not require the user to guess an undocumented
    double-click gesture.' These test the real discoverable affordance
    (`templates-open-button`), not just that double-click still works."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_open_button_starts_disabled_with_no_selection(self) -> None:
        create_entry_template(name="Selectable", description="", language="French", template_type="custom")
        controller = TemplatesController()
        view = TemplatesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        self.assertFalse(view._open_button.isEnabled())

    def test_open_button_enables_on_row_selection(self) -> None:
        create_entry_template(name="Selectable", description="", language="French", template_type="custom")
        controller = TemplatesController()
        view = TemplatesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        view._table.selectRow(0)

        self.assertTrue(view._open_button.isEnabled())

    def test_open_button_click_opens_editor_for_the_selected_custom_template(self) -> None:
        create_entry_template(name="Click To Open", description="", language="French", template_type="custom")
        controller = TemplatesController()
        view = TemplatesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        # Pre-seeded system Templates may sort before a fresh custom one
        # (get_entry_templates() orders is_system DESC, name ASC); select
        # the actual target row rather than assuming row 0.
        target_row = next(
            row
            for row in range(view._table.rowCount())
            if view._table.item(row, 0).text() == "Click To Open"
        )
        view._table.selectRow(target_row)

        opened_dialogs: list[_TemplateEditorDialog] = []
        original_exec = _TemplateEditorDialog.exec

        def _capture_and_close(self):
            opened_dialogs.append(self)
            return 0  # QDialog.DialogCode.Rejected, without a real event loop

        _TemplateEditorDialog.exec = _capture_and_close
        try:
            view._on_open_selected()
        finally:
            _TemplateEditorDialog.exec = original_exec

        self.assertEqual(len(opened_dialogs), 1)
        self.assertEqual(opened_dialogs[0]._name_input.text(), "Click To Open")

    def test_selection_follows_template_id_across_a_reordering_refresh(self) -> None:
        """Regression for an independent-review finding on this
        corrective checkpoint: selection is QTableWidget row-index-based,
        but `templates_changed` can fire (reordering rows by name) while a
        row is selected -- e.g. renaming the selected Template inside a
        still-open Template Editor. The selection must follow the
        Template's stable id, never a stale row index."""
        create_entry_template(name="AAA First", description="", language="French", template_type="custom")
        create_entry_template(name="MMM Middle", description="", language="French", template_type="custom")
        controller = TemplatesController()
        view = TemplatesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        middle_row = next(
            row for row in range(view._table.rowCount()) if view._table.item(row, 0).text() == "MMM Middle"
        )
        view._table.selectRow(middle_row)
        middle_id = view._table.item(middle_row, 0).data(Qt.ItemDataRole.UserRole)
        self.assertTrue(view._open_button.isEnabled())

        # Renaming "MMM Middle" ahead of "AAA First" reorders the table on
        # the very next `templates_changed`-triggered refresh.
        controller.select_template(middle_id)
        controller.update_selected_template("AA Renamed Ahead", "", "French", "custom")

        new_row = next(
            row for row in range(view._table.rowCount()) if view._table.item(row, 0).text() == "AA Renamed Ahead"
        )
        self.assertEqual(view._table.currentRow(), new_row)
        self.assertTrue(view._open_button.isEnabled())

    def test_selection_clears_when_the_selected_template_no_longer_exists(self) -> None:
        template_id = create_entry_template(name="Will Be Deleted", description="", language="French", template_type="custom")
        controller = TemplatesController()
        view = TemplatesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        row = next(row for row in range(view._table.rowCount()) if view._table.item(row, 0).text() == "Will Be Deleted")
        view._table.selectRow(row)
        self.assertTrue(view._open_button.isEnabled())

        controller.select_template(template_id)
        controller.delete_selected_template()

        self.assertFalse(view._open_button.isEnabled())

    def test_custom_template_field_edits_actually_persist_through_the_editor(self) -> None:
        """End-to-end proof that a Custom Template opened through the
        discoverable affordance is genuinely editable, not merely
        inspectable."""
        controller = TemplatesController()
        controller.refresh()
        template_id = controller.create_new_template("Editable Roundtrip", "", "French", "custom")

        dialog = _TemplateEditorDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)
        dialog._name_input.setText("Editable Roundtrip (edited)")
        dialog._on_save_metadata()

        from src.entry_templates import get_entry_template

        self.assertEqual(get_entry_template(template_id)["name"], "Editable Roundtrip (edited)")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CollectionsSpinBoxThemingTests(_SyntheticDatabaseTestCase):
    """The Collection Editor's card-size QSpinBox had no QSS coverage at
    all before this corrective pass (no `QDialog QSpinBox` rule existed
    anywhere in the stylesheet)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_collection_editor_spinbox_is_covered_by_the_new_dialog_rule(self) -> None:
        controller = CollectionsController()
        controller.refresh()
        dialog = _CollectionEditorDialog(controller, collection=None, parent=None)
        self.addCleanup(dialog.deleteLater)

        stylesheet = build_stylesheet(THEME_CALM_BLUE_LIGHT)
        self.assertIn("QDialog QSpinBox", stylesheet)
        self.assertIsNotNone(dialog._card_size_input)


if __name__ == "__main__":
    unittest.main()

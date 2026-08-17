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
from src.collections import (
    CrossCardMoveConfirmationRequired,
    add_entries_to_collection,
    create_collection,
    get_card_metadata_for_collection,
    get_collection_by_id,
    get_entries_in_collection,
    get_or_create_system_collection,
)
from src.entries import add_entry

"""
Focused tests for M18.1 Collection Manager + Card Organization
(collections_view.py Design Derivation Record above `LIST_PANE_WIDTH`).
Per DESIGN.md § 2 Rule C these are structural/behavioral proof that
`CollectionsController`'s new writes call the exact same
`src.collections` functions the Streamlit Collections page already uses
(including the `CrossCardMoveConfirmationRequired` safety gate) -- not
evidence that the P5/P6 dialogs were visually realized. Native human
visual acceptance is a separate, required gate (AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.collections_controller import CollectionsController
    from src.ui_desktop.views.collections_view import (
        CollectionsView,
        _CardOrganizationDialog,
        _CollectionEditorDialog,
        _DeleteCollectionDialog,
    )

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
        db.DB_PATH = self.root / "m18_collection_manager.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_entries(self, terms) -> list[int]:
        return [add_entry("French", "English", "word", term, meaning) for term, meaning in terms]


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CollectionManagerControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_create_new_collection_selects_and_appears_in_list(self) -> None:
        controller = CollectionsController()
        controller.refresh()

        collection_id = controller.create_new_collection("Weather", "Weather words", 5)

        self.assertEqual(controller.selected_id, collection_id)
        self.assertFalse(controller.selected_is_system)
        self.assertIn(collection_id, {c["id"] for c in controller.collections})
        stored = get_collection_by_id(collection_id)
        self.assertEqual(stored["name"], "Weather")
        self.assertEqual(stored["card_size"], 5)

    def test_create_new_collection_rejects_blank_name(self) -> None:
        controller = CollectionsController()
        controller.refresh()
        with self.assertRaises(ValueError):
            controller.create_new_collection("   ", "", 5)

    def test_update_selected_collection_persists_fields(self) -> None:
        collection_id = create_collection("Animals", "", card_size=8)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)

        controller.update_selected_collection("Animals (renamed)", "Farm animals", 8)

        stored = get_collection_by_id(collection_id)
        self.assertEqual(stored["name"], "Animals (renamed)")
        self.assertEqual(stored["description"], "Farm animals")

    def test_update_selected_collection_requires_cross_card_confirmation(self) -> None:
        collection_id = create_collection("Numbers", "", card_size=3)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        entry_ids = self._make_entries([(f"n{i}", f"m{i}") for i in range(4)])
        add_entries_to_collection(entry_ids, collection_id)

        with self.assertRaises(CrossCardMoveConfirmationRequired):
            controller.update_selected_collection("Numbers", "", 2)

        # unconfirmed change did not silently apply
        self.assertEqual(get_collection_by_id(collection_id)["card_size"], 3)

        controller.update_selected_collection("Numbers", "", 2, confirm_cross_card=True)
        self.assertEqual(get_collection_by_id(collection_id)["card_size"], 2)

    def test_update_selected_collection_requires_selection(self) -> None:
        controller = CollectionsController()
        controller.refresh()
        with self.assertRaises(ValueError):
            controller.update_selected_collection("Name", "", 5)

    def test_delete_selected_collection_removes_it_and_clears_selection(self) -> None:
        collection_id = create_collection("Temporary", "", card_size=8)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)

        result = controller.delete_selected_collection()

        self.assertEqual(result["collection_id"], collection_id)
        self.assertIsNone(controller.selected_id)
        self.assertIsNone(get_collection_by_id(collection_id))

    def test_delete_selected_collection_rejects_system_pool(self) -> None:
        starred_id = get_or_create_system_collection("starred", "Starred", "", card_size=8)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(starred_id, is_system=True)

        with self.assertRaises(ValueError):
            controller.delete_selected_collection()

    def test_rename_selected_card_persists(self) -> None:
        collection_id = create_collection("Verbs", "", card_size=8)
        entry_ids = self._make_entries([("parler", "to speak")])
        add_entries_to_collection(entry_ids, collection_id)

        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)

        controller.rename_selected_card(1, "First card")

        metadata = get_card_metadata_for_collection(collection_id)
        self.assertEqual(metadata[1]["name"], "First card")

    def test_organization_entries_and_remove(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        entry_ids = self._make_entries([("pomme", "apple"), ("poire", "pear")])
        add_entries_to_collection(entry_ids, collection_id)

        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)

        entries = controller.organization_entries()
        self.assertEqual(len(entries), 2)

        removed = controller.remove_organization_entries([entry_ids[0]])
        self.assertEqual(removed, 1)
        self.assertEqual(len(controller.organization_entries()), 1)

    def test_remove_organization_entries_requires_cross_card_confirmation(self) -> None:
        collection_id = create_collection("Colors", "", card_size=3)
        entry_ids = self._make_entries([(f"c{i}", f"m{i}") for i in range(4)])
        add_entries_to_collection(entry_ids, collection_id)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)

        with self.assertRaises(CrossCardMoveConfirmationRequired):
            controller.remove_organization_entries([entry_ids[0]])

        self.assertEqual(len(controller.organization_entries()), 4)

        controller.remove_organization_entries([entry_ids[0]], confirm_cross_card=True)
        self.assertEqual(len(controller.organization_entries()), 3)

    def test_move_organization_entry_reorders(self) -> None:
        collection_id = create_collection("Days", "", card_size=8)
        entry_ids = self._make_entries([("lundi", "Monday"), ("mardi", "Tuesday"), ("mercredi", "Wednesday")])
        add_entries_to_collection(entry_ids, collection_id)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)

        controller.move_organization_entry(entry_ids[2], 1)

        ordered_ids = [e["id"] for e in controller.organization_entries()]
        self.assertEqual(ordered_ids[0], entry_ids[2])

    def test_organization_entries_empty_for_system_pool(self) -> None:
        starred_id = get_or_create_system_collection("starred", "Starred", "", card_size=8)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(starred_id, is_system=True)

        self.assertEqual(controller.organization_entries(), [])
        with self.assertRaises(ValueError):
            controller.remove_organization_entries([1])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CollectionManagerViewStructureTests(_SyntheticDatabaseTestCase):
    """Structural-only proof (DESIGN.md § 2 Rule C) that the new
    Collection Manager / Card Organization actions exist and are wired to
    the controller -- never proof of visual realization."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_new_collection_button_opens_editor_dialog(self) -> None:
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)
        controller.refresh()

        dialog = _CollectionEditorDialog(controller, collection=None, parent=view)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.windowTitle(), "New Collection")

    def test_edit_dialog_prefills_existing_collection(self) -> None:
        collection_id = create_collection("Prefill Test", "desc", card_size=6)
        controller = CollectionsController()
        controller.refresh()
        collection = get_collection_by_id(collection_id)

        dialog = _CollectionEditorDialog(controller, collection=collection, parent=None)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.windowTitle(), "Edit Collection")
        self.assertEqual(dialog._name_input.text(), "Prefill Test")
        self.assertEqual(dialog._card_size_input.value(), 6)

    def test_delete_dialog_requires_typed_name_and_checkbox(self) -> None:
        collection_id = create_collection("Delete Me", "", card_size=8)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        collection = get_collection_by_id(collection_id)

        dialog = _DeleteCollectionDialog(controller, collection, parent=None)
        self.addCleanup(dialog.deleteLater)

        self.assertFalse(dialog._delete_button.isEnabled())
        dialog._name_input.setText("Delete Me")
        dialog._confirm_checkbox.setChecked(True)
        self.assertTrue(dialog._delete_button.isEnabled())

    def test_card_organization_dialog_lists_entries(self) -> None:
        collection_id = create_collection("Organize Me", "", card_size=8)
        entry_ids = self._make_entries([("un", "one"), ("deux", "two")])
        add_entries_to_collection(entry_ids, collection_id)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        collection = get_collection_by_id(collection_id)

        dialog = _CardOrganizationDialog(controller, collection, parent=None)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(len(dialog._checks), 2)
        self.assertEqual(dialog._move_combo.count(), 2)


if __name__ == "__main__":
    unittest.main()

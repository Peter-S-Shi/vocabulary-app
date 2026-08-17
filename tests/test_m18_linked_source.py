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
from src.linked_sources import LinkedSourceError, get_collection_source_link

"""
Focused tests for M18 Phase C6 -- Linked Source (linked_source_view.py
Design Derivation Record). Per DESIGN.md § 2 Rule C these are
structural/behavioral proof that `LinkedSourceController` delegates
every preview/link/refresh/unlink call to the exact same
`src.linked_sources` functions, that preview never mutates SQLite, and
that a missing/unreadable source is reported as a controlled error
rather than damaging existing Collection/Entry data -- not evidence the
P6 dialog was visually realized. Native human visual acceptance is a
separate, required gate (AGENTS.md). There is no Streamlit precedent for
this workflow (M13 closed the reusable core only).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.linked_source_controller import LinkedSourceController
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.collections_view import CollectionsView
    from src.ui_desktop.views.linked_source_view import LinkedSourceDialog

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
        db.DB_PATH = self.root / "m18_linked_source.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _write_source_csv(self, name: str, rows: str) -> str:
        path = self.root / name
        path.write_text("language,term,meaning\n" + rows, encoding="utf-8")
        return str(path)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class LinkedSourceControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_open_for_collection_with_no_link(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        controller = LinkedSourceController()

        controller.open_for_collection(collection_id, "Fruits")

        self.assertIsNone(controller.link)

    def test_preview_never_mutates_sqlite_before_confirm(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        source_path = self._write_source_csv("fruits.csv", "French,pomme,apple\n")
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        controller.stage_source_path(source_path)

        controller.run_preview()

        self.assertTrue(controller.preview["ok"])
        self.assertEqual(controller.preview["summary"]["new_valid_count"], 1)
        self.assertEqual(get_entries_in_collection(collection_id), [])

    def test_confirm_initial_link_creates_the_link_and_imports_rows(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        source_path = self._write_source_csv("fruits.csv", "French,pomme,apple\n")
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        controller.stage_source_path(source_path)
        controller.run_preview()

        result = controller.confirm()

        self.assertTrue(result["success"])
        self.assertIsNotNone(controller.link)
        self.assertEqual(len(get_entries_in_collection(collection_id)), 1)

    def test_cannot_confirm_before_a_preview(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")

        self.assertFalse(controller.can_confirm())
        with self.assertRaises(LinkedSourceError):
            controller.confirm()

    def test_cannot_confirm_twice_on_the_same_preview(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        source_path = self._write_source_csv("fruits.csv", "French,pomme,apple\n")
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        controller.stage_source_path(source_path)
        controller.run_preview()
        controller.confirm()

        self.assertFalse(controller.can_confirm())
        with self.assertRaises(LinkedSourceError):
            controller.confirm()

    def test_refresh_an_existing_link_appends_only_new_rows(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        source_path = self._write_source_csv("fruits.csv", "French,pomme,apple\n")
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        controller.stage_source_path(source_path)
        controller.run_preview()
        controller.confirm()

        # Append a new row to the same linked file, then refresh.
        with open(source_path, "a", encoding="utf-8") as handle:
            handle.write("French,poire,pear\n")
        controller.open_for_collection(collection_id, "Fruits")  # reload link state
        controller.run_preview()

        self.assertEqual(controller.preview["summary"]["new_valid_count"], 1)
        result = controller.confirm()
        self.assertTrue(result["success"])
        self.assertEqual(len(get_entries_in_collection(collection_id)), 2)

    def test_missing_source_reports_controlled_error_without_damaging_data(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        source_path = self._write_source_csv("fruits.csv", "French,pomme,apple\n")
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        controller.stage_source_path(source_path)
        controller.run_preview()
        controller.confirm()
        link_before = get_collection_source_link(collection_id)

        os.remove(source_path)
        controller.open_for_collection(collection_id, "Fruits")
        controller.run_preview()

        self.assertFalse(controller.preview["ok"])
        self.assertIn("unavailable", controller.preview["errors"][0].lower())
        self.assertFalse(controller.can_confirm())
        self.assertEqual(get_collection_source_link(collection_id), link_before)
        self.assertEqual(len(get_entries_in_collection(collection_id)), 1)

    def test_unlink_removes_metadata_only(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        source_path = self._write_source_csv("fruits.csv", "French,pomme,apple\n")
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        controller.stage_source_path(source_path)
        controller.run_preview()
        controller.confirm()

        result = controller.unlink()

        self.assertTrue(result["success"])
        self.assertIsNone(controller.link)
        self.assertIsNone(get_collection_source_link(collection_id))
        self.assertEqual(len(get_entries_in_collection(collection_id)), 1)  # Entries untouched

    def test_relink_after_unlink_uses_a_fresh_confirm(self) -> None:
        """No dedicated core relink function exists; recovery is
        unlink + a fresh confirm to a new path."""
        collection_id = create_collection("Fruits", "", card_size=8)
        old_path = self._write_source_csv("old.csv", "French,pomme,apple\n")
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        controller.stage_source_path(old_path)
        controller.run_preview()
        controller.confirm()
        controller.unlink()

        new_path = self._write_source_csv("new.csv", "French,poire,pear\n")
        controller.stage_source_path(new_path)
        controller.run_preview()
        result = controller.confirm()

        self.assertTrue(result["success"])
        self.assertEqual(controller.link["source_path"], str(Path(new_path).resolve()))

    def test_controller_has_no_dedicated_relink_method(self) -> None:
        """Product-truth guard: this controller must not invent a
        desktop-only "replace the linked path in place" shortcut the
        core does not support."""
        controller = LinkedSourceController()
        relink_names = [name for name in dir(controller) if "relink" in name.lower()]
        self.assertEqual(relink_names, [])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class LinkedSourceDialogStructureTests(_SyntheticDatabaseTestCase):
    """Structural-only proof (DESIGN.md § 2 Rule C)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_confirm_disabled_until_preview_and_checkbox(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        source_path = self._write_source_csv("fruits.csv", "French,pomme,apple\n")
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        dialog = LinkedSourceDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog._confirm_button.isEnabled())

        controller.stage_source_path(source_path)
        controller.run_preview()
        dialog._confirm_checkbox.setChecked(True)

        self.assertTrue(dialog._confirm_button.isEnabled())

    def test_unlink_button_hidden_when_no_link_exists(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        controller = LinkedSourceController()
        controller.open_for_collection(collection_id, "Fruits")
        dialog = LinkedSourceDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        self.assertFalse(dialog._unlink_button.isVisible())

    def test_collections_view_has_a_linked_source_button(self) -> None:
        from src.ui_desktop.controllers.collections_controller import CollectionsController

        collection_id = create_collection("Fruits", "", card_size=8)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)

        from PySide6.QtWidgets import QPushButton

        button = view.findChild(QPushButton, "collections-linked-source-button")
        self.assertIsNotNone(button)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18LinkedSourceTokenQssStructuralCoverageTests(unittest.TestCase):
    REPRESENTATIVE_SELECTORS = (
        "#collections-linked-source-button",
        "#linked-source-status-label",
        "#linked-source-choose-file-button",
        "#linked-source-preview-button",
        "#linked-source-confirm-button",
        "#linked-source-confirm-button:disabled",
        "#linked-source-unlink-button",
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

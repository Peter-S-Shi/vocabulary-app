from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import add_entries_to_system_collection, create_collection, get_entries_in_collection
from src.entries import add_entry, get_entry_by_id

"""
Focused tests for M17 -- Minimum Collection Integration (DESIGN.md § 6.8,
Class B). Per DESIGN.md § 2 Rule C, none of this proves the canonical
composition was *visually* realized -- only that the shell/navigation
wiring, the Collections Navigator's read-only projection of core truth,
and the two typed handoffs (Collections/Today -> Entries,
Collections -> Review) are correct and never bypass/duplicate existing
reusable core. Native human visual acceptance is a separate, required
gate (AGENTS.md).
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.collections_controller import CollectionsController
    from src.ui_desktop.controllers.entries_controller import SCOPE_ALL
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.state.app_state import ShellMode, Workspace
    from src.ui_desktop.state.handoff import EntriesScopeIntent, StudyTargetIntent
    from src.ui_desktop.views.collections_view import CollectionsView
    from src.ui_desktop.views.today_view import TodayView
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
        db.DB_PATH = self.root / "m17_collections.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_entries(self, terms) -> list[int]:
        return [add_entry("French", "English", "word", term, meaning) for term, meaning in terms]


# -- Shell / navigation --------------------------------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class NavigationRailCollectionsEnabledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_collections_destination_is_enabled(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)
        self.assertTrue(rail.is_enabled_destination("collections"))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class MainWindowCollectionsShellTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_navigating_to_collections_renders_the_real_workspace(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window._navigation_rail._buttons["collections"].click()

        self.assertIs(window.current_workspace(), Workspace.COLLECTIONS)
        self.assertIs(window.app_state.mode, ShellMode.MANAGEMENT)
        self.assertIs(window._workspace_stack.currentWidget(), window.collections_view)

    def test_navigation_state_lives_only_in_app_state(self) -> None:
        """No parallel shell state: MainWindow only ever reflects
        AppState.workspace (M17 Minimum Collection Integration prompt
        § 4)."""
        window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window.app_state.request_navigation(Workspace.COLLECTIONS)

        self.assertIs(window.current_workspace(), window.app_state.workspace)
        self.assertIs(window._workspace_stack.currentWidget(), window.collections_view)


# -- Collections Navigator ------------------------------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CollectionsControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_normal_collections_listed_from_core_truth(self) -> None:
        create_collection("IELTS Core", description="Exam vocabulary", card_size=8)
        controller = CollectionsController()

        controller.refresh()

        self.assertEqual(len(controller.collections), 1)
        self.assertEqual(controller.collections[0]["name"], "IELTS Core")

    def test_system_pools_are_semantically_separated(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "starred")
        controller = CollectionsController()

        controller.refresh()

        self.assertTrue(any(pool["name"] == "Starred" for pool in controller.system_pools))
        self.assertFalse(any(c["name"] == "Starred" for c in controller.collections))
        self.assertTrue(all(c["is_system"] for c in controller.system_pools))
        self.assertTrue(all(not c["is_system"] for c in controller.collections))

    def test_selecting_a_normal_collection_exposes_factual_context(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        collection_id = create_collection("IELTS Core", description="Exam vocabulary", card_size=8)
        from src.collections import add_entries_to_collection

        add_entries_to_collection(entry_ids, collection_id)
        controller = CollectionsController()
        controller.refresh()

        controller.select_collection(collection_id, is_system=False)

        detail = controller.selected_collection()
        self.assertEqual(detail["name"], "IELTS Core")
        self.assertEqual(detail["description"], "Exam vocabulary")
        self.assertEqual(detail["entry_count"], 2)
        self.assertEqual(detail["card_size"], 8)

    def test_current_card_page_comes_from_existing_core(self) -> None:
        from src.collections import add_entries_to_collection, get_card_page_for_collection

        entry_ids = self._make_entries([(f"term{i}", f"meaning{i}") for i in range(3)])
        collection_id = create_collection("Numbers", card_size=2)
        add_entries_to_collection(entry_ids, collection_id)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)

        self.assertEqual(
            controller.current_card_page(),
            get_card_page_for_collection(collection_id, page=1, page_size=controller.card_page_size, sort_by="card_number"),
        )
        self.assertEqual(controller.current_card_page()["total_cards"], 2)  # card_size=2, 3 entries -> 2 Cards

    def test_system_pool_selection_has_no_card_page(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "starred")
        controller = CollectionsController()
        controller.refresh()
        starred_id = next(pool["id"] for pool in controller.system_pools if pool["name"] == "Starred")

        controller.select_collection(starred_id, is_system=True)

        self.assertEqual(controller.current_card_page()["cards"], [])
        self.assertEqual(controller.system_type_for_selected(), "starred")

    def test_browsing_does_not_mutate_the_database(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        collection_id = create_collection("IELTS Core", card_size=8)
        from src.collections import add_entries_to_collection

        add_entries_to_collection(entry_ids, collection_id)
        before = get_entry_by_id(entry_ids[0])

        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        controller.current_card_page()
        controller.system_type_for_selected()
        controller.refresh()

        after = get_entry_by_id(entry_ids[0])
        self.assertEqual(before, after)
        self.assertEqual(get_entries_in_collection(collection_id), get_entries_in_collection(collection_id))

    def test_empty_state_is_honest(self) -> None:
        controller = CollectionsController()

        controller.refresh()

        self.assertEqual(controller.collections, [])
        self.assertIsNone(controller.selected_collection())
        self.assertEqual(controller.current_card_page()["cards"], [])

    def test_stale_selection_is_cleared_on_refresh_if_collection_disappears(self) -> None:
        collection_id = create_collection("Temp", card_size=8)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        self.assertIsNotNone(controller.selected_collection())

        from src.collections import delete_collection

        delete_collection(collection_id)
        controller.refresh()

        self.assertIsNone(controller.selected_id)
        self.assertIsNone(controller.selected_collection())


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CollectionsViewStructureTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_view_renders_collections_and_pools_sections(self) -> None:
        create_collection("IELTS Core", card_size=8)
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "starred")
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)

        view.refresh()

        headings = [
            w.text() for w in view._list_pane.findChildren(QWidget) if w.objectName() == "collections-list-heading"
        ]
        self.assertEqual(headings, ["Collections", "Practice Pools"])
        self.assertIn("IELTS Core", "".join(b.text() for b in view._list_pane._buttons.values()))

    def test_open_entries_emits_correct_scope_for_normal_collection(self) -> None:
        collection_id = create_collection("IELTS Core", card_size=8)
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.select_collection(collection_id, is_system=False)

        received: list[EntriesScopeIntent] = []
        view.open_entries_requested.connect(received.append)
        view._render_detail()
        open_button = next(
            w for w in view._detail_container.findChildren(QWidget) if w.objectName() == "collections-open-entries-button"
        )
        open_button.click()

        self.assertEqual(received, [EntriesScopeIntent(scope=f"collection:{collection_id}")])

    def test_open_entries_emits_correct_scope_for_system_pool(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "mistake_book")
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        pool_id = next(pool["id"] for pool in controller.system_pools if pool["name"] == "Mistake Book")
        controller.select_collection(pool_id, is_system=True)

        received: list[EntriesScopeIntent] = []
        view.open_entries_requested.connect(received.append)
        open_button = next(
            w for w in view._detail_container.findChildren(QWidget) if w.objectName() == "collections-open-entries-button"
        )
        open_button.click()

        self.assertEqual(received, [EntriesScopeIntent(scope="system:mistake_book")])

    def test_open_in_study_emits_correct_target(self) -> None:
        from src.collections import add_entries_to_collection

        entry_ids = self._make_entries([("chat", "cat")])
        collection_id = create_collection("IELTS Core", card_size=8)
        add_entries_to_collection(entry_ids, collection_id)
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.select_collection(collection_id, is_system=False)

        received: list[StudyTargetIntent] = []
        view.open_in_study_requested.connect(received.append)
        open_in_study_button = next(
            w for w in view._detail_container.findChildren(QWidget) if w.objectName() == "collections-open-in-study-button"
        )
        open_in_study_button.click()

        self.assertEqual(received, [StudyTargetIntent(collection_id=collection_id, card_number=1)])


# -- Collections -> Entries -----------------------------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CollectionsToEntriesHandoffTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_normal_collection_handoff_activates_collection_scope(self) -> None:
        from src.collections import add_entries_to_collection

        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        other_ids = self._make_entries([("resilient", "able to recover")])
        collection_id = create_collection("IELTS Core", card_size=8)
        add_entries_to_collection(entry_ids, collection_id)
        window = MainWindow()
        self.addCleanup(window.close)

        window._open_entries_with_scope(EntriesScopeIntent(scope=f"collection:{collection_id}"))

        self.assertEqual(window.entries_controller.scope, f"collection:{collection_id}")
        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertEqual({row["id"] for row in window.entries_controller.model.rows()}, set(entry_ids))

    def test_system_pool_handoff_activates_system_scope(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "mistake_book")
        window = MainWindow()
        self.addCleanup(window.close)

        window._open_entries_with_scope(EntriesScopeIntent(scope="system:mistake_book"))

        self.assertEqual(window.entries_controller.scope, "system:mistake_book")
        self.assertEqual({row["id"] for row in window.entries_controller.model.rows()}, set(entry_ids))

    def test_missing_collection_target_fails_safely(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)

        window._open_entries_with_scope(EntriesScopeIntent(scope="collection:999999"))

        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertEqual(window.entries_controller.model.rows(), [])


# -- Today -> Entries -------------------------------------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TodayToEntriesHandoffTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_actionable_pool_context_reaches_the_entries_scope(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "starred")
        window = MainWindow()
        self.addCleanup(window.close)
        window.today_controller.refresh()
        window.today_view._render_attention()

        received: list[EntriesScopeIntent] = []
        window.today_view.navigate_to_entries_scope_requested.connect(received.append)
        row = next(
            w
            for w in window.today_view.findChildren(QWidget)
            if w.objectName() == "today-attention-row" and w.isEnabled()
        )
        row.click()

        self.assertEqual(received, [EntriesScopeIntent(scope="system:starred")])

    def test_wired_through_main_window_reaches_entries_controller(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "proficient_pool")
        window = MainWindow()
        self.addCleanup(window.close)
        window.today_controller.refresh()
        window.today_view._render_attention()

        row = next(
            w
            for w in window.today_view.findChildren(QWidget)
            if w.objectName() == "today-attention-row" and w.isEnabled()
        )
        row.click()

        self.assertEqual(window.entries_controller.scope, "system:proficient_pool")
        self.assertIs(window.current_workspace(), Workspace.ENTRIES)

    def test_no_attention_items_when_pools_are_empty(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        window.today_controller.refresh()

        self.assertEqual(window.today_controller.collections_needing_attention(), [])


# -- Collections -> Review --------------------------------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CollectionsToReviewHandoffTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_selected_collection_card_opens_the_exact_target(self) -> None:
        from src.collections import add_entries_to_collection

        entry_ids = self._make_entries([(f"term{i}", f"meaning{i}") for i in range(6)])
        collection_id = create_collection("Numbers", card_size=2)
        add_entries_to_collection(entry_ids, collection_id)
        window = MainWindow()
        self.addCleanup(window.close)

        window._open_review_at_card(StudyTargetIntent(collection_id=collection_id, card_number=2))

        card = window.review_controller.current_card()
        self.assertIsNotNone(card)
        self.assertEqual(card["collection_id"], collection_id)
        self.assertEqual(card["card_number"], 2)
        self.assertIs(window.current_workspace(), Workspace.REVIEW)
        self.assertIs(window.app_state.mode, ShellMode.STUDY)

    def test_specific_target_never_falls_back_to_default_card(self) -> None:
        """The never-quizzed-first heuristic in open_default() must never
        silently override a specific requested Card (M17 Minimum
        Collection Integration prompt § 9)."""
        from src.collections import add_entries_to_collection

        entry_ids = self._make_entries([(f"term{i}", f"meaning{i}") for i in range(4)])
        collection_id = create_collection("Numbers", card_size=1)
        add_entries_to_collection(entry_ids, collection_id)
        window = MainWindow()
        self.addCleanup(window.close)

        window._open_review_at_card(StudyTargetIntent(collection_id=collection_id, card_number=4))

        card = window.review_controller.current_card()
        self.assertEqual(card["card_number"], 4)

    def test_missing_card_target_fails_honestly_without_navigating(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        starting_workspace = window.current_workspace()

        # QMessageBox.warning() is a blocking modal call -- patched here
        # the same way EntriesView's confirmation dialogs are patched
        # elsewhere, so the test doesn't hang waiting for a human click.
        with patch("src.ui_desktop.main_window.QMessageBox.warning") as mock_warning:
            window._open_review_at_card(StudyTargetIntent(collection_id=999999, card_number=1))

        mock_warning.assert_called_once()
        self.assertIsNone(window.review_controller.current_card())
        self.assertIs(window.current_workspace(), starting_workspace)
        self.assertIs(window.app_state.mode, ShellMode.MANAGEMENT)

    def test_browsing_the_opened_card_creates_no_completion_evidence(self) -> None:
        from src.collections import add_entries_to_collection
        from src.learning_workflow import get_card_learning_history

        entry_ids = self._make_entries([("chat", "cat")])
        collection_id = create_collection("IELTS Core", card_size=8)
        add_entries_to_collection(entry_ids, collection_id)
        window = MainWindow()
        self.addCleanup(window.close)

        window._open_review_at_card(StudyTargetIntent(collection_id=collection_id, card_number=1))

        with db.get_connection() as connection:
            history = get_card_learning_history(connection, collection_id, 1)
        self.assertEqual(history, [])


class EntriesCoreBoundaryTests(unittest.TestCase):
    """Reusable-core boundary guards (M16.1 contract): the Collections
    Navigator orchestrates presentation/selection state only, and never
    reaches SQLite or Streamlit directly."""

    def _assert_no_raw_sql(self, relative_path: str) -> None:
        path = PROJECT_ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("get_connection", text)
        self.assertNotIn(".execute(", text)
        self.assertNotIn("import sqlite3", text)
        self.assertNotIn("from src import db", text)

    def test_controller_has_no_raw_sql_and_no_db_import(self) -> None:
        self._assert_no_raw_sql("src/ui_desktop/controllers/collections_controller.py")

    def test_view_has_no_raw_sql_and_no_direct_db_import(self) -> None:
        self._assert_no_raw_sql("src/ui_desktop/views/collections_view.py")

    def test_no_streamlit_dependency(self) -> None:
        for relative_path in (
            "src/ui_desktop/controllers/collections_controller.py",
            "src/ui_desktop/views/collections_view.py",
        ):
            text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("import streamlit", text.lower())
            self.assertNotIn("from src.ui_streamlit", text)
            self.assertNotIn("import src.ui_streamlit", text)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry, search_entries

"""
Focused tests for M17 -- Final Parity + Exit Verification: the three
frozen corrective items (EXIT-BUG-001 Custom Entry Type, EXIT-BUG-002
Sorting, EXIT-BUG-003 Result count) plus high-leverage cross-feature
regression coverage proving the seven already-Human-Accepted M17
checkpoints work together as one coherent product.

Per DESIGN.md § 2 Rule C, none of this proves the integrated journeys
*look* correct -- only that the connections are real (exact scope/Card
targets, no silent fallback), presentation state (sort/filter/theme)
never mutates learning data, and the three corrective items behave as
specified. Native human visual/functional acceptance is a separate,
required gate.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.app import build_application
    from src.ui_desktop.controllers.entries_controller import SORT_OPTIONS, EntriesController
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.state.app_state import ShellMode, Workspace
    from src.ui_desktop.state.handoff import EntriesScopeIntent, QuizLaunchIntent, StudyTargetIntent
    from src.ui_desktop.theming.theme_manager import Accent, Appearance
    from src.ui_desktop.views.entries_view import EntriesView, _EntryEditorDialog

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    """Shared setup matching the existing repository pattern: swap
    db.DB_PATH to a temporary synthetic database, never the user's
    personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m17_exit_verification.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


# --- EXIT-BUG-001: Custom Entry Type ---------------------------------------


class SearchEntriesCoreCustomTypeTests(_SyntheticDatabaseTestCase):
    """Core already stores/validates ``entry_type`` as free text, not an
    enum/foreign key -- these confirm that stays true and that a custom
    value survives the real create/update/search path unchanged."""

    def test_custom_entry_type_persists_through_add_entry(self) -> None:
        entry_id = add_entry("English", "Chinese", "Idiom", "cope", "meaning")
        rows = search_entries(entry_type="Idiom")
        self.assertEqual([r["id"] for r in rows], [entry_id])

    def test_filtering_by_a_predefined_type_still_excludes_custom_values(self) -> None:
        add_entry("English", "Chinese", "Idiom", "cope", "meaning")
        word_id = add_entry("English", "Chinese", "word", "resilient", "meaning")
        rows = search_entries(entry_type="word")
        self.assertEqual([r["id"] for r in rows], [word_id])

    def test_all_filter_includes_custom_typed_entries(self) -> None:
        entry_id = add_entry("English", "Chinese", "Neologism", "term", "meaning")
        rows = search_entries()
        self.assertIn(entry_id, [r["id"] for r in rows])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CustomEntryTypeDialogTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self.entry_id = add_entry("English", "Chinese", "word", "alpha", "meaning")
        self.controller = EntriesController()
        self.controller.refresh_scopes()
        self.controller.refresh()

    def _open_dialog(self, entry_id: int | None = None) -> _EntryEditorDialog:
        dialog = _EntryEditorDialog(self.controller, entry_id)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_custom_sentinel_item_exists(self) -> None:
        dialog = self._open_dialog()
        self.assertGreaterEqual(dialog._entry_type_combo.findText(dialog.CUSTOM_ENTRY_TYPE_SENTINEL), 0)

    def test_confirmed_non_empty_custom_value_becomes_selected(self) -> None:
        dialog = self._open_dialog()
        sentinel_index = dialog._entry_type_combo.findText(dialog.CUSTOM_ENTRY_TYPE_SENTINEL)
        with patch("src.ui_desktop.views.entries_view.QInputDialog.getText", return_value=("Idiom", True)):
            dialog._on_entry_type_activated(sentinel_index)
        self.assertEqual(dialog._entry_type_combo.currentText(), "Idiom")

    def test_cancel_preserves_the_existing_value(self) -> None:
        dialog = self._open_dialog()
        original = dialog._entry_type_combo.currentText()
        sentinel_index = dialog._entry_type_combo.findText(dialog.CUSTOM_ENTRY_TYPE_SENTINEL)
        with patch("src.ui_desktop.views.entries_view.QInputDialog.getText", return_value=("", False)):
            dialog._on_entry_type_activated(sentinel_index)
        self.assertEqual(dialog._entry_type_combo.currentText(), original)

    def test_whitespace_only_confirm_is_safely_rejected(self) -> None:
        dialog = self._open_dialog()
        original = dialog._entry_type_combo.currentText()
        sentinel_index = dialog._entry_type_combo.findText(dialog.CUSTOM_ENTRY_TYPE_SENTINEL)
        with patch("src.ui_desktop.views.entries_view.QInputDialog.getText", return_value=("   ", True)):
            dialog._on_entry_type_activated(sentinel_index)
        self.assertEqual(dialog._entry_type_combo.currentText(), original)

    def test_confirmed_custom_value_saves_and_persists(self) -> None:
        dialog = self._open_dialog(self.entry_id)
        sentinel_index = dialog._entry_type_combo.findText(dialog.CUSTOM_ENTRY_TYPE_SENTINEL)
        with patch("src.ui_desktop.views.entries_view.QInputDialog.getText", return_value=("Neologism", True)):
            dialog._on_entry_type_activated(sentinel_index)
        dialog._on_save()
        stored = self.controller.entry_detail(self.entry_id)
        self.assertEqual(stored["entry_type"], "Neologism")

    def test_reopening_an_entry_with_a_custom_type_selects_it_correctly(self) -> None:
        self.controller.update_entry_core(
            self.entry_id,
            {"language": "English", "explanation_language": "Chinese", "entry_type": "Neologism", "status": "new"},
            {"term": "alpha", "meaning": "meaning", "example": "", "notes": "", "tags": "", "source": ""},
            "",
            "",
        )
        dialog = self._open_dialog(self.entry_id)
        self.assertEqual(dialog._entry_type_combo.currentText(), "Neologism")

    def test_entry_type_filtering_does_not_crash_with_a_custom_value_present(self) -> None:
        self.controller.update_entry_core(
            self.entry_id,
            {"language": "English", "explanation_language": "Chinese", "entry_type": "Neologism", "status": "new"},
            {"term": "alpha", "meaning": "meaning", "example": "", "notes": "", "tags": "", "source": ""},
            "",
            "",
        )
        self.controller.finish_edit()
        count = self.controller.set_entry_type("Neologism")
        self.assertEqual(count, 1)


# --- EXIT-BUG-002: Sorting --------------------------------------------------


class SearchEntriesCoreSortTests(_SyntheticDatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.id_alpha = add_entry("English", "Chinese", "word", "alpha", "m1")
        self.id_beta = add_entry("English", "Chinese", "word", "beta", "m2")
        self.id_gamma = add_entry("English", "Chinese", "word", "gamma", "m3")

    def test_default_order_is_unchanged_from_pre_existing_behavior(self) -> None:
        self.assertEqual(
            [r["id"] for r in search_entries()],
            [self.id_gamma, self.id_beta, self.id_alpha],
        )

    def test_term_ascending_is_deterministic(self) -> None:
        self.assertEqual(
            [r["term"] for r in search_entries(sort_by="term", sort_direction="asc")],
            ["alpha", "beta", "gamma"],
        )

    def test_term_descending_is_deterministic(self) -> None:
        self.assertEqual(
            [r["term"] for r in search_entries(sort_by="term", sort_direction="desc")],
            ["gamma", "beta", "alpha"],
        )

    def test_created_at_ascending(self) -> None:
        self.assertEqual(
            [r["id"] for r in search_entries(sort_by="created_at", sort_direction="asc")],
            [self.id_alpha, self.id_beta, self.id_gamma],
        )

    def test_unrecognized_sort_by_falls_back_safely(self) -> None:
        self.assertEqual(
            [r["id"] for r in search_entries(sort_by="not_a_real_column")],
            [self.id_gamma, self.id_beta, self.id_alpha],
        )

    def test_sort_composes_with_filters(self) -> None:
        add_entry("English", "Chinese", "phrase", "zzz", "m4")
        rows = search_entries(entry_type="word", sort_by="term", sort_direction="asc")
        self.assertEqual([r["term"] for r in rows], ["alpha", "beta", "gamma"])

    def test_sorting_does_not_mutate_entry_data(self) -> None:
        before = {r["id"]: dict(r) for r in search_entries()}
        search_entries(sort_by="term", sort_direction="asc")
        search_entries(sort_by="updated_at", sort_direction="desc")
        after = {r["id"]: dict(r) for r in search_entries()}
        self.assertEqual(before, after)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesControllerSortTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self.ids = [add_entry("English", "Chinese", "word", term, "m") for term in ("gamma", "alpha", "beta")]
        self.controller = EntriesController()
        self.controller.refresh_scopes()
        self.controller.refresh()

    def test_set_sort_reorders_the_visible_rows(self) -> None:
        self.controller.set_sort("term", "asc")
        self.assertEqual([r["term"] for r in self.controller.model.rows()], ["alpha", "beta", "gamma"])

    def test_set_sort_composes_with_scope_and_filter(self) -> None:
        collection_id = create_collection("Test Collection", card_size=3)
        add_entries_to_collection(self.ids[:2], collection_id)
        self.controller.set_scope(f"collection:{collection_id}")
        self.controller.set_sort("term", "asc")
        self.assertEqual([r["term"] for r in self.controller.model.rows()], ["alpha", "gamma"])

    def test_sort_does_not_change_result_count(self) -> None:
        before = self.controller.refresh()
        after = self.controller.set_sort("term", "asc")
        self.assertEqual(before, after)

    def test_focus_is_preserved_across_a_resort_when_entry_remains_visible(self) -> None:
        target_id = self.ids[0]
        self.controller.set_focused_id(target_id)
        self.controller.set_sort("term", "asc")
        self.assertEqual(self.controller.focused_id, target_id)

    def test_checked_ids_are_preserved_across_a_resort(self) -> None:
        checked = set(self.ids[:2])
        self.controller.set_checked_ids(checked)
        self.controller.set_sort("created_at", "asc")
        self.assertEqual(self.controller.checked_ids, checked)

    def test_sort_never_touches_star_or_collection_membership(self) -> None:
        from src.collections import add_entries_to_system_collection, get_entry_ids_in_system_collection

        add_entries_to_system_collection([self.ids[0]], "starred")
        before = get_entry_ids_in_system_collection(self.ids, "starred")
        self.controller.set_sort("term", "asc")
        after = get_entry_ids_in_system_collection(self.ids, "starred")
        self.assertEqual(before, after)

    def test_repeated_identical_sort_call_is_a_no_op(self) -> None:
        self.controller.set_sort("term", "asc")
        rows_before = self.controller.model.rows()
        self.controller.set_sort("term", "asc")
        self.assertEqual(self.controller.model.rows(), rows_before)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesViewSortAndResultCountTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_sort_combo_offers_every_sort_option_in_order(self) -> None:
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        labels = [view._sort_combo.itemText(i) for i in range(view._sort_combo.count())]
        self.assertEqual(labels, [label for label, _by, _direction in SORT_OPTIONS])

    def test_choosing_a_sort_option_calls_through_to_the_controller(self) -> None:
        add_entry("English", "Chinese", "word", "gamma", "m")
        add_entry("English", "Chinese", "word", "alpha", "m")
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        index = [label for label, _by, _direction in SORT_OPTIONS].index("Term (A-Z)")
        view._sort_combo.setCurrentIndex(index)
        self.assertEqual([r["term"] for r in controller.model.rows()], ["alpha", "gamma"])

    # Corrective fix regression tests: a prior version of this checkpoint
    # left QTableView.setSortingEnabled(True) in place alongside the new
    # "Sort by" combo. QSortFilterProxyModel then owned an independent
    # sort state Qt directly wires header clicks to (and which the proxy
    # defaults to column 0 the instant setSortingEnabled(True) runs, not
    # column -1) -- a parallel sorting mechanism that could silently
    # override "Sort by"'s real order. These tests check the *visible*
    # proxy/table order, not just EntriesController.model.rows() (the
    # source model) -- checking only the source model is exactly what let
    # the original defect through 587/587 green.

    def _visible_terms(self, view: EntriesView) -> list[str]:
        term_column = view._controller.model.COLUMNS.index("term")
        return [view._proxy.index(row, term_column).data() for row in range(view._proxy.rowCount())]

    def test_table_native_sorting_is_disabled(self) -> None:
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        self.assertFalse(view._table.isSortingEnabled())

    def test_proxy_has_no_active_sort_column_at_construction(self) -> None:
        add_entry("English", "Chinese", "word", "gamma", "m")
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        self.assertEqual(view._proxy.sortColumn(), -1)

    def test_visible_table_order_follows_sort_by_not_just_the_source_model(self) -> None:
        """The exact check the original defect's test suite was missing:
        the user-visible proxy order, not EntriesController.model.rows()."""
        add_entry("English", "Chinese", "word", "gamma", "m")
        add_entry("English", "Chinese", "word", "alpha", "m")
        add_entry("English", "Chinese", "word", "beta", "m")
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        index = [label for label, _by, _direction in SORT_OPTIONS].index("Term (A-Z)")
        view._sort_combo.setCurrentIndex(index)
        self.assertEqual(self._visible_terms(view), ["alpha", "beta", "gamma"])

    def test_a_native_header_click_does_not_create_a_parallel_sort_order(self) -> None:
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest

        add_entry("English", "Chinese", "word", "gamma", "m")
        add_entry("English", "Chinese", "word", "alpha", "m")
        add_entry("English", "Chinese", "word", "beta", "m")
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.show()
        view.refresh()
        self.app.processEvents()

        before = self._visible_terms(view)

        header = view._table.horizontalHeader()
        term_column = controller.model.COLUMNS.index("term")
        x = header.sectionViewportPosition(term_column) + header.sectionSize(term_column) // 2
        y = header.height() // 2
        QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x, y))
        self.app.processEvents()

        self.assertEqual(view._proxy.sortColumn(), -1)
        self.assertEqual(self._visible_terms(view), before)

    def test_sort_by_correctly_reorders_the_visible_table_even_after_a_header_click_attempt(self) -> None:
        """The precise regression scenario reported: a header click must
        never leave the proxy "stuck" on its own order such that a later
        Sort by change stops visibly taking effect."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest

        add_entry("English", "Chinese", "word", "gamma", "m")
        add_entry("English", "Chinese", "word", "alpha", "m")
        add_entry("English", "Chinese", "word", "beta", "m")
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.show()
        view.refresh()
        self.app.processEvents()

        header = view._table.horizontalHeader()
        term_column = controller.model.COLUMNS.index("term")
        x = header.sectionViewportPosition(term_column) + header.sectionSize(term_column) // 2
        y = header.height() // 2
        QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x, y))
        self.app.processEvents()

        sort_index = [label for label, _by, _direction in SORT_OPTIONS].index("Term (A-Z)")
        view._sort_combo.setCurrentIndex(sort_index)
        self.assertEqual(self._visible_terms(view), ["alpha", "beta", "gamma"])


# --- EXIT-BUG-003: Result count ---------------------------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ResultCountTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self.ids = [
            add_entry("English", "Chinese", "word", "alpha", "m"),
            add_entry("English", "Chinese", "word", "beta", "m"),
            add_entry("English", "Chinese", "phrase", "gamma", "m"),
        ]
        self.controller = EntriesController()
        self.view = EntriesView(self.controller)
        self.addCleanup(self.view.deleteLater)
        self.view.refresh()

    def test_base_scope_count(self) -> None:
        self.assertEqual(self.view._result_count_label.text(), "3 entries")

    def test_search_narrows_the_count(self) -> None:
        self.controller.set_search_text("alpha")
        self.assertEqual(self.view._result_count_label.text(), "1 entry")

    def test_filter_narrows_the_count(self) -> None:
        self.controller.set_entry_type("phrase")
        self.assertEqual(self.view._result_count_label.text(), "1 entry")

    def test_combined_scope_search_and_filter_count(self) -> None:
        collection_id = create_collection("Test Collection", card_size=3)
        add_entries_to_collection(self.ids[:2], collection_id)
        self.controller.set_scope(f"collection:{collection_id}")
        self.controller.set_entry_type("word")
        self.controller.set_search_text("beta")
        self.assertEqual(self.view._result_count_label.text(), "1 entry")

    def test_clearing_filters_restores_the_count(self) -> None:
        self.controller.set_entry_type("phrase")
        self.controller.set_entry_type("All")
        self.assertEqual(self.view._result_count_label.text(), "3 entries")

    def test_sorting_does_not_change_the_count(self) -> None:
        self.controller.set_sort("term", "asc")
        self.assertEqual(self.view._result_count_label.text(), "3 entries")

    def test_batch_selection_count_is_a_separate_concept(self) -> None:
        self.controller.set_checked_ids(set(self.ids))
        self.assertEqual(self.view._result_count_label.text(), "3 entries")
        self.assertIn("3", self.view._batch_count_label.text())


# --- Cross-feature integration ----------------------------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CrossFeatureIntegrationTests(_SyntheticDatabaseTestCase):
    """High-leverage integrated-journey coverage (prompt § 4/§ 8): the
    seven already-accepted M17 checkpoints connected as one product, not
    verified in isolation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self.entry_ids = [add_entry("English", "Chinese", "word", f"term{i}", f"meaning{i}") for i in range(3)]
        self.collection_id = create_collection("IELTS Core", card_size=3)
        add_entries_to_collection(self.entry_ids, self.collection_id)

    def test_collections_to_entries_opens_exact_scope(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        window._open_entries_with_scope(EntriesScopeIntent(scope=f"collection:{self.collection_id}"))
        self.assertEqual(window.app_state.workspace, Workspace.ENTRIES)
        self.assertEqual(window.entries_controller.scope, f"collection:{self.collection_id}")
        self.assertEqual(len(window.entries_controller.model.rows()), 3)

    def test_collection_card_opens_exact_review_card_not_a_fallback(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        window._open_review_at_card(StudyTargetIntent(collection_id=self.collection_id, card_number=1))
        self.assertEqual(window.app_state.workspace, Workspace.REVIEW)
        self.assertEqual(window.app_state.mode, ShellMode.STUDY)
        card = window.review_controller.current_card()
        self.assertIsNotNone(card)

    def test_missing_card_fails_honestly_without_navigating_or_falling_back(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        with patch("src.ui_desktop.main_window.QMessageBox.warning"):
            window._open_review_at_card(StudyTargetIntent(collection_id=self.collection_id, card_number=999))
        # Never entered Study Mode for a Card that doesn't exist.
        self.assertNotEqual(window.app_state.mode, ShellMode.STUDY)

    def test_review_to_quiz_preserves_collection_and_card_context(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        window._open_review_at_card(StudyTargetIntent(collection_id=self.collection_id, card_number=1))
        intent = QuizLaunchIntent(
            source="review_quick_quiz",
            collection_id=self.collection_id,
            collection_name="IELTS Core",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=len(self.entry_ids),
            reason="quick_quiz",
        )
        window._start_quiz(intent)
        self.assertEqual(window.app_state.workspace, Workspace.QUIZ)
        self.assertEqual(window.app_state.mode, ShellMode.STUDY)
        self.assertIsNotNone(window.quiz_controller.intent)
        self.assertEqual(window.quiz_controller.intent.collection_id, self.collection_id)
        self.assertEqual(window.quiz_controller.intent.card_number, 1)

    def test_study_exit_restores_the_correct_management_workspace_and_rail_state(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        window.show()
        self.app.processEvents()
        window._open_entries_with_scope(EntriesScopeIntent(scope=f"collection:{self.collection_id}"))
        window._open_review_at_card(StudyTargetIntent(collection_id=self.collection_id, card_number=1))
        self.assertFalse(window._navigation_rail.isVisible())

        window._exit_study_mode()

        self.assertEqual(window.app_state.workspace, Workspace.ENTRIES)
        self.assertEqual(window.app_state.mode, ShellMode.MANAGEMENT)
        self.assertTrue(window._navigation_rail.isVisible())
        active = [key for key, button in window._navigation_rail._buttons.items() if button.isChecked()]
        self.assertEqual(active, ["entries"])

    def test_theme_switch_never_mutates_entry_data(self) -> None:
        app, window, theme_manager = build_application([])
        self.addCleanup(window.deleteLater)
        before = [dict(row) for row in search_entries()]

        theme_manager.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        theme_manager.apply(Appearance.DARK, Accent.CALM_BLUE)
        theme_manager.apply(Appearance.SYSTEM, Accent.CALM_BLUE)

        after = [dict(row) for row in search_entries()]
        self.assertEqual(before, after)

    def test_theme_switch_never_resets_entries_presentation_state(self) -> None:
        app, window, theme_manager = build_application([])
        self.addCleanup(window.deleteLater)
        window.entries_controller.set_scope(f"collection:{self.collection_id}")
        window.entries_controller.set_sort("term", "asc")
        window.entries_controller.set_entry_type("word")

        theme_manager.apply(Appearance.DARK, Accent.CALM_BLUE)

        self.assertEqual(window.entries_controller.scope, f"collection:{self.collection_id}")
        self.assertEqual(window.entries_controller.sort_by, "term")
        self.assertEqual(window.entries_controller.entry_type, "word")

    def test_repeated_navigation_does_not_duplicate_review_evidence(self) -> None:
        """Navigating Collections -> Study -> exit -> Study again for the
        same Card must not itself write any learning evidence -- opening
        a Card is a read; review/correct/wrong counts are only ever
        written by an explicit grading action, unaffected by this
        checkpoint."""
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        before = {
            r["id"]: (r["review_count"], r["correct_count"], r["wrong_count"]) for r in search_entries()
        }

        window._open_review_at_card(StudyTargetIntent(collection_id=self.collection_id, card_number=1))
        window._exit_study_mode()
        window._open_review_at_card(StudyTargetIntent(collection_id=self.collection_id, card_number=1))

        after = {
            r["id"]: (r["review_count"], r["correct_count"], r["wrong_count"]) for r in search_entries()
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

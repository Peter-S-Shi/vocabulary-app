from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QDialog, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db, quiz
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry

"""
Focused tests for M17 Feature 2 -- Review / Study Mode Immersive Focus
(DESIGN.md § 6.3 `VR-STUDY-001`, parent pattern P3). Per DESIGN.md § 2
Rule C, none of this proves the canonical composition was *visually*
realized -- only that the required regions/behaviors exist structurally,
that the desktop layer reads real reusable-core data without duplicating
business logic, and that Review's frozen learning semantics (browsing
never completes learning) actually hold. Native human visual acceptance
is a separate, required gate (see AGENTS.md).
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.review_controller import (
        QUICK_QUIZ_DEFAULT_TYPE,
        QUIZ_TYPE_LABELS,
        ReviewController,
    )
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.motion.transitions import TransitionManager
    from src.ui_desktop.state.app_state import ShellMode, Workspace
    from src.ui_desktop.state.handoff import QuizLaunchIntent
    from src.ui_desktop.views.review_view import ReviewView

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    """Shared setup matching the existing repository pattern (see
    tests/test_m17_today_command_center_shell.py): swap db.DB_PATH to a
    temporary synthetic database, never the user's personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m17_review.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_card(self, terms, card_size=None, collection_name="Review Test Collection"):
        entry_ids = [add_entry("French", "English", "word", term, meaning) for term, meaning in terms]
        collection_id = create_collection(collection_name, card_size=card_size or len(entry_ids))
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids

    def _complete_quiz(self, collection_id, card_number, entry_id, term, meaning, *, correct=True):
        session_id = quiz.create_quiz_session(collection_id, card_number, "term_to_meaning", 1)
        quiz.record_quiz_answer(session_id, entry_id, term, meaning, meaning if correct else "wrong", correct)
        quiz.mark_quiz_session_completed(session_id)
        return session_id


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewControllerProjectionTests(_SyntheticDatabaseTestCase):
    def test_open_default_false_on_empty_database(self) -> None:
        controller = ReviewController()
        self.assertFalse(controller.open_default())
        self.assertIsNone(controller.current_card())
        self.assertEqual(controller.entries(), [])

    def test_open_default_prefers_never_quizzed_card(self) -> None:
        collection_id, entry_ids = self._make_card([("chat", "cat"), ("chien", "dog")])
        self._complete_quiz(collection_id, 1, entry_ids[0], "chat", "cat")
        other_collection_id, _ = self._make_card([("pomme", "apple")], collection_name="Other Collection")

        controller = ReviewController()
        self.assertTrue(controller.open_default())
        card = controller.current_card()
        self.assertEqual(card["status"], "never_quizzed")
        self.assertEqual(card["collection_id"], other_collection_id)

    def test_current_card_carries_stable_card_id(self) -> None:
        self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()
        self.assertIsNotNone(controller.current_card()["card_id"])

    def test_entries_reflect_real_core_composition(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = ReviewController()
        controller.open_default()
        entries = controller.entries()
        self.assertEqual([entry["term"] for entry in entries], ["chat", "chien"])
        self.assertEqual([entry["meaning"] for entry in entries], ["cat", "dog"])

    def test_history_reflects_completed_quiz_sessions(self) -> None:
        collection_id, entry_ids = self._make_card([("chat", "cat")])
        self._complete_quiz(collection_id, 1, entry_ids[0], "chat", "cat")

        controller = ReviewController()
        controller.open_default()
        history = controller.history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["correct_count"], 1)

    def test_history_empty_for_never_quizzed_card(self) -> None:
        self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()
        self.assertEqual(controller.history(), [])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewControllerNavigationTests(_SyntheticDatabaseTestCase):
    def test_previous_disabled_at_first_entry(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = ReviewController()
        controller.open_default()
        self.assertFalse(controller.can_go_previous())
        self.assertTrue(controller.can_go_next())

    def test_next_disabled_at_last_entry(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = ReviewController()
        controller.open_default()
        controller.go_next()
        self.assertFalse(controller.can_go_next())
        self.assertTrue(controller.can_go_previous())

    def test_navigation_out_of_bounds_is_a_no_op(self) -> None:
        self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()
        controller.go_previous()
        self.assertEqual(controller.entry_index(), 0)
        controller.go_next()
        self.assertEqual(controller.entry_index(), 0)

    def test_go_to_entry_index_updates_current_entry(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog"), ("pomme", "apple")])
        controller = ReviewController()
        controller.open_default()
        controller.go_to_entry_index(2)
        self.assertEqual(controller.entry_index(), 2)
        self.assertEqual(controller.current_entry()["term"], "pomme")

    def test_entry_progress_reports_position_and_total(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = ReviewController()
        controller.open_default()
        self.assertEqual(controller.entry_progress(), (1, 2))
        controller.go_next()
        self.assertEqual(controller.entry_progress(), (2, 2))

    def test_visited_entries_are_session_local_not_persisted(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = ReviewController()
        controller.open_default()
        first_entry_id = controller.current_entry()["id"]
        self.assertTrue(controller.is_entry_visited(first_entry_id))
        controller.go_next()
        second_entry_id = controller.current_entry()["id"]
        self.assertTrue(controller.is_entry_visited(second_entry_id))

        # A fresh controller has no memory of the previous one's browsing --
        # visited state is transient presentation state, never written
        # through core/SQLite (M17 Feature 2 prompt: "transient Review
        # state not leaking into durable/core state").
        fresh_controller = ReviewController()
        fresh_controller.open_default()
        self.assertFalse(fresh_controller.is_entry_visited(second_entry_id))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewControllerCardSelectionTests(_SyntheticDatabaseTestCase):
    def test_open_card_switches_to_requested_card(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")], card_size=1)
        controller = ReviewController()
        controller.open_default()
        self.assertTrue(controller.open_card(collection_id, 2))
        self.assertEqual(controller.current_card()["card_number"], 2)
        self.assertEqual(controller.current_entry()["term"], "chien")

    def test_open_card_resets_entry_index(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")], card_size=1)
        controller = ReviewController()
        controller.open_default()
        controller.open_card(collection_id, 2)
        self.assertEqual(controller.entry_index(), 0)

    def test_open_card_returns_false_for_missing_card_without_disturbing_state(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()
        before = controller.current_card()
        self.assertFalse(controller.open_card(collection_id, 99))
        self.assertEqual(controller.current_card(), before)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewControllerQuizHandoffTests(_SyntheticDatabaseTestCase):
    def test_quick_quiz_intent_uses_default_type_and_current_card_context(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()
        intent = controller.build_quick_quiz_intent()
        self.assertIsInstance(intent, QuizLaunchIntent)
        self.assertEqual(intent.source, "review_quick_quiz")
        self.assertEqual(intent.quiz_type, QUICK_QUIZ_DEFAULT_TYPE)
        self.assertEqual(intent.collection_id, collection_id)
        self.assertEqual(intent.card_number, 1)
        self.assertIsNotNone(intent.card_id)

    def test_choose_quiz_type_intent_uses_selected_type(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()
        intent = controller.build_choose_quiz_type_intent("term_to_meaning_mcq")
        self.assertEqual(intent.quiz_type, "term_to_meaning_mcq")
        self.assertEqual(intent.source, "review_choose_quiz_type")
        self.assertEqual(intent.collection_id, collection_id)
        self.assertEqual(intent.card_number, 1)

    def test_choose_quiz_type_matching_is_forced_whole_collection(self) -> None:
        """M17 Feature 3 compatibility check: plain Matching is
        whole-Collection only in the current product (Streamlit always
        forces card_number=0 for it) -- never Card-scoped, regardless of
        which Card Review currently displays."""
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog"), ("pomme", "apple"), ("poire", "pear")])
        controller = ReviewController()
        controller.open_default()
        intent = controller.build_choose_quiz_type_intent("matching", matching_item_count=4)
        self.assertEqual(intent.quiz_type, "matching")
        self.assertEqual(intent.card_number, 0)
        self.assertIsNone(intent.card_id)
        self.assertEqual(intent.item_count, 4)

    def test_matching_item_count_options_bounded_by_collection_size(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog"), ("pomme", "apple")])
        controller = ReviewController()
        controller.open_default()
        options = controller.matching_item_count_options()
        self.assertTrue(all(option <= 3 for option in options))

    def test_quiz_intents_are_none_without_a_current_card(self) -> None:
        controller = ReviewController()
        controller.open_default()  # empty database
        self.assertIsNone(controller.build_quick_quiz_intent())
        self.assertIsNone(controller.build_choose_quiz_type_intent("term_to_meaning"))

    def test_quiz_type_options_are_plain_types_only(self) -> None:
        """Template-aware types are offered through a separate template
        picker (available_template_sources/template_rules), not this flat
        list -- see ReviewDialogTests for the template flow."""
        controller = ReviewController()
        plain_types = {qt for qt in quiz.QUIZ_TYPES if not qt.startswith("template_field_")}
        self.assertEqual(set(controller.quiz_type_options()), plain_types)
        self.assertEqual(set(QUIZ_TYPE_LABELS.keys()), set(quiz.QUIZ_TYPES.keys()))

    def test_no_template_sources_for_a_plain_collection(self) -> None:
        self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()
        self.assertEqual(controller.available_template_sources(), [])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewDoesNotMutateLearningStateTests(_SyntheticDatabaseTestCase):
    """Frozen semantics (DESIGN.md § 6.3 Review semantics; ARCHITECTURE.md
    Learning Completion Semantics): browsing a Card in Review must never
    itself create a completion event or touch legacy scheduling state."""

    def test_browsing_creates_no_quiz_sessions(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog"), ("pomme", "apple")])
        with db.get_connection() as connection:
            before = connection.execute("SELECT COUNT(*) AS n FROM quiz_sessions").fetchone()["n"]

        controller = ReviewController()
        controller.open_default()
        controller.go_next()
        controller.go_next()
        controller.go_previous()
        controller.build_quick_quiz_intent()
        controller.build_choose_quiz_type_intent("matching")

        with db.get_connection() as connection:
            after = connection.execute("SELECT COUNT(*) AS n FROM quiz_sessions").fetchone()["n"]
        self.assertEqual(before, after)

    def test_browsing_creates_no_legacy_review_scheduling_rows(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        with db.get_connection() as connection:
            table_present = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='card_review_states'"
            ).fetchone()
        if table_present is None:
            self.skipTest("card_review_states table not present in this schema")

        with db.get_connection() as connection:
            before = connection.execute("SELECT COUNT(*) AS n FROM card_review_states").fetchone()["n"]

        controller = ReviewController()
        controller.open_default()
        controller.go_next()

        with db.get_connection() as connection:
            after = connection.execute("SELECT COUNT(*) AS n FROM card_review_states").fetchone()["n"]
        self.assertEqual(before, after)


class ReviewCoreBoundaryTests(unittest.TestCase):
    """Reusable-core boundary guards (M16.1 contract): Review orchestrates
    presentation only, and never reactivates the legacy SRS scheduler."""

    def test_view_has_no_raw_sql_and_no_direct_db_import(self) -> None:
        path = PROJECT_ROOT / "src" / "ui_desktop" / "views" / "review_view.py"
        text = path.read_text(encoding="utf-8")
        upper = text.upper()
        for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, upper)
        self.assertNotIn("import sqlite3", text)
        self.assertNotIn("from src import db", text)

    def test_controller_has_no_raw_sql(self) -> None:
        # ReviewController legitimately uses db.get_connection() to pass a
        # raw connection into src.learning_workflow's read functions,
        # exactly like TodayController -- only literal SQL keywords are
        # forbidden here, not the connection helper itself.
        path = PROJECT_ROOT / "src" / "ui_desktop" / "controllers" / "review_controller.py"
        text = path.read_text(encoding="utf-8")
        upper = text.upper()
        for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, upper)
        self.assertNotIn("import sqlite3", text)

    def test_controller_does_not_import_legacy_review_scheduler(self) -> None:
        path = PROJECT_ROOT / "src" / "ui_desktop" / "controllers" / "review_controller.py"
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("from src.review import", text)
        self.assertNotIn("import src.review", text)
        self.assertNotIn("src.review.", text)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewViewStructureTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_empty_database_produces_honest_empty_state_not_a_crash(self) -> None:
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        controller.open_default()

        empty_labels = [
            child
            for child in view.findChildren(QWidget)
            if getattr(child, "objectName", lambda: "")() == "review-empty-state"
        ]
        self.assertGreater(len(empty_labels), 0)

    def test_session_bar_shows_collection_card_and_progress(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        controller.open_default()

        self.assertIn("Card 1", view._context_label.text())
        self.assertEqual(view._progress_label.text(), "Review 1/2")

    def test_quick_quiz_button_launches_a_real_quiz(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        controller.open_default()

        buttons = [
            widget
            for widget in view.findChildren(QWidget)
            if getattr(widget, "objectName", lambda: "")() == "review-quick-quiz-button"
        ]
        self.assertEqual(len(buttons), 1)
        self.assertTrue(buttons[0].isEnabled())

        received: list[object] = []
        view.quiz_launch_requested.connect(received.append)
        buttons[0].click()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].source, "review_quick_quiz")
        self.assertEqual(received[0].collection_id, collection_id)

    def test_previous_next_buttons_respect_bounds(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        controller.open_default()

        previous_button = next(
            w for w in view.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "review-nav-previous"
        )
        next_button = next(
            w for w in view.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "review-nav-next"
        )
        self.assertFalse(previous_button.isEnabled())
        self.assertTrue(next_button.isEnabled())

    def test_drawer_hidden_by_default_and_toggle_reveals_it(self) -> None:
        self._make_card([("chat", "cat")])
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.close)
        # A widget's isVisible() reflects its whole ancestor chain -- the
        # drawer only reports itself visible once this standalone view has
        # actually been shown (tests/test_m16_2_desktop_vertical_slice.py's
        # established pattern for the same Qt behavior).
        view.show()
        self.app.processEvents()
        controller.open_default()

        self.assertFalse(view._drawer.isVisible())
        view._drawer_toggle.click()
        self.assertTrue(view._drawer.isVisible())
        view._drawer_toggle.click()
        self.assertFalse(view._drawer.isVisible())

    def test_drawer_close_button_hides_it_and_unchecks_toggle(self) -> None:
        self._make_card([("chat", "cat")])
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.close)
        view.show()
        self.app.processEvents()
        controller.open_default()

        view._drawer_toggle.click()
        self.assertTrue(view._drawer.isVisible())

        close_button = next(
            w for w in view._drawer.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "review-drawer-close"
        )
        close_button.click()
        self.assertFalse(view._drawer.isVisible())
        self.assertFalse(view._drawer_toggle.isChecked())

    def test_drawer_lists_entries_with_current_one_highlighted(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        controller.open_default()

        current_rows = [
            w
            for w in view._drawer.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "review-drawer-entry-current"
        ]
        self.assertEqual(len(current_rows), 1)
        self.assertIn("chat", current_rows[0].text())

    def test_drawer_toggle_with_real_motion_manager_is_lifecycle_safe(self) -> None:
        """Drawer reveal reuses the shared TransitionManager (module
        docstring); rapid open/close/open must not crash or leave the
        drawer's opacity effect stuck (M17 Feature 2 prompt: "explicitly
        verify lifecycle safety for the short-lived drawer/effects")."""
        self._make_card([("chat", "cat")])
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.close)
        view.set_motion(TransitionManager())
        view.show()
        self.app.processEvents()
        controller.open_default()

        view._drawer_toggle.click()
        view._drawer_toggle.click()
        view._drawer_toggle.click()
        self.assertTrue(view._drawer.isVisible())


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewDialogTests(_SyntheticDatabaseTestCase):
    """The two P6 utility dialogs (DESIGN.md § 8): Study Collection/Card
    selector and Choose Quiz Type. Exercised directly (not via a blocking
    modal .exec()) so these headless tests never wait on real user input."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_card_selector_dialog_switches_card_on_select(self) -> None:
        from src.ui_desktop.views.review_view import _StudyCardSelectorDialog

        self._make_card([("chat", "cat"), ("chien", "dog")], card_size=1)
        controller = ReviewController()
        controller.open_default()

        dialog = _StudyCardSelectorDialog(controller)
        self.addCleanup(dialog.deleteLater)
        card_index = dialog._card_combo.findData(2)
        self.assertGreaterEqual(card_index, 0)
        dialog._card_combo.setCurrentIndex(card_index)
        dialog._select()

        self.assertEqual(controller.current_card()["card_number"], 2)

    def test_card_selector_dialog_warns_on_stale_card(self) -> None:
        from src.ui_desktop.views.review_view import _StudyCardSelectorDialog

        self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()

        dialog = _StudyCardSelectorDialog(controller)
        self.addCleanup(dialog.deleteLater)
        dialog._card_combo.clear()
        dialog._card_combo.addItem("Card 99", 99)
        dialog._select()

        self.assertIn("no longer available", dialog._warning_label.text())

    def test_start_button_launches_the_selected_type_and_closes(self) -> None:
        """M17 Feature 3: replaces the transitional honest-unavailable
        message -- confirming a real choice now performs a real launch."""
        from src.ui_desktop.views.review_view import _ChooseQuizTypeDialog

        collection_id, _ = self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()

        dialog = _ChooseQuizTypeDialog(controller)
        self.addCleanup(dialog.deleteLater)
        mcq_index = dialog._type_combo.findData("term_to_meaning_mcq")
        self.assertGreaterEqual(mcq_index, 0)
        dialog._type_combo.setCurrentIndex(mcq_index)

        received: list[object] = []
        dialog.launch_requested.connect(received.append)
        start_button = next(
            w
            for w in dialog.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "review-choose-quiz-type-start-button"
        )
        self.assertTrue(start_button.isEnabled())
        start_button.click()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].quiz_type, "term_to_meaning_mcq")
        self.assertEqual(received[0].collection_id, collection_id)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_matching_selection_reveals_item_count_combo(self) -> None:
        from src.ui_desktop.views.review_view import _ChooseQuizTypeDialog

        self._make_card([("chat", "cat"), ("chien", "dog"), ("pomme", "apple"), ("poire", "pear")])
        controller = ReviewController()
        controller.open_default()

        dialog = _ChooseQuizTypeDialog(controller)
        self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog._matching_count_combo.isHidden())

        matching_index = dialog._type_combo.findData("matching")
        self.assertGreaterEqual(matching_index, 0)
        dialog._type_combo.setCurrentIndex(matching_index)

        self.assertFalse(dialog._matching_count_combo.isHidden())

    def test_matching_launch_is_whole_collection_not_card_scoped(self) -> None:
        from src.ui_desktop.views.review_view import _ChooseQuizTypeDialog

        collection_id, _ = self._make_card(
            [("chat", "cat"), ("chien", "dog"), ("pomme", "apple"), ("poire", "pear")], card_size=1
        )
        controller = ReviewController()
        controller.open_default()

        dialog = _ChooseQuizTypeDialog(controller)
        self.addCleanup(dialog.deleteLater)
        matching_index = dialog._type_combo.findData("matching")
        dialog._type_combo.setCurrentIndex(matching_index)

        received: list[object] = []
        dialog.launch_requested.connect(received.append)
        start_button = next(
            w
            for w in dialog.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "review-choose-quiz-type-start-button"
        )
        start_button.click()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].quiz_type, "matching")
        self.assertEqual(received[0].card_number, 0)
        self.assertEqual(received[0].collection_id, collection_id)

    def test_template_section_hidden_when_no_eligible_sources(self) -> None:
        from src.ui_desktop.views.review_view import _ChooseQuizTypeDialog

        self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()

        dialog = _ChooseQuizTypeDialog(controller)
        self.addCleanup(dialog.deleteLater)
        self.assertIsNone(dialog._template_checkbox)
        self.assertIsNone(dialog._template_section)

    def test_start_without_touching_template_section_uses_plain_type(self) -> None:
        from src.template_quiz import get_available_template_quiz_sources_for_card
        from src.ui_desktop.views.review_view import _ChooseQuizTypeDialog

        collection_id, _ = self._make_card([("chat", "cat")])
        controller = ReviewController()
        controller.open_default()
        # No entry in this synthetic Card uses a rule-eligible template, so
        # the template section never appears -- this test only proves the
        # plain-type path stays safe when template use is (correctly)
        # unavailable, matching test_template_section_hidden_when_no_eligible_sources.
        self.assertEqual(get_available_template_quiz_sources_for_card(collection_id, 1), [])

        dialog = _ChooseQuizTypeDialog(controller)
        self.addCleanup(dialog.deleteLater)
        received: list[object] = []
        dialog.launch_requested.connect(received.append)
        start_button = next(
            w
            for w in dialog.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "review-choose-quiz-type-start-button"
        )
        start_button.click()
        # Falls through to the plain-type path (the default selection),
        # which is a valid launch -- proving the absence of a template
        # section never blocks a normal Choose Quiz Type flow.
        self.assertEqual(len(received), 1)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class MainWindowStudyModeIntegrationTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        # Qt's isVisible() reflects the whole ancestor chain; a widget only
        # reports itself visible once the top-level window has been shown
        # (tests/test_m16_2_desktop_vertical_slice.py's established pattern).
        self.window.show()
        self.app.processEvents()

    def test_clicking_study_rail_destination_enters_review_and_hides_management_rail(self) -> None:
        self.window._navigation_rail._buttons["study"].click()

        self.assertIs(self.window.current_workspace(), Workspace.REVIEW)
        self.assertIs(self.window.app_state.mode, ShellMode.STUDY)
        self.assertIs(self.window._workspace_stack.currentWidget(), self.window.review_view)
        self.assertFalse(self.window._navigation_rail.isVisible())
        self.assertFalse(self.window._study_toolbar.isVisible())

    def test_exit_review_restores_management_rail_and_last_workspace(self) -> None:
        self.window._navigation_rail._buttons["entries"].click()
        self.window._navigation_rail._buttons["study"].click()

        self.window.review_view.exit_requested.emit()

        self.assertIs(self.window.app_state.mode, ShellMode.MANAGEMENT)
        self.assertIs(self.window.current_workspace(), Workspace.ENTRIES)
        self.assertTrue(self.window._navigation_rail.isVisible())
        self.assertIs(self.window._workspace_stack.currentWidget(), self.window.entries_view)

    def test_review_empty_state_open_entries_exits_study_mode_to_entries(self) -> None:
        self.window._navigation_rail._buttons["study"].click()

        self.window.review_view.navigate_to_entries_requested.emit()

        self.assertIs(self.window.current_workspace(), Workspace.ENTRIES)
        self.assertIs(self.window.app_state.mode, ShellMode.MANAGEMENT)

    def test_entering_review_loads_the_current_card_roster(self) -> None:
        entry_id = add_entry("French", "English", "word", "chat", "cat")
        collection_id = create_collection("Rail Entry Collection", card_size=1)
        add_entries_to_collection([entry_id], collection_id)

        self.window._navigation_rail._buttons["study"].click()

        self.assertIsNotNone(self.window.review_controller.current_card())


if __name__ == "__main__":
    unittest.main()

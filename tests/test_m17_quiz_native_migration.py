from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QComboBox, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db, quiz
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry, create_entry_with_template
from src.entry_templates import ensure_french_verb_present_template

"""
Focused tests for M17 Feature 3 -- native Quiz migration (DESIGN.md § 6.3
`VR-STUDY-001`, § 7.2 coverage matrix: Quiz Session / Quiz Completion are
class A under the same authority as Review). Per DESIGN.md § 2 Rule C,
none of this proves the canonical composition was *visually* realized --
only that session/grading/completion semantics match the existing core
exactly, that the desktop layer duplicates no business logic, and that
Review/Today -> Quiz integration produces one consistent launch path.
Native human visual acceptance is a separate, required gate (AGENTS.md).
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.quiz_controller import MCQ_FAMILY, SELF_GRADED_FAMILY, QuizController
    from src.ui_desktop.controllers.review_controller import ReviewController
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.state.app_state import ShellMode, Workspace
    from src.ui_desktop.state.handoff import (
        QuizLaunchIntent,
        learning_action_intent_from_recommendation,
        quiz_launch_intent_from_learning_action_intent,
    )
    from src.ui_desktop.views.quiz_view import QuizView

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
        db.DB_PATH = self.root / "m17_quiz.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_card(self, terms, card_size=None, collection_name="Quiz Test Collection"):
        entry_ids = [add_entry("French", "English", "word", term, meaning) for term, meaning in terms]
        collection_id = create_collection(collection_name, card_size=card_size or len(entry_ids))
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids

    def _quick_intent(self, collection_id, card_number, card_id, entry_count, quiz_type="term_to_meaning"):
        return QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="",
            card_number=card_number,
            card_id=card_id,
            quiz_type=quiz_type,
            item_count=entry_count,
            reason="test",
        )

    def _make_template_verb_card(self, verbs, card_size=None, collection_name="Verb Collection"):
        """One Card of french_verb_present entries eligible for the
        template-aware Quiz path (TEMPLATE_QUIZ_RULES["french_verb_present"])."""
        template_id = ensure_french_verb_present_template()
        entry_ids = []
        for infinitive, meaning, je in verbs:
            entry_id = create_entry_with_template(
                entry_data={
                    "template_id": template_id,
                    "language": "French",
                    "explanation_language": "English",
                    "entry_type": "verb",
                },
                template_values={
                    "infinitive": infinitive,
                    "meaning": meaning,
                    "je": je,
                    "tu": je,
                    "il_elle_on": je,
                    "nous": je,
                    "vous": je,
                    "ils_elles": je,
                },
            )
            entry_ids.append(entry_id)
        collection_id = create_collection(collection_name, card_size=card_size or len(entry_ids))
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids, template_id


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizControllerStartTests(_SyntheticDatabaseTestCase):
    def test_start_self_graded_creates_session_and_items(self) -> None:
        collection_id, entry_ids = self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = QuizController()
        intent = self._quick_intent(collection_id, 1, None, 2, "term_to_meaning")

        self.assertTrue(controller.start(intent))
        self.assertIsNotNone(controller.session_id)
        self.assertEqual(len(controller.items), 2)
        session = quiz.get_quiz_session(controller.session_id)
        self.assertEqual(session["status"], "active")
        self.assertEqual(session["total_items"], 2)

    def test_start_mcq_creates_session_with_options(self) -> None:
        # MCQ needs enough entries for 3 safe distractors per item.
        collection_id, _ = self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four"), ("cinq", "five")]
        )
        controller = QuizController()
        intent = self._quick_intent(collection_id, 1, None, 5, "term_to_meaning_mcq")

        self.assertTrue(controller.start(intent))
        self.assertEqual(controller.quiz_family(), MCQ_FAMILY)
        item = controller.current_item()
        self.assertIsNotNone(item)
        self.assertGreaterEqual(len(item["options"]), 4)

    def test_start_matching_forces_whole_collection_even_if_card_number_given(self) -> None:
        collection_id, _ = self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four")], card_size=1
        )
        controller = QuizController()
        # Deliberately construct a Card-scoped-looking matching intent to
        # prove the controller itself normalizes it (defense in depth,
        # not solely relied on from the caller).
        intent = self._quick_intent(collection_id, 1, 999, 4, "matching")

        self.assertTrue(controller.start(intent))
        self.assertEqual(controller.intent.card_number, 0)
        self.assertIsNone(controller.intent.card_id)
        session = quiz.get_quiz_session(controller.session_id)
        self.assertEqual(session["card_number"], 0)
        self.assertIsNone(session["card_id"])

    def test_start_template_quiz_generates_items_from_selected_rules(self) -> None:
        collection_id, entry_ids, template_id = self._make_template_verb_card(
            [("parler", "to speak", "parle"), ("manger", "to eat", "mange")]
        )
        controller = QuizController()
        intent = QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="",
            card_number=1,
            card_id=None,
            quiz_type="template_field_self_graded",
            item_count=2,
            reason="test",
            template_id=template_id,
            template_type="french_verb_present",
            template_rule_ids=("infinitive_to_je",),
        )

        self.assertTrue(controller.start(intent))
        self.assertEqual(controller.quiz_family(), SELF_GRADED_FAMILY)
        item = controller.current_item()
        self.assertIn(item["prompt"].split(" | ")[0], ("parler", "manger"))

    def test_start_fails_honestly_when_not_enough_entries_for_mcq(self) -> None:
        collection_id, _ = self._make_card([("un", "one")])
        controller = QuizController()
        intent = self._quick_intent(collection_id, 1, None, 1, "term_to_meaning_mcq")

        self.assertFalse(controller.start(intent))
        self.assertIsNotNone(controller.start_error)
        self.assertIsNone(controller.session_id)

    def test_start_fails_honestly_for_template_quiz_without_rules(self) -> None:
        collection_id, _, template_id = self._make_template_verb_card([("parler", "to speak", "parle")])
        controller = QuizController()
        intent = QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="",
            card_number=1,
            card_id=None,
            quiz_type="template_field_self_graded",
            item_count=1,
            reason="test",
            template_id=template_id,
            template_type="french_verb_present",
            template_rule_ids=(),
        )

        self.assertFalse(controller.start(intent))
        self.assertIsNotNone(controller.start_error)
        self.assertIn("rule", controller.start_error.lower())

    def test_start_blocks_on_a_foreign_active_session_and_never_creates_a_second_one(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")])
        foreign_session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 2)

        controller = QuizController()
        intent = self._quick_intent(collection_id, 1, None, 2)
        with db.get_connection() as connection:
            before = connection.execute("SELECT COUNT(*) AS n FROM quiz_sessions").fetchone()["n"]

        self.assertFalse(controller.start(intent))
        self.assertIsNotNone(controller.blocked_session)
        self.assertEqual(controller.blocked_session["id"], foreign_session_id)
        self.assertEqual(controller.pending_intent, intent)

        with db.get_connection() as connection:
            after = connection.execute("SELECT COUNT(*) AS n FROM quiz_sessions").fetchone()["n"]
        self.assertEqual(before, after)

    def test_cancel_blocked_and_retry_cancels_foreign_session_then_starts_pending_intent(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")])
        foreign_session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 2)

        controller = QuizController()
        intent = self._quick_intent(collection_id, 1, None, 2)
        controller.start(intent)
        self.assertIsNotNone(controller.blocked_session)

        self.assertTrue(controller.cancel_blocked_and_retry())

        self.assertIsNone(controller.blocked_session)
        self.assertIsNotNone(controller.session_id)
        self.assertNotEqual(controller.session_id, foreign_session_id)
        foreign_session = quiz.get_quiz_session(foreign_session_id)
        self.assertEqual(foreign_session["status"], "cancelled")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizControllerSelfGradedFlowTests(_SyntheticDatabaseTestCase):
    def test_full_self_graded_session_completes_and_records_correct_wrong_counts(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 2))

        controller.reveal_answer()
        self.assertTrue(controller.submit_self_graded(True))
        self.assertEqual(controller.current_index, 1)
        self.assertFalse(controller.show_answer)

        controller.reveal_answer()
        self.assertTrue(controller.submit_self_graded(False))

        self.assertIsNotNone(controller.completed_session)
        self.assertEqual(controller.completed_session["total_items"], 2)
        self.assertEqual(controller.completed_session["correct_count"], 1)
        self.assertEqual(controller.completed_session["wrong_count"], 1)

    def test_submit_before_reveal_is_a_no_op(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 1))

        self.assertFalse(controller.submit_self_graded(True))
        self.assertIsNone(controller.completed_session)

    def test_duplicate_answer_is_not_double_logged_and_does_not_advance(self) -> None:
        collection_id, entry_ids = self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 2))
        item = controller.current_item()

        # Simulate an out-of-band duplicate (e.g. a second submit racing
        # the first) by pre-logging the exact same (session, entry,
        # prompt) identity before the controller's own submit.
        quiz.record_quiz_answer(controller.session_id, item["entry_id"], item["prompt"], item["expected_answer"], "x", True)

        controller.reveal_answer()
        self.assertFalse(controller.submit_self_graded(True))
        self.assertEqual(controller.current_index, 0)  # never advanced

    def test_wrong_answer_adds_entry_to_mistake_book(self) -> None:
        collection_id, entry_ids = self._make_card([("chat", "cat")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 1))

        controller.reveal_answer()
        controller.submit_self_graded(False)

        mistake_book = quiz.get_mistake_book_collection()
        self.assertIsNotNone(mistake_book)
        with db.get_connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM entry_collections WHERE collection_id = ? AND entry_id = ?",
                (mistake_book["id"], entry_ids[0]),
            ).fetchone()
        self.assertIsNotNone(row)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizControllerMcqFlowTests(_SyntheticDatabaseTestCase):
    def _mcq_collection(self):
        return self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four"), ("cinq", "five")]
        )

    def test_submit_mcq_sets_feedback_and_locks_further_submits(self) -> None:
        collection_id, _ = self._mcq_collection()
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 5, "term_to_meaning_mcq"))
        item = controller.current_item()

        self.assertTrue(controller.submit_mcq(item["correct_answer"]))
        self.assertIsNotNone(controller.feedback)
        self.assertTrue(controller.feedback["is_correct"])

        # A second submit while feedback is showing must not re-log.
        self.assertFalse(controller.submit_mcq(item["correct_answer"]))

    def test_advance_after_mcq_moves_to_next_item(self) -> None:
        collection_id, _ = self._mcq_collection()
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 5, "term_to_meaning_mcq"))
        item = controller.current_item()
        controller.submit_mcq(item["correct_answer"])

        controller.advance_after_mcq()

        self.assertIsNone(controller.feedback)
        self.assertEqual(controller.current_index, 1)

    def test_mixed_mcq_disambiguates_prompt_identity_by_direction(self) -> None:
        """The same Entry answered in both MCQ directions within one mixed
        session must not collide as a duplicate (M17 Feature 3 prompt's
        answer-behavior preservation; mirrors quiz_page.py's prompt-suffix
        convention)."""
        collection_id, _ = self._mcq_collection()
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 5, "mixed_mcq"))
        item = controller.current_item()
        controller.submit_mcq(item["options"][0])

        with db.get_connection() as connection:
            logged_prompt = connection.execute(
                "SELECT prompt FROM quiz_item_logs WHERE session_id = ?", (controller.session_id,)
            ).fetchone()["prompt"]
        self.assertTrue(logged_prompt.endswith("]"))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizControllerMatchingFlowTests(_SyntheticDatabaseTestCase):
    def test_matching_requires_every_row_selected_before_submit(self) -> None:
        collection_id, _ = self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four")]
        )
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))

        self.assertFalse(controller.can_submit_matching())
        items = controller.matching_items()
        controller.set_matching_selection(items[0], controller.matching_choices()[0])
        self.assertFalse(controller.can_submit_matching())  # only 1 of N selected

    def test_full_matching_submit_grades_all_and_completes(self) -> None:
        collection_id, _ = self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four")]
        )
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))

        items = controller.matching_items()
        for item in items:
            controller.set_matching_selection(item, item["expected_meaning"])  # all correct

        self.assertTrue(controller.can_submit_matching())
        self.assertTrue(controller.submit_matching())

        self.assertIsNotNone(controller.completed_session)
        self.assertEqual(controller.completed_session["correct_count"], 4)
        self.assertEqual(controller.completed_session["wrong_count"], 0)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizControllerCancelRestartCompletionTests(_SyntheticDatabaseTestCase):
    def test_cancel_active_marks_session_cancelled_and_resets_controller(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 2))
        session_id = controller.session_id

        controller.cancel_active()

        self.assertIsNone(controller.session_id)
        self.assertIsNone(controller.intent)
        session = quiz.get_quiz_session(session_id)
        self.assertEqual(session["status"], "cancelled")

    def test_cancel_preserves_already_logged_answers(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 2))
        session_id = controller.session_id
        controller.reveal_answer()
        controller.submit_self_graded(True)

        controller.cancel_active()

        logs = quiz.get_quiz_item_logs(session_id)
        self.assertEqual(len(logs), 1)

    def test_restart_active_cancels_and_starts_a_fresh_session(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 2))
        original_session_id = controller.session_id

        self.assertTrue(controller.restart_active())

        self.assertIsNotNone(controller.session_id)
        self.assertNotEqual(controller.session_id, original_session_id)
        original_session = quiz.get_quiz_session(original_session_id)
        self.assertEqual(original_session["status"], "cancelled")

    def test_exit_active_is_the_only_way_to_leave_without_completing_and_it_cancels(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 1))
        session_id = controller.session_id

        controller.exit_active()

        self.assertEqual(quiz.get_quiz_session(session_id)["status"], "cancelled")

    def test_acknowledge_completion_after_full_completion_does_not_cancel_it(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 1))
        controller.reveal_answer()
        controller.submit_self_graded(True)
        session_id = controller.session_id

        controller.acknowledge_completion()

        self.assertEqual(quiz.get_quiz_session(session_id)["status"], "completed")
        self.assertIsNone(controller.completed_session)

    def test_completion_is_idempotent_calling_complete_session_again_is_a_no_op(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 1))
        controller.reveal_answer()
        controller.submit_self_graded(True)
        session_id = controller.session_id
        first_completed_at = quiz.get_quiz_session(session_id)["completed_at"]

        # Re-completing an already-completed session must not raise or
        # change the recorded result (mark_quiz_session_completed's own
        # idempotent no-op contract, exercised through the same call path
        # the controller uses).
        result = quiz.mark_quiz_session_completed(session_id)
        self.assertFalse(result)
        self.assertEqual(quiz.get_quiz_session(session_id)["completed_at"], first_completed_at)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizCardCompletionVisibilityTests(_SyntheticDatabaseTestCase):
    def test_completed_card_scoped_quiz_is_visible_in_review_history(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        quiz_controller = QuizController()
        quiz_controller.start(self._quick_intent(collection_id, 1, None, 1))
        quiz_controller.reveal_answer()
        quiz_controller.submit_self_graded(True)

        review_controller = ReviewController()
        review_controller.open_card(collection_id, 1)
        history = review_controller.history()

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["correct_count"], 1)

    def test_whole_collection_quiz_does_not_fabricate_card_completion(self) -> None:
        collection_id, _ = self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four")], card_size=1
        )
        quiz_controller = QuizController()
        quiz_controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))
        for item in quiz_controller.matching_items():
            quiz_controller.set_matching_selection(item, item["expected_meaning"])
        quiz_controller.submit_matching()

        self.assertIsNone(quiz_controller.completed_session["card_id"])
        self.assertEqual(quiz_controller.completed_session["card_number"], 0)

        review_controller = ReviewController()
        review_controller.open_card(collection_id, 1)
        self.assertEqual(review_controller.history(), [])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizLaunchHandoffTests(_SyntheticDatabaseTestCase):
    def test_today_quiz_action_converts_to_quiz_launch_intent(self) -> None:
        recommendation = {
            "collection_id": 7,
            "collection_name": "Mistake Book",
            "card_number": 3,
            "card_id": 42,
            "preferred_quiz_type": "mixed_mcq",
            "quiz_mode": "card",
            "reason": "never_quizzed",
            "entry_count": 2,
        }
        learning_intent = learning_action_intent_from_recommendation(recommendation)
        quiz_intent = quiz_launch_intent_from_learning_action_intent(learning_intent)

        self.assertIsInstance(quiz_intent, QuizLaunchIntent)
        self.assertEqual(quiz_intent.source, "today_queue")
        self.assertEqual(quiz_intent.collection_id, 7)
        self.assertEqual(quiz_intent.card_number, 3)
        self.assertEqual(quiz_intent.card_id, 42)
        self.assertEqual(quiz_intent.quiz_type, "mixed_mcq")

    def test_today_random_quiz_action_is_whole_collection(self) -> None:
        recommendation = {
            "collection_id": 9,
            "collection_name": "Proficient Pool",
            "card_number": 0,
            "card_id": None,
            "preferred_quiz_type": "mixed_mcq",
            "quiz_mode": "random",
            "reason": "proficient_pool_has_entries",
            "entry_count": 6,
        }
        learning_intent = learning_action_intent_from_recommendation(recommendation)
        quiz_intent = quiz_launch_intent_from_learning_action_intent(learning_intent)

        self.assertEqual(quiz_intent.card_number, 0)
        self.assertIsNone(quiz_intent.card_id)
        self.assertEqual(quiz_intent.item_count, 6)

    def test_organize_action_does_not_convert_to_a_quiz_intent(self) -> None:
        recommendation = {
            "collection_id": None,
            "collection_name": "",
            "card_number": None,
            "card_id": None,
            "preferred_quiz_type": None,
            "quiz_mode": "suggestion",
            "reason": "recent_entries",
            "entry_count": 3,
        }
        learning_intent = learning_action_intent_from_recommendation(recommendation)
        self.assertIsNone(quiz_launch_intent_from_learning_action_intent(learning_intent))


class QuizCoreBoundaryTests(unittest.TestCase):
    """Reusable-core boundary guards (M16.1 contract): Quiz orchestrates
    presentation and session state only; every actual grading/session write
    goes through existing src.quiz/src.template_quiz functions."""

    def test_controller_has_no_raw_sql_and_no_db_import(self) -> None:
        # Unlike ReviewController/TodayController, QuizController never
        # needs a raw sqlite3.Connection -- every src.quiz/src.template_quiz
        # function it calls manages its own connection -- so this is
        # stricter than the "no literal SQL keywords" check those use.
        path = PROJECT_ROOT / "src" / "ui_desktop" / "controllers" / "quiz_controller.py"
        text = path.read_text(encoding="utf-8")
        upper = text.upper()
        for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, upper)
        self.assertNotIn("import sqlite3", text)
        self.assertNotIn("from src import db", text)

    def test_view_has_no_raw_sql_and_no_direct_db_import(self) -> None:
        path = PROJECT_ROOT / "src" / "ui_desktop" / "views" / "quiz_view.py"
        text = path.read_text(encoding="utf-8")
        upper = text.upper()
        for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, upper)
        self.assertNotIn("import sqlite3", text)
        self.assertNotIn("from src import db", text)

    def test_controller_does_not_import_legacy_review_scheduler(self) -> None:
        path = PROJECT_ROOT / "src" / "ui_desktop" / "controllers" / "quiz_controller.py"
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("from src.review import", text)
        self.assertNotIn("src.review.", text)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizViewStructureTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_self_graded_shows_reveal_then_grading_controls(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        controller.start(self._quick_intent(collection_id, 1, None, 1))

        show_buttons = [
            w for w in view.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "quiz-show-answer-button"
        ]
        self.assertEqual(len(show_buttons), 1)

        controller.reveal_answer()

        correct_buttons = [
            w for w in view.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "quiz-grade-correct-button"
        ]
        self.assertEqual(len(correct_buttons), 1)

    def test_completion_state_shows_stats_and_next_actions(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        controller.start(self._quick_intent(collection_id, 1, None, 1))
        controller.reveal_answer()
        controller.submit_self_graded(True)

        title = next(
            w for w in view.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "quiz-completion-title"
        )
        self.assertIn("complete", title.text().lower())
        return_button = next(
            w
            for w in view.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "quiz-completion-return-today-button"
        )
        self.assertTrue(return_button.isEnabled())

    def test_blocked_state_renders_cancel_affordance(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")])
        quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 2)  # foreign active session

        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        controller.start(self._quick_intent(collection_id, 1, None, 2))

        cancel_buttons = [
            w
            for w in view.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "quiz-blocked-cancel-button"
        ]
        self.assertEqual(len(cancel_buttons), 1)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizMatchingStabilityTests(_SyntheticDatabaseTestCase):
    """VR-STUDY-001 corrective pass § 2: a Matching answer selection must
    not reset the task surface/scroll position, and wheel scrolling over a
    closed combo must not silently change its selection."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def _matching_collection(self):
        return self._make_card([("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four")])

    def test_set_matching_selection_emits_the_lightweight_signal_not_state_changed(self) -> None:
        collection_id, _ = self._matching_collection()
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))

        state_changed_calls: list[None] = []
        selection_changed_calls: list[None] = []
        controller.state_changed.connect(lambda: state_changed_calls.append(None))
        controller.matching_selection_changed.connect(lambda: selection_changed_calls.append(None))

        items = controller.matching_items()
        controller.set_matching_selection(items[0], controller.matching_choices()[0])

        self.assertEqual(len(selection_changed_calls), 1)
        self.assertEqual(len(state_changed_calls), 0)

    def test_all_selections_are_stored_before_submit_and_none_are_lost(self) -> None:
        collection_id, _ = self._matching_collection()
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))

        items = controller.matching_items()
        for item in items:
            controller.set_matching_selection(item, controller.matching_choices()[0])

        for item in items:
            self.assertEqual(controller.matching_selection_for(item), controller.matching_choices()[0])
        self.assertTrue(controller.can_submit_matching())

    def test_matching_selection_does_not_rebuild_the_task_surface_or_reset_scroll(self) -> None:
        collection_id, _ = self._matching_collection()
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))

        combos_before = [w for w in view.findChildren(QComboBox) if w.objectName() == "quiz-matching-combo"]
        self.assertEqual(len(combos_before), 4)
        submit_button = next(
            w for w in view.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "quiz-matching-submit-button"
        )
        self.assertFalse(submit_button.isEnabled())

        items = controller.matching_items()
        controller.set_matching_selection(items[0], controller.matching_choices()[0])

        combos_after = [w for w in view.findChildren(QComboBox) if w.objectName() == "quiz-matching-combo"]
        # Same widget instances -- proof the Matching rows were never torn
        # down and rebuilt for a single selection (the actual bug: doing so
        # lost the user's scroll position and any prior selections).
        self.assertEqual([id(c) for c in combos_before], [id(c) for c in combos_after])
        self.assertIs(submit_button, view._matching_submit_button)

        for item in items[1:]:
            controller.set_matching_selection(item, controller.matching_choices()[0])
        self.assertTrue(submit_button.isEnabled())

    def test_matching_combo_ignores_wheel_events_so_the_list_can_scroll_instead(self) -> None:
        from PySide6.QtCore import QPoint, QPointF
        from PySide6.QtCore import Qt as QtCore_Qt
        from PySide6.QtGui import QWheelEvent

        collection_id, _ = self._matching_collection()
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))

        combo = next(w for w in view.findChildren(QComboBox) if w.objectName() == "quiz-matching-combo")
        before_index = combo.currentIndex()

        event = QWheelEvent(
            QPointF(5, 5),
            QPointF(5, 5),
            QPoint(0, 0),
            QPoint(0, 120),
            QtCore_Qt.MouseButton.NoButton,
            QtCore_Qt.KeyboardModifier.NoModifier,
            QtCore_Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        combo.wheelEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertEqual(combo.currentIndex(), before_index)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizMistakeReviewTests(_SyntheticDatabaseTestCase):
    """VR-STUDY-001 corrective pass § 3: Review Mistakes must inspect the
    just-completed Quiz's own wrong answers, stay inside the Quiz surface
    (no navigation to Review, no clearing of ``completed_session``), and
    perform no mutation."""

    def _completed_session_with_one_mistake(self):
        collection_id, entry_ids = self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 2))
        controller.reveal_answer()
        controller.submit_self_graded(True)  # first item: correct
        wrong_item = controller.current_item()
        controller.reveal_answer()
        controller.submit_self_graded(False)  # second item: wrong
        return controller, collection_id, entry_ids, wrong_item

    def test_review_mistakes_shows_this_quizs_wrong_log_without_new_writes(self) -> None:
        controller, _, _, wrong_item = self._completed_session_with_one_mistake()
        session_id = controller.completed_session["id"]
        with db.get_connection() as connection:
            logs_before = connection.execute("SELECT COUNT(*) AS n FROM quiz_item_logs").fetchone()["n"]
            sessions_before = connection.execute("SELECT COUNT(*) AS n FROM quiz_sessions").fetchone()["n"]

        controller.review_mistakes()

        self.assertTrue(controller.reviewing_mistakes)
        self.assertIsNotNone(controller.completed_session)  # context preserved, not cleared
        mistake = controller.current_mistake()
        self.assertIsNotNone(mistake)
        self.assertEqual(mistake["session_id"], session_id)
        self.assertEqual(mistake["entry_id"], wrong_item["entry_id"])
        self.assertEqual(mistake["expected_answer"], wrong_item["expected_answer"])
        self.assertFalse(mistake["is_correct"])
        self.assertEqual(controller.mistake_progress(), (1, 1))

        with db.get_connection() as connection:
            logs_after = connection.execute("SELECT COUNT(*) AS n FROM quiz_item_logs").fetchone()["n"]
            sessions_after = connection.execute("SELECT COUNT(*) AS n FROM quiz_sessions").fetchone()["n"]
        self.assertEqual(logs_before, logs_after)
        self.assertEqual(sessions_before, sessions_after)

    def test_mistake_navigation_respects_bounds_and_does_not_mutate(self) -> None:
        collection_id, _ = self._make_card([("un", "one"), ("deux", "two"), ("trois", "three")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 3))
        for _ in range(3):
            controller.reveal_answer()
            controller.submit_self_graded(False)  # all three wrong

        controller.review_mistakes()
        self.assertEqual(controller.mistake_progress(), (1, 3))
        self.assertFalse(controller.can_go_previous_mistake())
        self.assertTrue(controller.can_go_next_mistake())

        controller.go_next_mistake()
        self.assertEqual(controller.mistake_progress(), (2, 3))
        controller.go_next_mistake()
        self.assertEqual(controller.mistake_progress(), (3, 3))
        self.assertFalse(controller.can_go_next_mistake())

        # Past-the-end navigation is a no-op, not an out-of-range crash.
        controller.go_next_mistake()
        self.assertEqual(controller.mistake_progress(), (3, 3))

        controller.go_previous_mistake()
        self.assertEqual(controller.mistake_progress(), (2, 3))

    def test_exit_mistake_review_returns_to_summary_without_clearing_context(self) -> None:
        controller, _, _, _ = self._completed_session_with_one_mistake()
        controller.review_mistakes()

        controller.exit_mistake_review()

        self.assertFalse(controller.reviewing_mistakes)
        self.assertIsNotNone(controller.completed_session)

    def test_review_mistakes_is_a_no_op_with_zero_mistakes(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        controller.start(self._quick_intent(collection_id, 1, None, 1))
        controller.reveal_answer()
        controller.submit_self_graded(True)  # no mistakes

        controller.review_mistakes()

        self.assertFalse(controller.reviewing_mistakes)
        self.assertEqual(controller.mistakes, [])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizMistakeReviewViewTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_review_mistakes_button_omitted_when_there_are_zero_mistakes(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        controller.start(self._quick_intent(collection_id, 1, None, 1))
        controller.reveal_answer()
        controller.submit_self_graded(True)

        buttons = [
            w
            for w in view.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "quiz-completion-review-mistakes-button"
        ]
        self.assertEqual(len(buttons), 0)

    def test_review_mistakes_button_present_and_enters_read_only_state(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat"), ("chien", "dog")])
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        controller.start(self._quick_intent(collection_id, 1, None, 2))
        controller.reveal_answer()
        controller.submit_self_graded(True)
        controller.reveal_answer()
        controller.submit_self_graded(False)

        review_button = next(
            w
            for w in view.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "quiz-completion-review-mistakes-button"
        )
        review_button.click()

        self.assertTrue(controller.reviewing_mistakes)
        # Still inside the Quiz workspace/surface -- no navigation signal.
        position_labels = [
            w
            for w in view.findChildren(QWidget)
            if getattr(w, "objectName", lambda: "")() == "quiz-mistake-position-label"
        ]
        self.assertEqual(len(position_labels), 1)
        self.assertEqual(position_labels[0].text(), "Mistake 1/1")

        back_button = next(
            w for w in view.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "quiz-mistake-back-button"
        )
        back_button.click()

        self.assertFalse(controller.reviewing_mistakes)
        title = next(
            w for w in view.findChildren(QWidget) if getattr(w, "objectName", lambda: "")() == "quiz-completion-title"
        )
        self.assertIn("complete", title.text().lower())


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class MainWindowStudyModeQuizIntegrationTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def _add_mcq_ready_card(self, collection_name: str = "Rail Quiz Collection") -> int:
        # Quick Quiz always uses the deterministic mixed_mcq default, which
        # needs at least 1 target + 3 distractors -- 4 entries in one Card.
        entry_ids = [
            add_entry("French", "English", "word", term, meaning)
            for term, meaning in (("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four"))
        ]
        collection_id = create_collection(collection_name, card_size=4)
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id

    def test_review_quick_quiz_enters_quiz_workspace_with_management_chrome_hidden(self) -> None:
        self._add_mcq_ready_card()

        self.window._navigation_rail._buttons["study"].click()  # enters Review
        self.window.review_view.quiz_launch_requested.emit(
            self.window.review_controller.build_quick_quiz_intent()
        )

        self.assertIs(self.window.current_workspace(), Workspace.QUIZ)
        self.assertIs(self.window.app_state.mode, ShellMode.STUDY)
        self.assertIs(self.window._workspace_stack.currentWidget(), self.window.quiz_view)
        self.assertFalse(self.window._navigation_rail.isVisible())
        self.assertFalse(self.window._study_toolbar.isVisible())
        self.assertIsNotNone(self.window.quiz_controller.session_id)

    def _enter_review_and_start_self_graded_quiz(self) -> None:
        entry_id = add_entry("French", "English", "word", "chat", "cat")
        collection_id = create_collection("Rail Quiz Collection", card_size=1)
        add_entries_to_collection([entry_id], collection_id)
        self.window._navigation_rail._buttons["study"].click()
        card = self.window.review_controller.current_card()
        intent = QuizLaunchIntent(
            source="test",
            collection_id=card["collection_id"],
            collection_name=card["collection_name"],
            card_number=card["card_number"],
            card_id=card["card_id"],
            quiz_type="term_to_meaning",
            item_count=1,
            reason="test",
        )
        self.window.review_view.quiz_launch_requested.emit(intent)

    def test_quiz_completion_return_to_today_exits_study_mode(self) -> None:
        self._enter_review_and_start_self_graded_quiz()
        self.window.quiz_controller.reveal_answer()
        self.window.quiz_controller.submit_self_graded(True)

        self.window.quiz_view.return_to_today_requested.emit()

        self.assertIs(self.window.current_workspace(), Workspace.TODAY)
        self.assertIs(self.window.app_state.mode, ShellMode.MANAGEMENT)
        self.assertTrue(self.window._navigation_rail.isVisible())

    def test_quiz_completion_next_card_returns_to_review_in_study_mode(self) -> None:
        self._enter_review_and_start_self_graded_quiz()
        self.window.quiz_controller.reveal_answer()
        self.window.quiz_controller.submit_self_graded(True)

        self.window.quiz_view.next_card_requested.emit()

        self.assertIs(self.window.current_workspace(), Workspace.REVIEW)
        self.assertIs(self.window.app_state.mode, ShellMode.STUDY)
        self.assertIsNone(self.window.quiz_controller.completed_session)

    def test_exit_confirmation_cancel_ends_active_quiz_and_returns_to_management(self) -> None:
        self._add_mcq_ready_card()
        self.window._navigation_rail._buttons["study"].click()
        self.window.review_view.quiz_launch_requested.emit(
            self.window.review_controller.build_quick_quiz_intent()
        )
        session_id = self.window.quiz_controller.session_id
        self.assertIsNotNone(session_id)

        # Exercise the controller-level cancel path directly (the dialog's
        # own click routing is a thin, already-covered Qt mechanism);
        # QuizView.exit_requested is what MainWindow listens to either way.
        self.window.quiz_controller.exit_active()
        self.window.quiz_view.exit_requested.emit()

        self.assertEqual(quiz.get_quiz_session(session_id)["status"], "cancelled")
        self.assertIs(self.window.app_state.mode, ShellMode.MANAGEMENT)

    def test_today_quiz_launch_enters_quiz_workspace(self) -> None:
        collection_id = self._add_mcq_ready_card("Today Quiz Collection")
        self.window.today_controller.refresh()

        self.window._navigation_rail._buttons["today"].click()
        self.window.today_view.quiz_launch_requested.emit(
            QuizLaunchIntent(
                source="today_queue",
                collection_id=collection_id,
                collection_name="Today Quiz Collection",
                card_number=1,
                card_id=None,
                quiz_type="mixed_mcq",
                item_count=4,
                reason="test",
            )
        )

        self.assertIs(self.window.current_workspace(), Workspace.QUIZ)
        self.assertIs(self.window.app_state.mode, ShellMode.STUDY)
        self.assertIsNotNone(self.window.quiz_controller.session_id)


if __name__ == "__main__":
    unittest.main()

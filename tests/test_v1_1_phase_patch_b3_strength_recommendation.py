from __future__ import annotations

from datetime import date, timedelta
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton

from src import db
from src.collections import (
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    is_entry_in_system_collection,
)
from src.entries import add_entry
from src.insights import get_completed_quiz_strength_candidates
from src.quiz import complete_quiz_session, create_quiz_session, get_quiz_session, record_quiz_answer
from src.ui_desktop.controllers.quiz_controller import QuizController
from src.ui_desktop.state.handoff import QuizLaunchIntent
from src.ui_desktop.views.quiz_view import QuizView


AS_OF = date(2026, 8, 27)


class PatchB3StrengthRecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "patch-b3.sqlite3"
        db.init_db()
        self.collection_id = create_collection("Synthetic Patch B3", "", card_size=8)

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _entry(self, term: str) -> int:
        entry_id = add_entry("English", "English", "word", term, f"Meaning for {term}")
        add_entries_to_collection([entry_id], self.collection_id)
        return entry_id

    def _answered_session(self, entry_id: int, attempt_count: int, *, complete: bool = True) -> int:
        session_id = create_quiz_session(
            self.collection_id,
            1,
            "term_to_meaning",
            attempt_count,
        )
        for index in range(attempt_count):
            record_quiz_answer(
                session_id,
                entry_id,
                f"prompt-{session_id}-{index}",
                "answer",
                "answer",
                True,
            )
        if complete:
            complete_quiz_session(session_id)
        return session_id

    def _seed_strength_history(self, entry_id: int) -> None:
        session_ids = [self._answered_session(entry_id, 2) for _ in range(4)]
        with db.get_connection() as connection:
            for index, session_id in enumerate(session_ids):
                answered_day = AS_OF - timedelta(days=1 if index < 2 else 0)
                connection.execute(
                    "UPDATE quiz_item_logs SET answered_at = ? WHERE session_id = ?",
                    (f"{answered_day.isoformat()}T12:00:00+00:00", session_id),
                )

    def test_candidates_require_a_completed_quiz_session(self) -> None:
        entry_id = self._entry("ready")
        self._seed_strength_history(entry_id)
        current_session_id = self._answered_session(entry_id, 1, complete=False)

        with db.get_connection() as connection:
            self.assertEqual(
                get_completed_quiz_strength_candidates(
                    connection,
                    current_session_id,
                    as_of_date=AS_OF,
                ),
                [],
            )

        complete_quiz_session(current_session_id)

        with db.get_connection() as connection:
            candidates = get_completed_quiz_strength_candidates(
                connection,
                current_session_id,
                as_of_date=AS_OF,
            )
        self.assertEqual([candidate["entry_id"] for candidate in candidates], [entry_id])

    def test_candidates_are_limited_to_session_strengths_not_already_proficient(self) -> None:
        ready = self._entry("ready")
        strength_outside_session = self._entry("outside")
        already_proficient = self._entry("already-proficient")
        non_strength = self._entry("not-strength")
        for entry_id in (ready, strength_outside_session, already_proficient):
            self._seed_strength_history(entry_id)
        add_entries_to_system_collection([already_proficient], "proficient_pool")

        session_id = create_quiz_session(self.collection_id, 1, "term_to_meaning", 3)
        for entry_id in (ready, already_proficient, non_strength):
            record_quiz_answer(
                session_id,
                entry_id,
                f"session-prompt-{entry_id}",
                "answer",
                "answer",
                True,
            )
        complete_quiz_session(session_id)

        with db.get_connection() as connection:
            candidates = get_completed_quiz_strength_candidates(
                connection,
                session_id,
                as_of_date=AS_OF,
            )

        self.assertEqual([candidate["entry_id"] for candidate in candidates], [ready])
        self.assertEqual(candidates[0]["term"], "ready")
        self.assertEqual(candidates[0]["primary_finding"], "strength")

    def test_completion_confirmation_is_explicit_idempotent_and_truth_preserving(self) -> None:
        entry_ids = [self._entry("ready-one"), self._entry("ready-two")]
        for entry_id in entry_ids:
            self._seed_strength_history(entry_id)
        controller = QuizController(today_provider=lambda: AS_OF)
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        intent = QuizLaunchIntent(
            source="test",
            collection_id=self.collection_id,
            collection_name="Synthetic Patch B3",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=2,
            reason="Patch B3 test",
        )
        self.assertTrue(controller.start(intent))
        while controller.completed_session is None:
            controller.reveal_answer()
            self.assertTrue(controller.submit_self_graded(True))
        session_before = get_quiz_session(controller.session_id)
        schedule_before = controller.completion_schedule(today=AS_OF.isoformat())

        candidates = controller.completion_proficient_candidates()
        self.assertEqual(
            {candidate["entry_id"] for candidate in candidates},
            set(entry_ids),
        )
        checkbox = view.findChild(QCheckBox, f"quiz-completion-proficient-entry-{entry_ids[0]}")
        add_button = view.findChild(QPushButton, "quiz-completion-proficient-add-button")
        self.assertIsNotNone(checkbox)
        self.assertIsNotNone(add_button)
        self.assertTrue(checkbox.isChecked())
        self.assertTrue(all(not is_entry_in_system_collection(entry_id, "proficient_pool") for entry_id in entry_ids))

        checkbox.setChecked(False)
        self.assertTrue(all(not is_entry_in_system_collection(entry_id, "proficient_pool") for entry_id in entry_ids))
        self.assertTrue(add_button.isEnabled())
        checkbox.setChecked(True)

        add_button.click()
        self.assertTrue(all(is_entry_in_system_collection(entry_id, "proficient_pool") for entry_id in entry_ids))
        self.assertEqual(controller.add_selected_completion_entries_to_proficient_pool(), [])
        self.assertEqual(get_quiz_session(controller.session_id), session_before)
        self.assertEqual(controller.completion_schedule(today=AS_OF.isoformat()), schedule_before)
        status_labels = [label.text() for label in view.findChildren(QLabel)]
        self.assertTrue(
            any("ready-one" in text and "ready-two" in text and "Added" in text for text in status_labels)
        )

    def test_completion_omits_recommendation_area_when_there_are_no_candidates(self) -> None:
        self._entry("not-ready")
        controller = QuizController(today_provider=lambda: AS_OF)
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        intent = QuizLaunchIntent(
            source="test",
            collection_id=self.collection_id,
            collection_name="Synthetic Patch B3",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=1,
            reason="Patch B3 no-candidate test",
        )
        self.assertTrue(controller.start(intent))
        controller.reveal_answer()
        self.assertTrue(controller.submit_self_graded(True))

        self.assertEqual(controller.completion_proficient_candidates(), [])
        self.assertIsNone(view.findChild(QLabel, "quiz-completion-proficient-heading"))
        self.assertIsNone(view.findChild(QPushButton, "quiz-completion-proficient-add-button"))


if __name__ == "__main__":
    unittest.main()

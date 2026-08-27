from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton

from src import db
from src.collections import (
    CrossCardMoveConfirmationRequired,
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    get_or_create_system_collection,
    get_system_collection_by_type_or_name,
    is_entry_in_system_collection,
    remove_entries_from_system_collection,
)
from src.entries import add_entry
from src.quiz import (
    complete_quiz_session,
    create_quiz_session,
    get_failed_proficient_pool_entries_for_session,
    get_quiz_session,
    record_quiz_answer,
)
from src.ui_desktop.controllers.collections_controller import CollectionsController
from src.ui_desktop.controllers.quiz_controller import QuizController
from src.ui_desktop.state.handoff import QuizLaunchIntent
from src.ui_desktop.views.collections_view import CollectionsView
from src.ui_desktop.views.quiz_view import QuizView


class PatchB4SystemPoolRandomQuizTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "patch-b4.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _entries(self, count: int) -> list[int]:
        return [
            add_entry("English", "English", "word", f"term-{index}", f"meaning-{index}")
            for index in range(count)
        ]

    def _selected_pool(self, system_type: str, count: int) -> tuple[CollectionsController, CollectionsView, dict]:
        get_or_create_system_collection(system_type, system_type.replace("_", " ").title())
        entry_ids = self._entries(count)
        if entry_ids:
            add_entries_to_system_collection(entry_ids, system_type)
        pool = get_system_collection_by_type_or_name(system_type)
        self.assertIsNotNone(pool)
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)
        controller.refresh()
        controller.select_collection(int(pool["id"]), is_system=True)
        return controller, view, pool

    def test_only_starred_and_proficient_pool_details_offer_random_quiz(self) -> None:
        for system_type in ("starred", "proficient_pool"):
            with self.subTest(system_type=system_type):
                _controller, view, _pool = self._selected_pool(system_type, 3)
                button = view.findChild(QPushButton, "collections-system-pool-random-quiz-button")
                self.assertIsNotNone(button)
                self.assertTrue(button.isEnabled())

        _controller, view, _pool = self._selected_pool("mistake_book", 3)
        self.assertIsNone(view.findChild(QPushButton, "collections-system-pool-random-quiz-button"))

        normal_entry_id = self._entries(1)[0]
        normal_collection_id = create_collection("Normal Collection", card_size=1)
        add_entries_to_collection([normal_entry_id], normal_collection_id)
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)
        controller.refresh()
        controller.select_collection(normal_collection_id, is_system=False)
        self.assertIsNone(view.findChild(QPushButton, "collections-system-pool-random-quiz-button"))

    def test_pool_random_quiz_intent_is_whole_pool_and_count_is_bounded(self) -> None:
        controller, _view, pool = self._selected_pool("starred", 3)

        self.assertEqual(controller.random_quiz_item_count_range(), (1, 3))
        intent = controller.build_system_pool_random_quiz_intent("term_to_meaning", 2)

        self.assertIsInstance(intent, QuizLaunchIntent)
        self.assertEqual(intent.collection_id, int(pool["id"]))
        self.assertEqual(intent.card_number, 0)
        self.assertIsNone(intent.card_id)
        self.assertEqual(intent.item_count, 2)
        with self.assertRaises(ValueError):
            controller.build_system_pool_random_quiz_intent("term_to_meaning", 4)

    def test_setup_omits_quiz_families_when_pool_quantity_is_insufficient(self) -> None:
        controller, _view, _pool = self._selected_pool("starred", 1)
        self.assertEqual(
            controller.random_quiz_type_options(),
            ["term_to_meaning", "meaning_to_term"],
        )
        self.assertEqual(controller.random_quiz_item_count_range("matching"), (0, 0))

        add_entries_to_system_collection(self._entries(1), "starred")
        controller.refresh()
        self.assertIn("matching", controller.random_quiz_type_options())
        self.assertNotIn("mixed_mcq", controller.random_quiz_type_options())

    def test_empty_pool_disables_random_quiz_and_has_no_legal_count(self) -> None:
        controller, view, _pool = self._selected_pool("proficient_pool", 0)

        button = view.findChild(QPushButton, "collections-system-pool-random-quiz-button")
        self.assertIsNotNone(button)
        self.assertFalse(button.isEnabled())
        self.assertEqual(controller.random_quiz_item_count_range(), (0, 0))

    def test_failed_audit_query_requires_completed_proficient_pool_session(self) -> None:
        entry_ids = self._entries(2)
        add_entries_to_system_collection(entry_ids, "proficient_pool")
        pool = get_system_collection_by_type_or_name("proficient_pool")
        session_id = create_quiz_session(int(pool["id"]), 0, "term_to_meaning", 1)
        record_quiz_answer(session_id, entry_ids[0], "term-0", "meaning-0", "wrong", False)

        self.assertEqual(get_failed_proficient_pool_entries_for_session(session_id), [])

        complete_quiz_session(session_id)
        candidates = get_failed_proficient_pool_entries_for_session(session_id)
        self.assertEqual([row["entry_id"] for row in candidates], [entry_ids[0]])
        self.assertTrue(candidates[0]["currently_in_proficient_pool"])

        card_scoped_session = create_quiz_session(int(pool["id"]), 1, "term_to_meaning", 1)
        record_quiz_answer(
            card_scoped_session,
            entry_ids[0],
            "term-0-card",
            "meaning-0",
            "wrong",
            False,
        )
        complete_quiz_session(card_scoped_session)
        self.assertEqual(get_failed_proficient_pool_entries_for_session(card_scoped_session), [])

    def test_starred_random_quiz_wrong_answer_keeps_star_and_adds_mistake_evidence(self) -> None:
        entry_id = self._entries(1)[0]
        add_entries_to_system_collection([entry_id], "starred")
        pool = get_system_collection_by_type_or_name("starred")
        controller = QuizController()
        intent = QuizLaunchIntent(
            source="collections_starred_random_quiz",
            collection_id=int(pool["id"]),
            collection_name="Starred",
            card_number=0,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=1,
            reason="Patch B4 Starred practice",
        )

        self.assertTrue(controller.start(intent))
        controller.reveal_answer()
        self.assertTrue(controller.submit_self_graded(False))

        self.assertTrue(is_entry_in_system_collection(entry_id, "starred"))
        self.assertTrue(is_entry_in_system_collection(entry_id, "mistake_book"))
        self.assertEqual(controller.completion_proficient_audit_candidates(), [])
        self.assertEqual(controller.completed_session["card_number"], 0)
        self.assertIsNone(controller.completed_session["card_id"])

    def test_proficient_audit_selection_and_keep_do_not_mutate_until_confirmed(self) -> None:
        entry_ids = self._entries(2)
        add_entries_to_system_collection(entry_ids, "proficient_pool")
        pool = get_system_collection_by_type_or_name("proficient_pool")
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        intent = QuizLaunchIntent(
            source="collections_proficient_pool_random_quiz",
            collection_id=int(pool["id"]),
            collection_name="Proficient Pool",
            card_number=0,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=2,
            reason="Patch B4 audit",
        )
        self.assertTrue(controller.start(intent))
        wrong_entry_id = int(controller.current_item()["entry_id"])
        controller.reveal_answer()
        controller.submit_self_graded(False)
        controller.reveal_answer()
        controller.submit_self_graded(True)

        candidates = controller.completion_proficient_audit_candidates()
        self.assertEqual([row["entry_id"] for row in candidates], [wrong_entry_id])
        heading = view.findChild(QLabel, "quiz-completion-proficient-audit-heading")
        checkbox = view.findChild(QCheckBox, f"quiz-completion-proficient-audit-entry-{wrong_entry_id}")
        keep_button = view.findChild(QPushButton, "quiz-completion-proficient-audit-keep-button")
        remove_button = view.findChild(QPushButton, "quiz-completion-proficient-audit-remove-button")
        self.assertIsNotNone(heading)
        self.assertIsNotNone(checkbox)
        self.assertFalse(checkbox.isChecked())
        self.assertFalse(remove_button.isEnabled())

        checkbox.setChecked(True)
        self.assertTrue(is_entry_in_system_collection(wrong_entry_id, "proficient_pool"))
        keep_button.click()
        self.assertTrue(is_entry_in_system_collection(wrong_entry_id, "proficient_pool"))
        checkbox = view.findChild(QCheckBox, f"quiz-completion-proficient-audit-entry-{wrong_entry_id}")
        remove_button = view.findChild(QPushButton, "quiz-completion-proficient-audit-remove-button")
        self.assertFalse(checkbox.isChecked())

        checkbox.setChecked(True)
        remove_button.click()
        self.assertFalse(is_entry_in_system_collection(wrong_entry_id, "proficient_pool"))
        self.assertTrue(is_entry_in_system_collection(wrong_entry_id, "mistake_book"))
        self.assertEqual(controller.remove_selected_completion_proficient_audit_entries(), [])

    def test_proficient_audit_removal_preserves_cross_card_confirmation(self) -> None:
        entry_ids = self._entries(9)
        add_entries_to_system_collection(entry_ids, "proficient_pool")
        pool = get_system_collection_by_type_or_name("proficient_pool")
        controller = QuizController()
        self.assertTrue(
            controller.start(
                QuizLaunchIntent(
                    source="collections_proficient_pool_random_quiz",
                    collection_id=int(pool["id"]),
                    collection_name="Proficient Pool",
                    card_number=0,
                    card_id=None,
                    quiz_type="term_to_meaning",
                    item_count=9,
                    reason="Patch B4 cross-card audit",
                )
            )
        )
        while controller.completed_session is None:
            current_entry_id = int(controller.current_item()["entry_id"])
            controller.reveal_answer()
            controller.submit_self_graded(current_entry_id != entry_ids[0])

        controller.set_completion_proficient_audit_candidate_selected(entry_ids[0], True)
        with self.assertRaises(CrossCardMoveConfirmationRequired):
            controller.remove_selected_completion_proficient_audit_entries()
        self.assertTrue(is_entry_in_system_collection(entry_ids[0], "proficient_pool"))

        self.assertEqual(
            controller.remove_selected_completion_proficient_audit_entries(confirm_cross_card=True),
            [entry_ids[0]],
        )
        self.assertFalse(is_entry_in_system_collection(entry_ids[0], "proficient_pool"))
        self.assertEqual(get_quiz_session(controller.session_id)["status"], "completed")

    def test_failed_query_ignores_historical_wrong_from_another_session(self) -> None:
        entry_ids = self._entries(2)
        add_entries_to_system_collection(entry_ids, "proficient_pool")
        pool = get_system_collection_by_type_or_name("proficient_pool")

        historical_session = create_quiz_session(int(pool["id"]), 0, "term_to_meaning", 1)
        record_quiz_answer(
            historical_session,
            entry_ids[1],
            "term-1",
            "meaning-1",
            "wrong",
            False,
        )
        complete_quiz_session(historical_session)

        current_session = create_quiz_session(int(pool["id"]), 0, "term_to_meaning", 1)
        record_quiz_answer(current_session, entry_ids[0], "term-0", "meaning-0", "wrong", False)
        complete_quiz_session(current_session)

        self.assertEqual(
            [row["entry_id"] for row in get_failed_proficient_pool_entries_for_session(current_session)],
            [entry_ids[0]],
        )

    def test_audit_excludes_entry_removed_before_completion(self) -> None:
        entry_id = self._entries(1)[0]
        add_entries_to_system_collection([entry_id], "proficient_pool")
        pool = get_system_collection_by_type_or_name("proficient_pool")

        controller = QuizController()
        self.assertTrue(
            controller.start(
                QuizLaunchIntent(
                    source="collections_proficient_pool_random_quiz",
                    collection_id=int(pool["id"]),
                    collection_name="Proficient Pool",
                    card_number=0,
                    card_id=None,
                    quiz_type="term_to_meaning",
                    item_count=1,
                    reason="Patch B4 current-session audit",
                )
            )
        )
        current_entry_id = int(controller.current_item()["entry_id"])
        remove_entries_from_system_collection([current_entry_id], "proficient_pool")
        controller.reveal_answer()
        controller.submit_self_graded(False)

        self.assertEqual(controller.completion_proficient_audit_candidates(), [])


if __name__ == "__main__":
    unittest.main()

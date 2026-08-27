from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from src import db, learning_workflow, quiz
from src.collections import (
    CrossCardMoveConfirmationRequired,
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    is_entry_in_system_collection,
)
from src.entries import add_entry, create_entry_with_template
from src.entry_templates import ensure_french_verb_present_template
from src.ui_desktop.controllers.review_controller import ReviewController
from src.ui_desktop.controllers.quiz_controller import QuizController
from src.ui_desktop.controllers.collections_controller import CollectionsController
from src.ui_desktop.state.handoff import QuizLaunchIntent
from src.ui_desktop.views.review_view import ReviewView
from src.ui_desktop.views.quiz_view import QuizView
from src.ui_desktop.views.collections_view import CollectionsView


def _qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


class PhaseBTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "phase-b.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _collection_with_entries(self, count: int = 1, *, card_size: int = 8) -> tuple[int, list[int]]:
        collection_id = create_collection("Synthetic Phase B", "", card_size=card_size)
        entry_ids = [
            add_entry("English", "English", "word", f"term-{index}", f"meaning-{index}")
            for index in range(1, count + 1)
        ]
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids

    def _template_collection(self) -> tuple[int, list[int], int]:
        template_id = ensure_french_verb_present_template()
        entry_ids = []
        for index, (infinitive, meaning, conjugation) in enumerate(
            (
                ("parler", "to speak", "parle"),
                ("manger", "to eat", "mange"),
                ("finir", "to finish", "finis"),
                ("vendre", "to sell", "vends"),
            ),
            start=1,
        ):
            entry_ids.append(
                create_entry_with_template(
                    entry_data={
                        "template_id": template_id,
                        "language": "French",
                        "explanation_language": "English",
                        "entry_type": "verb",
                    },
                    template_values={
                        "infinitive": infinitive,
                        "meaning": meaning,
                        "je": conjugation,
                        "tu": f"{conjugation}-{index}-tu",
                        "il_elle_on": f"{conjugation}-{index}-il",
                        "nous": f"{conjugation}-{index}-nous",
                        "vous": f"{conjugation}-{index}-vous",
                        "ils_elles": f"{conjugation}-{index}-ils",
                    },
                )
            )
        collection_id = create_collection("Synthetic Template Phase B", "", card_size=4)
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids, template_id


class StudyStarMutationTests(PhaseBTestCase):
    def test_current_entry_can_be_starred_without_changing_study_position(self) -> None:
        collection_id, entry_ids = self._collection_with_entries()
        controller = ReviewController()
        self.assertTrue(controller.open_card(collection_id, 1))
        card_before = controller.current_card()
        progress_before = controller.entry_progress()

        starred = controller.toggle_current_entry_star()

        self.assertTrue(starred)
        self.assertTrue(is_entry_in_system_collection(entry_ids[0], "starred"))
        self.assertEqual(controller.current_card(), card_before)
        self.assertEqual(controller.current_entry()["id"], entry_ids[0])
        self.assertEqual(controller.entry_progress(), progress_before)

    def test_unstar_preserves_confirmation_gate_and_state_until_confirmed(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(9)
        add_entries_to_system_collection(entry_ids, "starred")
        controller = ReviewController()
        self.assertTrue(controller.open_card(collection_id, 1))
        entry_before = controller.current_entry()
        progress_before = controller.entry_progress()

        with self.assertRaises(CrossCardMoveConfirmationRequired):
            controller.toggle_current_entry_star()

        self.assertTrue(controller.is_entry_starred(entry_ids[0]))
        self.assertTrue(is_entry_in_system_collection(entry_ids[0], "starred"))
        self.assertEqual(controller.current_entry(), entry_before)
        self.assertEqual(controller.entry_progress(), progress_before)

        self.assertFalse(controller.toggle_current_entry_star(confirm_cross_card=True))
        self.assertFalse(is_entry_in_system_collection(entry_ids[0], "starred"))


class StudyStarActionTests(PhaseBTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_current_entry_star_action_mutates_membership(self) -> None:
        collection_id, entry_ids = self._collection_with_entries()
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        self.assertTrue(controller.open_card(collection_id, 1))

        button = view.findChild(QPushButton, "review-current-entry-star-button")
        self.assertIsNotNone(button)
        button.click()

        self.assertTrue(is_entry_in_system_collection(entry_ids[0], "starred"))


class QuizStarMutationTests(PhaseBTestCase):
    def test_current_item_can_be_starred_without_changing_quiz_state(self) -> None:
        collection_id, _entry_ids = self._collection_with_entries(2)
        controller = QuizController()
        intent = QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="Synthetic Phase B",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=2,
            reason="test",
        )
        self.assertTrue(controller.start(intent))
        controller.set_answer_draft("draft answer")
        item = controller.current_item()
        session_id = controller.session_id
        items_before = list(controller.items)

        starred = controller.toggle_entry_star(item["entry_id"])

        self.assertTrue(starred)
        self.assertTrue(is_entry_in_system_collection(item["entry_id"], "starred"))
        self.assertEqual(controller.session_id, session_id)
        self.assertEqual(controller.current_index, 0)
        self.assertEqual(controller.answer_draft, "draft answer")
        self.assertFalse(controller.show_answer)
        self.assertIsNone(controller.feedback)
        self.assertEqual(controller.matching_selection, {})
        self.assertEqual(controller.items, items_before)

    def test_matching_star_does_not_reset_existing_selections_or_session(self) -> None:
        collection_id, _entry_ids = self._collection_with_entries(4)
        controller = QuizController()
        intent = QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="Synthetic Phase B",
            card_number=0,
            card_id=None,
            quiz_type="matching",
            item_count=4,
            reason="test",
        )
        self.assertTrue(controller.start(intent))
        first, second = controller.matching_items()[:2]
        controller.set_matching_selection(first, controller.matching_choices()[0])
        selection_before = dict(controller.matching_selection)
        session_before = controller.session_id

        controller.toggle_entry_star(second["entry_id"])

        self.assertEqual(controller.session_id, session_before)
        self.assertEqual(controller.matching_selection, selection_before)
        self.assertTrue(is_entry_in_system_collection(second["entry_id"], "starred"))

    def test_quiz_unstar_preserves_cross_card_confirmation_gate(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(9)
        add_entries_to_system_collection(entry_ids, "starred")
        controller = QuizController()
        intent = QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="Synthetic Phase B",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=9,
            reason="test",
        )
        self.assertTrue(controller.start(intent))
        entry_id = controller.current_item()["entry_id"]
        session_before = controller.session_id

        with self.assertRaises(CrossCardMoveConfirmationRequired):
            controller.toggle_entry_star(entry_id)

        self.assertTrue(controller.is_entry_starred(entry_id))
        self.assertEqual(controller.session_id, session_before)
        self.assertFalse(controller.toggle_entry_star(entry_id, confirm_cross_card=True))
        self.assertFalse(is_entry_in_system_collection(entry_id, "starred"))


class QuizStarActionTests(PhaseBTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    @staticmethod
    def _template_intent(collection_id: int, template_id: int, quiz_type: str) -> QuizLaunchIntent:
        return QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="Synthetic Template Phase B",
            card_number=1,
            card_id=None,
            quiz_type=quiz_type,
            item_count=4,
            reason="test",
            template_id=template_id,
            template_type="french_verb_present",
            template_rule_ids=("infinitive_to_je",),
        )

    def test_self_graded_current_item_star_action_preserves_draft(self) -> None:
        collection_id, _entry_ids = self._collection_with_entries(2)
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        intent = QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="Synthetic Phase B",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=2,
            reason="test",
        )
        self.assertTrue(controller.start(intent))
        controller.set_answer_draft("kept draft")
        entry_id = controller.current_item()["entry_id"]

        button = view.findChild(QPushButton, "quiz-current-entry-star-button")
        self.assertIsNotNone(button)
        button.click()

        self.assertTrue(is_entry_in_system_collection(entry_id, "starred"))
        self.assertEqual(controller.answer_draft, "kept draft")
        self.assertEqual(controller.current_index, 0)

    def test_mcq_current_item_star_action_does_not_grade_or_advance(self) -> None:
        collection_id, _entry_ids = self._collection_with_entries(5)
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        intent = QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="Synthetic Phase B",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning_mcq",
            item_count=5,
            reason="test",
        )
        self.assertTrue(controller.start(intent))
        session_before = controller.session_id
        entry_id = controller.current_item()["entry_id"]

        view.findChild(QPushButton, "quiz-current-entry-star-button").click()

        self.assertTrue(is_entry_in_system_collection(entry_id, "starred"))
        self.assertEqual(controller.session_id, session_before)
        self.assertEqual(controller.current_index, 0)
        self.assertIsNone(controller.feedback)

    def test_matching_exposes_one_star_action_per_item_without_resetting_selection(self) -> None:
        collection_id, _entry_ids = self._collection_with_entries(4)
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        intent = QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="Synthetic Phase B",
            card_number=0,
            card_id=None,
            quiz_type="matching",
            item_count=4,
            reason="test",
        )
        self.assertTrue(controller.start(intent))
        items = controller.matching_items()
        controller.set_matching_selection(items[0], controller.matching_choices()[0])
        selection_before = dict(controller.matching_selection)
        buttons = [
            button
            for button in view.findChildren(QPushButton)
            if button.objectName().startswith("quiz-matching-star-button-")
        ]

        self.assertEqual(len(buttons), len(items))
        target = items[1]
        button = next(button for button in buttons if button.property("entryId") == target["entry_id"])
        button.click()

        self.assertTrue(is_entry_in_system_collection(target["entry_id"], "starred"))
        self.assertEqual(controller.matching_selection, selection_before)

    def test_template_self_graded_star_action_preserves_draft(self) -> None:
        collection_id, _entry_ids, template_id = self._template_collection()
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        self.assertTrue(controller.start(self._template_intent(collection_id, template_id, "template_field_self_graded")))
        controller.set_answer_draft("template draft")
        entry_id = controller.current_item()["entry_id"]

        view.findChild(QPushButton, "quiz-current-entry-star-button").click()

        self.assertTrue(is_entry_in_system_collection(entry_id, "starred"))
        self.assertEqual(controller.answer_draft, "template draft")
        self.assertEqual(controller.current_index, 0)

    def test_template_mcq_star_action_does_not_grade_or_advance(self) -> None:
        collection_id, _entry_ids, template_id = self._template_collection()
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        self.assertTrue(controller.start(self._template_intent(collection_id, template_id, "template_field_mcq")))
        entry_id = controller.current_item()["entry_id"]

        view.findChild(QPushButton, "quiz-current-entry-star-button").click()

        self.assertTrue(is_entry_in_system_collection(entry_id, "starred"))
        self.assertEqual(controller.current_index, 0)
        self.assertIsNone(controller.feedback)

    def test_template_matching_star_action_preserves_matching_selection(self) -> None:
        collection_id, _entry_ids, template_id = self._template_collection()
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        self.assertTrue(controller.start(self._template_intent(collection_id, template_id, "template_field_matching")))
        items = controller.matching_items()
        controller.set_matching_selection(items[0], controller.matching_choices()[0])
        selection_before = dict(controller.matching_selection)
        target = items[1]
        button = view.findChild(QPushButton, f"quiz-matching-star-button-{target['entry_id']}")

        self.assertIsNotNone(button)
        button.click()

        self.assertTrue(is_entry_in_system_collection(target["entry_id"], "starred"))
        self.assertEqual(controller.matching_selection, selection_before)


class CollectionLearningProgressTests(PhaseBTestCase):
    def test_progress_counts_distinct_current_cards_and_excludes_legacy_and_system_pools(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(3, card_size=1)
        from src.collections import get_card_groups_for_collection

        cards = get_card_groups_for_collection(collection_id)
        learned_card_id = cards[0]["card_id"]
        for index in range(2):
            session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 1)
            quiz.record_quiz_answer(
                session_id,
                entry_ids[0],
                f"prompt-{index}",
                "answer",
                "answer",
                True,
            )
            quiz.complete_quiz_session(session_id)

        with db.get_connection() as connection:
            connection.execute(
                """
                INSERT INTO quiz_sessions (
                    collection_id, card_number, quiz_type, started_at, completed_at,
                    total_items, status, card_id, card_revision_id
                ) VALUES (?, 2, 'term_to_meaning', '2026-01-01', '2026-01-01', 1, 'completed', NULL, NULL)
                """,
                (collection_id,),
            )

        add_entries_to_system_collection([entry_ids[0]], "starred")

        with db.get_connection() as connection:
            progress = learning_workflow.get_collection_learning_progress(connection)

        self.assertEqual(
            progress[collection_id],
            {
                "collection_id": collection_id,
                "learned_cards": 1,
                "total_cards": 3,
                "percent": 33,
            },
        )
        self.assertEqual(cards[0]["card_id"], learned_card_id)
        starred_ids = {
            row["collection_id"]
            for row in learning_workflow.get_study_cards(db.get_connection())
            if row["collection_name"] == "Starred"
        }
        self.assertTrue(starred_ids)
        self.assertTrue(starred_ids.isdisjoint(progress))

    def test_card_revision_change_does_not_reset_learned_status(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(2, card_size=2)
        from src.collections import get_card_groups_for_collection, move_entry_in_collection

        before = get_card_groups_for_collection(collection_id)[0]
        session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 1)
        quiz.record_quiz_answer(session_id, entry_ids[0], "prompt", "answer", "answer", True)
        quiz.complete_quiz_session(session_id)

        move_entry_in_collection(collection_id, entry_ids[0], 2)
        after = get_card_groups_for_collection(collection_id)[0]
        self.assertEqual(after["card_id"], before["card_id"])
        self.assertNotEqual(after["card_revision_id"], before["card_revision_id"])

        with db.get_connection() as connection:
            progress = learning_workflow.get_collection_learning_progress(connection)
        self.assertEqual(progress[collection_id]["learned_cards"], 1)
        self.assertEqual(progress[collection_id]["total_cards"], 1)


class CollectionProgressProjectionTests(PhaseBTestCase):
    def test_controller_projects_progress_only_onto_normal_collections(self) -> None:
        collection_id, entry_ids = self._collection_with_entries()
        session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 1)
        quiz.record_quiz_answer(session_id, entry_ids[0], "prompt", "answer", "answer", True)
        quiz.complete_quiz_session(session_id)
        add_entries_to_system_collection(entry_ids, "starred")

        controller = CollectionsController()
        controller.refresh()

        normal = next(row for row in controller.collections if row["id"] == collection_id)
        self.assertEqual(normal["learned_cards"], 1)
        self.assertEqual(normal["total_cards"], 1)
        self.assertEqual(normal["learning_percent"], 100)
        self.assertTrue(all("learned_cards" not in row for row in controller.system_pools))


class CollectionProgressVisibilityTests(PhaseBTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_normal_collection_progress_is_visible_but_system_pool_progress_is_not(self) -> None:
        collection_id, entry_ids = self._collection_with_entries()
        session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 1)
        quiz.record_quiz_answer(session_id, entry_ids[0], "prompt", "answer", "answer", True)
        quiz.complete_quiz_session(session_id)
        add_entries_to_system_collection(entry_ids, "starred")
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)

        view.refresh()

        buttons = view.findChildren(QPushButton, "collections-list-item")
        normal_button = next(button for button in buttons if button.text().startswith("Synthetic Phase B"))
        starred_button = next(button for button in buttons if "Starred" in button.text())
        self.assertIn("1/1", normal_button.text())
        self.assertIn("100%", normal_button.text())
        self.assertNotIn("%", starred_button.text())

        controller.select_collection(collection_id, is_system=False)
        progress_label = view.findChild(QLabel, "collections-learning-progress")
        self.assertIsNotNone(progress_label)
        self.assertIn("1 of 1 Cards learned (100%)", progress_label.text())


if __name__ == "__main__":
    unittest.main()

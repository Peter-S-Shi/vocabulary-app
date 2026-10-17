from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from src import db
from src.collections import (
    add_entries_to_collection, add_entries_to_system_collection, create_collection,
    get_or_create_system_collection, get_system_collection_by_type_or_name,
)
from src.entries import add_entry
from src.ui_desktop.controllers.collections_controller import CollectionsController
from src.ui_desktop.controllers.quiz_controller import QuizController
from src.ui_desktop.theming.color_math import contrast_ratio
from src.ui_desktop.theming.theme_manager import build_stylesheet
from src.ui_desktop.theming.tokens import ModeCustomization, PRESET_NAMES, build_resolved_theme_tokens
from src.ui_desktop.views.collections_view import CollectionsView
from src.ui_desktop.state.handoff import QuizLaunchIntent
from src.ui_desktop.views.quiz_view import QuizView


RANDOM_QUIZ_SELECTOR = "QPushButton#collections-system-pool-random-quiz-button"


def _rule_body(stylesheet: str, selector: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(selector)}\s*\{{([^}}]*)\}}", stylesheet)
    return match.group(1) if match else None


class _FictionalQtDatabase:
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "m22c-fictional.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.previous_db_path
        self.temp_dir.cleanup()


class PoolRandomQuizThemeTests(_FictionalQtDatabase, unittest.TestCase):
    def test_starred_and_proficient_quiz_buttons_have_explicit_readable_theme_pairs(self) -> None:
        for system_type in ("starred", "proficient_pool"):
            with self.subTest(pool=system_type):
                get_or_create_system_collection(system_type, system_type.replace("_", " ").title())
                entry_id = add_entry("French", "English", "word", f"mot-{system_type}", f"meaning-{system_type}")
                add_entries_to_system_collection([entry_id], system_type)
                pool = get_system_collection_by_type_or_name(system_type)
                controller = CollectionsController()
                view = CollectionsView(controller)
                self.addCleanup(view.deleteLater)
                controller.refresh()
                controller.select_collection(int(pool["id"]), is_system=True)
                button = view.findChild(QPushButton, "collections-system-pool-random-quiz-button")
                self.assertIsNotNone(button)
                self.assertTrue(button.isEnabled())
                self.assertEqual(button.text(), "Random Quiz")

        for mode in ("Light", "Dark"):
            for preset in PRESET_NAMES:
                with self.subTest(mode=mode, preset=preset):
                    tokens = build_resolved_theme_tokens(mode, ModeCustomization(preset=preset))
                    body = _rule_body(build_stylesheet(tokens), RANDOM_QUIZ_SELECTOR)
                    self.assertIsNotNone(body)
                    self.assertIn(f"background-color: {tokens.accent.primary.background};", body)
                    self.assertIn(f"color: {tokens.accent.primary.foreground};", body)
                    self.assertGreaterEqual(
                        contrast_ratio(tokens.accent.primary.background, tokens.accent.primary.foreground),
                        4.5,
                    )


    def test_empty_pool_random_quiz_buttons_are_visible_but_disabled(self) -> None:
        for system_type in ("starred", "proficient_pool"):
            with self.subTest(pool=system_type):
                get_or_create_system_collection(system_type, system_type.replace("_", " ").title())
                pool = get_system_collection_by_type_or_name(system_type)
                controller = CollectionsController()
                view = CollectionsView(controller)
                self.addCleanup(view.deleteLater)
                controller.refresh()
                controller.select_collection(int(pool["id"]), is_system=True)
                button = view.findChild(QPushButton, "collections-system-pool-random-quiz-button")
                self.assertIsNotNone(button)
                self.assertFalse(button.isEnabled())
                self.assertEqual(button.text(), "Random Quiz")

    def test_pool_button_states_and_custom_themes_use_readable_pairs(self) -> None:
        for mode in ("Light", "Dark"):
            choices = [ModeCustomization(preset=name) for name in PRESET_NAMES]
            choices.append(ModeCustomization(
                accent_color="#9C264A" if mode == "Light" else "#D9A846",
                background_color="#F9F5ED" if mode == "Light" else "#151923",
                surface_color="#FFFDF9" if mode == "Light" else "#222938",
            ))
            for custom in choices:
                with self.subTest(mode=mode, custom=custom):
                    tokens = build_resolved_theme_tokens(mode, custom)
                    stylesheet = build_stylesheet(tokens)
                    base = _rule_body(stylesheet, RANDOM_QUIZ_SELECTOR)
                    hover = _rule_body(stylesheet, RANDOM_QUIZ_SELECTOR + ":hover:enabled")
                    focus = _rule_body(stylesheet, RANDOM_QUIZ_SELECTOR + ":focus:enabled")
                    disabled = _rule_body(stylesheet, RANDOM_QUIZ_SELECTOR + ":disabled")
                    self.assertIn(f"background-color: {tokens.accent.primary.background};", base)
                    self.assertIn(f"color: {tokens.accent.primary.foreground};", base)
                    self.assertIn(f"background-color: {tokens.accent.hover.background};", hover)
                    self.assertIn(f"color: {tokens.accent.hover.foreground};", hover)
                    self.assertIn(f"border: 2px solid {tokens.accent.primary.foreground};", focus)
                    self.assertIn(f"background-color: {tokens.neutral.surface_secondary};", disabled)
                    self.assertIn(f"color: {tokens.neutral.text_disabled};", disabled)
                    self.assertGreaterEqual(contrast_ratio(tokens.accent.primary.background, tokens.accent.primary.foreground), 4.5)
                    self.assertGreaterEqual(contrast_ratio(tokens.accent.hover.background, tokens.accent.hover.foreground), 4.5)


class QuizAnswerThemeTests(_FictionalQtDatabase, unittest.TestCase):
    def _start_quiz(
        self, terms: list[tuple[str, str]], quiz_type: str = "term_to_meaning",
    ) -> tuple[QuizController, QuizView]:
        entries = [add_entry("French", "English", "word", term, meaning) for term, meaning in terms]
        collection_id = create_collection("Fictional theme check", card_size=len(entries))
        add_entries_to_collection(entries, collection_id)
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        intent = QuizLaunchIntent(
            source="test", collection_id=collection_id, collection_name="Fictional theme check",
            card_number=0 if quiz_type == "matching" else 1, card_id=None,
            quiz_type=quiz_type, item_count=len(entries), reason="test",
        )
        self.assertTrue(controller.start(intent))
        return controller, view

    def _values(self, view: QuizView, role: str) -> list[QLabel]:
        return view.findChildren(QLabel, role)

    def test_revealed_self_graded_draft_is_neutral_and_expected_is_accent(self) -> None:
        controller, view = self._start_quiz([("chat", "cat")])
        controller.set_answer_draft("draft answer")
        controller.reveal_answer()
        self.assertEqual([label.text() for label in self._values(view, "quiz-field-text")], ["draft answer"])
        self.assertEqual([label.text() for label in self._values(view, "quiz-field-text-expected")], ["cat"])
        self.assertEqual(self._values(view, "quiz-field-text-wrong"), [])

    def test_wrong_and_correct_mcq_feedback_roles_follow_grading(self) -> None:
        terms = [(f"term-{index}", f"meaning-{index}") for index in range(5)]
        controller, view = self._start_quiz(terms, "term_to_meaning_mcq")
        item = controller.current_item()
        wrong = next(option for option in item["options"] if option != item["correct_answer"])
        self.assertTrue(controller.submit_mcq(wrong))
        self.assertEqual([label.text() for label in self._values(view, "quiz-field-text-wrong")], [wrong])
        self.assertEqual([label.text() for label in self._values(view, "quiz-field-text-expected")], [item["correct_answer"]])
        self.assertEqual(len(self._values(view, "quiz-feedback-wrong")), 1)

    def test_correct_mcq_submission_uses_accent_without_wrong_role(self) -> None:
        terms = [(f"term-{index}", f"meaning-{index}") for index in range(5)]
        controller, view = self._start_quiz(terms, "term_to_meaning_mcq")
        expected = controller.current_item()["correct_answer"]
        self.assertTrue(controller.submit_mcq(expected))
        self.assertEqual(
            [label.text() for label in self._values(view, "quiz-field-text-expected")],
            [expected, expected],
        )
        self.assertEqual(self._values(view, "quiz-field-text-wrong"), [])
        self.assertEqual(len(self._values(view, "quiz-feedback-correct")), 1)

    def test_matching_wrong_answers_use_same_read_only_mistake_roles(self) -> None:
        terms = [(f"term-{index}", f"meaning-{index}") for index in range(4)]
        controller, view = self._start_quiz(terms, "matching")
        items = controller.matching_items()
        meanings = [item["expected_meaning"] for item in items]
        for item, wrong in zip(items, meanings[1:] + meanings[:1]):
            controller.set_matching_selection(item, wrong)
        self.assertTrue(controller.submit_matching())
        controller.review_mistakes()
        self.assertEqual(len(self._values(view, "quiz-field-text-wrong")), 1)
        self.assertEqual(len(self._values(view, "quiz-field-text-expected")), 1)
        self.assertEqual(len(self._values(view, "quiz-feedback-wrong")), 1)

    def test_completed_wrong_answer_remains_semantic_in_mistake_review(self) -> None:
        controller, view = self._start_quiz([("chien", "dog")])
        controller.set_answer_draft("not dog")
        controller.reveal_answer()
        self.assertTrue(controller.submit_self_graded(False))
        controller.review_mistakes()
        self.assertEqual([label.text() for label in self._values(view, "quiz-field-text-wrong")], ["not dog"])
        self.assertEqual([label.text() for label in self._values(view, "quiz-field-text-expected")], ["dog"])
        self.assertEqual(len(self._values(view, "quiz-feedback-wrong")), 1)

    def test_feedback_theme_pairs_remain_readable_in_presets_and_custom_modes(self) -> None:
        for mode in ("Light", "Dark"):
            choices = [ModeCustomization(preset=name) for name in PRESET_NAMES]
            choices.append(ModeCustomization(
                accent_color="#9C264A" if mode == "Light" else "#D9A846",
                surface_color="#FFFDF9" if mode == "Light" else "#222938",
            ))
            for custom in choices:
                with self.subTest(mode=mode, custom=custom):
                    tokens = build_resolved_theme_tokens(mode, custom)
                    qss = build_stylesheet(tokens)
                    wrong = _rule_body(qss, "QLabel#quiz-field-text-wrong")
                    expected = _rule_body(qss, "QLabel#quiz-field-text-expected")
                    self.assertIsNotNone(wrong)
                    self.assertIsNotNone(expected)
                    self.assertIn(f"background-color: {tokens.semantic.quiz_wrong_soft};", wrong)
                    self.assertIn(f"color: {tokens.semantic.quiz_wrong.background};", wrong)
                    self.assertIn(f"background-color: {tokens.accent.soft.background};", expected)
                    self.assertIn(f"color: {tokens.accent.soft.foreground};", expected)
                    self.assertGreaterEqual(
                        contrast_ratio(tokens.semantic.quiz_wrong_soft, tokens.semantic.quiz_wrong.background), 4.5,
                    )
                    self.assertGreaterEqual(
                        contrast_ratio(tokens.accent.soft.background, tokens.accent.soft.foreground), 4.5,
                    )


if __name__ == "__main__":
    unittest.main()

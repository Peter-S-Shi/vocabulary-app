from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDateEdit, QLabel, QPushButton

from src import db
from src.card_history import reconcile_collection_card_history
from src.review_schedule import get_card_schedule
from src.ui_desktop.controllers.quiz_controller import QuizController
from src.ui_desktop.theming.color_math import contrast_ratio
from src.ui_desktop.theming.theme_manager import Accent, Appearance, build_stylesheet
from src.ui_desktop.theming.tokens import (
    THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT,
    THEME_INDIGO_VIOLET_DARK, THEME_INDIGO_VIOLET_LIGHT,
    THEME_SAGE_TEAL_DARK, THEME_SAGE_TEAL_LIGHT,
    THEME_WARM_NEUTRAL_DARK, THEME_WARM_NEUTRAL_LIGHT,
    CustomThemeConfig, ModeCustomization, build_resolved_theme_tokens,
)
from src.ui_desktop.views.quiz_view import QuizView

class PatchA1QuizReviewSchedulingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "test-patch-a1.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _create_card(self, *, name: str = "Test Card Collection") -> int:
        now = "2026-08-27T12:00:00+00:00"
        with db.get_connection() as conn:
            col_id = int(conn.execute(
                "INSERT INTO collections (name, description, card_size, created_at, updated_at) VALUES (?, '', 1, ?, ?)",
                (name, now, now),
            ).lastrowid)
            entry_id = int(conn.execute(
                "INSERT INTO entries (language, explanation_language, entry_type, term, meaning, example, notes, tags, source, status, created_at, updated_at) VALUES ('English', 'English', 'word', 'test-term', 'test-meaning', '', '', '', '', 'new', ?, ?)",
                (now, now),
            ).lastrowid)
            conn.execute(
                "INSERT INTO entry_collections (entry_id, collection_id, position, added_at) VALUES (?, ?, 1, ?)",
                (entry_id, col_id, now),
            )
            reconcile_collection_card_history(conn, col_id, change_reason="test_patch_a1")
            return int(conn.execute(
                "SELECT id FROM cards WHERE collection_id = ? AND card_number = 1 AND is_active = 1",
                (col_id,),
            ).fetchone()[0])

    def _setup_completed_quiz_view(self, card_id: int, today: date = date(2026, 8, 27)) -> tuple[QuizController, QuizView]:
        controller = QuizController(today_provider=lambda: today)
        controller.completed_session = {
            "card_id": card_id,
            "card_number": 1,
            "total_items": 1,
            "correct_count": 1,
            "wrong_count": 0,
        }
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        view._render()
        return controller, view

    def test_selection_does_not_persist_to_database(self) -> None:
        """Selecting candidate date presets or custom date does NOT write to database."""
        card_id = self._create_card()
        controller, view = self._setup_completed_quiz_view(card_id, today=date(2026, 8, 27))
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        status_label = view.findChild(QLabel, "quiz-completion-schedule-status")
        self.assertIsNotNone(status_label)
        self.assertEqual(status_label.text(), "Unscheduled")
        btn_1day = view.findChild(QPushButton, "quiz-completion-schedule-1-day")
        self.assertIsNotNone(btn_1day)
        btn_1day.click()
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        self.assertIsNone(controller.completion_schedule()["next_due_at"])
        btn_7day = view.findChild(QPushButton, "quiz-completion-schedule-7-days")
        self.assertIsNotNone(btn_7day)
        btn_7day.click()
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        custom_date = view.findChild(QDateEdit, "quiz-completion-schedule-custom-date")
        self.assertIsNotNone(custom_date)
        custom_date.setDate(QDate(2026, 9, 15))
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])

    def test_confirmation_persists_and_updates_status(self) -> None:
        """Explicit confirmation via Schedule Review button persists the schedule."""
        card_id = self._create_card()
        controller, view = self._setup_completed_quiz_view(card_id, today=date(2026, 8, 27))
        save_button = view.findChild(QPushButton, "quiz-completion-schedule-save-button")
        self.assertIsNotNone(save_button)
        self.assertFalse(save_button.isEnabled())
        btn_2days = view.findChild(QPushButton, "quiz-completion-schedule-2-days")
        self.assertIsNotNone(btn_2days)
        btn_2days.click()
        self.assertTrue(save_button.isEnabled())
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        save_button.click()
        db_schedule = get_card_schedule(card_id)
        self.assertEqual(db_schedule["next_due_at"], "2026-08-29")
        self.assertEqual(controller.completion_schedule()["next_due_at"], "2026-08-29")
        status_label = view.findChild(QLabel, "quiz-completion-schedule-status")
        self.assertIsNotNone(status_label)
        self.assertEqual(status_label.text(), "Scheduled · 2026-08-29")

    def test_reselection_overrides_staged_choice_without_intermediate_persists(self) -> None:
        """User can change candidate selections multiple times; only final choice is persisted upon clicking Schedule Review."""
        card_id = self._create_card()
        controller, view = self._setup_completed_quiz_view(card_id, today=date(2026, 8, 27))
        btn_today = view.findChild(QPushButton, "quiz-completion-schedule-today")
        btn_1day = view.findChild(QPushButton, "quiz-completion-schedule-1-day")
        btn_2days = view.findChild(QPushButton, "quiz-completion-schedule-2-days")
        btn_7days = view.findChild(QPushButton, "quiz-completion-schedule-7-days")
        custom_date = view.findChild(QDateEdit, "quiz-completion-schedule-custom-date")
        save_button = view.findChild(QPushButton, "quiz-completion-schedule-save-button")
        btn_1day.click()
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        btn_7days.click()
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        btn_2days.click()
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        custom_date.setDate(QDate(2026, 10, 1))
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        btn_today.click()
        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        save_button.click()
        self.assertEqual(get_card_schedule(card_id)["next_due_at"], "2026-08-27")
        status_label = view.findChild(QLabel, "quiz-completion-schedule-status")
        self.assertEqual(status_label.text(), "Scheduled · 2026-08-27")

class PatchA1NextReviewThemeCoherenceTests(unittest.TestCase):
    REQUIRED_SELECTORS = [
        "QLabel#quiz-completion-schedule-heading",
        "QLabel#quiz-completion-schedule-status",
        "QPushButton#quiz-completion-schedule-today",
        "QPushButton#quiz-completion-schedule-1-day",
        "QPushButton#quiz-completion-schedule-2-days",
        "QPushButton#quiz-completion-schedule-7-days",
        "QDateEdit#quiz-completion-schedule-custom-date",
        "QCalendarWidget#quiz-completion-schedule-popup",
        "QPushButton#quiz-completion-schedule-save-button",
    ]
    ALL_PRESET_TOKENS = [
        THEME_CALM_BLUE_LIGHT, THEME_CALM_BLUE_DARK,
        THEME_INDIGO_VIOLET_LIGHT, THEME_INDIGO_VIOLET_DARK,
        THEME_SAGE_TEAL_LIGHT, THEME_SAGE_TEAL_DARK,
        THEME_WARM_NEUTRAL_LIGHT, THEME_WARM_NEUTRAL_DARK,
    ]
    def test_all_next_review_selectors_present_in_preset_stylesheets(self) -> None:
        for tokens in self.ALL_PRESET_TOKENS:
            stylesheet = build_stylesheet(tokens)
            for selector in self.REQUIRED_SELECTORS:
                self.assertIn(selector, stylesheet, f"Selector {selector} missing")
    def test_light_mode_controls_use_dark_foreground_tokens(self) -> None:
        for tokens in [THEME_CALM_BLUE_LIGHT, THEME_INDIGO_VIOLET_LIGHT, THEME_SAGE_TEAL_LIGHT, THEME_WARM_NEUTRAL_LIGHT]:
            stylesheet = build_stylesheet(tokens)
            text_primary_color = QColor(tokens.neutral.text_primary)
            self.assertLess(text_primary_color.lightness(), 100)
            ratio = contrast_ratio(tokens.neutral.text_primary, tokens.neutral.surface_primary)
            self.assertGreaterEqual(ratio, 4.5)
            self.assertIn(f"color: {tokens.neutral.text_primary};", stylesheet)
            self.assertIn(f"background-color: {tokens.neutral.surface_primary};", stylesheet)
    def test_dark_mode_controls_use_light_foreground_tokens(self) -> None:
        for tokens in [THEME_CALM_BLUE_DARK, THEME_INDIGO_VIOLET_DARK, THEME_SAGE_TEAL_DARK, THEME_WARM_NEUTRAL_DARK]:
            stylesheet = build_stylesheet(tokens)
            text_primary_color = QColor(tokens.neutral.text_primary)
            self.assertGreater(text_primary_color.lightness(), 150)
            ratio = contrast_ratio(tokens.neutral.text_primary, tokens.neutral.surface_primary)
            self.assertGreaterEqual(ratio, 4.5)
    def test_custom_theme_tokens_are_dynamically_applied_to_next_review(self) -> None:
        custom_light = ModeCustomization(
            accent_color="#c2410c",
            surface_color="#fff7ed",
            text_color="#431407",
        )
        custom_dark = ModeCustomization(
            accent_color="#fb923c",
            surface_color="#1c1917",
            text_color="#fafaf9",
        )
        custom_light_tokens = build_resolved_theme_tokens("Light", custom_light)
        custom_dark_tokens = build_resolved_theme_tokens("Dark", custom_dark)
        for tokens in [custom_light_tokens, custom_dark_tokens]:
            stylesheet = build_stylesheet(tokens)
            for selector in self.REQUIRED_SELECTORS:
                self.assertIn(selector, stylesheet)
            self.assertIn(f"background-color: {tokens.neutral.surface_primary};", stylesheet)
            self.assertIn(f"color: {tokens.neutral.text_primary};", stylesheet)

if __name__ == "__main__":
    unittest.main()

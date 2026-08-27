from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QLabel,
    QPushButton,
    QTableWidget,
)

from src import db, quiz
from src.card_history import reconcile_collection_card_history
from src.review_schedule import set_card_next_review
from src.ui_desktop.controllers.review_calendar_controller import ReviewCalendarController
from src.ui_desktop.theming.color_math import contrast_ratio
from src.ui_desktop.theming.theme_manager import (
    Accent,
    Appearance,
    build_palette,
    build_stylesheet,
)
from src.ui_desktop.theming.tokens import (
    THEME_CALM_BLUE_DARK,
    THEME_CALM_BLUE_LIGHT,
    THEME_INDIGO_VIOLET_DARK,
    THEME_INDIGO_VIOLET_LIGHT,
    THEME_SAGE_TEAL_DARK,
    THEME_SAGE_TEAL_LIGHT,
    THEME_WARM_NEUTRAL_DARK,
    THEME_WARM_NEUTRAL_LIGHT,
    CustomThemeConfig,
    ModeCustomization,
    build_resolved_theme_tokens,
)
from src.ui_desktop.views.review_calendar_view import ReviewCalendarView


class PatchA2ReviewCalendarCoherenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "test-patch-a2.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _create_card(self, *, name: str = "Test Collection") -> tuple[int, int, int]:
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
            reconcile_collection_card_history(conn, col_id, change_reason="test_patch_a2")
            card_row = conn.execute(
                "SELECT id, card_number FROM cards WHERE collection_id = ? AND is_active = 1",
                (col_id,),
            ).fetchone()
            return int(card_row[0]), col_id, int(card_row[1])

    def _record_completion(self, col_id: int, card_number: int, card_id: int, completed_at: str) -> int:
        session_id = quiz.create_quiz_session(col_id, card_number, "term_to_meaning", 1)
        quiz.record_quiz_answer(session_id, 1, "test-term", "test-meaning", "test-meaning", True)
        quiz.mark_quiz_session_completed(session_id)
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE quiz_sessions SET completed_at = ?, card_id = ? WHERE id = ?",
                (completed_at, card_id, session_id),
            )
        return session_id

    def test_calendar_date_selection_updates_schedule_table_content(self) -> None:
        """Switching calendar dates filters _schedule_table to only cards scheduled on that date."""
        card_a, col_a, num_a = self._create_card(name="Collection Alpha")
        card_b, col_b, num_b = self._create_card(name="Collection Beta")
        card_today, col_today, num_today = self._create_card(name="Collection Today")

        today_str = date.today().isoformat()
        set_card_next_review(card_a, "2026-08-29")
        set_card_next_review(card_b, "2026-08-30")
        set_card_next_review(card_today, today_str)

        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        # On initial load (Today): only card_today appears in table
        self.assertEqual(view._schedule_table.rowCount(), 1)
        self.assertEqual(view._schedule_table.item(0, 0).text(), "Collection Today")
        self.assertEqual(view._schedule_table.item(0, 3).text(), today_str)

        # 1. Switch to Date A (2026-08-29): only card_a appears
        view._calendar.setSelectedDate(QDate(2026, 8, 29))
        self.assertEqual(controller.selected_date, "2026-08-29")
        self.assertIn("2026-08-29", view._schedule_heading.text())
        self.assertEqual(view._schedule_table.rowCount(), 1)
        self.assertEqual(view._schedule_table.item(0, 0).text(), "Collection Alpha")
        self.assertEqual(view._schedule_table.item(0, 3).text(), "2026-08-29")

        # 2. Switch to Date B (2026-08-30): only card_b appears
        view._calendar.setSelectedDate(QDate(2026, 8, 30))
        self.assertEqual(controller.selected_date, "2026-08-30")
        self.assertIn("2026-08-30", view._schedule_heading.text())
        self.assertEqual(view._schedule_table.rowCount(), 1)
        self.assertEqual(view._schedule_table.item(0, 0).text(), "Collection Beta")
        self.assertEqual(view._schedule_table.item(0, 3).text(), "2026-08-30")

        # 3. Switch to Date C (2026-08-31) with no schedules: table is empty
        view._calendar.setSelectedDate(QDate(2026, 8, 31))
        self.assertEqual(controller.selected_date, "2026-08-31")
        self.assertEqual(view._schedule_table.rowCount(), 0)

        # 4. Click Today button: table faithfully shows today's scheduled card
        today_button = view.findChild(QPushButton, "review-calendar-today-button")
        self.assertIsNotNone(today_button)
        today_button.click()
        self.assertEqual(controller.selected_date, today_str)
        self.assertEqual(view._schedule_table.rowCount(), 1)
        self.assertEqual(view._schedule_table.item(0, 0).text(), "Collection Today")

    def test_schedule_mutation_refreshes_date_list_faithfully(self) -> None:
        """Rescheduling or clearing a card updates the current date's schedule table immediately."""
        card_a, col_a, num_a = self._create_card(name="Reschedule Col")
        set_card_next_review(card_a, "2026-08-29")

        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        # Switch to 2026-08-29
        view._calendar.setSelectedDate(QDate(2026, 8, 29))
        self.assertEqual(view._schedule_table.rowCount(), 1)

        # Select Card and reschedule to 2026-08-30
        view._schedule_table.selectRow(0)
        view._schedule_date.setDate(QDate(2026, 8, 30))
        view._schedule_save_button.click()

        # Table on 2026-08-29 is now empty because card moved to 2026-08-30
        self.assertEqual(view._schedule_table.rowCount(), 0)

        # Switch to 2026-08-30: card now appears there
        view._calendar.setSelectedDate(QDate(2026, 8, 30))
        self.assertEqual(view._schedule_table.rowCount(), 1)
        self.assertEqual(view._schedule_table.item(0, 0).text(), "Reschedule Col")
        self.assertEqual(view._schedule_table.item(0, 3).text(), "2026-08-30")

        # Clear schedule
        view._schedule_table.selectRow(0)
        view._schedule_clear_button.click()
        # Table on 2026-08-30 is now empty
        self.assertEqual(view._schedule_table.rowCount(), 0)

    def test_review_count_displayed_for_selected_card(self) -> None:
        """Selecting a card displays its completed review count in the schedule editing target header."""
        card_id, col_id, card_num = self._create_card(name="Count Collection")
        self._record_completion(col_id, card_num, card_id, "2026-08-20T10:00:00+00:00")
        self._record_completion(col_id, card_num, card_id, "2026-08-22T10:00:00+00:00")
        self._record_completion(col_id, card_num, card_id, "2026-08-25T10:00:00+00:00")
        set_card_next_review(card_id, "2026-08-28")

        controller = ReviewCalendarController()
        controller.set_selected_date("2026-08-28")
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        view._schedule_table.selectRow(0)
        self.assertEqual(controller.card_review_count(), 3)
        target_label = view.findChild(QLabel, "review-calendar-editing-target-label")
        self.assertIsNotNone(target_label)
        self.assertIn("Editing schedule for: Count Collection — Card #1", target_label.text())
        self.assertIn("Reviews completed: 3", target_label.text())

    def test_schedule_target_isolation_from_quiz_history(self) -> None:
        """Clicking Completion History rows inspects evidence without hijacking or changing the schedule editing target."""
        card1, col1, num1 = self._create_card(name="Target Card")
        card2, col2, num2 = self._create_card(name="History Card")

        set_card_next_review(card1, "2026-08-28")
        self._record_completion(col2, num2, card2, f"{date.today().isoformat()}T10:00:00+00:00")

        controller = ReviewCalendarController()
        controller.set_selected_date("2026-08-28")
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        # Step 1: Select Target Card from the Schedule table (2026-08-28)
        self.assertEqual(view._schedule_table.rowCount(), 1)
        view._schedule_table.selectRow(0)
        self.assertEqual(controller.current_schedule["card_id"], card1)
        self.assertEqual(controller.current_schedule["next_due_at"], "2026-08-28")
        self.assertTrue(view._schedule_save_button.isEnabled())
        self.assertTrue(view._schedule_clear_button.isEnabled())
        self.assertIn("Target Card", view._editing_target_label.text())

        # Step 2: Select History Card from the completion history table
        view._table.selectRow(0)
        # History table loads card2 history evidence
        self.assertEqual(view._history_table.rowCount(), 1)
        # BUT current_schedule is STILL card1 -- NOT hijacked!
        self.assertEqual(controller.current_schedule["card_id"], card1)
        self.assertEqual(controller.current_schedule["next_due_at"], "2026-08-28")
        self.assertIn("Target Card", view._editing_target_label.text())

        # Saving schedule mutates Card1, not Card2
        view._schedule_date.setDate(QDate(2026, 9, 5))
        view._schedule_save_button.click()
        self.assertEqual(controller.current_schedule["card_id"], card1)
        self.assertEqual(controller.current_schedule["next_due_at"], "2026-09-05")

    def test_legacy_ui_retired_from_native_view(self) -> None:
        """Legacy Review History table is completely removed from native view while backend remains intact."""
        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)

        self.assertFalse(hasattr(view, "_legacy_table"))
        self.assertIsNone(view.findChild(QLabel, "review-calendar-legacy-heading"))
        self.assertIsNone(view.findChild(QLabel, "review-calendar-legacy-caption"))
        self.assertIsNone(view.findChild(QTableWidget, "review-calendar-legacy-table"))
        self.assertTrue(hasattr(controller, "legacy_logs"))
        self.assertEqual(controller.legacy_logs, [])

    def test_dynamic_theme_switching_updates_calendar_weekend_format(self) -> None:
        """Dynamic palette/theme change updates calendar weekend text format without hardcoded colors."""
        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)

        # 1. Light Theme
        view.setPalette(build_palette(THEME_CALM_BLUE_LIGHT))
        view._update_weekend_format()
        sat_fmt_light = view._calendar.weekdayTextFormat(Qt.DayOfWeek.Saturday)
        sat_color = sat_fmt_light.foreground().color()
        self.assertTrue(sat_color.isValid())
        self.assertEqual(sat_color.name(), THEME_CALM_BLUE_LIGHT.neutral.text_primary.lower())

        # 2. Dark Theme
        view.setPalette(build_palette(THEME_CALM_BLUE_DARK))
        view._update_weekend_format()
        sat_fmt_dark = view._calendar.weekdayTextFormat(Qt.DayOfWeek.Saturday)
        sat_color_dark = sat_fmt_dark.foreground().color()
        self.assertTrue(sat_color_dark.isValid())
        self.assertEqual(sat_color_dark.name(), THEME_CALM_BLUE_DARK.neutral.text_primary.lower())
        self.assertNotEqual(sat_color.name(), sat_color_dark.name())

    def test_selected_card_row_and_calendar_theming(self) -> None:
        """Theme stylesheet includes paired contrast tokens for schedule selection and calendar widget."""
        for tokens in [
            THEME_CALM_BLUE_LIGHT, THEME_CALM_BLUE_DARK,
            THEME_INDIGO_VIOLET_LIGHT, THEME_INDIGO_VIOLET_DARK,
            THEME_SAGE_TEAL_LIGHT, THEME_SAGE_TEAL_DARK,
            THEME_WARM_NEUTRAL_LIGHT, THEME_WARM_NEUTRAL_DARK,
        ]:
            stylesheet = build_stylesheet(tokens)
            self.assertIn("QTableWidget#review-calendar-schedule-table::item:selected", stylesheet)
            self.assertIn(f"background-color: {tokens.accent.primary.background};", stylesheet)
            self.assertIn(f"color: {tokens.accent.primary.foreground};", stylesheet)
            self.assertIn("font-weight: 700;", stylesheet)
            self.assertIn("QCalendarWidget#review-calendar-widget", stylesheet)
            self.assertIn("QPushButton#review-calendar-today-button", stylesheet)
            self.assertIn("QLabel#review-calendar-editing-target-label", stylesheet)

            ratio = contrast_ratio(tokens.accent.primary.foreground, tokens.accent.primary.background)
            self.assertGreaterEqual(ratio, 4.5)


if __name__ == "__main__":
    unittest.main()

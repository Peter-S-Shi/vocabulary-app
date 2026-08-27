from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
)

from src import db, quiz
from src.card_history import reconcile_collection_card_history
from src.review_schedule import get_card_schedule, set_card_next_review
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

        # Clear schedule with confirmation Yes
        view._schedule_table.selectRow(0)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            view._schedule_clear_button.click()
        # Table on 2026-08-30 is now empty
        self.assertEqual(view._schedule_table.rowCount(), 0)

    def test_clear_schedule_confirmation_behavior(self) -> None:
        """Clear schedule requires explicit confirmation; Cancel produces 0 mutations."""
        card_id, col_id, card_num = self._create_card(name="Confirmation Col")
        set_card_next_review(card_id, "2026-08-28")

        controller = ReviewCalendarController()
        controller.set_selected_date("2026-08-28")
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        view._schedule_table.selectRow(0)

        # 1. User clicks Cancel in dialog: NO changes made
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel) as mock_msg:
            view._schedule_clear_button.click()
            mock_msg.assert_called_once()
            # Dialog message explicitly mentions card and that action cannot be undone
            prompt_text = mock_msg.call_args[0][2]
            self.assertIn("Confirmation Col — Card #1", prompt_text)
            self.assertIn("cannot be undone", prompt_text)

        # Card is still scheduled on 2026-08-28 in DB and controller
        self.assertEqual(get_card_schedule(card_id)["next_due_at"], "2026-08-28")
        self.assertEqual(controller.current_schedule["next_due_at"], "2026-08-28")
        self.assertEqual(view._schedule_table.rowCount(), 1)

        # 2. User clicks Yes in dialog: schedule is cleared
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as mock_msg:
            view._schedule_clear_button.click()
            mock_msg.assert_called_once()

        self.assertIsNone(get_card_schedule(card_id)["next_due_at"])
        self.assertEqual(controller.current_schedule["state"], "unscheduled")
        self.assertEqual(view._schedule_table.rowCount(), 0)

    def test_card_history_detail_header_format_from_schedule_and_from_history(self) -> None:
        """Card History detail header displays completed reviews and selected session timestamp cleanly."""
        card_id, col_id, card_num = self._create_card(name="Text collections")
        self._record_completion(col_id, card_num, card_id, "2026-08-10T09:48:00+00:00")
        self._record_completion(col_id, card_num, card_id, "2026-08-12T14:20:00+00:00")
        self._record_completion(col_id, card_num, card_id, "2026-08-15T18:00:00+00:00")
        set_card_next_review(card_id, "2026-08-28")

        controller = ReviewCalendarController()
        controller.set_selected_date("2026-08-28")
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        # 1. Selected from Schedule Table
        view._schedule_table.selectRow(0)
        self.assertEqual(
            view._detail_summary.text(),
            "Text collections — Card #1 · Reviews completed: 3",
        )
        self.assertNotIn("Session Evidence", view._detail_summary.text())

        # 2. Selected from Quiz Completion History Table
        self.assertEqual(view._table.rowCount(), 3)
        view._table.selectRow(0)
        session_text = view._table.item(0, 0).text()
        expected_history_header = (
            f"Text collections — Card #1 · Reviews completed: 3 · Selected session: {session_text}"
        )
        self.assertEqual(view._detail_summary.text(), expected_history_header)
        self.assertNotIn("Session Evidence", view._detail_summary.text())

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

    def test_calendar_workspace_popups_and_dropdowns_theming(self) -> None:
        """Theme stylesheet includes semantic tokens for Calendar grid selected cells, dropdowns, and popups."""
        for tokens in [
            THEME_CALM_BLUE_LIGHT, THEME_CALM_BLUE_DARK,
            THEME_INDIGO_VIOLET_LIGHT, THEME_INDIGO_VIOLET_DARK,
            THEME_SAGE_TEAL_LIGHT, THEME_SAGE_TEAL_DARK,
            THEME_WARM_NEUTRAL_LIGHT, THEME_WARM_NEUTRAL_DARK,
        ]:
            stylesheet = build_stylesheet(tokens)

            # Selected Date cell in QCalendarWidget
            self.assertIn("QCalendarWidget#review-calendar-widget QTableView::item:selected", stylesheet)
            self.assertIn(f"background-color: {tokens.accent.primary.background};", stylesheet)
            self.assertIn(f"color: {tokens.accent.primary.foreground};", stylesheet)

            # Dropdown popup view
            self.assertIn("QComboBox#review-calendar-range-combo QAbstractItemView", stylesheet)
            self.assertIn("QComboBox#review-calendar-range-combo QAbstractItemView::item:selected", stylesheet)

            # Date picker popup calendar
            self.assertIn("QCalendarWidget#review-calendar-popup QTableView::item:selected", stylesheet)
            self.assertIn("QCalendarWidget#review-calendar-popup QToolButton", stylesheet)
            self.assertIn("QCalendarWidget#review-calendar-popup QMenu", stylesheet)

            # Contrast guarantee
            ratio = contrast_ratio(tokens.accent.primary.foreground, tokens.accent.primary.background)
            self.assertGreaterEqual(ratio, 4.5)

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


if __name__ == "__main__":
    unittest.main()

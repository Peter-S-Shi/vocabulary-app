from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QScrollArea

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db, quiz
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry

"""
Focused tests for M18 Phase C1 -- Review Calendar / Card History
(review_calendar_view.py Design Derivation Record). Per DESIGN.md § 2
Rule C these are structural/behavioral proof that
`ReviewCalendarController` projects the exact same authoritative
completion evidence (`get_card_learning_sessions_between_dates`,
`get_card_learning_history`) the existing Streamlit Learning History page
already reads, keeps legacy Review compatibility records visibly
separate, and never mutates SQLite -- not evidence that the P7
composition was visually realized. Native human visual acceptance is a
separate, required gate (AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.review_calendar_controller import (
        DEFAULT_RANGE_DAYS,
        ReviewCalendarController,
    )
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.review_calendar_view import ReviewCalendarView
    from src.ui_desktop.widgets.navigation_rail import NavigationRail

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m18_review_calendar.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_completed_card(self, collection_name: str, term: str, meaning: str, *, card_size: int = 8) -> tuple[int, int]:
        collection_id = create_collection(collection_name, "", card_size=card_size)
        entry_id = add_entry("French", "English", "word", term, meaning)
        add_entries_to_collection([entry_id], collection_id)
        session_id = quiz.create_quiz_session(collection_id, 1, "term_to_meaning", 1)
        quiz.record_quiz_answer(session_id, entry_id, term, meaning, meaning, True)
        quiz.mark_quiz_session_completed(session_id)
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE quiz_sessions SET completed_at = ? WHERE id = ?",
                (f"{date.today().isoformat()}T12:00:00+00:00", session_id),
            )
        return collection_id, entry_id


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class NavigationRailReviewCalendarEnabledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_review_calendar_destination_is_enabled(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)
        self.assertTrue(rail.is_enabled_destination("review_calendar"))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewCalendarControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_refresh_projects_completed_card_scoped_quiz_sessions(self) -> None:
        self._make_completed_card("Fruits", "pomme", "apple")
        controller = ReviewCalendarController()

        controller.refresh()

        self.assertEqual(len(controller.entries), 1)
        self.assertEqual(controller.entries[0]["collection_name"], "Fruits")
        self.assertEqual(controller.range_days, DEFAULT_RANGE_DAYS)

    def test_refresh_never_mutates_learning_state(self) -> None:
        """Browsing this surface must not create Card completion evidence
        or otherwise touch durable learning tables (frozen semantic
        boundary: read-only evidence browsing)."""
        self._make_completed_card("Colors", "rouge", "red")
        controller = ReviewCalendarController()

        controller.refresh()
        before = len(controller.entries)
        controller.refresh()
        after = len(controller.entries)

        self.assertEqual(before, after)

    def test_select_card_loads_history_and_legacy_logs_separately(self) -> None:
        collection_id, _entry_id = self._make_completed_card("Animals", "chat", "cat")
        controller = ReviewCalendarController()
        controller.refresh()

        controller.select_card(collection_id, 1, "Animals")

        self.assertEqual(len(controller.card_history), 1)
        self.assertEqual(controller.card_history[0]["quiz_type"], "term_to_meaning")
        # No legacy Review scheduler activity was ever created for this Card.
        self.assertEqual(controller.legacy_logs, [])

    def test_clear_selection_resets_detail_state(self) -> None:
        collection_id, _entry_id = self._make_completed_card("Numbers", "un", "one")
        controller = ReviewCalendarController()
        controller.refresh()
        controller.select_card(collection_id, 1, "Numbers")
        self.assertTrue(controller.card_history)

        controller.clear_selection()

        self.assertIsNone(controller.selected_collection_id)
        self.assertEqual(controller.card_history, [])
        self.assertEqual(controller.legacy_logs, [])

    def test_refresh_clears_selection(self) -> None:
        """Regression for an independent-review finding on this
        checkpoint: refresh() (e.g. from a range-preset change) must
        clear selection outright rather than trying to preserve it --
        this evidence surface is an event log, not a stable-entity list,
        so a stale row index could otherwise show detail from a
        different completion than the one now visually highlighted."""
        collection_id, _entry_id = self._make_completed_card("Fruits", "pomme", "apple")
        controller = ReviewCalendarController()
        controller.refresh()
        controller.select_card(collection_id, 1, "Fruits")
        self.assertIsNotNone(controller.selected_collection_id)

        controller.refresh()

        self.assertIsNone(controller.selected_collection_id)
        self.assertEqual(controller.card_history, [])

    def test_set_range_days_reloads_entries(self) -> None:
        self._make_completed_card("Weather", "pluie", "rain")
        controller = ReviewCalendarController()
        controller.refresh()
        self.assertEqual(len(controller.entries), 1)

        controller.set_range_days(7)

        self.assertEqual(controller.range_days, 7)
        self.assertEqual(len(controller.entries), 1)  # completed "now", still within 7 days

    def test_entries_outside_the_range_are_excluded(self) -> None:
        controller = ReviewCalendarController()
        controller.set_range_days(30)
        self.assertEqual(controller.entries, [])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ReviewCalendarViewStructureTests(_SyntheticDatabaseTestCase):
    """Structural-only proof (DESIGN.md § 2 Rule C)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_view_table_lists_completions_after_refresh(self) -> None:
        self._make_completed_card("Places", "ville", "city")
        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)

        view.refresh()

        self.assertEqual(view._table.rowCount(), 1)

    def test_pre_m11_3_completion_without_card_identity_remains_browseable(self) -> None:
        self._make_completed_card("Legacy Evidence", "ancien", "old")
        with db.get_connection() as conn:
            session_id = int(
                conn.execute(
                    "SELECT id FROM quiz_sessions ORDER BY id DESC LIMIT 1"
                ).fetchone()[0]
            )
            conn.execute(
                """
                UPDATE quiz_sessions
                SET card_id = NULL, card_revision_id = NULL
                WHERE id = ?
                """,
                (session_id,),
            )
        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)

        view.refresh()
        view._table.selectRow(0)

        self.assertEqual(view._table.rowCount(), 1)
        self.assertIsNone(controller.selected_card_id)
        self.assertIsNone(controller.current_schedule)
        self.assertEqual(
            [entry["session_id"] for entry in controller.card_history],
            [session_id],
        )

    def test_selecting_a_row_populates_the_history_table(self) -> None:
        self._make_completed_card("Shapes", "carre", "square")
        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        view._table.selectRow(0)

        self.assertEqual(view._history_table.rowCount(), 1)
        self.assertIn("Shapes", view._detail_summary.text())

    def test_row_selection_and_detail_do_not_go_stale_after_a_range_change(self) -> None:
        """Regression for an independent-review finding: selecting row 0
        then triggering a refresh (range-preset change) must not leave
        row 0 visually highlighted with detail data left over from a
        completion that may no longer even be at that index."""
        self._make_completed_card("Fruits", "pomme", "apple")
        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        view._table.selectRow(0)
        self.assertIn("Fruits", view._detail_summary.text())

        self._make_completed_card("Colors", "rouge", "red")
        controller.refresh()

        self.assertEqual(len(view._table.selectedItems()), 0)
        self.assertEqual(
            view._detail_summary.text(), "Select a completion above to see its Card's full history."
        )

    def test_page_and_each_table_remain_scrollable_with_large_results_in_a_short_window(self) -> None:
        controller = ReviewCalendarController()
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)

        tables = (view._schedule_table, view._table, view._history_table, view._legacy_table)
        for table in tables:
            table.setRowCount(40)

        view.resize(640, 420)
        view.show()
        self.app.processEvents()
        self.app.processEvents()

        page_scroll = view.findChild(QScrollArea, "review-calendar-scroll")
        self.assertIsNotNone(page_scroll)
        self.assertGreater(page_scroll.verticalScrollBar().maximum(), 0)
        for table in tables:
            with self.subTest(table=table.objectName()):
                self.assertEqual(
                    table.verticalScrollBarPolicy(),
                    Qt.ScrollBarPolicy.ScrollBarAsNeeded,
                )
                self.assertEqual(
                    table.horizontalScrollBarPolicy(),
                    Qt.ScrollBarPolicy.ScrollBarAsNeeded,
                )
                self.assertGreater(table.verticalScrollBar().maximum(), 0)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18ReviewCalendarTokenQssStructuralCoverageTests(unittest.TestCase):
    """Every new control's object-name selector must be themed -- checked
    once per Appearance, per the Human Gate 1 corrective lesson that an
    unstyled workspace-level control silently loses its palette
    foreground under the global stylesheet."""

    REPRESENTATIVE_SELECTORS = (
        "#review-calendar-title",
        "#review-calendar-range-label",
        "#review-calendar-range-combo",
        "#review-calendar-detail-heading",
        "#review-calendar-detail-summary",
        "#review-calendar-legacy-heading",
        "#review-calendar-legacy-caption",
    )

    def _assert_all_selectors_present(self, tokens) -> None:
        stylesheet = build_stylesheet(tokens)
        for selector in self.REPRESENTATIVE_SELECTORS:
            self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")

    def test_light_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_LIGHT)

    def test_dark_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_DARK)


if __name__ == "__main__":
    unittest.main()

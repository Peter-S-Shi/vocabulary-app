from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
import tempfile

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QLabel
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from src import db, quiz
from src.app_config import get_app_icon_path
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry
from src.entry_templates import create_entry_template
from src.review_schedule import set_card_next_review
from src.time_utils import format_local_timestamp, is_pure_date, utc_to_local_datetime
from src.ui_desktop.app import WINDOWS_APP_USER_MODEL_ID, build_application, configure_windows_identity
from src.ui_desktop.controllers.entries_controller import EntriesController
from src.ui_desktop.controllers.review_calendar_controller import ReviewCalendarController
from src.ui_desktop.controllers.review_controller import ReviewController
from src.ui_desktop.controllers.templates_controller import TemplatesController
from src.ui_desktop.qt_models.entries_table_model import EntriesTableModel
from src.ui_desktop.views.review_calendar_view import ReviewCalendarView
from src.ui_desktop.views.review_view import ReviewView
from src.ui_desktop.views.templates_view import TemplatesView


class V11PhaseCTimeUtilsUnitTests(unittest.TestCase):
    """Unit tests for src.time_utils timestamp vs pure date parsing and formatting."""

    def test_pure_date_detection(self) -> None:
        self.assertTrue(is_pure_date("2026-08-27"))
        self.assertTrue(is_pure_date("  2026-12-31  "))
        self.assertFalse(is_pure_date("2026-08-27T13:45:00Z"))
        self.assertFalse(is_pure_date("2026-08-27 13:45:00"))
        self.assertFalse(is_pure_date(""))
        self.assertFalse(is_pure_date("not-a-date"))

    def test_pure_date_formatting_never_shifts_timezone(self) -> None:
        self.assertEqual(format_local_timestamp("2026-08-27"), "2026-08-27")
        self.assertEqual(format_local_timestamp("2026-01-01"), "2026-01-01")

    def test_empty_or_none_timestamps(self) -> None:
        self.assertEqual(format_local_timestamp(""), "")
        self.assertEqual(format_local_timestamp(None), "")
        self.assertEqual(format_local_timestamp(None, empty_placeholder="N/A"), "N/A")

    def test_utc_to_local_datetime_conversion(self) -> None:
        utc_dt = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
        expected_local = utc_dt.astimezone()
        expected_str = expected_local.strftime("%Y-%m-%d %H:%M:%S")

        # Test ISO string with +00:00
        self.assertEqual(format_local_timestamp("2026-08-27T12:00:00+00:00"), expected_str)
        # Test ISO string with Z
        self.assertEqual(format_local_timestamp("2026-08-27T12:00:00Z"), expected_str)
        # Test SQLite format without T (assumed UTC)
        self.assertEqual(format_local_timestamp("2026-08-27 12:00:00"), expected_str)
        # Test datetime object
        self.assertEqual(format_local_timestamp(utc_dt), expected_str)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class V11PhaseCDesktopUiLocalTimeTests(unittest.TestCase):
    """Verify that all desktop UI surfaces present timestamps in local time while
    preserving pure calendar dates unaltered."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._temp_dir.cleanup)
        db.DB_PATH = Path(self._temp_dir.name) / "test.sqlite3"
        db.init_db()

    def test_review_calendar_displays_local_timestamp_and_pure_date(self) -> None:
        col_id = create_collection("TimeCol", "desc", card_size=8)
        entry_id = add_entry("English", "English", "word", "ephemeral", "transitory", "example")
        add_entries_to_collection([entry_id], col_id)

        # 1. Complete a quiz to generate completed_at timestamp
        session_id = quiz.create_quiz_session(col_id, 1, "term_to_meaning", 1)
        quiz.record_quiz_answer(session_id, entry_id, "ephemeral", "transitory", "transitory", True)
        quiz.mark_quiz_session_completed(session_id)

        # 2. Set next due date (pure date)
        with db.get_connection() as conn:
            card_id = conn.execute("SELECT id FROM cards WHERE collection_id = ? AND card_number = 1", (col_id,)).fetchone()[0]
        set_card_next_review(card_id, "2026-09-15")

        controller = ReviewCalendarController()
        controller.set_selected_date("2026-09-15")
        view = ReviewCalendarView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        # Assert completions table (Column 0 is completed_at)
        self.assertGreaterEqual(view._table.rowCount(), 1)
        completed_at_text = view._table.item(0, 0).text()
        self.assertTrue(len(completed_at_text) >= 16)
        # Ensure it contains spaces (YYYY-MM-DD HH:MM:SS) rather than raw ISO 'T' or '+00:00'
        self.assertNotIn("T", completed_at_text)
        self.assertNotIn("+00:00", completed_at_text)

        # Assert schedule table (Column 3 is next_due_at, pure date)
        self.assertGreaterEqual(view._schedule_table.rowCount(), 1)
        next_due_text = view._schedule_table.item(0, 3).text()
        self.assertEqual(next_due_text, "2026-09-15")

    def test_entries_table_model_displays_updated_at_in_local_time(self) -> None:
        add_entry("English", "English", "word", "serendipity", "happy accident", "example")
        controller = EntriesController()
        controller.refresh()
        model = controller.model

        updated_col = model.COLUMNS.index("updated_at")
        updated_text = model.data(model.index(0, updated_col), Qt.ItemDataRole.DisplayRole)
        self.assertTrue(len(updated_text) >= 16)
        self.assertNotIn("T", updated_text)
        self.assertNotIn("+00:00", updated_text)

    def test_templates_view_displays_updated_at_in_local_time(self) -> None:
        create_entry_template("CustomVocab", description="desc", language="English")
        controller = TemplatesController()
        controller.refresh()
        view = TemplatesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        self.assertGreaterEqual(view._table.rowCount(), 1)
        # Column 5 is updated_at
        updated_text = view._table.item(0, 5).text()
        self.assertTrue(len(updated_text) >= 16)
        self.assertNotIn("T", updated_text)
        self.assertNotIn("+00:00", updated_text)

    def test_review_view_drawer_history_displays_local_time(self) -> None:
        col_id = create_collection("HistoryCol", "desc", card_size=8)
        entry_id = add_entry("English", "English", "word", "ubiquitous", "omnipresent", "example")
        add_entries_to_collection([entry_id], col_id)

        session_id = quiz.create_quiz_session(col_id, 1, "term_to_meaning", 1)
        quiz.record_quiz_answer(session_id, entry_id, "ubiquitous", "omnipresent", "omnipresent", True)
        quiz.mark_quiz_session_completed(session_id)

        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        controller.open_card(col_id, 1)

        view._toggle_drawer(True)
        labels = view.findChildren(QLabel, "review-drawer-history-row")
        self.assertGreaterEqual(len(labels), 1)
        history_text = labels[0].text()
        self.assertNotIn("T", history_text)
        self.assertNotIn("+00:00", history_text)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class V11PhaseCWindowsIdentityTests(unittest.TestCase):
    """Verify Windows AppUserModelID, application metadata, and icon integrity."""

    def test_windows_identity_configuration(self) -> None:
        # configure_windows_identity handles win32 safely without crashing on other OS
        result = configure_windows_identity()
        self.assertIsInstance(result, bool)

    def test_application_metadata_and_aumid(self) -> None:
        app, window, theme_manager = build_application([])
        self.addCleanup(window.deleteLater)

        self.assertEqual(app.applicationName(), "Vocabulary App")
        self.assertEqual(app.applicationDisplayName(), "Vocabulary App")
        self.assertEqual(WINDOWS_APP_USER_MODEL_ID, "PeterShi.VocabularyApp.Desktop")
        self.assertEqual(app.desktopFileName(), WINDOWS_APP_USER_MODEL_ID)
        self.assertEqual(app.organizationName(), "PeterShi")
        self.assertEqual(app.organizationDomain(), "github.com/Peter-S-Shi")
        # Invariant: AUMID must be version-agnostic to preserve pinned shortcuts across upgrades
        self.assertNotIn("1.1", WINDOWS_APP_USER_MODEL_ID)
        self.assertNotIn("v1", WINDOWS_APP_USER_MODEL_ID)

    def test_multi_resolution_app_icon_asset(self) -> None:
        icon_path = get_app_icon_path()
        self.assertTrue(icon_path.is_file(), f"Icon not found at {icon_path}")

        icon = QIcon(str(icon_path))
        sizes = [f"{s.width()}x{s.height()}" for s in icon.availableSizes()]
        # Verify standard Windows resolutions are available
        self.assertIn("16x16", sizes)
        self.assertIn("24x24", sizes)
        self.assertIn("32x32", sizes)
        self.assertIn("48x48", sizes)
        self.assertIn("64x64", sizes)
        self.assertIn("128x128", sizes)
        self.assertIn("256x256", sizes)

    def test_inno_setup_app_user_model_id_and_app_id(self) -> None:
        inno_iss_path = Path(__file__).resolve().parent.parent / "winbuild" / "inno_setup.iss"
        self.assertTrue(inno_iss_path.is_file(), f"inno_setup.iss not found at {inno_iss_path}")
        content = inno_iss_path.read_text(encoding="utf-8")

        # 1. Inno AppId remains frozen for upgrade tracking
        self.assertIn("AppId={{6C6F9E2A-6E3A-4C9F-9E8E-6B9C6E9A6F3D}}", content)
        # 2. Stable AppUserModelID is defined and matches runtime AUMID
        self.assertIn(f'#define AppUserModelID "{WINDOWS_APP_USER_MODEL_ID}"', content)
        # 3. [Icons] definitions carry AppUserModelID parameter for Start Menu & Desktop
        self.assertIn('Name: "{group}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"; AppUserModelID: "{#AppUserModelID}"', content)
        self.assertIn('Name: "{autodesktop}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"; Tasks: desktopicon; AppUserModelID: "{#AppUserModelID}"', content)

    def test_dev_launcher_shortcut_aumid_attachment(self) -> None:
        from tools.setup_desktop_launcher import set_shortcut_app_user_model_id, create_shortcut
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dummy_target = tmp_path / "pythonw.exe"
            dummy_target.write_text("")
            dummy_icon = tmp_path / "app.ico"
            dummy_icon.write_text("")

            # Test set_shortcut_app_user_model_id handles invalid / test paths safely
            result = set_shortcut_app_user_model_id(tmp_path / "nonexistent.lnk", WINDOWS_APP_USER_MODEL_ID)
            self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()

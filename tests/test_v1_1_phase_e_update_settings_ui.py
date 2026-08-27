from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication

from src.app_config import APP_VERSION
from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.main_window import MainWindow
from src.ui_desktop.state.preferences import Preferences
from src.ui_desktop.views.settings_view import SettingsView
from src.ui_desktop.widgets.navigation_rail import NavigationRail
from src.update_checker import (
    PYSIDE6_AVAILABLE,
    UpdateAwarenessService,
    UpdateCheckResult,
    UpdateCheckState,
)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is required for UI tests.")
class SettingsControllerUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_controller_initial_update_state(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        controller = SettingsController(update_service=service)
        result = controller.update_result()
        self.assertEqual(result.state, UpdateCheckState.NOT_CHECKED)
        self.assertEqual(result.current_version, "1.0.0")
        self.assertFalse(controller.is_checking_updates())

    def test_controller_manual_check_triggers_service_and_signal(self) -> None:
        payload = [
            {
                "tag_name": "v1.2.0",
                "name": "Vocabulary App v1.2.0",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0",
            }
        ]

        def fake_fetcher(url: str, timeout: float):
            return 200, json.dumps(payload).encode("utf-8"), {}

        service = UpdateAwarenessService(current_version="1.0.0", fetcher=fake_fetcher)
        controller = SettingsController(update_service=service)

        emitted_results: list[UpdateCheckResult] = []
        controller.update_status_changed.connect(emitted_results.append)

        controller.check_for_updates()
        if service._active_worker is not None:
            service._active_worker.wait(2000)
        QApplication.processEvents()

        self.assertGreaterEqual(len(emitted_results), 1)
        final_result = controller.update_result()
        self.assertEqual(final_result.state, UpdateCheckState.UPDATE_AVAILABLE)
        self.assertEqual(final_result.latest_version, "1.2.0")
        self.assertEqual(final_result.release_url, "https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0")

    @patch("PySide6.QtGui.QDesktopServices.openUrl")
    def test_controller_open_latest_release_page_success(self, mock_open_url: MagicMock) -> None:
        mock_open_url.return_value = True
        service = UpdateAwarenessService(current_version="1.0.0")
        # Pre-seed update available result
        service._current_result = UpdateCheckResult(
            state=UpdateCheckState.UPDATE_AVAILABLE,
            current_version="1.0.0",
            latest_version="1.2.0",
            release_url="https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0",
        )
        controller = SettingsController(update_service=service)

        opened = controller.open_latest_release_page()
        self.assertTrue(opened)
        mock_open_url.assert_called_once_with(QUrl("https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0"))

    @patch("PySide6.QtGui.QDesktopServices.openUrl")
    def test_controller_open_latest_release_page_no_url(self, mock_open_url: MagicMock) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        service._current_result = UpdateCheckResult(
            state=UpdateCheckState.UP_TO_DATE,
            current_version="1.0.0",
            release_url=None,
        )
        controller = SettingsController(update_service=service)

        opened = controller.open_latest_release_page()
        self.assertFalse(opened)
        mock_open_url.assert_not_called()

    def test_controller_shutdown_delegates_to_service(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        controller = SettingsController(update_service=service)
        completed = controller.shutdown(wait_ms=100)
        self.assertTrue(completed)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is required for UI tests.")
class SettingsViewUpdateSectionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_view_ui_state_not_checked(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        controller = SettingsController(update_service=service)
        view = SettingsView(controller)

        self.assertIn("v1.0.0", view._update_version_label.text())
        self.assertEqual(view._update_check_btn.text(), "Check for Updates")
        self.assertTrue(view._update_check_btn.isEnabled())
        self.assertTrue(view._update_state_badge.isHidden())
        self.assertTrue(view._update_release_btn.isHidden())
        self.assertIn("not been checked", view._update_status_label.text().lower())

    def test_settings_view_ui_state_checking(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        service._current_result = UpdateCheckResult(
            state=UpdateCheckState.CHECKING,
            current_version="1.0.0",
        )
        controller = SettingsController(update_service=service)
        view = SettingsView(controller)

        self.assertEqual(view._update_check_btn.text(), "Checking...")
        self.assertFalse(view._update_check_btn.isEnabled())
        self.assertTrue(view._update_state_badge.isHidden())
        self.assertTrue(view._update_release_btn.isHidden())
        self.assertIn("checking github", view._update_status_label.text().lower())

    def test_settings_view_ui_state_up_to_date(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        service._current_result = UpdateCheckResult(
            state=UpdateCheckState.UP_TO_DATE,
            current_version="1.0.0",
            latest_version="1.0.0",
        )
        controller = SettingsController(update_service=service)
        view = SettingsView(controller)

        self.assertEqual(view._update_check_btn.text(), "Check Again")
        self.assertTrue(view._update_check_btn.isEnabled())
        self.assertFalse(view._update_state_badge.isHidden())
        self.assertEqual(view._update_state_badge.text(), "Up to Date")
        self.assertTrue(view._update_release_btn.isHidden())
        self.assertIn("up to date", view._update_status_label.text().lower())

    def test_settings_view_ui_state_update_available(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        service._current_result = UpdateCheckResult(
            state=UpdateCheckState.UPDATE_AVAILABLE,
            current_version="1.0.0",
            latest_version="1.2.0",
            release_url="https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0",
            published_at="2026-08-27T10:00:00Z",
        )
        controller = SettingsController(update_service=service)
        view = SettingsView(controller)

        self.assertEqual(view._update_check_btn.text(), "Check Again")
        self.assertTrue(view._update_check_btn.isEnabled())
        self.assertFalse(view._update_state_badge.isHidden())
        self.assertEqual(view._update_state_badge.text(), "Update Available: v1.2.0")
        self.assertFalse(view._update_release_btn.isHidden())
        self.assertTrue(view._update_release_btn.isEnabled())
        self.assertEqual(view._update_release_btn.text(), "View Release")
        self.assertIn("v1.2.0", view._update_status_label.text())

    def test_settings_view_ui_state_check_failed_reassures_offline_learning(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        service._current_result = UpdateCheckResult(
            state=UpdateCheckState.CHECK_FAILED,
            current_version="1.0.0",
            error_message="Network connection timeout.",
        )
        controller = SettingsController(update_service=service)
        view = SettingsView(controller)

        self.assertEqual(view._update_check_btn.text(), "Check Again")
        self.assertTrue(view._update_check_btn.isEnabled())
        self.assertFalse(view._update_state_badge.isHidden())
        self.assertEqual(view._update_state_badge.text(), "Check Failed")
        self.assertTrue(view._update_release_btn.isHidden())
        # Crucial reassurance: failure must not sound alarming and must clarify normal offline operation
        status_text = view._update_status_label.text()
        self.assertIn("Unable to check for updates", status_text)
        self.assertIn("Offline study and all local features continue to work normally", status_text)

    def test_settings_view_check_button_click_triggers_check(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        controller = SettingsController(update_service=service)
        view = SettingsView(controller)

        with patch.object(controller, "check_for_updates") as mock_check:
            view._update_check_btn.click()
            mock_check.assert_called_once()

    def test_settings_view_release_button_click_triggers_open_release(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        service._current_result = UpdateCheckResult(
            state=UpdateCheckState.UPDATE_AVAILABLE,
            current_version="1.0.0",
            latest_version="1.2.0",
            release_url="https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0",
        )
        controller = SettingsController(update_service=service)
        view = SettingsView(controller)

        with patch.object(controller, "open_latest_release_page") as mock_open:
            view._update_release_btn.click()
            mock_open.assert_called_once()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is required for UI tests.")
class NavigationRailAndMainWindowUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_navigation_rail_update_indicator(self) -> None:
        rail = NavigationRail()
        settings_button = rail._buttons["settings"]
        settings_mark = rail._marks["settings"]

        # Default state: no update
        self.assertEqual(settings_button.toolTip(), "")
        self.assertFalse(settings_mark.property("hasUpdate"))

        # Update available
        rail.set_update_available(True)
        self.assertEqual(settings_button.toolTip(), "Settings (Update Available)")
        self.assertTrue(settings_mark.property("hasUpdate"))

        # Clear update available
        rail.set_update_available(False)
        self.assertEqual(settings_button.toolTip(), "")
        self.assertFalse(settings_mark.property("hasUpdate"))

    def test_main_window_startup_and_update_signal_wiring(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")

        # Mock check_for_updates during MainWindow init to prevent live worker thread in test
        with patch.object(UpdateAwarenessService, "check_for_updates"):
            window = MainWindow()
            window.settings_controller._update_service = service
            service.state_changed.connect(window.settings_controller._on_update_service_state_changed)

            # Simulate update available arriving from background check
            service._current_result = UpdateCheckResult(
                state=UpdateCheckState.UPDATE_AVAILABLE,
                current_version="1.0.0",
                latest_version="1.3.0",
                release_url="https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.3.0",
            )
            service.state_changed.emit(service._current_result)
            QApplication.processEvents()

            # Navigation rail should reflect update available
            self.assertEqual(window._navigation_rail._buttons["settings"].toolTip(), "Settings (Update Available)")

            # Close event should safely shutdown update workers
            with patch.object(window.settings_controller, "shutdown") as mock_shutdown:
                window.close()
                mock_shutdown.assert_called_once()


if __name__ == "__main__":
    unittest.main()

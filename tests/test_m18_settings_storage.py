from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src.app_config import get_app_storage_summary

"""
Focused tests for M18 Phase C2 -- Settings Storage information
(settings_view.py Design Derivation trace addendum). Per DESIGN.md § 2
Rule C these are structural/behavioral proof that
`SettingsController.storage_summary()` is a thin passthrough to the same
`src.app_config.get_app_storage_summary()` the Streamlit Settings/Data
page already reads, and that the new rows render read-only -- not
evidence the P8 composition was visually realized.
"""

if PYSIDE6_AVAILABLE:
    from PySide6.QtWidgets import QComboBox, QLabel

    from src.ui_desktop.controllers.settings_controller import SettingsController
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.settings_view import SettingsView

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsControllerStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_storage_summary_matches_app_config_directly(self) -> None:
        controller = SettingsController()

        summary = controller.storage_summary()

        self.assertEqual(summary, get_app_storage_summary())

    def test_storage_summary_contains_expected_keys(self) -> None:
        controller = SettingsController()

        summary = controller.storage_summary()

        for key in (
            "app_version",
            "database_path",
            "data_directory",
            "backup_directory",
            "audio_cache_directory",
            "path_source",
            "database_exists",
        ):
            self.assertIn(key, summary)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsViewStorageStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_view_renders_a_row_per_storage_field_read_only(self) -> None:
        controller = SettingsController()
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        value_labels = view.findChildren(QLabel, "settings-row-value")
        self.assertEqual(len(value_labels), 7)
        rendered_values = {label.text() for label in value_labels}
        summary = controller.storage_summary()
        self.assertIn(str(summary["database_path"]), rendered_values)
        self.assertIn(str(summary["app_version"]), rendered_values)

        # Storage rows are informational only -- no editable combo exists
        # for any of them (unlike Appearance/Quiz presentation).
        combos = view.findChildren(QComboBox)
        self.assertEqual(len(combos), 2)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18SettingsTokenQssStructuralCoverageTests(unittest.TestCase):
    def _assert_selector_present(self, tokens) -> None:
        stylesheet = build_stylesheet(tokens)
        self.assertIn("#settings-row-value", stylesheet)

    def test_light_calm_blue_covers_settings_row_value(self) -> None:
        self._assert_selector_present(THEME_CALM_BLUE_LIGHT)

    def test_dark_calm_blue_covers_settings_row_value(self) -> None:
        self._assert_selector_present(THEME_CALM_BLUE_DARK)


if __name__ == "__main__":
    unittest.main()

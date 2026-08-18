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
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox, QLabel, QScrollArea

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
        # 7 read-only Storage rows + the 2 M19 Audio rows (shared TTS
        # runtime folder value, effective runtime-in-use source).
        self.assertEqual(len(value_labels), 9)
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
    REPRESENTATIVE_SELECTORS = ("#settings-row-value", "#settings-scroll")

    def _assert_selectors_present(self, tokens) -> None:
        stylesheet = build_stylesheet(tokens)
        for selector in self.REPRESENTATIVE_SELECTORS:
            self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")

    def test_light_calm_blue_covers_settings_row_value(self) -> None:
        self._assert_selectors_present(THEME_CALM_BLUE_LIGHT)

    def test_dark_calm_blue_covers_settings_row_value(self) -> None:
        self._assert_selectors_present(THEME_CALM_BLUE_DARK)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsScrollAreaTests(unittest.TestCase):
    """Human Gate 2 corrective: the Settings page's content lives inside a
    native vertical QScrollArea (so a growing Storage section scrolls
    instead of compressing the Appearance/Quiz combos), never horizontal."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_content_is_wrapped_in_a_resizable_vertical_only_scroll_area(self) -> None:
        controller = SettingsController()
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        scroll = view.findChild(QScrollArea, "settings-scroll")
        self.assertIsNotNone(scroll)
        self.assertTrue(scroll.widgetResizable())
        self.assertEqual(scroll.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertIsNotNone(scroll.widget())

    def test_appearance_and_quiz_combos_keep_their_natural_width_when_the_window_is_narrow(self) -> None:
        """Regression for the Human Gate 2 layout defect: at a real
        production window size the combos were compressed/clipped. A
        narrow-width min-width workaround was tried and reverted in favor
        of this scroll area, which removes the pressure that caused the
        squeeze in the first place -- confirmed here by forcing a width
        far narrower than any realistic desktop window and checking the
        combos are never squeezed below their natural size hint."""
        controller = SettingsController()
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        # Independent-review finding (M18 Phase E self-review): sizeHint()
        # on a combo that has never been shown/polished can be affected by
        # whatever global style/font-metric caching state the rest of the
        # process happens to be in at that exact moment -- observed to
        # intermittently under-report width once enough other GUI tests
        # ran earlier in the same `unittest discover` process. Showing the
        # view at a comfortably wide size first (matching how ``width()``
        # below is itself measured, after show()+processEvents()) makes
        # "natural width" a real post-layout measurement instead of a
        # pre-show guess, while still exercising the same regression this
        # test guards: at that width nothing is squeezing the combos.
        view.resize(1280, 800)
        view.show()
        self.app.processEvents()
        self.app.processEvents()
        natural_appearance_width = view._appearance_combo.width()
        natural_quiz_width = view._quiz_presentation_combo.width()

        view.resize(400, 800)
        self.app.processEvents()
        self.app.processEvents()

        self.assertEqual(view._appearance_combo.width(), natural_appearance_width)
        self.assertEqual(view._quiz_presentation_combo.width(), natural_quiz_width)

    def test_a_short_window_shows_a_vertical_scrollbar_not_a_horizontal_one(self) -> None:
        controller = SettingsController()
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)
        scroll = view.findChild(QScrollArea, "settings-scroll")

        view.resize(1280, 300)
        view.show()
        self.app.processEvents()
        self.app.processEvents()

        self.assertTrue(scroll.verticalScrollBar().isVisible())
        self.assertFalse(scroll.horizontalScrollBar().isVisible())


if __name__ == "__main__":
    unittest.main()

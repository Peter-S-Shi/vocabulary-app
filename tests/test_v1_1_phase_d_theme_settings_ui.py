from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.state.preferences import Preferences, save_preferences
from src.ui_desktop.theming.theme_manager import Accent, Appearance, ThemeManager
from src.ui_desktop.theming.tokens import (
    CustomThemeConfig,
    ModeCustomization,
    PRESET_CALM_BLUE,
    PRESET_INDIGO_VIOLET,
    PRESET_SAGE_TEAL,
    PRESET_WARM_NEUTRAL,
)
from src.ui_desktop.views.settings_view import SettingsView


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ThemeSettingsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.pref_file = Path(self.tmp_dir.name) / "preferences.json"
        self.prefs = Preferences(
            appearance="System",
            accent="Calm Blue",
            custom_theme=CustomThemeConfig(
                light=ModeCustomization(preset=PRESET_CALM_BLUE),
                dark=ModeCustomization(preset=PRESET_CALM_BLUE),
            ),
        )
        save_preferences(self.prefs, self.pref_file)

        self.theme_manager = ThemeManager(self.app)
        self.controller = SettingsController(self.prefs, self.theme_manager)
        self.view = SettingsView(self.controller)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_settings_view_structure_and_tabs(self) -> None:
        self.assertEqual(self.view._theme_tabs.count(), 2)
        self.assertEqual(self.view._theme_tabs.tabText(0), "Light Mode")
        self.assertEqual(self.view._theme_tabs.tabText(1), "Dark Mode")

        self.assertIn("Light", self.view._preset_combos)
        self.assertIn("Dark", self.view._preset_combos)
        self.assertIn("Light", self.view._accent_swatches)
        self.assertIn("Dark", self.view._accent_swatches)

        # Initial button states
        self.assertFalse(self.view._theme_apply_btn.isEnabled())
        self.assertFalse(self.view._theme_cancel_btn.isEnabled())
        self.assertFalse(self.view._theme_undo_btn.isEnabled())

    def test_tab_switching_triggers_live_preview_without_mutating_stored_appearance(self) -> None:
        self.assertEqual(self.controller.appearance(), "System")

        # Switch to Dark tab (index 1)
        self.view._theme_tabs.setCurrentIndex(1)
        self.assertEqual(self.view._get_active_tab_mode(), "Dark")
        self.assertEqual(self.controller.appearance(), "System")  # Invariant: stored appearance unchanged

        # Switch to Light tab (index 0)
        self.view._theme_tabs.setCurrentIndex(0)
        self.assertEqual(self.view._get_active_tab_mode(), "Light")
        self.assertEqual(self.controller.appearance(), "System")  # Invariant: stored appearance unchanged

    def test_preset_change_stages_live_preview_and_enables_apply(self) -> None:
        # Change Light Mode preset to Sage / Teal
        combo = self.view._preset_combos["Light"]
        idx = combo.findData(PRESET_SAGE_TEAL)
        self.assertGreaterEqual(idx, 0)
        combo.setCurrentIndex(idx)

        # Staged config updated
        staged = self.controller.staged_custom_theme()
        self.assertEqual(staged.light.preset, PRESET_SAGE_TEAL)
        self.assertTrue(self.controller.is_staged_dirty())
        self.assertTrue(self.view._theme_apply_btn.isEnabled())
        self.assertTrue(self.view._theme_cancel_btn.isEnabled())

        # Live tokens previewed
        self.assertEqual(self.theme_manager.current_tokens.accent.primary.background, "#4B7767")

    def test_cancel_reverts_staged_preview_to_persisted_state(self) -> None:
        # Stage a custom accent color
        custom_light = ModeCustomization(preset=PRESET_CALM_BLUE, accent_color="#2E7D32")
        self.controller.stage_mode_customization("Light", custom_light)
        self.assertTrue(self.controller.is_staged_dirty())
        self.assertEqual(self.theme_manager.current_tokens.accent.primary.background, "#2E7D32")

        # Click Cancel
        self.view._theme_cancel_btn.click()
        self.assertFalse(self.controller.is_staged_dirty())
        self.assertFalse(self.view._theme_apply_btn.isEnabled())
        self.assertIsNone(self.controller.custom_theme().light.accent_color)

    def test_apply_commits_changes_and_records_undo_snapshot(self) -> None:
        # Stage Warm Neutral with custom background
        custom_light = ModeCustomization(
            preset=PRESET_WARM_NEUTRAL,
            background_color="#FAF8F5",
        )
        self.controller.stage_mode_customization("Light", custom_light)

        # Click Apply
        self.view._theme_apply_btn.click()
        self.assertFalse(self.controller.is_staged_dirty())
        self.assertTrue(self.controller.can_undo())
        self.assertTrue(self.view._theme_undo_btn.isEnabled())

        # Persisted in controller preferences
        self.assertEqual(self.controller.custom_theme().light.preset, PRESET_WARM_NEUTRAL)
        self.assertEqual(self.controller.custom_theme().light.background_color, "#FAF8F5")

    def test_undo_restores_complete_previous_theme_snapshot(self) -> None:
        # 1. Start at Calm Blue baseline
        self.assertEqual(self.controller.custom_theme().light.preset, PRESET_CALM_BLUE)

        # 2. Apply change 1: Sage / Teal
        self.controller.stage_mode_customization(
            "Light",
            ModeCustomization(preset=PRESET_SAGE_TEAL, accent_color="#2E7D32"),
        )
        self.controller.apply_staged_custom_theme()
        self.assertEqual(self.controller.custom_theme().light.preset, PRESET_SAGE_TEAL)

        # 3. Apply change 2: Indigo / Violet
        self.controller.stage_mode_customization(
            "Light",
            ModeCustomization(preset=PRESET_INDIGO_VIOLET, accent_color="#5C5C9B"),
        )
        self.controller.apply_staged_custom_theme()
        self.assertEqual(self.controller.custom_theme().light.preset, PRESET_INDIGO_VIOLET)

        # 4. Click Undo -> restores change 1 (Sage / Teal with #2E7D32)
        self.view._theme_undo_btn.click()
        self.assertEqual(self.controller.custom_theme().light.preset, PRESET_SAGE_TEAL)
        self.assertEqual(self.controller.custom_theme().light.accent_color, "#2E7D32")

        # 5. Click Undo again -> restores initial baseline (Calm Blue)
        self.view._theme_undo_btn.click()
        self.assertEqual(self.controller.custom_theme().light.preset, PRESET_CALM_BLUE)
        self.assertIsNone(self.controller.custom_theme().light.accent_color)
        self.assertFalse(self.controller.can_undo())

    def test_reset_to_preset_clears_active_mode_custom_colors(self) -> None:
        # Set Light Mode to Sage / Teal with custom accent and surface
        self.controller.stage_mode_customization(
            "Light",
            ModeCustomization(
                preset=PRESET_SAGE_TEAL,
                accent_color="#FF0000",
                surface_color="#EEEEEE",
            ),
        )
        self.view._theme_tabs.setCurrentIndex(0)

        # Click Reset to Preset
        self.view._theme_reset_mode_btn.click()
        staged = self.controller.staged_custom_theme()
        self.assertEqual(staged.light.preset, PRESET_SAGE_TEAL)
        self.assertIsNone(staged.light.accent_color)
        self.assertIsNone(staged.light.surface_color)

    def test_reset_all_to_default_clears_both_modes(self) -> None:
        self.controller.stage_mode_customization(
            "Light",
            ModeCustomization(preset=PRESET_WARM_NEUTRAL, accent_color="#111111"),
        )
        self.controller.stage_mode_customization(
            "Dark",
            ModeCustomization(preset=PRESET_INDIGO_VIOLET, accent_color="#222222"),
        )

        # Click Reset All to Default
        self.view._theme_reset_all_btn.click()
        staged = self.controller.staged_custom_theme()
        self.assertEqual(staged.light.preset, PRESET_CALM_BLUE)
        self.assertEqual(staged.dark.preset, PRESET_CALM_BLUE)
        self.assertIsNone(staged.light.accent_color)
        self.assertIsNone(staged.dark.accent_color)


if __name__ == "__main__":
    unittest.main()

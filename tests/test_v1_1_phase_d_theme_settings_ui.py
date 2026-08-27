from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QColorDialog
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.state.preferences import Preferences, load_preferences, save_preferences
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

        # Patch get_app_preferences_path to strictly guarantee no test touches real user files
        self._patcher = patch(
            "src.ui_desktop.state.preferences.get_app_preferences_path",
            return_value=self.pref_file,
        )
        self._patcher.start()

        self.theme_manager = ThemeManager(self.app)
        self.theme_manager.apply_preferences(self.prefs)
        self.controller = SettingsController(
            self.prefs,
            self.theme_manager,
            preferences_path=self.pref_file,
        )
        self.view = SettingsView(self.controller)

    def tearDown(self) -> None:
        self._patcher.stop()
        self.tmp_dir.cleanup()

    def test_settings_controller_constructor_and_imports_compatibility(self) -> None:
        ctrl_default = SettingsController()
        self.assertIsInstance(ctrl_default.preferences, Preferences)
        self.assertIsNone(ctrl_default.preferences_path)

        ctrl_path = SettingsController(
            preferences=self.prefs,
            theme_manager=self.theme_manager,
            preferences_path=self.pref_file,
        )
        self.assertEqual(ctrl_path.preferences_path, self.pref_file)

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
        self.assertIn("Cancelled", self.view._theme_feedback_label.text())

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
        self.assertIn("applied", self.view._theme_feedback_label.text().lower())

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
        self.assertIn("Restored", self.view._theme_feedback_label.text())

        # 5. Click Undo again -> restores initial baseline (Calm Blue)
        self.view._theme_undo_btn.click()
        self.assertEqual(self.controller.custom_theme().light.preset, PRESET_CALM_BLUE)
        self.assertIsNone(self.controller.custom_theme().light.accent_color)
        self.assertFalse(self.controller.can_undo())

    def test_staged_reset_undo_does_not_mutate_committed_preferences_or_disk(self) -> None:
        # Initial committed state: Calm Blue (no custom colors)
        self.assertEqual(self.controller.custom_theme().light.preset, PRESET_CALM_BLUE)
        self.assertIsNone(self.controller.custom_theme().light.accent_color)

        # 1. Stage custom color on Light Mode (UNCOMMITTED)
        self.controller.stage_mode_customization(
            "Light",
            ModeCustomization(preset=PRESET_SAGE_TEAL, accent_color="#00FF00"),
        )
        self.assertEqual(self.controller.staged_custom_theme().light.accent_color, "#00FF00")
        # Committed preferences & disk remain untouched!
        self.assertIsNone(self.controller.custom_theme().light.accent_color)
        loaded_disk = load_preferences(self.pref_file)
        self.assertIsNone(loaded_disk.custom_theme.light.accent_color)

        # 2. Click Reset to Preset (Staged Reset)
        self.view._theme_reset_mode_btn.click()
        self.assertIsNone(self.controller.staged_custom_theme().light.accent_color)
        self.assertIsNone(self.controller.custom_theme().light.accent_color)
        loaded_disk = load_preferences(self.pref_file)
        self.assertIsNone(loaded_disk.custom_theme.light.accent_color)

        # 3. Click Undo -> restores previously staged custom color in memory & preview ONLY
        self.view._theme_undo_btn.click()
        self.assertEqual(self.controller.staged_custom_theme().light.accent_color, "#00FF00")
        self.assertEqual(self.theme_manager.current_tokens.accent.primary.background, "#00FF00")

        # INVARIANT: committed preferences and disk MUST still be the unmutated committed state!
        self.assertIsNone(self.controller.custom_theme().light.accent_color)
        loaded_disk = load_preferences(self.pref_file)
        self.assertIsNone(loaded_disk.custom_theme.light.accent_color)

        # 4. Now click Apply -> only now should preferences and disk receive the change!
        self.view._theme_apply_btn.click()
        self.assertEqual(self.controller.custom_theme().light.accent_color, "#00FF00")
        loaded_disk_after_apply = load_preferences(self.pref_file)
        self.assertEqual(loaded_disk_after_apply.custom_theme.light.accent_color, "#00FF00")

    def test_appearance_system_dark_tab_staged_reset_undo_preserves_dark_preview_and_isolation(self) -> None:
        # Appearance is set to System
        self.assertEqual(self.controller.appearance(), "System")
        self.assertEqual(self.controller.custom_theme().dark.preset, PRESET_CALM_BLUE)
        self.assertIsNone(self.controller.custom_theme().dark.accent_color)

        # 1. Switch to Dark Mode Tab
        self.view._theme_tabs.setCurrentIndex(1)
        self.assertEqual(self.view._get_active_tab_mode(), "Dark")

        # 2. Stage custom color on Dark Mode (UNCOMMITTED)
        self.controller.stage_mode_customization(
            "Dark",
            ModeCustomization(preset=PRESET_INDIGO_VIOLET, accent_color="#7B68EE"),
        )
        self.assertEqual(self.controller.staged_custom_theme().dark.accent_color, "#7B68EE")
        # In Dark tab live preview, tokens must reflect the staged dark accent
        self.assertEqual(self.theme_manager.current_tokens.accent.primary.background, "#7B68EE")
        # Committed preferences & disk remain untouched
        self.assertIsNone(self.controller.custom_theme().dark.accent_color)
        loaded_disk = load_preferences(self.pref_file)
        self.assertIsNone(loaded_disk.custom_theme.dark.accent_color)

        # 3. Click Reset to Preset in Dark Tab
        self.view._theme_reset_mode_btn.click()
        self.assertIsNone(self.controller.staged_custom_theme().dark.accent_color)
        self.assertIsNone(self.controller.custom_theme().dark.accent_color)
        loaded_disk = load_preferences(self.pref_file)
        self.assertIsNone(loaded_disk.custom_theme.dark.accent_color)

        # 4. Click Undo in Dark Tab -> must restore Dark staged state AND Dark live tokens!
        self.view._theme_undo_btn.click()
        self.assertEqual(self.controller.staged_custom_theme().dark.accent_color, "#7B68EE")
        self.assertEqual(self.controller.staged_custom_theme().dark.preset, PRESET_INDIGO_VIOLET)
        self.assertEqual(self.theme_manager.current_tokens.accent.primary.background, "#7B68EE")

        # Invariant: committed preferences & disk remain unchanged
        self.assertIsNone(self.controller.custom_theme().dark.accent_color)
        loaded_disk = load_preferences(self.pref_file)
        self.assertIsNone(loaded_disk.custom_theme.dark.accent_color)
        self.assertEqual(self.controller.appearance(), "System")

    def test_reset_all_to_default_is_immediately_undoable(self) -> None:
        self.controller.stage_mode_customization(
            "Light",
            ModeCustomization(preset=PRESET_WARM_NEUTRAL, accent_color="#111111"),
        )
        self.controller.stage_mode_customization(
            "Dark",
            ModeCustomization(preset=PRESET_INDIGO_VIOLET, accent_color="#222222"),
        )

        # 1. Click Reset All to Default
        self.view._theme_reset_all_btn.click()
        staged = self.controller.staged_custom_theme()
        self.assertEqual(staged.light.preset, PRESET_CALM_BLUE)
        self.assertEqual(staged.dark.preset, PRESET_CALM_BLUE)
        self.assertIsNone(staged.light.accent_color)
        self.assertIsNone(staged.dark.accent_color)
        self.assertTrue(self.controller.can_undo())

        # 2. Undo immediately restores both Light and Dark custom configurations!
        self.view._theme_undo_btn.click()
        restored = self.controller.staged_custom_theme()
        self.assertEqual(restored.light.preset, PRESET_WARM_NEUTRAL)
        self.assertEqual(restored.light.accent_color, "#111111")
        self.assertEqual(restored.dark.preset, PRESET_INDIGO_VIOLET)
        self.assertEqual(restored.dark.accent_color, "#222222")

    def test_in_picker_live_preview_and_cancellation_rollback(self) -> None:
        self.controller.preview_tab_mode("Light")
        initial_tokens = self.theme_manager.current_tokens
        self.assertEqual(initial_tokens.accent.primary.background, "#3E6690")

        # Mock QColorDialog behavior
        with patch.object(QColorDialog, "exec", return_value=False):
            # When user opens picker and cancels without accepting
            self.view._on_pick_color("Light", "accent_color")
            # Must remain at initial tokens
            self.assertEqual(
                self.theme_manager.current_tokens.accent.primary.background,
                "#3E6690",
            )

        # When user accepts dialog with green color
        with patch.object(QColorDialog, "exec", return_value=True), \
             patch.object(QColorDialog, "selectedColor", return_value=QColor("#00AA55")):
            self.view._on_pick_color("Light", "accent_color")
            self.assertEqual(
                self.controller.staged_custom_theme().light.accent_color,
                "#00AA55",
            )
            self.assertEqual(
                self.theme_manager.current_tokens.accent.primary.background,
                "#00AA55",
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtCore import Qt
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from src.ui_desktop.state.preferences import (
    DEFAULT_ACCENT,
    DEFAULT_APPEARANCE,
    Preferences,
    load_preferences,
    save_preferences,
)
from src.ui_desktop.theming.color_math import (
    adjust_lightness,
    best_foreground,
    blend_colors,
    contrast_ratio,
    derive_accent_tokens_from_primary,
    hex_to_rgb,
    is_valid_hex,
    normalize_hex,
    relative_luminance,
    rgb_to_hex,
)
from src.ui_desktop.theming.theme_manager import (
    Accent,
    Appearance,
    ThemeManager,
    build_palette,
    build_stylesheet,
    parse_accent,
    parse_appearance,
    resolve_effective_appearance,
    resolve_tokens,
)
from src.ui_desktop.theming.tokens import (
    ACCENT_CALM_BLUE_DARK,
    ACCENT_CALM_BLUE_LIGHT,
    ACCENT_INDIGO_VIOLET_DARK,
    ACCENT_INDIGO_VIOLET_LIGHT,
    ACCENT_SAGE_TEAL_DARK,
    ACCENT_SAGE_TEAL_LIGHT,
    ACCENT_WARM_NEUTRAL_DARK,
    ACCENT_WARM_NEUTRAL_LIGHT,
    NEUTRAL_DARK,
    NEUTRAL_LIGHT,
    PRESET_CALM_BLUE,
    PRESET_INDIGO_VIOLET,
    PRESET_NAMES,
    PRESET_SAGE_TEAL,
    PRESET_WARM_NEUTRAL,
    SEMANTIC_DARK,
    SEMANTIC_LIGHT,
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
    ThemeTokens,
    build_custom_accent_tokens,
    build_custom_neutral_tokens,
    build_resolved_theme_tokens,
)


class ColorMathAndContrastTests(unittest.TestCase):
    """Tests for WCAG 2.1 relative luminance, contrast calculation, and hex validation."""

    def test_hex_normalization_and_validation(self) -> None:
        self.assertEqual(normalize_hex("#fff"), "#FFFFFF")
        self.assertEqual(normalize_hex("3e6690"), "#3E6690")
        self.assertEqual(normalize_hex("  #123abc  "), "#123ABC")
        self.assertEqual(normalize_hex("invalid", fallback="#AABBCC"), "#AABBCC")
        self.assertEqual(normalize_hex(None, fallback="#112233"), "#112233")

        self.assertTrue(is_valid_hex("#fff"))
        self.assertTrue(is_valid_hex("#123456"))
        self.assertTrue(is_valid_hex("ABCDEF"))
        self.assertFalse(is_valid_hex("#gggggg"))
        self.assertFalse(is_valid_hex("12345"))
        self.assertFalse(is_valid_hex(None))

    def test_rgb_conversions(self) -> None:
        self.assertEqual(hex_to_rgb("#FFFFFF"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("#000000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("#3E6690"), (62, 102, 144))
        self.assertEqual(rgb_to_hex(62, 102, 144), "#3E6690")

    def test_wcag_luminance_and_contrast_ratios(self) -> None:
        l_white = relative_luminance("#FFFFFF")
        l_black = relative_luminance("#000000")
        self.assertAlmostEqual(l_white, 1.0, places=4)
        self.assertAlmostEqual(l_black, 0.0, places=4)
        self.assertAlmostEqual(contrast_ratio("#FFFFFF", "#000000"), 21.0, places=1)
        self.assertAlmostEqual(contrast_ratio("#FFFFFF", "#FFFFFF"), 1.0, places=1)

        self.assertGreaterEqual(contrast_ratio(NEUTRAL_LIGHT.surface_primary, NEUTRAL_LIGHT.text_primary), 7.0)
        self.assertGreaterEqual(contrast_ratio(NEUTRAL_DARK.surface_primary, NEUTRAL_DARK.text_primary), 7.0)

    def test_best_foreground_selection(self) -> None:
        self.assertEqual(best_foreground("#FFFFFF", "#FFFFFF", "#17181A"), "#17181A")
        self.assertEqual(best_foreground("#000000", "#FFFFFF", "#17181A"), "#FFFFFF")
        self.assertEqual(best_foreground("#0A192F", "#FFFFFF", "#17181A"), "#FFFFFF")
        self.assertEqual(best_foreground("#FFFFD0", "#FFFFFF", "#17181A"), "#17181A")


class MidLuminanceBoundaryContrastGuardTests(unittest.TestCase):
    """Rigorous contrast tests for tricky mid-luminance, boundary, and extreme custom colors."""

    BOUNDARY_COLORS = [
        "#808080",  # Mid gray (luminance ~0.21)
        "#A07050",  # Tricky brownish mid-orange
        "#7F7F00",  # Olive yellow
        "#008080",  # Teal
        "#800080",  # Purple
        "#408040",  # Medium green
        "#B08030",  # Gold / ochre
        "#907090",  # Dusty mauve
        "#778899",  # Slate gray
        "#BDB76B",  # Dark khaki
        "#7A7A7A",  # Boundary gray
        "#888888",  # Boundary gray
        "#666666",  # Boundary gray
        "#FFFF00",  # Pure bright yellow
        "#00FF00",  # Neon green
        "#00FFFF",  # Neon cyan
        "#FF00FF",  # Magenta
        "#000000",  # Pure black
        "#FFFFFF",  # Pure white
        "#123456",  # Deep navy
        "#FEDCBA",  # Pale peach
    ]

    def test_all_boundary_colors_achieve_wcag_aa_for_primary_and_soft(self) -> None:
        for hex_code in self.BOUNDARY_COLORS:
            for is_dark in (False, True):
                mode_str = "Dark" if is_dark else "Light"
                derived = derive_accent_tokens_from_primary(hex_code, is_dark_mode=is_dark)
                (
                    p_bg, on_p,
                    hov_bg, on_hov,
                    pres_bg, on_pres,
                    soft_bg, on_soft,
                    sel_bg,
                ) = derived

                cr_primary = contrast_ratio(p_bg, on_p)
                cr_hover = contrast_ratio(hov_bg, on_hov)
                cr_pressed = contrast_ratio(pres_bg, on_pres)
                cr_soft = contrast_ratio(soft_bg, on_soft)

                self.assertGreaterEqual(
                    cr_primary, 4.5,
                    f"Primary text contrast failed for {hex_code} in {mode_str} mode: {cr_primary:.2f}:1"
                )
                self.assertGreaterEqual(
                    cr_hover, 4.5,
                    f"Hover text contrast failed for {hex_code} in {mode_str} mode: {cr_hover:.2f}:1"
                )
                self.assertGreaterEqual(
                    cr_pressed, 4.5,
                    f"Pressed text contrast failed for {hex_code} in {mode_str} mode: {cr_pressed:.2f}:1"
                )
                self.assertGreaterEqual(
                    cr_soft, 4.5,
                    f"Soft text contrast failed for {hex_code} in {mode_str} mode: {cr_soft:.2f}:1"
                )

    def test_random_arbitrary_colors_contrast_invariants(self) -> None:
        random.seed(20260827)
        for _ in range(100):
            rand_hex = f"#{random.randint(0, 0xFFFFFF):06X}"
            for is_dark in (False, True):
                derived = derive_accent_tokens_from_primary(rand_hex, is_dark_mode=is_dark)
                p_bg, on_p, _, _, _, _, soft_bg, on_soft, _ = derived
                self.assertGreaterEqual(
                    contrast_ratio(p_bg, on_p), 4.5,
                    f"Random primary {rand_hex} (is_dark={is_dark}) failed contrast: {contrast_ratio(p_bg, on_p):.2f}"
                )
                self.assertGreaterEqual(
                    contrast_ratio(soft_bg, on_soft), 4.5,
                    f"Random soft {rand_hex} (is_dark={is_dark}) failed contrast: {contrast_ratio(soft_bg, on_soft):.2f}"
                )


class PresetAuthoritativeTruthTests(unittest.TestCase):
    """Verify elimination of preset dual-truth: custom_theme.<mode>.preset is the sole authoritative preset."""

    def test_preset_only_customization_resolves_accurately_without_custom_hex(self) -> None:
        # User only picked Sage / Teal for Light, and Indigo / Violet for Dark, with NO custom hexes
        config = CustomThemeConfig(
            light=ModeCustomization(preset=PRESET_SAGE_TEAL),
            dark=ModeCustomization(preset=PRESET_INDIGO_VIOLET),
        )

        tokens_light = build_resolved_theme_tokens("Light", config.light)
        self.assertEqual(tokens_light.accent.primary.background, ACCENT_SAGE_TEAL_LIGHT.primary.background)
        self.assertEqual(tokens_light.accent.primary.foreground, ACCENT_SAGE_TEAL_LIGHT.primary.foreground)

        tokens_dark = build_resolved_theme_tokens("Dark", config.dark)
        self.assertEqual(tokens_dark.accent.primary.background, ACCENT_INDIGO_VIOLET_DARK.primary.background)
        self.assertEqual(tokens_dark.accent.primary.foreground, ACCENT_INDIGO_VIOLET_DARK.primary.foreground)

    def test_reboot_persistence_preserves_independent_mode_presets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pref_file = Path(tmp) / "preferences.json"
            prefs = Preferences(
                appearance="Light",
                custom_theme=CustomThemeConfig(
                    light=ModeCustomization(preset=PRESET_WARM_NEUTRAL),
                    dark=ModeCustomization(preset=PRESET_SAGE_TEAL),
                ),
            )
            save_preferences(prefs, pref_file)

            # Re-read from disk (reboot simulation)
            loaded = load_preferences(pref_file)
            self.assertEqual(loaded.custom_theme.light.preset, PRESET_WARM_NEUTRAL)
            self.assertEqual(loaded.custom_theme.dark.preset, PRESET_SAGE_TEAL)
            # Legacy fallback accent mirrors active mode's preset
            self.assertEqual(loaded.accent, PRESET_WARM_NEUTRAL)

    def test_legacy_global_accent_does_not_override_mode_preset(self) -> None:
        # Simulating JSON file where custom_theme has explicit mode presets, but legacy accent says "Calm Blue"
        with tempfile.TemporaryDirectory() as tmp:
            pref_file = Path(tmp) / "preferences.json"
            raw_data = {
                "appearance": "Dark",
                "accent": "Calm Blue",  # Stale legacy global field
                "custom_theme": {
                    "light": {"preset": "Sage / Teal"},
                    "dark": {"preset": "Indigo / Violet"},
                },
            }
            pref_file.write_text(json.dumps(raw_data), encoding="utf-8")

            loaded = load_preferences(pref_file)
            self.assertEqual(loaded.custom_theme.light.preset, "Sage / Teal")
            self.assertEqual(loaded.custom_theme.dark.preset, "Indigo / Violet")

            # Resolving tokens must use mode presets, NOT the stale legacy "Calm Blue"
            tokens_light = build_resolved_theme_tokens("Light", loaded.custom_theme.light)
            self.assertEqual(tokens_light.accent.primary.background, ACCENT_SAGE_TEAL_LIGHT.primary.background)

            tokens_dark = build_resolved_theme_tokens("Dark", loaded.custom_theme.dark)
            self.assertEqual(tokens_dark.accent.primary.background, ACCENT_INDIGO_VIOLET_DARK.primary.background)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SystemModeSwitchingAndLifecycleTests(unittest.TestCase):
    """Test ThemeManager dynamic switching in System mode between independent Light/Dark presets."""

    def test_system_mode_switches_between_light_and_dark_presets_live(self) -> None:
        app = QApplication.instance() or QApplication([])
        tm = ThemeManager(app)

        prefs = Preferences(
            appearance="System",
            custom_theme=CustomThemeConfig(
                light=ModeCustomization(preset=PRESET_SAGE_TEAL),
                dark=ModeCustomization(preset=PRESET_INDIGO_VIOLET),
            ),
        )

        # 1. When OS reports Light
        with patch("src.ui_desktop.theming.theme_manager.detect_system_color_scheme", return_value=Qt.ColorScheme.Light):
            tokens = tm.apply_preferences(prefs)
            self.assertEqual(tokens.accent.primary.background, ACCENT_SAGE_TEAL_LIGHT.primary.background)

        # 2. When OS switches to Dark
        with patch("src.ui_desktop.theming.theme_manager.detect_system_color_scheme", return_value=Qt.ColorScheme.Dark):
            # Trigger OS scheme change handler
            tm._on_os_color_scheme_changed(Qt.ColorScheme.Dark)
            self.assertEqual(tm.current_tokens.accent.primary.background, ACCENT_INDIGO_VIOLET_DARK.primary.background)

        # 3. When OS switches back to Light
        with patch("src.ui_desktop.theming.theme_manager.detect_system_color_scheme", return_value=Qt.ColorScheme.Light):
            tm._on_os_color_scheme_changed(Qt.ColorScheme.Light)
            self.assertEqual(tm.current_tokens.accent.primary.background, ACCENT_SAGE_TEAL_LIGHT.primary.background)

    def test_theme_manager_preview_and_revert_with_preset_only(self) -> None:
        app = QApplication.instance() or QApplication([])
        tm = ThemeManager(app)

        # Apply Calm Blue baseline
        tm.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        self.assertEqual(tm.current_tokens.accent.primary.background, ACCENT_CALM_BLUE_LIGHT.primary.background)

        # Live preview Warm Neutral preset
        preview_tokens = tm.preview_customization(
            Appearance.LIGHT,
            ModeCustomization(preset=PRESET_WARM_NEUTRAL),
        )
        self.assertEqual(preview_tokens.accent.primary.background, ACCENT_WARM_NEUTRAL_LIGHT.primary.background)

        # Revert live preview back to Calm Blue
        reverted_tokens = tm.revert_preview()
        self.assertEqual(reverted_tokens.accent.primary.background, ACCENT_CALM_BLUE_LIGHT.primary.background)


if __name__ == "__main__":
    unittest.main()

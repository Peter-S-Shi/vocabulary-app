from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor, QPalette
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
        # Black and White
        l_white = relative_luminance("#FFFFFF")
        l_black = relative_luminance("#000000")
        self.assertAlmostEqual(l_white, 1.0, places=4)
        self.assertAlmostEqual(l_black, 0.0, places=4)
        self.assertAlmostEqual(contrast_ratio("#FFFFFF", "#000000"), 21.0, places=1)
        self.assertAlmostEqual(contrast_ratio("#FFFFFF", "#FFFFFF"), 1.0, places=1)

        # Body text contrast against background (WCAG AA requirement >= 4.5:1)
        self.assertGreaterEqual(contrast_ratio(NEUTRAL_LIGHT.surface_primary, NEUTRAL_LIGHT.text_primary), 7.0)
        self.assertGreaterEqual(contrast_ratio(NEUTRAL_DARK.surface_primary, NEUTRAL_DARK.text_primary), 7.0)

    def test_best_foreground_selection(self) -> None:
        # On pure white, dark text gives much higher contrast
        self.assertEqual(best_foreground("#FFFFFF", "#FFFFFF", "#17181A"), "#17181A")
        # On pure black, white text gives much higher contrast
        self.assertEqual(best_foreground("#000000", "#FFFFFF", "#17181A"), "#FFFFFF")
        # On deep navy #0A192F, white text should be selected
        self.assertEqual(best_foreground("#0A192F", "#FFFFFF", "#17181A"), "#FFFFFF")
        # On light pastel yellow #FFFFD0, dark text should be selected
        self.assertEqual(best_foreground("#FFFFD0", "#FFFFFF", "#17181A"), "#17181A")


class FourOfficialPresetsTests(unittest.TestCase):
    """Verify exact audited hex values and structure of the 4 official presets in Light & Dark."""

    def test_calm_blue_preset(self) -> None:
        self.assertEqual(ACCENT_CALM_BLUE_LIGHT.primary.background, "#3E6690")
        self.assertEqual(ACCENT_CALM_BLUE_LIGHT.primary.foreground, "#FFFFFF")
        self.assertEqual(ACCENT_CALM_BLUE_DARK.primary.background, "#82ACD4")
        self.assertEqual(ACCENT_CALM_BLUE_DARK.primary.foreground, "#17181A")

    def test_sage_teal_preset(self) -> None:
        self.assertEqual(ACCENT_SAGE_TEAL_LIGHT.primary.background, "#4B7767")
        self.assertEqual(ACCENT_SAGE_TEAL_LIGHT.primary.foreground, "#FFFFFF")
        self.assertEqual(ACCENT_SAGE_TEAL_DARK.primary.background, "#83B09E")
        self.assertEqual(ACCENT_SAGE_TEAL_DARK.primary.foreground, "#17181A")

    def test_indigo_violet_preset(self) -> None:
        self.assertEqual(ACCENT_INDIGO_VIOLET_LIGHT.primary.background, "#5C5C9B")
        self.assertEqual(ACCENT_INDIGO_VIOLET_LIGHT.primary.foreground, "#FFFFFF")
        self.assertEqual(ACCENT_INDIGO_VIOLET_DARK.primary.background, "#9C9CCF")
        self.assertEqual(ACCENT_INDIGO_VIOLET_DARK.primary.foreground, "#17181A")

    def test_warm_neutral_preset(self) -> None:
        self.assertEqual(ACCENT_WARM_NEUTRAL_LIGHT.primary.background, "#8C6B4E")
        self.assertEqual(ACCENT_WARM_NEUTRAL_LIGHT.primary.foreground, "#FFFFFF")
        self.assertEqual(ACCENT_WARM_NEUTRAL_DARK.primary.background, "#C9A57F")
        self.assertEqual(ACCENT_WARM_NEUTRAL_DARK.primary.foreground, "#17181A")

    def test_accent_enum_and_parser(self) -> None:
        self.assertEqual(parse_accent("Calm Blue"), Accent.CALM_BLUE)
        self.assertEqual(parse_accent("Sage / Teal"), Accent.SAGE_TEAL)
        self.assertEqual(parse_accent("Indigo / Violet"), Accent.INDIGO_VIOLET)
        self.assertEqual(parse_accent("Warm Neutral"), Accent.WARM_NEUTRAL)
        # Fuzzy / alias fallback
        self.assertEqual(parse_accent("sage"), Accent.SAGE_TEAL)
        self.assertEqual(parse_accent("indigo"), Accent.INDIGO_VIOLET)
        self.assertEqual(parse_accent("unknown_garbage"), Accent.CALM_BLUE)


class AccentAndSurfaceDerivationTests(unittest.TestCase):
    """Test custom accent interaction family and neutral surface derivations."""

    def test_accent_family_derivation_light_and_dark(self) -> None:
        # Light mode custom accent
        derived_light = derive_accent_tokens_from_primary("#2E7D32", is_dark_mode=False)
        (
            p_bg, on_p,
            hov_bg, on_hov,
            pres_bg, on_pres,
            soft_bg, on_soft,
            sel_bg,
        ) = derived_light

        self.assertEqual(p_bg, "#2E7D32")
        self.assertEqual(on_p, "#FFFFFF")
        self.assertGreaterEqual(contrast_ratio(p_bg, on_p), 4.5)
        self.assertGreaterEqual(contrast_ratio(soft_bg, on_soft), 4.5)

        # Dark mode custom accent
        derived_dark = derive_accent_tokens_from_primary("#81C784", is_dark_mode=True)
        (
            dp_bg, don_p,
            dhov_bg, don_hov,
            dpres_bg, don_pres,
            dsoft_bg, don_soft,
            dsel_bg,
        ) = derived_dark
        self.assertEqual(dp_bg, "#81C784")
        self.assertEqual(don_p, "#17181A")
        self.assertGreaterEqual(contrast_ratio(dp_bg, don_p), 4.5)
        self.assertGreaterEqual(contrast_ratio(dsoft_bg, don_soft), 4.5)

    def test_neutral_tokens_contrast_guard(self) -> None:
        # When an unreadable text color (e.g. bright yellow #FFFF00 on pure white surface) is specified,
        # the contrast guard must fall back to the readable high-contrast foreground.
        custom = ModeCustomization(
            preset=PRESET_CALM_BLUE,
            background_color="#FFFFFF",
            surface_color="#FFFFFF",
            text_color="#FFFF00",  # Unreadable yellow on white
        )
        resolved = build_resolved_theme_tokens("Light", custom)
        # Must not be #FFFF00; should guard with readable dark text
        self.assertNotEqual(resolved.neutral.text_primary, "#FFFF00")
        self.assertGreaterEqual(contrast_ratio(resolved.neutral.surface_primary, resolved.neutral.text_primary), 4.5)

    def test_semantic_invariants_are_immutable(self) -> None:
        # Regardless of custom accent or surface overrides, semantic tokens remain 100% stable
        custom_wild = ModeCustomization(
            preset=PRESET_INDIGO_VIOLET,
            accent_color="#FF00FF",  # Magenta
            background_color="#001122",
            surface_color="#002244",
            text_color="#FFFFFF",
        )
        resolved_light = build_resolved_theme_tokens("Light", custom_wild)
        self.assertEqual(resolved_light.semantic.success.background, SEMANTIC_LIGHT.success.background)
        self.assertEqual(resolved_light.semantic.warning.background, SEMANTIC_LIGHT.warning.background)
        self.assertEqual(resolved_light.semantic.danger.background, SEMANTIC_LIGHT.danger.background)
        self.assertEqual(resolved_light.semantic.star.background, SEMANTIC_LIGHT.star.background)
        self.assertEqual(resolved_light.semantic.quiz_correct.background, SEMANTIC_LIGHT.quiz_correct.background)
        self.assertEqual(resolved_light.semantic.quiz_wrong.background, SEMANTIC_LIGHT.quiz_wrong.background)

        resolved_dark = build_resolved_theme_tokens("Dark", custom_wild)
        self.assertEqual(resolved_dark.semantic.success.background, SEMANTIC_DARK.success.background)
        self.assertEqual(resolved_dark.semantic.danger.background, SEMANTIC_DARK.danger.background)
        self.assertEqual(resolved_dark.semantic.star.background, SEMANTIC_DARK.star.background)


class ThemePersistenceAndCompatibilityTests(unittest.TestCase):
    """Test JSON preferences serialization, backward compatibility, and corruption resistance."""

    def test_backward_compatibility_with_legacy_preferences_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pref_file = Path(tmp) / "preferences.json"
            # Old format without custom_theme field
            legacy_data = {
                "appearance": "Dark",
                "accent": "Sage / Teal",
                "motion": "Reduced",
                "quiz_presentation": "immersive_focus",
            }
            pref_file.write_text(json.dumps(legacy_data), encoding="utf-8")

            loaded = load_preferences(pref_file)
            self.assertEqual(loaded.appearance, "Dark")
            self.assertEqual(loaded.accent, "Sage / Teal")
            self.assertEqual(loaded.custom_theme.dark.preset, "Sage / Teal")
            self.assertEqual(loaded.custom_theme.light.preset, "Sage / Teal")
            self.assertFalse(loaded.custom_theme.dark.is_customized())

    def test_corrupted_preferences_file_degrades_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pref_file = Path(tmp) / "preferences.json"
            pref_file.write_text("NOT_JSON{{{", encoding="utf-8")
            loaded = load_preferences(pref_file)
            self.assertEqual(loaded.appearance, DEFAULT_APPEARANCE)
            self.assertEqual(loaded.accent, DEFAULT_ACCENT)
            self.assertEqual(loaded.custom_theme.light.preset, PRESET_CALM_BLUE)

    def test_save_and_reload_full_custom_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pref_file = Path(tmp) / "preferences.json"
            prefs = Preferences(
                appearance="Light",
                accent="Calm Blue",
                custom_theme=CustomThemeConfig(
                    light=ModeCustomization(
                        preset=PRESET_SAGE_TEAL,
                        accent_color="#2E7D32",
                        background_color="#F0F5F1",
                        surface_color="#FFFFFF",
                        text_color="#1B3B22",
                    ),
                    dark=ModeCustomization(
                        preset=PRESET_INDIGO_VIOLET,
                        accent_color="#9C9CCF",
                    ),
                ),
            )
            save_preferences(prefs, pref_file)

            reloaded = load_preferences(pref_file)
            self.assertEqual(reloaded.appearance, "Light")
            self.assertEqual(reloaded.custom_theme.light.preset, PRESET_SAGE_TEAL)
            self.assertEqual(reloaded.custom_theme.light.accent_color, "#2E7D32")
            self.assertEqual(reloaded.custom_theme.light.background_color, "#F0F5F1")
            self.assertEqual(reloaded.custom_theme.dark.preset, PRESET_INDIGO_VIOLET)
            self.assertEqual(reloaded.custom_theme.dark.accent_color, "#9C9CCF")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ThemeManagerLifecycleTests(unittest.TestCase):
    """Test ThemeManager live preview, staging, apply, and reset mechanics."""

    def test_theme_manager_preview_and_revert(self) -> None:
        app = QApplication.instance() or QApplication([])
        tm = ThemeManager(app)

        # 1. Apply baseline
        tm.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        self.assertEqual(tm.current, (Appearance.LIGHT, Accent.CALM_BLUE))
        self.assertEqual(tm.current_tokens.accent.primary.background, "#3E6690")

        # 2. Stage live preview with custom green accent
        preview_custom = ModeCustomization(preset=PRESET_CALM_BLUE, accent_color="#2E7D32")
        preview_tokens = tm.preview_customization(Appearance.LIGHT, preview_custom)
        self.assertEqual(preview_tokens.accent.primary.background, "#2E7D32")
        self.assertEqual(tm.current_tokens.accent.primary.background, "#2E7D32")
        # Stored committed appearance has not changed
        self.assertEqual(tm.current, (Appearance.LIGHT, Accent.CALM_BLUE))

        # 3. Cancel / Revert preview
        reverted = tm.revert_preview()
        self.assertEqual(reverted.accent.primary.background, "#3E6690")
        self.assertEqual(tm.current_tokens.accent.primary.background, "#3E6690")

    def test_theme_manager_reset_mode_to_preset(self) -> None:
        app = QApplication.instance() or QApplication([])
        tm = ThemeManager(app)

        # Apply custom theme
        custom_cfg = CustomThemeConfig(
            light=ModeCustomization(preset=PRESET_WARM_NEUTRAL, accent_color="#AA5500")
        )
        tm.apply(Appearance.LIGHT, Accent.WARM_NEUTRAL, custom_config=custom_cfg)
        self.assertEqual(tm.current_tokens.accent.primary.background, "#AA5500")

        # Reset mode to Sage / Teal preset
        tm.reset_mode_to_preset(Appearance.LIGHT, PRESET_SAGE_TEAL)
        self.assertEqual(tm.current_tokens.accent.primary.background, ACCENT_SAGE_TEAL_LIGHT.primary.background)
        self.assertFalse(tm.custom_config.light.is_customized())

    def test_theme_manager_reset_all_to_default(self) -> None:
        app = QApplication.instance() or QApplication([])
        tm = ThemeManager(app)

        tm.reset_all_to_default()
        self.assertEqual(tm.custom_config.light.preset, PRESET_CALM_BLUE)
        self.assertEqual(tm.custom_config.dark.preset, PRESET_CALM_BLUE)
        self.assertFalse(tm.custom_config.light.is_customized())
        self.assertFalse(tm.custom_config.dark.is_customized())


if __name__ == "__main__":
    unittest.main()

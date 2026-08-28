from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.ui_desktop.theming.color_math import (
    adjust_lightness,
    best_foreground,
    blend_colors,
    contrast_ratio,
    derive_accent_tokens_from_primary,
    is_valid_hex,
    normalize_hex,
)

"""
Semantic token architecture and theme presets for Vocabulary App (Phase D).

DESIGN.md's hex values remain the numeric authority for official presets
(§ 8 Semantic Token Architecture, § 11 Frozen Theme Tokens, § 18 Contrast Tables).

All four official presets are supported as safe baseline starters:
1. Calm Blue / Slate (Default)
2. Sage / Teal
3. Indigo / Violet
4. Warm Neutral

User-level theme customization (Background/Surfaces, Text, Accent) is structured
under Light and Dark modes independently, and derives complete, internally-consistent
semantic token families with automatic WCAG AA (>= 4.5:1) contrast guards.
Semantic feedback states (success, warning, danger, star, quiz correct, quiz wrong)
remain strictly immutable invariants protected from accent/surface overrides.
"""


@dataclass(frozen=True)
class ColorPair:
    """A background paired with its explicit, compatible ``on-*`` foreground."""

    background: str
    foreground: str


@dataclass(frozen=True)
class NeutralTokens:
    app_background: str
    surface_primary: str
    surface_secondary: str
    surface_sunken: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_disabled: str
    border_subtle: str
    border_default: str
    border_strong: str
    overlay: str


@dataclass(frozen=True)
class AccentTokens:
    primary: ColorPair
    hover: ColorPair
    pressed: ColorPair
    soft: ColorPair
    selected_background: str

    @property
    def border(self) -> str:
        """``accent-border`` reuses ``accent-primary`` (DESIGN.md § 11.2)."""
        return self.primary.background

    @property
    def focus_ring(self) -> str:
        """``focus-ring`` reuses ``accent-primary`` (DESIGN.md § 11.2)."""
        return self.primary.background


@dataclass(frozen=True)
class SemanticTokens:
    success: ColorPair
    success_soft: str
    warning: ColorPair
    warning_soft: str
    danger: ColorPair
    danger_soft: str
    info: ColorPair
    info_soft: str
    star: ColorPair  # Entries Star affordance; independent of accent/warning (DESIGN.md § 15)

    @property
    def quiz_correct(self) -> ColorPair:
        """``quiz-correct`` aliases ``success`` (DESIGN.md § 11.3)."""
        return self.success

    @property
    def quiz_correct_soft(self) -> str:
        return self.success_soft

    @property
    def quiz_wrong(self) -> ColorPair:
        """``quiz-wrong`` aliases ``danger`` (DESIGN.md § 11.3)."""
        return self.danger

    @property
    def quiz_wrong_soft(self) -> str:
        return self.danger_soft


@dataclass(frozen=True)
class ThemeTokens:
    neutral: NeutralTokens
    accent: AccentTokens
    semantic: SemanticTokens


# --- Neutral Base (DESIGN.md § 11.1) ---------------------------------------

NEUTRAL_LIGHT = NeutralTokens(
    app_background="#F4F3EF",
    surface_primary="#FFFFFF",
    surface_secondary="#F8F7F4",
    surface_sunken="#ECEAE5",
    text_primary="#1C1B18",
    text_secondary="#56534C",
    text_muted="#6E6B62",
    text_disabled="#938F81",
    border_subtle="#E8E6E0",
    border_default="#D9D6CE",
    border_strong="#989486",
    overlay="rgba(28,27,24,.45)",
)

NEUTRAL_DARK = NeutralTokens(
    app_background="#17181A",
    surface_primary="#1E2023",
    surface_secondary="#232528",
    surface_sunken="#131415",
    text_primary="#EDECE8",
    text_secondary="#B7B4AC",
    text_muted="#8F8D87",
    text_disabled="#726F67",
    border_subtle="#2C2E31",
    border_default="#383A3D",
    border_strong="#686B6F",
    overlay="rgba(0,0,0,.6)",
)

# --- 1. Calm Blue / Slate (Default, DESIGN.md § 11.2, § 18.2) --------------

ACCENT_CALM_BLUE_LIGHT = AccentTokens(
    primary=ColorPair("#3E6690", "#FFFFFF"),
    hover=ColorPair("#355A80", "#FFFFFF"),
    pressed=ColorPair("#2C4C6C", "#FFFFFF"),
    soft=ColorPair("#E5EDF3", "#2C4C6C"),
    selected_background="#DCE6EE",
)

ACCENT_CALM_BLUE_DARK = AccentTokens(
    primary=ColorPair("#82ACD4", "#17181A"),
    hover=ColorPair("#93B8DA", "#17181A"),
    pressed=ColorPair("#6E97BC", "#17181A"),
    soft=ColorPair("#223140", "#B7D1E8"),
    selected_background="#283A4B",
)

# --- 2. Sage / Teal (DESIGN.md § 18.2) -------------------------------------

ACCENT_SAGE_TEAL_LIGHT = AccentTokens(
    primary=ColorPair("#4B7767", "#FFFFFF"),
    hover=ColorPair("#40695A", "#FFFFFF"),
    pressed=ColorPair("#35594C", "#FFFFFF"),
    soft=ColorPair("#E6EEEA", "#35594C"),
    selected_background="#DCE9E2",
)

ACCENT_SAGE_TEAL_DARK = AccentTokens(
    primary=ColorPair("#83B09E", "#17181A"),
    hover=ColorPair("#93BAAA", "#17181A"),
    pressed=ColorPair("#6E9C8B", "#17181A"),
    soft=ColorPair("#21302B", "#B7D8C9"),
    selected_background="#263A32",
)

# --- 3. Indigo / Violet (DESIGN.md § 18.2) ---------------------------------

ACCENT_INDIGO_VIOLET_LIGHT = AccentTokens(
    primary=ColorPair("#5C5C9B", "#FFFFFF"),
    hover=ColorPair("#4E4E87", "#FFFFFF"),
    pressed=ColorPair("#414172", "#FFFFFF"),
    soft=ColorPair("#EAEAF3", "#414172"),
    selected_background="#E1E1EE",
)

ACCENT_INDIGO_VIOLET_DARK = AccentTokens(
    primary=ColorPair("#9C9CCF", "#17181A"),
    hover=ColorPair("#ABABD6", "#17181A"),
    pressed=ColorPair("#8A8AC0", "#17181A"),
    soft=ColorPair("#292A3B", "#C7C7E5"),
    selected_background="#2F3044",
)

# --- 4. Warm Neutral (DESIGN.md § 18.2) ------------------------------------

ACCENT_WARM_NEUTRAL_LIGHT = AccentTokens(
    primary=ColorPair("#8C6B4E", "#FFFFFF"),
    hover=ColorPair("#7A5C42", "#FFFFFF"),
    pressed=ColorPair("#684D37", "#FFFFFF"),
    soft=ColorPair("#F1E8DE", "#684D37"),
    selected_background="#E9DDCE",
)

ACCENT_WARM_NEUTRAL_DARK = AccentTokens(
    primary=ColorPair("#C9A57F", "#17181A"),
    hover=ColorPair("#D3B392", "#17181A"),
    pressed=ColorPair("#B98F68", "#17181A"),
    soft=ColorPair("#322820", "#E4CBAE"),
    selected_background="#392E24",
)

# --- Semantic state tokens, independent of accent (DESIGN.md § 11.3, § 18.3)

SEMANTIC_LIGHT = SemanticTokens(
    success=ColorPair("#3B764C", "#FFFFFF"),
    success_soft="#E6F1E7",
    warning=ColorPair("#8F631B", "#FFFFFF"),
    warning_soft="#F6ECDA",
    danger=ColorPair("#B23A3A", "#FFFFFF"),
    danger_soft="#F7E4E3",
    info=ColorPair("#3F6D82", "#FFFFFF"),
    info_soft="#E4EEF1",
    star=ColorPair("#2C4C6C", "#FFFFFF"),
)

SEMANTIC_DARK = SemanticTokens(
    success=ColorPair("#74B285", "#17181A"),
    success_soft="#1F2E23",
    warning=ColorPair("#CDA059", "#17181A"),
    warning_soft="#332A19",
    danger=ColorPair("#DD8080", "#17181A"),
    danger_soft="#3A2323",
    info=ColorPair("#7CAFC2", "#17181A"),
    info_soft="#21313A",
    star=ColorPair("#6E97BC", "#17181A"),
)

# --- Canonical Preset Registries --------------------------------------------

PRESET_CALM_BLUE = "Calm Blue"
PRESET_SAGE_TEAL = "Sage / Teal"
PRESET_INDIGO_VIOLET = "Indigo / Violet"
PRESET_WARM_NEUTRAL = "Warm Neutral"

PRESET_NAMES = (
    PRESET_CALM_BLUE,
    PRESET_SAGE_TEAL,
    PRESET_INDIGO_VIOLET,
    PRESET_WARM_NEUTRAL,
)

PRESETS_LIGHT: dict[str, AccentTokens] = {
    PRESET_CALM_BLUE: ACCENT_CALM_BLUE_LIGHT,
    PRESET_SAGE_TEAL: ACCENT_SAGE_TEAL_LIGHT,
    PRESET_INDIGO_VIOLET: ACCENT_INDIGO_VIOLET_LIGHT,
    PRESET_WARM_NEUTRAL: ACCENT_WARM_NEUTRAL_LIGHT,
}

PRESETS_DARK: dict[str, AccentTokens] = {
    PRESET_CALM_BLUE: ACCENT_CALM_BLUE_DARK,
    PRESET_SAGE_TEAL: ACCENT_SAGE_TEAL_DARK,
    PRESET_INDIGO_VIOLET: ACCENT_INDIGO_VIOLET_DARK,
    PRESET_WARM_NEUTRAL: ACCENT_WARM_NEUTRAL_DARK,
}

THEME_CALM_BLUE_LIGHT = ThemeTokens(
    neutral=NEUTRAL_LIGHT, accent=ACCENT_CALM_BLUE_LIGHT, semantic=SEMANTIC_LIGHT
)
THEME_CALM_BLUE_DARK = ThemeTokens(
    neutral=NEUTRAL_DARK, accent=ACCENT_CALM_BLUE_DARK, semantic=SEMANTIC_DARK
)
THEME_SAGE_TEAL_LIGHT = ThemeTokens(
    neutral=NEUTRAL_LIGHT, accent=ACCENT_SAGE_TEAL_LIGHT, semantic=SEMANTIC_LIGHT
)
THEME_SAGE_TEAL_DARK = ThemeTokens(
    neutral=NEUTRAL_DARK, accent=ACCENT_SAGE_TEAL_DARK, semantic=SEMANTIC_DARK
)
THEME_INDIGO_VIOLET_LIGHT = ThemeTokens(
    neutral=NEUTRAL_LIGHT, accent=ACCENT_INDIGO_VIOLET_LIGHT, semantic=SEMANTIC_LIGHT
)
THEME_INDIGO_VIOLET_DARK = ThemeTokens(
    neutral=NEUTRAL_DARK, accent=ACCENT_INDIGO_VIOLET_DARK, semantic=SEMANTIC_DARK
)
THEME_WARM_NEUTRAL_LIGHT = ThemeTokens(
    neutral=NEUTRAL_LIGHT, accent=ACCENT_WARM_NEUTRAL_LIGHT, semantic=SEMANTIC_LIGHT
)
THEME_WARM_NEUTRAL_DARK = ThemeTokens(
    neutral=NEUTRAL_DARK, accent=ACCENT_WARM_NEUTRAL_DARK, semantic=SEMANTIC_DARK
)


# --- Customization Data Model ----------------------------------------------


@dataclass
class ModeCustomization:
    """User-level customization configuration for one appearance mode (Light or Dark).

    Fields:
        preset: Baseline official preset (Calm Blue, Sage / Teal, Indigo / Violet, Warm Neutral).
        accent_color: Optional custom primary accent hex (overrides preset primary and derives interaction family).
        background_color: Optional custom app background hex.
        surface_color: Optional custom primary surface hex.
        text_color: Optional custom primary text hex (validated against WCAG contrast >= 4.5:1).
    """

    preset: str = PRESET_CALM_BLUE
    accent_color: str | None = None
    background_color: str | None = None
    surface_color: str | None = None
    text_color: str | None = None

    def is_customized(self) -> bool:
        """Returns True if any user override is actively configured."""
        return any(
            (
                self.accent_color is not None,
                self.background_color is not None,
                self.surface_color is not None,
                self.text_color is not None,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "accent_color": self.accent_color,
            "background_color": self.background_color,
            "surface_color": self.surface_color,
            "text_color": self.text_color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ModeCustomization:
        if not isinstance(data, dict):
            return cls()
        preset = str(data.get("preset") or PRESET_CALM_BLUE)
        if preset not in PRESET_NAMES:
            preset = PRESET_CALM_BLUE

        def parse_opt_hex(val: Any) -> str | None:
            if isinstance(val, str) and is_valid_hex(val):
                return normalize_hex(val)
            return None

        return cls(
            preset=preset,
            accent_color=parse_opt_hex(data.get("accent_color")),
            background_color=parse_opt_hex(data.get("background_color")),
            surface_color=parse_opt_hex(data.get("surface_color")),
            text_color=parse_opt_hex(data.get("text_color")),
        )


@dataclass
class CustomThemeConfig:
    """Complete theme customization storage across Light and Dark appearance modes."""

    light: ModeCustomization = field(default_factory=ModeCustomization)
    dark: ModeCustomization = field(default_factory=ModeCustomization)

    def to_dict(self) -> dict[str, Any]:
        return {
            "light": self.light.to_dict(),
            "dark": self.dark.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CustomThemeConfig:
        if not isinstance(data, dict):
            return cls()
        return cls(
            light=ModeCustomization.from_dict(data.get("light")),
            dark=ModeCustomization.from_dict(data.get("dark")),
        )


# --- Token Builders & Derivation Engine -------------------------------------


def build_custom_accent_tokens(
    base_accent: AccentTokens,
    custom_primary_hex: str | None,
    is_dark: bool,
) -> AccentTokens:
    """Build an AccentTokens instance, applying custom primary if provided, or preserving preset tokens."""
    if not custom_primary_hex or not is_valid_hex(custom_primary_hex):
        return base_accent

    (
        p_bg,
        on_p,
        hov_bg,
        on_hov,
        pres_bg,
        on_pres,
        soft_bg,
        on_soft,
        sel_bg,
    ) = derive_accent_tokens_from_primary(custom_primary_hex, is_dark_mode=is_dark)

    return AccentTokens(
        primary=ColorPair(p_bg, on_p),
        hover=ColorPair(hov_bg, on_hov),
        pressed=ColorPair(pres_bg, on_pres),
        soft=ColorPair(soft_bg, on_soft),
        selected_background=sel_bg,
    )


def build_custom_neutral_tokens(
    base_neutral: NeutralTokens,
    custom_bg_hex: str | None,
    custom_surface_hex: str | None,
    custom_text_hex: str | None,
    is_dark: bool,
) -> NeutralTokens:
    """Build a NeutralTokens instance with automatic contrast guarding and derived sub-surfaces."""
    app_bg = normalize_hex(custom_bg_hex, fallback=base_neutral.app_background) if custom_bg_hex else base_neutral.app_background
    surf_pri = normalize_hex(custom_surface_hex, fallback=base_neutral.surface_primary) if custom_surface_hex else base_neutral.surface_primary

    if not custom_bg_hex and not custom_surface_hex and not custom_text_hex:
        return base_neutral

    # Derive layered surfaces
    if not is_dark:
        surf_sec = blend_colors(surf_pri, app_bg, 0.40)
        surf_sunken = adjust_lightness(app_bg, -0.04)
        border_subtle = blend_colors(surf_pri, "#000000", 0.08)
        border_default = blend_colors(surf_pri, "#000000", 0.15)
        border_strong = blend_colors(surf_pri, "#000000", 0.38)
    else:
        surf_sec = blend_colors(surf_pri, app_bg, 0.50)
        surf_sunken = adjust_lightness(app_bg, -0.03)
        border_subtle = blend_colors(surf_pri, "#FFFFFF", 0.08)
        border_default = blend_colors(surf_pri, "#FFFFFF", 0.15)
        border_strong = blend_colors(surf_pri, "#FFFFFF", 0.38)

    # Text derivation with contrast guard
    if custom_text_hex and is_valid_hex(custom_text_hex):
        candidate_text = normalize_hex(custom_text_hex)
        cr_surf = contrast_ratio(surf_pri, candidate_text)
        cr_bg = contrast_ratio(app_bg, candidate_text)
        if cr_surf >= 4.5 and cr_bg >= 4.5:
            text_pri = candidate_text
        else:
            # Fall back to best foreground guaranteeing high readability
            text_pri = best_foreground(surf_pri, light_option="#EDECE8", dark_option="#1C1B18")
    else:
        text_pri = best_foreground(surf_pri, light_option="#EDECE8", dark_option="#1C1B18")

    # Derive text hierarchy
    if not is_dark:
        text_sec = blend_colors(text_pri, surf_pri, 0.35)
        text_mut = blend_colors(text_pri, surf_pri, 0.48)
        # Ensure text_muted passes 4.5:1 against surfaces
        if contrast_ratio(surf_pri, text_mut) < 4.5:
            text_mut = adjust_lightness(text_mut, -0.10)
        text_dis = blend_colors(text_pri, surf_pri, 0.62)
    else:
        text_sec = blend_colors(text_pri, surf_pri, 0.30)
        text_mut = blend_colors(text_pri, surf_pri, 0.44)
        if contrast_ratio(surf_pri, text_mut) < 4.5:
            text_mut = adjust_lightness(text_mut, +0.10)
        text_dis = blend_colors(text_pri, surf_pri, 0.60)

    return NeutralTokens(
        app_background=app_bg,
        surface_primary=surf_pri,
        surface_secondary=surf_sec,
        surface_sunken=surf_sunken,
        text_primary=text_pri,
        text_secondary=text_sec,
        text_muted=text_mut,
        text_disabled=text_dis,
        border_subtle=border_subtle,
        border_default=border_default,
        border_strong=border_strong,
        overlay=base_neutral.overlay,
    )


def build_resolved_theme_tokens(
    effective_appearance: str,
    customization: ModeCustomization | None = None,
) -> ThemeTokens:
    """Resolve concrete ThemeTokens for a given concrete appearance mode ('Light' or 'Dark').

    Guarantees:
    - Base preset fallback if unknown preset is provided.
    - Full derivation of Accent and Neutral token families.
    - Immutable semantic invariant tokens.
    """
    is_dark = effective_appearance.lower() == "dark"
    custom = customization or ModeCustomization()

    preset_map = PRESETS_DARK if is_dark else PRESETS_LIGHT
    base_neutral = NEUTRAL_DARK if is_dark else NEUTRAL_LIGHT
    base_semantic = SEMANTIC_DARK if is_dark else SEMANTIC_LIGHT

    base_accent = preset_map.get(custom.preset, preset_map[PRESET_CALM_BLUE])

    accent_tokens = build_custom_accent_tokens(base_accent, custom.accent_color, is_dark)
    neutral_tokens = build_custom_neutral_tokens(
        base_neutral,
        custom.background_color,
        custom.surface_color,
        custom.text_color,
        is_dark,
    )

    return ThemeTokens(
        neutral=neutral_tokens,
        accent=accent_tokens,
        semantic=base_semantic,
    )

from __future__ import annotations

from dataclasses import dataclass

"""
Direct Python transcription of the frozen DESIGN.md semantic-token tables
(§ 8 Semantic Token Architecture, § 11 Frozen Theme Tokens).

DESIGN.md's hex values remain the numeric authority; this module must be
kept in sync with it, not the reverse (M16.1 contract § 14). Only the
Calm Blue / Slate accent family is transcribed in M16.2 (DESIGN.md § 6.2
lists Calm Blue as the default); Sage/Teal, Indigo/Violet, and Warm Neutral
remain additive future work per the M16.1 contract's explicit scope
decision, not a redesign.

Accent/foreground pairs are stored as paired ``ColorPair`` values rather
than independent flat keys, structurally encoding DESIGN.md § 9's explicit
foreground-pair rule.
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
class TypographyTokens:
    """Concrete type scale realizing DESIGN.md § 15's *structure*.

    § 15 freezes the durable structure -- "a small number of weight/size
    steps (page title, section header, body, secondary/metadata) is
    sufficient; avoid inventing a large type scale" -- and § 20 explicitly
    defers the exact metrics until they can be validated against the
    chosen framework's native text rendering rather than a browser mockup.
    These are those PySide6-validated values; the *names and steps* remain
    the contract, not the pixel numbers.

    Deliberately five steps, not a general-purpose scale. Sizes are px
    (Qt style-sheet units); weights are CSS-style numeric weights.
    """

    page_title_size: int = 21
    page_title_weight: int = 600

    section_heading_size: int = 12
    section_heading_weight: int = 600
    section_heading_letter_spacing: str = "0.6px"

    body_size: int = 13
    body_weight: int = 400

    metric_value_size: int = 21
    metric_value_weight: int = 600

    meta_size: int = 12
    meta_weight: int = 400


@dataclass(frozen=True)
class MetricsTokens:
    """Spacing rhythm, radius, and control sizing (DESIGN.md § 15).

    § 15 requires "a small consistent step scale (e.g. 4/8/12/16/24px-class
    increments) applied uniformly rather than ad hoc per-component
    spacing", "a single small-to-moderate radius used consistently", and
    "consistent control height across buttons/inputs within a density
    mode". These tokens make that enforceable instead of leaving each
    widget to invent its own numbers.
    """

    space_xs: int = 4
    space_sm: int = 8
    space_md: int = 12
    space_lg: int = 16
    space_xl: int = 24

    radius: int = 6
    control_height: int = 30
    table_row_height: int = 32
    page_margin: int = 24


TYPOGRAPHY = TypographyTokens()
METRICS = MetricsTokens()


@dataclass(frozen=True)
class ThemeTokens:
    neutral: NeutralTokens
    accent: AccentTokens
    semantic: SemanticTokens
    # Typography and metrics are Appearance/Accent-independent: switching
    # Light <-> Dark or changing accent family must never reflow the page
    # or resize text (DESIGN.md § 6.1/§ 15).
    typography: TypographyTokens = TYPOGRAPHY
    metrics: MetricsTokens = METRICS


# --- Neutral Base (DESIGN.md § 11.1) ---------------------------------------

NEUTRAL_LIGHT = NeutralTokens(
    app_background="#F4F3EF",
    surface_primary="#FFFFFF",
    surface_secondary="#F8F7F4",
    surface_sunken="#ECEAE5",
    text_primary="#1C1B18",
    text_secondary="#56534C",
    text_muted="#79766D",
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

# --- Calm Blue / Slate accent family (DESIGN.md § 11.2) --------------------

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

# --- Semantic state tokens, independent of accent (DESIGN.md § 11.3) -------

SEMANTIC_LIGHT = SemanticTokens(
    success=ColorPair("#3B764C", "#FFFFFF"),
    success_soft="#E6F1E7",
    warning=ColorPair("#8F631B", "#FFFFFF"),
    warning_soft="#F6ECDA",
    danger=ColorPair("#B23A3A", "#FFFFFF"),
    danger_soft="#F7E4E3",
    info=ColorPair("#3F6D82", "#FFFFFF"),
    info_soft="#E4EEF1",
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
)

THEME_CALM_BLUE_LIGHT = ThemeTokens(
    neutral=NEUTRAL_LIGHT, accent=ACCENT_CALM_BLUE_LIGHT, semantic=SEMANTIC_LIGHT
)
THEME_CALM_BLUE_DARK = ThemeTokens(
    neutral=NEUTRAL_DARK, accent=ACCENT_CALM_BLUE_DARK, semantic=SEMANTIC_DARK
)

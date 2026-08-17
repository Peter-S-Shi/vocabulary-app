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
    # M17 Theme Completion contrast hardening: the prior #79766D only
    # passed the DESIGN.md-audited 4.5:1 minimum against surface-primary
    # (4.54:1); against the surfaces text-muted is actually deployed on
    # in the running app (surface-secondary, app-background -- e.g. Today
    # captions, Entries/Collections scope headings), it measured 4.24:1
    # and 4.09:1, a real WCAG AA failure the audit in DESIGN.md § 18/§ 19
    # had not caught. #6E6B62 clears 4.5:1 against all three surfaces
    # (4.97 / 5.33 / 4.80) while staying strictly between text-secondary
    # and text-disabled, preserving the hierarchy.
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
    # M17 Theme Completion (prompt § 13): the desktop Entries Star column
    # previously used one fixed hardcoded gold (#C9972E) with no theme
    # awareness. It measured only 2.64:1 against Light surface-primary
    # (fails WCAG AA) and sits at hue ~41 deg, only ~4 deg from warning's
    # own ~37 deg hue in both Appearances -- close enough to risk reading
    # as a warning badge. #8A6D00 clears 4.5:1+ against every Light
    # surface it appears on and shifts to hue ~47 deg (clearly more
    # yellow/gold, less brown/amber) for real separation from warning.
    star=ColorPair("#8A6D00", "#FFFFFF"),
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
    # Same Star rationale as Light: #E8C547 keeps hue ~47 deg (vs
    # warning's ~37 deg) and contrasts ~9.7:1 against Dark surface-primary.
    star=ColorPair("#E8C547", "#17181A"),
)

THEME_CALM_BLUE_LIGHT = ThemeTokens(
    neutral=NEUTRAL_LIGHT, accent=ACCENT_CALM_BLUE_LIGHT, semantic=SEMANTIC_LIGHT
)
THEME_CALM_BLUE_DARK = ThemeTokens(
    neutral=NEUTRAL_DARK, accent=ACCENT_CALM_BLUE_DARK, semantic=SEMANTIC_DARK
)

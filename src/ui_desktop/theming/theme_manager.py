from __future__ import annotations

from enum import Enum

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from src.ui_desktop.theming.tokens import (
    THEME_CALM_BLUE_DARK,
    THEME_CALM_BLUE_LIGHT,
    ThemeTokens,
)

"""
Resolves (Appearance, Accent) into a QPalette + QSS pair and applies both
through one call site, per the M16.1 contract § 14 theme/token
implementation boundary. This module decides only the PySide6 plumbing; it
does not redesign any DESIGN.md token value.
"""


class Appearance(str, Enum):
    SYSTEM = "System"
    LIGHT = "Light"
    DARK = "Dark"


class Accent(str, Enum):
    CALM_BLUE = "Calm Blue"


DEFAULT_APPEARANCE = Appearance.SYSTEM
DEFAULT_ACCENT = Accent.CALM_BLUE


def parse_appearance(value: str) -> Appearance:
    try:
        return Appearance(value)
    except ValueError:
        return DEFAULT_APPEARANCE


def parse_accent(value: str) -> Accent:
    try:
        return Accent(value)
    except ValueError:
        return DEFAULT_ACCENT


def resolve_effective_appearance(appearance: Appearance) -> Appearance:
    """Resolve ``System`` to a concrete Light/Dark value.

    Reading the OS Light/Dark preference is packaging-specific behavior
    that DESIGN.md § 20 explicitly defers to the packaging milestones.
    Until that is implemented, ``System`` resolves to ``Light`` as a
    documented, safe placeholder rather than silently guessing per-OS
    behavior. This is a known limitation, not a redesign of the Appearance
    axis (which still accepts and stores ``System``).
    """
    if appearance is Appearance.SYSTEM:
        return Appearance.LIGHT
    return appearance


_TOKENS_BY_THEME: dict[tuple[Appearance, Accent], ThemeTokens] = {
    (Appearance.LIGHT, Accent.CALM_BLUE): THEME_CALM_BLUE_LIGHT,
    (Appearance.DARK, Accent.CALM_BLUE): THEME_CALM_BLUE_DARK,
}


def resolve_tokens(appearance: Appearance, accent: Accent) -> ThemeTokens:
    effective_appearance = resolve_effective_appearance(appearance)
    key = (effective_appearance, accent)
    if key not in _TOKENS_BY_THEME:
        # Only Calm Blue is transcribed in M16.2 (tokens.py docstring);
        # fall back to the default accent rather than raising for an
        # unimplemented family so a malformed/future preference value
        # degrades safely instead of crashing the shell.
        key = (effective_appearance, DEFAULT_ACCENT)
    return _TOKENS_BY_THEME[key]


def build_palette(tokens: ThemeTokens) -> QPalette:
    """Map resolved tokens onto native QPalette roles (§ 14)."""
    palette = QPalette()
    neutral = tokens.neutral
    accent = tokens.accent

    palette.setColor(QPalette.ColorRole.Window, QColor(neutral.app_background))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(neutral.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(neutral.surface_primary))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(neutral.surface_secondary))
    palette.setColor(QPalette.ColorRole.Text, QColor(neutral.text_primary))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(neutral.text_primary))
    palette.setColor(QPalette.ColorRole.Button, QColor(neutral.surface_secondary))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(neutral.text_muted))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(neutral.surface_primary))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(neutral.text_primary))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(accent.primary.background))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(accent.primary.foreground))

    disabled_group = QPalette.ColorGroup.Disabled
    palette.setColor(disabled_group, QPalette.ColorRole.WindowText, QColor(neutral.text_disabled))
    palette.setColor(disabled_group, QPalette.ColorRole.Text, QColor(neutral.text_disabled))
    palette.setColor(disabled_group, QPalette.ColorRole.ButtonText, QColor(neutral.text_disabled))

    return palette


def build_stylesheet(tokens: ThemeTokens) -> str:
    """Application-level QSS: the shared desktop component grammar (§ 14).

    This is the single place the product's visual language is realized.
    It deliberately styles *component roles*, not individual screens, so
    every M17 workspace inherits one coherent grammar instead of
    re-styling itself: typography steps, panel/tile surfaces, the
    management table grammar, navigation state, and the button hierarchy
    are all defined once here and selected by semantic properties
    (``typography``, ``surface``, ``variant``) rather than per-screen
    object names.

    Every rule resolves explicit, paired tokens. Once
    ``QApplication.setStyleSheet()`` is set at all, Qt's style-sheet engine
    takes over painting for every widget application-wide; any widget left
    without an explicit color can silently lose its QPalette-resolved
    foreground and render as low-contrast/disabled-looking rather than
    falling back to the palette. That is exactly the defect the M16.2
    human visual-acceptance pass found in the navigation ``QToolButton``s,
    and the same class of bug DESIGN.md § 11.4 documents for unstyled
    table rows and status pills. Hence DESIGN.md § 9's foreground-pair
    rule is applied to every state below, including ``:disabled``.

    Sizing/spacing come from ``tokens.typography`` / ``tokens.metrics``
    (DESIGN.md § 15) rather than per-widget magic numbers, so density and
    rhythm stay consistent and adjustable in one place.
    """
    neutral = tokens.neutral
    accent = tokens.accent
    semantic = tokens.semantic
    danger = semantic.danger
    type_ = tokens.typography
    metrics = tokens.metrics

    return f"""
    /* --- Base ------------------------------------------------------- */
    QWidget {{
        color: {neutral.text_primary};
        font-size: {type_.body_size}px;
        font-weight: {type_.body_weight};
    }}
    QMainWindow, QWidget#workspace-host {{
        background-color: {neutral.app_background};
    }}

    /* --- Typography steps (DESIGN.md § 15) -------------------------- */
    QLabel[typography="page-title"] {{
        color: {neutral.text_primary};
        font-size: {type_.page_title_size}px;
        font-weight: {type_.page_title_weight};
    }}
    QLabel[typography="page-subtitle"] {{
        color: {neutral.text_secondary};
        font-size: {type_.meta_size}px;
    }}
    QLabel[typography="nav-brand"] {{
        color: {neutral.text_primary};
        font-size: {type_.body_size + 1}px;
        font-weight: 600;
        padding-right: {metrics.space_sm}px;
    }}
    QLabel[typography="section-heading"] {{
        color: {neutral.text_secondary};
        font-size: {type_.section_heading_size}px;
        font-weight: {type_.section_heading_weight};
        letter-spacing: {type_.section_heading_letter_spacing};
    }}
    QLabel[typography="body"] {{
        color: {neutral.text_primary};
        font-size: {type_.body_size}px;
    }}
    QLabel[typography="meta"] {{
        color: {neutral.text_muted};
        font-size: {type_.meta_size}px;
    }}
    QLabel[typography="metric-value"] {{
        color: {neutral.text_primary};
        font-size: {type_.metric_value_size}px;
        font-weight: {type_.metric_value_weight};
    }}
    QLabel[typography="metric-label"] {{
        color: {neutral.text_secondary};
        font-size: {type_.meta_size}px;
    }}
    QLabel[typography="empty-state"] {{
        color: {neutral.text_muted};
        font-size: {type_.body_size}px;
    }}
    QLabel:disabled {{
        color: {neutral.text_disabled};
    }}

    /* --- Surfaces (DESIGN.md § 11.1 surface hierarchy) -------------- */
    QFrame[surface="panel"] {{
        background-color: {neutral.surface_primary};
        border: 1px solid {neutral.border_subtle};
        border-radius: {metrics.radius}px;
    }}
    QFrame[surface="tile"] {{
        background-color: {neutral.surface_primary};
        border: 1px solid {neutral.border_subtle};
        border-radius: {metrics.radius}px;
    }}
    QFrame[surface="accent-tile"] {{
        background-color: {accent.soft.background};
        border: 1px solid {accent.border};
        border-radius: {metrics.radius}px;
    }}
    QFrame[surface="accent-tile"] QLabel[typography="metric-value"],
    QFrame[surface="accent-tile"] QLabel[typography="metric-label"] {{
        color: {accent.soft.foreground};
    }}
    QFrame[surface="divider"] {{
        background-color: {neutral.border_subtle};
        border: none;
        max-height: 1px;
        min-height: 1px;
    }}

    /* --- Application shell / navigation ----------------------------- */
    QToolBar {{
        background-color: {neutral.surface_primary};
        border: none;
        border-bottom: 1px solid {neutral.border_default};
        spacing: {metrics.space_xs}px;
        padding: {metrics.space_sm}px {metrics.space_lg}px;
    }}
    QToolBar::separator {{
        background-color: {neutral.border_subtle};
        width: 1px;
        margin: {metrics.space_xs}px {metrics.space_sm}px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {neutral.text_secondary};
        border: 1px solid transparent;
        border-radius: {metrics.radius}px;
        padding: {metrics.space_xs}px {metrics.space_md}px;
        min-height: {metrics.control_height - 10}px;
        font-weight: 500;
    }}
    QToolButton:hover {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_subtle};
    }}
    /* Current location is visually distinct from hover, never collapsed
       into the same treatment (DESIGN.md § 16 Navigation). */
    QToolButton:checked {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
        font-weight: 600;
    }}
    QToolButton:pressed {{
        background-color: {accent.pressed.background};
        color: {accent.pressed.foreground};
        border: 1px solid {accent.pressed.background};
    }}
    QToolButton:disabled {{
        background-color: transparent;
        color: {neutral.text_disabled};
        border: 1px solid transparent;
    }}

    /* --- Management table grammar (DESIGN.md § 16 Tables) ----------- */
    QTableView {{
        background-color: {neutral.surface_primary};
        alternate-background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        gridline-color: transparent;
        border: 1px solid {neutral.border_subtle};
        border-radius: {metrics.radius}px;
        selection-background-color: {accent.soft.background};
        selection-color: {accent.soft.foreground};
    }}
    QTableView::item {{
        padding: {metrics.space_sm}px {metrics.space_md}px;
        border: none;
        border-bottom: 1px solid {neutral.border_subtle};
        /* Reserve the selection marker's width on every row so selecting
           a row shifts nothing horizontally. */
        border-left: 3px solid transparent;
    }}
    QTableView::item:hover {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_primary};
    }}
    /* Selection reads as shape + color, not color alone, so it stays
       legible for colorblind users (DESIGN.md § 16 Tables). */
    QTableView::item:selected {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border-left: 3px solid {accent.primary.background};
    }}
    QHeaderView {{
        background-color: {neutral.surface_secondary};
        border: none;
    }}
    QHeaderView::section {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_secondary};
        border: none;
        border-bottom: 1px solid {neutral.border_default};
        padding: {metrics.space_sm}px {metrics.space_md}px;
        font-size: {type_.section_heading_size}px;
        font-weight: {type_.section_heading_weight};
    }}
    QTableView QTableCornerButton::section {{
        background-color: {neutral.surface_secondary};
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {neutral.border_default};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {neutral.border_strong};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    /* --- Buttons (DESIGN.md § 16 Buttons) --------------------------- */
    /* Secondary/default: outlined neutral. */
    QPushButton {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {metrics.radius}px;
        padding: 0px {metrics.space_lg}px;
        min-height: {metrics.control_height}px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_strong};
    }}
    QPushButton:pressed {{
        background-color: {accent.pressed.background};
        color: {accent.pressed.foreground};
        border: 1px solid {accent.pressed.background};
    }}
    QPushButton:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    /* Primary: filled accent -- one per surface, restrained (§ 14). */
    QPushButton[variant="primary"] {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: 1px solid {accent.primary.background};
        font-weight: 600;
    }}
    QPushButton[variant="primary"]:hover {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
        border: 1px solid {accent.hover.background};
    }}
    QPushButton[variant="primary"]:pressed {{
        background-color: {accent.pressed.background};
        color: {accent.pressed.foreground};
        border: 1px solid {accent.pressed.background};
    }}
    QPushButton[variant="primary"]:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    /* Subtle: text-only, for tertiary actions. */
    QPushButton[variant="subtle"] {{
        background-color: transparent;
        color: {accent.primary.background};
        border: 1px solid transparent;
        font-weight: 500;
    }}
    QPushButton[variant="subtle"]:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid transparent;
    }}
    QPushButton[variant="subtle"]:disabled {{
        background-color: transparent;
        color: {neutral.text_disabled};
        border: 1px solid transparent;
    }}
    /* Destructive stays outlined, never the loudest control (§ 5). */
    QPushButton[variant="destructive"], QPushButton[destructive="true"] {{
        color: {danger.background};
        background-color: {neutral.surface_primary};
        border: 1px solid {danger.background};
    }}

    /* --- Inputs ----------------------------------------------------- */
    QLineEdit {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {metrics.radius}px;
        padding: 0px {metrics.space_md}px;
        min-height: {metrics.control_height}px;
        selection-background-color: {accent.primary.background};
        selection-color: {accent.primary.foreground};
    }}
    QLineEdit:focus {{
        border: 1px solid {accent.border};
    }}
    QLineEdit:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}

    /* --- Status pills ----------------------------------------------- */
    QLabel[pill="neutral"] {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_secondary};
        border: 1px solid {neutral.border_subtle};
        border-radius: {metrics.radius}px;
        padding: {metrics.space_xs}px {metrics.space_sm}px;
        font-size: {type_.meta_size}px;
    }}
    QLabel[pill="accent"] {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
        border-radius: {metrics.radius}px;
        padding: {metrics.space_xs}px {metrics.space_sm}px;
        font-size: {type_.meta_size}px;
    }}
    QLabel[pill="warning"] {{
        background-color: {semantic.warning_soft};
        color: {semantic.warning.background};
        border: 1px solid {semantic.warning.background};
        border-radius: {metrics.radius}px;
        padding: {metrics.space_xs}px {metrics.space_sm}px;
        font-size: {type_.meta_size}px;
    }}
    QToolTip {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        padding: {metrics.space_xs}px {metrics.space_sm}px;
    }}
    """.strip()


class ThemeManager:
    """Single apply point for (Appearance, Accent) -> QPalette + QSS."""

    def __init__(self, application: QApplication) -> None:
        self._application = application
        self._current: tuple[Appearance, Accent] | None = None

    @property
    def current(self) -> tuple[Appearance, Accent] | None:
        return self._current

    def apply(self, appearance: Appearance, accent: Accent) -> ThemeTokens:
        tokens = resolve_tokens(appearance, accent)
        self._application.setPalette(build_palette(tokens))
        self._application.setStyleSheet(build_stylesheet(tokens))
        self._current = (appearance, accent)
        return tokens

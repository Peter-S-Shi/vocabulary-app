from __future__ import annotations

from enum import Enum

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from src.ui_desktop.theming.metrics import RADIUS_DEFAULT, SPACING
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
    """Application-level QSS for custom-drawn components (§ 14).

    Covers what the M16.2 vertical slice draws beyond native
    QPalette-resolved chrome: selected-row emphasis in the Entries table
    (accent-soft background/foreground, per DESIGN.md § 16 selection rule),
    outlined-danger buttons per DESIGN.md § 16, and explicit toolbar-action
    (``QToolButton``) colors.

    The ``QToolButton`` rule exists specifically because, once
    ``QApplication.setStyleSheet()`` is set at all, Qt's style-sheet engine
    takes over painting for every widget application-wide; any widget left
    without an explicit color in the sheet can silently lose its
    QPalette-resolved foreground and render as low-contrast/disabled-
    looking instead of falling back to the palette. This was found during
    the M16.2 human visual-acceptance pass: the Management-mode Today/
    Entries navigation actions (``QToolButton``s inside ``QToolBar``)
    rendered with extremely low contrast. Every ``QToolButton`` state below
    resolves an explicit, paired foreground token, mirroring DESIGN.md § 9's
    foreground-pair rule and § 11.4's "always resolve an explicit
    foreground" requirement -- the same class of bug DESIGN.md § 11.4
    already documents for unstyled table rows and status pills.

    The M17 Today Command Center / shared Management Rail rules below
    (``#nav-rail-item``, ``#today-*``) follow the same explicit-
    foreground-pair discipline for the same reason: any of these
    custom-drawn widgets left unstyled would silently fall through to an
    unstyled default under the same style-sheet-engine takeover.
    """
    neutral = tokens.neutral
    accent = tokens.accent
    semantic = tokens.semantic
    danger = tokens.semantic.danger
    radius = RADIUS_DEFAULT
    sp = SPACING

    return f"""
    QTableView {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        gridline-color: {neutral.border_subtle};
        selection-background-color: {accent.soft.background};
        selection-color: {accent.soft.foreground};
        border: 1px solid {neutral.border_default};
    }}
    QHeaderView::section {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_secondary};
        border: 1px solid {neutral.border_default};
        padding: 4px;
    }}
    QToolBar {{
        background-color: {neutral.surface_secondary};
        border-bottom: 1px solid {neutral.border_default};
        spacing: 6px;
        padding: 4px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {neutral.text_primary};
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px 10px;
    }}
    QToolButton:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
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
    QPushButton[destructive="true"] {{
        color: {danger.background};
        background-color: {neutral.surface_primary};
        border: 1px solid {danger.background};
        border-radius: 4px;
        padding: 4px 10px;
    }}
    #nav-rail {{
        background-color: {neutral.surface_secondary};
        border-right: 1px solid {neutral.border_default};
    }}
    QPushButton#nav-rail-item {{
        background-color: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
        padding: 0px 2px;
    }}
    QPushButton#nav-rail-item:hover:enabled {{
        background-color: {accent.soft.background};
    }}
    QPushButton#nav-rail-item:checked {{
        background-color: {neutral.surface_primary};
        border-left: 3px solid {accent.primary.background};
    }}
    QLabel#nav-rail-mark {{
        background-color: transparent;
        border: 1.5px solid {neutral.border_strong};
        border-radius: 4px;
    }}
    QPushButton#nav-rail-item:hover:enabled QLabel#nav-rail-mark {{
        border-color: {accent.border};
    }}
    QPushButton#nav-rail-item:checked QLabel#nav-rail-mark {{
        background-color: {accent.primary.background};
        border-color: {accent.primary.background};
    }}
    QPushButton#nav-rail-item:disabled QLabel#nav-rail-mark {{
        border-color: {neutral.border_subtle};
    }}
    QLabel#nav-rail-label {{
        background-color: transparent;
        color: {neutral.text_secondary};
        font-size: 10px;
    }}
    QPushButton#nav-rail-item:checked QLabel#nav-rail-label {{
        color: {neutral.text_primary};
        font-weight: 600;
    }}
    QPushButton#nav-rail-item:disabled QLabel#nav-rail-label {{
        color: {neutral.text_disabled};
    }}
    QLabel#today-page-title {{
        color: {neutral.text_primary};
        font-size: 20px;
        font-weight: 700;
    }}
    QLabel#today-date {{
        color: {neutral.text_secondary};
    }}
    QLabel#today-section-heading {{
        color: {neutral.text_secondary};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#today-context-heading {{
        color: {neutral.text_secondary};
        font-size: 12px;
        font-weight: 600;
    }}
    QWidget#today-summary-card {{
        background-color: {neutral.surface_secondary};
        border: 1px solid {neutral.border_subtle};
        border-radius: {radius}px;
    }}
    QLabel#today-summary-caption {{
        color: {neutral.text_muted};
        font-size: 11px;
    }}
    QLabel#today-summary-value {{
        color: {neutral.text_primary};
        font-size: 18px;
        font-weight: 700;
    }}
    QWidget#today-queue-card {{
        background-color: {neutral.surface_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
    }}
    QLabel#today-action-title {{
        color: {neutral.text_primary};
        font-weight: 600;
        font-size: 12px;
    }}
    QLabel#today-action-subtitle {{
        color: {neutral.text_secondary};
        font-size: 11px;
    }}
    QPushButton#today-action-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 4px 10px;
    }}
    QPushButton#today-action-button:hover:enabled {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QPushButton#today-action-button:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QWidget#today-suggested-tile {{
        background-color: {neutral.surface_secondary};
        border: 1px solid {neutral.border_subtle};
        border-radius: {radius}px;
    }}
    QLabel#today-tile-title {{
        color: {neutral.text_primary};
        font-weight: 600;
        font-size: 12px;
    }}
    QLabel#today-tile-subtitle {{
        color: {neutral.text_secondary};
        font-size: 11px;
    }}
    QPushButton#today-tile-button {{
        background-color: {neutral.surface_primary};
        color: {accent.primary.background};
        border: 1px solid {accent.border};
        border-radius: {radius}px;
        padding: 3px 10px;
        font-size: 11px;
    }}
    QPushButton#today-tile-button:hover:enabled {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
    }}
    QPushButton#today-tile-button:disabled {{
        background-color: transparent;
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QWidget#today-context-rail {{
        background-color: {neutral.surface_secondary};
        border-left: 1px solid {neutral.border_default};
    }}
    QWidget#today-context-divider {{
        background-color: {neutral.border_subtle};
    }}
    QLabel#today-activity-title {{
        color: {neutral.text_primary};
        font-weight: 600;
        font-size: 12px;
    }}
    QLabel#today-activity-subtitle {{
        color: {neutral.text_muted};
        font-size: 11px;
    }}
    QLabel#today-attention-chip {{
        background-color: {semantic.warning_soft};
        color: {semantic.warning.background};
        border-radius: {radius}px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
    }}
    QPushButton#today-quick-action {{
        background-color: transparent;
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px 10px;
    }}
    QPushButton#today-quick-action:hover:enabled {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QPushButton#today-quick-action:disabled {{
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QLabel#today-empty-state {{
        color: {neutral.text_muted};
        font-style: italic;
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

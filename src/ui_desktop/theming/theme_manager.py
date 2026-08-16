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

    The M17 Today feature is this application's first real use of
    ``QPushButton``; its rules (including the ``disabled`` state and the
    ``primary="true"`` filled-accent variant per DESIGN.md § 16 Buttons)
    are added here proactively, applying that same lesson before a first
    use rather than after a second contrast defect is found. The
    ``today-panel`` / ``today-page-title`` / label ``role`` rules give
    Today's Command Center panels and secondary/muted text explicit,
    paired foregrounds for the same reason.
    """
    neutral = tokens.neutral
    accent = tokens.accent
    danger = tokens.semantic.danger

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
    QPushButton {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: 4px;
        padding: 4px 12px;
    }}
    QPushButton:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
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
    QPushButton[primary="true"] {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: 1px solid {accent.primary.background};
    }}
    QPushButton[primary="true"]:hover {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
        border: 1px solid {accent.hover.background};
    }}
    QPushButton[primary="true"]:pressed {{
        background-color: {accent.pressed.background};
        color: {accent.pressed.foreground};
        border: 1px solid {accent.pressed.background};
    }}
    QPushButton[primary="true"]:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QFrame#today-panel {{
        background-color: {neutral.surface_secondary};
        border: 1px solid {neutral.border_default};
        border-radius: 6px;
    }}
    QLabel#today-page-title {{
        color: {neutral.text_primary};
        font-weight: 600;
    }}
    QLabel[role="secondary"] {{
        color: {neutral.text_secondary};
    }}
    QLabel[role="muted"] {{
        color: {neutral.text_muted};
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

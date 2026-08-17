from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from src.ui_desktop.theming.metrics import RADIUS_DEFAULT, SPACING
from src.ui_desktop.theming.system_appearance import detect_system_color_scheme
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

M17 Theme Completion & Cross-Screen Validation closes the Appearance axis:
``System`` now resolves through a real, live OS Light/Dark read
(``system_appearance.detect_system_color_scheme``) instead of the M16.2
placeholder that always resolved to Light, and ``ThemeManager.apply()`` is
now safely re-callable at any point during a running session -- Settings'
Appearance control and a live OS appearance change (while ``System`` is
selected) both drive re-application through this same single call site,
never a second theme-switch mechanism.
"""

LOGGER = logging.getLogger("vocabulary_app.ui")


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

    Reads the OS's current appearance live, every call, through Qt's own
    ``QStyleHints.colorScheme()`` abstraction (``system_appearance.py``).
    If the platform cannot report an appearance (``Qt.ColorScheme.
    Unknown`` -- an unsupported platform/Qt build, not an error), this
    falls back to ``Light`` explicitly and logs the fallback rather than
    silently pretending ``System`` detection succeeded (M17 Theme
    Completion prompt § 7).
    """
    if appearance is not Appearance.SYSTEM:
        return appearance
    scheme = detect_system_color_scheme()
    if scheme == Qt.ColorScheme.Dark:
        return Appearance.DARK
    if scheme == Qt.ColorScheme.Light:
        return Appearance.LIGHT
    LOGGER.warning(
        "Could not detect the OS Light/Dark appearance (Qt reported ColorScheme.Unknown); "
        "falling back to Light for the System appearance preference."
    )
    return Appearance.LIGHT


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
        font-size: 11px;
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

    /* Study Mode / Review -- Immersive Focus (DESIGN.md § 6.3, `VR-STUDY-001`).
    Visual-calibration corrective pass: font-family set once here on the two
    Study root containers so every descendant Label/Button/LineEdit/
    RadioButton/ComboBox inherits it via Qt's normal font-inheritance chain
    (the QSS rule below never needs repeating per-widget) -- a robust
    Windows-native pairing (no bundled font dependency) chosen so English and
    CJK text read as one coherent Study typeface rather than two visually
    disconnected fallbacks. */
    QWidget#review-root, QWidget#quiz-root {{
        font-family: "Segoe UI", "Segoe UI Variable", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    }}
    QWidget#review-session-bar {{
        background-color: {neutral.surface_secondary};
        border-bottom: 1px solid {neutral.border_default};
    }}
    QScrollArea#review-main-scroll, QScrollArea#review-main-scroll > QWidget#qt_scrollarea_viewport,
    QScrollArea#quiz-main-scroll, QScrollArea#quiz-main-scroll > QWidget#qt_scrollarea_viewport {{
        background-color: transparent;
        border: none;
    }}
    QPushButton#review-exit-button {{
        background-color: transparent;
        border: none;
        color: {neutral.text_secondary};
        font-size: 13px;
        padding: 4px 8px;
    }}
    QPushButton#review-exit-button:hover {{
        color: {neutral.text_primary};
    }}
    QLabel#review-context-label {{
        color: {neutral.text_primary};
        font-size: 14px;
        font-weight: 600;
    }}
    QLabel#review-progress-label {{
        color: {neutral.text_secondary};
        font-size: 13px;
    }}
    QPushButton#review-drawer-toggle {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: 12px;
        padding: 4px 14px;
    }}
    QPushButton#review-drawer-toggle:checked {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QPushButton#review-drawer-toggle:disabled {{
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QLabel#review-term-label {{
        color: {neutral.text_primary};
        font-size: 42px;
        font-weight: 700;
    }}
    QLabel#review-field-caption {{
        color: {neutral.text_muted};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#review-field-text {{
        color: {neutral.text_secondary};
        font-size: 19px;
    }}
    QPushButton#review-nav-previous {{
        background-color: transparent;
        border: none;
        color: {neutral.text_secondary};
        font-size: 14px;
        padding: 6px 12px;
    }}
    QPushButton#review-nav-previous:hover:enabled {{
        color: {neutral.text_primary};
    }}
    QPushButton#review-nav-previous:disabled {{
        color: {neutral.text_disabled};
    }}
    QPushButton#review-nav-next {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 9px 24px;
        font-size: 15px;
        font-weight: 600;
    }}
    QPushButton#review-nav-next:hover:enabled {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QPushButton#review-nav-next:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QPushButton#review-quick-quiz-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 7px 18px;
        font-size: 14px;
        font-weight: 600;
    }}
    QPushButton#review-quick-quiz-button:hover:enabled {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QPushButton#review-quick-quiz-button:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QPushButton#review-choose-quiz-type-button {{
        background-color: transparent;
        border: none;
        color: {accent.primary.background};
        font-size: 14px;
    }}
    QPushButton#review-choose-quiz-type-button:hover {{
        color: {accent.hover.background};
    }}
    QLabel#review-safety-caption {{
        color: {neutral.text_muted};
        font-size: 12px;
        font-style: italic;
    }}
    QLabel#review-empty-state {{
        color: {neutral.text_muted};
        font-style: italic;
    }}
    QPushButton#review-empty-open-entries {{
        background-color: transparent;
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px 14px;
    }}
    QPushButton#review-empty-open-entries:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QWidget#review-drawer {{
        background-color: {neutral.surface_secondary};
        border-left: 1px solid {neutral.border_default};
    }}
    QLabel#review-drawer-header {{
        color: {neutral.text_primary};
        font-weight: 600;
        font-size: 16px;
    }}
    QPushButton#review-drawer-close {{
        background-color: transparent;
        border: none;
        color: {neutral.text_secondary};
        font-size: 15px;
        font-weight: 700;
    }}
    QPushButton#review-drawer-close:hover {{
        color: {neutral.text_primary};
    }}
    QPushButton#review-drawer-entry {{
        background-color: transparent;
        border: none;
        text-align: left;
        color: {neutral.text_secondary};
        font-size: 14px;
        padding: 6px 8px;
    }}
    QPushButton#review-drawer-entry:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
    }}
    QPushButton#review-drawer-entry-current {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: none;
        border-left: 3px solid {accent.primary.background};
        border-radius: {radius}px;
        text-align: left;
        font-size: 14px;
        padding: 6px 8px;
        font-weight: 700;
    }}
    QWidget#review-drawer-divider {{
        background-color: {neutral.border_subtle};
    }}
    QLabel#review-drawer-history-heading {{
        color: {neutral.text_secondary};
        font-weight: 600;
        font-size: 13px;
    }}
    QLabel#review-drawer-history-row {{
        color: {neutral.text_muted};
        font-size: 12px;
    }}
    QPushButton#review-drawer-browse-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px;
    }}
    QPushButton#review-drawer-browse-button:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QLabel#review-selector-warning {{
        color: {danger.background};
        font-size: 11px;
    }}

    /* P6 Utility / Dialog baseline (`VR-UTILITY-001`) -- the first QDialogs
    in the desktop app; styled explicitly for the same reason every other
    custom-drawn widget above is (module docstring: an unstyled widget
    under a global QApplication stylesheet silently loses its
    QPalette-resolved foreground rather than falling back to it). */
    QDialog {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
    }}
    QDialog QLabel {{
        color: {neutral.text_primary};
        font-size: 13px;
    }}
    QDialog QComboBox {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 4px 8px;
    }}
    QDialog QPushButton {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px 14px;
    }}
    QDialog QPushButton:hover:enabled {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QDialog QPushButton:disabled {{
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QPushButton#review-selector-select-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
    }}
    QPushButton#review-selector-select-button:hover:enabled {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QPushButton#review-choose-quiz-type-start-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
    }}
    QPushButton#review-choose-quiz-type-start-button:hover:enabled {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QDialog QCheckBox {{
        color: {neutral.text_primary};
    }}
    QDialog QLineEdit {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 4px 8px;
    }}

    /* Quiz -- Immersive Focus (DESIGN.md § 6.3, `VR-STUDY-001`; M17 Feature 3) */
    QWidget#quiz-session-bar {{
        background-color: {neutral.surface_secondary};
        border-bottom: 1px solid {neutral.border_default};
    }}
    QPushButton#quiz-exit-button {{
        background-color: transparent;
        border: none;
        color: {neutral.text_secondary};
        font-size: 13px;
        padding: 4px 8px;
    }}
    QPushButton#quiz-exit-button:hover {{
        color: {neutral.text_primary};
    }}
    QLabel#quiz-context-label {{
        color: {neutral.text_primary};
        font-size: 14px;
        font-weight: 600;
    }}
    QLabel#quiz-progress-label {{
        color: {neutral.text_secondary};
        font-size: 13px;
    }}
    QLabel#quiz-term-label {{
        color: {neutral.text_primary};
        font-size: 42px;
        font-weight: 700;
    }}
    QLineEdit#quiz-answer-input {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 12px 16px;
        font-size: 20px;
        min-height: 24px;
    }}
    QLineEdit#quiz-answer-input:focus {{
        border: 1px solid {accent.border};
    }}
    QLineEdit#quiz-answer-input:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_secondary};
    }}
    QLabel#quiz-field-caption {{
        color: {neutral.text_muted};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#quiz-field-text {{
        color: {neutral.text_secondary};
        font-size: 19px;
    }}
    QPushButton#quiz-show-answer-button,
    QPushButton#quiz-mcq-submit-button,
    QPushButton#quiz-mcq-next-button,
    QPushButton#quiz-matching-submit-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 10px 26px;
        font-size: 15px;
        font-weight: 600;
    }}
    QPushButton#quiz-show-answer-button:hover:enabled,
    QPushButton#quiz-mcq-submit-button:hover:enabled,
    QPushButton#quiz-mcq-next-button:hover:enabled,
    QPushButton#quiz-matching-submit-button:hover:enabled {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QPushButton#quiz-matching-submit-button:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QPushButton#quiz-grade-correct-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 2px solid {neutral.text_primary};
        border-radius: {radius}px;
        padding: 8px 24px;
        font-size: 15px;
        font-weight: 700;
    }}
    QPushButton#quiz-grade-correct-button:hover {{
        background-color: {semantic.quiz_correct_soft};
        border-color: {semantic.quiz_correct.background};
        color: {semantic.quiz_correct.background};
    }}
    QPushButton#quiz-grade-wrong-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_secondary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 9px 25px;
        font-size: 15px;
        font-weight: 600;
    }}
    QPushButton#quiz-grade-wrong-button:hover {{
        background-color: {semantic.quiz_wrong_soft};
        border-color: {semantic.quiz_wrong.background};
        color: {semantic.quiz_wrong.background};
    }}
    QRadioButton#quiz-mcq-option {{
        color: {neutral.text_primary};
        font-size: 16px;
        padding: 8px 4px;
    }}
    QRadioButton#quiz-mcq-option::indicator {{
        width: 18px;
        height: 18px;
    }}
    QLabel#quiz-feedback-correct {{
        color: {semantic.quiz_correct.background};
        font-size: 20px;
        font-weight: 700;
    }}
    QLabel#quiz-feedback-wrong {{
        color: {semantic.quiz_wrong.background};
        font-size: 20px;
        font-weight: 700;
    }}
    QLabel#quiz-matching-heading {{
        color: {neutral.text_secondary};
        font-size: 14px;
        font-weight: 600;
    }}
    QWidget#quiz-matching-row {{
        background-color: {neutral.surface_secondary};
        border: 1px solid {neutral.border_subtle};
        border-radius: {radius}px;
    }}
    QLabel#quiz-matching-term-label {{
        color: {neutral.text_primary};
        font-size: 15px;
        font-weight: 600;
        padding: 8px 10px;
    }}
    QComboBox#quiz-matching-combo {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px 10px;
        font-size: 14px;
    }}
    QLabel#quiz-completion-title {{
        color: {neutral.text_primary};
        font-size: 26px;
        font-weight: 700;
    }}
    QLabel#quiz-completion-stat-value {{
        color: {neutral.text_primary};
        font-size: 36px;
        font-weight: 700;
    }}
    QLabel#quiz-completion-stat-label {{
        color: {neutral.text_muted};
        font-size: 12px;
    }}
    QWidget#quiz-completion-divider {{
        background-color: {neutral.border_subtle};
    }}
    QLabel#quiz-completion-mistakes-heading {{
        color: {neutral.text_secondary};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#quiz-completion-mistakes-list {{
        color: {neutral.text_primary};
        font-size: 15px;
    }}
    QPushButton#quiz-completion-return-today-button,
    QPushButton#quiz-completion-next-card-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 8px 16px;
        font-size: 14px;
    }}
    QPushButton#quiz-completion-return-today-button:hover,
    QPushButton#quiz-completion-next-card-button:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QPushButton#quiz-completion-review-mistakes-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 8px 16px;
        font-size: 14px;
        font-weight: 600;
    }}
    QPushButton#quiz-completion-review-mistakes-button:hover {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QLabel#quiz-mistake-position-label {{
        color: {neutral.text_secondary};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#quiz-mistake-context-label {{
        color: {neutral.text_muted};
        font-size: 13px;
    }}
    QPushButton#quiz-mistake-previous-button {{
        background-color: transparent;
        border: none;
        color: {neutral.text_secondary};
        font-size: 14px;
        padding: 6px 12px;
    }}
    QPushButton#quiz-mistake-previous-button:hover:enabled {{
        color: {neutral.text_primary};
    }}
    QPushButton#quiz-mistake-previous-button:disabled {{
        color: {neutral.text_disabled};
    }}
    QPushButton#quiz-mistake-next-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 8px 20px;
        font-size: 14px;
        font-weight: 600;
    }}
    QPushButton#quiz-mistake-next-button:hover:enabled {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QPushButton#quiz-mistake-next-button:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QPushButton#quiz-mistake-back-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 8px 16px;
        font-size: 14px;
    }}
    QPushButton#quiz-mistake-back-button:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QLabel#quiz-blocked-message, QLabel#quiz-error-message, QLabel#quiz-empty-state {{
        color: {neutral.text_secondary};
        font-size: 14px;
    }}
    QPushButton#quiz-blocked-cancel-button {{
        background-color: {neutral.surface_primary};
        color: {danger.background};
        border: 1px solid {danger.background};
        border-radius: {radius}px;
        padding: 8px 16px;
        font-size: 14px;
    }}
    QPushButton#quiz-blocked-cancel-button:hover {{
        background-color: {semantic.danger_soft};
    }}
    QLabel#quiz-exit-confirm-message {{
        color: {neutral.text_secondary};
        font-size: 14px;
    }}

    /* Flip Card + Filmstrip -- VR-STUDY-002 (M17 Feature 3B, DESIGN.md
    § 6.4, `Review - Quiz.pdf` p5 Variant D). Front/revealed reuse the same
    strong-border card silhouette the canonical reference uses for both
    Review and Quiz; only the fill distinguishes an unanswered prompt from
    a revealed answer/feedback state, matching Review's own front/back
    treatment. Inner content (term/answer-input/field-caption/field-text/
    grade/MCQ buttons) intentionally reuses the exact Immersive Focus
    object names/tokens above -- the card adapts to that content rather
    than shrinking it (M17 Feature 3B prompt § 11). */
    QWidget#quiz-flip-card-front, QWidget#quiz-flip-card-revealed {{
        border: 2px solid {neutral.border_strong};
        border-radius: {radius * 2}px;
        min-width: 380px;
    }}
    QWidget#quiz-flip-card-front {{
        background-color: {neutral.surface_primary};
    }}
    QWidget#quiz-flip-card-revealed {{
        background-color: {neutral.surface_secondary};
    }}
    QWidget#quiz-filmstrip {{
        background-color: {neutral.surface_secondary};
        border: 1px solid {neutral.border_subtle};
        border-radius: {radius}px;
    }}
    QLabel#quiz-filmstrip-tile-future {{
        color: {neutral.text_muted};
        border: 1px solid {neutral.border_subtle};
        border-radius: {radius}px;
        padding: 4px 10px;
        font-size: 12px;
    }}
    QLabel#quiz-filmstrip-tile-current {{
        color: {neutral.text_primary};
        background-color: {neutral.surface_primary};
        border: 2px solid {neutral.text_primary};
        border-radius: {radius}px;
        padding: 3px 9px;
        font-size: 12px;
        font-weight: 700;
    }}
    QLabel#quiz-filmstrip-tile-correct {{
        color: {semantic.quiz_correct.background};
        border: 1px solid {neutral.border_subtle};
        border-radius: {radius}px;
        padding: 4px 10px;
        font-size: 12px;
    }}
    QLabel#quiz-filmstrip-tile-wrong {{
        color: {semantic.quiz_wrong.background};
        border: 1px solid {neutral.border_subtle};
        border-radius: {radius}px;
        padding: 4px 10px;
        font-size: 12px;
    }}

    /* Settings -- P8 Settings Form (DESIGN.md § 8), M17 Feature 3B bounded
    vertical slice: Quiz presentation only. */
    QLabel#settings-page-title {{
        color: {neutral.text_primary};
        font-size: 20px;
        font-weight: 700;
    }}
    QLabel#settings-section-heading {{
        color: {neutral.text_secondary};
        font-size: 13px;
        font-weight: 600;
    }}
    QWidget#settings-row {{
        background-color: {neutral.surface_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
    }}
    QLabel#settings-row-label {{
        color: {neutral.text_primary};
        font-size: 14px;
    }}
    QComboBox#settings-quiz-presentation-combo, QComboBox#settings-appearance-combo {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px 10px;
        font-size: 14px;
        min-width: 200px;
    }}

    /* Entries -- Table-First Manager (DESIGN.md § 6.2 `VR-ENTRIES-001`,
    M17 Feature 4). Ordinary Management Mode workspace -- Management Rail
    stays visible, no Study-mode chrome swap.

    Corrective pass (M17_Feature4_Entries_Corrective_Pass.md): typography
    recalibrated against the canonical hierarchy (workspace/title > table
    content > toolbar/scope navigation > detail values > muted metadata),
    a resizable Scope/Table `QSplitter` replaces the rigid fixed-width
    pane, batch actions moved to their own conditional row so search
    keeps a usable minimum width, explicit checkbox-column/selected-row/
    header-checkbox styling makes native multi-selection visible, and
    `QMenu` gets its own explicit rule -- the "Add to Collection" menu
    previously inherited only the bare QPalette once the application
    stylesheet was set, which human review correctly read as looking
    unavailable even though every enabled action was fully clickable
    (§ 6/§ 12 of that prompt). */
    QSplitter#entries-splitter::handle {{
        background-color: {neutral.border_default};
    }}
    QSplitter#entries-splitter::handle:hover {{
        background-color: {accent.border};
    }}
    QWidget#entries-scope-pane {{
        background-color: {neutral.surface_secondary};
        border-right: 1px solid {neutral.border_default};
    }}
    QLabel#entries-scope-heading {{
        color: {neutral.text_muted};
        font-size: 11px;
        font-weight: 700;
        padding: 6px 8px 2px 8px;
    }}
    QWidget#entries-scope-divider {{
        background-color: {neutral.border_subtle};
    }}
    QPushButton#entries-scope-item {{
        background-color: transparent;
        border: none;
        border-left: 3px solid transparent;
        text-align: left;
        color: {neutral.text_secondary};
        font-size: 13px;
        padding: 6px 8px;
        border-radius: 0px;
    }}
    QPushButton#entries-scope-item:hover:enabled {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
    }}
    QPushButton#entries-scope-item:checked {{
        background-color: {neutral.surface_primary};
        border-left: 3px solid {accent.primary.background};
        color: {neutral.text_primary};
        font-weight: 600;
    }}
    QLabel#entries-title {{
        color: {neutral.text_primary};
        font-size: 21px;
        font-weight: 700;
    }}
    QLineEdit#entries-search-input {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px 10px;
        font-size: 14px;
    }}
    QLineEdit#entries-search-input:focus {{
        border: 1px solid {accent.border};
    }}
    QComboBox#entries-language-filter, QComboBox#entries-entry-type-filter, QComboBox#entries-status-filter {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 5px 8px;
        font-size: 13px;
    }}
    QWidget#entries-batch-bar {{
        background-color: {accent.soft.background};
        border: 1px solid {accent.border};
        border-radius: {radius}px;
    }}
    QLabel#entries-batch-count-label {{
        color: {accent.soft.foreground};
        font-size: 13px;
        font-weight: 600;
        padding: 4px 10px;
    }}
    QPushButton#entries-batch-star-button,
    QPushButton#entries-batch-collection-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 5px 10px;
        font-size: 13px;
    }}
    QPushButton#entries-batch-star-button:hover,
    QPushButton#entries-batch-collection-button:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QPushButton#entries-batch-delete-button {{
        background-color: {neutral.surface_primary};
        color: {danger.background};
        border: 1px solid {danger.background};
        border-radius: {radius}px;
        padding: 5px 10px;
        font-size: 13px;
    }}
    QPushButton#entries-batch-delete-button:hover {{
        background-color: {semantic.danger_soft};
    }}
    QPushButton#entries-quick-add-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 5px 12px;
        font-size: 13px;
    }}
    QPushButton#entries-quick-add-button:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QPushButton#entries-add-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton#entries-add-button:hover {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QTableView#entries-table {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        gridline-color: {neutral.border_subtle};
        border: 1px solid {neutral.border_default};
        font-size: 14px;
    }}
    QTableView#entries-table::item {{
        padding: 6px 8px;
    }}
    QTableView#entries-table::item:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
    }}
    QTableView#entries-table::item:selected {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        font-weight: 600;
    }}
    QTableView#entries-table QHeaderView::section {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_secondary};
        border: 1px solid {neutral.border_default};
        padding: 6px 8px;
        font-size: 12px;
        font-weight: 600;
    }}
    QWidget#entries-detail {{
        background-color: {neutral.surface_secondary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
    }}
    QLabel#entries-detail-caption {{
        color: {neutral.text_muted};
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel#entries-detail-value {{
        color: {neutral.text_primary};
        font-size: 15px;
    }}
    QLabel#entries-detail-secondary {{
        color: {neutral.text_secondary};
        font-size: 12px;
    }}
    QPushButton#entries-detail-edit-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px 16px;
        font-size: 13px;
    }}
    QPushButton#entries-detail-edit-button:hover {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QLabel#entries-empty-state {{
        color: {neutral.text_muted};
        font-style: italic;
        font-size: 13px;
    }}
    QLabel#entries-editor-collections-heading {{
        color: {neutral.text_secondary};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#entries-editor-error {{
        color: {danger.background};
        font-size: 12px;
    }}
    QPushButton#entries-editor-save-button,
    QPushButton#entries-quick-add-create-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 6px 16px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton#entries-editor-save-button:hover,
    QPushButton#entries-quick-add-create-button:hover {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QScrollArea#entries-editor-scroll {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea#entries-editor-scroll > QWidget#qt_scrollarea_viewport {{
        background-color: transparent;
    }}
    QDialog QPlainTextEdit {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 6px 8px;
        font-size: 13px;
    }}
    QMenu {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        font-size: 13px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 20px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
    }}
    QMenu::item:disabled {{
        color: {neutral.text_disabled};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {neutral.border_subtle};
        margin: 4px 0px;
    }}

    /* Today -- "Collections Needing Attention" rows become actionable
    (M17 Minimum Collection Integration prompt § 8): a clickable row
    styled consistently with the existing today-quick-action affordance. */
    QPushButton#today-attention-row {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: {radius}px;
        text-align: left;
        padding: 2px;
    }}
    QPushButton#today-attention-row:hover:enabled {{
        background-color: {accent.soft.background};
        border: 1px solid {accent.border};
    }}
    QPushButton#today-attention-row:disabled {{
        color: {neutral.text_disabled};
    }}

    /* Collections Navigator / Collection Context -- Minimum M17
    Collection Integration (DESIGN.md § 6.8, Class B). Read-only
    navigation/context surface; visual traits inherited from Entries'
    Scope Pane + detail vocabulary rather than a new visual language. */
    QWidget#collections-list-pane {{
        background-color: {neutral.surface_secondary};
        border-right: 1px solid {neutral.border_default};
    }}
    QLabel#collections-list-heading {{
        color: {neutral.text_muted};
        font-size: 11px;
        font-weight: 700;
        padding: 6px 8px 2px 8px;
    }}
    QWidget#collections-list-divider {{
        background-color: {neutral.border_subtle};
    }}
    QPushButton#collections-list-item {{
        background-color: transparent;
        border: none;
        border-left: 3px solid transparent;
        text-align: left;
        color: {neutral.text_secondary};
        font-size: 13px;
        padding: 6px 8px;
        border-radius: 0px;
    }}
    QPushButton#collections-list-item:hover:enabled {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
    }}
    QPushButton#collections-list-item:checked {{
        background-color: {neutral.surface_primary};
        border-left: 3px solid {accent.primary.background};
        color: {neutral.text_primary};
        font-weight: 600;
    }}
    QLabel#collections-title {{
        color: {neutral.text_primary};
        font-size: 21px;
        font-weight: 700;
    }}
    QLabel#collections-empty-state {{
        color: {neutral.text_muted};
        font-style: italic;
        font-size: 13px;
    }}
    QLabel#collections-detail-name {{
        color: {neutral.text_primary};
        font-size: 18px;
        font-weight: 700;
    }}
    QLabel#collections-detail-description {{
        color: {neutral.text_secondary};
        font-size: 13px;
    }}
    QLabel#collections-detail-meta {{
        color: {neutral.text_muted};
        font-size: 12px;
    }}
    QPushButton#collections-open-entries-button {{
        background-color: {accent.primary.background};
        color: {accent.primary.foreground};
        border: none;
        border-radius: {radius}px;
        padding: 6px 16px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton#collections-open-entries-button:hover:enabled {{
        background-color: {accent.hover.background};
        color: {accent.hover.foreground};
    }}
    QPushButton#collections-open-entries-button:disabled {{
        background-color: {neutral.surface_secondary};
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QLabel#collections-cards-heading {{
        color: {neutral.text_secondary};
        font-size: 13px;
        font-weight: 600;
    }}
    QWidget#collections-card-row {{
        background-color: {neutral.surface_secondary};
        border: 1px solid {neutral.border_subtle};
        border-radius: {radius}px;
    }}
    QLabel#collections-card-label {{
        color: {neutral.text_primary};
        font-size: 13px;
    }}
    QLabel#collections-card-count {{
        color: {neutral.text_muted};
        font-size: 12px;
    }}
    QPushButton#collections-open-in-study-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 4px 12px;
        font-size: 12px;
    }}
    QPushButton#collections-open-in-study-button:hover:enabled {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}

    /* Card pagination controls (M17 Minimum Collection Integration
    corrective pass § 2). Pinned above the scrollable Card page. */
    QLabel#collections-card-controls-label {{
        color: {neutral.text_muted};
        font-size: 12px;
    }}
    QComboBox#collections-card-sort-combo,
    QComboBox#collections-card-page-size-combo {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 3px 8px;
        font-size: 12px;
    }}
    QPushButton#collections-card-previous-button,
    QPushButton#collections-card-next-button {{
        background-color: {neutral.surface_primary};
        color: {neutral.text_primary};
        border: 1px solid {neutral.border_default};
        border-radius: {radius}px;
        padding: 4px 10px;
        font-size: 12px;
    }}
    QPushButton#collections-card-previous-button:hover:enabled,
    QPushButton#collections-card-next-button:hover:enabled {{
        background-color: {accent.soft.background};
        color: {accent.soft.foreground};
        border: 1px solid {accent.border};
    }}
    QPushButton#collections-card-previous-button:disabled,
    QPushButton#collections-card-next-button:disabled {{
        color: {neutral.text_disabled};
        border: 1px solid {neutral.border_subtle};
    }}
    QLabel#collections-card-page-label {{
        color: {neutral.text_secondary};
        font-size: 12px;
        font-weight: 600;
    }}
    QScrollArea#collections-card-scroll {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea#collections-card-scroll > QWidget#qt_scrollarea_viewport {{
        background-color: transparent;
    }}
    """.strip()


class ThemeManager(QObject):
    """Single apply point for (Appearance, Accent) -> QPalette + QSS.

    ``apply()`` is safely re-callable at any point during a running
    session -- both Settings' Appearance control (live explicit
    Light/Dark/System switching) and ``watch_system_appearance()``'s live
    OS-change reaction call back through this one method, never a second
    theme-switch mechanism (M17 Theme Completion prompt § 6/§ 8). Because
    every custom-drawn widget in this app is styled through the single
    application-level QSS ``build_stylesheet()`` returns (module
    docstring; every ``QToolButton``/dialog/menu/etc. rule lives there),
    re-calling ``QApplication.setStyleSheet()``/``setPalette()`` re-themes
    the entire already-rendered widget tree automatically, including
    dialogs/menus opened afterward -- no per-view re-theme wiring is
    needed for anything QSS/QPalette-driven. ``theme_applied`` exists only
    for the one narrow exception: presentation baked into custom
    ``QAbstractItemModel`` data roles (the Entries Star column's gold),
    which Qt's style engine cannot re-paint on its own.
    """

    theme_applied = Signal(object)  # emits the just-applied ThemeTokens

    def __init__(self, application: QApplication) -> None:
        super().__init__()
        self._application = application
        self._current: tuple[Appearance, Accent] | None = None
        self._current_tokens: ThemeTokens | None = None
        self._watching_system = False

    @property
    def current(self) -> tuple[Appearance, Accent] | None:
        return self._current

    @property
    def current_tokens(self) -> ThemeTokens | None:
        return self._current_tokens

    def apply(self, appearance: Appearance, accent: Accent) -> ThemeTokens:
        tokens = resolve_tokens(appearance, accent)
        self._application.setPalette(build_palette(tokens))
        self._application.setStyleSheet(build_stylesheet(tokens))
        self._current = (appearance, accent)
        self._current_tokens = tokens
        self.theme_applied.emit(tokens)
        return tokens

    def watch_system_appearance(self) -> None:
        """Opt-in, idempotent: wires a live reaction to the OS Light/Dark
        appearance changing while this manager's stored preference is
        ``System`` (M17 Theme Completion prompt § 7.3).

        Connects to Qt's own ``QStyleHints.colorSchemeChanged`` signal --
        each platform's native OS-level notification, not a polling loop
        (``system_appearance.py``). This is opt-in rather than automatic
        at construction time so constructing a ``ThemeManager`` for a
        test never silently subscribes it to a process-global Qt signal
        it did not ask to watch; the one production ``ThemeManager``
        (``app.py``) calls this once, explicitly, after its initial
        ``apply()``. Calling this more than once on the same instance is
        a safe no-op (M17 Theme Completion prompt § 18 "no duplicate
        theme manager instance/state").
        """
        if self._watching_system:
            return
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_os_color_scheme_changed)
        self._watching_system = True

    def _on_os_color_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        """Re-applies only while the *stored* preference is ``System`` --
        an OS change while an explicit Light/Dark preference is active
        must never override that explicit choice (prompt § 7.3's
        "does not override the explicit choice"). Always re-reads the
        live OS state through ``apply()`` -> ``resolve_effective_
        appearance()`` rather than trusting this signal's payload, so
        this stays correct even if multiple OS changes coalesce into one
        emission."""
        if self._current is not None and self._current[0] is Appearance.SYSTEM:
            self.apply(*self._current)

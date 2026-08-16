from __future__ import annotations

import ast
import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

"""
Structural guards for the M17 shared visual system (the reusable
typography/spacing/surface grammar in ``theming/`` and
``widgets/primitives.py``).

**These tests do not, and cannot, prove visual quality.** The first M17
human visual-acceptance pass failed while every structural Today test was
already green -- that is exactly why visual acceptance is a human gate.
What these protect is narrower and genuinely automatable: that the shared
grammar stays *shared* (no per-screen hardcoded colors or font sizes
creeping back in), that every styled interactive state resolves an
explicit foreground, and that the contrast pairs the grammar introduces
still satisfy DESIGN.md § 12.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UI_DESKTOP = PROJECT_ROOT / "src" / "ui_desktop"

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.theming.theme_manager import (
        Accent,
        Appearance,
        build_stylesheet,
        resolve_tokens,
    )
    from src.ui_desktop.theming.tokens import METRICS, TYPOGRAPHY
    from src.ui_desktop.widgets.primitives import (
        EmptyState,
        MetricTile,
        PageHeader,
        Panel,
        SectionHeading,
        StatusPill,
    )

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


def _relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance, matching the formula DESIGN.md § 12's own
    contrast audit is computed with (not a pixel-rendered measurement)."""
    hex_color = hex_color.lstrip("#")
    channels = []
    for i in (0, 2, 4):
        value = int(hex_color[i : i + 2], 16) / 255.0
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    lum_a = _relative_luminance(hex_a) + 0.05
    lum_b = _relative_luminance(hex_b) + 0.05
    return max(lum_a, lum_b) / min(lum_a, lum_b)


THEMES = (
    ("Light", Appearance.LIGHT) if PYSIDE6_AVAILABLE else (),
    ("Dark", Appearance.DARK) if PYSIDE6_AVAILABLE else (),
)


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17SharedGrammarSourceScanTests(unittest.TestCase):
    """The visual grammar must stay centralized. A screen that hardcodes
    its own hex color or font size has silently forked the design system,
    which is how the product drifted toward "default Qt with token
    colors" in the first place."""

    HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    FONT_SIZE = re.compile(r"font-size\s*:")

    def _screen_sources(self) -> list[Path]:
        return sorted((UI_DESKTOP / "views").glob("*.py")) + [
            UI_DESKTOP / "main_window.py",
            UI_DESKTOP / "widgets" / "primitives.py",
        ]

    def test_no_view_or_primitive_hardcodes_a_hex_color(self) -> None:
        offenders = []
        for path in self._screen_sources():
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if self.HEX_COLOR.search(line):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}: {line.strip()}")
        self.assertEqual(offenders, [])

    def test_no_view_or_primitive_declares_its_own_font_size(self) -> None:
        offenders = []
        for path in self._screen_sources():
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if self.FONT_SIZE.search(line):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}: {line.strip()}")
        self.assertEqual(offenders, [])

    def test_only_theme_manager_calls_set_style_sheet(self) -> None:
        """One apply point for QSS (M16.1 contract § 14). A view calling
        setStyleSheet() would bypass the shared grammar entirely."""
        offenders = []
        for path in sorted(UI_DESKTOP.rglob("*.py")):
            if path.name == "theme_manager.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "setStyleSheet"
                ):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
        self.assertEqual(offenders, [])


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17StylesheetGrammarTests(unittest.TestCase):
    """The stylesheet must actually define the component roles the
    primitives select on -- otherwise a primitive silently renders as an
    unstyled default widget, which is the failure mode this pass fixes."""

    REQUIRED_SELECTORS = (
        'QLabel[typography="page-title"]',
        'QLabel[typography="section-heading"]',
        'QLabel[typography="metric-value"]',
        'QLabel[typography="metric-label"]',
        'QLabel[typography="meta"]',
        'QLabel[typography="empty-state"]',
        'QFrame[surface="panel"]',
        'QFrame[surface="tile"]',
        'QFrame[surface="accent-tile"]',
        "QToolButton:checked",
        "QTableView::item:selected",
        "QHeaderView::section",
        'QPushButton[variant="primary"]',
        'QPushButton[variant="subtle"]',
        "QLineEdit",
    )

    def test_every_primitive_selector_role_is_styled(self) -> None:
        for label, appearance in THEMES:
            with self.subTest(theme=label):
                sheet = build_stylesheet(resolve_tokens(appearance, Accent.CALM_BLUE))
                for selector in self.REQUIRED_SELECTORS:
                    self.assertIn(selector, sheet, f"{selector} missing in {label}")

    # Text-bearing interactive controls: the widget class that produced the
    # M16.2 navigation-contrast defect. Container frames and pure chrome
    # (QToolBar, QScrollBar, corner buttons) legitimately render no text of
    # their own -- their child labels resolve their own explicit color --
    # so requiring a foreground on those would be noise, not a real guard.
    TEXT_BEARING_CONTROL = re.compile(
        r"^\s*(QToolButton|QPushButton|QLineEdit|QLabel|QHeaderView::section|QTableView)\b"
    )

    def test_every_text_bearing_control_state_resolves_an_explicit_foreground(self) -> None:
        """DESIGN.md § 9/§ 11.4: a styled state that sets a background but
        no color can inherit an unrelated default foreground -- the exact
        M16.2 navigation-contrast defect. Every state of a text-bearing
        control must therefore declare its own paired foreground rather
        than relying on inheritance."""
        for label, appearance in THEMES:
            with self.subTest(theme=label):
                sheet = build_stylesheet(resolve_tokens(appearance, Accent.CALM_BLUE))
                missing = []
                for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", sheet):
                    last_selector = selector.strip().splitlines()[-1]
                    if not self.TEXT_BEARING_CONTROL.match(last_selector):
                        continue
                    if "QTableCornerButton" in last_selector:
                        # Pure chrome: the corner button renders no text.
                        continue
                    if "background-color:" not in body:
                        continue
                    if not re.search(r"(^|[;\s])color\s*:", body):
                        missing.append(last_selector.strip())
                self.assertEqual(missing, [], f"{label}: states without explicit foreground")

    def test_disabled_states_are_styled_for_every_interactive_control(self) -> None:
        """A disabled control must stay identifiable rather than
        disappearing or keeping its enabled foreground (DESIGN.md § 12
        Muted vs. Disabled, § 16 Disabled)."""
        for label, appearance in THEMES:
            with self.subTest(theme=label):
                sheet = build_stylesheet(resolve_tokens(appearance, Accent.CALM_BLUE))
                for control in ("QToolButton:disabled", "QPushButton:disabled", "QLineEdit:disabled"):
                    self.assertIn(control, sheet, f"{label}: {control} unstyled")

    def test_navigation_checked_state_is_distinct_from_hover(self) -> None:
        """DESIGN.md § 16: hover and selected must be visually
        distinguishable, "never collapsed into one treatment"."""
        for label, appearance in THEMES:
            with self.subTest(theme=label):
                tokens = resolve_tokens(appearance, Accent.CALM_BLUE)
                sheet = build_stylesheet(tokens)
                hover = re.search(r"QToolButton:hover \{([^}]*)\}", sheet).group(1)
                checked = re.search(r"QToolButton:checked \{([^}]*)\}", sheet).group(1)
                self.assertNotEqual(hover.strip(), checked.strip())
                self.assertIn(tokens.accent.soft.background, checked)
                self.assertNotIn(tokens.accent.soft.background, hover)


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17VisualSystemContrastTests(unittest.TestCase):
    """Contrast for the token pairs this pass newly puts text on
    (DESIGN.md § 12 minimums: 4.5:1 normal text, 3:1 large text/boundaries)."""

    def test_typography_roles_meet_normal_text_minimum_on_their_surfaces(self) -> None:
        for label, appearance in THEMES:
            tokens = resolve_tokens(appearance, Accent.CALM_BLUE)
            neutral = tokens.neutral
            pairs = {
                "page-title on panel": (neutral.text_primary, neutral.surface_primary),
                "section-heading on panel": (neutral.text_secondary, neutral.surface_primary),
                "body on panel": (neutral.text_primary, neutral.surface_primary),
                "meta on panel": (neutral.text_muted, neutral.surface_primary),
                "empty-state on panel": (neutral.text_muted, neutral.surface_primary),
                "header section": (neutral.text_secondary, neutral.surface_secondary),
                "nav rest": (neutral.text_secondary, neutral.surface_primary),
            }
            for name, (foreground, background) in pairs.items():
                with self.subTest(theme=label, pair=name):
                    self.assertGreaterEqual(
                        _contrast_ratio(foreground, background), 4.5, f"{label} {name}"
                    )

    def test_accent_tile_and_selection_pairs_meet_normal_text_minimum(self) -> None:
        for label, appearance in THEMES:
            tokens = resolve_tokens(appearance, Accent.CALM_BLUE)
            accent = tokens.accent
            for name, (foreground, background) in {
                "accent tile / nav checked / row selected": (
                    accent.soft.foreground,
                    accent.soft.background,
                ),
                "primary button": (accent.primary.foreground, accent.primary.background),
                "pressed button": (accent.pressed.foreground, accent.pressed.background),
            }.items():
                with self.subTest(theme=label, pair=name):
                    self.assertGreaterEqual(
                        _contrast_ratio(foreground, background), 4.5, f"{label} {name}"
                    )

    def test_selection_marker_is_visible_against_its_own_selected_row(self) -> None:
        """Selection reads as shape + color: the accent-primary left marker
        must be distinguishable from the accent-soft row it sits on, so the
        cue survives for colorblind users (DESIGN.md § 16 Tables)."""
        for label, appearance in THEMES:
            with self.subTest(theme=label):
                accent = resolve_tokens(appearance, Accent.CALM_BLUE).accent
                self.assertGreaterEqual(
                    _contrast_ratio(accent.primary.background, accent.soft.background), 3.0
                )


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17PrimitiveConstructionTests(unittest.TestCase):
    """Primitives must set the selector properties the stylesheet keys on;
    a primitive that forgets one renders as an unstyled default widget."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_page_header_sets_title_and_subtitle_roles(self) -> None:
        header = PageHeader("Today", "subtitle text")
        self.addCleanup(header.deleteLater)
        self.assertEqual(header.title_label.property("typography"), "page-title")
        self.assertEqual(header.subtitle_label.property("typography"), "page-subtitle")
        self.assertTrue(header.subtitle_label.isVisible() or not header.isVisible())

    def test_page_header_hides_empty_subtitle(self) -> None:
        header = PageHeader("Today")
        self.addCleanup(header.deleteLater)
        self.assertFalse(header.subtitle_label.isVisibleTo(header))

    def test_section_heading_role_and_uppercase_treatment(self) -> None:
        heading = SectionHeading("Today's Learning Queue")
        self.addCleanup(heading.deleteLater)
        self.assertEqual(heading.property("typography"), "section-heading")
        self.assertEqual(heading.text(), "TODAY'S LEARNING QUEUE")

    def test_panel_uses_surface_role_and_shared_spacing(self) -> None:
        panel = Panel("Heading")
        self.addCleanup(panel.deleteLater)
        self.assertEqual(panel.property("surface"), "panel")
        margins = panel.body_layout().contentsMargins()
        self.assertEqual(margins.left(), METRICS.space_lg)
        self.assertEqual(panel.body_layout().spacing(), METRICS.space_sm)

    def test_metric_tile_roles_and_emphasis_variant(self) -> None:
        plain = MetricTile("Available Cards", "7")
        emphasized = MetricTile("Available Cards", "7", emphasized=True)
        self.addCleanup(plain.deleteLater)
        self.addCleanup(emphasized.deleteLater)
        self.assertEqual(plain.property("surface"), "tile")
        self.assertEqual(emphasized.property("surface"), "accent-tile")
        self.assertEqual(plain.value_label.property("typography"), "metric-value")
        self.assertEqual(plain.label_label.property("typography"), "metric-label")
        plain.set_value("12")
        self.assertEqual(plain.value_label.text(), "12")

    def test_empty_state_role_and_message(self) -> None:
        empty = EmptyState("Nothing here yet.")
        self.addCleanup(empty.deleteLater)
        self.assertEqual(empty.message_label.property("typography"), "empty-state")
        empty.set_message("Updated.")
        self.assertEqual(empty.message_label.text(), "Updated.")

    def test_status_pill_tone_switch_repolishes(self) -> None:
        pill = StatusPill("Ready", "neutral")
        self.addCleanup(pill.deleteLater)
        self.assertEqual(pill.property("pill"), "neutral")
        pill.set_tone("accent")
        self.assertEqual(pill.property("pill"), "accent")

    def test_typography_and_metrics_tokens_are_theme_independent(self) -> None:
        """Switching Light <-> Dark must never reflow the page or resize
        text (DESIGN.md § 6.1/§ 15)."""
        light = resolve_tokens(Appearance.LIGHT, Accent.CALM_BLUE)
        dark = resolve_tokens(Appearance.DARK, Accent.CALM_BLUE)
        self.assertIs(light.typography, dark.typography)
        self.assertIs(light.metrics, dark.metrics)
        self.assertIs(light.typography, TYPOGRAPHY)
        self.assertIs(light.metrics, METRICS)


if __name__ == "__main__":
    unittest.main()

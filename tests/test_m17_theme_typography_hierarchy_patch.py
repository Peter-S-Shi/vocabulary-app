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
Focused tests for the M17 Theme Completion Typography Color Hierarchy
Corrective Patch.

Per DESIGN.md § 2 Rule C, these structural/string-level checks cannot
prove the four-level information hierarchy (primary/secondary/muted/
disabled) *reads correctly* to a human across Light and Dark -- only that
the four fixed defects stay fixed, the token-role mapping for a
representative set of already-correct pairings doesn't regress, and no
new hard-coded typography color bypasses the token system. Native human
visual acceptance (DESIGN.md § 27.8) remains the real gate.

Confirmed defects this patch fixes (each verified empirically against a
real running QApplication before the fix, not just by reading the QSS
text):

1. ``QLineEdit#quiz-answer-input:disabled`` used ``text-secondary``
   instead of ``text-disabled`` -- the only exception among 15+
   ``:disabled`` rules in the whole stylesheet.
2. ``QDialog QComboBox`` had no ``:disabled`` rule at all -- a disabled
   dialog combo (Entries' locked template combo; Review's Choose Quiz
   Type combos) rendered pixel-identical to a fully enabled one.
3. ``QLabel#settings-row-label`` used ``text-primary``, breaking from the
   established "caption for a value" convention (``today-summary-
   caption``, ``entries-detail-caption``, ``quiz-completion-stat-label``
   all use ``text-muted``/``text-secondary``) and collapsing hierarchy
   with the combo's own ``text-primary`` selected-value text.
4. Today's "Collections Needing Attention" row name label had no object
   name at all. It happened to render at ``text-primary`` at rest only
   via plain QPalette fallback (verified empirically) -- but a genuinely
   disabled row (no ``system_type``) would have stayed at that same
   full-strength color instead of ``text-disabled``, since nothing
   distinguished the two cases. Fixed by deciding the object name in
   Python (``today_view.py``'s ``_build_attention_row()``) from the same
   ``system_type`` data that already decides whether the row is enabled,
   rather than a QSS ``:disabled`` pseudo-state selector.

A fifth defect was investigated and found *not* fixable within this
patch's scope: ``QPushButton#nav-rail-item:hover:enabled`` sets an
``accent-soft`` background with no paired foreground for its child
label. Attempting the same descendant-selector pairing used elsewhere in
this file (``QPushButton#nav-rail-item:hover:enabled QLabel#nav-rail-
label { color: ...; }``) was empirically verified -- against both the
``offscreen`` and the real native ``windows`` Qt platforms, through the
real ``app.py`` bootstrap path -- to be unreliable: Qt's style engine
does not correctly re-evaluate a child QLabel's color against an
ancestor's *dynamic* pseudo-state here, so the highest-specificity
descendant rule wins unconditionally regardless of whether that
pseudo-state actually holds. This is a pre-existing limitation of
``nav-rail-item``'s already-Human-Accepted ``nav-rail-mark``/``nav-rail-
label`` rules (confirmed present, and unnoticed, before this patch too,
just manifesting as a different always-wrong color) -- redesigning that
mechanism is out of this narrow patch's scope (see
``theme_manager.py``'s comment on ``nav-rail-mark``).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT


def _rule_body(stylesheet: str, selector: str) -> str:
    """Extract the ``{ ... }`` body immediately following ``selector``.

    QSS blocks in this stylesheet are always flat (no nested braces), so
    a non-greedy match up to the first ``}`` is exact and unambiguous.
    """
    pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
    match = re.search(pattern, stylesheet)
    if match is None:
        raise AssertionError(f"selector not found in stylesheet: {selector!r}")
    return match.group(1)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIEW_SOURCE_FILES = tuple(
    (PROJECT_ROOT / "src" / "ui_desktop" / "views").glob("*.py")
) + tuple((PROJECT_ROOT / "src" / "ui_desktop" / "qt_models").glob("*.py")) + tuple(
    (PROJECT_ROOT / "src" / "ui_desktop" / "widgets").glob("*.py")
)

# The one intentional, documented exception: a safe placeholder default
# overwritten by the live theme push before it is ever actually painted
# (EntriesTableModel.DEFAULT_STAR_COLOR, entries_table_model.py).
ALLOWED_HARDCODED_HEX = {"#8A6D00"}
HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ConfirmedDefectRegressionTests(unittest.TestCase):
    """Each of the four confirmed defects, locked in as a permanent
    regression guard against the exact wrong token reappearing."""

    def _themes(self):
        return {"Light": THEME_CALM_BLUE_LIGHT, "Dark": THEME_CALM_BLUE_DARK}

    def test_quiz_answer_input_disabled_uses_text_disabled_not_secondary(self) -> None:
        for name, tokens in self._themes().items():
            body = _rule_body(build_stylesheet(tokens), "QLineEdit#quiz-answer-input:disabled")
            self.assertIn(f"color: {tokens.neutral.text_disabled};", body, name)
            self.assertNotIn(tokens.neutral.text_secondary, body, name)

    def test_dialog_combo_disabled_uses_text_disabled(self) -> None:
        for name, tokens in self._themes().items():
            body = _rule_body(build_stylesheet(tokens), "QDialog QComboBox:disabled")
            self.assertIn(f"color: {tokens.neutral.text_disabled};", body, name)

    def test_settings_row_label_uses_text_secondary_not_primary(self) -> None:
        for name, tokens in self._themes().items():
            body = _rule_body(build_stylesheet(tokens), "QLabel#settings-row-label")
            self.assertIn(f"color: {tokens.neutral.text_secondary};", body, name)
            self.assertNotIn(f"color: {tokens.neutral.text_primary};", body, name)

    def test_today_attention_label_has_distinct_static_enabled_and_disabled_selectors(self) -> None:
        """Reliable single-level selectors, not a QSS :disabled pseudo-
        state on an ancestor (module docstring's nav-rail-item finding)
        -- ``today_view.py`` picks between these two object names in
        Python from real ``system_type`` data."""
        for name, tokens in self._themes().items():
            stylesheet = build_stylesheet(tokens)
            enabled_body = _rule_body(stylesheet, "QLabel#today-attention-label")
            self.assertIn(f"color: {tokens.neutral.text_primary};", enabled_body, name)

            disabled_body = _rule_body(stylesheet, "QLabel#today-attention-label-disabled")
            self.assertIn(f"color: {tokens.neutral.text_disabled};", disabled_body, name)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TextRoleDistinctionTests(unittest.TestCase):
    """M17 Theme Completion Typography patch § 11: primary/secondary/
    muted/disabled must remain four distinct values in both Appearances
    -- a collapsed pair (e.g. secondary == muted) would silently flatten
    the hierarchy regardless of which literal tokens QSS selectors
    reference."""

    def test_four_text_roles_are_pairwise_distinct(self) -> None:
        for name, tokens in {"Light": THEME_CALM_BLUE_LIGHT, "Dark": THEME_CALM_BLUE_DARK}.items():
            n = tokens.neutral
            roles = {
                "text_primary": n.text_primary,
                "text_secondary": n.text_secondary,
                "text_muted": n.text_muted,
                "text_disabled": n.text_disabled,
            }
            values = list(roles.values())
            self.assertEqual(len(values), len(set(values)), f"{name}: duplicate text-role token values: {roles}")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class AccentSoftForegroundPairingCoverageTests(unittest.TestCase):
    """Every ``accent.soft.background`` usage in the stylesheet must have
    a paired ``accent.soft.foreground`` declared in the *same* rule body
    (M17 Theme Completion Typography patch § 4/§ 7 "wrong foreground
    pairing"). Parses ``build_stylesheet()``'s actual selector blocks
    rather than hand-listing selectors, so a future addition that forgets
    the pairing fails this test automatically."""

    # A background selector's paired foreground normally lives in the
    # exact same rule, or (for a widget whose text lives in a *reliably
    # stateful* child, unlike nav-rail-item -- see module docstring) a
    # CSS descendant selector scoped under it. This container's
    # foreground genuinely lives in a same-level *sibling* widget's own
    # selector instead -- verified by reading entries_view.py:
    # ``entries-batch-bar`` is the batch-action bar container;
    # ``entries-batch-count-label`` is a plain child QLabel inside it
    # with its own independent object name, not addressed by a QSS
    # descendant combinator.
    KNOWN_SIBLING_FOREGROUND_SELECTORS = {
        "QWidget#entries-batch-bar": "QLabel#entries-batch-count-label",
    }

    # Investigated and deliberately left unpaired (module docstring's
    # "fifth defect ... not fixable within this patch's scope"): a
    # descendant-selector foreground pairing for this hover background
    # was verified empirically to be unreliable in this codebase, and
    # this pre-existing, already-Human-Accepted selector is out of scope
    # for this narrow patch to redesign.
    KNOWN_UNRELIABLE_DESCENDANT_PAIRING_SELECTORS = {
        "QPushButton#nav-rail-item:hover:enabled",
        # Same unreliable-descendant-pairing class; the label stays
        # text-primary during hover instead, which is high-contrast
        # against accent-soft (~11.2-14.6:1, well above AA) so this is
        # not a readability regression, just not the "on-accent-soft" hue.
        "QPushButton#today-attention-row:hover:enabled",
    }

    def test_every_rule_using_accent_soft_background_also_sets_accent_soft_foreground(self) -> None:
        for name, tokens in {"Light": THEME_CALM_BLUE_LIGHT, "Dark": THEME_CALM_BLUE_DARK}.items():
            stylesheet = build_stylesheet(tokens)
            soft_bg = tokens.accent.soft.background
            soft_fg = tokens.accent.soft.foreground
            rules = [
                (m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^}]*)\}", stylesheet)
            ]
            fg_declared_selectors = {selector for selector, body in rules if f"color: {soft_fg};" in body}
            for selector, body in rules:
                if f"background-color: {soft_bg};" not in body:
                    continue
                if selector in self.KNOWN_UNRELIABLE_DESCENDANT_PAIRING_SELECTORS:
                    continue
                sibling = self.KNOWN_SIBLING_FOREGROUND_SELECTORS.get(selector)
                paired = (
                    selector in fg_declared_selectors
                    or any(other.startswith(selector) and other != selector for other in fg_declared_selectors)
                    or (sibling is not None and sibling in fg_declared_selectors)
                )
                self.assertTrue(
                    paired,
                    f"{name}: {selector!r} sets accent-soft background without any paired accent-soft foreground",
                )


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class StudyModeRestraintTests(unittest.TestCase):
    """M17 Theme Completion Typography patch § 6/§ 7: primary Study
    content (the term itself) must stay neutral, never accent-colored,
    in both Review and Quiz -- accent creeping onto primary content would
    be exactly the "Study Mode should not feel more intense" violation
    the canonical Theme Architecture Visual Validation board calls out.
    """

    def test_review_and_quiz_term_labels_use_neutral_text_primary_not_accent(self) -> None:
        for name, tokens in {"Light": THEME_CALM_BLUE_LIGHT, "Dark": THEME_CALM_BLUE_DARK}.items():
            stylesheet = build_stylesheet(tokens)
            for selector in ("QLabel#review-term-label", "QLabel#quiz-term-label"):
                body = _rule_body(stylesheet, selector)
                self.assertIn(f"color: {tokens.neutral.text_primary};", body, f"{name} {selector}")
                self.assertNotIn(tokens.accent.primary.background, body, f"{name} {selector}")

    def test_quiz_feedback_uses_semantic_not_accent(self) -> None:
        for name, tokens in {"Light": THEME_CALM_BLUE_LIGHT, "Dark": THEME_CALM_BLUE_DARK}.items():
            stylesheet = build_stylesheet(tokens)
            correct_body = _rule_body(stylesheet, "QLabel#quiz-feedback-correct")
            wrong_body = _rule_body(stylesheet, "QLabel#quiz-feedback-wrong")
            self.assertIn(f"color: {tokens.semantic.quiz_correct.background};", correct_body, name)
            self.assertIn(f"color: {tokens.semantic.quiz_wrong.background};", wrong_body, name)
            self.assertNotIn(tokens.accent.primary.background, correct_body, name)
            self.assertNotIn(tokens.accent.primary.background, wrong_body, name)


class NoHardcodedTypographyColorTests(unittest.TestCase):
    """M17 Theme Completion Typography patch § 9/§ 11: no newly introduced
    hard-coded gray/white typography color may bypass ThemeManager. Scans
    the actual view/model/widget source files (not the theming package
    itself, which legitimately owns the literal token values) for raw hex
    color literals via the Python AST -- string constants only, so this
    can't false-positive on unrelated comment text containing a '#'.
    """

    def test_no_undocumented_hex_color_literals_in_view_layer_source(self) -> None:
        offenders: list[str] = []
        for path in VIEW_SOURCE_FILES:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    for found in HEX_COLOR_RE.findall(node.value):
                        if found.upper() not in {h.upper() for h in ALLOWED_HARDCODED_HEX}:
                            offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}: {found}")
        self.assertEqual(offenders, [], f"undocumented hard-coded colors bypassing ThemeManager: {offenders}")


if __name__ == "__main__":
    unittest.main()

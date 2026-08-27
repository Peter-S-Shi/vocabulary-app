from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db

"""
Focused tests for M17 -- Theme Completion & Cross-Screen Validation.

Per DESIGN.md § 2 Rule C, none of this proves the Theme Matrix / Cross-
Screen Validation boards were *visually* realized on the real native
window -- only that: System resolves through one real, live,
mockable OS abstraction with a documented safe fallback; explicit
Light/Dark is never silently overridden by an OS change; Settings'
Appearance control persists and live-applies through the single existing
ThemeManager call site; the one non-QSS-driven presentation (Entries'
Star column) participates in live theme switching; and the frozen token
tables/representative QSS selectors meet WCAG-oriented contrast targets.
Native human visual acceptance (System / Light / Dark cross-screen) is a
separate, required gate (AGENTS.md), never satisfied by this suite alone.
"""

APP_PREFERENCES_PATH_ENV = "VOCAB_APP_PREFERENCES_PATH"


def _qt_app() -> "QApplication":
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _IsolatedPreferencesEnv:
    """Redirects ``get_app_preferences_path()`` to a throwaway temp file
    for the duration of a test, matching the pattern already established
    by ``tests/test_m17_feature_3b_quiz_presentation.py`` -- constructing
    a bare ``SettingsController()`` must never write to the real user
    preferences.json."""

    def setUp(self) -> None:  # noqa: N802 (unittest mixin convention)
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.preferences_path = Path(self.temp_dir.name) / "preferences.json"
        self._previous_env = os.environ.get(APP_PREFERENCES_PATH_ENV)
        os.environ[APP_PREFERENCES_PATH_ENV] = str(self.preferences_path)

    def tearDown(self) -> None:  # noqa: N802 (unittest mixin convention)
        if self._previous_env is None:
            os.environ.pop(APP_PREFERENCES_PATH_ENV, None)
        else:
            os.environ[APP_PREFERENCES_PATH_ENV] = self._previous_env
        self.temp_dir.cleanup()


class _SyntheticDatabaseTestCase(unittest.TestCase):
    """Shared setup matching the existing repository pattern: swap
    db.DB_PATH to a temporary synthetic database, never the user's
    personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m17_theme_completion.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


# --- WCAG contrast helpers (test-only; not a production dependency) -------


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # noqa: E203


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    lum_a = _relative_luminance(_hex_to_rgb(hex_a))
    lum_b = _relative_luminance(_hex_to_rgb(hex_b))
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def _hue_degrees(value: str) -> float:
    r, g, b = (c / 255.0 for c in _hex_to_rgb(value))
    mx, mn = max(r, g, b), min(r, g, b)
    delta = mx - mn
    if delta == 0:
        return 0.0
    if mx == r:
        h = 60 * (((g - b) / delta) % 6)
    elif mx == g:
        h = 60 * (((b - r) / delta) + 2)
    else:
        h = 60 * (((r - g) / delta) + 4)
    return h


if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.settings_controller import SettingsController
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.qt_models.entries_table_model import EntriesTableModel
    from src.ui_desktop.state.preferences import (
        DEFAULT_APPEARANCE,
        Preferences,
        load_preferences,
        parse_quiz_presentation,
        save_preferences,
    )
    from src.ui_desktop.theming import theme_manager as theme_manager_module
    from src.ui_desktop.theming.theme_manager import (
        Accent,
        Appearance,
        ThemeManager,
        build_stylesheet,
        parse_accent,
        parse_appearance,
        resolve_effective_appearance,
        resolve_tokens,
    )
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.entries_view import EntriesView
    from src.ui_desktop.views.settings_view import SettingsView


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class PreferencesAppearanceTests(unittest.TestCase):
    """`state/preferences.py` Appearance persistence (M17 Theme Completion
    prompt § 18 "Preferences / Settings")."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.temp_dir.name) / "preferences.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_default_appearance_is_system(self) -> None:
        self.assertEqual(DEFAULT_APPEARANCE, "System")
        preferences = load_preferences(self.path)
        self.assertEqual(preferences.appearance, "System")

    def test_malformed_appearance_in_file_falls_back_safely_at_theme_resolution(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"appearance": "Not A Real Value"}), encoding="utf-8")
        preferences = load_preferences(self.path)
        # load_preferences intentionally stores the raw string as-is (a
        # self-healing normalization happens at Appearance.parse_appearance()
        # call sites, e.g. ThemeManager.apply()/SettingsController), so the
        # malformed value must not crash resolution downstream.
        self.assertIs(parse_appearance(preferences.appearance), Appearance.SYSTEM)

    def test_appearance_round_trips_through_save_and_load(self) -> None:
        preferences = Preferences(appearance="Dark")
        save_preferences(preferences, self.path)
        reloaded = load_preferences(self.path)
        self.assertEqual(reloaded.appearance, "Dark")

    def test_old_preferences_file_without_appearance_key_stays_valid(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"quiz_presentation": "immersive_focus"}), encoding="utf-8")
        preferences = load_preferences(self.path)
        self.assertEqual(preferences.appearance, DEFAULT_APPEARANCE)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ParseAppearanceTests(unittest.TestCase):
    def test_all_three_supported_values_parse_exactly(self) -> None:
        self.assertIs(parse_appearance("System"), Appearance.SYSTEM)
        self.assertIs(parse_appearance("Light"), Appearance.LIGHT)
        self.assertIs(parse_appearance("Dark"), Appearance.DARK)

    def test_unknown_value_falls_back_to_system(self) -> None:
        self.assertIs(parse_appearance("Solarized"), Appearance.SYSTEM)
        self.assertIs(parse_appearance(""), Appearance.SYSTEM)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SystemAppearanceAbstractionTests(unittest.TestCase):
    """`resolve_effective_appearance()` resolving `System` through the one
    platform/theme abstraction (M17 Theme Completion prompt § 7 / § 18
    "System appearance")."""

    def test_os_light_resolves_light(self) -> None:
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Light):
            self.assertIs(resolve_effective_appearance(Appearance.SYSTEM), Appearance.LIGHT)

    def test_os_dark_resolves_dark(self) -> None:
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Dark):
            self.assertIs(resolve_effective_appearance(Appearance.SYSTEM), Appearance.DARK)

    def test_unknown_os_scheme_falls_back_to_light_and_logs_a_warning(self) -> None:
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Unknown):
            with self.assertLogs("vocabulary_app.ui", level="WARNING") as captured:
                resolved = resolve_effective_appearance(Appearance.SYSTEM)
        self.assertIs(resolved, Appearance.LIGHT)
        self.assertTrue(any("System" in message or "Unknown" in message for message in captured.output))

    def test_explicit_light_and_dark_never_consult_system_detection(self) -> None:
        with patch.object(theme_manager_module, "detect_system_color_scheme") as mocked:
            self.assertIs(resolve_effective_appearance(Appearance.LIGHT), Appearance.LIGHT)
            self.assertIs(resolve_effective_appearance(Appearance.DARK), Appearance.DARK)
            mocked.assert_not_called()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ThemeManagerLiveSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_switching_to_system_re_resolves_immediately_against_current_os_state(self) -> None:
        manager = ThemeManager(self.app)
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Light):
            manager.apply(Appearance.SYSTEM, Accent.CALM_BLUE)
            self.assertEqual(manager.current_tokens.neutral.app_background, THEME_CALM_BLUE_LIGHT.neutral.app_background)
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Dark):
            manager.apply(Appearance.SYSTEM, Accent.CALM_BLUE)
            self.assertEqual(manager.current_tokens.neutral.app_background, THEME_CALM_BLUE_DARK.neutral.app_background)

    def test_os_change_while_system_active_triggers_a_live_reapply(self) -> None:
        manager = ThemeManager(self.app)
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Light):
            manager.apply(Appearance.SYSTEM, Accent.CALM_BLUE)
        manager.watch_system_appearance()

        applied_count = {"n": 0}
        manager.theme_applied.connect(lambda _tokens: applied_count.__setitem__("n", applied_count["n"] + 1))

        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Dark):
            manager._on_os_color_scheme_changed(Qt.ColorScheme.Dark)

        self.assertEqual(applied_count["n"], 1)
        self.assertEqual(manager.current_tokens.neutral.app_background, THEME_CALM_BLUE_DARK.neutral.app_background)

    def test_os_change_while_explicit_appearance_active_does_not_override_it(self) -> None:
        manager = ThemeManager(self.app)
        manager.apply(Appearance.DARK, Accent.CALM_BLUE)
        manager.watch_system_appearance()

        applied_count = {"n": 0}
        manager.theme_applied.connect(lambda _tokens: applied_count.__setitem__("n", applied_count["n"] + 1))

        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Light):
            manager._on_os_color_scheme_changed(Qt.ColorScheme.Light)

        self.assertEqual(applied_count["n"], 0, "an OS change must not re-apply while an explicit choice is active")
        self.assertEqual(manager.current, (Appearance.DARK, Accent.CALM_BLUE))
        self.assertEqual(manager.current_tokens.neutral.app_background, THEME_CALM_BLUE_DARK.neutral.app_background)

    def test_watch_system_appearance_is_idempotent_per_instance(self) -> None:
        """Calling watch twice must not double-apply on one OS change
        (M17 Theme Completion prompt § 18 "no duplicate theme manager
        instance/state")."""
        manager = ThemeManager(self.app)
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Light):
            manager.apply(Appearance.SYSTEM, Accent.CALM_BLUE)
        manager.watch_system_appearance()
        manager.watch_system_appearance()  # second call must be a no-op

        applied_count = {"n": 0}
        manager.theme_applied.connect(lambda _tokens: applied_count.__setitem__("n", applied_count["n"] + 1))
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Dark):
            manager._on_os_color_scheme_changed(Qt.ColorScheme.Dark)

        self.assertEqual(applied_count["n"], 1)

    def test_watch_system_appearance_wires_the_real_qt_style_hints_signal(self) -> None:
        """Proves the actual Qt-level wiring (not just the private
        dispatcher method other tests call directly): emitting the real
        ``QStyleHints.colorSchemeChanged`` signal reaches this manager."""
        from PySide6.QtGui import QGuiApplication

        manager = ThemeManager(self.app)
        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Light):
            manager.apply(Appearance.SYSTEM, Accent.CALM_BLUE)
        manager.watch_system_appearance()

        with patch.object(theme_manager_module, "detect_system_color_scheme", return_value=Qt.ColorScheme.Dark):
            QGuiApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)

        self.assertEqual(manager.current_tokens.neutral.app_background, THEME_CALM_BLUE_DARK.neutral.app_background)

    def test_repeated_apply_is_safe_and_idempotent_for_runtime_switching(self) -> None:
        manager = ThemeManager(self.app)
        manager.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        manager.apply(Appearance.DARK, Accent.CALM_BLUE)
        manager.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        self.assertEqual(manager.current, (Appearance.LIGHT, Accent.CALM_BLUE))
        self.assertEqual(self.app.styleSheet(), build_stylesheet(resolve_tokens(Appearance.LIGHT, Accent.CALM_BLUE)))

    def test_theme_applied_emits_the_resolved_tokens(self) -> None:
        manager = ThemeManager(self.app)
        received = []
        manager.theme_applied.connect(received.append)
        manager.apply(Appearance.DARK, Accent.CALM_BLUE)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].neutral.app_background, THEME_CALM_BLUE_DARK.neutral.app_background)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsAppearanceControllerTests(_IsolatedPreferencesEnv, unittest.TestCase):
    def setUp(self) -> None:
        _IsolatedPreferencesEnv.setUp(self)

    def tearDown(self) -> None:
        _IsolatedPreferencesEnv.tearDown(self)

    def test_appearance_defaults_to_system(self) -> None:
        controller = SettingsController()
        self.assertEqual(controller.appearance(), "System")

    def test_set_appearance_persists_to_disk_and_emits_state_changed(self) -> None:
        controller = SettingsController()
        events = []
        controller.state_changed.connect(lambda: events.append(True))

        controller.set_appearance("Dark")

        self.assertEqual(controller.appearance(), "Dark")
        self.assertEqual(len(events), 1)
        reloaded = load_preferences(Path(os.environ[APP_PREFERENCES_PATH_ENV]))
        self.assertEqual(reloaded.appearance, "Dark")

    def test_set_appearance_malformed_value_falls_back_safely(self) -> None:
        controller = SettingsController()
        controller.set_appearance("Not A Real Value")
        self.assertEqual(controller.appearance(), "System")

    def test_set_appearance_is_a_no_op_when_unchanged(self) -> None:
        controller = SettingsController(Preferences(appearance="Dark"))
        events = []
        controller.state_changed.connect(lambda: events.append(True))
        controller.set_appearance("Dark")
        self.assertEqual(events, [])

    def test_set_appearance_live_applies_through_the_injected_theme_manager(self) -> None:
        applied = []

        class _FakeThemeManager:
            def apply(self, appearance, accent):
                applied.append((appearance, accent))

        controller = SettingsController(Preferences(accent="Calm Blue"), _FakeThemeManager())
        controller.set_appearance("Dark")
        self.assertEqual(applied, [(Appearance.DARK, Accent.CALM_BLUE)])

    def test_set_appearance_without_a_theme_manager_still_persists(self) -> None:
        controller = SettingsController(Preferences(), None)
        controller.set_appearance("Dark")  # must not raise
        self.assertEqual(controller.appearance(), "Dark")

    def test_changing_appearance_never_touches_quiz_presentation(self) -> None:
        controller = SettingsController(Preferences(quiz_presentation="flip_card_filmstrip"))
        controller.set_appearance("Dark")
        self.assertEqual(controller.quiz_presentation(), "flip_card_filmstrip")

    def test_changing_quiz_presentation_never_touches_appearance(self) -> None:
        controller = SettingsController(Preferences(appearance="Dark"))
        controller.set_quiz_presentation(parse_quiz_presentation("flip_card_filmstrip"))
        self.assertEqual(controller.appearance(), "Dark")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsViewAppearanceUITests(_IsolatedPreferencesEnv, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        _IsolatedPreferencesEnv.setUp(self)

    def tearDown(self) -> None:
        _IsolatedPreferencesEnv.tearDown(self)

    def test_appearance_combo_offers_exactly_system_light_dark(self) -> None:
        controller = SettingsController()
        view = SettingsView(controller)
        values = [view._appearance_combo.itemData(i) for i in range(view._appearance_combo.count())]
        self.assertEqual(values, ["System", "Light", "Dark"])

    def test_selecting_dark_calls_through_to_the_controller(self) -> None:
        controller = SettingsController()
        view = SettingsView(controller)
        dark_index = view._appearance_combo.findData("Dark")
        view._appearance_combo.setCurrentIndex(dark_index)
        self.assertEqual(controller.appearance(), "Dark")

    def test_combo_reflects_the_current_persisted_preference_on_construction(self) -> None:
        controller = SettingsController(Preferences(appearance="Dark"))
        view = SettingsView(controller)
        self.assertEqual(view._appearance_combo.currentData(), "Dark")

    def test_external_state_changed_resync_does_not_reenter_set_appearance(self) -> None:
        """Regression guard for a theme-switch feedback loop (prompt §
        15): syncing the combo from an external state_changed emission
        must not itself call set_appearance() again."""
        controller = SettingsController()
        view = SettingsView(controller)
        calls = []
        original = controller.set_appearance
        controller.set_appearance = lambda value: (calls.append(value), original(value))[1]
        controller.preferences.appearance = "Dark"
        controller.state_changed.emit()
        self.assertEqual(calls, [])
        self.assertEqual(view._appearance_combo.currentData(), "Dark")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesStarThemeAwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_default_star_color_is_a_safe_placeholder_before_any_theme_push(self) -> None:
        model = EntriesTableModel([{"id": 1, "starred": True}])
        color = model.data(model.index(0, model.COLUMNS.index(model.STAR_COLUMN)), Qt.ItemDataRole.ForegroundRole)
        self.assertEqual(color.name(), QColor("#2C4C6C").name())

    def test_set_star_color_repaints_only_filled_stars(self) -> None:
        model = EntriesTableModel([{"id": 1, "starred": True}, {"id": 2, "starred": False}])
        model.set_star_color(QColor(THEME_CALM_BLUE_DARK.semantic.star.background))

        star_col = model.COLUMNS.index(model.STAR_COLUMN)
        starred_color = model.data(model.index(0, star_col), Qt.ItemDataRole.ForegroundRole)
        unstarred_color = model.data(model.index(1, star_col), Qt.ItemDataRole.ForegroundRole)

        self.assertEqual(starred_color.name(), QColor(THEME_CALM_BLUE_DARK.semantic.star.background).name())
        self.assertIsNone(unstarred_color)

    def test_set_star_color_emits_data_changed_only_for_the_star_column(self) -> None:
        model = EntriesTableModel([{"id": 1, "starred": True}])
        emitted_columns = []
        model.dataChanged.connect(lambda top_left, bottom_right, roles: emitted_columns.append((top_left.column(), bottom_right.column())))

        model.set_star_color(QColor("#000000"))

        star_col = model.COLUMNS.index(model.STAR_COLUMN)
        self.assertEqual(emitted_columns, [(star_col, star_col)])

    def test_set_star_color_is_a_no_op_when_unchanged(self) -> None:
        model = EntriesTableModel([{"id": 1, "starred": True}])
        model.set_star_color(QColor(EntriesTableModel.DEFAULT_STAR_COLOR))
        fired = []
        model.dataChanged.connect(lambda *args: fired.append(True))
        model.set_star_color(QColor(EntriesTableModel.DEFAULT_STAR_COLOR))
        self.assertEqual(fired, [])

    def test_entries_view_apply_theme_tokens_pushes_the_resolved_star_color_into_the_model(self) -> None:
        from src.ui_desktop.controllers.entries_controller import EntriesController

        controller = EntriesController()
        view = EntriesView(controller)
        view.apply_theme_tokens(THEME_CALM_BLUE_LIGHT)
        self.assertEqual(controller.model._star_color.name(), QColor(THEME_CALM_BLUE_LIGHT.semantic.star.background).name())


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class MainWindowLiveThemeWiringTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_construction_applies_whatever_the_theme_manager_already_resolved(self) -> None:
        manager = ThemeManager(self.app)
        manager.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        window = MainWindow(theme_manager=manager)
        self.assertEqual(
            window.entries_controller.model._star_color.name(),
            QColor(THEME_CALM_BLUE_LIGHT.semantic.star.background).name(),
        )

    def test_live_theme_change_after_construction_repaints_the_star_column(self) -> None:
        manager = ThemeManager(self.app)
        manager.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        window = MainWindow(theme_manager=manager)

        manager.apply(Appearance.DARK, Accent.CALM_BLUE)

        self.assertEqual(
            window.entries_controller.model._star_color.name(),
            QColor(THEME_CALM_BLUE_DARK.semantic.star.background).name(),
        )

    def test_construction_without_a_theme_manager_does_not_crash(self) -> None:
        MainWindow(theme_manager=None)  # must not raise


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TokenQssStructuralCoverageTests(unittest.TestCase):
    """Guards against a future edit silently dropping theming for an
    already-shipped M17 surface/state (M17 Theme Completion prompt § 18
    "Token/QSS coverage"). Checked once per Appearance; the same object
    names must remain themed regardless of which tokens resolved."""

    REPRESENTATIVE_SELECTORS = (
        "#nav-rail-item",
        "#today-action-button",
        "#today-attention-chip",
        "#entries-table",
        "#entries-batch-delete-button",
        "QTableView#entries-table::item:selected",
        "#collections-card-row",
        "#collections-card-previous-button",
        "#review-nav-next",
        "#quiz-grade-correct-button",
        "#quiz-grade-wrong-button",
        "#settings-appearance-combo",
        "#settings-quiz-presentation-combo",
        "QMenu",
        "QMenu::item:disabled",
        "QDialog",
        'QPushButton[destructive="true"]',
        "QToolButton:disabled",
        "QPushButton#nav-rail-item:checked",
    )

    def _assert_all_selectors_present(self, tokens) -> None:
        stylesheet = build_stylesheet(tokens)
        for selector in self.REPRESENTATIVE_SELECTORS:
            self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")

    def test_light_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_LIGHT)

    def test_dark_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_DARK)


class ContrastAuditTests(unittest.TestCase):
    """Automated WCAG-oriented contrast checks (M17 Theme Completion
    prompt § 16/§ 18 "Contrast"). Not a substitute for real native human
    acceptance (DESIGN.md § 19/§ 27.8), but a blocker-catching floor.

    Every pair here reflects an actual foreground/background combination
    the running QSS deploys (theme_manager.py), not just the token's
    single "best case" surface -- the previous #79766D Light text-muted
    value passed against surface-primary alone but failed against
    surface-secondary/app-background, which this suite would have caught.
    """

    AA_NORMAL_TEXT = 4.5
    AA_NON_TEXT = 3.0

    def _themes(self):
        from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK as dark
        from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_LIGHT as light

        return {"Light": light, "Dark": dark}

    def test_primary_secondary_muted_text_meet_aa_against_every_surface_they_appear_on(self) -> None:
        for name, tokens in self._themes().items():
            n = tokens.neutral
            surfaces = (n.app_background, n.surface_primary, n.surface_secondary)
            for text_name, text_color in (
                ("text_primary", n.text_primary),
                ("text_secondary", n.text_secondary),
                ("text_muted", n.text_muted),
            ):
                for surface in surfaces:
                    ratio = _contrast_ratio(text_color, surface)
                    self.assertGreaterEqual(
                        ratio,
                        self.AA_NORMAL_TEXT,
                        f"{name} {text_name} ({text_color}) vs {surface} = {ratio:.2f} (< {self.AA_NORMAL_TEXT})",
                    )

    def test_disabled_text_remains_identifiable_though_exempt_from_aa(self) -> None:
        """WCAG 1.4.3 exempts inactive/disabled UI text from the 4.5:1
        requirement; it must still clear a much weaker legibility floor
        so it reads as dim-but-present, not invisible."""
        for name, tokens in self._themes().items():
            ratio = _contrast_ratio(tokens.neutral.text_disabled, tokens.neutral.surface_primary)
            self.assertGreaterEqual(ratio, 2.5, f"{name} text_disabled vs surface_primary = {ratio:.2f}")

    def test_accent_primary_hover_pressed_soft_foreground_pairs_meet_aa(self) -> None:
        for name, tokens in self._themes().items():
            accent = tokens.accent
            for pair_name, pair in (
                ("primary", accent.primary),
                ("hover", accent.hover),
                ("pressed", accent.pressed),
                ("soft", accent.soft),
            ):
                ratio = _contrast_ratio(pair.foreground, pair.background)
                self.assertGreaterEqual(ratio, self.AA_NORMAL_TEXT, f"{name} accent.{pair_name} = {ratio:.2f}")

    def test_semantic_solid_and_soft_foreground_pairs_meet_aa(self) -> None:
        for name, tokens in self._themes().items():
            semantic = tokens.semantic
            for state_name in ("success", "warning", "danger", "info"):
                pair = getattr(semantic, state_name)
                ratio = _contrast_ratio(pair.foreground, pair.background)
                self.assertGreaterEqual(ratio, self.AA_NORMAL_TEXT, f"{name} semantic.{state_name} = {ratio:.2f}")

                soft_bg = getattr(semantic, f"{state_name}_soft")
                soft_ratio = _contrast_ratio(pair.background, soft_bg)
                self.assertGreaterEqual(
                    soft_ratio, self.AA_NORMAL_TEXT, f"{name} semantic.{state_name} solid-on-soft = {soft_ratio:.2f}"
                )

    def test_quiz_correct_and_wrong_alias_success_and_danger_contrast(self) -> None:
        for name, tokens in self._themes().items():
            self.assertGreaterEqual(
                _contrast_ratio(tokens.semantic.quiz_correct.foreground, tokens.semantic.quiz_correct.background),
                self.AA_NORMAL_TEXT,
            )
            self.assertGreaterEqual(
                _contrast_ratio(tokens.semantic.quiz_wrong.foreground, tokens.semantic.quiz_wrong.background),
                self.AA_NORMAL_TEXT,
            )

    def test_selected_row_meets_aa(self) -> None:
        """`entries-table::item:selected` uses accent.primary fg/bg
        directly (theme_manager.py)."""
        for name, tokens in self._themes().items():
            ratio = _contrast_ratio(tokens.accent.primary.foreground, tokens.accent.primary.background)
            self.assertGreaterEqual(ratio, self.AA_NORMAL_TEXT, f"{name} selected row = {ratio:.2f}")

    def test_border_strong_meets_non_text_floor(self) -> None:
        for name, tokens in self._themes().items():
            ratio = _contrast_ratio(tokens.neutral.border_strong, tokens.neutral.surface_primary)
            self.assertGreaterEqual(ratio, self.AA_NON_TEXT, f"{name} border_strong = {ratio:.2f}")

    def test_star_semantic_meets_aa_against_surfaces_it_renders_on(self) -> None:
        for name, tokens in self._themes().items():
            star = tokens.semantic.star.background
            for surface_name, surface in (
                ("surface_primary", tokens.neutral.surface_primary),
                ("surface_secondary", tokens.neutral.surface_secondary),
            ):
                ratio = _contrast_ratio(star, surface)
                self.assertGreaterEqual(
                    ratio, self.AA_NORMAL_TEXT, f"{name} star vs {surface_name} = {ratio:.2f}"
                )

    def test_star_semantic_stays_hue_distinct_from_warning(self) -> None:
        """Star must not become visually indistinguishable from warning.
        A fixed hue-distance
        floor is a coarse but real guard against the two semantics
        converging on the same amber."""
        MIN_HUE_SEPARATION_DEGREES = 8.0
        for name, tokens in self._themes().items():
            star_hue = _hue_degrees(tokens.semantic.star.background)
            warning_hue = _hue_degrees(tokens.semantic.warning.background)
            separation = abs(star_hue - warning_hue)
            self.assertGreaterEqual(
                separation,
                MIN_HUE_SEPARATION_DEGREES,
                f"{name} star hue {star_hue:.1f} too close to warning hue {warning_hue:.1f} "
                f"(separation {separation:.1f} deg)",
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from scripts.audit_architecture import main as audit_architecture_main
from src import app_config, db
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry
from src.migrations import APP_DATA_VERSION, CURRENT_SCHEMA_VERSION, get_metadata, get_schema_version

"""
Focused tests for the M16.2 production vertical slice under src/ui_desktop/.
Distinct from tests/test_m16_1_architecture_spike.py, which only proves the
underlying PySide6 mechanisms in isolation; these tests exercise the actual
desktop bootstrap, shell, controllers, models, theming, preferences, and
SQLite compatibility path built on top of that architecture.
"""


if PYSIDE6_AVAILABLE:
    from src.ui_desktop.app import build_application
    from src.ui_desktop.controllers.today_controller import TodayController
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.qt_models.entries_table_model import EntriesTableModel
    from src.ui_desktop.state.app_state import AppState, ShellMode, Workspace
    from src.ui_desktop.state.preferences import Preferences, load_preferences, save_preferences
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

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


@contextlib.contextmanager
def _isolated_environ(**overrides):
    """Temporarily set/remove environment variables, restoring the original state."""
    sentinel = object()
    previous = {key: os.environ.get(key, sentinel) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


class _SyntheticDatabaseTestCase(unittest.TestCase):
    """Shared setup matching the existing repository pattern (see
    tests/test_m15_3_audio_export.py, tests/test_m16_1_architecture_spike.py):
    swap db.DB_PATH to a temporary synthetic database, never the user's
    personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m16_2.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. The M16.2 desktop "
    "vertical slice is desktop-only and optional for the core/Streamlit test run.",
)
class M162BootstrapTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self._preferences_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._env = _isolated_environ(
            VOCAB_APP_PREFERENCES_PATH=str(Path(self._preferences_dir.name) / "preferences.json")
        )
        self._env.__enter__()

    def tearDown(self) -> None:
        self._env.__exit__(None, None, None)
        self._preferences_dir.cleanup()
        super().tearDown()

    def test_build_application_constructs_shell_headless(self) -> None:
        application, window, theme_manager = build_application([])
        self.addCleanup(window.close)

        self.assertIsInstance(window, MainWindow)
        self.assertEqual(window.windowTitle(), "Vocabulary App (Desktop Preview)")
        self.assertIs(window.current_workspace(), Workspace.TODAY)
        self.assertIsNotNone(theme_manager.current)

        window.show()
        application.processEvents()
        window.close()
        application.processEvents()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M162NavigationAndChromeTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        # Qt's isVisible() reflects the whole ancestor chain; a toolbar only
        # reports itself visible once the top-level window has been shown.
        self.window.show()
        self.app.processEvents()

    def test_navigation_switches_workspace(self) -> None:
        self.assertIs(self.window.current_workspace(), Workspace.TODAY)

        self.window.app_state.request_navigation(Workspace.ENTRIES)
        self.assertIs(self.window.current_workspace(), Workspace.ENTRIES)

        self.window.app_state.request_navigation(Workspace.TODAY)
        self.assertIs(self.window.current_workspace(), Workspace.TODAY)

    def test_study_mode_suppresses_management_chrome_and_restores_it(self) -> None:
        self.assertTrue(self.window._navigation_rail.isVisible())
        self.assertFalse(self.window._study_toolbar.isVisible())

        self.window.app_state.enter_study_mode()
        self.assertFalse(self.window._navigation_rail.isVisible())
        self.assertTrue(self.window._study_toolbar.isVisible())

        self.window.app_state.enter_management_mode()
        self.assertTrue(self.window._navigation_rail.isVisible())
        self.assertFalse(self.window._study_toolbar.isVisible())

    def test_mode_changed_signal_only_fires_on_actual_transition(self) -> None:
        events: list[str] = []
        self.window.app_state.mode_changed.connect(events.append)

        self.window.app_state.enter_management_mode()  # already Management: no-op
        self.assertEqual(events, [])

        self.window.app_state.enter_study_mode()
        self.window.app_state.enter_study_mode()  # already Study: no-op
        self.assertEqual(events, [ShellMode.STUDY.value])

    def test_returning_to_management_mode_preserves_workspace_domain_state(self) -> None:
        self.window.app_state.request_navigation(Workspace.ENTRIES)
        self.window.app_state.enter_study_mode()
        self.window.app_state.enter_management_mode()
        self.assertIs(self.window.current_workspace(), Workspace.ENTRIES)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M162ShellStateAuthorityTests(_SyntheticDatabaseTestCase):
    """
    AppState is frozen as the owner of active workspace and Management/
    Study mode (M16.1 contract § 11.C). These tests prove MainWindow can
    never render a state that disagrees with AppState -- at construction
    time (including with an injected non-default AppState) and after any
    workspace transition, whether requested through the MainWindow
    convenience method or directly through AppState.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_injected_workspace_is_respected_at_construction(self) -> None:
        window = MainWindow(AppState(workspace=Workspace.ENTRIES))
        self.addCleanup(window.close)

        self.assertIs(window.app_state.workspace, Workspace.ENTRIES)
        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertIs(window._workspace_stack.currentWidget(), window.entries_view)

    def test_injected_study_mode_is_respected_at_construction(self) -> None:
        window = MainWindow(AppState(mode=ShellMode.STUDY))
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        self.assertIs(window.app_state.mode, ShellMode.STUDY)
        self.assertTrue(window._study_toolbar.isVisible())
        self.assertFalse(window._navigation_rail.isVisible())

    def test_shell_convenience_method_keeps_state_and_ui_aligned(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)

        # "normal" transition: MainWindow.show_workspace() delegates to
        # AppState -- it must never touch the widget stack independently.
        window.show_workspace(Workspace.ENTRIES)
        self.assertIs(window.app_state.workspace, Workspace.ENTRIES)
        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertIs(window._workspace_stack.currentWidget(), window.entries_view)

    def test_direct_appstate_transition_keeps_state_and_ui_aligned(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)

        # "direct" transition: bypassing MainWindow.show_workspace() and
        # calling AppState.request_navigation() directly, the way the
        # toolbar actions and any future controller code do.
        window.app_state.request_navigation(Workspace.ENTRIES)
        self.assertIs(window.app_state.workspace, Workspace.ENTRIES)
        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertIs(window._workspace_stack.currentWidget(), window.entries_view)

        window.app_state.request_navigation(Workspace.TODAY)
        self.assertIs(window.app_state.workspace, Workspace.TODAY)
        self.assertIs(window.current_workspace(), Workspace.TODAY)
        self.assertIs(window._workspace_stack.currentWidget(), window.today_view)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M162TodayControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_refresh_consumes_real_reusable_core_output(self) -> None:
        entry_id = add_entry("English", "Chinese", "word", "vertical-slice", "a small proof")
        collection_id = create_collection("M16.2 Today Slice", card_size=5)
        add_entries_to_collection([entry_id], collection_id)

        controller = TodayController()
        received: list[dict] = []
        controller.overview_changed.connect(received.append)

        overview = controller.refresh()

        self.assertIs(controller.overview, overview)
        self.assertEqual(len(received), 1)
        self.assertIn("study_workload", overview)
        self.assertIn("study_cards", overview)
        self.assertIn("recommendations", overview)
        self.assertGreaterEqual(overview["study_workload"]["total_entries"], 1)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M162EntriesTableModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_row_column_count_and_data_resolution(self) -> None:
        rows = [
            {"term": "alpha", "meaning": "first", "language": "English", "entry_type": "word",
             "status": "new", "updated_at": "2026-01-01T00:00:00Z"},
        ]
        model = EntriesTableModel(rows)

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.columnCount(), len(EntriesTableModel.COLUMNS))
        self.assertEqual(model.data(model.index(0, 0)), "alpha")
        self.assertEqual(model.headerData(0, Qt.Orientation.Horizontal), "Term")

    def test_row_at_returns_none_out_of_range(self) -> None:
        model = EntriesTableModel([])
        self.assertIsNone(model.row_at(0))


class M162PreferencesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.temp_dir.name) / "preferences.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_missing_file_returns_defaults(self) -> None:
        preferences = load_preferences(self.path)
        self.assertEqual(preferences.appearance, "System")
        self.assertEqual(preferences.accent, "Calm Blue")

    def test_round_trip_save_and_load(self) -> None:
        saved_path = save_preferences(Preferences(appearance="Dark", accent="Calm Blue"), self.path)
        self.assertEqual(saved_path, self.path)

        loaded = load_preferences(self.path)
        self.assertEqual(loaded.appearance, "Dark")
        self.assertEqual(loaded.accent, "Calm Blue")

    def test_malformed_json_degrades_to_defaults(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{not valid json", encoding="utf-8")

        preferences = load_preferences(self.path)
        self.assertEqual(preferences.appearance, "System")
        self.assertEqual(preferences.accent, "Calm Blue")

    def test_non_object_json_degrades_to_defaults(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        preferences = load_preferences(self.path)
        self.assertEqual(preferences.appearance, "System")
        self.assertEqual(preferences.accent, "Calm Blue")


class M162PreferencesPathResolutionTests(unittest.TestCase):
    def test_env_override_wins(self) -> None:
        with _isolated_environ(VOCAB_APP_PREFERENCES_PATH="/tmp/custom/preferences.json"):
            self.assertEqual(
                app_config.get_app_preferences_path(),
                Path("/tmp/custom/preferences.json").expanduser().resolve(),
            )

    def test_windows_local_appdata_path_is_not_a_cache_directory(self) -> None:
        with _isolated_environ(
            VOCAB_APP_PREFERENCES_PATH=None,
            LOCALAPPDATA="C:\\Users\\tester\\AppData\\Local",
        ):
            resolved = app_config.get_app_preferences_path()
            self.assertIn("preferences.json", resolved.name)
            self.assertNotIn("cache", str(resolved).lower())

    def test_non_windows_fallback_uses_xdg_config_not_cache(self) -> None:
        with _isolated_environ(VOCAB_APP_PREFERENCES_PATH=None, LOCALAPPDATA=None, XDG_CONFIG_HOME="/home/tester/.config"):
            resolved = app_config.get_app_preferences_path()
            self.assertEqual(resolved, Path("/home/tester/.config/vocabulary_app/preferences.json").resolve())

    def test_final_fallback_uses_dot_config_never_dot_cache(self) -> None:
        with _isolated_environ(VOCAB_APP_PREFERENCES_PATH=None, LOCALAPPDATA=None, XDG_CONFIG_HOME=None):
            resolved = app_config.get_app_preferences_path()
            self.assertIn(".config", resolved.parts)
            self.assertNotIn(".cache", resolved.parts)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M162ThemeManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_resolve_effective_appearance_system_defaults_to_light(self) -> None:
        self.assertIs(resolve_effective_appearance(Appearance.SYSTEM), Appearance.LIGHT)
        self.assertIs(resolve_effective_appearance(Appearance.DARK), Appearance.DARK)

    def test_parse_helpers_fall_back_safely_on_unknown_values(self) -> None:
        self.assertIs(parse_appearance("Not A Real Value"), Appearance.SYSTEM)
        self.assertIs(parse_accent("Not A Real Accent"), Accent.CALM_BLUE)
        self.assertIs(parse_appearance("Dark"), Appearance.DARK)

    def test_apply_light_and_dark_produce_distinct_palette_and_stylesheet(self) -> None:
        manager = ThemeManager(self.app)

        light_tokens = manager.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        light_stylesheet = self.app.styleSheet()
        light_window_color = self.app.palette().color(self.app.palette().ColorRole.Window).name()

        dark_tokens = manager.apply(Appearance.DARK, Accent.CALM_BLUE)
        dark_stylesheet = self.app.styleSheet()
        dark_window_color = self.app.palette().color(self.app.palette().ColorRole.Window).name()

        self.assertNotEqual(light_stylesheet, dark_stylesheet)
        self.assertNotEqual(light_window_color, dark_window_color)
        self.assertEqual(light_tokens.neutral.app_background, "#F4F3EF")
        self.assertEqual(dark_tokens.neutral.app_background, "#17181A")
        self.assertEqual(manager.current, (Appearance.DARK, Accent.CALM_BLUE))

    def test_accent_foreground_pairs_stay_structurally_paired(self) -> None:
        manager = ThemeManager(self.app)
        tokens = manager.apply(Appearance.LIGHT, Accent.CALM_BLUE)
        self.assertEqual(tokens.accent.primary.background, "#3E6690")
        self.assertEqual(tokens.accent.primary.foreground, "#FFFFFF")


class M162ToolbarContrastRegressionTests(unittest.TestCase):
    """
    Regression coverage for the M16.2 human-visual-acceptance finding: the
    Management-mode Today/Entries navigation actions (QToolButtons inside
    QToolBar) rendered with extremely low contrast, because
    QApplication.setStyleSheet() takes over painting for every widget
    application-wide and any widget left unstyled can silently lose its
    QPalette-resolved foreground (the exact class of bug DESIGN.md § 11.4
    already documents for unstyled table rows/status pills).

    Two checks, deliberately not pixel-grabbing a rendered widget (fragile
    across styles/DPI/antialiasing): (1) the generated stylesheet actually
    contains explicit QToolButton rules -- proving the fix is structurally
    present, not just that the token *values* happen to be safe; and (2)
    the token pairs those rules resolve to meet DESIGN.md § 12's hard
    contrast minimums, computed with the same WCAG relative-luminance
    formula DESIGN.md's own audit uses.
    """

    def test_stylesheet_explicitly_styles_toolbutton_states(self) -> None:
        for appearance in (Appearance.LIGHT, Appearance.DARK):
            tokens = resolve_tokens(appearance, Accent.CALM_BLUE)
            stylesheet = build_stylesheet(tokens)
            with self.subTest(appearance=appearance):
                self.assertIn("QToolButton {", stylesheet)
                self.assertIn("QToolButton:hover {", stylesheet)
                self.assertIn("QToolButton:pressed {", stylesheet)
                self.assertIn("QToolButton:disabled {", stylesheet)
                # the default (non-hover) rule must resolve text_primary,
                # not be left to fall through to an unstyled default.
                self.assertIn(f"color: {tokens.neutral.text_primary};", stylesheet)

    def test_toolbutton_default_state_meets_normal_text_contrast_minimum(self) -> None:
        for appearance in (Appearance.LIGHT, Appearance.DARK):
            tokens = resolve_tokens(appearance, Accent.CALM_BLUE)
            ratio = _contrast_ratio(tokens.neutral.text_primary, tokens.neutral.surface_secondary)
            with self.subTest(appearance=appearance, state="default"):
                self.assertGreaterEqual(ratio, 4.5, f"{appearance}: {ratio:.2f}:1")

    def test_toolbutton_hover_and_pressed_states_meet_contrast_minimum(self) -> None:
        for appearance in (Appearance.LIGHT, Appearance.DARK):
            tokens = resolve_tokens(appearance, Accent.CALM_BLUE)
            hover_ratio = _contrast_ratio(tokens.accent.soft.foreground, tokens.accent.soft.background)
            pressed_ratio = _contrast_ratio(tokens.accent.pressed.foreground, tokens.accent.pressed.background)
            with self.subTest(appearance=appearance, state="hover"):
                self.assertGreaterEqual(hover_ratio, 4.5, f"{appearance}: {hover_ratio:.2f}:1")
            with self.subTest(appearance=appearance, state="pressed"):
                self.assertGreaterEqual(pressed_ratio, 4.5, f"{appearance}: {pressed_ratio:.2f}:1")

    def test_toolbutton_disabled_state_meets_disabled_contrast_target(self) -> None:
        # Disabled text is intentionally weaker than normal/hover text
        # (DESIGN.md "Muted vs. Disabled": disabled targets ~3:1, not 4.5:1)
        # but must remain identifiable, never invisible.
        for appearance in (Appearance.LIGHT, Appearance.DARK):
            tokens = resolve_tokens(appearance, Accent.CALM_BLUE)
            ratio = _contrast_ratio(tokens.neutral.text_disabled, tokens.neutral.surface_secondary)
            with self.subTest(appearance=appearance):
                self.assertGreaterEqual(ratio, 2.5, f"{appearance}: {ratio:.2f}:1")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M162SqliteCompatibilityTests(unittest.TestCase):
    """
    Milestone 16 exit-criterion proof: a synthetic representative database,
    already created and populated through the existing core/migration APIs
    -- standing in for an already-existing user database -- can be reopened
    by the REAL desktop bootstrap (``build_application()``, including its
    own ``init_db()`` call) through the same ``VOCAB_APP_DB_PATH`` /
    ``get_database_path()`` resolution the real application uses, and
    preserved without destructive conversion. Never uses the user's
    personal data/vocab.db (AGENTS.md privacy rule).

    This is deliberately stronger than exercising the controllers directly
    against a monkeypatched ``db.DB_PATH``: it proves the *bootstrap path*
    itself -- the same code a real user's `python -m src.ui_desktop` runs --
    does not destructively touch a pre-existing compatible database.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.preferences_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "existing_compatible.sqlite3"
        self.preferences_path = Path(self.preferences_dir.name) / "preferences.json"
        self.original_db_path = db.DB_PATH

        # 1. create/init a synthetic "already existing" current database,
        #    entirely independent of the desktop bootstrap exercised below.
        db.DB_PATH = self.db_path
        db.init_db()

        # 2. populate a small representative set of Entries/Collection data
        entry_ids = [
            add_entry("English", "Chinese", "word", "existing-alpha", "meaning alpha"),
            add_entry("French", "Chinese", "word", "existing-beta", "sens beta"),
        ]
        collection_id = create_collection("Pre-Existing Collection", card_size=5)
        add_entries_to_collection(entry_ids, collection_id)

        with db.get_connection() as connection:
            self.schema_version_before = get_schema_version(connection)
            self.app_data_version_before = get_metadata(connection, "app_data_version")

        # 3. restore module state so step 4 resolves the database entirely
        #    on its own, exactly as it would for a real already-existing
        #    user database -- setUp does not leave db.DB_PATH pointed at it.
        db.DB_PATH = self.original_db_path

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()
        self.preferences_dir.cleanup()

    def test_desktop_bootstrap_reopens_existing_database_without_destructive_conversion(self) -> None:
        self.assertTrue(self.db_path.is_file())

        with _isolated_environ(
            VOCAB_APP_DB_PATH=str(self.db_path),
            VOCAB_APP_PREFERENCES_PATH=str(self.preferences_path),
        ):
            # 4. point the desktop configuration at that existing database
            #    through the *real* resolution path -- not an assumed
            #    equivalence to a direct db.DB_PATH assignment.
            resolved_path = app_config.get_database_path()
            self.assertEqual(resolved_path, self.db_path.resolve())

            # db.DB_PATH is a module-level constant computed once at import
            # time from get_database_path(); align it with the
            # just-verified resolution before exercising the bootstrap,
            # the same constraint every test in this repository's suite
            # works around (see tests/test_m15_3_audio_export.py).
            db.DB_PATH = resolved_path

            # 5. construct/run the relevant desktop controllers/shell path
            #    through the REAL bootstrap, including its own init_db()
            #    call -- not a hand-assembled controller-only path.
            application, window, theme_manager = build_application([])
            self.addCleanup(window.close)

            # 6. verify records surface through the real desktop path
            self.assertIs(window.current_workspace(), Workspace.TODAY)
            overview = window.today_controller.overview
            self.assertIsNotNone(overview)
            self.assertGreaterEqual(overview["study_workload"]["total_entries"], 2)

            window.show_workspace(Workspace.ENTRIES)
            row_count = window.entries_controller.model.rowCount()
            self.assertEqual(row_count, 2)
            terms = {
                window.entries_controller.model.row_at(i)["term"]
                for i in range(row_count)
            }
            self.assertEqual(terms, {"existing-alpha", "existing-beta"})

            # 7. verify current schema/app-data identity remains intact --
            #    no destructive re-migration occurred.
            with db.get_connection() as connection:
                schema_version_after = get_schema_version(connection)
                app_data_version_after = get_metadata(connection, "app_data_version")

        self.assertEqual(schema_version_after, self.schema_version_before)
        self.assertEqual(schema_version_after, CURRENT_SCHEMA_VERSION)
        self.assertEqual(app_data_version_after, self.app_data_version_before)
        self.assertEqual(app_data_version_after, APP_DATA_VERSION)


class M162ArchitectureBoundaryTests(unittest.TestCase):
    def test_audit_architecture_reports_no_serious_violations(self) -> None:
        self.assertEqual(
            audit_architecture_main(),
            0,
            "scripts/audit_architecture.py reported a serious boundary violation; "
            "run it directly for details.",
        )


if __name__ == "__main__":
    unittest.main()

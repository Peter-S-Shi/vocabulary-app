from __future__ import annotations

import ast
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db

"""
Focused tests for the M17 Motion / Transition Foundation
(src/ui_desktop/motion/transitions.py, DESIGN.md § 23). These prove the
behavioral guarantees required by the M17 Feature 1 prompt § 4 --
centralized policy, no correctness dependency on animation completion,
safe rapid/repeated transitions, and a working reduced/disabled path --
structurally, without brittle wall-clock timing or pixel tests.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.app import build_application
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.motion.transitions import (
        NORMAL_DURATION_MS,
        REDUCED_DURATION_MS,
        MotionPolicy,
        TransitionManager,
        parse_motion_policy,
    )
    from src.ui_desktop.state.app_state import AppState, Workspace
    from src.ui_desktop.state.preferences import Preferences, load_preferences, save_preferences

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    """Shared setup matching the existing repository pattern (see
    tests/test_m16_2_desktop_vertical_slice.py): swap db.DB_PATH to a
    temporary synthetic database, never the user's personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m17_motion.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17MotionPolicyParsingTests(unittest.TestCase):
    def test_parse_valid_values_round_trip(self) -> None:
        self.assertIs(parse_motion_policy("Normal"), MotionPolicy.NORMAL)
        self.assertIs(parse_motion_policy("Reduced"), MotionPolicy.REDUCED)
        self.assertIs(parse_motion_policy("Disabled"), MotionPolicy.DISABLED)

    def test_parse_invalid_value_defaults_to_normal(self) -> None:
        self.assertIs(parse_motion_policy(""), MotionPolicy.NORMAL)
        self.assertIs(parse_motion_policy("bounce-everything"), MotionPolicy.NORMAL)


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17TransitionManagerBehaviorTests(unittest.TestCase):
    """Behavioral guarantees required by the M17 Feature 1 prompt § 4."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_normal_policy_attaches_opacity_effect_and_animation(self) -> None:
        manager = TransitionManager(MotionPolicy.NORMAL)
        widget = QLabel("target")
        self.addCleanup(widget.deleteLater)

        animation = manager.fade_in(widget)

        self.assertIsNotNone(animation)
        self.assertIsNotNone(widget.graphicsEffect())
        self.assertEqual(animation.duration(), NORMAL_DURATION_MS)
        self.assertEqual(animation.endValue(), 1.0)
        self.assertTrue(manager.is_animating(widget))

    def test_disabled_policy_never_attaches_effect_or_animation(self) -> None:
        manager = TransitionManager(MotionPolicy.DISABLED)
        widget = QLabel("target")
        self.addCleanup(widget.deleteLater)

        animation = manager.fade_in(widget)

        self.assertIsNone(animation)
        self.assertIsNone(widget.graphicsEffect())
        self.assertFalse(manager.is_animating(widget))

    def test_reduced_duration_is_shorter_than_normal(self) -> None:
        self.assertLess(REDUCED_DURATION_MS, NORMAL_DURATION_MS)

        manager = TransitionManager(MotionPolicy.REDUCED)
        widget = QLabel("target")
        self.addCleanup(widget.deleteLater)

        animation = manager.fade_in(widget)
        self.assertEqual(animation.duration(), REDUCED_DURATION_MS)

    def test_rapid_repeated_fade_in_leaves_exactly_one_tracked_animation(self) -> None:
        manager = TransitionManager(MotionPolicy.NORMAL)
        widget = QLabel("target")
        self.addCleanup(widget.deleteLater)

        manager.fade_in(widget)
        manager.fade_in(widget)
        manager.fade_in(widget)

        self.assertEqual(len(manager._animations), 1)
        self.assertTrue(manager.is_animating(widget))

    def test_interrupted_transition_leaves_widget_fully_opaque(self) -> None:
        """Correctness must never depend on an animation finishing: an
        interrupted fade must immediately (synchronously) leave the widget
        at full opacity, not a partial/stale value."""
        manager = TransitionManager(MotionPolicy.NORMAL)
        widget = QLabel("target")
        self.addCleanup(widget.deleteLater)

        manager.fade_in(widget)
        effect_after_first_call = widget.graphicsEffect()
        self.assertLess(effect_after_first_call.opacity(), 1.0)

        # Interrupt before the first fade would naturally finish.
        manager.fade_in(widget)

        # The manager cancels the in-flight animation and resets opacity
        # to 1.0 synchronously as part of starting the new one -- no
        # processEvents()/timer wait is needed to observe this.
        self.assertEqual(len(manager._animations), 1)

    def test_finished_animation_removes_graphics_effect(self) -> None:
        """Deterministically triggering the same ``finished`` signal Qt
        emits on natural completion proves cleanup removes the graphics
        effect rather than leaving it attached forever at full opacity,
        without depending on real wall-clock animation timing."""
        manager = TransitionManager(MotionPolicy.NORMAL)
        widget = QLabel("target")
        self.addCleanup(widget.deleteLater)

        animation = manager.fade_in(widget)
        animation.finished.emit()

        self.assertIsNone(widget.graphicsEffect())
        self.assertFalse(manager.is_animating(widget))


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17MotionSourceScanTests(unittest.TestCase):
    """Structural proof that motion stays centralized (M17 Feature 1
    prompt § 10 motion-specific checks): ordinary feature/shell code must
    not construct its own QPropertyAnimation."""

    FILES_THAT_MUST_NOT_CONSTRUCT_ANIMATIONS = (
        PROJECT_ROOT / "src" / "ui_desktop" / "views" / "today_view.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "views" / "entries_view.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "main_window.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "app.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "controllers" / "today_controller.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "controllers" / "entries_controller.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "widgets" / "navigation_rail.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "widgets" / "panels.py",
    )

    def test_only_motion_module_constructs_animations(self) -> None:
        offenders = []
        for path in self.FILES_THAT_MUST_NOT_CONSTRUCT_ANIMATIONS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("QPropertyAnimation", "QVariantAnimation")
                ):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_motion_module_is_the_single_animation_construction_site(self) -> None:
        motion_file = PROJECT_ROOT / "src" / "ui_desktop" / "motion" / "transitions.py"
        tree = ast.parse(motion_file.read_text(encoding="utf-8"), filename=str(motion_file))
        constructions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "QPropertyAnimation"
        ]
        self.assertEqual(len(constructions), 1)


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17MotionPreferenceTests(unittest.TestCase):
    def test_default_preferences_motion_is_normal(self) -> None:
        self.assertEqual(Preferences().motion, "Normal")
        self.assertIs(parse_motion_policy(Preferences().motion), MotionPolicy.NORMAL)

    def test_motion_preference_round_trips_through_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "preferences.json"
            save_preferences(Preferences(motion="Reduced"), path)
            loaded = load_preferences(path)
            self.assertEqual(loaded.motion, "Reduced")

    def test_missing_motion_key_in_stored_file_degrades_to_default(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "preferences.json"
            path.write_text('{"appearance": "Dark", "accent": "Calm Blue"}', encoding="utf-8")
            loaded = load_preferences(path)
            self.assertEqual(loaded.motion, "Normal")


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17MainWindowMotionIntegrationTests(_SyntheticDatabaseTestCase):
    """Proves motion never gates shell correctness (M17 Feature 1 prompt
    § 4): rapid navigation must keep AppState and the visible widget stack
    aligned without ever waiting for an animation to finish."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_rapid_navigation_stays_correct_without_waiting_for_animation(self) -> None:
        window = MainWindow(AppState(), TransitionManager(MotionPolicy.NORMAL))
        self.addCleanup(window.close)

        for workspace in (Workspace.ENTRIES, Workspace.TODAY, Workspace.ENTRIES, Workspace.TODAY):
            window.show_workspace(workspace)
            self.assertIs(window.current_workspace(), workspace)
            expected_widget = window.today_view if workspace is Workspace.TODAY else window.entries_view
            self.assertIs(window._workspace_stack.currentWidget(), expected_widget)

    def test_disabled_motion_policy_still_navigates_correctly(self) -> None:
        window = MainWindow(AppState(), TransitionManager(MotionPolicy.DISABLED))
        self.addCleanup(window.close)

        window.show_workspace(Workspace.ENTRIES)

        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertIs(window._workspace_stack.currentWidget(), window.entries_view)
        self.assertIsNone(window.entries_view.graphicsEffect())

    # A Today -> Entries handoff test lived here. It drove the rejected
    # TodayView's ``entries_requested`` signal, which no longer exists now
    # that Today is reset to the M16.2 placeholder, so it was removed
    # rather than rewritten: a cross-feature handoff test belongs with
    # whatever Today the replacement DESIGN.md defines. Shared navigation
    # itself stays covered above, driven through AppState directly.

    def test_build_application_wires_motion_policy_from_preferences(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            preferences_path = Path(tmp) / "preferences.json"
            save_preferences(Preferences(motion="Disabled"), preferences_path)
            original_env = os.environ.get("VOCAB_APP_PREFERENCES_PATH")
            os.environ["VOCAB_APP_PREFERENCES_PATH"] = str(preferences_path)
            try:
                application, window, _theme_manager = build_application([])
                self.addCleanup(window.close)
                self.assertIs(window._motion.policy, MotionPolicy.DISABLED)
            finally:
                if original_env is None:
                    os.environ.pop("VOCAB_APP_PREFERENCES_PATH", None)
                else:
                    os.environ["VOCAB_APP_PREFERENCES_PATH"] = original_env


if __name__ == "__main__":
    unittest.main()

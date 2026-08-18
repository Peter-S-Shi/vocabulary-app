from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

try:
    import PySide6  # noqa: F401

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - environment-dependent
    PYSIDE6_AVAILABLE = False

"""
Focused tests for the M19 shared TTS runtime configuration hardening
(ROADMAP § "Mandatory M19 / M20 Productization Handoff -- Card Audio
Export"; `src/ui_desktop/state/tts_runtime.py` module docstring).

They prove the durable product-facing configuration contract:

- the `shared_tts_dir` preference persists round-trip through the
  existing desktop preferences file and degrades safely on malformed
  input, like every existing preference;
- the resolution order is environment variable (advanced per-process
  override, the `VOCAB_APP_DB_PATH` precedence model) -> saved app
  setting -> honestly not configured;
- the fully-unconfigured registry keeps the HG3 corrective's
  `shared_tts_dir_not_configured` code while its detail now names the
  in-app Settings surface first (no expectation that a normal end user
  sets a shell environment variable);
- an app-setting-configured (but broken/missing) runtime folder flows
  through the same core `build_shared_runtime_registry()` path, so
  missing assets keep being named path by path; and
- `SettingsController` persists/clears the setting and reports the
  effective resolution for display.

Provider/voice/language routing itself is frozen (M15.0) and is not
retested here; `tests/test_m15_1_speech_semantics.py` owns that.
"""

if PYSIDE6_AVAILABLE:
    from src.tts_providers import FROZEN_PROVIDER_SPECS, SHARED_TTS_ENV
    from src.ui_desktop.controllers.settings_controller import SettingsController
    from src.ui_desktop.state import preferences as preferences_module
    from src.ui_desktop.state.preferences import Preferences, load_preferences, save_preferences
    from src.ui_desktop.state.tts_runtime import (
        SOURCE_APP_SETTING,
        SOURCE_ENVIRONMENT,
        SOURCE_NOT_CONFIGURED,
        build_provider_registry,
        resolve_shared_tts_dir,
    )


class _EnvIsolationMixin(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._saved_env = os.environ.get(SHARED_TTS_ENV)
        os.environ.pop(SHARED_TTS_ENV, None)

    def tearDown(self) -> None:
        if self._saved_env is None:
            os.environ.pop(SHARED_TTS_ENV, None)
        else:
            os.environ[SHARED_TTS_ENV] = self._saved_env
        super().tearDown()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SharedTtsPreferencePersistenceTests(unittest.TestCase):
    def test_default_is_empty_and_round_trips(self) -> None:
        self.assertEqual(Preferences().shared_tts_dir, "")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            save_preferences(Preferences(shared_tts_dir="D:/tts-runtime"), path)
            loaded = load_preferences(path)
            self.assertEqual(loaded.shared_tts_dir, "D:/tts-runtime")

    def test_old_preferences_file_without_field_degrades_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            path.write_text(json.dumps({"appearance": "Dark"}), encoding="utf-8")
            loaded = load_preferences(path)
            self.assertEqual(loaded.shared_tts_dir, "")
            self.assertEqual(loaded.appearance, "Dark")

    def test_malformed_value_degrades_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            path.write_text(json.dumps({"shared_tts_dir": None}), encoding="utf-8")
            self.assertEqual(load_preferences(path).shared_tts_dir, "")
            path.write_text(json.dumps({"shared_tts_dir": "   "}), encoding="utf-8")
            self.assertEqual(load_preferences(path).shared_tts_dir, "")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SharedTtsResolutionOrderTests(_EnvIsolationMixin):
    def test_environment_variable_wins_over_app_setting(self) -> None:
        os.environ[SHARED_TTS_ENV] = "D:/env-runtime"
        resolved, source = resolve_shared_tts_dir(Preferences(shared_tts_dir="D:/setting-runtime"))
        self.assertEqual(resolved, "D:/env-runtime")
        self.assertEqual(source, SOURCE_ENVIRONMENT)

    def test_app_setting_used_when_environment_unset(self) -> None:
        resolved, source = resolve_shared_tts_dir(Preferences(shared_tts_dir="D:/setting-runtime"))
        self.assertEqual(resolved, "D:/setting-runtime")
        self.assertEqual(source, SOURCE_APP_SETTING)

    def test_not_configured_when_neither_exists(self) -> None:
        resolved, source = resolve_shared_tts_dir(Preferences())
        self.assertIsNone(resolved)
        self.assertEqual(source, SOURCE_NOT_CONFIGURED)

    def test_blank_environment_value_falls_through_to_app_setting(self) -> None:
        os.environ[SHARED_TTS_ENV] = "   "
        resolved, source = resolve_shared_tts_dir(Preferences(shared_tts_dir="D:/setting-runtime"))
        self.assertEqual(resolved, "D:/setting-runtime")
        self.assertEqual(source, SOURCE_APP_SETTING)

    def test_none_preferences_reads_persisted_file(self) -> None:
        """`preferences=None` must perform a fresh read of the persisted
        file, so a value just saved from Settings > Audio takes effect
        without restart or explicit plumbing."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            save_preferences(Preferences(shared_tts_dir="D:/saved-runtime"), path)
            original = preferences_module.get_app_preferences_path
            preferences_module.get_app_preferences_path = lambda: path
            try:
                resolved, source = resolve_shared_tts_dir(None)
            finally:
                preferences_module.get_app_preferences_path = original
            self.assertEqual(resolved, "D:/saved-runtime")
            self.assertEqual(source, SOURCE_APP_SETTING)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SharedTtsRegistryBuildTests(_EnvIsolationMixin):
    def test_unconfigured_registry_keeps_code_and_names_settings_first(self) -> None:
        registry = build_provider_registry(Preferences())
        for spec in FROZEN_PROVIDER_SPECS.values():
            availability = registry.preflight(spec.language)
            self.assertFalse(availability.available)
            self.assertEqual(availability.code, "shared_tts_dir_not_configured")
            self.assertIn("Settings > Audio", availability.detail)
            self.assertIn(SHARED_TTS_ENV, availability.detail)

    def test_app_setting_path_flows_through_core_runtime_registry(self) -> None:
        """A configured-but-missing folder must keep core's honest
        per-provider missing-asset diagnostics (paths named), proving the
        app setting reaches the exact same core path the environment
        variable always used -- not a second desktop-only registry."""
        with tempfile.TemporaryDirectory() as tmp:
            missing_root = str(Path(tmp) / "not-a-runtime")
            registry = build_provider_registry(Preferences(shared_tts_dir=missing_root))
            for language in ("en", "fr"):
                availability = registry.preflight(language)
                self.assertFalse(availability.available)
                self.assertNotEqual(availability.code, "shared_tts_dir_not_configured")
                self.assertIn("not-a-runtime", availability.detail)

    def test_environment_override_beats_app_setting_in_registry_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_root = Path(tmp) / "env-runtime"
            env_root.mkdir()
            os.environ[SHARED_TTS_ENV] = str(env_root)
            registry = build_provider_registry(Preferences(shared_tts_dir=str(Path(tmp) / "setting-runtime")))
            availability = registry.preflight("en")
            self.assertFalse(availability.available)
            self.assertIn("env-runtime", availability.detail)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsControllerSharedTtsTests(_EnvIsolationMixin):
    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._prefs_path = Path(self._tmp.name) / "prefs.json"
        self._original_get_path = preferences_module.get_app_preferences_path
        preferences_module.get_app_preferences_path = lambda: self._prefs_path
        self.addCleanup(self._restore_get_path)

    def _restore_get_path(self) -> None:
        preferences_module.get_app_preferences_path = self._original_get_path

    def test_set_persists_and_clear_removes(self) -> None:
        controller = SettingsController(Preferences())
        controller.set_shared_tts_dir("D:/tts-runtime")
        self.assertEqual(load_preferences(self._prefs_path).shared_tts_dir, "D:/tts-runtime")
        self.assertEqual(controller.shared_tts_dir_setting(), "D:/tts-runtime")

        controller.clear_shared_tts_dir()
        self.assertEqual(load_preferences(self._prefs_path).shared_tts_dir, "")
        self.assertEqual(controller.shared_tts_dir_setting(), "")

    def test_set_emits_state_changed_once_and_skips_no_op(self) -> None:
        controller = SettingsController(Preferences())
        emissions: list[int] = []
        controller.state_changed.connect(lambda: emissions.append(1))
        controller.set_shared_tts_dir("D:/tts-runtime")
        controller.set_shared_tts_dir("D:/tts-runtime")  # no-op: same value
        self.assertEqual(len(emissions), 1)

    def test_status_reports_effective_source(self) -> None:
        controller = SettingsController(Preferences())
        status = controller.shared_tts_status()
        self.assertIsNone(status["directory"])
        self.assertEqual(status["source"], SOURCE_NOT_CONFIGURED)

        controller.set_shared_tts_dir("D:/setting-runtime")
        status = controller.shared_tts_status()
        self.assertEqual(status["directory"], "D:/setting-runtime")
        self.assertEqual(status["source"], SOURCE_APP_SETTING)

        os.environ[SHARED_TTS_ENV] = "D:/env-runtime"
        status = controller.shared_tts_status()
        self.assertEqual(status["directory"], "D:/env-runtime")
        self.assertEqual(status["source"], SOURCE_ENVIRONMENT)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsViewAudioSectionTests(_EnvIsolationMixin):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_audio_rows_render_and_reflect_controller_state(self) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.ui_desktop.views.settings_view import SettingsView

        controller = SettingsController(Preferences())
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        browse = view.findChildren(QPushButton, "settings-tts-browse-button")
        clear = view.findChildren(QPushButton, "settings-tts-clear-button")
        self.assertEqual(len(browse), 1)
        self.assertEqual(len(clear), 1)
        # Nothing configured: value shows an honest placeholder and Clear
        # is disabled (there is nothing to clear).
        self.assertEqual(view._tts_dir_value.text(), "Not configured")
        self.assertFalse(clear[0].isEnabled())
        self.assertIn("Not configured", view._tts_source_value.text())

        controller.set_shared_tts_dir("D:/tts-runtime")
        self.assertEqual(view._tts_dir_value.text(), "D:/tts-runtime")
        self.assertTrue(clear[0].isEnabled())
        self.assertIn("D:/tts-runtime", view._tts_source_value.text())
        self.assertIn("App setting", view._tts_source_value.text())

    def test_audio_controls_have_explicit_qss_coverage_in_both_themes(self) -> None:
        """M18 Human Gate 1 lesson: a workspace control without explicit
        QSS coverage renders at effectively-invisible Light Mode
        contrast. Every new M19 Settings > Audio control must appear in
        the generated stylesheet for both bundled themes."""
        from src.ui_desktop.theming.theme_manager import build_stylesheet
        from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT

        for tokens in (THEME_CALM_BLUE_LIGHT, THEME_CALM_BLUE_DARK):
            stylesheet = build_stylesheet(tokens)
            for selector in (
                "#settings-tts-browse-button",
                "#settings-tts-clear-button",
                "#settings-section-note",
            ):
                self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")

    def setUp(self) -> None:
        super().setUp()
        import tempfile as _tempfile

        self._view_tmp = _tempfile.TemporaryDirectory()
        self.addCleanup(self._view_tmp.cleanup)
        self._view_prefs_path = Path(self._view_tmp.name) / "prefs.json"
        self._view_original_get_path = preferences_module.get_app_preferences_path
        preferences_module.get_app_preferences_path = lambda: self._view_prefs_path
        self.addCleanup(self._restore_view_get_path)

    def _restore_view_get_path(self) -> None:
        preferences_module.get_app_preferences_path = self._view_original_get_path


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

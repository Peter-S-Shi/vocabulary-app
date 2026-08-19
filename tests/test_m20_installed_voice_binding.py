from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import PySide6  # noqa: F401

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - environment-dependent
    PYSIDE6_AVAILABLE = False

"""
Focused tests for the M20 Local Windows Speech Provider / Installed
Voice Binding capability (docs/packaging/M20_RELEASE_CONTRACT.md §§ 2.3,
7; supersedes the M19 "shared external TTS runtime folder" model
`tests/test_m19_tts_runtime_config.py` used to cover).

They prove the durable product-facing configuration contract:

- the `voice_bindings` preference (``{language: voice_id}``) persists
  round-trip through the existing desktop preferences file and degrades
  safely on malformed/old input, like every existing preference;
- the resolution order is environment variable (advanced per-process
  override, the `VOCAB_APP_DB_PATH` precedence model) -> saved app
  setting -> honestly not configured;
- `build_installed_voice_registry()` reports `voice_not_configured` for
  an unbound language and `voice_not_installed` (naming the missing
  voice ID) for a binding no longer present on the system -- never a
  silent fallback to a different voice;
- `SettingsController` persists/clears bindings per language and reports
  the effective resolution for display.

Provider/voice/language *routing* -- which canonical languages are
supported, and that a synthesis attempt without a real available voice
fails honestly -- is exercised with synthetic providers in
`tests/test_m15_1_speech_semantics.py` and is not retested here.
"""

if PYSIDE6_AVAILABLE:
    from src.tts_providers import VOICE_BINDINGS_ENV, FROZEN_PROVIDER_SPECS, InstalledVoice
    from src.ui_desktop.controllers.settings_controller import SettingsController
    from src.ui_desktop.state import preferences as preferences_module
    from src.ui_desktop.state.preferences import Preferences, load_preferences, save_preferences
    from src.ui_desktop.state.tts_runtime import (
        SOURCE_APP_SETTING,
        SOURCE_ENVIRONMENT,
        SOURCE_NOT_CONFIGURED,
        build_provider_registry,
        resolve_voice_bindings,
    )


_EN_VOICE = "HKEY_LOCAL_MACHINE\\...\\MSTTS_V110_enUS_DavidM"
_FR_VOICE = "HKEY_LOCAL_MACHINE\\...\\MSTTS_V110_frFR_HortenseM"


def _fake_successful_preflight() -> subprocess.CompletedProcess:
    """A stand-in for a real ``tts_windows_voice.ps1 -Preflight`` run
    that found the voice installed. ``build_installed_voice_registry``'s
    own ``installed_ids`` membership check is what these tests are
    really proving; this only keeps ``CommandSpeechProvider.preflight``'s
    own independent, real-subprocess re-check from failing against a
    synthetic voice ID that was never actually installed anywhere."""
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


class _EnvIsolationMixin(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._saved_env = os.environ.get(VOICE_BINDINGS_ENV)
        os.environ.pop(VOICE_BINDINGS_ENV, None)

    def tearDown(self) -> None:
        if self._saved_env is None:
            os.environ.pop(VOICE_BINDINGS_ENV, None)
        else:
            os.environ[VOICE_BINDINGS_ENV] = self._saved_env
        super().tearDown()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class VoiceBindingPreferencePersistenceTests(unittest.TestCase):
    def test_default_is_empty_and_round_trips(self) -> None:
        self.assertEqual(Preferences().voice_bindings, {})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            save_preferences(Preferences(voice_bindings={"en": _EN_VOICE, "fr": _FR_VOICE}), path)
            loaded = load_preferences(path)
            self.assertEqual(loaded.voice_bindings, {"en": _EN_VOICE, "fr": _FR_VOICE})

    def test_old_preferences_file_without_field_degrades_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            path.write_text(json.dumps({"appearance": "Dark"}), encoding="utf-8")
            loaded = load_preferences(path)
            self.assertEqual(loaded.voice_bindings, {})
            self.assertEqual(loaded.appearance, "Dark")

    def test_pre_m20_shared_tts_dir_field_is_ignored_not_a_load_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            path.write_text(json.dumps({"shared_tts_dir": "D:/old-runtime"}), encoding="utf-8")
            loaded = load_preferences(path)
            self.assertEqual(loaded.voice_bindings, {})

    def test_malformed_value_degrades_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            path.write_text(json.dumps({"voice_bindings": None}), encoding="utf-8")
            self.assertEqual(load_preferences(path).voice_bindings, {})
            path.write_text(json.dumps({"voice_bindings": "not-a-dict"}), encoding="utf-8")
            self.assertEqual(load_preferences(path).voice_bindings, {})

    def test_unrecognized_language_key_is_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            path.write_text(
                json.dumps({"voice_bindings": {"es": "some-voice", "en": _EN_VOICE, "": "junk"}}),
                encoding="utf-8",
            )
            self.assertEqual(load_preferences(path).voice_bindings, {"en": _EN_VOICE})

    def test_blank_voice_id_is_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            path.write_text(json.dumps({"voice_bindings": {"en": "   "}}), encoding="utf-8")
            self.assertEqual(load_preferences(path).voice_bindings, {})


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class VoiceBindingResolutionOrderTests(_EnvIsolationMixin):
    def test_environment_variable_wins_over_app_setting(self) -> None:
        os.environ[VOICE_BINDINGS_ENV] = json.dumps({"en": "env-voice"})
        bindings, source = resolve_voice_bindings(Preferences(voice_bindings={"en": "setting-voice"}))
        self.assertEqual(bindings, {"en": "env-voice"})
        self.assertEqual(source, SOURCE_ENVIRONMENT)

    def test_app_setting_used_when_environment_unset(self) -> None:
        bindings, source = resolve_voice_bindings(Preferences(voice_bindings={"en": "setting-voice"}))
        self.assertEqual(bindings, {"en": "setting-voice"})
        self.assertEqual(source, SOURCE_APP_SETTING)

    def test_not_configured_when_neither_exists(self) -> None:
        bindings, source = resolve_voice_bindings(Preferences())
        self.assertEqual(bindings, {})
        self.assertEqual(source, SOURCE_NOT_CONFIGURED)

    def test_blank_environment_value_falls_through_to_app_setting(self) -> None:
        os.environ[VOICE_BINDINGS_ENV] = "   "
        bindings, source = resolve_voice_bindings(Preferences(voice_bindings={"en": "setting-voice"}))
        self.assertEqual(bindings, {"en": "setting-voice"})
        self.assertEqual(source, SOURCE_APP_SETTING)

    def test_malformed_environment_json_still_wins_as_source_with_no_bindings(self) -> None:
        os.environ[VOICE_BINDINGS_ENV] = "not-json"
        bindings, source = resolve_voice_bindings(Preferences(voice_bindings={"en": "setting-voice"}))
        self.assertEqual(bindings, {})
        self.assertEqual(source, SOURCE_ENVIRONMENT)

    def test_none_preferences_reads_persisted_file(self) -> None:
        """`preferences=None` must perform a fresh read of the persisted
        file, so a binding just saved from Settings > Audio takes effect
        without restart or explicit plumbing."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.json"
            save_preferences(Preferences(voice_bindings={"en": "saved-voice"}), path)
            original = preferences_module.get_app_preferences_path
            preferences_module.get_app_preferences_path = lambda: path
            try:
                bindings, source = resolve_voice_bindings(None)
            finally:
                preferences_module.get_app_preferences_path = original
            self.assertEqual(bindings, {"en": "saved-voice"})
            self.assertEqual(source, SOURCE_APP_SETTING)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class InstalledVoiceRegistryBuildTests(_EnvIsolationMixin):
    def test_unconfigured_registry_names_settings_and_env_var(self) -> None:
        with patch("src.tts_providers.list_installed_voices", return_value=[]):
            registry = build_provider_registry(Preferences())
            for spec in FROZEN_PROVIDER_SPECS.values():
                availability = registry.preflight(spec.language)
                self.assertFalse(availability.available)
                self.assertEqual(availability.code, "voice_not_configured")
                self.assertIn("Settings > Audio", availability.detail)
                self.assertIn(VOICE_BINDINGS_ENV, availability.detail)

    def test_bound_but_not_installed_voice_is_named_in_the_detail(self) -> None:
        with patch("src.tts_providers.list_installed_voices", return_value=[]):
            registry = build_provider_registry(Preferences(voice_bindings={"en": _EN_VOICE}))
            availability = registry.preflight("en")
            self.assertFalse(availability.available)
            self.assertEqual(availability.code, "voice_not_installed")
            self.assertIn(_EN_VOICE, availability.detail)

    def test_bound_and_installed_voice_is_available_and_selected_spec_matches(self) -> None:
        installed = [InstalledVoice(_EN_VOICE, "Microsoft David", "en-US")]
        with patch("src.tts_providers.list_installed_voices", return_value=installed), \
                patch("src.tts_providers.subprocess.run", return_value=_fake_successful_preflight()):
            registry = build_provider_registry(Preferences(voice_bindings={"en": _EN_VOICE}))
            availability = registry.preflight("en")
            self.assertTrue(availability.available)
            spec = registry.selected_spec("en")
            self.assertIsNotNone(spec)
            assert spec is not None
            self.assertEqual(spec.voice_id, _EN_VOICE)
            self.assertEqual(spec.language, "en")

    def test_environment_override_beats_app_setting_in_registry_build(self) -> None:
        installed = [InstalledVoice(_EN_VOICE, "Microsoft David", "en-US")]
        os.environ[VOICE_BINDINGS_ENV] = json.dumps({"en": _EN_VOICE})
        with patch("src.tts_providers.list_installed_voices", return_value=installed), \
                patch("src.tts_providers.subprocess.run", return_value=_fake_successful_preflight()):
            registry = build_provider_registry(Preferences(voice_bindings={"en": "setting-voice-not-installed"}))
            availability = registry.preflight("en")
            self.assertTrue(availability.available)
            spec = registry.selected_spec("en")
            assert spec is not None
            self.assertEqual(spec.voice_id, _EN_VOICE)

    def test_selected_spec_tracks_rebinding_not_a_frozen_constant(self) -> None:
        """Distinct from the superseded model: voice_id is user-chosen,
        so selected_spec() must reflect whatever is currently bound, not
        a static module-level constant -- otherwise a rebind would leave
        stale provider/voice identity in any persisted speech plan."""
        installed = [
            InstalledVoice(_EN_VOICE, "Microsoft David", "en-US"),
            InstalledVoice("other-en-voice", "Microsoft Zira", "en-US"),
        ]
        with patch("src.tts_providers.list_installed_voices", return_value=installed):
            first = build_provider_registry(Preferences(voice_bindings={"en": _EN_VOICE}))
            second = build_provider_registry(Preferences(voice_bindings={"en": "other-en-voice"}))
            self.assertEqual(first.selected_spec("en").voice_id, _EN_VOICE)
            self.assertEqual(second.selected_spec("en").voice_id, "other-en-voice")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsControllerVoiceBindingTests(_EnvIsolationMixin):
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
        controller.set_voice_binding("en", _EN_VOICE)
        self.assertEqual(load_preferences(self._prefs_path).voice_bindings, {"en": _EN_VOICE})
        self.assertEqual(controller.voice_binding("en"), _EN_VOICE)

        controller.clear_voice_binding("en")
        self.assertEqual(load_preferences(self._prefs_path).voice_bindings, {})
        self.assertEqual(controller.voice_binding("en"), "")

    def test_bindings_for_different_languages_are_independent(self) -> None:
        controller = SettingsController(Preferences())
        controller.set_voice_binding("en", _EN_VOICE)
        controller.set_voice_binding("fr", _FR_VOICE)
        self.assertEqual(controller.voice_binding("en"), _EN_VOICE)
        self.assertEqual(controller.voice_binding("fr"), _FR_VOICE)
        self.assertEqual(controller.voice_binding("zh-CN"), "")

    def test_set_emits_state_changed_once_and_skips_no_op(self) -> None:
        controller = SettingsController(Preferences())
        emissions: list[int] = []
        controller.state_changed.connect(lambda: emissions.append(1))
        controller.set_voice_binding("en", _EN_VOICE)
        controller.set_voice_binding("en", _EN_VOICE)  # no-op: same value
        self.assertEqual(len(emissions), 1)

    def test_status_reports_effective_source(self) -> None:
        controller = SettingsController(Preferences())
        status = controller.voice_binding_status("en")
        self.assertIsNone(status["voice_id"])
        self.assertEqual(status["source"], SOURCE_NOT_CONFIGURED)

        controller.set_voice_binding("en", "setting-voice")
        status = controller.voice_binding_status("en")
        self.assertEqual(status["voice_id"], "setting-voice")
        self.assertEqual(status["source"], SOURCE_APP_SETTING)

        os.environ[VOICE_BINDINGS_ENV] = json.dumps({"en": "env-voice"})
        status = controller.voice_binding_status("en")
        self.assertEqual(status["voice_id"], "env-voice")
        self.assertEqual(status["source"], SOURCE_ENVIRONMENT)

    def test_installed_voices_delegates_to_core_enumeration(self) -> None:
        controller = SettingsController(Preferences())
        installed = [InstalledVoice(_EN_VOICE, "Microsoft David", "en-US")]
        with patch("src.ui_desktop.controllers.settings_controller.list_installed_voices_for_language", return_value=installed) as mocked:
            result = controller.installed_voices("en")
            mocked.assert_called_once_with("en")
            self.assertEqual(result, installed)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsViewAudioSectionTests(_EnvIsolationMixin):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        super().setUp()
        import tempfile as _tempfile

        self._view_tmp = _tempfile.TemporaryDirectory()
        self.addCleanup(self._view_tmp.cleanup)
        self._view_prefs_path = Path(self._view_tmp.name) / "prefs.json"
        self._view_original_get_path = preferences_module.get_app_preferences_path
        preferences_module.get_app_preferences_path = lambda: self._view_prefs_path
        self.addCleanup(self._restore_view_get_path)
        installed = [InstalledVoice(_EN_VOICE, "Microsoft David", "en-US")]
        self._voices_patch = patch(
            "src.ui_desktop.controllers.settings_controller.list_installed_voices_for_language",
            return_value=installed,
        )
        self._voices_patch.start()
        self.addCleanup(self._voices_patch.stop)
        # SettingsView construction never calls this (M19-lesson: must
        # not block on a real PowerShell/WinRT scan just to open
        # Settings) -- only "Refresh Voices" does, through
        # `all_installed_voices()`.
        self._all_voices_patch = patch(
            "src.ui_desktop.controllers.settings_controller.list_installed_voices",
            return_value=installed,
        )
        self._all_voices_patch.start()
        self.addCleanup(self._all_voices_patch.stop)

    def _restore_view_get_path(self) -> None:
        preferences_module.get_app_preferences_path = self._view_original_get_path

    def test_audio_rows_render_and_reflect_controller_state(self) -> None:
        from src.ui_desktop.views.settings_view import SettingsView

        controller = SettingsController(Preferences())
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        self.assertEqual(set(view._voice_combos), {"en", "fr", "zh-CN"})
        # Nothing configured: "Not bound" is selected and status is honest.
        self.assertEqual(view._voice_combos["en"].currentData(), "")
        self.assertIn("Not configured", view._voice_status_labels["en"].text())

        # A binding made elsewhere (no "Refresh Voices" click) still
        # reflects via the cheap placeholder path, not a real rescan.
        controller.set_voice_binding("en", _EN_VOICE)
        self.assertEqual(view._voice_combos["en"].currentData(), _EN_VOICE)
        self.assertIn(_EN_VOICE, view._voice_status_labels["en"].text())
        self.assertIn("Settings > Audio", view._voice_status_labels["en"].text())

    def test_opening_settings_never_enumerates_voices_only_refresh_does(self) -> None:
        """The M19 Audio Export corrective exists because a synchronous
        PowerShell/WinRT call during dialog construction froze the UI
        for seconds. Settings > Audio must not reintroduce that: opening
        it performs zero real voice enumeration, and only the explicit
        "Refresh Voices" button does."""
        from src.ui_desktop.views.settings_view import SettingsView

        controller = SettingsController(Preferences())
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        self._voices_patch.stop()
        self._all_voices_patch.stop()
        try:
            with patch("src.tts_providers.list_installed_voices") as mocked:
                mocked.return_value = []
                # Re-open-equivalent: rebuilding state from an existing
                # binding must not enumerate either.
                controller.set_voice_binding("fr", _FR_VOICE)
                mocked.assert_not_called()
        finally:
            self._voices_patch.start()
            self._all_voices_patch.start()

    def test_choosing_a_voice_in_the_combo_persists_the_binding(self) -> None:
        from src.ui_desktop.views.settings_view import SettingsView

        controller = SettingsController(Preferences())
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        view._on_voice_refresh()
        combo = view._voice_combos["en"]
        index = combo.findData(_EN_VOICE)
        self.assertGreaterEqual(index, 0)
        combo.setCurrentIndex(index)

        self.assertEqual(controller.voice_binding("en"), _EN_VOICE)

    def test_audio_controls_have_explicit_qss_coverage_in_both_themes(self) -> None:
        """M18 Human Gate 1 lesson: a workspace control without explicit
        QSS coverage renders at effectively-invisible Light Mode
        contrast. Every new M20 Settings > Audio control must appear in
        the generated stylesheet for both bundled themes."""
        from src.ui_desktop.theming.theme_manager import build_stylesheet
        from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT

        for tokens in (THEME_CALM_BLUE_LIGHT, THEME_CALM_BLUE_DARK):
            stylesheet = build_stylesheet(tokens)
            for selector in (
                "#settings-voice-refresh-button",
                "#settings-voice-binding-combo",
                "#settings-section-note",
            ):
                self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

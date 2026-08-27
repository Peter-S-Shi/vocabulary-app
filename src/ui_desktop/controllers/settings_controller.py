import copy
from PySide6.QtCore import QObject, Signal

from src.app_config import get_app_storage_summary
from src.tts_providers import InstalledVoice, list_installed_voices, list_installed_voices_for_language
from src.ui_desktop.state.preferences import Preferences, parse_quiz_presentation, save_preferences
from src.ui_desktop.state.tts_runtime import SOURCE_LABELS, resolve_voice_binding
from src.ui_desktop.theming.theme_manager import ThemeManager, parse_accent, parse_appearance, Appearance
from src.ui_desktop.theming.tokens import CustomThemeConfig, ModeCustomization, PRESET_CALM_BLUE, PRESET_NAMES

"""
SettingsController owns the durable, user-facing preferences Settings exposes:
- Appearance (System/Light/Dark)
- Theme Customization ([Light]/[Dark] per-mode presets, accent, background/surfaces, text)
- Quiz presentation (Immersive Focus, Flip Card + Filmstrip)
- Collections progress bars
- Local Windows Voice Bindings
- Read-only storage inspection

All theme staging, real-time live preview, cancel, apply, undo, and reset
are managed through this controller and live-applied via ThemeManager.
"""


class SettingsController(QObject):
    state_changed = Signal()
    collection_progress_bars_changed = Signal(bool)

    def __init__(self, preferences: Preferences | None = None, theme_manager: ThemeManager | None = None) -> None:
        super().__init__()
        self.preferences = preferences or Preferences()
        self._theme_manager = theme_manager
        self._staged_custom_theme: CustomThemeConfig = copy.deepcopy(self.preferences.custom_theme)
        self._undo_stack: list[CustomThemeConfig] = []

    def quiz_presentation(self) -> str:
        return self.preferences.quiz_presentation

    def set_quiz_presentation(self, value: str) -> None:
        normalized = parse_quiz_presentation(value)
        if normalized == self.preferences.quiz_presentation:
            return
        self.preferences.quiz_presentation = normalized
        save_preferences(self.preferences)
        self.state_changed.emit()

    def appearance(self) -> str:
        return self.preferences.appearance

    def set_appearance(self, value: str) -> None:
        normalized = parse_appearance(value)
        if normalized.value == self.preferences.appearance:
            return
        self.preferences.appearance = normalized.value
        save_preferences(self.preferences)
        self._apply_theme_to_manager()
        self.state_changed.emit()

    def _apply_theme_to_manager(self) -> None:
        if self._theme_manager is not None:
            if hasattr(self._theme_manager, "apply_preferences"):
                self._theme_manager.apply_preferences(self.preferences)
            elif hasattr(self._theme_manager, "apply"):
                self._theme_manager.apply(
                    parse_appearance(self.preferences.appearance),
                    parse_accent(self.preferences.accent),
                )

    # -- Theme Customization (Phase D) --------------------------------------

    def custom_theme(self) -> CustomThemeConfig:
        return self.preferences.custom_theme

    def staged_custom_theme(self) -> CustomThemeConfig:
        return self._staged_custom_theme

    def is_staged_dirty(self) -> bool:
        return self._staged_custom_theme != self.preferences.custom_theme

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def undo(self) -> None:
        if not self._undo_stack:
            return
        previous = self._undo_stack.pop()
        self.preferences.custom_theme = copy.deepcopy(previous)
        self._staged_custom_theme = copy.deepcopy(previous)
        save_preferences(self.preferences)
        self._apply_theme_to_manager()
        self.state_changed.emit()

    def stage_mode_customization(self, mode: str, customization: ModeCustomization) -> None:
        if mode.lower() == "dark":
            self._staged_custom_theme.dark = copy.deepcopy(customization)
        else:
            self._staged_custom_theme.light = copy.deepcopy(customization)

        if self._theme_manager is not None:
            eff = Appearance.DARK if mode.lower() == "dark" else Appearance.LIGHT
            if hasattr(self._theme_manager, "preview_customization"):
                self._theme_manager.preview_customization(eff, customization)
            elif hasattr(self._theme_manager, "apply"):
                self._theme_manager.apply(eff, parse_accent(customization.preset))
        self.state_changed.emit()

    def preview_tab_mode(self, mode: str) -> None:
        """Temporarily live-preview the specified tab's mode without modifying stored appearance."""
        if self._theme_manager is not None:
            eff = Appearance.DARK if mode.lower() == "dark" else Appearance.LIGHT
            custom = self._staged_custom_theme.dark if eff is Appearance.DARK else self._staged_custom_theme.light
            if hasattr(self._theme_manager, "preview_customization"):
                self._theme_manager.preview_customization(eff, custom)
            elif hasattr(self._theme_manager, "apply"):
                self._theme_manager.apply(eff, parse_accent(custom.preset))

    def apply_staged_custom_theme(self) -> None:
        self._undo_stack.append(copy.deepcopy(self.preferences.custom_theme))
        self.preferences.custom_theme = copy.deepcopy(self._staged_custom_theme)
        save_preferences(self.preferences)
        self._apply_theme_to_manager()
        self.state_changed.emit()

    def cancel_staged_custom_theme(self) -> None:
        self._staged_custom_theme = copy.deepcopy(self.preferences.custom_theme)
        self._apply_theme_to_manager()
        self.state_changed.emit()

    def reset_staged_mode_to_preset(self, mode: str, preset_name: str) -> None:
        clean = ModeCustomization(preset=preset_name)
        self.stage_mode_customization(mode, clean)

    def reset_staged_all_to_default(self, active_mode: str = "Light") -> None:
        self._staged_custom_theme = CustomThemeConfig()
        if self._theme_manager is not None:
            eff = Appearance.DARK if active_mode.lower() == "dark" else Appearance.LIGHT
            custom = self._staged_custom_theme.dark if eff is Appearance.DARK else self._staged_custom_theme.light
            self._theme_manager.preview_customization(eff, custom)
        self.state_changed.emit()

    def collection_progress_bars_visible(self) -> bool:
        return self.preferences.show_collection_progress_bars

    def set_collection_progress_bars_visible(self, visible: bool) -> None:
        normalized = bool(visible)
        if normalized == self.preferences.show_collection_progress_bars:
            return
        self.preferences.show_collection_progress_bars = normalized
        save_preferences(self.preferences)
        self.collection_progress_bars_changed.emit(normalized)
        self.state_changed.emit()

    # -- Local Windows Speech Provider / Installed Voice Binding (M20) ---

    def installed_voices(self, language: str) -> list[InstalledVoice]:
        """Windows-installed voices compatible with ``language``, for
        the Settings > Audio voice-selection control. Never bundles,
        downloads, or possesses the voice itself -- this only lists what
        the user's own Windows installation already has."""
        return list_installed_voices_for_language(language)

    def all_installed_voices(self) -> list[InstalledVoice]:
        """Every Windows-installed voice, across all languages, from one
        real enumeration call -- used by "Refresh Voices" so refreshing
        all language rows costs one PowerShell/WinRT scan, not one per
        language."""
        return list_installed_voices()

    def voice_binding(self, language: str) -> str:
        """The persisted app-setting value itself (may be empty), as
        distinct from the *effective* resolution below -- Settings edits
        this value; the environment variable is never written here."""
        return self.preferences.voice_bindings.get(language, "")

    def set_voice_binding(self, language: str, voice_id: str) -> None:
        normalized = (voice_id or "").strip()
        if normalized == self.preferences.voice_bindings.get(language, ""):
            return
        if normalized:
            self.preferences.voice_bindings[language] = normalized
        else:
            self.preferences.voice_bindings.pop(language, None)
        save_preferences(self.preferences)
        self.state_changed.emit()

    def clear_voice_binding(self, language: str) -> None:
        self.set_voice_binding(language, "")

    def voice_binding_status(self, language: str) -> dict:
        """Effective resolution for display: the voice ID actually in
        use for ``language`` (or None), which source supplied it, and a
        human-readable source label. Uses the live Preferences instance
        so an edit made one row above is reflected immediately."""
        resolved, source = resolve_voice_binding(language, self.preferences)
        return {
            "voice_id": resolved,
            "source": source,
            "source_label": SOURCE_LABELS.get(source, source),
        }

    def storage_summary(self) -> dict:
        """M18 Phase C2: read-only storage/data-location information
        (DESIGN.md § 7.3 "Storage / data-location information: B, P8").
        A thin passthrough to the existing ``src.app_config`` summary the
        Streamlit Settings/Data page already reads -- no second path-
        resolution implementation, no mutation."""
        return get_app_storage_summary()

from __future__ import annotations

import copy
from pathlib import Path
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices

from src.app_config import APP_VERSION, get_app_storage_summary
from src.tts_providers import InstalledVoice, list_installed_voices, list_installed_voices_for_language
from src.ui_desktop.state.preferences import Preferences, parse_quiz_presentation, save_preferences
from src.ui_desktop.state.tts_runtime import SOURCE_LABELS, resolve_voice_binding
from src.ui_desktop.theming.theme_manager import ThemeManager, parse_accent, parse_appearance, Appearance
from src.ui_desktop.theming.tokens import CustomThemeConfig, ModeCustomization, PRESET_CALM_BLUE, PRESET_NAMES
from src.update_checker import (
    PYSIDE6_AVAILABLE,
    UpdateAwarenessService,
    UpdateCheckResult,
    UpdateCheckState,
)

"""
SettingsController owns the durable, user-facing preferences Settings exposes:
- Appearance (System/Light/Dark)
- Theme Customization ([Light]/[Dark] per-mode presets, accent, background/surfaces, text)
- Quiz presentation (Immersive Focus, Flip Card + Filmstrip)
- Collections progress bars
- Local Windows Voice Bindings
- Software Update awareness (Level 1 GitHub Release check & view)
- Read-only storage inspection

All theme staging, real-time live preview, cancel, apply, undo, and reset
are managed through this controller and live-applied via ThemeManager.
"""


class SettingsController(QObject):
    state_changed = Signal()
    collection_progress_bars_changed = Signal(bool)
    include_proficient_in_study_changed = Signal(bool)
    update_status_changed = Signal(object)  # Emits UpdateCheckResult

    def __init__(
        self,
        preferences: Preferences | None = None,
        theme_manager: ThemeManager | None = None,
        preferences_path: Path | None = None,
        update_service: UpdateAwarenessService | None = None,
    ) -> None:
        super().__init__()
        self.preferences = preferences or Preferences()
        self._theme_manager = theme_manager
        self.preferences_path = preferences_path
        self._staged_custom_theme: CustomThemeConfig = copy.deepcopy(self.preferences.custom_theme)
        self._staged_undo_stack: list[tuple[CustomThemeConfig, str]] = []
        self._committed_undo_stack: list[CustomThemeConfig] = []

        if update_service is not None:
            self._update_service: UpdateAwarenessService | None = update_service
        elif PYSIDE6_AVAILABLE:
            self._update_service = UpdateAwarenessService(current_version=APP_VERSION)
        else:
            self._update_service = None

        if self._update_service is not None:
            self._update_service.state_changed.connect(self._on_update_service_state_changed)

    def quiz_presentation(self) -> str:
        return self.preferences.quiz_presentation

    def set_quiz_presentation(self, value: str) -> None:
        normalized = parse_quiz_presentation(value)
        if normalized == self.preferences.quiz_presentation:
            return
        self.preferences.quiz_presentation = normalized
        save_preferences(self.preferences, self.preferences_path)
        self.state_changed.emit()

    def appearance(self) -> str:
        return self.preferences.appearance

    def set_appearance(self, value: str) -> None:
        normalized = parse_appearance(value)
        if normalized.value == self.preferences.appearance:
            return
        self.preferences.appearance = normalized.value
        save_preferences(self.preferences, self.preferences_path)
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
        return len(self._staged_undo_stack) > 0 or len(self._committed_undo_stack) > 0

    def undo(self, active_mode: str | None = None) -> None:
        # Case A: There are uncommitted staged undo actions (e.g. undoing a staged Reset)
        if self._staged_undo_stack:
            previous_staged, recorded_mode = self._staged_undo_stack.pop()
            self._staged_custom_theme = copy.deepcopy(previous_staged)
            # Live-preview the restored staged theme in the target tab mode without writing to disk
            target_mode = active_mode or recorded_mode
            self.preview_tab_mode(target_mode)
            self.state_changed.emit()
            return

        # Case B: Undoing a committed Apply
        if self._committed_undo_stack:
            previous_committed = self._committed_undo_stack.pop()
            self.preferences.custom_theme = copy.deepcopy(previous_committed)
            self._staged_custom_theme = copy.deepcopy(previous_committed)
            save_preferences(self.preferences, self.preferences_path)
            self._apply_theme_to_manager()
            self.state_changed.emit()
            return

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
        self._committed_undo_stack.append(copy.deepcopy(self.preferences.custom_theme))
        self._staged_undo_stack.clear()
        self.preferences.custom_theme = copy.deepcopy(self._staged_custom_theme)
        save_preferences(self.preferences, self.preferences_path)
        self._apply_theme_to_manager()
        self.state_changed.emit()

    def cancel_staged_custom_theme(self) -> None:
        self._staged_custom_theme = copy.deepcopy(self.preferences.custom_theme)
        self._staged_undo_stack.clear()
        self._apply_theme_to_manager()
        self.state_changed.emit()

    def reset_staged_mode_to_preset(self, mode: str, preset_name: str) -> None:
        self._staged_undo_stack.append((copy.deepcopy(self._staged_custom_theme), mode))
        clean = ModeCustomization(preset=preset_name)
        self.stage_mode_customization(mode, clean)

    def reset_staged_all_to_default(self, active_mode: str = "Light") -> None:
        self._staged_undo_stack.append((copy.deepcopy(self._staged_custom_theme), active_mode))
        self._staged_custom_theme = CustomThemeConfig()
        self.preview_tab_mode(active_mode)
        self.state_changed.emit()

    def collection_progress_bars_visible(self) -> bool:
        return self.preferences.show_collection_progress_bars

    def set_collection_progress_bars_visible(self, visible: bool) -> None:
        normalized = bool(visible)
        if normalized == self.preferences.show_collection_progress_bars:
            return
        self.preferences.show_collection_progress_bars = normalized
        save_preferences(self.preferences, self.preferences_path)
        self.collection_progress_bars_changed.emit(normalized)
        self.state_changed.emit()

    def include_proficient_in_study(self) -> bool:
        return self.preferences.include_proficient_in_study

    def set_include_proficient_in_study(self, include: bool) -> None:
        normalized = bool(include)
        if normalized == self.preferences.include_proficient_in_study:
            return
        self.preferences.include_proficient_in_study = normalized
        save_preferences(self.preferences, self.preferences_path)
        self.include_proficient_in_study_changed.emit(normalized)
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
        save_preferences(self.preferences, self.preferences_path)
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

    # -- Software Update (Phase E Level 1 Update Awareness) ------------------

    def update_result(self) -> UpdateCheckResult:
        if self._update_service is not None:
            return self._update_service.current_result()
        return UpdateCheckResult(
            state=UpdateCheckState.NOT_CHECKED,
            current_version=APP_VERSION,
        )

    def is_checking_updates(self) -> bool:
        if self._update_service is not None:
            return self._update_service.is_checking()
        return False

    def check_for_updates(self) -> None:
        """Triggers an asynchronous background check for updates."""
        if self._update_service is not None:
            self._update_service.check_for_updates()

    def open_latest_release_page(self) -> bool:
        """Opens the official GitHub release page in the user's default system browser.

        Strictly opens the URL without downloading or executing binaries.
        """
        result = self.update_result()
        if not result.release_url:
            return False
        return QDesktopServices.openUrl(QUrl(result.release_url))

    def _on_update_service_state_changed(self, result: UpdateCheckResult) -> None:
        self.update_status_changed.emit(result)
        self.state_changed.emit()

    def shutdown(self, wait_ms: int = 2000) -> bool:
        """Gracefully waits for background worker threads during application teardown."""
        if self._update_service is not None:
            return self._update_service.shutdown(wait_ms)
        return True

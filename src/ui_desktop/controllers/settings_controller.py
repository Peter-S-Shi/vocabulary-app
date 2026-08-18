from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.app_config import get_app_storage_summary
from src.ui_desktop.state.preferences import Preferences, parse_quiz_presentation, save_preferences
from src.ui_desktop.state.tts_runtime import SOURCE_LABELS, resolve_shared_tts_dir
from src.ui_desktop.theming.theme_manager import ThemeManager, parse_accent, parse_appearance

"""
SettingsController owns the durable, user-facing preferences Settings
exposes: `quiz_presentation` (M17 Feature 3B, `VR-STUDY-002` DESIGN.md
§ 6.4) and, since M17 Theme Completion, `appearance` (DESIGN.md § 13.1/
§ 14 "Settings -> Appearance -- full authoritative configuration
surface"). Both wrap the existing `state/preferences.py`
Appearance/Accent/Motion persistence mechanism rather than inventing a
second settings file or a vocab.db table (M17 Feature 3B prompt § 5; M17
Theme Completion prompt § 5).

`MainWindow` constructs this once from whatever `Preferences` `app.py`
already loaded at bootstrap, plus the one production `ThemeManager`
(M17 Theme Completion prompt § 5: "the active application must update
immediately; no restart required"). `set_appearance()` persists first,
then re-runs the existing single `ThemeManager.apply()` call site --
never a second theme-switch mechanism -- so the running application
re-themes itself synchronously, the same call frame as the Settings
change. `theme_manager` is optional (`None` in most existing tests that
construct this controller directly): a missing manager still persists
the preference, it just cannot live-apply it in that context.
"""


class SettingsController(QObject):
    state_changed = Signal()

    def __init__(self, preferences: Preferences | None = None, theme_manager: ThemeManager | None = None) -> None:
        super().__init__()
        self.preferences = preferences or Preferences()
        self._theme_manager = theme_manager

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
        if self._theme_manager is not None:
            self._theme_manager.apply(normalized, parse_accent(self.preferences.accent))
        self.state_changed.emit()

    # -- Shared TTS runtime (M19 hardening; state/tts_runtime.py) --------

    def shared_tts_dir_setting(self) -> str:
        """The persisted app-setting value itself (may be empty), as
        distinct from the *effective* resolution below -- Settings edits
        this value; the environment variable is never written here."""
        return self.preferences.shared_tts_dir

    def set_shared_tts_dir(self, path: str) -> None:
        normalized = (path or "").strip()
        if normalized == self.preferences.shared_tts_dir:
            return
        self.preferences.shared_tts_dir = normalized
        save_preferences(self.preferences)
        self.state_changed.emit()

    def clear_shared_tts_dir(self) -> None:
        self.set_shared_tts_dir("")

    def shared_tts_status(self) -> dict:
        """Effective resolution for display: the directory actually in
        use (or None), which source supplied it, and a human-readable
        source label. Uses the live Preferences instance so an edit made
        one row above is reflected immediately."""
        resolved, source = resolve_shared_tts_dir(self.preferences)
        return {
            "directory": resolved,
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

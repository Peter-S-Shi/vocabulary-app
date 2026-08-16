from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.ui_desktop.state.preferences import Preferences, parse_quiz_presentation, save_preferences

"""
SettingsController owns the one durable, user-facing preference this M17
Feature 3B vertical slice introduces (`quiz_presentation`, `VR-STUDY-002`
DESIGN.md § 6.4). It wraps the existing `state/preferences.py`
Appearance/Accent/Motion persistence mechanism rather than inventing a
second settings file or a vocab.db table (M17 Feature 3B prompt § 5).

`MainWindow` constructs this once from whatever `Preferences` `app.py`
already loaded at bootstrap, and reads `quiz_presentation` from it at Quiz
launch time (M17 Feature 3B prompt § 7: the preference is applied "when
the Quiz presentation is created", not through a second in-session
switcher). Changing the preference here immediately persists to disk and
is reflected in the very next Quiz launch within the same running session
-- no restart required -- while still surviving a real restart because it
round-trips through the same `preferences.json` file `app.py` loads from.
"""


class SettingsController(QObject):
    state_changed = Signal()

    def __init__(self, preferences: Preferences | None = None) -> None:
        super().__init__()
        self.preferences = preferences or Preferences()

    def quiz_presentation(self) -> str:
        return self.preferences.quiz_presentation

    def set_quiz_presentation(self, value: str) -> None:
        normalized = parse_quiz_presentation(value)
        if normalized == self.preferences.quiz_presentation:
            return
        self.preferences.quiz_presentation = normalized
        save_preferences(self.preferences)
        self.state_changed.emit()

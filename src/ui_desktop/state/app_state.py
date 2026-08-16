from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, Signal

"""
AppState owns cross-screen transient desktop state: the active workspace,
the Management/Study chrome mode, and navigation/focus handoff between
workspaces. It is the typed replacement for the flat Streamlit
``st.session_state`` "focus" pattern (``set_page_focus`` /
``today_focus_*`` / ``quiz_focus_*`` keys in
``src/ui_streamlit/common.py`` and ``today_page.py``), per the M16.1
contract § 11.C.

Durable domain state stays in SQLite/core; durable presentation
preferences persist through ``state/preferences.py``. Neither lives here.
"""


class Workspace(str, Enum):
    TODAY = "today"
    ENTRIES = "entries"
    REVIEW = "review"


class ShellMode(str, Enum):
    MANAGEMENT = "management"
    STUDY = "study"


class AppState(QObject):
    navigation_requested = Signal(str, object)
    mode_changed = Signal(str)

    def __init__(
        self,
        *,
        workspace: Workspace = Workspace.TODAY,
        mode: ShellMode = ShellMode.MANAGEMENT,
    ) -> None:
        super().__init__()
        self.workspace = workspace
        self.mode = mode

    def request_navigation(self, workspace: Workspace, payload: object = None) -> None:
        self.workspace = workspace
        self.navigation_requested.emit(workspace.value, payload)

    def enter_study_mode(self) -> None:
        if self.mode is ShellMode.STUDY:
            return
        self.mode = ShellMode.STUDY
        self.mode_changed.emit(self.mode.value)

    def enter_management_mode(self) -> None:
        if self.mode is ShellMode.MANAGEMENT:
            return
        self.mode = ShellMode.MANAGEMENT
        self.mode_changed.emit(self.mode.value)

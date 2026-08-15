from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QToolBar

from src.ui_desktop.controllers.entries_controller import EntriesController
from src.ui_desktop.controllers.today_controller import TodayController
from src.ui_desktop.state.app_state import AppState, ShellMode, Workspace
from src.ui_desktop.views.entries_view import EntriesView
from src.ui_desktop.views.today_view import TodayView

"""
QMainWindow shell proving native navigation and the Management Mode <->
Study Mode chrome swap structurally (DESIGN.md § 3, M16.1 contract § 8).
Full Study Mode (Review/Quiz) content is M17 work; only the chrome-swap
mechanism is proven here via AppState.enter_study_mode()/
enter_management_mode(), exercised through controller/shell APIs and
tests rather than a fake production Study workflow.
"""


class MainWindow(QMainWindow):
    def __init__(self, app_state: AppState | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Vocabulary App (Desktop Preview)")
        self.resize(1024, 720)

        self.app_state = app_state or AppState()

        self.today_controller = TodayController()
        self.entries_controller = EntriesController()

        self.today_view = TodayView(self.today_controller)
        self.entries_view = EntriesView(self.entries_controller)

        self._workspace_stack = QStackedWidget(self)
        self._workspace_stack.addWidget(self.today_view)
        self._workspace_stack.addWidget(self.entries_view)
        self.setCentralWidget(self._workspace_stack)

        self._management_toolbar = self._build_management_toolbar()
        self.addToolBar(self._management_toolbar)

        self._study_toolbar = self._build_study_toolbar()
        self._study_toolbar.setVisible(False)
        self.addToolBar(self._study_toolbar)

        self.app_state.navigation_requested.connect(self._on_navigation_requested)
        self.app_state.mode_changed.connect(self._on_mode_changed)

        self.show_workspace(Workspace.TODAY)

    def _build_management_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Navigation", self)
        toolbar.setObjectName("management-toolbar")

        today_action = toolbar.addAction("Today")
        today_action.triggered.connect(lambda: self.app_state.request_navigation(Workspace.TODAY))

        entries_action = toolbar.addAction("Entries")
        entries_action.triggered.connect(lambda: self.app_state.request_navigation(Workspace.ENTRIES))

        return toolbar

    def _build_study_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Study Session", self)
        toolbar.setObjectName("study-toolbar")

        exit_action = toolbar.addAction("Exit Study Mode")
        exit_action.triggered.connect(self.app_state.enter_management_mode)

        return toolbar

    def show_workspace(self, workspace: Workspace) -> None:
        if workspace is Workspace.TODAY:
            self._workspace_stack.setCurrentWidget(self.today_view)
            self.today_controller.refresh()
        elif workspace is Workspace.ENTRIES:
            self._workspace_stack.setCurrentWidget(self.entries_view)
            self.entries_controller.refresh()

    def current_workspace(self) -> Workspace:
        current = self._workspace_stack.currentWidget()
        if current is self.entries_view:
            return Workspace.ENTRIES
        return Workspace.TODAY

    def _on_navigation_requested(self, workspace_value: str, _payload: object) -> None:
        self.show_workspace(Workspace(workspace_value))

    def _on_mode_changed(self, mode_value: str) -> None:
        is_study = mode_value == ShellMode.STUDY.value
        self._management_toolbar.setVisible(not is_study)
        self._study_toolbar.setVisible(is_study)

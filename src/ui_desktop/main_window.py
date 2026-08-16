from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QToolBar

from src.ui_desktop.controllers.entries_controller import EntriesController
from src.ui_desktop.controllers.today_controller import TodayController
from src.ui_desktop.motion.transitions import TransitionManager
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

`AppState` is the single source of truth for the active workspace and
shell mode (M16.1 contract § 11.C). `MainWindow` never keeps an
independent notion of "current workspace" or "current mode" -- it only
renders whatever `AppState` currently holds, and reacts to `AppState`'s
signals. This holds for construction too: an `AppState` injected with a
non-default `workspace`/`mode` (e.g. for tests or a future session-restore
feature) is rendered as-is, rather than the shell silently resetting to
Today/Management on startup.

``TransitionManager`` (motion/transitions.py) is shared desktop-shell
infrastructure, not Today-owned: it decorates workspace switches and the
Management/Study chrome swap with the same centralized fade, per the M17
Feature 1 Motion / Transition Foundation (DESIGN.md § 23). It is never
consulted for correctness -- every render below performs the actual state
change synchronously first, then optionally fades the result in.
"""


class MainWindow(QMainWindow):
    def __init__(
        self,
        app_state: AppState | None = None,
        motion: TransitionManager | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Vocabulary App (Desktop Preview)")
        self.resize(1024, 720)

        self.app_state = app_state or AppState()
        self._motion = motion or TransitionManager()

        self.today_controller = TodayController()
        self.entries_controller = EntriesController()

        self.today_view = TodayView(self.today_controller)
        self.entries_view = EntriesView(self.entries_controller)
        self.today_view.entries_requested.connect(
            lambda: self.app_state.request_navigation(Workspace.ENTRIES)
        )

        self._workspace_stack = QStackedWidget(self)
        self._workspace_stack.addWidget(self.today_view)
        self._workspace_stack.addWidget(self.entries_view)
        self.setCentralWidget(self._workspace_stack)

        self._management_toolbar = self._build_management_toolbar()
        self.addToolBar(self._management_toolbar)

        self._study_toolbar = self._build_study_toolbar()
        self.addToolBar(self._study_toolbar)

        self.app_state.navigation_requested.connect(self._on_navigation_requested)
        self.app_state.mode_changed.connect(self._on_mode_changed)

        # Render whatever AppState already holds -- including an injected
        # non-default workspace/mode -- rather than hardcoding Today/
        # Management. This must call the render helpers directly, not
        # AppState.request_navigation()/enter_study_mode(): those mutator
        # methods are no-ops when the target state already matches (by
        # design, to avoid redundant signal emission on repeat calls), so
        # routing initialization through them would silently fail to render
        # an injected non-default starting state. The initial render never
        # animates -- motion decorates a *transition*, not first paint.
        self._render_workspace(self.app_state.workspace, animate=False)
        self._render_mode(self.app_state.mode, animate=False)

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
        """Request a workspace change.

        This only ever delegates to ``AppState.request_navigation()`` --
        the single source of truth for shell state -- so the visible UI
        can never diverge from ``AppState``. It never touches
        ``_workspace_stack`` directly.
        """
        self.app_state.request_navigation(workspace)

    def current_workspace(self) -> Workspace:
        """The active workspace, read directly from AppState (not from
        widget/stack inspection), so this can never disagree with it."""
        return self.app_state.workspace

    def _render_workspace(self, workspace: Workspace, *, animate: bool = True) -> None:
        widget = None
        if workspace is Workspace.TODAY:
            widget = self.today_view
            self._workspace_stack.setCurrentWidget(widget)
            self.today_controller.refresh()
        elif workspace is Workspace.ENTRIES:
            widget = self.entries_view
            self._workspace_stack.setCurrentWidget(widget)
            self.entries_controller.refresh()

        # The workspace switch above is already complete and correct by
        # this point; the fade below is a purely decorative reveal of that
        # already-correct state, never a precondition for it.
        if animate and widget is not None:
            self._motion.fade_in(widget)

    def _render_mode(self, mode: ShellMode, *, animate: bool = True) -> None:
        is_study = mode is ShellMode.STUDY
        self._management_toolbar.setVisible(not is_study)
        self._study_toolbar.setVisible(is_study)

        if animate:
            visible_toolbar = self._study_toolbar if is_study else self._management_toolbar
            self._motion.fade_in(visible_toolbar)

    def _on_navigation_requested(self, workspace_value: str, _payload: object) -> None:
        self._render_workspace(Workspace(workspace_value))

    def _on_mode_changed(self, mode_value: str) -> None:
        self._render_mode(ShellMode(mode_value))

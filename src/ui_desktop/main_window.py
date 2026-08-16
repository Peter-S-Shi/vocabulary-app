from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QToolBar, QWidget

from src.ui_desktop.controllers.entries_controller import EntriesController
from src.ui_desktop.controllers.review_controller import ReviewController
from src.ui_desktop.controllers.today_controller import TodayController
from src.ui_desktop.motion.transitions import TransitionManager
from src.ui_desktop.state.app_state import AppState, ShellMode, Workspace
from src.ui_desktop.views.entries_view import EntriesView
from src.ui_desktop.views.review_view import ReviewView
from src.ui_desktop.views.today_view import TodayView
from src.ui_desktop.widgets.navigation_rail import NavigationRail

"""
QMainWindow shell: the shared vertical left Management Navigation Rail
(DESIGN.md § 5, `VR-SHELL-001`) plus the Management Mode <-> Study Mode
chrome swap (M16.1 contract § 8). M17 Feature 2 (Review) is the first real
Study Mode content; Quiz remains out of scope for this checkpoint.

Review supplies its own complete session bar (DESIGN.md § 6.3's "a
minimal session bar remains" -- singular), so the generic `_study_toolbar`
built for the M16.2/M17-Feature-1 chrome-swap proof is suppressed
specifically while the Review workspace is active, rather than stacking a
second bar above Review's own. It remains available for `mode=STUDY`
combined with any other workspace (still exercised by
`tests/test_m16_2_desktop_vertical_slice.py`'s structural chrome-swap
tests, which use the synthetic `workspace=TODAY, mode=STUDY` combination
that predates any real Study content).

`AppState` is the single source of truth for the active workspace and
shell mode (M16.1 contract § 11.C). `MainWindow` never keeps an
independent notion of "current workspace" or "current mode" -- it only
renders whatever `AppState` currently holds, and reacts to `AppState`'s
signals. This holds for construction too: an `AppState` injected with a
non-default `workspace`/`mode` (e.g. for tests or a future session-restore
feature) is rendered as-is, rather than the shell silently resetting to
Today/Management on startup.

``TransitionManager`` (motion/transitions.py) is shared desktop-shell
infrastructure and is design-neutral: it decorates workspace switches and
the Management/Study chrome swap with the centrally-configured transition,
whatever shell composition the design specifies. It is never consulted
for correctness -- every render below performs the actual state change
synchronously first, then optionally animates the result.

The Management-mode shell composition (this checkpoint's fresh
implementation) is now frozen at product level by the replacement
DESIGN.md's Global Management Shell Contract (§ 5) and Today Command
Center contract (§ 6.1) -- not agent-derived. The rail is shared shell
infrastructure: any future Management Mode screen reuses the same
``NavigationRail`` instance/class rather than inventing its own
first-level navigation.
"""


class MainWindow(QMainWindow):
    def __init__(
        self,
        app_state: AppState | None = None,
        motion: TransitionManager | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Vocabulary App (Desktop Preview)")
        self.resize(1280, 800)

        self.app_state = app_state or AppState()
        self._motion = motion or TransitionManager()

        self.today_controller = TodayController()
        self.entries_controller = EntriesController()
        self.review_controller = ReviewController()

        self.today_view = TodayView(self.today_controller)
        self.today_view.navigate_to_entries_requested.connect(
            lambda: self.app_state.request_navigation(Workspace.ENTRIES)
        )
        self.entries_view = EntriesView(self.entries_controller)
        self.review_view = ReviewView(self.review_controller)
        self.review_view.set_motion(self._motion)
        self.review_view.exit_requested.connect(self._exit_study_mode)
        self.review_view.navigate_to_entries_requested.connect(self._exit_study_mode_to_entries)

        self._workspace_stack = QStackedWidget(self)
        self._workspace_stack.addWidget(self.today_view)
        self._workspace_stack.addWidget(self.entries_view)
        self._workspace_stack.addWidget(self.review_view)

        self._last_management_workspace = Workspace.TODAY

        self._navigation_rail = NavigationRail(self)
        self._navigation_rail.destination_activated.connect(self._on_rail_destination_activated)
        self._navigation_rail.set_active(self._rail_key_for_workspace(self.app_state.workspace))

        shell_root = QWidget(self)
        shell_layout = QHBoxLayout(shell_root)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._navigation_rail, 0)
        shell_layout.addWidget(self._workspace_stack, 1)
        self.setCentralWidget(shell_root)

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

    def _on_rail_destination_activated(self, destination_key: str) -> None:
        if destination_key == "today":
            self.app_state.request_navigation(Workspace.TODAY)
        elif destination_key == "entries":
            self.app_state.request_navigation(Workspace.ENTRIES)
        elif destination_key == "study":
            self.app_state.request_navigation(Workspace.REVIEW)
            self.app_state.enter_study_mode()

    def _build_study_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Study Session", self)
        toolbar.setObjectName("study-toolbar")

        exit_action = toolbar.addAction("Exit Study Mode")
        exit_action.triggered.connect(self._exit_study_mode)

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

    @staticmethod
    def _rail_key_for_workspace(workspace: Workspace) -> str:
        """Review has no dedicated rail button -- entering it is reached
        through the shared "study" destination (NavigationRail's existing
        placeholder key), the same way DESIGN.md's frozen IA already names
        that slot."""
        return "study" if workspace is Workspace.REVIEW else workspace.value

    def _render_workspace(self, workspace: Workspace, *, animate: bool = True) -> None:
        widget = None
        if workspace is Workspace.TODAY:
            widget = self.today_view
            self._workspace_stack.setCurrentWidget(widget)
            self.today_controller.refresh()
            self._last_management_workspace = workspace
        elif workspace is Workspace.ENTRIES:
            widget = self.entries_view
            self._workspace_stack.setCurrentWidget(widget)
            self.entries_controller.refresh()
            self._last_management_workspace = workspace
        elif workspace is Workspace.REVIEW:
            widget = self.review_view
            self._workspace_stack.setCurrentWidget(widget)
            self.review_controller.open_default()

        self._navigation_rail.set_active(self._rail_key_for_workspace(workspace))

        # The workspace switch above is already complete and correct by
        # this point; the transition below is a purely decorative reveal of
        # that already-correct state, never a precondition for it.
        if animate and widget is not None:
            self._motion.fade_in(widget)

    def _render_mode(self, mode: ShellMode, *, animate: bool = True) -> None:
        is_study = mode is ShellMode.STUDY
        # Review supplies its own complete session bar (module docstring);
        # the generic toolbar only covers a hypothetical bare Study mode
        # with no dedicated content, which no real workspace exercises today.
        show_generic_toolbar = is_study and self.app_state.workspace is not Workspace.REVIEW
        self._navigation_rail.setVisible(not is_study)
        self._study_toolbar.setVisible(show_generic_toolbar)

        if animate:
            visible_widget = self._study_toolbar if show_generic_toolbar else self._navigation_rail
            self._motion.fade_in(visible_widget)

    def _exit_study_mode(self) -> None:
        """Restore the correct Management shell through AppState, without
        parallel UI state or shell divergence (DESIGN.md § 6.3 "Exit /
        return")."""
        self.app_state.request_navigation(self._last_management_workspace)
        self.app_state.enter_management_mode()

    def _exit_study_mode_to_entries(self) -> None:
        """Review's empty-state "Open Entries" action: leaves Study mode
        the same way any other exit does, just landing on Entries instead
        of the last Management workspace."""
        self.app_state.request_navigation(Workspace.ENTRIES)
        self.app_state.enter_management_mode()

    def _on_navigation_requested(self, workspace_value: str, _payload: object) -> None:
        self._render_workspace(Workspace(workspace_value))

    def _on_mode_changed(self, mode_value: str) -> None:
        self._render_mode(ShellMode(mode_value))

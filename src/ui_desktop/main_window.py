from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QToolBar, QWidget

from src.update_checker import UpdateCheckResult, UpdateCheckState
from src.ui_desktop.controllers.collections_controller import CollectionsController
from src.ui_desktop.controllers.entries_controller import EntriesController
from src.ui_desktop.controllers.quiz_controller import QuizController
from src.ui_desktop.controllers.review_controller import ReviewController
from src.ui_desktop.controllers.analytics_controller import AnalyticsController
from src.ui_desktop.controllers.data_tools_controller import DataToolsController
from src.ui_desktop.controllers.review_calendar_controller import ReviewCalendarController
from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.controllers.templates_controller import TemplatesController
from src.ui_desktop.controllers.today_controller import TodayController
from src.ui_desktop.motion.transitions import TransitionManager
from src.ui_desktop.state.app_state import AppState, ShellMode, Workspace
from src.ui_desktop.state.preferences import Preferences
from src.ui_desktop.theming.theme_manager import ThemeManager
from src.ui_desktop.views.collections_view import CollectionsView
from src.ui_desktop.views.entries_view import EntriesView
from src.ui_desktop.views.analytics_view import AnalyticsView
from src.ui_desktop.views.data_tools_view import DataToolsView
from src.ui_desktop.views.quiz_view import QuizView
from src.ui_desktop.views.review_calendar_view import ReviewCalendarView
from src.ui_desktop.views.review_view import ReviewView
from src.ui_desktop.views.settings_view import SettingsView
from src.ui_desktop.views.templates_view import TemplatesView
from src.ui_desktop.views.today_view import TodayView
from src.ui_desktop.widgets.navigation_rail import NavigationRail

"""
QMainWindow shell: the shared vertical left Management Navigation Rail
(DESIGN.md § 5, `VR-SHELL-001`) plus the Management Mode <-> Study Mode
chrome swap (M16.1 contract § 8). Review and, since M17 Feature 3, Quiz
are both real Study Mode content sharing the same chrome-swap mechanism.

Review and Quiz each supply their own complete session bar (DESIGN.md
§ 6.3's "a minimal session bar remains" -- singular), so the generic
`_study_toolbar` built for the M16.2/M17-Feature-1 chrome-swap proof is
suppressed specifically while either workspace is active, rather than
stacking a second bar above their own. It remains available for
`mode=STUDY` combined with any other workspace (still exercised by
`tests/test_m16_2_desktop_vertical_slice.py`'s structural chrome-swap
tests, which use the synthetic `workspace=TODAY, mode=STUDY` combination
that predates any real Study content).

Quiz has no rail entry point of its own -- it is only ever reached through
a real launch request (Review's Quick Quiz / Choose Quiz Type, or a Today
Learning Queue item), each producing a `QuizLaunchIntent`
(`state/handoff.py`) that `_start_quiz()` hands to the one shared
`QuizController`. Review and Today never talk to `src.quiz`/
`src.template_quiz` directly, and neither invents its own session
machinery (M17 Feature 3 prompt § 11).

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
        preferences: Preferences | None = None,
        theme_manager: ThemeManager | None = None,
    ) -> None:
        super().__init__()
        # M19 product truthfulness: the desktop application has been the
        # accepted primary product surface since M17/M18 -- it is no
        # longer a "(Desktop Preview)" of anything.
        self.setWindowTitle("Vocabulary App")
        self.resize(1280, 800)

        self.app_state = app_state or AppState()
        self._motion = motion or TransitionManager()
        self.theme_manager = theme_manager

        self.today_controller = TodayController()
        self.entries_controller = EntriesController()
        self.collections_controller = CollectionsController()
        self.settings_controller = SettingsController(preferences, self.theme_manager)
        self.review_controller = ReviewController(self.settings_controller.preferences)
        self.quiz_controller = QuizController(preferences=self.settings_controller.preferences)
        self.templates_controller = TemplatesController()
        self.review_calendar_controller = ReviewCalendarController()
        self.data_tools_controller = DataToolsController()
        self.analytics_controller = AnalyticsController()

        self.settings_controller.include_proficient_in_study_changed.connect(
            lambda _: self.review_controller.reload_current_card()
        )

        self.today_view = TodayView(self.today_controller)
        self.today_view.navigate_to_entries_requested.connect(
            lambda: self.app_state.request_navigation(Workspace.ENTRIES)
        )
        self.today_view.navigate_to_entries_scope_requested.connect(self._open_entries_with_scope)
        self.today_view.navigate_to_review_requested.connect(self._enter_review)
        self.today_view.quiz_launch_requested.connect(self._start_quiz)
        self.entries_view = EntriesView(self.entries_controller)
        self.collections_view = CollectionsView(self.collections_controller)
        self.collections_view.set_learning_progress_bars_visible(
            self.settings_controller.collection_progress_bars_visible()
        )
        self.settings_controller.collection_progress_bars_changed.connect(
            self.collections_view.set_learning_progress_bars_visible
        )
        self.collections_view.open_entries_requested.connect(self._open_entries_with_scope)
        self.collections_view.open_in_study_requested.connect(self._open_review_at_card)
        self.collections_view.quiz_launch_requested.connect(self._start_quiz)
        self.review_view = ReviewView(self.review_controller)
        self.review_view.set_motion(self._motion)
        self.review_view.exit_requested.connect(self._exit_study_mode)
        self.review_view.navigate_to_entries_requested.connect(self._exit_study_mode_to_entries)
        self.review_view.quiz_launch_requested.connect(self._start_quiz)
        self.quiz_view = QuizView(self.quiz_controller)
        self.quiz_view.exit_requested.connect(self._exit_study_mode)
        self.quiz_view.return_to_today_requested.connect(self._on_quiz_return_to_today)
        self.quiz_view.next_card_requested.connect(self._on_quiz_next_card)
        self.settings_view = SettingsView(self.settings_controller)
        self.templates_view = TemplatesView(self.templates_controller)
        self.review_calendar_view = ReviewCalendarView(self.review_calendar_controller)
        self.data_tools_view = DataToolsView(self.data_tools_controller)
        self.analytics_view = AnalyticsView(self.analytics_controller)

        self._workspace_stack = QStackedWidget(self)
        self._workspace_stack.addWidget(self.today_view)
        self._workspace_stack.addWidget(self.entries_view)
        self._workspace_stack.addWidget(self.collections_view)
        self._workspace_stack.addWidget(self.templates_view)
        self._workspace_stack.addWidget(self.review_calendar_view)
        self._workspace_stack.addWidget(self.data_tools_view)
        self._workspace_stack.addWidget(self.analytics_view)
        self._workspace_stack.addWidget(self.review_view)
        self._workspace_stack.addWidget(self.quiz_view)
        self._workspace_stack.addWidget(self.settings_view)

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

        # M17 Theme Completion: everything QSS/QPalette-driven re-themes
        # itself automatically the instant ThemeManager.apply() re-runs
        # (ThemeManager docstring) -- only the Star column's custom
        # QAbstractItemModel-painted Star color needs an explicit push, both now
        # (using whatever ThemeManager already applied at bootstrap) and
        # on every future live theme change.
        if self.theme_manager is not None:
            self.theme_manager.theme_applied.connect(self._on_theme_applied)
            if self.theme_manager.current_tokens is not None:
                self._on_theme_applied(self.theme_manager.current_tokens)

        # Level 1 Update Awareness (Phase E): non-blocking background check
        # Never blocks startup or modalizes UI; updates the navigation rail indicator on detection.
        self.settings_controller.update_status_changed.connect(self._on_update_status_changed)
        QTimer.singleShot(200, self.settings_controller.check_for_updates)

    def _on_update_status_changed(self, result: UpdateCheckResult) -> None:
        """Updates shell chrome with a restrained, non-modal update indicator when an update is available."""
        self._navigation_rail.set_update_available(result.state == UpdateCheckState.UPDATE_AVAILABLE)

    def _on_theme_applied(self, tokens) -> None:
        """The live-theme seam MainWindow brokers (module docstring's
        ``ThemeManager`` note): every QSS/QPalette-styled widget
        re-themes itself for free, so this only forwards to the views
        that paint a color QSS cannot express -- Entries' Star column
        (a model data role) and Data Tools' Audio Export progress ring
        (a painted arc)."""
        self.entries_view.apply_theme_tokens(tokens)
        self.data_tools_view.apply_theme_tokens(tokens)

    def _on_rail_destination_activated(self, destination_key: str) -> None:
        if destination_key == "today":
            self.app_state.request_navigation(Workspace.TODAY)
        elif destination_key == "entries":
            self.app_state.request_navigation(Workspace.ENTRIES)
        elif destination_key == "collections":
            self.app_state.request_navigation(Workspace.COLLECTIONS)
        elif destination_key == "templates":
            self.app_state.request_navigation(Workspace.TEMPLATES)
        elif destination_key == "review_calendar":
            self.app_state.request_navigation(Workspace.REVIEW_CALENDAR)
        elif destination_key == "data_tools":
            self.app_state.request_navigation(Workspace.DATA_TOOLS)
        elif destination_key == "analytics":
            self.app_state.request_navigation(Workspace.ANALYTICS)
        elif destination_key == "study":
            self._enter_review()
        elif destination_key == "settings":
            self.app_state.request_navigation(Workspace.SETTINGS)

    def _enter_review(self) -> None:
        """Generic Review entry point (rail "study" destination, Today's
        Review-targeted suggestion): opens the default Card. A specific
        Collection/Card handoff (``_open_review_at_card``) prepares its
        own exact target instead and must never be overridden by this
        default (M17 Minimum Collection Integration prompt § 9) -- so
        ``open_default()`` is called here explicitly, not inside
        ``_render_workspace``, which only ever renders whatever state the
        caller already prepared."""
        self.review_controller.open_default()
        self.app_state.request_navigation(Workspace.REVIEW)
        self.app_state.enter_study_mode()

    def _open_entries_with_scope(self, intent) -> None:
        """The one consumer of ``EntriesScopeIntent`` (state/handoff.py):
        hands the scope key straight to the existing
        ``EntriesController.set_scope()`` -- Entries' own scope contract
        already understands it, so this never re-implements Collection
        filtering (M17 Minimum Collection Integration prompt § 7)."""
        self.entries_controller.set_scope(intent.scope)
        self.app_state.request_navigation(Workspace.ENTRIES)

    def _open_review_at_card(self, intent) -> None:
        """The one consumer of ``StudyTargetIntent``. If the exact
        Collection/Card is no longer available, this fails honestly --
        Review is never entered and ``open_default()`` is never called as
        a fallback -- leaving the user on Collections, a recoverable state
        (prompt § 9)."""
        opened = self.review_controller.open_card(intent.collection_id, intent.card_number)
        if not opened:
            QMessageBox.warning(
                self,
                "Card Unavailable",
                "This Card is no longer available. It may have been removed or reorganized since this list was loaded.",
            )
            return
        self.app_state.request_navigation(Workspace.REVIEW)
        self.app_state.enter_study_mode()

    def _start_quiz(self, intent) -> None:
        """The single entry point every Quiz launch source goes through
        (module docstring). ``QuizController.start()`` never raises -- a
        blocked or failed start still navigates to the Quiz workspace, which
        renders whichever honest state resulted (module docstring;
        QuizView._render).

        The saved Quiz presentation (`VR-STUDY-002`, M17 Feature 3B) is
        resolved here, once, "when the Quiz presentation is created" (M17
        Feature 3B prompt § 7) -- not re-read on every render, and never a
        second in-session switcher. This must happen before ``start()``
        so the very first synchronous ``state_changed`` render already
        uses the right presentation."""
        self.quiz_view.set_presentation(self.settings_controller.quiz_presentation())
        self.quiz_controller.start(intent)
        self.app_state.request_navigation(Workspace.QUIZ)
        self.app_state.enter_study_mode()

    def _on_quiz_return_to_today(self) -> None:
        self.quiz_controller.acknowledge_completion()
        self._exit_study_mode()

    def _on_quiz_next_card(self) -> None:
        self.quiz_controller.acknowledge_completion()
        self.app_state.request_navigation(Workspace.REVIEW)
        self.review_controller.open_default()

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
        """Review and Quiz have no dedicated rail button -- both are
        reached through the shared "study" destination (NavigationRail's
        existing placeholder key), the same way DESIGN.md's frozen IA
        already names that slot. The rail itself stays hidden throughout
        Study Mode regardless, so this only matters for which button is
        checked once Management Mode is restored."""
        return "study" if workspace in (Workspace.REVIEW, Workspace.QUIZ) else workspace.value

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
            self.entries_view.refresh()
            self._last_management_workspace = workspace
        elif workspace is Workspace.COLLECTIONS:
            widget = self.collections_view
            self._workspace_stack.setCurrentWidget(widget)
            self.collections_view.refresh()
            self._last_management_workspace = workspace
        elif workspace is Workspace.TEMPLATES:
            widget = self.templates_view
            self._workspace_stack.setCurrentWidget(widget)
            self.templates_view.refresh()
            self._last_management_workspace = workspace
        elif workspace is Workspace.REVIEW_CALENDAR:
            widget = self.review_calendar_view
            self._workspace_stack.setCurrentWidget(widget)
            self.review_calendar_view.refresh()
            self._last_management_workspace = workspace
        elif workspace is Workspace.DATA_TOOLS:
            widget = self.data_tools_view
            self._workspace_stack.setCurrentWidget(widget)
            self.data_tools_view.refresh()
            self._last_management_workspace = workspace
        elif workspace is Workspace.ANALYTICS:
            widget = self.analytics_view
            self._workspace_stack.setCurrentWidget(widget)
            self.analytics_view.refresh()
            self._last_management_workspace = workspace
        elif workspace is Workspace.REVIEW:
            # No default-Card-open here: whichever caller requested this
            # navigation (_enter_review, _open_review_at_card,
            # _on_quiz_next_card) already prepared the exact Card state
            # itself. Calling open_default() here unconditionally would
            # silently override a specific Collection/Card handoff the
            # instant it navigated -- exactly the fallback the M17 Minimum
            # Collection Integration prompt § 9 forbids. ReviewView
            # re-renders reactively from ReviewController.state_changed,
            # not from this workspace switch, so this is safe.
            widget = self.review_view
            self._workspace_stack.setCurrentWidget(widget)
        elif workspace is Workspace.QUIZ:
            # No refresh-on-render here: _start_quiz() already called
            # QuizController.start() before requesting this navigation, and
            # QuizController's own completion/exit actions manage state
            # explicitly rather than through a workspace re-render.
            widget = self.quiz_view
            self._workspace_stack.setCurrentWidget(widget)
        elif workspace is Workspace.SETTINGS:
            widget = self.settings_view
            self._workspace_stack.setCurrentWidget(widget)
            self._last_management_workspace = workspace

        self._navigation_rail.set_active(self._rail_key_for_workspace(workspace))

        # The workspace switch above is already complete and correct by
        # this point; the transition below is a purely decorative reveal of
        # that already-correct state, never a precondition for it.
        if animate and widget is not None:
            self._motion.fade_in(widget)

    def _render_mode(self, mode: ShellMode, *, animate: bool = True) -> None:
        is_study = mode is ShellMode.STUDY
        # Review and Quiz each supply their own complete session bar
        # (module docstring); the generic toolbar only covers a
        # hypothetical bare Study mode with no dedicated content, which no
        # real workspace exercises today.
        show_generic_toolbar = is_study and self.app_state.workspace not in (Workspace.REVIEW, Workspace.QUIZ)
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

    def closeEvent(self, event) -> None:
        # Human Gate 2 corrective / independent-review finding: without
        # this, closing the app while an Analytics background load was
        # still in flight could destroy AnalyticsController (and the
        # QThread it was the only reference keeping alive) while the
        # thread was still running -- fatal in Qt ("QThread: Destroyed
        # while thread is still running"). Blocks briefly so any in-
        # flight load finishes cleanly first.
        self.analytics_controller.shutdown()
        # Same QThread-lifetime rule for the Data Tools hub's background
        # Audio Export voice preflight (Final Human Acceptance Gate
        # corrective): never let the app tear down while it is running.
        self.data_tools_view._audio_preflight_controller.shutdown_voice_preflight()
        # Phase E update awareness: ensure background update check workers are safely stopped/detached
        self.settings_controller.shutdown()
        super().closeEvent(event)

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.today_controller import TodayController
from src.ui_desktop.state.handoff import (
    QUIZ_NO_TARGET_TOOLTIP,
    EntriesScopeIntent,
    LearningActionIntent,
    quiz_launch_intent_from_learning_action_intent,
)
from src.ui_desktop.theming.metrics import CONTEXT_RAIL_WIDTH, SPACING
from src.ui_desktop.widgets.panels import ActionRowCard, SuggestedActionTile, SummaryStatCard

"""
Today / Home -- Command Center (DESIGN.md § 6.1, `VR-TODAY-001`:
`Today - Home.pdf` p2 Variant A). Fresh implementation from the
replacement DESIGN authority after the controlled M17 reset -- not a
restoration of either rejected attempt and not built from the rejected
top-nav/KPI/full-width-table composition.

Three-region composition. The left Navigation Rail is shared shell
infrastructure owned by ``MainWindow`` (DESIGN.md § 5); this view owns
only the remaining two regions:

    Center Command Workspace (dominant, stretch=1)
        compact 4-metric status summary -- auxiliary, never a KPI tile
        Today's Learning Queue -- the visual/action anchor
        Suggested Next Actions -- supports the queue

    Right Context Rail (secondary but persistent, fixed width)
        Recent Activity
        Collections Needing Attention
        Quick Actions

Every number/recommendation is read directly from ``TodayController``
projections over ``src.learning_workflow`` -- no duplicated business
logic, no legacy Review-due scheduling reintroduced (DESIGN.md § 6.1
product semantics). The summary intentionally uses this app's real
metrics (available/never-quizzed/quizzed-today/learned-today) rather than
the canonical reference's "Due today" framing, which would imply a
Review-scheduling due-date concept this product does not have.

Since M17 Feature 3, a Learning Queue item whose ``LearningActionIntent``
represents a real supported Quiz target (``action == "quiz"``) is wired to
a real launch: ``quiz_launch_intent_from_learning_action_intent``
(``state/handoff.py``) converts it into the same ``QuizLaunchIntent``
Review builds, and MainWindow's one ``QuizController`` starts it -- Today
never talks to ``src.quiz``/``src.template_quiz`` directly, and never
invents a second session mechanism (M17 Feature 3 prompt § 11). The
contextless Quick Actions "Start Quiz" tile, and a Suggested Next Action
naming "Quiz" without a specific Collection/Card, still have no real
target to launch -- those stay honestly disabled with
``QUIZ_NO_TARGET_TOOLTIP`` rather than fabricating one; only ``action ==
"organize"`` (Entries) and a Review-targeted suggestion have unambiguous,
data-complete real destinations without further user input.
"""


class TodayView(QWidget):
    navigate_to_entries_requested = Signal()
    navigate_to_entries_scope_requested = Signal(object)  # EntriesScopeIntent
    navigate_to_review_requested = Signal()
    quiz_launch_requested = Signal(object)  # QuizLaunchIntent

    def __init__(self, controller: TodayController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(SPACING.lg)

        root.addWidget(self._build_command_workspace(), 1)
        root.addWidget(self._build_context_rail(), 0)

        controller.overview_changed.connect(self._render_overview)

    # -- construction ---------------------------------------------------

    def _build_command_workspace(self) -> QWidget:
        workspace = QWidget(self)
        workspace.setObjectName("today-command-workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.md)

        header_row = QHBoxLayout()
        title = QLabel("Today", workspace)
        title.setObjectName("today-page-title")
        self._date_label = QLabel("", workspace)
        self._date_label.setObjectName("today-date")
        header_row.addWidget(title)
        header_row.addStretch(1)
        header_row.addWidget(self._date_label)
        layout.addLayout(header_row)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(SPACING.sm)
        self._summary_cards = {
            "available_cards": SummaryStatCard("Available Cards", 0, workspace),
            "never_quizzed": SummaryStatCard("Never Quizzed", 0, workspace),
            "quizzed_today": SummaryStatCard("Quizzed Today", 0, workspace),
            "learned_today": SummaryStatCard("Learned Today", 0, workspace),
        }
        for card in self._summary_cards.values():
            summary_row.addWidget(card)
        layout.addLayout(summary_row)

        queue_heading = QLabel("Today's Learning Queue", workspace)
        queue_heading.setObjectName("today-section-heading")
        layout.addWidget(queue_heading)

        # The queue is the dominant region but must stay *bounded*: at
        # normal window size, real data can produce enough items to push
        # Suggested Next Actions off the first screen entirely (DESIGN.md
        # § 6.1 requires it stay visibly represented, not scrolled away).
        # A scroll area lets the queue itself take the remaining stretch
        # while Suggested Next Actions stays pinned below it, always
        # visible.
        queue_content = QWidget()
        self._queue_column = QVBoxLayout(queue_content)
        self._queue_column.setContentsMargins(0, 0, 0, 0)
        self._queue_column.setSpacing(SPACING.xs)

        queue_scroll = QScrollArea(workspace)
        queue_scroll.setObjectName("today-queue-scroll")
        queue_scroll.setWidgetResizable(True)
        queue_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        queue_scroll.setWidget(queue_content)
        queue_scroll.setMinimumHeight(120)
        # Stretch=1 *and* capped: without a stretch factor, QScrollArea's
        # generic sizeHint() left most of the window as dead space below
        # the queue even with items to show. Stretch alone caused the
        # original bug (unbounded growth swallowed Suggested Next
        # Actions entirely). Both together let the queue actually use the
        # available room up to a firm cap -- it scrolls internally past
        # that cap instead of growing further, and Suggested Next Actions
        # always immediately follows it.
        queue_scroll.setMaximumHeight(400)
        layout.addWidget(queue_scroll, 1)

        suggested_heading = QLabel("Suggested Next Actions", workspace)
        suggested_heading.setObjectName("today-section-heading")
        layout.addWidget(suggested_heading)

        # A horizontal row of bounded tiles, not a vertical stack of
        # full-width rows: each real recommendation occupies one compact
        # tile, left-anchored via the trailing stretch, never stretched
        # across the whole workspace width.
        self._suggested_row = QHBoxLayout()
        self._suggested_row.setSpacing(SPACING.sm)
        layout.addLayout(self._suggested_row)

        # Any extra vertical space (a taller-than-normal window) collects
        # here instead of being reclaimed by the queue -- Suggested Next
        # Actions stays immediately below the queue at any window height.
        layout.addStretch(1)

        return workspace

    def _build_context_rail(self) -> QWidget:
        rail = QWidget(self)
        rail.setObjectName("today-context-rail")
        # See widgets/panels.py docstring: a bare QWidget ignores its QSS
        # border/background without this attribute.
        rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rail.setFixedWidth(CONTEXT_RAIL_WIDTH)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(SPACING.md, SPACING.lg, SPACING.md, SPACING.lg)
        layout.setSpacing(SPACING.md)

        activity_heading = QLabel("Recent Activity", rail)
        activity_heading.setObjectName("today-context-heading")
        layout.addWidget(activity_heading)
        self._activity_column = QVBoxLayout()
        self._activity_column.setSpacing(SPACING.sm)
        layout.addLayout(self._activity_column)

        layout.addWidget(_section_divider(rail))

        attention_heading = QLabel("Collections Needing Attention", rail)
        attention_heading.setObjectName("today-context-heading")
        layout.addWidget(attention_heading)
        self._attention_column = QVBoxLayout()
        self._attention_column.setSpacing(SPACING.xs)
        layout.addLayout(self._attention_column)

        layout.addWidget(_section_divider(rail))

        quick_actions_heading = QLabel("Quick Actions", rail)
        quick_actions_heading.setObjectName("today-context-heading")
        layout.addWidget(quick_actions_heading)

        # A compact 2-column block grid (DESIGN.md § 6.1 canonical Quick
        # Actions grammar), not two full-width stretched buttons. Only
        # genuinely real actions are offered -- no placeholder actions
        # (e.g. "Add entry") for capability the desktop app doesn't have.
        quick_actions_grid = QGridLayout()
        quick_actions_grid.setSpacing(SPACING.xs)

        open_entries_button = _quick_action_button("Open Entries", rail)
        open_entries_button.clicked.connect(self.navigate_to_entries_requested.emit)
        quick_actions_grid.addWidget(open_entries_button, 0, 0)

        start_quiz_button = _quick_action_button("Start Quiz", rail)
        start_quiz_button.setEnabled(False)
        start_quiz_button.setToolTip(QUIZ_NO_TARGET_TOOLTIP)
        quick_actions_grid.addWidget(start_quiz_button, 0, 1)

        # Both cells are fixed-width; a stretch in the (unused) third
        # column keeps the pair anchored to the first row/left edge
        # instead of stretching across the full rail width.
        quick_actions_grid.setColumnStretch(2, 1)
        layout.addLayout(quick_actions_grid)
        layout.addStretch(1)
        return rail

    # -- rendering --------------------------------------------------------

    def _render_overview(self, overview: dict) -> None:
        self._render_date(overview.get("today"))
        self._render_summary(overview)
        self._render_queue()
        self._render_suggested_actions()
        self._render_recent_activity()
        self._render_attention()

    def _render_date(self, today_iso: str | None) -> None:
        if not today_iso:
            self._date_label.setText("")
            return
        try:
            self._date_label.setText(datetime.fromisoformat(today_iso).strftime("%A, %d %B"))
        except ValueError:
            self._date_label.setText(today_iso)

    def _render_summary(self, overview: dict) -> None:
        workload = overview.get("study_workload") or {}
        quiz_activity = overview.get("quiz_activity") or {}
        review_activity = overview.get("review_activity") or {}
        self._summary_cards["available_cards"].set_value(workload.get("total_cards", 0))
        self._summary_cards["never_quizzed"].set_value(workload.get("never_quizzed_cards", 0))
        self._summary_cards["quizzed_today"].set_value(quiz_activity.get("item_attempts", 0))
        self._summary_cards["learned_today"].set_value(review_activity.get("reviewed_cards", 0))

    def _render_queue(self) -> None:
        _clear_layout(self._queue_column)
        items = self._controller.queue_items()
        if not items:
            self._queue_column.addWidget(_empty_state_label("Nothing queued right now."))
            self._queue_column.addStretch(1)
            return
        for item in items:
            self._queue_column.addWidget(self._build_queue_card(item))
        self._queue_column.addStretch(1)

    def _build_queue_card(self, item: dict) -> ActionRowCard:
        intent = self._controller.build_learning_action_intent(item)
        button_text, enabled, tooltip = self._action_button_spec(intent)
        card = ActionRowCard(
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            button_text,
            button_enabled=enabled,
            button_tooltip=tooltip,
            object_name="today-queue-card",
        )
        if intent.action == "organize":
            card.action_triggered.connect(self.navigate_to_entries_requested.emit)
        elif intent.action == "quiz":
            quiz_intent = quiz_launch_intent_from_learning_action_intent(intent)
            if quiz_intent is not None:
                card.action_triggered.connect(lambda quiz_intent=quiz_intent: self.quiz_launch_requested.emit(quiz_intent))
        return card

    def _render_suggested_actions(self) -> None:
        _clear_layout(self._suggested_row)
        recommendation = self._controller.primary_recommendation()
        if recommendation is None:
            self._suggested_row.addWidget(_empty_state_label("No further suggestions right now."))
            self._suggested_row.addStretch(1)
            return

        target_page = recommendation.get("target_page")
        if target_page == "Entries":
            tile = SuggestedActionTile(
                str(recommendation.get("title") or ""),
                str(recommendation.get("description") or ""),
                "Open Entries",
                button_enabled=True,
            )
            tile.action_triggered.connect(self.navigate_to_entries_requested.emit)
        elif target_page == "Review":
            tile = SuggestedActionTile(
                str(recommendation.get("title") or ""),
                str(recommendation.get("description") or ""),
                "Open Review",
                button_enabled=True,
            )
            tile.action_triggered.connect(self.navigate_to_review_requested.emit)
        else:
            # target_page == "Quiz" here names a special-pool drill
            # (Mistake Book / Proficient Pool / Starred) without a specific
            # Collection/Card -- unlike a Learning Queue item, this
            # recommendation carries no collection_id to launch a real
            # Quiz from, so it stays honestly disabled rather than
            # fabricating a target (module docstring).
            tile = SuggestedActionTile(
                str(recommendation.get("title") or ""),
                str(recommendation.get("description") or ""),
                f"Open {target_page}" if target_page else "Unavailable",
                button_enabled=False,
                button_tooltip=QUIZ_NO_TARGET_TOOLTIP,
            )
        # Not every Learning Queue item's LearningActionIntent duplicates
        # the single primary_recommendation() -- Suggested Next Actions
        # intentionally shows only that one real recommendation, never a
        # fabricated second/third tile just to fill the row.
        self._suggested_row.addWidget(tile, 0)
        self._suggested_row.addStretch(1)

    def _render_recent_activity(self) -> None:
        _clear_layout(self._activity_column)
        items = self._controller.recent_activity()
        if not items:
            self._activity_column.addWidget(_empty_state_label("No activity yet today."))
            return
        for item in items[:5]:
            self._activity_column.addWidget(self._build_activity_row(item))

    def _build_activity_row(self, item: dict) -> QWidget:
        action = str(item.get("action") or "Quiz").replace("_", " ").title()
        title = QLabel(f"{action} completed", self)
        title.setObjectName("today-activity-title")
        subtitle = QLabel(
            f"{item.get('collection_name', '')} · Card #{item.get('card_number', '')}",
            self,
        )
        subtitle.setObjectName("today-activity-subtitle")
        row = QWidget(self)
        column = QVBoxLayout(row)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(title)
        column.addWidget(subtitle)
        return row

    def _render_attention(self) -> None:
        _clear_layout(self._attention_column)
        items = self._controller.collections_needing_attention()
        if not items:
            self._attention_column.addWidget(_empty_state_label("Nothing needs attention."))
            return
        for item in items:
            self._attention_column.addWidget(self._build_attention_row(item))

    def _build_attention_row(self, item: dict) -> QWidget:
        """Each pool with real practiceable Entries is an actionable
        management/browse target, so it completes the handoff into the
        matching Entries system scope (M17 Minimum Collection Integration
        prompt § 8) instead of staying a plain informational row."""
        button = QPushButton(self)
        button.setObjectName("today-attention-row")
        button.setFlat(True)
        layout = QHBoxLayout(button)
        layout.setContentsMargins(SPACING.xs, SPACING.xs, SPACING.xs, SPACING.xs)
        # "★ " prefix on Starred is presentation-only (M17 Minimum
        # Collection Integration corrective pass § 12); system_type stays
        # "starred".
        label_text = str(item.get("label") or "")
        if item.get("system_type") == "starred":
            label_text = f"★ {label_text}"
        label = QLabel(label_text, button)
        chip = QLabel(f"{item.get('entry_count', 0)} item(s)", button)
        chip.setObjectName("today-attention-chip")
        layout.addWidget(label, 1)
        layout.addWidget(chip, 0)

        system_type = item.get("system_type")
        if system_type:
            button.clicked.connect(
                lambda _checked=False, system_type=system_type: self.navigate_to_entries_scope_requested.emit(
                    EntriesScopeIntent(scope=f"system:{system_type}")
                )
            )
        else:
            button.setEnabled(False)
        return button

    def _action_button_spec(self, intent: LearningActionIntent) -> tuple[str, bool, str]:
        if intent.action == "quiz":
            if quiz_launch_intent_from_learning_action_intent(intent) is not None:
                return "Quiz", True, ""
            return "Quiz", False, QUIZ_NO_TARGET_TOOLTIP
        if intent.action == "organize":
            return "Organize in Entries", True, ""
        return "Unavailable", False, "This action is not recognized yet."


def _empty_state_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("today-empty-state")
    return label


def _section_divider(parent: QWidget) -> QWidget:
    """A 1px separator between right-rail sections (DESIGN.md § 6.1: the
    Context Rail's three sections must read as intentionally separated,
    not loose text in a column)."""
    divider = QWidget(parent)
    divider.setObjectName("today-context-divider")
    divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    divider.setFixedHeight(1)
    return divider


def _quick_action_button(text: str, parent: QWidget) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName("today-quick-action")
    button.setFixedSize(96, 40)
    return button


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()

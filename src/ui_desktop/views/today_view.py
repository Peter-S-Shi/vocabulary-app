from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui_desktop.controllers.today_controller import TodayController
from src.ui_desktop.state.handoff import LearningActionIntent
from src.ui_desktop.theming.metrics import CONTEXT_RAIL_WIDTH
from src.ui_desktop.widgets.panels import ActionRowCard, SummaryStatCard

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

Any action that would launch Review/Quiz is rendered honestly disabled --
neither is implemented in the desktop app yet (M17 Feature 1
fresh-implementation prompt § 9). The real ``LearningActionIntent`` is
still built for every queue item so a later checkpoint can wire it in
without redesigning this view, but the button never pretends to work.
"""

QUIZ_UNAVAILABLE_TOOLTIP = "Review/Quiz is not implemented yet in the desktop app."


class TodayView(QWidget):
    navigate_to_entries_requested = Signal()

    def __init__(self, controller: TodayController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(24)

        root.addWidget(self._build_command_workspace(), 1)
        root.addWidget(self._build_context_rail(), 0)

        controller.overview_changed.connect(self._render_overview)

    # -- construction ---------------------------------------------------

    def _build_command_workspace(self) -> QWidget:
        workspace = QWidget(self)
        workspace.setObjectName("today-command-workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

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
        summary_row.setSpacing(12)
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

        self._queue_column = QVBoxLayout()
        self._queue_column.setSpacing(8)
        layout.addLayout(self._queue_column, 1)

        suggested_heading = QLabel("Suggested Next Actions", workspace)
        suggested_heading.setObjectName("today-section-heading")
        layout.addWidget(suggested_heading)

        self._suggested_column = QVBoxLayout()
        self._suggested_column.setSpacing(8)
        layout.addLayout(self._suggested_column)

        return workspace

    def _build_context_rail(self) -> QWidget:
        rail = QWidget(self)
        rail.setObjectName("today-context-rail")
        rail.setFixedWidth(CONTEXT_RAIL_WIDTH)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        activity_heading = QLabel("Recent Activity", rail)
        activity_heading.setObjectName("today-context-heading")
        layout.addWidget(activity_heading)
        self._activity_column = QVBoxLayout()
        self._activity_column.setSpacing(8)
        layout.addLayout(self._activity_column)

        attention_heading = QLabel("Collections Needing Attention", rail)
        attention_heading.setObjectName("today-context-heading")
        layout.addWidget(attention_heading)
        self._attention_column = QVBoxLayout()
        self._attention_column.setSpacing(6)
        layout.addLayout(self._attention_column)

        quick_actions_heading = QLabel("Quick Actions", rail)
        quick_actions_heading.setObjectName("today-context-heading")
        layout.addWidget(quick_actions_heading)

        quick_actions_row = QHBoxLayout()
        open_entries_button = QPushButton("Open Entries", rail)
        open_entries_button.setObjectName("today-quick-action")
        open_entries_button.clicked.connect(self.navigate_to_entries_requested.emit)
        quick_actions_row.addWidget(open_entries_button)

        start_quiz_button = QPushButton("Start Quiz", rail)
        start_quiz_button.setObjectName("today-quick-action")
        start_quiz_button.setEnabled(False)
        start_quiz_button.setToolTip(QUIZ_UNAVAILABLE_TOOLTIP)
        quick_actions_row.addWidget(start_quiz_button)
        layout.addLayout(quick_actions_row)

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
            return
        for item in items:
            self._queue_column.addWidget(self._build_queue_card(item))

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
        return card

    def _render_suggested_actions(self) -> None:
        _clear_layout(self._suggested_column)
        recommendation = self._controller.primary_recommendation()
        if recommendation is None:
            self._suggested_column.addWidget(_empty_state_label("No further suggestions right now."))
            return

        target_page = recommendation.get("target_page")
        if target_page == "Entries":
            card = ActionRowCard(
                str(recommendation.get("title") or ""),
                str(recommendation.get("description") or ""),
                "Open Entries",
                button_enabled=True,
                object_name="today-suggested-card",
            )
            card.action_triggered.connect(self.navigate_to_entries_requested.emit)
        else:
            card = ActionRowCard(
                str(recommendation.get("title") or ""),
                str(recommendation.get("description") or ""),
                f"Open {target_page}" if target_page else "Unavailable",
                button_enabled=False,
                button_tooltip=QUIZ_UNAVAILABLE_TOOLTIP,
                object_name="today-suggested-card",
            )
        self._suggested_column.addWidget(card)

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
            row = QWidget(self)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(str(item.get("label") or ""), row)
            chip = QLabel(f"{item.get('entry_count', 0)} item(s)", row)
            chip.setObjectName("today-attention-chip")
            row_layout.addWidget(label, 1)
            row_layout.addWidget(chip, 0)
            self._attention_column.addWidget(row)

    def _action_button_spec(self, intent: LearningActionIntent) -> tuple[str, bool, str]:
        if intent.action == "quiz":
            return "Quiz", False, QUIZ_UNAVAILABLE_TOOLTIP
        if intent.action == "organize":
            return "Organize in Entries", True, ""
        return "Unavailable", False, "This action is not recognized yet."


def _empty_state_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("today-empty-state")
    return label


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()

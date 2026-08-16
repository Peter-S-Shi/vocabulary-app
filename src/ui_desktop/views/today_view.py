from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.today_controller import TodayController
from src.ui_desktop.qt_models.learning_queue_table_model import LearningQueueTableModel

"""
Today / Home -- Command Center (DESIGN.md § 4.1), the first real M17
product feature built on the M16.2 vertical-slice proof. Hierarchy, top to
bottom, matches the frozen archetype: compact summary, Today's Learning
Queue as the dominant area (largest stretch factor below), suggested next
action, recent activity / collections needing attention, quick actions.
Analytics-style charts are deliberately excluded (DESIGN.md § 18 Today
anti-pattern: "statistics visually dominating the learning queue").

Review/Quiz destinations are not yet implemented in the desktop app (M17
Feature 1 prompt § 6/§ 13): every action here that would target them is
intentionally disabled with an explanatory tooltip rather than a dead
button pretending they exist. Only the Entries handoff is real, wired
through ``entries_requested`` so this view never imports EntriesView or
AppState directly (M17 Feature 1 prompt § 5, no view-to-view coupling).

Not every Learning Queue item is a Review/Quiz candidate: a
``recommendation_type = "recent_entries_suggestion"`` item's real next
step is organizing recently added Entries into a Collection
(``state/handoff.py``'s ``action="organize"``), which desktop Collection
management does not implement yet either -- it gets its own distinct
pending tooltip rather than reusing the Review/Quiz wording, which would
misstate why it can't be started.
"""

PENDING_MIGRATION_TOOLTIP = (
    "Review/Quiz isn't available in the desktop app yet -- coming in a later M17 checkpoint."
)
PENDING_ORGANIZE_TOOLTIP = (
    "Organizing entries into a Collection isn't available in the desktop app yet -- "
    "open Entries to review them individually in the meantime."
)


class TodayView(QWidget):
    entries_requested = Signal()

    def __init__(self, controller: TodayController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._next_action_target_page: str | None = None

        self._page_title = QLabel("Today", self)
        self._page_title.setObjectName("today-page-title")

        self._summary_label = QLabel("Loading Today overview...", self)
        self._summary_label.setObjectName("today-summary")
        self._summary_label.setProperty("role", "secondary")

        self._queue_heading = QLabel("Today's Learning Queue", self)
        self._queue_heading.setObjectName("today-queue-heading")

        self._queue_model = LearningQueueTableModel()
        self._queue_table = QTableView(self)
        self._queue_table.setObjectName("today-queue-table")
        self._queue_table.setModel(self._queue_model)
        self._queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._queue_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._queue_table.horizontalHeader().setStretchLastSection(True)

        self._queue_detail_label = QLabel("Select a Learning Queue item to see details.", self)
        self._queue_detail_label.setObjectName("today-queue-detail")
        self._queue_detail_label.setWordWrap(True)
        self._queue_start_button = QPushButton("Start", self)
        self._queue_start_button.setObjectName("today-queue-start")
        self._queue_start_button.setEnabled(False)
        self._queue_start_button.setToolTip(PENDING_MIGRATION_TOOLTIP)

        queue_detail_row = QHBoxLayout()
        queue_detail_row.addWidget(self._queue_detail_label, 1)
        queue_detail_row.addWidget(self._queue_start_button)

        self._next_action_panel = QFrame(self)
        self._next_action_panel.setObjectName("today-panel")
        self._next_action_title = QLabel("", self)
        self._next_action_title.setObjectName("today-next-action-title")
        self._next_action_description = QLabel("", self)
        self._next_action_description.setObjectName("today-next-action-description")
        self._next_action_description.setWordWrap(True)
        self._next_action_description.setProperty("role", "secondary")
        self._next_action_button = QPushButton("Go", self)
        self._next_action_button.setObjectName("today-next-action-button")
        self._next_action_button.setProperty("primary", True)
        self._next_action_button.setEnabled(False)
        self._next_action_button.clicked.connect(self._on_next_action_clicked)

        next_action_header = QHBoxLayout()
        next_action_header.addWidget(self._next_action_title, 1)
        next_action_header.addWidget(self._next_action_button)
        next_action_layout = QVBoxLayout(self._next_action_panel)
        next_action_layout.addLayout(next_action_header)
        next_action_layout.addWidget(self._next_action_description)

        self._recent_activity_panel = QFrame(self)
        self._recent_activity_panel.setObjectName("today-panel")
        recent_activity_heading = QLabel("Recent Card Learning", self)
        recent_activity_heading.setProperty("role", "secondary")
        self._recent_activity_label = QLabel("", self)
        self._recent_activity_label.setObjectName("today-recent-activity")
        self._recent_activity_label.setWordWrap(True)
        recent_activity_layout = QVBoxLayout(self._recent_activity_panel)
        recent_activity_layout.addWidget(recent_activity_heading)
        recent_activity_layout.addWidget(self._recent_activity_label, 1)

        self._attention_panel = QFrame(self)
        self._attention_panel.setObjectName("today-panel")
        attention_heading = QLabel("Collections Needing Attention", self)
        attention_heading.setProperty("role", "secondary")
        self._attention_label = QLabel("", self)
        self._attention_label.setObjectName("today-attention")
        self._attention_label.setWordWrap(True)
        attention_layout = QVBoxLayout(self._attention_panel)
        attention_layout.addWidget(attention_heading)
        attention_layout.addWidget(self._attention_label, 1)

        secondary_row = QHBoxLayout()
        secondary_row.addWidget(self._recent_activity_panel, 1)
        secondary_row.addWidget(self._attention_panel, 1)

        self._entries_button = QPushButton("Open Entries", self)
        self._entries_button.setObjectName("today-quick-entries")
        self._entries_button.setProperty("primary", True)
        self._entries_button.clicked.connect(self.entries_requested.emit)

        self._review_button = QPushButton("Review", self)
        self._review_button.setObjectName("today-quick-review")
        self._review_button.setEnabled(False)
        self._review_button.setToolTip(PENDING_MIGRATION_TOOLTIP)

        self._quiz_button = QPushButton("Quiz", self)
        self._quiz_button.setObjectName("today-quick-quiz")
        self._quiz_button.setEnabled(False)
        self._quiz_button.setToolTip(PENDING_MIGRATION_TOOLTIP)

        quick_actions_row = QHBoxLayout()
        quick_actions_row.addWidget(self._entries_button)
        quick_actions_row.addWidget(self._review_button)
        quick_actions_row.addWidget(self._quiz_button)
        quick_actions_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._page_title)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._queue_heading)
        layout.addWidget(self._queue_table, 3)
        layout.addLayout(queue_detail_row)
        layout.addWidget(self._next_action_panel)
        layout.addLayout(secondary_row, 1)
        layout.addLayout(quick_actions_row)

        controller.overview_changed.connect(self._render_overview)

        selection_model = self._queue_table.selectionModel()
        if selection_model is not None:
            selection_model.currentRowChanged.connect(self._on_queue_row_changed)

    def _render_overview(self, overview: dict) -> None:
        workload = overview.get("study_workload") or {}
        quiz_activity = overview.get("quiz_activity") or {}
        review_activity = overview.get("review_activity") or {}
        accuracy = quiz_activity.get("accuracy")
        accuracy_text = f"{accuracy}%" if accuracy is not None else "--"

        self._summary_label.setText(
            f"Available Cards: {workload.get('total_cards', 0)}   |   "
            f"Never Quizzed: {workload.get('never_quizzed_cards', 0)}   |   "
            f"Quiz Items Today: {quiz_activity.get('item_attempts', 0)} "
            f"(Accuracy: {accuracy_text})   |   "
            f"Card Learning Today: {review_activity.get('reviewed_cards', 0)}"
        )

        self._queue_model.set_rows(self._controller.queue_items())
        self._queue_detail_label.setText("Select a Learning Queue item to see details.")
        self._queue_start_button.setEnabled(False)
        self._queue_start_button.setToolTip(PENDING_MIGRATION_TOOLTIP)

        self._render_next_action(self._controller.primary_recommendation())
        self._render_recent_activity(self._controller.recent_activity())
        self._render_attention(self._controller.collections_needing_attention())

    def _render_next_action(self, recommendation: dict | None) -> None:
        if not recommendation:
            self._next_action_target_page = None
            self._next_action_title.setText("No recommendation is available yet.")
            self._next_action_description.setText("")
            self._next_action_button.setText("Go")
            self._next_action_button.setEnabled(False)
            self._next_action_button.setToolTip("")
            return

        self._next_action_title.setText(recommendation.get("title", ""))
        self._next_action_description.setText(recommendation.get("description", ""))
        target_page = recommendation.get("target_page")
        self._next_action_target_page = target_page

        if target_page == "Entries":
            self._next_action_button.setText("Open Entries")
            self._next_action_button.setEnabled(True)
            self._next_action_button.setToolTip("")
        else:
            self._next_action_button.setText(target_page or "Go")
            self._next_action_button.setEnabled(False)
            self._next_action_button.setToolTip(PENDING_MIGRATION_TOOLTIP)

    def _on_next_action_clicked(self) -> None:
        # Only "Entries" is ever enabled (see _render_next_action), but the
        # target is checked again here rather than assuming button state,
        # so this handler can never fire an Entries navigation for a
        # different/unmigrated target page.
        if self._next_action_target_page == "Entries":
            self.entries_requested.emit()

    def _render_recent_activity(self, recent: list[dict]) -> None:
        if not recent:
            self._recent_activity_label.setText("No Card learning recorded yet today.")
            return
        lines = [
            f"{item.get('collection_name', '')} / Card #{item.get('card_number', '')} "
            f"({item.get('action', '')})"
            for item in recent[:5]
        ]
        self._recent_activity_label.setText("\n".join(lines))

    def _render_attention(self, attention: list[dict]) -> None:
        if not attention:
            self._attention_label.setText("Nothing needs attention right now.")
            return
        lines = [f"{item['label']}: {item['entry_count']} item(s)" for item in attention]
        self._attention_label.setText("\n".join(lines))

    def _on_queue_row_changed(self, current, _previous) -> None:
        row = current.row() if current.isValid() else -1
        item = self._queue_model.row_at(row)
        if item is None:
            self._queue_detail_label.setText("Select a Learning Queue item to see details.")
            self._queue_start_button.setEnabled(False)
            self._queue_start_button.setToolTip(PENDING_MIGRATION_TOOLTIP)
            return

        intent = self._controller.build_learning_action_intent(item)
        self._queue_detail_label.setText(f"{item.get('title', '')} -- {item.get('description', '')}")
        # No current Learning Queue item has a migrated desktop
        # destination yet, so Start always stays disabled -- but *why* it
        # is disabled differs by intent.action, and must say so accurately
        # rather than blaming Review/Quiz for an item that was never
        # headed there (M17 Feature 1 prompt § 6/§ 7 and its corrective
        # patch). If a future checkpoint migrates one of these
        # destinations, this is the one place that needs to branch on
        # ``intent.action`` to actually enable Start.
        self._queue_start_button.setEnabled(False)
        if intent.action == "organize":
            self._queue_start_button.setToolTip(PENDING_ORGANIZE_TOOLTIP)
        else:
            self._queue_start_button.setToolTip(
                f"{PENDING_MIGRATION_TOOLTIP} (would start: {intent.action} / {intent.reason})"
            )

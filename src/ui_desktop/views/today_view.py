from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.today_controller import TodayController
from src.ui_desktop.qt_models.learning_queue_table_model import LearningQueueTableModel
from src.ui_desktop.theming.tokens import METRICS
from src.ui_desktop.widgets.primitives import (
    EmptyState,
    MetricTile,
    PageHeader,
    Panel,
    SectionHeading,
)

"""
Today / Home -- Command Center (DESIGN.md § 4.1), the first real M17
product feature.

Hierarchy, top to bottom, matches the frozen archetype: page header,
compact summary tiles, Today's Learning Queue as the dominant area
(largest stretch factor below), suggested next action, recent activity /
collections needing attention, quick actions. Analytics-style charts are
deliberately excluded (DESIGN.md § 18 Today anti-pattern: "statistics
visually dominating the learning queue") -- the summary is a quiet row of
figures, not a dashboard.

All visual treatment comes from the shared grammar: layout uses
``widgets/primitives.py`` and the ``theming/tokens.py`` spacing rhythm, and
colors/typography resolve from the theme stylesheet. **This view hardcodes
no color and no font size**, so it inherits Light/Dark and any future
accent family for free.

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

        self._header = PageHeader(
            "Today",
            "Your current learning workload and the next useful action.",
            self,
        )

        self._summary_row, self._tiles = self._build_summary_row()
        self._queue_section = self._build_queue_section()
        self._next_action_panel = self._build_next_action_panel()
        self._supporting_row = self._build_supporting_row()
        self._quick_actions_row = self._build_quick_actions_row()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            METRICS.page_margin, METRICS.space_xl, METRICS.page_margin, METRICS.space_xl
        )
        layout.setSpacing(METRICS.space_lg)
        layout.addWidget(self._header)
        layout.addLayout(self._summary_row)
        # The Learning Queue carries the dominant stretch: DESIGN.md § 4.1
        # requires it to outweigh statistics, and § 19's Today PASS
        # criterion is that the queue is the visual priority.
        layout.addWidget(self._queue_section, 5)
        layout.addWidget(self._next_action_panel)
        layout.addLayout(self._supporting_row, 2)
        layout.addLayout(self._quick_actions_row)

        controller.overview_changed.connect(self._render_overview)

    # --- construction -----------------------------------------------------

    def _build_summary_row(self) -> tuple[QHBoxLayout, dict[str, MetricTile]]:
        tiles = {
            "available_cards": MetricTile("Available Cards", emphasized=True),
            "never_quizzed": MetricTile("Never Quizzed"),
            "quiz_items_today": MetricTile("Quiz Items Today"),
            "card_learning_today": MetricTile("Card Learning Today"),
        }
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(METRICS.space_md)
        for tile in tiles.values():
            row.addWidget(tile, 1)
        return row, tiles

    def _build_queue_section(self) -> Panel:
        panel = Panel(parent=self)

        heading_row = QHBoxLayout()
        heading_row.setContentsMargins(0, 0, 0, 0)
        self._queue_heading = SectionHeading("Today's Learning Queue", panel)
        self._queue_heading.setObjectName("today-queue-heading")
        self._queue_count_label = QLabel("", panel)
        self._queue_count_label.setProperty("typography", "meta")
        heading_row.addWidget(self._queue_heading)
        heading_row.addStretch(1)
        heading_row.addWidget(self._queue_count_label)
        panel.body_layout().addLayout(heading_row)

        self._queue_model = LearningQueueTableModel()
        self._queue_table = QTableView(panel)
        self._queue_table.setObjectName("today-queue-table")
        self._queue_table.setModel(self._queue_model)
        self._queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._queue_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._queue_table.setAlternatingRowColors(False)
        self._queue_table.setShowGrid(False)
        self._queue_table.setFrameShape(QTableView.Shape.NoFrame)
        self._queue_table.verticalHeader().setVisible(False)
        self._queue_table.verticalHeader().setDefaultSectionSize(METRICS.table_row_height)
        self._queue_table.horizontalHeader().setHighlightSections(False)
        self._queue_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Detail is the widest, most-read column, so it takes the slack while
        # the short factual columns stay compact and scannable.
        header = self._queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self._queue_empty_state = EmptyState(
            "Nothing is queued right now.\n"
            "Add entries and organize them into a Collection to build a learning queue.",
            panel,
        )

        # Swapped rather than left blank: DESIGN.md § 16 requires an empty
        # state to explain what would appear here.
        self._queue_stack = QStackedWidget(panel)
        self._queue_stack.addWidget(self._queue_table)
        self._queue_stack.addWidget(self._queue_empty_state)
        panel.add_widget(self._queue_stack, 1)

        self._queue_detail_label = QLabel("Select a Learning Queue item to see details.", panel)
        self._queue_detail_label.setObjectName("today-queue-detail")
        self._queue_detail_label.setProperty("typography", "body")
        self._queue_detail_label.setWordWrap(True)
        self._queue_start_button = QPushButton("Start", panel)
        self._queue_start_button.setObjectName("today-queue-start")
        self._queue_start_button.setProperty("variant", "primary")
        self._queue_start_button.setEnabled(False)
        self._queue_start_button.setToolTip(PENDING_MIGRATION_TOOLTIP)

        detail_row = QHBoxLayout()
        detail_row.setContentsMargins(0, 0, 0, 0)
        detail_row.setSpacing(METRICS.space_md)
        detail_row.addWidget(self._queue_detail_label, 1)
        detail_row.addWidget(self._queue_start_button)
        panel.body_layout().addLayout(detail_row)

        selection_model = self._queue_table.selectionModel()
        if selection_model is not None:
            selection_model.currentRowChanged.connect(self._on_queue_row_changed)

        return panel

    def _build_next_action_panel(self) -> Panel:
        panel = Panel("Suggested Next Action", parent=self)
        self._next_action_title = QLabel("", panel)
        self._next_action_title.setObjectName("today-next-action-title")
        self._next_action_title.setProperty("typography", "body")
        self._next_action_description = QLabel("", panel)
        self._next_action_description.setObjectName("today-next-action-description")
        self._next_action_description.setProperty("typography", "meta")
        self._next_action_description.setWordWrap(True)
        self._next_action_button = QPushButton("Go", panel)
        self._next_action_button.setObjectName("today-next-action-button")
        self._next_action_button.setProperty("variant", "primary")
        self._next_action_button.setEnabled(False)
        self._next_action_button.clicked.connect(self._on_next_action_clicked)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(METRICS.space_xs)
        text_column.addWidget(self._next_action_title)
        text_column.addWidget(self._next_action_description)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(METRICS.space_lg)
        row.addLayout(text_column, 1)
        row.addWidget(self._next_action_button)
        panel.body_layout().addLayout(row)
        return panel

    def _build_supporting_row(self) -> QHBoxLayout:
        top_left = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft

        self._recent_activity_panel = Panel("Recent Card Learning", parent=self)
        self._recent_activity_label = QLabel("", self._recent_activity_panel)
        self._recent_activity_label.setObjectName("today-recent-activity")
        self._recent_activity_label.setProperty("typography", "body")
        self._recent_activity_label.setWordWrap(True)
        self._recent_activity_label.setAlignment(top_left)
        self._recent_activity_panel.add_widget(self._recent_activity_label, 1)

        self._attention_panel = Panel("Collections Needing Attention", parent=self)
        self._attention_label = QLabel("", self._attention_panel)
        self._attention_label.setObjectName("today-attention")
        self._attention_label.setProperty("typography", "body")
        self._attention_label.setWordWrap(True)
        self._attention_label.setAlignment(top_left)
        self._attention_panel.add_widget(self._attention_label, 1)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(METRICS.space_md)
        row.addWidget(self._recent_activity_panel, 1)
        row.addWidget(self._attention_panel, 1)
        return row

    def _build_quick_actions_row(self) -> QHBoxLayout:
        self._entries_button = QPushButton("Open Entries", self)
        self._entries_button.setObjectName("today-quick-entries")
        self._entries_button.clicked.connect(self.entries_requested.emit)

        self._review_button = QPushButton("Review", self)
        self._review_button.setObjectName("today-quick-review")
        self._review_button.setEnabled(False)
        self._review_button.setToolTip(PENDING_MIGRATION_TOOLTIP)

        self._quiz_button = QPushButton("Quiz", self)
        self._quiz_button.setObjectName("today-quick-quiz")
        self._quiz_button.setEnabled(False)
        self._quiz_button.setToolTip(PENDING_MIGRATION_TOOLTIP)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(METRICS.space_sm)
        row.addWidget(SectionHeading("Quick Actions", self))
        row.addSpacing(METRICS.space_sm)
        row.addWidget(self._entries_button)
        row.addWidget(self._review_button)
        row.addWidget(self._quiz_button)
        row.addStretch(1)
        return row

    # --- rendering --------------------------------------------------------

    def _render_overview(self, overview: dict) -> None:
        workload = overview.get("study_workload") or {}
        quiz_activity = overview.get("quiz_activity") or {}
        review_activity = overview.get("review_activity") or {}
        accuracy = quiz_activity.get("accuracy")

        self._tiles["available_cards"].set_value(str(workload.get("total_cards", 0)))
        self._tiles["never_quizzed"].set_value(str(workload.get("never_quizzed_cards", 0)))
        quiz_items = quiz_activity.get("item_attempts", 0)
        self._tiles["quiz_items_today"].set_value(
            f"{quiz_items}" if accuracy is None else f"{quiz_items}  ({accuracy}%)"
        )
        self._tiles["card_learning_today"].set_value(str(review_activity.get("reviewed_cards", 0)))

        queue_items = self._controller.queue_items()
        self._queue_model.set_rows(queue_items)
        self._queue_stack.setCurrentWidget(
            self._queue_table if queue_items else self._queue_empty_state
        )
        self._queue_count_label.setText("" if not queue_items else f"{len(queue_items)} item(s)")
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
        # headed there. If a future checkpoint migrates one of these
        # destinations, this is the one place that needs to branch on
        # ``intent.action`` to actually enable Start.
        self._queue_start_button.setEnabled(False)
        if intent.action == "organize":
            self._queue_start_button.setToolTip(PENDING_ORGANIZE_TOOLTIP)
        else:
            self._queue_start_button.setToolTip(
                f"{PENDING_MIGRATION_TOOLTIP} (would start: {intent.action} / {intent.reason})"
            )

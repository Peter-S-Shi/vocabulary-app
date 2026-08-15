from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from src.ui_desktop.controllers.today_controller import TodayController

"""
Minimal Today/Home slice following the DESIGN.md § 4.1 Command Center
hierarchy at vertical-slice depth: a compact summary, the Learning Queue as
the visually dominant area, and the single primary recommendation. Full
Command Center polish (icons, richer supporting sections) is M17 work.
"""


class TodayView(QWidget):
    def __init__(self, controller: TodayController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        self._summary_label = QLabel("Loading Today overview...")
        self._summary_label.setObjectName("today-summary")

        self._queue_label = QLabel("Today's Learning Queue")
        self._queue_label.setObjectName("today-queue-heading")

        self._queue_table = QTableWidget(0, 3, self)
        self._queue_table.setHorizontalHeaderLabels(["Collection", "Card", "Status"])
        self._queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self._recommendation_label = QLabel("")
        self._recommendation_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._queue_label)
        layout.addWidget(self._queue_table, 1)
        layout.addWidget(self._recommendation_label)

        controller.overview_changed.connect(self._render_overview)

    def _render_overview(self, overview: dict) -> None:
        workload = overview.get("study_workload") or {}
        quiz_activity = overview.get("quiz_activity") or {}
        review_activity = overview.get("review_activity") or {}

        self._summary_label.setText(
            f"Available Cards: {workload.get('total_cards', 0)}   |   "
            f"Never Quizzed: {workload.get('never_quizzed_cards', 0)}   |   "
            f"Quiz Items Today: {quiz_activity.get('item_attempts', 0)}   |   "
            f"Card Learning Today: {review_activity.get('reviewed_cards', 0)}"
        )

        study_cards = overview.get("study_cards") or []
        self._queue_table.setRowCount(len(study_cards))
        for row, card in enumerate(study_cards):
            self._queue_table.setItem(row, 0, QTableWidgetItem(str(card.get("collection_name", ""))))
            self._queue_table.setItem(row, 1, QTableWidgetItem(str(card.get("card_number", ""))))
            self._queue_table.setItem(row, 2, QTableWidgetItem(str(card.get("status", ""))))

        recommendations = overview.get("recommendations") or []
        if recommendations:
            primary = recommendations[0]
            self._recommendation_label.setText(
                f"Recommended: {primary.get('title', '')} — {primary.get('description', '')}"
            )
        else:
            self._recommendation_label.setText("No recommendation is available yet.")

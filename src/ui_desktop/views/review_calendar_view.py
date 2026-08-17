from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.review_calendar_controller import DATE_RANGE_PRESETS, ReviewCalendarController
from src.ui_desktop.theming.metrics import SPACING

"""
Review Calendar / Card History (DESIGN.md § 7.3 "B, P7 Evidence
Browser"; § 8 P7: "primary evidence surface + secondary selected-item
detail"). Design Derivation Record per § 9, since DESIGN.md pins no
canonical mockup or exact rail placement for this surface:

  1. Interaction Mode        -> Management.
  2. Parent Pattern          -> P7 Evidence Browser. DESIGN.md groups
                                 "Review Calendar" and "Card History"
                                 together everywhere they appear (§ 4.1,
                                 § 7.3, § 8) rather than describing two
                                 independent screens; this implements
                                 them as one P7 composition -- the
                                 evidence list *is* the calendar, and
                                 "Card History" is what its secondary
                                 detail pane shows once a completion is
                                 selected -- rather than inventing a
                                 second top-level surface DESIGN.md never
                                 separately specifies.
  3. Primary User Task       -> browse when Cards were actually learned
                                 (completed Card-scoped Quiz, the
                                 authoritative completion event) and drill
                                 into one Card's full history.
  4. Spatial Composition     -> Management Rail -> compact range-preset
                                 control -> dominant chronological
                                 completions table (primary evidence) ->
                                 subordinate Card History detail (full
                                 completion history for the selected
                                 Card, plus a clearly separate, labeled
                                 legacy-compatibility Review log section)
                                 beneath it.
  5. Dominance Rule          -> the completions table dominates; detail
                                 explains the current selection and is
                                 never a second primary surface.
  6. Density Rule            -> inherits existing Management Mode density
                                 (matches Entries/Templates tables).
  7. Surface Hierarchy       -> table on `surface_primary`, matching
                                 Entries/Templates; unchanged detail
                                 vocabulary.
  8. Action Hierarchy        -> no destructive/mutating actions exist
                                 here at all (read-only evidence browsing,
                                 like the M17 Collections Navigator before
                                 M18.1 added writes) -- selection is the
                                 only interaction.
  9. Editing Container       -> none; purely a read surface.
 10. Navigation/Chrome       -> full Management shell retained.
 11. Motion/Transition       -> reuses the existing shared
                                 `TransitionManager.fade_in` on workspace
                                 switch, matching every other Management
                                 workspace; no new motion.
 12. Canonical Visual Rel.   -> table/detail vocabulary inherited from
                                 Entries/Templates rather than inventing a
                                 literal calendar-grid widget DESIGN.md
                                 never mocks up.
 13. Native Human Acceptance -> the real native Review Calendar / Card
                                 History workspace showing the
                                 completions table, a range-preset change,
                                 and a selected Card's full history
                                 (including its legacy-compatibility
                                 section) in Light and Dark Mode.

Read-only: this workspace never mutates SQLite, never revives legacy
due/interval/rating scheduling as active product truth (frozen semantic
boundary), and keeps Quiz-backed completion evidence visually distinct
from legacy Review compatibility records.
"""


class ReviewCalendarView(QWidget):
    def __init__(self, controller: ReviewCalendarController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("review-calendar-root")
        self._controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)
        layout.setSpacing(SPACING.md)

        toolbar = QHBoxLayout()
        title = QLabel("Review Calendar", self)
        title.setObjectName("review-calendar-title")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        range_label = QLabel("Range", self)
        range_label.setObjectName("review-calendar-range-label")
        toolbar.addWidget(range_label)
        self._range_combo = QComboBox(self)
        self._range_combo.setObjectName("review-calendar-range-combo")
        for label, days in DATE_RANGE_PRESETS:
            self._range_combo.addItem(label, days)
        self._range_combo.setCurrentIndex(1)  # "Last 30 days" default
        self._range_combo.currentIndexChanged.connect(self._on_range_changed)
        toolbar.addWidget(self._range_combo)
        layout.addLayout(toolbar)

        self._table = QTableWidget(self)
        self._table.setObjectName("review-calendar-table")
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Completed", "Collection", "Card", "Quiz Type", "Correct", "Wrong"])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self._table, 2)

        detail_heading = QLabel("Card History", self)
        detail_heading.setObjectName("review-calendar-detail-heading")
        layout.addWidget(detail_heading)

        self._detail_summary = QLabel("Select a completion above to see its Card's full history.", self)
        self._detail_summary.setObjectName("review-calendar-detail-summary")
        self._detail_summary.setWordWrap(True)
        layout.addWidget(self._detail_summary)

        self._history_table = QTableWidget(self)
        self._history_table.setObjectName("review-calendar-history-table")
        self._history_table.setColumnCount(4)
        self._history_table.setHorizontalHeaderLabels(["Completed", "Quiz Type", "Correct", "Wrong"])
        self._history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._history_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._history_table, 1)

        legacy_heading = QLabel("Legacy Review History (compatibility only)", self)
        legacy_heading.setObjectName("review-calendar-legacy-heading")
        layout.addWidget(legacy_heading)
        legacy_caption = QLabel(
            "These records came from the retired independent Review scheduler. "
            "They are not Quiz-backed Card learning completions.",
            self,
        )
        legacy_caption.setObjectName("review-calendar-legacy-caption")
        legacy_caption.setWordWrap(True)
        layout.addWidget(legacy_caption)

        self._legacy_table = QTableWidget(self)
        self._legacy_table.setObjectName("review-calendar-legacy-table")
        self._legacy_table.setColumnCount(3)
        self._legacy_table.setHorizontalHeaderLabels(["Reviewed", "Rating", "Entries"])
        self._legacy_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._legacy_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._legacy_table.verticalHeader().setVisible(False)
        self._legacy_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._legacy_table, 1)

        controller.entries_changed.connect(self._render_table)
        controller.selection_changed.connect(self._render_detail)

    def refresh(self) -> None:
        self._controller.refresh()

    def _render_table(self) -> None:
        entries = self._controller.entries
        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._table.setItem(row, 0, QTableWidgetItem(str(entry.get("completed_at") or "")))
            self._table.setItem(row, 1, QTableWidgetItem(str(entry.get("collection_name") or "")))
            self._table.setItem(row, 2, QTableWidgetItem(f"#{entry.get('card_number')}"))
            self._table.setItem(row, 3, QTableWidgetItem(str(entry.get("quiz_type") or "")))
            self._table.setItem(row, 4, QTableWidgetItem(str(int(entry.get("correct_count") or 0))))
            self._table.setItem(row, 5, QTableWidgetItem(str(int(entry.get("wrong_count") or 0))))
            item = self._table.item(row, 0)
            item.setData(Qt.ItemDataRole.UserRole, (int(entry["collection_id"]), int(entry["card_number"])))
            item.setData(Qt.ItemDataRole.UserRole + 1, str(entry.get("collection_name") or ""))
        if not entries:
            self._controller.clear_selection()

    def _on_range_changed(self, index: int) -> None:
        days = self._range_combo.itemData(index)
        if days is not None:
            self._controller.set_range_days(int(days))

    def _on_row_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        collection_id, card_number = item.data(Qt.ItemDataRole.UserRole)
        collection_name = item.data(Qt.ItemDataRole.UserRole + 1)
        self._controller.select_card(collection_id, card_number, collection_name)

    def _render_detail(self) -> None:
        controller = self._controller
        if controller.selected_collection_id is None:
            self._detail_summary.setText("Select a completion above to see its Card's full history.")
            self._history_table.setRowCount(0)
            self._legacy_table.setRowCount(0)
            return

        self._detail_summary.setText(
            f"{controller.selected_collection_name} — Card #{controller.selected_card_number}"
        )

        history = controller.card_history
        self._history_table.setRowCount(len(history))
        for row, entry in enumerate(history):
            self._history_table.setItem(row, 0, QTableWidgetItem(str(entry.get("completed_at") or "")))
            self._history_table.setItem(row, 1, QTableWidgetItem(str(entry.get("quiz_type") or "")))
            self._history_table.setItem(row, 2, QTableWidgetItem(str(int(entry.get("correct_count") or 0))))
            self._history_table.setItem(row, 3, QTableWidgetItem(str(int(entry.get("wrong_count") or 0))))

        legacy_logs = controller.legacy_logs
        self._legacy_table.setRowCount(len(legacy_logs))
        for row, log in enumerate(legacy_logs):
            self._legacy_table.setItem(row, 0, QTableWidgetItem(str(log.get("reviewed_at") or "")))
            self._legacy_table.setItem(row, 1, QTableWidgetItem(str(log.get("rating") or "")))
            self._legacy_table.setItem(row, 2, QTableWidgetItem(str(log.get("entry_count") or "")))

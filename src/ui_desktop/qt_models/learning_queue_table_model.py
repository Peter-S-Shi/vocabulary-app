from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

"""
QAbstractTableModel adapter wrapping the prioritized action dicts returned
by src.learning_workflow.get_daily_quiz_candidates() (surfaced as
``daily_quiz_recommendations`` in get_today_overview()). This is the
dominant Today / Command Center surface (DESIGN.md § 4.1); like
EntriesTableModel, it is a desktop-specific view adapter with no business
logic and no SQL.
"""


class LearningQueueTableModel(QAbstractTableModel):
    COLUMNS: tuple[str, ...] = ("title", "description", "entry_count", "status")
    HEADERS: tuple[str, ...] = ("Action", "Detail", "Entries", "Status")

    def __init__(self, rows: list[dict] | None = None) -> None:
        super().__init__()
        self._rows: list[dict] = list(rows) if rows else []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt API)
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt API)
        return 0 if parent.isValid() else len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        row = self._rows[index.row()]
        key = self.COLUMNS[index.column()]
        if key == "status":
            return "Ready" if row.get("enabled") else "Needs setup"
        return str(row.get(key, "") or "")

    def headerData(  # noqa: N802 (Qt API)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return self.HEADERS[section]

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

"""
QAbstractTableModel adapter wrapping the plain dict rows returned by
src.entries.search_entries(). This is a desktop-specific view adapter, not
a domain model: it holds no business logic and performs no SQL (M16.1
contract § 8/§ 9).
"""


class EntriesTableModel(QAbstractTableModel):
    COLUMNS: tuple[str, ...] = ("term", "meaning", "language", "entry_type", "status", "updated_at")
    HEADERS: tuple[str, ...] = ("Term", "Meaning", "Language", "Type", "Status", "Updated")

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

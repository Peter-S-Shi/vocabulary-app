from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

"""
QAbstractTableModel adapter wrapping the plain dict rows returned by
src.entries.search_entries()/get_entries_in_collection() (each row
additionally carries a ``collection_names`` list the controller attaches
before calling set_rows() -- see EntriesController.refresh()). This is a
desktop-specific view adapter, not a domain model: it holds no business
logic and performs no SQL (M16.1 contract § 8/§ 9).

M17 Feature 4 (VR-ENTRIES-001 Table-First): "Last reviewed" from the
canonical mockup does not correspond to any real column current core
exposes (M11.4 retired the legacy SRS due-date concept in favor of Quiz
evidence); "Updated" (``updated_at``) is shown instead as the honest
timestamp current product truth actually has, matching the "current
product truth controls semantics" principle already established for
Review/Quiz. Status shows the real ``entries.status`` values
(new/learning/familiar/mastered), not the mockup's fictional
Due/Reviewed/Stale/Mistake review-state badges.
"""


class EntriesTableModel(QAbstractTableModel):
    COLUMNS: tuple[str, ...] = ("term", "language", "entry_type", "template_name", "collections", "status", "updated_at")
    HEADERS: tuple[str, ...] = ("Term", "Language", "Type", "Template", "Collections", "Status", "Updated")

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

    def rows(self) -> list[dict]:
        return list(self._rows)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt API)
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt API)
        return 0 if parent.isValid() else len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        row = self._rows[index.row()]
        key = self.COLUMNS[index.column()]
        if key == "collections":
            names = row.get("collection_names") or []
            return ", ".join(names)
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

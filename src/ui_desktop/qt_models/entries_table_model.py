from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal

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

M17 Feature 4 corrective pass (§ 7): a leading checkbox column makes the
existing native ``ExtendedSelection`` explicitly visible, per
`VR-ENTRIES-001`'s checkbox affordance. The model only *renders* the
checkbox against the selected-id set the view hands it via
``set_selected_ids`` -- ``EntriesController.selected_ids`` stays the
single selection truth; the model never owns selection state, it only
mirrors it for CheckStateRole painting and reports user toggles back
through ``checkbox_toggled`` so the view can fold them into that same
truth.
"""


class EntriesTableModel(QAbstractTableModel):
    SELECT_COLUMN = "select"
    COLUMNS: tuple[str, ...] = (SELECT_COLUMN, "term", "language", "entry_type", "template_name", "collections", "status", "updated_at")
    HEADERS: tuple[str, ...] = ("", "Term", "Language", "Type", "Template", "Collections", "Status", "Updated")

    checkbox_toggled = Signal(int, bool)

    def __init__(self, rows: list[dict] | None = None) -> None:
        super().__init__()
        self._rows: list[dict] = list(rows) if rows else []
        self._selected_ids: set[int] = set()

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def set_selected_ids(self, ids: set[int]) -> None:
        self._selected_ids = set(ids)
        if self._rows:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._rows) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])

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

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa: N802 (Qt API)
        base = super().flags(index)
        if not index.isValid():
            return base
        if self.COLUMNS[index.column()] == self.SELECT_COLUMN:
            return base | Qt.ItemFlag.ItemIsUserCheckable
        return base

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = self.COLUMNS[index.column()]
        if key == self.SELECT_COLUMN:
            if role == Qt.ItemDataRole.CheckStateRole:
                checked = int(row.get("id")) in self._selected_ids
                return Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            return None
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        if key == "collections":
            names = row.get("collection_names") or []
            return ", ".join(names)
        return str(row.get(key, "") or "")

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802 (Qt API)
        if not index.isValid() or role != Qt.ItemDataRole.CheckStateRole:
            return False
        if self.COLUMNS[index.column()] != self.SELECT_COLUMN:
            return False
        row = self._rows[index.row()]
        entry_id = int(row["id"])
        checked = value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked
        self.checkbox_toggled.emit(entry_id, bool(checked))
        return True

    def headerData(  # noqa: N802 (Qt API)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return self.HEADERS[section]

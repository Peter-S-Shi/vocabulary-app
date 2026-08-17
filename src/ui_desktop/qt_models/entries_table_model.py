from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor

"""
QAbstractTableModel adapter wrapping the plain dict rows returned by
src.entries.search_entries()/get_entries_in_collection() (each row
additionally carries a ``collection_names`` list and a ``starred`` flag
the controller attaches before calling set_rows() -- see
EntriesController.refresh()). This is a desktop-specific view adapter,
not a domain model: it holds no business logic and performs no SQL
(M16.1 contract § 8/§ 9).

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
checkbox against the checked-id set the view hands it via
``set_checked_ids`` -- ``EntriesController.checked_ids`` stays the single
batch-selection truth; the model never owns it, it only mirrors it for
CheckStateRole painting and reports user toggles back through
``checkbox_toggled`` so the view can fold them into that same truth.

M17 Minimum Collection Integration corrective pass (§ 5-9): the checkbox
column's ``checked_ids`` is deliberately kept a separate concept from
``focused_id`` (the single row currently shown in the bottom detail
pane, set by a plain row click/current-index change, never by a
checkbox). Both are pure presentation mirrors the view keeps in sync
with the controller's two independent truths -- neither is derived from
the other. A leading Star column (``STAR_COLUMN``) gives each row a
direct, persisted Starred toggle (``row["starred"]``) painted via a
fixed semantic gold when filled; the model has no theme-token access
(models stay theme-agnostic per the M16.1 layering), so this is one
fixed accent rather than a full palette resolution, chosen to read
legibly on both Light and Dark surfaces.
"""


class EntriesTableModel(QAbstractTableModel):
    SELECT_COLUMN = "select"
    STAR_COLUMN = "star"
    COLUMNS: tuple[str, ...] = (
        SELECT_COLUMN,
        STAR_COLUMN,
        "term",
        "language",
        "entry_type",
        "template_name",
        "collections",
        "status",
        "updated_at",
    )
    HEADERS: tuple[str, ...] = ("", "★", "Term", "Language", "Type", "Template", "Collections", "Status", "Updated")

    STAR_FILLED_COLOR = QColor("#C9972E")
    FOCUSED_ROW_TINT = QColor(62, 102, 144, 40)

    checkbox_toggled = Signal(int, bool)

    def __init__(self, rows: list[dict] | None = None) -> None:
        super().__init__()
        self._rows: list[dict] = list(rows) if rows else []
        self._checked_ids: set[int] = set()
        self._focused_id: int | None = None

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def set_checked_ids(self, ids: set[int]) -> None:
        self._checked_ids = set(ids)
        if self._rows:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._rows) - 1, len(self.COLUMNS) - 1)
            self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole, Qt.ItemDataRole.BackgroundRole])

    def set_focused_id(self, entry_id: int | None) -> None:
        if entry_id == self._focused_id:
            return
        previous_id = self._focused_id
        self._focused_id = entry_id
        self._emit_row_changed(previous_id)
        self._emit_row_changed(entry_id)

    def _emit_row_changed(self, entry_id: int | None) -> None:
        if entry_id is None:
            return
        row = next((i for i, r in enumerate(self._rows) if r.get("id") == entry_id), None)
        if row is not None:
            self.dataChanged.emit(self.index(row, 0), self.index(row, len(self.COLUMNS) - 1), [Qt.ItemDataRole.BackgroundRole])

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
        entry_id = row.get("id")

        if key == self.SELECT_COLUMN:
            if role == Qt.ItemDataRole.CheckStateRole:
                checked = int(entry_id) in self._checked_ids
                return Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            return None

        if key == self.STAR_COLUMN:
            starred = bool(row.get("starred"))
            if role == Qt.ItemDataRole.DisplayRole:
                return "★" if starred else "☆"
            if role == Qt.ItemDataRole.ToolTipRole:
                return "Remove from Starred" if starred else "Add to Starred"
            if role == Qt.ItemDataRole.ForegroundRole:
                return self.STAR_FILLED_COLOR if starred else None
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(Qt.AlignmentFlag.AlignCenter)
            return None

        if role == Qt.ItemDataRole.BackgroundRole:
            if entry_id is not None and int(entry_id) == self._focused_id and int(entry_id) not in self._checked_ids:
                return self.FOCUSED_ROW_TINT
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

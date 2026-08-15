from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.entries import search_entries
from src.ui_desktop.qt_models.entries_table_model import EntriesTableModel

"""
EntriesController owns the Entries workspace's transient filter/selection
state and calls src.entries.search_entries() directly -- a direct
controller-to-core call is sufficient here (M16.1 contract § 10); no
ui_desktop/services/ orchestration is needed for a single reusable query.
"""


class EntriesController(QObject):
    rows_changed = Signal(int)
    selection_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.model = EntriesTableModel()
        self.search_text = ""
        self.language = "All"
        self.entry_type = "All"
        self.status = "All"
        self.selected_entry: dict | None = None

    def refresh(self) -> int:
        rows = search_entries(
            search_text=self.search_text,
            language=self.language,
            entry_type=self.entry_type,
            status=self.status,
        )
        self.model.set_rows(rows)
        self.selected_entry = None
        self.selection_changed.emit(None)
        self.rows_changed.emit(len(rows))
        return len(rows)

    def set_search_text(self, text: str) -> int:
        self.search_text = text
        return self.refresh()

    def select_row(self, row: int) -> dict | None:
        entry = self.model.row_at(row)
        self.selected_entry = entry
        self.selection_changed.emit(entry)
        return entry

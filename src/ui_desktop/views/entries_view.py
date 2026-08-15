from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.entries_controller import EntriesController

"""
Minimal Entries/Table-First slice: a dense QTableView as the dominant
surface over src.entries.search_entries() results, a basic search box, and
a bottom detail label. Editing, batch actions, and full Collection
integration are out of scope for M16.2 (DESIGN.md § 4.2 describes the full
target; this proves the architecture, not feature parity).
"""


class EntriesView(QWidget):
    def __init__(self, controller: EntriesController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText("Search term, meaning, tags...")
        self._search_input.returnPressed.connect(self._on_search_submitted)

        self._table = QTableView(self)
        self._table.setModel(controller.model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._detail_label = QLabel("Select a row to see details.", self)
        self._detail_label.setWordWrap(True)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:", self))
        search_row.addWidget(self._search_input)

        layout = QVBoxLayout(self)
        layout.addLayout(search_row)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._detail_label)

        selection_model = self._table.selectionModel()
        if selection_model is not None:
            selection_model.currentRowChanged.connect(self._on_current_row_changed)

        controller.rows_changed.connect(self._on_rows_changed)

    def _on_search_submitted(self) -> None:
        self._controller.set_search_text(self._search_input.text())

    def _on_rows_changed(self, count: int) -> None:
        self._detail_label.setText(f"{count} entries. Select a row to see details.")

    def _on_current_row_changed(self, current, _previous) -> None:
        row = current.row() if current.isValid() else -1
        entry = self._controller.select_row(row)
        if entry:
            self._detail_label.setText(f"{entry.get('term', '')} — {entry.get('meaning', '')}")
        else:
            self._detail_label.setText("Select a row to see details.")

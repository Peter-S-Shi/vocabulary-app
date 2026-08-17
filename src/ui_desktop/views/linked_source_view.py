from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.linked_sources import LinkedSourceError
from src.ui_desktop.controllers.linked_source_controller import IMPORT_MODE_LABELS, LinkedSourceController

"""
Linked Source (DESIGN.md § 7.4 "Linked Source setup/status: B, P6 within
Collection context"; "Linked Source Refresh Preview: B, VR-UTILITY-001").
Design Derivation Record per § 9 -- DESIGN.md pins no canonical mockup
for this workflow and there is no Streamlit precedent at all (M13 closed
the reusable core only):

  1. Interaction Mode        -> Utility/Dialog, launched from within the
                                 Collection Manager (Management Mode) --
                                 "within Collection context" per DESIGN.
  2. Parent Pattern          -> P6 Utility Workflow /
                                 `VR-UTILITY-001` Upload -> Validate ->
                                 Preview -> Confirm, the same grammar
                                 Data Tools' `_ImportDialog` already
                                 established this milestone.
  3. Primary User Task       -> link a Collection to a local CSV/XLSX
                                 append-only source, or refresh/unlink an
                                 already-linked one.
  4. Spatial Composition     -> status/setup section (current link, or a
                                 file/mode picker if unlinked) -> Preview
                                 action -> preview results (new-valid/
                                 invalid/duplicate summary + tables) ->
                                 confirmation + Confirm action -> Unlink
                                 as a separate, clearly secondary action.
  5. Dominance Rule          -> preview results dominate once a preview
                                 has run; the status/setup section stays
                                 visible above for context, never hidden.
  6. Density Rule            -> inherits existing Management Mode
                                 density (matches Data Tools' dialogs).
  7. Surface Hierarchy       -> identical modal surface treatment to
                                 every other M18 P6 dialog.
  8. Action Hierarchy        -> primary = Preview / Confirm (accent);
                                 secondary = Choose File; Unlink is
                                 metadata-only removal (Collection/
                                 Entries are never touched) so it is an
                                 outlined confirmation action, not the
                                 full destructive-red treatment reserved
                                 for actions that delete user content.
  9. Editing Container       -> one P6 dialog, matching `_ImportDialog`'s
                                 "keep list/status context visible while
                                 acting" precedent rather than a wizard
                                 with separate pages.
 10. Navigation/Chrome       -> unchanged Management shell behind it;
                                 modal overlay, no chrome swap.
 11. Motion/Transition       -> none new.
 12. Canonical Visual Rel.   -> inherits `_ImportDialog`'s P6 grammar
                                 (file/mode controls, preview tables,
                                 confirmation checkbox + primary Confirm
                                 button).
 13. Native Human Acceptance -> the real native dialog showing an initial
                                 link (General Entry mode), a refresh of
                                 an already-linked source, and the
                                 missing/unreadable-source recovery path
                                 (Unlink -> choose a new file -> Preview
                                 -> Confirm) leaving the Collection and
                                 its existing Entries untouched, in Light
                                 and Dark Mode.

A missing/unreadable linked file must not damage existing Collection/
Entry data (DESIGN.md § 12.3) -- `preview_collection_source_link`/
`preview_linked_source_refresh` report a controlled error
(`can_confirm=False`) rather than raising, and this dialog surfaces it
inline; recovery is Unlink (metadata only) then a fresh link to a new
path, since no core function invents a "replace path in place" shortcut.
"""


class LinkedSourceDialog(QDialog):
    def __init__(self, controller: LinkedSourceController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("linked-source-dialog")
        self.setMinimumSize(560, 560)
        self._controller = controller

        layout = QVBoxLayout(self)

        self._status_label = QLabel("", self)
        self._status_label.setObjectName("linked-source-status-label")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        setup_form = QFormLayout()
        file_row = QHBoxLayout()
        self._file_label = QLabel("No file selected.", self)
        file_row.addWidget(self._file_label, 1)
        self._choose_button = QPushButton("Choose File…", self)
        self._choose_button.setObjectName("linked-source-choose-file-button")
        self._choose_button.clicked.connect(self._on_choose_file)
        file_row.addWidget(self._choose_button, 0)
        setup_form.addRow("Source file", file_row)

        self._mode_combo = QComboBox(self)
        for value, label in IMPORT_MODE_LABELS:
            self._mode_combo.addItem(label, value)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._mode_row_label = QLabel("Import mode", self)
        setup_form.addRow(self._mode_row_label, self._mode_combo)

        self._sheet_combo = QComboBox(self)
        self._sheet_combo.currentIndexChanged.connect(self._on_sheet_changed)
        self._sheet_row_label = QLabel("Worksheet", self)
        setup_form.addRow(self._sheet_row_label, self._sheet_combo)
        layout.addLayout(setup_form)

        preview_row = QHBoxLayout()
        preview_row.addStretch(1)
        self._preview_button = QPushButton("Preview", self)
        self._preview_button.setObjectName("linked-source-preview-button")
        self._preview_button.clicked.connect(self._on_preview)
        preview_row.addWidget(self._preview_button)
        layout.addLayout(preview_row)

        self._preview_error_label = QLabel("", self)
        self._preview_error_label.setObjectName("data-tools-preview-error")
        self._preview_error_label.setWordWrap(True)
        layout.addWidget(self._preview_error_label)

        self._summary_label = QLabel("", self)
        self._summary_label.setObjectName("data-tools-summary-label")
        layout.addWidget(self._summary_label)

        new_heading = QLabel("New Valid Rows", self)
        new_heading.setObjectName("data-tools-section-heading")
        layout.addWidget(new_heading)
        self._new_table = QTableWidget(self)
        self._new_table.setObjectName("linked-source-new-table")
        self._new_table.setColumnCount(3)
        self._new_table.setHorizontalHeaderLabels(["Row", "Term", "Meaning"])
        self._new_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._new_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._new_table.verticalHeader().setVisible(False)
        self._new_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._new_table.setMaximumHeight(160)
        layout.addWidget(self._new_table)

        self._confirm_checkbox = QCheckBox("", self)
        self._confirm_checkbox.toggled.connect(self._update_confirm_enabled)
        layout.addWidget(self._confirm_checkbox)

        action_row = QHBoxLayout()
        self._unlink_button = QPushButton("Unlink", self)
        self._unlink_button.setObjectName("linked-source-unlink-button")
        self._unlink_button.clicked.connect(self._on_unlink)
        action_row.addWidget(self._unlink_button)
        action_row.addStretch(1)
        self._confirm_button = QPushButton("Confirm", self)
        self._confirm_button.setObjectName("linked-source-confirm-button")
        self._confirm_button.setEnabled(False)
        self._confirm_button.clicked.connect(self._on_confirm)
        action_row.addWidget(self._confirm_button)
        layout.addLayout(action_row)

        self._result_label = QLabel("", self)
        self._result_label.setObjectName("data-tools-result-label")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        layout.addStretch(1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

        controller.state_changed.connect(self._reload)
        self._reload()

    # -- actions -----------------------------------------------------------

    def _on_choose_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Choose a CSV or XLSX source file", "", "CSV/XLSX Files (*.csv *.xlsx)")
        if not path:
            return
        self._controller.stage_source_path(path)

    def _on_mode_changed(self, index: int) -> None:
        value = self._mode_combo.itemData(index)
        if value is not None:
            self._controller.set_staged_import_mode(value)

    def _on_sheet_changed(self, index: int) -> None:
        value = self._sheet_combo.itemData(index)
        if value is not None:
            self._controller.set_staged_sheet(value)

    def _on_preview(self) -> None:
        if self._controller.link is None and not self._controller.staged_source_path:
            self._preview_error_label.setText("Choose a file first.")
            return
        self._controller.run_preview()

    def _on_confirm(self) -> None:
        try:
            self._controller.confirm()
        except LinkedSourceError as error:
            self._result_label.setText(str(error))

    def _on_unlink(self) -> None:
        confirmed = QMessageBox.question(
            self,
            "Unlink Source",
            "Unlink this source? This only removes the link; the Collection and its "
            "existing Entries are not changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._controller.unlink()

    # -- reload ----------------------------------------------------------

    def _reload(self) -> None:
        controller = self._controller
        is_linked = controller.link is not None

        if is_linked:
            link = controller.link
            self._status_label.setText(
                f"Linked to {link['source_path']} ({link['source_type']}, {link['import_mode']}). "
                f"Linked {link['linked_at']}. Last refreshed: {link['last_refreshed_at'] or 'never'}."
            )
        else:
            self._status_label.setText("This Collection has no linked source yet.")

        # Setup controls (Choose File / mode / sheet) only apply while
        # staging a brand-new link; an existing link is refreshed as-is
        # from its stored path (Unlink first to point at a different file).
        self._file_label.setVisible(not is_linked)
        self._choose_button.setVisible(not is_linked)
        self._mode_row_label.setVisible(not is_linked)
        self._mode_combo.setVisible(not is_linked)
        self._unlink_button.setVisible(is_linked)
        self._preview_button.setText("Refresh Preview" if is_linked else "Preview")

        if not is_linked:
            self._file_label.setText(controller.staged_source_path or "No file selected.")

        has_multiple_sheets = len(controller.sheet_names) > 1
        self._sheet_row_label.setVisible(has_multiple_sheets and not is_linked)
        self._sheet_combo.setVisible(has_multiple_sheets and not is_linked)
        if has_multiple_sheets and not is_linked:
            self._sheet_combo.blockSignals(True)
            self._sheet_combo.clear()
            for sheet_name in controller.sheet_names:
                self._sheet_combo.addItem(sheet_name, sheet_name)
            index = self._sheet_combo.findData(controller.staged_sheet_name)
            if index >= 0:
                self._sheet_combo.setCurrentIndex(index)
            self._sheet_combo.blockSignals(False)

        self._confirm_checkbox.setChecked(False)
        self._confirm_checkbox.setText(
            "I understand this will refresh the linked source and append new Entries."
            if is_linked
            else "I understand this will link this file and append its new Entries."
        )

        preview = controller.preview
        if preview is None:
            self._preview_error_label.setText("")
            self._summary_label.setText("")
            self._new_table.setRowCount(0)
        elif not preview.get("ok", True):
            self._preview_error_label.setText("; ".join(preview.get("errors") or []))
            self._summary_label.setText("")
            self._new_table.setRowCount(0)
        else:
            self._preview_error_label.setText("")
            summary = preview["summary"]
            self._summary_label.setText(
                f"New valid {summary['new_valid_count']} · Invalid {summary['invalid_count']} · "
                f"Duplicate {summary['duplicate_count']} · Total {summary['total_rows']}"
            )
            new_rows = preview["new_valid_rows"]
            self._new_table.setRowCount(len(new_rows))
            for row, entry in enumerate(new_rows):
                data = entry.get("data", {})
                self._new_table.setItem(row, 0, QTableWidgetItem(str(entry.get("row_number"))))
                self._new_table.setItem(row, 1, QTableWidgetItem(str(data.get("resolved_term") or "")))
                self._new_table.setItem(row, 2, QTableWidgetItem(str(data.get("resolved_meaning") or "")))

        if controller.result is not None:
            result = controller.result
            if result.get("success"):
                self._result_label.setText(f"Done. Imported {result.get('imported_count', 0)} new Entries.")
            else:
                self._result_label.setText("; ".join(result.get("errors") or ["Could not complete this action."]))
        else:
            self._result_label.setText("")

        self._update_confirm_enabled()

    def _update_confirm_enabled(self) -> None:
        self._confirm_button.setEnabled(self._controller.can_confirm() and self._confirm_checkbox.isChecked())

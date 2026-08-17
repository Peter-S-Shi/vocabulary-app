from __future__ import annotations

import os

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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.template_definitions import TemplateDefinitionError
from src.ui_desktop.controllers.data_tools_controller import (
    EXPORT_SCOPE_LABELS,
    IMPORT_MODE_LABELS,
    DataToolsController,
)
from src.ui_desktop.theming.metrics import SPACING

"""
Data Tools (DESIGN.md § 7.4 "Data Tools hub: B, P6 Utility Workflow";
"Import Preview: B, VR-UTILITY-001: Validate -> Preview -> Confirm").
Design Derivation Record per § 9 (VR-UTILITY-001 is a PATTERN board, not
a fixed per-screen CANONICAL mockup, so the exact local composition is
resolved here against its textual grammar, DESIGN.md § 12):

  1. Interaction Mode        -> Utility/Dialog, launched from Management
                                 (§ 4.3: "belongs to and returns to its
                                 parent workflow" -- no new nav shell).
  2. Parent Pattern          -> P6 Utility Workflow. Import follows § 12.3
                                 verbatim: Upload -> Validate -> Preview
                                 -> Confirm -> Import, never collapsed
                                 into one opaque action.
  3. Primary User Task       -> import validated CSV/XLSX rows (General
                                 Entry / Template-Based / Collection/Card)
                                 after an explicit preview; export
                                 existing data to CSV/XLSX.
  4. Spatial Composition     -> Management Rail -> Data Tools hub (two
                                 actions: Import, Export) -> each opens
                                 its own focused P6 dialog. `_ImportDialog`
                                 stacks, top to bottom: file/mode
                                 controls -> Preview action -> preview
                                 results (summary + valid/invalid tables)
                                 -> duplicate-handling + destination
                                 controls -> confirmation + Confirm
                                 action -> result. `_ExportDialog`:
                                 scope/format controls -> Export action
                                 (native Save dialog) -> result.
  5. Dominance Rule          -> the current step's controls/results
                                 dominate; earlier steps remain visible
                                 above (not hidden), matching § 12.3
                                 "preview must look and behave
                                 differently from committed state" --
                                 result replaces preview, never merges
                                 with it.
  6. Density Rule            -> inherits Management Mode density (matches
                                 Entries/Templates tables).
  7. Surface Hierarchy       -> table/detail vocabulary inherited from
                                 Entries/Templates; dialogs use the same
                                 modal surface treatment as
                                 `_EntryEditorDialog`/`_TemplateEditorDialog`.
  8. Action Hierarchy        -> primary = Preview / Confirm Import /
                                 Export (accent-primary, bottom-right per
                                 § 12.1); Cancel/Close always present and
                                 easy to find; no destructive action
                                 exists in this checkpoint (Import only
                                 ever creates rows; it never deletes or
                                 overwrites -- matching the frozen "no
                                 overwrite" duplicate-handling contract:
                                 skip or import-anyway, never a merge).
  9. Editing Container       -> both workflows are P6 independent focused
                                 dialogs (large, roomy -- matching
                                 `_TemplateEditorDialog`'s "independent
                                 focused workspace" precedent) rather than
                                 inline Data Tools hub controls, since
                                 file-based import/export is a meaningful
                                 multi-step task in its own right.
 10. Navigation/Chrome       -> unchanged Management shell behind the
                                 hub; dialogs are modal overlays.
 11. Motion/Transition       -> unchanged `TransitionManager.fade_in` on
                                 workspace switch into the hub; no new
                                 motion for dialogs.
 12. Canonical Visual Rel.   -> inherits `_TemplateEditorDialog`'s P5/P6
                                 grammar (scrollable body, pinned
                                 action footer) as the closest existing
                                 large-focused-dialog precedent; no
                                 canonical VR-UTILITY-001 pixel mockup is
                                 required since it is a PATTERN board, not
                                 a CANONICAL per-screen contract (§ 7.1).
 13. Native Human Acceptance -> the real native Data Tools hub, a General
                                 Entry import (upload -> preview -> skip/
                                 import-anyway duplicate choice -> confirm
                                 -> result), a Collection import creating
                                 a new Collection, and an Export (All
                                 entries, CSV and XLSX) actually writing a
                                 readable file to disk, in Light and Dark
                                 Mode.

Import never mutates SQLite before Confirm (`DataToolsController.
run_preview()` only calls read-only `build_import_preview`); Confirm
dispatches to the exact same writer the Streamlit page's confirm step
uses per mode (general_entry -> `import_general_entry_rows`,
template_aware -> `import_template_entry_rows`, collection ->
`import_collection_rows`) -- no second import engine, no SQL in this
view/controller.
"""


class DataToolsView(QWidget):
    def __init__(self, controller: DataToolsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("data-tools-root")
        self._controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)
        layout.setSpacing(SPACING.md)

        title = QLabel("Data Tools", self)
        title.setObjectName("data-tools-title")
        layout.addWidget(title)

        caption = QLabel(
            "Import validated CSV/XLSX rows or export your existing data. "
            "Imports always show a preview before anything is written.",
            self,
        )
        caption.setObjectName("data-tools-caption")
        caption.setWordWrap(True)
        layout.addWidget(caption)

        actions = QHBoxLayout()
        import_button = QPushButton("Import…", self)
        import_button.setObjectName("data-tools-import-button")
        import_button.clicked.connect(self._on_import)
        actions.addWidget(import_button)

        export_button = QPushButton("Export…", self)
        export_button.setObjectName("data-tools-export-button")
        export_button.clicked.connect(self._on_export)
        actions.addWidget(export_button)

        template_definition_button = QPushButton("Template Definitions…", self)
        template_definition_button.setObjectName("data-tools-template-definition-button")
        template_definition_button.clicked.connect(self._on_template_definitions)
        actions.addWidget(template_definition_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)

    def refresh(self) -> None:
        pass

    def _on_import(self) -> None:
        self._controller.reset_import()
        dialog = _ImportDialog(self._controller, parent=self)
        dialog.exec()

    def _on_export(self) -> None:
        dialog = _ExportDialog(self._controller, parent=self)
        dialog.exec()

    def _on_template_definitions(self) -> None:
        self._controller.reset_template_definition_import()
        dialog = _TemplateDefinitionDialog(self._controller, parent=self)
        dialog.exec()


class _ImportDialog(QDialog):
    """P6 Import workflow (DESIGN.md § 12.3 "Upload -> Validate ->
    Preview -> Confirm -> Import")."""

    def __init__(self, controller: DataToolsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("data-tools-import-dialog")
        self.setWindowTitle("Import")
        self.setMinimumSize(640, 620)
        self._controller = controller

        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setSpacing(SPACING.md)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # -- Upload -------------------------------------------------
        upload_form = QFormLayout()
        self._mode_combo = QComboBox(self)
        for value, label in IMPORT_MODE_LABELS:
            self._mode_combo.addItem(label, value)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        upload_form.addRow("Import mode", self._mode_combo)

        file_row = QHBoxLayout()
        self._file_label = QLabel("No file selected.", self)
        file_row.addWidget(self._file_label, 1)
        choose_button = QPushButton("Choose File…", self)
        choose_button.setObjectName("data-tools-choose-file-button")
        choose_button.clicked.connect(self._on_choose_file)
        file_row.addWidget(choose_button, 0)
        upload_form.addRow("File", file_row)

        self._sheet_combo = QComboBox(self)
        self._sheet_combo.currentIndexChanged.connect(self._on_sheet_changed)
        self._sheet_row_label = QLabel("Worksheet", self)
        upload_form.addRow(self._sheet_row_label, self._sheet_combo)
        layout.addLayout(upload_form)

        preview_row = QHBoxLayout()
        preview_row.addStretch(1)
        self._preview_button = QPushButton("Preview Import", self)
        self._preview_button.setObjectName("data-tools-preview-button")
        self._preview_button.clicked.connect(self._on_preview)
        preview_row.addWidget(self._preview_button)
        layout.addLayout(preview_row)

        # -- Preview results ------------------------------------------
        self._preview_error_label = QLabel("", self)
        self._preview_error_label.setObjectName("data-tools-preview-error")
        self._preview_error_label.setWordWrap(True)
        layout.addWidget(self._preview_error_label)

        self._summary_label = QLabel("", self)
        self._summary_label.setObjectName("data-tools-summary-label")
        layout.addWidget(self._summary_label)

        valid_heading = QLabel("Valid Rows", self)
        valid_heading.setObjectName("data-tools-section-heading")
        layout.addWidget(valid_heading)
        self._valid_table = QTableWidget(self)
        self._valid_table.setObjectName("data-tools-valid-table")
        self._valid_table.setColumnCount(4)
        self._valid_table.setHorizontalHeaderLabels(["Row", "Term", "Meaning", "Language"])
        self._valid_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._valid_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._valid_table.verticalHeader().setVisible(False)
        self._valid_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._valid_table.setMaximumHeight(160)
        layout.addWidget(self._valid_table)

        invalid_heading = QLabel("Invalid Rows", self)
        invalid_heading.setObjectName("data-tools-section-heading")
        layout.addWidget(invalid_heading)
        self._invalid_table = QTableWidget(self)
        self._invalid_table.setObjectName("data-tools-invalid-table")
        self._invalid_table.setColumnCount(2)
        self._invalid_table.setHorizontalHeaderLabels(["Row", "Errors"])
        self._invalid_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._invalid_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._invalid_table.verticalHeader().setVisible(False)
        self._invalid_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._invalid_table.setMaximumHeight(140)
        layout.addWidget(self._invalid_table)

        # -- Duplicate handling + destination --------------------------
        options_form = QFormLayout()
        self._duplicate_combo = QComboBox(self)
        self._duplicate_combo.addItem("Skip duplicates", "skip")
        self._duplicate_combo.addItem("Import anyway", "import_anyway")
        self._duplicate_combo.currentIndexChanged.connect(self._on_duplicate_changed)
        options_form.addRow("Duplicate handling", self._duplicate_combo)

        self._target_collection_combo = QComboBox(self)
        self._target_collection_combo.currentIndexChanged.connect(self._on_target_collection_changed)
        self._target_collection_label = QLabel("Add to Collection", self)
        options_form.addRow(self._target_collection_label, self._target_collection_combo)

        self._collection_mode_combo = QComboBox(self)
        self._collection_mode_combo.addItem("Append to existing Collection", "append_to_existing")
        self._collection_mode_combo.addItem("Create new Collection", "create_new_collection")
        self._collection_mode_combo.currentIndexChanged.connect(self._on_collection_mode_changed)
        self._collection_mode_label = QLabel("Destination", self)
        options_form.addRow(self._collection_mode_label, self._collection_mode_combo)

        self._new_name_input = QLineEdit(self)
        self._new_name_input.textChanged.connect(self._on_new_collection_fields_changed)
        self._new_name_label = QLabel("New Collection name", self)
        options_form.addRow(self._new_name_label, self._new_name_input)

        self._new_description_input = QLineEdit(self)
        self._new_description_input.textChanged.connect(self._on_new_collection_fields_changed)
        self._new_description_label = QLabel("Description", self)
        options_form.addRow(self._new_description_label, self._new_description_input)

        self._new_card_size_input = QSpinBox(self)
        self._new_card_size_input.setRange(1, 1000)
        self._new_card_size_input.setValue(8)
        self._new_card_size_input.valueChanged.connect(self._on_new_collection_fields_changed)
        self._new_card_size_label = QLabel("Card size", self)
        options_form.addRow(self._new_card_size_label, self._new_card_size_input)
        layout.addLayout(options_form)

        self._preserve_order_checkbox = QCheckBox("Use file order / position when available", self)
        self._preserve_order_checkbox.setChecked(True)
        self._preserve_order_checkbox.toggled.connect(self._controller.set_preserve_file_order)
        layout.addWidget(self._preserve_order_checkbox)

        self._confirm_checkbox = QCheckBox("", self)
        self._confirm_checkbox.toggled.connect(self._update_confirm_enabled)
        layout.addWidget(self._confirm_checkbox)

        confirm_row = QHBoxLayout()
        confirm_row.addStretch(1)
        self._confirm_button = QPushButton("Confirm Import", self)
        self._confirm_button.setObjectName("data-tools-confirm-import-button")
        self._confirm_button.setEnabled(False)
        self._confirm_button.clicked.connect(self._on_confirm)
        confirm_row.addWidget(self._confirm_button)
        layout.addLayout(confirm_row)

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
        outer.addLayout(close_row)

        controller.import_state_changed.connect(self._reload)
        self._reload_target_collections()
        self._reload()

    # -- upload -------------------------------------------------------

    def _on_choose_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Choose a CSV or XLSX file", "", "CSV/XLSX Files (*.csv *.xlsx)")
        if not path:
            return
        try:
            with open(path, "rb") as handle:
                file_bytes = handle.read()
        except OSError as error:
            QMessageBox.warning(self, "Choose File", f"Could not read this file: {error}")
            return
        self._controller.load_file(file_bytes, os.path.basename(path))

    def _on_mode_changed(self, index: int) -> None:
        value = self._mode_combo.itemData(index)
        if value is not None:
            self._controller.set_mode(value)

    def _on_sheet_changed(self, index: int) -> None:
        value = self._sheet_combo.itemData(index)
        if value is not None:
            self._controller.set_sheet(value)

    def _on_duplicate_changed(self, index: int) -> None:
        value = self._duplicate_combo.itemData(index)
        if value is not None:
            self._controller.set_duplicate_handling(value)

    def _on_target_collection_changed(self, index: int) -> None:
        self._controller.set_target_collection(self._target_collection_combo.itemData(index))

    def _on_collection_mode_changed(self, index: int) -> None:
        value = self._collection_mode_combo.itemData(index)
        if value is not None:
            self._controller.set_collection_import_mode(value)
        self._update_destination_visibility()

    def _on_new_collection_fields_changed(self, *_args) -> None:
        self._controller.set_new_collection_fields(
            self._new_name_input.text(), self._new_description_input.text(), self._new_card_size_input.value()
        )

    def _on_preview(self) -> None:
        if self._controller.file_bytes is None:
            self._preview_error_label.setText("Choose a file first.")
            return
        self._controller.run_preview()

    def _reload_target_collections(self) -> None:
        collections = self._controller.import_target_collections()
        self._target_collection_combo.blockSignals(True)
        self._target_collection_combo.clear()
        self._target_collection_combo.addItem("None", None)
        for collection in collections:
            self._target_collection_combo.addItem(collection["name"], int(collection["id"]))
        self._target_collection_combo.blockSignals(False)

    def _update_destination_visibility(self) -> None:
        is_collection_mode = self._controller.mode == "collection"
        create_new = self._controller.collection_import_mode == "create_new_collection"

        self._target_collection_label.setVisible(not is_collection_mode)
        self._target_collection_combo.setVisible(not is_collection_mode)

        self._collection_mode_label.setVisible(is_collection_mode)
        self._collection_mode_combo.setVisible(is_collection_mode)
        self._preserve_order_checkbox.setVisible(is_collection_mode)

        show_new_fields = is_collection_mode and create_new
        for widget in (
            self._new_name_label,
            self._new_name_input,
            self._new_description_label,
            self._new_description_input,
            self._new_card_size_label,
            self._new_card_size_input,
        ):
            widget.setVisible(show_new_fields)

        if is_collection_mode and not create_new:
            self._target_collection_label.setVisible(True)
            self._target_collection_combo.setVisible(True)
            self._target_collection_label.setText("Target Collection")
        else:
            self._target_collection_label.setText("Add to Collection")

        self._confirm_checkbox.setText(self._confirmation_text())

    def _confirmation_text(self) -> str:
        if self._controller.mode == "collection":
            if self._controller.collection_import_mode == "create_new_collection":
                return "I understand this will create a new Collection and import Entries into it."
            return "I understand this will create Entries and add them to the selected Collection."
        if self._controller.mode == "template_aware":
            return "I understand this will add template-based Entries and field values to my database."
        return "I understand this will add new General Entry rows to my database."

    # -- reload ----------------------------------------------------------

    def _reload(self) -> None:
        controller = self._controller

        self._file_label.setText(controller.filename or "No file selected.")
        has_multiple_sheets = len(controller.sheet_names) > 1
        self._sheet_row_label.setVisible(has_multiple_sheets)
        self._sheet_combo.setVisible(has_multiple_sheets)
        if has_multiple_sheets:
            self._sheet_combo.blockSignals(True)
            self._sheet_combo.clear()
            for sheet_name in controller.sheet_names:
                self._sheet_combo.addItem(sheet_name, sheet_name)
            index = self._sheet_combo.findData(controller.selected_sheet)
            if index >= 0:
                self._sheet_combo.setCurrentIndex(index)
            self._sheet_combo.blockSignals(False)

        self._update_destination_visibility()

        if controller.preview_error:
            self._preview_error_label.setText(controller.preview_error)
        else:
            self._preview_error_label.setText("")

        preview = controller.preview
        if preview is None:
            self._summary_label.setText("")
            self._valid_table.setRowCount(0)
            self._invalid_table.setRowCount(0)
        else:
            summary = preview["summary"]
            self._summary_label.setText(
                f"Total {summary['total_rows']} · Valid {summary['valid_count']} · "
                f"Invalid {summary['invalid_count']} · Warnings {summary['warning_count']} · "
                f"Possible duplicates {summary['duplicate_candidate_count']}"
            )
            valid_rows = preview["valid_rows"]
            self._valid_table.setRowCount(len(valid_rows))
            for row, entry in enumerate(valid_rows):
                data = entry.get("data", {})
                self._valid_table.setItem(row, 0, QTableWidgetItem(str(entry.get("row_number"))))
                self._valid_table.setItem(row, 1, QTableWidgetItem(str(data.get("resolved_term") or "")))
                self._valid_table.setItem(row, 2, QTableWidgetItem(str(data.get("resolved_meaning") or "")))
                self._valid_table.setItem(row, 3, QTableWidgetItem(str(data.get("language") or "")))

            invalid_rows = preview["invalid_rows"]
            self._invalid_table.setRowCount(len(invalid_rows))
            for row, entry in enumerate(invalid_rows):
                self._invalid_table.setItem(row, 0, QTableWidgetItem(str(entry.get("row_number"))))
                self._invalid_table.setItem(row, 1, QTableWidgetItem("; ".join(entry.get("errors") or [])))

        if controller.import_result is not None:
            result = controller.import_result
            imported = result.get("imported_count", result.get("imported_entry_count", 0))
            self._result_label.setText(
                f"Import finished. Imported {imported}, "
                f"skipped {result.get('skipped_duplicate_count', 0)} duplicates, "
                f"failed {result.get('failed_count', 0)}."
            )
        else:
            self._result_label.setText("")

        self._update_confirm_enabled()

    def _update_confirm_enabled(self) -> None:
        self._confirm_button.setEnabled(
            self._controller.can_confirm_import() and self._confirm_checkbox.isChecked()
        )

    def _on_confirm(self) -> None:
        try:
            self._controller.confirm_import()
        except ValueError as error:
            self._result_label.setText(str(error))


class _ExportDialog(QDialog):
    """P6 Export workflow: scope + format -> a native Save dialog writes
    the file directly to disk (the desktop equivalent of Streamlit's
    ``st.download_button``) -- no separate in-app preview step, since
    export never mutates SQLite and the file itself is the result."""

    def __init__(self, controller: DataToolsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("data-tools-export-dialog")
        self.setWindowTitle("Export")
        self.setMinimumWidth(420)
        self._controller = controller

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._scope_combo = QComboBox(self)
        for value, label in EXPORT_SCOPE_LABELS:
            self._scope_combo.addItem(label, value)
        self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        form.addRow("Scope", self._scope_combo)

        self._collection_combo = QComboBox(self)
        self._collection_label = QLabel("Collection", self)
        form.addRow(self._collection_label, self._collection_combo)

        self._format_combo = QComboBox(self)
        self._format_combo.addItem("CSV", "csv")
        self._format_combo.addItem("XLSX", "xlsx")
        form.addRow("File format", self._format_combo)

        layout.addLayout(form)

        self._result_label = QLabel("", self)
        self._result_label.setObjectName("data-tools-export-result-label")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Close", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        export_button = QPushButton("Export…", self)
        export_button.setObjectName("data-tools-export-confirm-button")
        export_button.clicked.connect(self._on_export)
        buttons.addWidget(export_button)
        layout.addLayout(buttons)

        controller.export_collections_changed.connect(self._reload_collections)
        controller.refresh_export_collections()
        self._on_scope_changed(0)

    def _reload_collections(self) -> None:
        self._collection_combo.clear()
        for collection in self._controller.export_collections:
            self._collection_combo.addItem(
                f"{collection['name']} ({int(collection.get('entry_count') or 0)} entries)", int(collection["id"])
            )

    def _on_scope_changed(self, index: int) -> None:
        scope = self._scope_combo.itemData(index)
        show_collection = scope == "collection"
        self._collection_label.setVisible(show_collection)
        self._collection_combo.setVisible(show_collection)

    def _on_export(self) -> None:
        scope = self._scope_combo.currentData()
        file_format = self._format_combo.currentData()
        collection_id = None
        label = "all"
        filename_scope = "all_entries"
        if scope == "collection":
            collection_id = self._collection_combo.currentData()
            if collection_id is None:
                self._result_label.setText("Choose a Collection to export.")
                return
            label = self._collection_combo.currentText().split(" (")[0]
            filename_scope = "collection"
        elif scope == "summary":
            label = "summary"
            filename_scope = "collections"

        try:
            rows, columns = self._controller.export_rows(scope, collection_id)
        except ValueError as error:
            self._result_label.setText(str(error))
            return

        default_name = self._controller.export_filename(filename_scope, label, file_format)
        file_filter = "CSV Files (*.csv)" if file_format == "csv" else "Excel Files (*.xlsx)"
        path, _filter = QFileDialog.getSaveFileName(self, "Export", default_name, file_filter)
        if not path:
            return

        data = self._controller.export_bytes(rows, columns, file_format)
        try:
            with open(path, "wb") as handle:
                handle.write(data)
        except OSError as error:
            QMessageBox.warning(self, "Export", f"Could not write this file: {error}")
            return

        self._result_label.setText(f"Exported {len(rows)} rows to {path}.")


class _TemplateDefinitionDialog(QDialog):
    """P6 Template Definition portability (DESIGN.md § 7.4 "Template
    definition import/export: B, P6"). A distinct concept from the
    General/Template-Based/Collection Entry import above -- this moves a
    Template's *field structure*, not Entries -- kept in its own P6
    dialog rather than folded into `_ImportDialog`'s mode combo, since
    the source/target object (Templates, not Entries) and the confirm
    action's consequence (creates a new Template + Fields, never Entries)
    are different enough to be a separate meaningful task."""

    def __init__(self, controller: DataToolsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("data-tools-template-definition-dialog")
        self.setWindowTitle("Template Definitions")
        self.setMinimumSize(520, 520)
        self._controller = controller

        layout = QVBoxLayout(self)

        export_heading = QLabel("Export", self)
        export_heading.setObjectName("data-tools-section-heading")
        layout.addWidget(export_heading)

        export_form = QFormLayout()
        self._export_template_combo = QComboBox(self)
        for template in controller.exportable_templates():
            self._export_template_combo.addItem(template["name"], int(template["id"]))
        export_form.addRow("Template", self._export_template_combo)
        layout.addLayout(export_form)

        export_row = QHBoxLayout()
        export_row.addStretch(1)
        export_button = QPushButton("Export…", self)
        export_button.setObjectName("data-tools-template-definition-export-button")
        export_button.clicked.connect(self._on_export)
        export_row.addWidget(export_button)
        layout.addLayout(export_row)

        self._export_result_label = QLabel("", self)
        self._export_result_label.setWordWrap(True)
        layout.addWidget(self._export_result_label)

        import_heading = QLabel("Import", self)
        import_heading.setObjectName("data-tools-section-heading")
        layout.addWidget(import_heading)

        file_row = QHBoxLayout()
        self._import_file_label = QLabel("No file selected.", self)
        file_row.addWidget(self._import_file_label, 1)
        choose_button = QPushButton("Choose File…", self)
        choose_button.clicked.connect(self._on_choose_file)
        file_row.addWidget(choose_button, 0)
        layout.addLayout(file_row)

        preview_row = QHBoxLayout()
        preview_row.addStretch(1)
        self._preview_button = QPushButton("Preview Import", self)
        self._preview_button.setObjectName("data-tools-template-definition-preview-button")
        self._preview_button.clicked.connect(self._on_preview)
        preview_row.addWidget(self._preview_button)
        layout.addLayout(preview_row)

        self._preview_summary_label = QLabel("", self)
        self._preview_summary_label.setObjectName("data-tools-summary-label")
        self._preview_summary_label.setWordWrap(True)
        layout.addWidget(self._preview_summary_label)

        self._preview_errors_label = QLabel("", self)
        self._preview_errors_label.setObjectName("data-tools-preview-error")
        self._preview_errors_label.setWordWrap(True)
        layout.addWidget(self._preview_errors_label)

        self._confirm_checkbox = QCheckBox("I understand this will create a new Template and its Fields.", self)
        self._confirm_checkbox.toggled.connect(self._update_confirm_enabled)
        layout.addWidget(self._confirm_checkbox)

        confirm_row = QHBoxLayout()
        confirm_row.addStretch(1)
        self._confirm_button = QPushButton("Confirm Import", self)
        self._confirm_button.setObjectName("data-tools-template-definition-confirm-button")
        self._confirm_button.setEnabled(False)
        self._confirm_button.clicked.connect(self._on_confirm)
        confirm_row.addWidget(self._confirm_button)
        layout.addLayout(confirm_row)

        self._import_result_label = QLabel("", self)
        self._import_result_label.setObjectName("data-tools-result-label")
        self._import_result_label.setWordWrap(True)
        layout.addWidget(self._import_result_label)

        layout.addStretch(1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

        controller.template_definition_state_changed.connect(self._reload)
        self._reload()

    def _on_export(self) -> None:
        template_id = self._export_template_combo.currentData()
        if template_id is None:
            return
        template_name = self._export_template_combo.currentText()
        try:
            data = self._controller.export_template_definition(int(template_id))
        except TemplateDefinitionError as error:
            self._export_result_label.setText(str(error))
            return
        default_name = self._controller.template_definition_export_filename(template_name)
        path, _filter = QFileDialog.getSaveFileName(self, "Export Template Definition", default_name, "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "wb") as handle:
                handle.write(data)
        except OSError as error:
            QMessageBox.warning(self, "Export Template Definition", f"Could not write this file: {error}")
            return
        self._export_result_label.setText(f"Exported to {path}.")

    def _on_choose_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Choose a Template Definition CSV file", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "rb") as handle:
                file_bytes = handle.read()
        except OSError as error:
            QMessageBox.warning(self, "Choose File", f"Could not read this file: {error}")
            return
        self._controller.load_template_definition_file(file_bytes, os.path.basename(path))

    def _on_preview(self) -> None:
        if self._controller.template_definition_file_bytes is None:
            self._preview_errors_label.setText("Choose a file first.")
            return
        self._controller.run_template_definition_preview()

    def _reload(self) -> None:
        controller = self._controller
        self._import_file_label.setText(controller.template_definition_filename or "No file selected.")

        preview = controller.template_definition_preview
        if preview is None:
            self._preview_summary_label.setText("")
            self._preview_errors_label.setText("")
        else:
            template = preview.get("template") or {}
            self._preview_summary_label.setText(
                f"Template: {template.get('name') or '(unknown)'} · "
                f"Fields: {len(preview.get('fields') or [])} · "
                f"{'Ready to import' if preview['can_import'] else 'Cannot import'}"
            )
            self._preview_errors_label.setText("; ".join(preview.get("errors") or []))

        if controller.template_definition_result is not None:
            result = controller.template_definition_result
            self._import_result_label.setText(
                f"Imported Template '{result['template']['name']}' with {result['field_count']} Fields."
            )
        else:
            self._import_result_label.setText("")

        self._update_confirm_enabled()

    def _update_confirm_enabled(self) -> None:
        self._confirm_button.setEnabled(
            self._controller.can_confirm_template_definition_import() and self._confirm_checkbox.isChecked()
        )

    def _on_confirm(self) -> None:
        try:
            self._controller.confirm_template_definition_import()
        except TemplateDefinitionError as error:
            self._import_result_label.setText(str(error))

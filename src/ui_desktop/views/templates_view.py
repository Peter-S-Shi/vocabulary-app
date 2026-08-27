from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.text_parser import VALID_LANGUAGES
from src.time_utils import format_local_timestamp
from src.ui_desktop.controllers.templates_controller import FIELD_TYPES, TemplatesController
from src.ui_desktop.theming.metrics import SPACING

"""
Template Manager (DESIGN.md § 7.3 "B, P2") + Template Editor (§ 7.3 "B, P5
independent Focused Workspace by default") + Template Field small edit
(§ 7.3 "B, P5 modal when bounded"). Design Derivation Record per § 9,
since the exact local composition is not fully obvious from the parent
patterns alone:

  1. Interaction Mode        -> Management.
  2. Parent Pattern          -> P2 Table-First Manager (this workspace) +
                                 P5 independent Focused Workspace for the
                                 Template Editor + P5 modal for Field
                                 add/edit.
  3. Primary User Task       -> browse/create Templates; edit a Template's
                                 metadata and Fields (add/edit/delete).
  4. Spatial Composition     -> Management Rail -> compact toolbar (New
                                 Template) -> dominant Templates table
                                 (system + custom, matching Entries' P2
                                 table grammar). Selecting a row opens the
                                 Template Editor as its own large modal
                                 workspace (`_TemplateEditorDialog`)
                                 rather than an inline detail pane, since
                                 § 8 P5 explicitly calls Template + Field
                                 definition "complex enough to be a
                                 meaningful task."
  5. Dominance Rule          -> the table dominates the Manager surface;
                                 inside the Editor, the Fields table
                                 dominates alongside the (secondary)
                                 metadata form.
  6. Density Rule            -> inherits existing Management Mode density
                                 (matches Entries/Collections tables).
  7. Surface Hierarchy       -> table on `surface_primary`, matching
                                 Entries; the Editor dialog uses the same
                                 modal surface treatment as
                                 `_EntryEditorDialog`/
                                 `_CollectionEditorDialog`.
  8. Action Hierarchy        -> primary = New Template / Save / Add Field
                                 (accent-primary); destructive = Delete
                                 Template / Delete Field (P6), both
                                 disabled outright (not merely warned) when
                                 the existing `template_has_entries`/
                                 `template_field_has_values` in-use gate
                                 blocks it -- the same safety the
                                 Streamlit page already enforces; system
                                 Templates are read-only throughout
                                 (Save/Add/Delete disabled).
  9. Editing Container       -> Template Editor = P5 independent focused
                                 workspace (large modal dialog); Field
                                 add/edit = P5 modal (small, bounded:
                                 key/label/type/required/display_order).
 10. Navigation/Chrome       -> unchanged Management shell on the Manager
                                 table; both dialogs are modal overlays,
                                 no chrome swap.
 11. Motion/Transition       -> unchanged `TransitionManager.fade_in` on
                                 workspace switch, matching Entries/
                                 Collections; no new motion for dialogs.
 12. Canonical Visual Rel.   -> the Manager table inherits Entries' P2
                                 Table-First grammar; the Editor inherits
                                 `_EntryEditorDialog`'s P5 grammar
                                 (scrollable body, pinned Save/Cancel
                                 footer) as the closest existing
                                 focused-editor precedent.
 13. Native Human Acceptance -> the real native Templates workspace
                                 showing the table (system + custom), New
                                 Template creation, the Template Editor
                                 (metadata edit, Add/Edit/Delete Field,
                                 disabled-delete states when in use, a
                                 read-only system Template), in Light and
                                 Dark Mode.

Template Definition CSV import/export (DESIGN.md § 7.4, a P6 Data Tools
surface) is explicitly out of scope for this checkpoint -- it belongs to
the later Data Tools phase, not the Template Manager/Editor pattern this
file implements.
"""

_LANGUAGE_OPTIONS: tuple[str, ...] = ("", *sorted(VALID_LANGUAGES), "any")


class TemplatesView(QWidget):
    def __init__(self, controller: TemplatesController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("templates-root")
        self._controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)
        layout.setSpacing(SPACING.md)

        toolbar = QHBoxLayout()
        title = QLabel("Templates", self)
        title.setObjectName("templates-title")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        # Human Gate 1 corrective: double-click alone was not a discoverable
        # entry point into an existing Template (undiscoverable gesture,
        # not the established P2 grammar). "Open Template" is the explicit,
        # always-visible affordance -- enabled only once a row is selected,
        # the same selection-gates-the-action pattern Entries' bottom
        # "Edit" action already uses -- while double-click remains a
        # convenience shortcut onto the exact same code path, not a second
        # implementation.
        self._open_button = QPushButton("Open Template", self)
        self._open_button.setObjectName("templates-open-button")
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(self._on_open_selected)
        toolbar.addWidget(self._open_button)
        new_button = QPushButton("New Template", self)
        new_button.setObjectName("templates-new-button")
        new_button.clicked.connect(self._on_new_template)
        toolbar.addWidget(new_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(self)
        self._table.setObjectName("templates-table")
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Name", "Type", "Language", "Owner", "Fields", "Updated"])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self._table.doubleClicked.connect(self._on_row_activated)
        layout.addWidget(self._table, 1)

        controller.templates_changed.connect(self._render_table)

    def refresh(self) -> None:
        self._controller.refresh()

    def _render_table(self) -> None:
        # Selection is row-index-based (QTableWidget's own selection
        # model), but rows are reshuffled by sort order every refresh --
        # including a refresh that fires while a modal Template Editor is
        # still open (e.g. renaming a Template moves it to a different
        # alphabetical row). Capture the selected Template's stable id
        # before repopulating and restore selection by id afterward, so a
        # reorder can never silently leave a stale row "selected" (and
        # Open Template pointed at the wrong Template) -- an independent
        # review finding on this corrective checkpoint.
        previously_selected_id = self._current_row_template_id()

        templates = self._controller.templates
        self._table.setRowCount(len(templates))
        target_row = -1
        for row, template in enumerate(templates):
            self._table.setItem(row, 0, QTableWidgetItem(str(template.get("name") or "")))
            self._table.setItem(row, 1, QTableWidgetItem(str(template.get("template_type") or "")))
            self._table.setItem(row, 2, QTableWidgetItem(str(template.get("language") or "")))
            self._table.setItem(row, 3, QTableWidgetItem("System" if template.get("is_system") else "Custom"))
            self._table.setItem(row, 4, QTableWidgetItem(str(int(template.get("field_count") or 0))))
            self._table.setItem(row, 5, QTableWidgetItem(format_local_timestamp(template.get("updated_at"))))
            template_id = int(template["id"])
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, template_id)
            if previously_selected_id is not None and template_id == previously_selected_id:
                target_row = row

        if target_row >= 0:
            self._table.selectRow(target_row)
        else:
            self._table.clearSelection()
        self._on_table_selection_changed()

    def _current_row_template_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _on_table_selection_changed(self) -> None:
        self._open_button.setEnabled(bool(self._table.selectedItems()))

    def _open_editor_for_row(self, row: int) -> None:
        item = self._table.item(row, 0)
        if item is None:
            return
        template_id = int(item.data(Qt.ItemDataRole.UserRole))
        self._controller.select_template(template_id)
        dialog = _TemplateEditorDialog(self._controller, parent=self)
        dialog.exec()
        self._controller.clear_selection()

    def _on_row_activated(self, index) -> None:
        self._open_editor_for_row(index.row())

    def _on_open_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        self._open_editor_for_row(row)

    def _on_new_template(self) -> None:
        dialog = _NewTemplateDialog(self._controller, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog2 = _TemplateEditorDialog(self._controller, parent=self)
            dialog2.exec()
            self._controller.clear_selection()


class _NewTemplateDialog(QDialog):
    """P5 modal (small, bounded: four metadata fields) -- the create step
    only; Field definition happens afterward in the Template Editor,
    matching the Streamlit page's "create, then add fields under Inspect"
    flow."""

    def __init__(self, controller: TemplatesController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("templates-new-dialog")
        self.setWindowTitle("New Template")
        self.setMinimumWidth(420)
        self._controller = controller

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_input = QLineEdit(self)
        form.addRow("Name", self._name_input)

        self._description_input = QPlainTextEdit(self)
        self._description_input.setFixedHeight(70)
        form.addRow("Description", self._description_input)

        self._language_combo = QComboBox(self)
        self._language_combo.addItems(_LANGUAGE_OPTIONS)
        form.addRow("Language", self._language_combo)

        self._type_input = QLineEdit(self)
        self._type_input.setText("custom")
        form.addRow("Template type", self._type_input)

        layout.addLayout(form)

        self._error_label = QLabel("", self)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        create_button = QPushButton("Create", self)
        create_button.setObjectName("templates-new-create-button")
        create_button.clicked.connect(self._on_create)
        buttons.addWidget(create_button)
        layout.addLayout(buttons)

    def _on_create(self) -> None:
        try:
            self._controller.create_new_template(
                self._name_input.text(),
                self._description_input.toPlainText(),
                self._language_combo.currentText() or None,
                self._type_input.text(),
            )
        except ValueError as error:
            self._error_label.setText(str(error))
            return
        self.accept()


class _TemplateEditorDialog(QDialog):
    """P5 independent Focused Workspace (DESIGN.md § 7.3/§ 8): metadata
    form plus the Fields table together, since editing a Template's field
    composition is a meaningful task in its own right, not a bounded
    inline tweak. Reads/writes always target
    ``TemplatesController.selected_id`` -- the caller selects the
    Template before constructing this dialog."""

    def __init__(self, controller: TemplatesController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("templates-editor-dialog")
        self.setMinimumSize(640, 560)
        self._controller = controller

        layout = QVBoxLayout(self)

        self._form = QFormLayout()
        self._name_input = QLineEdit(self)
        self._form.addRow("Name", self._name_input)
        self._description_input = QPlainTextEdit(self)
        self._description_input.setFixedHeight(60)
        self._form.addRow("Description", self._description_input)
        self._language_combo = QComboBox(self)
        self._language_combo.addItems(_LANGUAGE_OPTIONS)
        self._form.addRow("Language", self._language_combo)
        self._type_input = QLineEdit(self)
        self._form.addRow("Template type", self._type_input)
        layout.addLayout(self._form)

        self._system_notice = QLabel("System template: read-only.", self)
        self._system_notice.setObjectName("templates-editor-system-notice")
        layout.addWidget(self._system_notice)

        self._save_error_label = QLabel("", self)
        self._save_error_label.setWordWrap(True)
        layout.addWidget(self._save_error_label)

        metadata_buttons = QHBoxLayout()
        metadata_buttons.addStretch(1)
        self._save_button = QPushButton("Save Template", self)
        self._save_button.setObjectName("templates-editor-save-button")
        self._save_button.clicked.connect(self._on_save_metadata)
        metadata_buttons.addWidget(self._save_button)
        layout.addLayout(metadata_buttons)

        fields_heading = QLabel("Fields", self)
        fields_heading.setObjectName("templates-editor-fields-heading")
        layout.addWidget(fields_heading)

        self._fields_table = QTableWidget(self)
        self._fields_table.setObjectName("templates-editor-fields-table")
        self._fields_table.setColumnCount(5)
        self._fields_table.setHorizontalHeaderLabels(["Order", "Key", "Label", "Type", "Required"])
        self._fields_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._fields_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._fields_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._fields_table.verticalHeader().setVisible(False)
        self._fields_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._fields_table, 1)

        field_buttons = QHBoxLayout()
        self._add_field_button = QPushButton("Add Field", self)
        self._add_field_button.setObjectName("templates-editor-add-field-button")
        self._add_field_button.clicked.connect(self._on_add_field)
        field_buttons.addWidget(self._add_field_button)
        self._edit_field_button = QPushButton("Edit Field", self)
        self._edit_field_button.setObjectName("templates-editor-edit-field-button")
        self._edit_field_button.clicked.connect(self._on_edit_field)
        field_buttons.addWidget(self._edit_field_button)
        self._delete_field_button = QPushButton("Delete Field", self)
        self._delete_field_button.setObjectName("templates-editor-delete-field-button")
        self._delete_field_button.setProperty("destructive", "true")
        self._delete_field_button.clicked.connect(self._on_delete_field)
        field_buttons.addWidget(self._delete_field_button)
        field_buttons.addStretch(1)
        layout.addLayout(field_buttons)

        self._delete_template_button = QPushButton("Delete Template", self)
        self._delete_template_button.setObjectName("templates-editor-delete-template-button")
        self._delete_template_button.setProperty("destructive", "true")
        self._delete_template_button.clicked.connect(self._on_delete_template)
        layout.addWidget(self._delete_template_button, 0, Qt.AlignmentFlag.AlignRight)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

        controller.selection_changed.connect(self._reload)
        self._reload()

    def _reload(self) -> None:
        template = self._controller.selected_template()
        if template is None:
            self.reject()
            return
        self.setWindowTitle(f"Edit Template — {template.get('name') or ''}")

        is_system = bool(template.get("is_system"))
        self._name_input.setText(str(template.get("name") or ""))
        self._description_input.setPlainText(str(template.get("description") or ""))
        self._language_combo.setCurrentText(str(template.get("language") or ""))
        self._type_input.setText(str(template.get("template_type") or ""))

        self._system_notice.setVisible(is_system)
        for widget in (self._name_input, self._description_input, self._language_combo, self._type_input, self._save_button):
            widget.setEnabled(not is_system)
        self._add_field_button.setEnabled(not is_system)
        self._delete_template_button.setEnabled(not is_system and self._controller.can_delete_selected_template())

        fields = self._controller.selected_fields()
        self._fields_table.setRowCount(len(fields))
        for row, field in enumerate(fields):
            self._fields_table.setItem(row, 0, QTableWidgetItem(str(field.get("display_order"))))
            self._fields_table.setItem(row, 1, QTableWidgetItem(str(field.get("field_key") or "")))
            self._fields_table.setItem(row, 2, QTableWidgetItem(str(field.get("field_label") or "")))
            self._fields_table.setItem(row, 3, QTableWidgetItem(str(field.get("field_type") or "")))
            self._fields_table.setItem(row, 4, QTableWidgetItem("Yes" if field.get("required") else "No"))
            self._fields_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, int(field["id"]))
        self._edit_field_button.setEnabled(not is_system and bool(fields))
        self._delete_field_button.setEnabled(not is_system and bool(fields))

    def _selected_field_id(self) -> int | None:
        row = self._fields_table.currentRow()
        if row < 0:
            return None
        item = self._fields_table.item(row, 0)
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _on_save_metadata(self) -> None:
        self._save_error_label.setText("")
        try:
            self._controller.update_selected_template(
                self._name_input.text(),
                self._description_input.toPlainText(),
                self._language_combo.currentText() or None,
                self._type_input.text(),
            )
        except ValueError as error:
            self._save_error_label.setText(str(error))

    def _on_add_field(self) -> None:
        dialog = _TemplateFieldDialog(self._controller, field=None, parent=self)
        dialog.exec()

    def _on_edit_field(self) -> None:
        field_id = self._selected_field_id()
        if field_id is None:
            return
        field = next((f for f in self._controller.selected_fields() if int(f["id"]) == field_id), None)
        if field is None:
            return
        dialog = _TemplateFieldDialog(self._controller, field=field, parent=self)
        dialog.exec()

    def _on_delete_field(self) -> None:
        field_id = self._selected_field_id()
        if field_id is None:
            return
        if self._controller.field_has_values(field_id):
            QMessageBox.warning(
                self,
                "Delete Field",
                "This field already has entry values and cannot be deleted safely.",
            )
            return
        confirmed = QMessageBox.question(
            self,
            "Delete Field",
            "Delete this field? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._controller.delete_field(field_id)

    def _on_delete_template(self) -> None:
        if not self._controller.can_delete_selected_template():
            QMessageBox.warning(
                self,
                "Delete Template",
                "This Template is used by existing Entries and cannot be deleted safely.",
            )
            return
        confirmed = QMessageBox.question(
            self,
            "Delete Template",
            "Delete this Template? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        if self._controller.delete_selected_template():
            self.accept()


class _TemplateFieldDialog(QDialog):
    """P5 modal, bounded (DESIGN.md § 7.3 "Template Field small edit: P5
    modal when bounded"): field_key (locked on edit, matching the
    Streamlit page), field_label, field_type, required, display_order.
    ``field is None`` means add."""

    def __init__(self, controller: TemplatesController, field: dict | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("templates-field-dialog")
        self.setWindowTitle("Add Field" if field is None else "Edit Field")
        self.setMinimumWidth(380)
        self._controller = controller
        self._field = field

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._key_input = QLineEdit(self)
        if field is not None:
            self._key_input.setText(str(field.get("field_key") or ""))
            self._key_input.setEnabled(False)
        form.addRow("Field key", self._key_input)

        self._label_input = QLineEdit(self)
        self._label_input.setText(str(field.get("field_label") or "") if field else "")
        form.addRow("Field label", self._label_input)

        self._type_combo = QComboBox(self)
        self._type_combo.addItems(FIELD_TYPES)
        if field is not None:
            self._type_combo.setCurrentText(str(field.get("field_type") or ""))
        form.addRow("Field type", self._type_combo)

        self._required_checkbox = QCheckBox("Required", self)
        self._required_checkbox.setChecked(bool(field.get("required")) if field else False)
        form.addRow("", self._required_checkbox)

        self._order_input = QSpinBox(self)
        self._order_input.setRange(0, 1000)
        self._order_input.setValue(int(field.get("display_order") or 0) if field else 0)
        form.addRow("Display order", self._order_input)

        layout.addLayout(form)

        self._error_label = QLabel("", self)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        save_button = QPushButton("Save", self)
        save_button.setObjectName("templates-field-save-button")
        save_button.clicked.connect(self._on_save)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def _on_save(self) -> None:
        try:
            if self._field is None:
                self._controller.create_field(
                    self._key_input.text(),
                    self._label_input.text(),
                    self._type_combo.currentText(),
                    self._required_checkbox.isChecked(),
                    self._order_input.value(),
                )
            else:
                self._controller.update_field(
                    int(self._field["id"]),
                    self._label_input.text(),
                    self._type_combo.currentText(),
                    self._required_checkbox.isChecked(),
                    self._order_input.value(),
                )
        except ValueError as error:
            self._error_label.setText(str(error))
            return
        self.accept()

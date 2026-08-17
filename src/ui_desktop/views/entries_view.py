from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.collections import CROSS_CARD_CONFIRMATION_MESSAGE, CrossCardMoveConfirmationRequired
from src.text_parser import VALID_ENTRY_TYPES, VALID_EXPLANATION_LANGUAGES, VALID_LANGUAGES, VALID_STATUSES
from src.ui_desktop.controllers.entries_controller import SCOPE_ALL, EntriesController
from src.ui_desktop.theming.metrics import SPACING

"""
Entries -- Table-First Manager (DESIGN.md § 6.2 `VR-ENTRIES-001`,
`Entries & Collections Manager.pdf` p3 Variant B, parent pattern P2). M17
Feature 4: replaces the M16.2 architecture-proof placeholder with the real
native workflow -- ``src/ui_streamlit/entries_page.py`` is a behavioral
reference only, not a structural one.

Design -> Implementation trace:

  shell/chrome           -> ordinary Management Mode workspace (Management
                             Rail stays visible, unlike Review/Quiz's Study
                             chrome swap); reused verbatim.
  frozen composition      -> Management Rail -> Scope Pane -> Main
                             Workspace (compact toolbar -> dominant Entries
                             Table -> subordinate horizontal Entry Detail),
                             DESIGN.md § 6.2's exact structure.
  dominance               -> the table gets all remaining vertical space
                             (stretch factor); the detail region is a
                             fixed-height horizontal strip below it, never
                             a competing panel (forbidden-substitution
                             list: "detail area consuming roughly half the
                             default workspace").
  Scope Pane              -> _ScopePane: All Entries, the three system
                             collections (Starred/Mistake Book/Proficient
                             Pool -- `src.collections.SYSTEM_COLLECTION_TYPES`),
                             then real user Collections with entry counts.
                             No fake scopes; Collection *management*
                             (create/rename/delete) stays out of scope for
                             this checkpoint (M17 Feature 4 prompt § 5/§ 9)
                             -- these are read-only browse scopes.
  toolbar                 -> search (Enter to apply, matching the existing
                             M16.2 pattern) + Language/Type/Status filters
                             (the exact `search_entries()` filter surface,
                             not a reinvented one) + batch actions (shown
                             only while rows are selected) + Add Entry +
                             Quick Add.
  table                   -> QTableView + QSortFilterProxyModel for real
                             native header-click sorting, ExtendedSelection
                             for real multi-row selection (ctrl/shift-click)
                             -- not Streamlit-style checkbox emulation
                             (M17 Feature 4 prompt § 9) -- and selection is
                             restored by id after every refresh so editing/
                             batch actions don't silently lose the user's
                             place.
  bottom detail            -> read-only factual summary of the single
                             selected Entry (Term / Meaning & Example /
                             Collections / Reviews & Accuracy / Notes) plus
                             an Edit action; multi-selection shows a plain
                             selection-count message instead (never a
                             second editor).
  Add / Edit               -> _EntryEditorDialog (P5 focused editor, modal
                             -- DESIGN.md § 10 editing-container decision:
                             "focused multi-field edit with clear
                             Save/Cancel and moderate complexity"), one
                             class for both modes. Template picker is only
                             editable when adding (`create_entry_with_template`);
                             Edit keeps the existing entry's template fixed,
                             matching current core/product behavior (no
                             template-switch API exists). Dynamic per-
                             template fields, manual canonical Term/Meaning
                             inputs shown only when the template's
                             canonical mapping actually needs them, and a
                             non-system Collections checklist.
  Quick Add                -> _QuickAddDialog (P6 bounded utility): the
                             structured-text-card flow is genuinely live
                             product behavior (confirmed against
                             `src/ui_streamlit/entries_page.py`), migrated
                             as-is through `parse_and_validate_entry_card`
                             + `add_entry` -- General-Entry-template only,
                             matching current product truth, not expanded
                             into Import/Export.
  destructive / batch      -> Delete Selected and any Collection-removal
                             path always go through the existing
                             `delete_entries`/`update_entry_collections`
                             confirmation gate (`CrossCardMoveConfirmationRequired`,
                             `src.collections`); a plain "Delete N Entries?"
                             confirm always precedes the call, and if the
                             core additionally requires Card-reorganization
                             confirmation, `CROSS_CARD_CONFIRMATION_MESSAGE`
                             (reused verbatim, not reworded) is shown before
                             retrying with ``confirm_cross_card=True``. There
                             is no silent-delete path.
"""

SCOPE_PANE_WIDTH = 200


class EntriesView(QWidget):
    def __init__(self, controller: EntriesController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entries-root")
        self._controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scope_pane = _ScopePane(self)
        self._scope_pane.setFixedWidth(SCOPE_PANE_WIDTH)
        self._scope_pane.scope_selected.connect(self._on_scope_selected)
        root.addWidget(self._scope_pane, 0)

        main = QWidget(self)
        main.setObjectName("entries-main-workspace")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)
        main_layout.setSpacing(SPACING.md)

        main_layout.addWidget(self._build_toolbar())

        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(controller.model)

        self._table = QTableView(self)
        self._table.setObjectName("entries-table")
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        main_layout.addWidget(self._table, 1)

        self._detail_container = QWidget(self)
        self._detail_container.setObjectName("entries-detail")
        self._detail_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._detail_layout = QHBoxLayout(self._detail_container)
        self._detail_layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        self._detail_layout.setSpacing(SPACING.lg)
        main_layout.addWidget(self._detail_container, 0)

        root.addWidget(main, 1)

        selection_model = self._table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._on_table_selection_changed)

        controller.rows_changed.connect(self._on_rows_changed)
        controller.scopes_changed.connect(self._on_scopes_changed)
        controller.selection_changed.connect(self._on_selection_changed)

    def refresh(self) -> None:
        self._controller.refresh_scopes()
        self._controller.refresh()

    # -- toolbar -------------------------------------------------------------

    def _build_toolbar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("entries-toolbar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.sm)

        title = QLabel("Entries", bar)
        title.setObjectName("entries-title")
        layout.addWidget(title, 0)

        self._search_input = QLineEdit(bar)
        self._search_input.setObjectName("entries-search-input")
        self._search_input.setPlaceholderText("Search term, meaning, tags…")
        self._search_input.returnPressed.connect(self._on_search_submitted)
        layout.addWidget(self._search_input, 1)

        self._language_combo = self._build_filter_combo("entries-language-filter", VALID_LANGUAGES)
        self._language_combo.currentTextChanged.connect(lambda value: self._controller.set_language(value))
        layout.addWidget(self._language_combo, 0)

        self._entry_type_combo = self._build_filter_combo("entries-entry-type-filter", VALID_ENTRY_TYPES)
        self._entry_type_combo.currentTextChanged.connect(lambda value: self._controller.set_entry_type(value))
        layout.addWidget(self._entry_type_combo, 0)

        self._status_combo = self._build_filter_combo("entries-status-filter", VALID_STATUSES)
        self._status_combo.currentTextChanged.connect(lambda value: self._controller.set_status(value))
        layout.addWidget(self._status_combo, 0)

        self._star_button = QPushButton("★ Star", bar)
        self._star_button.setObjectName("entries-batch-star-button")
        self._star_button.clicked.connect(self._on_add_to_starred)
        layout.addWidget(self._star_button, 0)

        self._collection_button = QPushButton("Add to Collection ▾", bar)
        self._collection_button.setObjectName("entries-batch-collection-button")
        self._collection_button.clicked.connect(self._open_add_to_collection_menu)
        layout.addWidget(self._collection_button, 0)

        self._delete_button = QPushButton("Delete", bar)
        self._delete_button.setObjectName("entries-batch-delete-button")
        self._delete_button.setProperty("destructive", "true")
        self._delete_button.clicked.connect(self._on_delete_selected)
        layout.addWidget(self._delete_button, 0)

        self._set_batch_actions_visible(False)

        quick_add_button = QPushButton("Quick Add", bar)
        quick_add_button.setObjectName("entries-quick-add-button")
        quick_add_button.clicked.connect(self._open_quick_add)
        layout.addWidget(quick_add_button, 0)

        add_button = QPushButton("Add Entry", bar)
        add_button.setObjectName("entries-add-button")
        add_button.clicked.connect(self._open_add_entry)
        layout.addWidget(add_button, 0)

        return bar

    @staticmethod
    def _build_filter_combo(object_name: str, values: set[str] | frozenset[str]) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(object_name)
        combo.addItem("All")
        combo.addItems(sorted(values))
        return combo

    def _set_batch_actions_visible(self, visible: bool) -> None:
        self._star_button.setVisible(visible)
        self._collection_button.setVisible(visible)
        self._delete_button.setVisible(visible)

    # -- scope / filter reactions --------------------------------------------

    def _on_scope_selected(self, scope_key: str) -> None:
        self._controller.set_scope(scope_key)

    def _on_search_submitted(self) -> None:
        self._controller.set_search_text(self._search_input.text())

    def _on_scopes_changed(self) -> None:
        self._scope_pane.render(self._controller.scopes, self._controller.scope)

    def _on_rows_changed(self, _count: int) -> None:
        self._restore_table_selection()

    # -- table selection -------------------------------------------------

    def _on_table_selection_changed(self, *_args: object) -> None:
        selection_model = self._table.selectionModel()
        if selection_model is None:
            return
        ids: set[int] = set()
        for proxy_index in selection_model.selectedRows():
            source_index = self._proxy.mapToSource(proxy_index)
            entry = self._controller.model.row_at(source_index.row())
            if entry is not None:
                ids.add(entry["id"])
        self._controller.set_selected_ids(ids)

    def _restore_table_selection(self) -> None:
        selection_model = self._table.selectionModel()
        if selection_model is None:
            return
        selection_model.blockSignals(True)
        selection_model.clearSelection()
        for source_row, entry in enumerate(self._controller.model.rows()):
            if entry["id"] in self._controller.selected_ids:
                source_index = self._controller.model.index(source_row, 0)
                proxy_index = self._proxy.mapFromSource(source_index)
                selection_model.select(
                    proxy_index,
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )
        selection_model.blockSignals(False)

    def _on_selection_changed(self, entries: list[dict]) -> None:
        self._set_batch_actions_visible(bool(entries))
        self._render_detail(entries)

    # -- bottom detail -------------------------------------------------------

    def _render_detail(self, entries: list[dict]) -> None:
        _clear_layout(self._detail_layout)

        if not entries:
            self._detail_layout.addWidget(_message_label("Choose a row to see details."))
            return
        if len(entries) > 1:
            self._detail_layout.addWidget(_message_label(f"{len(entries)} entries selected."))
            return

        entry = entries[0]
        self._detail_layout.addWidget(_detail_field("Term", str(entry.get("term") or "")))
        self._detail_layout.addWidget(
            _detail_field("Meaning & Example", str(entry.get("meaning") or ""), secondary=str(entry.get("example") or ""))
        )
        collection_names = entry.get("collection_names") or []
        self._detail_layout.addWidget(_detail_field("Collections", ", ".join(collection_names) or "—"))

        review_count = int(entry.get("review_count") or 0)
        correct_count = int(entry.get("correct_count") or 0)
        accuracy = f"{round(correct_count / review_count * 100)}%" if review_count else "—"
        self._detail_layout.addWidget(_detail_field("Reviews", str(review_count), secondary=f"Accuracy {accuracy}"))
        self._detail_layout.addWidget(_detail_field("Notes", str(entry.get("notes") or "") or "—"))

        self._detail_layout.addStretch(1)

        edit_button = QPushButton("Edit", self._detail_container)
        edit_button.setObjectName("entries-detail-edit-button")
        edit_button.clicked.connect(lambda: self._open_edit_entry(entry["id"]))
        self._detail_layout.addWidget(edit_button, 0, Qt.AlignmentFlag.AlignVCenter)

    # -- Add / Edit / Quick Add ----------------------------------------------

    def _open_add_entry(self) -> None:
        dialog = _EntryEditorDialog(self._controller, None, self)
        dialog.exec()

    def _open_edit_entry(self, entry_id: int) -> None:
        dialog = _EntryEditorDialog(self._controller, entry_id, self)
        dialog.exec()

    def _open_quick_add(self) -> None:
        dialog = _QuickAddDialog(self._controller, self)
        dialog.exec()

    # -- batch actions ---------------------------------------------------

    def _on_add_to_starred(self) -> None:
        self._controller.add_selected_to_starred()

    def _open_add_to_collection_menu(self) -> None:
        menu = QMenu(self)
        options = self._controller.collection_options()
        if not options:
            action = menu.addAction("No Collections yet")
            action.setEnabled(False)
        for collection in options:
            action = menu.addAction(collection["name"])
            action.triggered.connect(lambda _checked=False, collection_id=collection["id"]: self._controller.add_selected_to_collection(collection_id))
        menu.exec(QCursor.pos())

    def _on_delete_selected(self) -> None:
        count = len(self._controller.selected_ids)
        if not count:
            return
        noun = "Entry" if count == 1 else "Entries"
        confirmed = QMessageBox.question(
            self,
            "Delete Entries",
            f"Delete {count} selected {noun}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._delete_selected(confirm_cross_card=False)

    def _delete_selected(self, *, confirm_cross_card: bool) -> None:
        try:
            self._controller.delete_selected(confirm_cross_card=confirm_cross_card)
        except CrossCardMoveConfirmationRequired:
            if _confirm_cross_card_reorganization(self):
                self._delete_selected(confirm_cross_card=True)


class _ScopePane(QWidget):
    """Read-only left-of-table browse scopes (DESIGN.md § 6.2 Scope Pane):
    All Entries, the three system collections, then real user Collections.
    Never Collection create/rename/delete -- that belongs to the following
    M17 minimum Collection Integration checkpoint."""

    scope_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entries-scope-pane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACING.sm, SPACING.md, SPACING.sm, SPACING.md)
        self._layout.setSpacing(2)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

    def render(self, scopes: list[dict], active_key: str) -> None:
        _clear_layout(self._layout)
        for button in list(self._group.buttons()):
            self._group.removeButton(button)
        self._buttons = {}

        for scope in scopes:
            label = scope["label"]
            count = scope.get("count")
            text = f"{label}    {count}" if count is not None else label
            button = QPushButton(text, self)
            button.setObjectName("entries-scope-item")
            button.setCheckable(True)
            button.setFlat(True)
            button.setChecked(scope["key"] == active_key)
            button.clicked.connect(lambda _checked=False, key=scope["key"]: self.scope_selected.emit(key))
            self._group.addButton(button)
            self._buttons[scope["key"]] = button
            self._layout.addWidget(button)


class _EntryEditorDialog(QDialog):
    """P5 Focused Editor (DESIGN.md § 10: "focused multi-field edit with
    clear Save/Cancel and moderate complexity -> modal / focused dialog").
    One class handles both Add (``entry_id is None``) and Edit -- the
    template picker is only editable while adding; current core has no
    template-switch operation, so Edit always keeps the entry's existing
    template (M17 Feature 4 prompt § 8)."""

    def __init__(self, controller: EntriesController, entry_id: int | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entries-editor-dialog")
        self.setWindowTitle("Add Entry" if entry_id is None else "Edit Entry")
        self.setMinimumWidth(480)

        self._controller = controller
        self._entry_id = entry_id
        self._field_inputs: dict[str, QWidget] = {}
        self._collection_checks: dict[int, QCheckBox] = {}
        self._detail = controller.entry_detail(entry_id) if entry_id is not None else None

        layout = QVBoxLayout(self)

        top_form = QFormLayout()
        self._template_combo = QComboBox(self)
        for template in controller.template_options():
            self._template_combo.addItem(template["name"], template["id"])
        top_form.addRow("Template", self._template_combo)

        self._language_combo = QComboBox(self)
        self._language_combo.addItems(sorted(VALID_LANGUAGES))
        top_form.addRow("Language", self._language_combo)

        self._explanation_language_combo = QComboBox(self)
        self._explanation_language_combo.addItems(sorted(VALID_EXPLANATION_LANGUAGES))
        top_form.addRow("Explanation language", self._explanation_language_combo)

        self._entry_type_combo = QComboBox(self)
        self._entry_type_combo.addItems(sorted(VALID_ENTRY_TYPES))
        top_form.addRow("Entry type", self._entry_type_combo)

        self._status_combo = QComboBox(self)
        self._status_combo.addItems(sorted(VALID_STATUSES))
        top_form.addRow("Status", self._status_combo)
        layout.addLayout(top_form)

        self._fields_form = QFormLayout()
        layout.addLayout(self._fields_form)

        self._manual_term_input = QLineEdit(self)
        self._manual_term_row_label = QLabel("Canonical term", self)
        self._manual_meaning_input = QLineEdit(self)
        self._manual_meaning_row_label = QLabel("Canonical meaning", self)
        manual_form = QFormLayout()
        manual_form.addRow(self._manual_term_row_label, self._manual_term_input)
        manual_form.addRow(self._manual_meaning_row_label, self._manual_meaning_input)
        layout.addLayout(manual_form)

        collections_heading = QLabel("Collections", self)
        collections_heading.setObjectName("entries-editor-collections-heading")
        layout.addWidget(collections_heading)
        self._collections_container = QWidget(self)
        collections_layout = QVBoxLayout(self._collections_container)
        collections_layout.setContentsMargins(0, 0, 0, 0)
        collections_layout.setSpacing(2)
        current_collection_ids = set(controller.get_entry_collection_ids(entry_id)) if entry_id is not None else set()
        options = controller.collection_options()
        if not options:
            collections_layout.addWidget(_message_label("No Collections yet."))
        for collection in options:
            checkbox = QCheckBox(f"{collection['name']} ({collection['entry_count']})", self._collections_container)
            checkbox.setChecked(collection["id"] in current_collection_ids)
            self._collection_checks[collection["id"]] = checkbox
            collections_layout.addWidget(checkbox)
        layout.addWidget(self._collections_container)

        self._error_label = QLabel("", self)
        self._error_label.setObjectName("entries-editor-error")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        save_button = QPushButton("Save", self)
        save_button.setObjectName("entries-editor-save-button")
        save_button.clicked.connect(self._on_save)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

        if entry_id is None:
            default_id = controller.default_template_id()
            if default_id is not None:
                index = self._template_combo.findData(default_id)
                if index >= 0:
                    self._template_combo.setCurrentIndex(index)
            self._template_combo.currentIndexChanged.connect(self._rebuild_template_fields)
        else:
            self._template_combo.setEnabled(False)
            index = self._template_combo.findData(self._detail["template_id"])
            if index >= 0:
                self._template_combo.setCurrentIndex(index)
            self._language_combo.setCurrentText(self._detail.get("language") or "")
            self._explanation_language_combo.setCurrentText(self._detail.get("explanation_language") or "")
            self._entry_type_combo.setCurrentText(self._detail.get("entry_type") or "")
            self._status_combo.setCurrentText(self._detail.get("status") or "")

        self._rebuild_template_fields()

    def _current_template_id(self) -> int:
        return self._template_combo.currentData()

    def _rebuild_template_fields(self) -> None:
        template_id = self._current_template_id()
        if template_id is None:
            return
        _clear_form_layout(self._fields_form)
        self._field_inputs = {}

        prefill: dict[str, str] = {}
        if self._detail is not None:
            prefill = {key: values["field_value"] for key, values in (self._detail.get("template_values") or {}).items()}

        for field in self._controller.template_fields(template_id):
            key = field["field_key"]
            if field["field_type"] == "long_text":
                widget: QWidget = QPlainTextEdit(self)
                widget.setPlainText(prefill.get(key, ""))
                widget.setFixedHeight(60)
            else:
                widget = QLineEdit(self)
                widget.setText(prefill.get(key, ""))
            label_text = field["field_label"] + (" *" if field["required"] else "")
            self._fields_form.addRow(label_text, widget)
            self._field_inputs[key] = widget

        mapping = self._controller.canonical_mapping(template_id)
        self._manual_term_row_label.setVisible(mapping["needs_manual_term"])
        self._manual_term_input.setVisible(mapping["needs_manual_term"])
        self._manual_meaning_row_label.setVisible(mapping["needs_manual_meaning"])
        self._manual_meaning_input.setVisible(mapping["needs_manual_meaning"])
        if self._entry_id is None:
            self._manual_term_input.clear()
            self._manual_meaning_input.clear()
        else:
            self._manual_term_input.setText(str(self._detail.get("term") or "") if mapping["needs_manual_term"] else "")
            self._manual_meaning_input.setText(str(self._detail.get("meaning") or "") if mapping["needs_manual_meaning"] else "")

    @staticmethod
    def _read_field(widget: QWidget) -> str:
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        return widget.text()

    def _on_save(self) -> None:
        self._error_label.setText("")
        entry_data = {
            "template_id": self._current_template_id(),
            "language": self._language_combo.currentText(),
            "explanation_language": self._explanation_language_combo.currentText(),
            "entry_type": self._entry_type_combo.currentText(),
            "status": self._status_combo.currentText(),
        }
        template_values = {key: self._read_field(widget) for key, widget in self._field_inputs.items()}
        manual_term = self._manual_term_input.text().strip()
        manual_meaning = self._manual_meaning_input.text().strip()
        collection_ids = [collection_id for collection_id, checkbox in self._collection_checks.items() if checkbox.isChecked()]

        if self._entry_id is None:
            entry_id, errors = self._controller.create_entry(entry_data, template_values, manual_term, manual_meaning, collection_ids)
            if errors:
                self._error_label.setText("\n".join(errors))
                return
            self.accept()
            return

        errors = self._controller.update_entry_core(self._entry_id, entry_data, template_values, manual_term, manual_meaning)
        if errors:
            self._error_label.setText("\n".join(errors))
            return
        self._sync_collections(collection_ids, confirm_cross_card=False)

    def _sync_collections(self, collection_ids: list[int], *, confirm_cross_card: bool) -> None:
        try:
            self._controller.sync_entry_collections(self._entry_id, collection_ids, confirm_cross_card=confirm_cross_card)
        except CrossCardMoveConfirmationRequired:
            if _confirm_cross_card_reorganization(self):
                self._sync_collections(collection_ids, confirm_cross_card=True)
            return
        self._controller.finish_edit()
        self.accept()


class _QuickAddDialog(QDialog):
    """P6 bounded utility: the structured-text-card Quick Add flow, still
    genuinely live product behavior (M17 Feature 4 prompt § 7) -- migrated
    as-is, not expanded into Import/Export. Validation errors leave the
    pasted text untouched (same widget instance, never cleared on error)."""

    _PLACEHOLDER = (
        "language: English\n"
        "explanation_language: Chinese\n"
        "entry_type: phrase\n"
        "term: cope with stress\n"
        "meaning: cope with pressure or difficulty\n"
        "example: She learned to cope with stress during exam season.\n"
        "notes: \n"
        "tags: \n"
        "source: \n"
        "status: new\n"
        "collections: IELTS Core; Proficient Pool"
    )

    def __init__(self, controller: EntriesController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entries-quick-add-dialog")
        self.setWindowTitle("Quick Add")
        self.setMinimumWidth(420)
        self._controller = controller

        layout = QVBoxLayout(self)
        hint = QLabel("Paste a structured Entry card (one field per line).", self)
        layout.addWidget(hint)

        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setPlaceholderText(self._PLACEHOLDER)
        self._text_edit.setFixedHeight(220)
        layout.addWidget(self._text_edit)

        self._error_label = QLabel("", self)
        self._error_label.setObjectName("entries-editor-error")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        create_button = QPushButton("Create", self)
        create_button.setObjectName("entries-quick-add-create-button")
        create_button.clicked.connect(self._on_create)
        buttons.addWidget(create_button)
        layout.addLayout(buttons)

    def _on_create(self) -> None:
        self._error_label.setText("")
        _entry_id, errors = self._controller.quick_add(self._text_edit.toPlainText())
        if errors:
            self._error_label.setText("\n".join(errors))
            return
        self.accept()


def _confirm_cross_card_reorganization(parent: QWidget) -> bool:
    """Reuses ``CROSS_CARD_CONFIRMATION_MESSAGE`` verbatim (``src.collections``)
    -- the exact copy already approved for this warning, not reworded here
    (M17 Feature 4 prompt § 9)."""
    result = QMessageBox.question(
        parent,
        "Confirm Card Reorganization",
        CROSS_CARD_CONFIRMATION_MESSAGE,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return result == QMessageBox.StandardButton.Yes


def _detail_field(caption_text: str, value_text: str, secondary: str = "") -> QWidget:
    block = QWidget()
    layout = QVBoxLayout(block)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    caption = QLabel(caption_text, block)
    caption.setObjectName("entries-detail-caption")
    layout.addWidget(caption)

    value = QLabel(value_text or "—", block)
    value.setObjectName("entries-detail-value")
    value.setWordWrap(True)
    layout.addWidget(value)

    if secondary:
        secondary_label = QLabel(secondary, block)
        secondary_label.setObjectName("entries-detail-secondary")
        secondary_label.setWordWrap(True)
        layout.addWidget(secondary_label)

    return block


def _message_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("entries-empty-state")
    label.setWordWrap(True)
    return label


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _clear_form_layout(form: QFormLayout) -> None:
    while form.rowCount():
        form.removeRow(0)

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QRect, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QStyleOptionButton,
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
                             `src.collections`); a first-stage confirm
                             (copy distinguishes permanent Vocabulary-App
                             deletion from removing an Entry only from the
                             current Collection -- M17 Feature 4 corrective
                             pass § 9) always precedes the call, and if the
                             core additionally requires Card-reorganization
                             confirmation, `CROSS_CARD_CONFIRMATION_MESSAGE`
                             (reused verbatim, not reworded) is shown before
                             retrying with ``confirm_cross_card=True``. There
                             is no silent-delete path.

Corrective pass (M17_Feature4_Entries_Corrective_Pass.md), on top of the
above:

  scope/table boundary    -> a bounded, user-resizable `QSplitter`
                             replaces the rigid fixed-width Scope Pane
                             (§ 4); the pane still can never out-grow the
                             Table (`SCOPE_PANE_MAX_WIDTH`).
  Scope Pane sections      -> `_ScopePane` now renders an explicit
                             "Scope" heading (All Entries + the three
                             system collections), a divider, then an
                             explicit "Collections" heading for real user
                             Collections (§ 8) -- still read-only browse
                             scopes, no Collection management here.
  toolbar / batch bar      -> batch actions moved off the search row into
                             their own conditional row beneath it, so
                             selecting rows can never squeeze search into
                             an unusable sliver (§ 3); the search field
                             also keeps an explicit minimum width.
  checkbox selection        -> `EntriesTableModel` renders a leading
                             checkbox column and a header-level "select
                             all visible" affordance (`_CheckableHeaderView`);
                             both are pure views onto
                             `EntriesController.checked_ids` (renamed from
                             `selected_ids` in the Minimum Collection
                             Integration corrective pass below) --
                             toggling a checkbox or the header updates
                             that same set, never a second selection
                             state (§ 7).
  Add to Collection         -> the menu is now anchored below the button
                             (`mapToGlobal(...bottomLeft())`) instead of
                             at `QCursor.pos()`, which on Windows could
                             make the just-opened popup dismiss itself
                             before a click landed on an item -- a real
                             interaction defect, not merely a contrast
                             one (§ 6).

M17 Minimum Collection Integration corrective pass
(M17_Minimum_Collection_Integration_Corrective_Pass.md), on top of both
of the above:

  focused vs checked        -> row inspection and batch selection are now
                             two independent truths
                             (`EntriesController.focused_id`/`checked_ids`,
                             § 5/§ 6). A plain click sets `focused_id` via
                             `QItemSelectionModel.currentRowChanged`
                             (native "current row", never the multi-row
                             "selected" set) and never touches
                             `checked_ids`. The checkbox column/header
                             remain the primary way to build `checked_ids`
                             non-contiguously; Ctrl/Shift native selection
                             is kept only as an optional convenience that
                             *unions* into `checked_ids` (gated on
                             `QApplication.keyboardModifiers()` so a plain
                             click never auto-checks a row) -- native
                             selection itself is always driven back out of
                             `checked_ids` (`_restore_table_selection`),
                             never a second competing truth.
  visual states              -> checked rows keep the existing strong
                             `::item:selected` QSS treatment (native
                             selection mirrors `checked_ids` exactly);
                             focused-but-unchecked rows get a distinct,
                             lighter translucent tint painted by the model
                             itself via `Qt.ItemDataRole.BackgroundRole`
                             (§ 7) -- the two states can never be
                             confused, and a row that is both simply shows
                             the stronger checked treatment.
  bottom detail              -> now follows `focused_id`, independent of
                             how many Entries are checked (§ 8): it never
                             collapses into a bare "N selected" message
                             again. A compact "N checked" line appears
                             only as secondary status alongside the real
                             focused-Entry detail. Edit acts on
                             `focused_id`; batch actions act on
                             `checked_ids`.
  Star column                -> a direct per-row Starred toggle (§ 9/§ 10)
                             next to the checkbox column, reusing the
                             existing `add_entries_to_system_collection`/
                             `remove_entries_from_system_collection`
                             core (never a duplicated membership write),
                             including the `CrossCardMoveConfirmationRequired`
                             safety gate on unstar. "Starred" scope/
                             Collections-Navigator/Today labels get a "★ "
                             prefix as a presentation-only touch (§ 12) --
                             `system_type = "starred"` is untouched.
"""

SCOPE_PANE_DEFAULT_WIDTH = 220
SCOPE_PANE_MIN_WIDTH = 160
SCOPE_PANE_MAX_WIDTH = 420


class EntriesView(QWidget):
    def __init__(self, controller: EntriesController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entries-root")
        self._controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("entries-splitter")
        splitter.setChildrenCollapsible(False)

        self._scope_pane = _ScopePane(self)
        self._scope_pane.setMinimumWidth(SCOPE_PANE_MIN_WIDTH)
        self._scope_pane.setMaximumWidth(SCOPE_PANE_MAX_WIDTH)
        self._scope_pane.scope_selected.connect(self._on_scope_selected)
        splitter.addWidget(self._scope_pane)

        main = QWidget(self)
        main.setObjectName("entries-main-workspace")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)
        main_layout.setSpacing(SPACING.md)

        main_layout.addWidget(self._build_toolbar())

        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(controller.model)

        self._checkable_header = _CheckableHeaderView(self)
        self._checkable_header.toggled.connect(self._on_header_toggled)

        self._table = QTableView(self)
        self._table.setObjectName("entries-table")
        self._table.setModel(self._proxy)
        self._table.setHorizontalHeader(self._checkable_header)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setMouseTracking(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        select_column = self._controller.model.COLUMNS.index(self._controller.model.SELECT_COLUMN)
        self._star_column = self._controller.model.COLUMNS.index(self._controller.model.STAR_COLUMN)
        self._table.horizontalHeader().resizeSection(select_column, 32)
        self._table.horizontalHeader().setSectionResizeMode(select_column, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().resizeSection(self._star_column, 32)
        self._table.horizontalHeader().setSectionResizeMode(self._star_column, QHeaderView.ResizeMode.Fixed)
        self._table.verticalHeader().setVisible(False)
        main_layout.addWidget(self._table, 1)

        self._detail_container = QWidget(self)
        self._detail_container.setObjectName("entries-detail")
        self._detail_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._detail_layout = QHBoxLayout(self._detail_container)
        self._detail_layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        self._detail_layout.setSpacing(SPACING.lg)
        main_layout.addWidget(self._detail_container, 0)

        splitter.addWidget(main)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setSizes([SCOPE_PANE_DEFAULT_WIDTH, 800])
        root.addWidget(splitter, 1)

        selection_model = self._table.selectionModel()
        if selection_model is not None:
            selection_model.currentRowChanged.connect(self._on_table_current_row_changed)
            selection_model.selectionChanged.connect(self._on_table_selection_changed)
        controller.model.checkbox_toggled.connect(self._on_row_checkbox_toggled)
        self._table.clicked.connect(self._on_table_cell_clicked)

        controller.rows_changed.connect(self._on_rows_changed)
        controller.scopes_changed.connect(self._on_scopes_changed)
        controller.checked_changed.connect(self._on_checked_changed)
        controller.focused_changed.connect(self._on_focused_changed)

    def refresh(self) -> None:
        self._controller.refresh_scopes()
        self._controller.refresh()

    def apply_theme_tokens(self, tokens) -> None:
        """The one non-QSS-driven live-theme seam this checkpoint needs
        (``theme_manager.py`` module docstring): the Star column's fill
        color is a custom ``QAbstractItemModel`` data role, not QSS, so it
        does not repaint itself when the application stylesheet changes.
        ``MainWindow`` calls this once at startup and again on every
        ``ThemeManager.theme_applied`` emission."""
        self._controller.model.set_star_color(QColor(tokens.semantic.star.background))

    # -- toolbar -------------------------------------------------------------

    def _build_toolbar(self) -> QWidget:
        """Two-row toolbar (M17 Feature 4 corrective pass § 3): row 1 is
        always visible (title/search/filters/Quick Add/Add Entry) and
        never competes for space with batch actions, which live in
        ``self._batch_bar`` -- a second row shown only while rows are
        selected, so search never collapses into an unusable sliver."""
        container = QWidget(self)
        container.setObjectName("entries-toolbar-container")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(SPACING.sm)

        bar = QWidget(container)
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
        self._search_input.setMinimumWidth(220)
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

        quick_add_button = QPushButton("Quick Add", bar)
        quick_add_button.setObjectName("entries-quick-add-button")
        quick_add_button.clicked.connect(self._open_quick_add)
        layout.addWidget(quick_add_button, 0)

        add_button = QPushButton("Add Entry", bar)
        add_button.setObjectName("entries-add-button")
        add_button.clicked.connect(self._open_add_entry)
        layout.addWidget(add_button, 0)

        outer.addWidget(bar)

        self._batch_bar = QWidget(container)
        self._batch_bar.setObjectName("entries-batch-bar")
        batch_layout = QHBoxLayout(self._batch_bar)
        batch_layout.setContentsMargins(SPACING.sm, SPACING.xs, SPACING.sm, SPACING.xs)
        batch_layout.setSpacing(SPACING.sm)

        self._batch_count_label = QLabel("", self._batch_bar)
        self._batch_count_label.setObjectName("entries-batch-count-label")
        batch_layout.addWidget(self._batch_count_label, 0)
        batch_layout.addStretch(1)

        self._star_button = QPushButton("★ Star", self._batch_bar)
        self._star_button.setObjectName("entries-batch-star-button")
        self._star_button.clicked.connect(self._on_add_to_starred)
        batch_layout.addWidget(self._star_button, 0)

        self._collection_button = QPushButton("Add to Collection ▾", self._batch_bar)
        self._collection_button.setObjectName("entries-batch-collection-button")
        self._collection_button.clicked.connect(self._open_add_to_collection_menu)
        batch_layout.addWidget(self._collection_button, 0)

        self._delete_button = QPushButton("Delete", self._batch_bar)
        self._delete_button.setObjectName("entries-batch-delete-button")
        self._delete_button.setProperty("destructive", "true")
        self._delete_button.clicked.connect(self._on_delete_selected)
        batch_layout.addWidget(self._delete_button, 0)

        outer.addWidget(self._batch_bar)
        self._set_batch_actions_visible(False)

        return container

    @staticmethod
    def _build_filter_combo(object_name: str, values: set[str] | frozenset[str]) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(object_name)
        combo.addItem("All")
        combo.addItems(sorted(values))
        return combo

    def _set_batch_actions_visible(self, visible: bool) -> None:
        self._batch_bar.setVisible(visible)
        if visible:
            count = len(self._controller.checked_ids)
            noun = "Entry" if count == 1 else "Entries"
            self._batch_count_label.setText(f"{count} {noun} checked")

    # -- scope / filter reactions --------------------------------------------

    def _on_scope_selected(self, scope_key: str) -> None:
        self._controller.set_scope(scope_key)

    def _on_search_submitted(self) -> None:
        self._controller.set_search_text(self._search_input.text())

    def _on_scopes_changed(self) -> None:
        self._scope_pane.render(self._controller.scopes, self._controller.scope)

    def _on_rows_changed(self, _count: int) -> None:
        self._restore_table_selection()

    # -- table selection: focused_id vs checked_ids (M17 Minimum
    # Collection Integration corrective pass § 5/§ 6) -----------------------

    def _on_table_current_row_changed(self, current, _previous) -> None:
        """A plain row click/keyboard-navigation change (Qt's "current
        index", independent of the multi-row "selected" set) sets
        ``focused_id`` only -- it never touches ``checked_ids``."""
        if not current.isValid():
            return
        source_index = self._proxy.mapToSource(current)
        entry = self._controller.model.row_at(source_index.row())
        if entry is not None:
            self._controller.set_focused_id(entry["id"])

    def _on_table_selection_changed(self, *_args: object) -> None:
        """Ctrl/Shift native multi-row selection remains an *optional*
        convenience that unions into ``checked_ids`` -- gated on an actual
        modifier being held, so a plain click (which Qt also reports here
        as a 1-row "selection") never silently checks a row (§ 5/§ 6)."""
        modifiers = QApplication.keyboardModifiers()
        if not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
            return
        selection_model = self._table.selectionModel()
        if selection_model is None:
            return
        ids = set(self._controller.checked_ids)
        for proxy_index in selection_model.selectedRows():
            source_index = self._proxy.mapToSource(proxy_index)
            entry = self._controller.model.row_at(source_index.row())
            if entry is not None:
                ids.add(entry["id"])
        self._controller.set_checked_ids(ids)

    def _restore_table_selection(self) -> None:
        """Native ``QItemSelectionModel`` selection is always driven back
        out of ``checked_ids`` -- it is presentation only, never a second
        competing batch-selection truth (§ 6)."""
        selection_model = self._table.selectionModel()
        if selection_model is None:
            return
        selection_model.blockSignals(True)
        selection_model.clearSelection()
        for source_row, entry in enumerate(self._controller.model.rows()):
            if entry["id"] in self._controller.checked_ids:
                source_index = self._controller.model.index(source_row, 0)
                proxy_index = self._proxy.mapFromSource(source_index)
                selection_model.select(
                    proxy_index,
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )
        selection_model.blockSignals(False)

    def _on_row_checkbox_toggled(self, entry_id: int, checked: bool) -> None:
        """Checkbox column click -- the primary way to build
        ``checked_ids`` non-contiguously, with no Ctrl/Shift required
        (§ 5)."""
        ids = set(self._controller.checked_ids)
        if checked:
            ids.add(entry_id)
        else:
            ids.discard(entry_id)
        self._controller.set_checked_ids(ids)

    def _on_table_cell_clicked(self, proxy_index) -> None:
        source_index = self._proxy.mapToSource(proxy_index)
        if source_index.column() != self._star_column:
            return
        entry = self._controller.model.row_at(source_index.row())
        if entry is not None:
            self._toggle_star(entry["id"], confirm_cross_card=False)

    def _on_header_toggled(self, checked: bool) -> None:
        """Header "select all" affordance (§ 5): checks/clears every row
        currently visible under the active scope/search/filters, not the
        entire database."""
        if checked:
            ids = {row["id"] for row in self._controller.model.rows()}
        else:
            ids = set()
        self._controller.set_checked_ids(ids)

    def _update_header_checkbox_state(self) -> None:
        rows = self._controller.model.rows()
        all_checked = bool(rows) and all(row["id"] in self._controller.checked_ids for row in rows)
        self._checkable_header.set_checked(all_checked)

    def _on_checked_changed(self, _entries: list[dict]) -> None:
        self._set_batch_actions_visible(bool(self._controller.checked_ids))
        self._controller.model.set_checked_ids(self._controller.checked_ids)
        self._restore_table_selection()
        self._update_header_checkbox_state()
        self._render_detail()

    def _on_focused_changed(self, _entry: dict | None) -> None:
        self._controller.model.set_focused_id(self._controller.focused_id)
        self._render_detail()

    # -- bottom detail -------------------------------------------------------

    def _render_detail(self) -> None:
        """Follows ``focused_id`` only -- never collapses into a bare "N
        checked" message regardless of how many Entries are checked (§ 8).
        A compact checked-count line appears as secondary status
        alongside the real focused-Entry detail, not instead of it."""
        _clear_layout(self._detail_layout)

        entry = self._controller.focused_entry()
        checked_count = len(self._controller.checked_ids)

        if entry is None:
            self._detail_layout.addWidget(_message_label("Choose a row to see details."))
            if checked_count:
                self._detail_layout.addWidget(_message_label(f"{checked_count} checked."))
            return

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

        if checked_count > 1:
            self._detail_layout.addWidget(_detail_field("Checked", f"{checked_count} Entries"))

        self._detail_layout.addStretch(1)

        edit_button = QPushButton("Edit", self._detail_container)
        edit_button.setObjectName("entries-detail-edit-button")
        edit_button.clicked.connect(lambda: self._open_edit_entry(entry["id"]))
        self._detail_layout.addWidget(edit_button, 0, Qt.AlignmentFlag.AlignVCenter)

    # -- Star (§ 9/§ 10) -------------------------------------------------

    def _toggle_star(self, entry_id: int, *, confirm_cross_card: bool) -> None:
        try:
            self._controller.toggle_star(entry_id, confirm_cross_card=confirm_cross_card)
        except CrossCardMoveConfirmationRequired:
            if _confirm_cross_card_reorganization(self):
                self._toggle_star(entry_id, confirm_cross_card=True)

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

    def _build_add_to_collection_menu(self) -> QMenu:
        """Split out from ``_open_add_to_collection_menu`` so tests can
        build and trigger actions without going through the blocking
        ``QMenu.exec()`` call (M17 Feature 4 corrective pass § 6/§ 11)."""
        menu = QMenu(self)
        menu.setObjectName("entries-add-to-collection-menu")
        options = self._controller.collection_options()
        if not options:
            action = menu.addAction("No Collections yet")
            action.setEnabled(False)
        for collection in options:
            action = menu.addAction(collection["name"])
            action.triggered.connect(
                lambda _checked=False, collection_id=collection["id"]: self._on_add_to_collection_triggered(collection_id)
            )
        return menu

    def _on_add_to_collection_triggered(self, collection_id: int) -> None:
        self._controller.add_selected_to_collection(collection_id)

    def _open_add_to_collection_menu(self) -> None:
        menu = self._build_add_to_collection_menu()
        # Anchored below the button rather than at QCursor.pos(): exec()-ing
        # a popup directly under a mouse position that was *just* released
        # is a known Qt/Windows interaction bug where the popup opens and
        # immediately dismisses itself before any item can be clicked --
        # this read to human review as "the actions cannot actually be
        # selected" even though every enabled QAction was fully wired and
        # functional (M17 Feature 4 corrective pass § 6).
        global_point = self._collection_button.mapToGlobal(self._collection_button.rect().bottomLeft())
        menu.exec(global_point)

    def _on_delete_selected(self) -> None:
        count = len(self._controller.checked_ids)
        if not count:
            return
        # Copy explicitly distinguishes a permanent Vocabulary App delete
        # (removes the Entry from every Collection) from merely removing
        # it from the current Collection -- inside a Collection-scoped
        # Entries view "Delete" alone reads ambiguously (M17 Feature 4
        # corrective pass § 9).
        if count == 1:
            message = (
                "Permanently delete this Entry from Vocabulary App?\n\n"
                "This removes it from all Collections. This is not the same "
                "as removing it only from the current Collection.\n\n"
                "This action cannot be undone."
            )
        else:
            message = (
                f"Permanently delete these {count} Entries from Vocabulary App?\n\n"
                "This removes them from all Collections. This is not the same "
                "as removing them only from the current Collection.\n\n"
                "This action cannot be undone."
            )
        confirmed = QMessageBox.question(
            self,
            "Delete Entries",
            message,
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
    M17 minimum Collection Integration checkpoint.

    Corrective pass § 8: system scopes render under an explicit "Scope"
    heading and real user Collections under a separate "Collections"
    heading with a divider between them, matching the canonical
    reference's information hierarchy instead of one flat list."""

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

        system_scopes = [scope for scope in scopes if scope["key"] == SCOPE_ALL or scope["key"].startswith("system:")]
        collection_scopes = [scope for scope in scopes if scope["key"].startswith("collection:")]

        self._layout.addWidget(_scope_heading("Scope"))
        for scope in system_scopes:
            self._add_scope_button(scope, active_key)

        if collection_scopes:
            self._layout.addWidget(_scope_divider())
            self._layout.addWidget(_scope_heading("Collections"))
            for scope in collection_scopes:
                self._add_scope_button(scope, active_key)

    def _add_scope_button(self, scope: dict, active_key: str) -> None:
        # "★ " prefix on the Starred scope is presentation-only (M17
        # Minimum Collection Integration corrective pass § 12) --
        # system_type "starred" is untouched.
        label = f"★ {scope['label']}" if scope["key"] == "system:starred" else scope["label"]
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


def _scope_heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("entries-scope-heading")
    return label


def _scope_divider() -> QWidget:
    divider = QWidget()
    divider.setObjectName("entries-scope-divider")
    divider.setFixedHeight(1)
    divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return divider


class _CheckableHeaderView(QHeaderView):
    """Header-level "select all visible" affordance for the checkbox
    column (M17 Feature 4 corrective pass § 7). Paints/toggles a checkbox
    over section 0; the real batch-selection truth stays in
    ``EntriesController.checked_ids`` -- this view only mirrors/requests
    it through the ``toggled`` signal, never owns it."""

    toggled = Signal(bool)

    _BOX_SIZE = 16

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._checked = False
        self.setSectionsClickable(True)

    def set_checked(self, checked: bool) -> None:
        if checked != self._checked:
            self._checked = checked
            self.updateSection(0)

    def _checkbox_rect(self, section_rect: QRect) -> QRect:
        return QRect(
            section_rect.x() + max(0, (section_rect.width() - self._BOX_SIZE) // 2),
            section_rect.y() + max(0, (section_rect.height() - self._BOX_SIZE) // 2),
            self._BOX_SIZE,
            self._BOX_SIZE,
        )

    def paintSection(self, painter, rect, logicalIndex) -> None:  # noqa: N802 (Qt API)
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex != 0:
            return
        option = QStyleOptionButton()
        option.rect = self._checkbox_rect(rect)
        option.state = QStyle.StateFlag.State_Enabled | (
            QStyle.StateFlag.State_On if self._checked else QStyle.StateFlag.State_Off
        )
        self.style().drawControl(QStyle.ControlElement.CE_CheckBox, option, painter)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if self.logicalIndexAt(position) == 0:
            section_rect = QRect(self.sectionViewportPosition(0), 0, self.sectionSize(0), self.height())
            if self._checkbox_rect(section_rect).contains(position):
                self.toggled.emit(not self._checked)
                return
        super().mousePressEvent(event)


class _EntryEditorDialog(QDialog):
    """P5 Focused Editor (DESIGN.md § 10: "focused multi-field edit with
    clear Save/Cancel and moderate complexity -> modal / focused dialog").
    One class handles both Add (``entry_id is None``) and Edit -- the
    template picker is only editable while adding; current core has no
    template-switch operation, so Edit always keeps the entry's existing
    template (M17 Feature 4 prompt § 8).

    Corrective pass § 5: the form body (template/meta fields, dynamic
    template fields, manual canonical fields, Collections checklist) lives
    inside a ``QScrollArea`` so a template with many fields/long-text
    fields/many Collections can exceed the screen height without pushing
    Save/Cancel off-screen -- only the scrollable body grows or shrinks;
    the error label and Save/Cancel footer stay pinned outside it."""

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

        scroll = QScrollArea(self)
        scroll.setObjectName("entries-editor-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(SPACING.md)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

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
        body_layout.addLayout(top_form)

        self._fields_form = QFormLayout()
        body_layout.addLayout(self._fields_form)

        self._manual_term_input = QLineEdit(self)
        self._manual_term_row_label = QLabel("Canonical term", self)
        self._manual_meaning_input = QLineEdit(self)
        self._manual_meaning_row_label = QLabel("Canonical meaning", self)
        manual_form = QFormLayout()
        manual_form.addRow(self._manual_term_row_label, self._manual_term_input)
        manual_form.addRow(self._manual_meaning_row_label, self._manual_meaning_input)
        body_layout.addLayout(manual_form)

        collections_heading = QLabel("Collections", self)
        collections_heading.setObjectName("entries-editor-collections-heading")
        body_layout.addWidget(collections_heading)
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
        body_layout.addWidget(self._collections_container)
        body_layout.addStretch(1)

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

        self._bound_height_to_screen()

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

    def _bound_height_to_screen(self) -> None:
        """Respects available screen geometry (§ 5): the dialog never
        requests a height beyond what the current screen can show, so the
        scroll area -- not the window -- absorbs long template/Collections
        content."""
        screen = self.screen() if hasattr(self, "screen") else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(560, 640)
            return
        available = screen.availableGeometry()
        max_height = max(360, int(available.height() * 0.9))
        self.setMaximumHeight(max_height)
        self.resize(560, min(700, max_height))

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

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.collections import (
    CARD_PAGE_SIZE_OPTIONS,
    COLLECTION_DELETE_CONFIRMATION,
    COLLECTION_DELETE_WARNING,
    CROSS_CARD_CONFIRMATION_MESSAGE,
    CrossCardMoveConfirmationRequired,
)
from src.ui_desktop.controllers.collections_controller import CollectionsController
from src.ui_desktop.state.handoff import EntriesScopeIntent, StudyTargetIntent
from src.ui_desktop.theming.metrics import SPACING

"""
Collections Navigator / Collection Context -- Minimum M17 Collection
Integration (DESIGN.md § 6.8, Class B "inherited from the invoking A/B
surface"). Not a Collection Manager: read-only navigation/context plus two
typed handoffs into already Human Accepted workflows.

Design -> Implementation trace (full Design Derivation Record in
DESIGN.md § 6.8):

  shell/chrome           -> ordinary Management Mode workspace, shared
                             Management Rail stays visible (no Study
                             chrome swap here -- "Open in Study" triggers
                             Review's own chrome swap instead).
  composition             -> Management Rail -> left selector pane
                             (_CollectionsListPane: "Collections" section,
                             divider, "Practice Pools" section) -> right
                             read-only detail (selected Collection's
                             factual metadata + compact Card list, or a
                             pool's factual summary) with handoff actions.
  dominance               -> the selector pane drives the surface; detail
                             is subordinate factual context, never an
                             editor.
  Collections vs Pools    -> CollectionsController keeps two separate
                             lists throughout (never one flat mixed list),
                             mirroring the same semantic separation
                             EntriesController/_ScopePane already
                             established for the Scope Pane.
  Open Entries            -> emits ``EntriesScopeIntent`` (state/handoff.py)
                             carrying Entries' own existing scope key
                             (``collection:<id>`` / ``system:<type>``) --
                             MainWindow hands it straight to
                             ``EntriesController.set_scope()``; no second
                             Collection-filter implementation here.
  Open in Study           -> emits ``StudyTargetIntent`` (collection_id,
                             card_number); MainWindow calls the existing
                             ``ReviewController.open_card(...)`` -- never
                             ``open_default()`` once a specific Card target
                             is supplied, and never a silent fallback if
                             the Card is gone by the time the handoff is
                             consumed.
  no Quiz launcher here    -> Quiz is only ever reached through Review's
                             existing Quick Quiz / Choose Quiz Type
                             affordances after "Open in Study" -- this
                             surface never talks to src.quiz directly.

Corrective pass (M17_Minimum_Collection_Integration_Corrective_Pass.md
§ 2-4): a Collection's Card list is no longer rendered in full. A compact
control row (Sort by / Cards per page / Previous / page indicator / Next)
sits above a `QScrollArea` holding only the current page's Card rows --
`CollectionsController.current_card_page()` reads exactly one page
through the new paged core query, so opening a Collection with thousands
of Entries never constructs a widget (or reads an Entry row) for every
Card up front.

---

M18.1 Collection Manager + Card Organization -- Design Derivation Record
(DESIGN.md § 7.3 "Collection Manager: B, P2 Table-First Manager" /
"Card Organization Workspace: B, P2 + P5"; § 9, since the exact local
composition is not fully obvious from the parent patterns alone):

  1. Interaction Mode        -> Management.
  2. Parent Pattern          -> P2 (this workspace, unchanged) + P5 Focused
                                 Editor for Collection create/edit + P6
                                 Utility/Dialog for destructive delete and
                                 Card Organization's remove/move actions.
  3. Primary User Task       -> create/rename/edit/delete a Collection;
                                 rename a Card; remove or reposition
                                 Entries within a Collection.
  4. Spatial Composition     -> unchanged Management Rail -> selector pane
                                 -> detail pane, now with a "New
                                 Collection" action atop the selector pane
                                 and "Edit"/"Delete"/"Organize Entries"
                                 actions plus a per-Card "Rename" action in
                                 the existing read-only detail composition.
  5. Dominance Rule          -> unchanged: selector pane drives the
                                 surface; new editors are bounded P5/P6
                                 dialogs that never permanently distort
                                 this Table-First Manager.
  6. Density Rule            -> inherits existing Management Mode density
                                 (matches Entries' `_EntryEditorDialog`).
  7. Surface Hierarchy       -> unchanged detail/selector surface roles;
                                 dialogs use the same `surface_primary`
                                 modal treatment as Entries' editor.
  8. Action Hierarchy        -> primary = New Collection / Edit / Organize
                                 Entries (accent-primary, matching Entries'
                                 Add/Edit treatment); destructive = Delete
                                 Collection and Remove Entries (P6
                                 destructive confirmation); secondary =
                                 Rename Card, Move Entry.
  9. Editing Container       -> Collection create/edit = P5 modal
                                 (`_CollectionEditorDialog`, three bounded
                                 fields, Save/Cancel) per DESIGN.md § 10
                                 "focused multi-field edit -> modal"; Card
                                 rename = inline `QInputDialog.getText`
                                 (tiny, local, low-risk -> inline), the
                                 same grammar EXIT-BUG-001's Custom Entry
                                 Type prompt already established; Card
                                 Organization (remove/move Entries) = one
                                 bounded P6 dialog
                                 (`_CardOrganizationDialog`) so list/
                                 selection context stays visible while
                                 acting, rather than a second full
                                 workspace window.
 10. Navigation/Chrome       -> unchanged Management shell; dialogs are
                                 modal overlays, no chrome swap.
 11. Motion/Transition       -> unchanged; no new motion behavior.
 12. Canonical Visual Rel.   -> `_CollectionEditorDialog` inherits
                                 `_EntryEditorDialog`'s P5 grammar
                                 (scrollable body, pinned error label +
                                 Save/Cancel footer); delete/remove
                                 confirmations reuse Entries'
                                 `QMessageBox.question` destructive
                                 grammar, extended with the typed-name +
                                 checkbox safety gate the existing
                                 Streamlit Collections page already
                                 established for this specific
                                 higher-consequence action (deleting a
                                 Collection also deletes its Card/Review/
                                 Quiz history, unlike deleting an Entry).
 13. Native Human Acceptance -> the real native Collections workspace
                                 showing New Collection creation, Edit
                                 (including a card-size change that
                                 triggers the Cross-Card confirmation),
                                 Delete (typed-name gate), Card rename, and
                                 Card Organization (remove with Cross-Card
                                 confirmation, move with Cross-Card
                                 confirmation) in Light and Dark Mode.
"""

LIST_PANE_WIDTH = 240
_SORT_LABELS: tuple[tuple[str, str], ...] = (
    ("card_number", "Card #"),
    ("card_created_at", "Created"),
    ("card_updated_at", "Updated"),
)


class CollectionsView(QWidget):
    open_entries_requested = Signal(object)  # EntriesScopeIntent
    open_in_study_requested = Signal(object)  # StudyTargetIntent

    def __init__(self, controller: CollectionsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("collections-root")
        self._controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        list_column = QWidget(self)
        list_column_layout = QVBoxLayout(list_column)
        list_column_layout.setContentsMargins(0, 0, 0, 0)
        list_column_layout.setSpacing(0)
        list_column.setFixedWidth(LIST_PANE_WIDTH)

        new_collection_button = QPushButton("New Collection", list_column)
        new_collection_button.setObjectName("collections-new-button")
        new_collection_button.clicked.connect(self._on_new_collection)
        list_column_layout.addWidget(new_collection_button)

        self._list_pane = _CollectionsListPane(self)
        self._list_pane.item_selected.connect(self._on_item_selected)
        list_column_layout.addWidget(self._list_pane, 1)
        root.addWidget(list_column, 0)

        main = QWidget(self)
        main.setObjectName("collections-main-workspace")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)
        main_layout.setSpacing(SPACING.md)

        title = QLabel("Collections", main)
        title.setObjectName("collections-title")
        main_layout.addWidget(title)

        self._detail_container = QWidget(main)
        self._detail_layout = QVBoxLayout(self._detail_container)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(SPACING.md)
        main_layout.addWidget(self._detail_container, 1)

        root.addWidget(main, 1)

        controller.collections_changed.connect(self._on_collections_changed)
        controller.selection_changed.connect(self._on_selection_changed)
        controller.card_page_changed.connect(self._on_card_page_changed)

        self._render_detail()

    def refresh(self) -> None:
        self._controller.refresh()

    # -- reactions ------------------------------------------------------

    def _on_collections_changed(self) -> None:
        self._list_pane.render(self._controller.collections, self._controller.system_pools, self._controller.selected_id)

    def _on_item_selected(self, collection_id: int, is_system: bool) -> None:
        self._controller.select_collection(collection_id, is_system=is_system)

    def _on_new_collection(self) -> None:
        dialog = _CollectionEditorDialog(self._controller, collection=None, parent=self)
        dialog.exec()

    def _on_edit_collection(self, collection: dict) -> None:
        dialog = _CollectionEditorDialog(self._controller, collection=collection, parent=self)
        dialog.exec()

    def _on_delete_collection(self, collection: dict) -> None:
        dialog = _DeleteCollectionDialog(self._controller, collection, parent=self)
        dialog.exec()

    def _on_organize_entries(self, collection: dict) -> None:
        dialog = _CardOrganizationDialog(self._controller, collection, parent=self)
        dialog.exec()

    def _on_rename_card(self, card_number: int, current_name: str) -> None:
        text, confirmed = QInputDialog.getText(self, "Rename Card", "Card name:", text=current_name)
        if not confirmed:
            return
        try:
            self._controller.rename_selected_card(card_number, text.strip())
        except ValueError as error:
            QMessageBox.warning(self, "Rename Card", str(error))

    def _on_selection_changed(self) -> None:
        self._render_detail()

    def _on_card_page_changed(self) -> None:
        self._render_detail()

    # -- detail -----------------------------------------------------------

    def _render_detail(self) -> None:
        _clear_layout(self._detail_layout)
        collection = self._controller.selected_collection()
        if collection is None:
            self._detail_layout.addWidget(_message_label("Choose a Collection to see its context."))
            self._detail_layout.addStretch(1)
            return
        if self._controller.selected_is_system:
            self._render_system_pool_detail(collection)
        else:
            self._render_collection_detail(collection)

    def _render_system_pool_detail(self, collection: dict) -> None:
        display_name = _pool_display_name(collection.get("name"))
        name = QLabel(display_name, self._detail_container)
        name.setObjectName("collections-detail-name")
        self._detail_layout.addWidget(name)

        meta = QLabel(f"{int(collection.get('entry_count') or 0)} Entries", self._detail_container)
        meta.setObjectName("collections-detail-meta")
        self._detail_layout.addWidget(meta)

        system_type = self._controller.system_type_for_selected()
        open_button = QPushButton("Open Entries", self._detail_container)
        open_button.setObjectName("collections-open-entries-button")
        if system_type is not None:
            open_button.clicked.connect(
                lambda: self.open_entries_requested.emit(EntriesScopeIntent(scope=f"system:{system_type}"))
            )
        else:
            open_button.setEnabled(False)
        self._detail_layout.addWidget(open_button, 0)

        self._detail_layout.addWidget(
            _message_label("Practice pools are managed automatically and browsed here as a factual, read-only context.")
        )
        self._detail_layout.addStretch(1)

    def _render_collection_detail(self, collection: dict) -> None:
        collection_id = int(collection["id"])

        name = QLabel(str(collection.get("name") or ""), self._detail_container)
        name.setObjectName("collections-detail-name")
        self._detail_layout.addWidget(name)

        description = str(collection.get("description") or "")
        if description:
            description_label = QLabel(description, self._detail_container)
            description_label.setObjectName("collections-detail-description")
            description_label.setWordWrap(True)
            self._detail_layout.addWidget(description_label)

        meta = QLabel(
            f"{int(collection.get('entry_count') or 0)} Entries · Card size {int(collection.get('card_size') or 0)}",
            self._detail_container,
        )
        meta.setObjectName("collections-detail-meta")
        self._detail_layout.addWidget(meta)

        actions_row = QWidget(self._detail_container)
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACING.sm)

        open_entries_button = QPushButton("Open Entries", actions_row)
        open_entries_button.setObjectName("collections-open-entries-button")
        open_entries_button.clicked.connect(
            lambda: self.open_entries_requested.emit(EntriesScopeIntent(scope=f"collection:{collection_id}"))
        )
        actions_layout.addWidget(open_entries_button, 0)

        edit_button = QPushButton("Edit", actions_row)
        edit_button.setObjectName("collections-edit-button")
        edit_button.clicked.connect(lambda: self._on_edit_collection(collection))
        actions_layout.addWidget(edit_button, 0)

        organize_button = QPushButton("Organize Entries", actions_row)
        organize_button.setObjectName("collections-organize-button")
        organize_button.clicked.connect(lambda: self._on_organize_entries(collection))
        actions_layout.addWidget(organize_button, 0)

        delete_button = QPushButton("Delete", actions_row)
        delete_button.setObjectName("collections-delete-button")
        delete_button.setProperty("destructive", "true")
        delete_button.clicked.connect(lambda: self._on_delete_collection(collection))
        actions_layout.addWidget(delete_button, 0)

        actions_layout.addStretch(1)
        self._detail_layout.addWidget(actions_row)

        cards_heading = QLabel("Cards", self._detail_container)
        cards_heading.setObjectName("collections-cards-heading")
        self._detail_layout.addWidget(cards_heading)

        self._detail_layout.addWidget(self._build_card_page_controls())

        page = self._controller.current_card_page()
        cards = page["cards"]

        scroll = QScrollArea(self._detail_container)
        scroll.setObjectName("collections-card-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(2)
        if not cards:
            body_layout.addWidget(_message_label("No Cards yet."))
        for card in cards:
            body_layout.addWidget(self._build_card_row(collection_id, card))
        body_layout.addStretch(1)
        scroll.setWidget(body)
        self._detail_layout.addWidget(scroll, 1)

    def _build_card_page_controls(self) -> QWidget:
        """Compact control row (§ 2): Sort by / Cards per page / Previous
        / page indicator / Next -- pinned above the scrollable Card page,
        never scrolls away with it."""
        controller = self._controller
        page = controller.current_card_page()

        row = QWidget(self._detail_container)
        row.setObjectName("collections-card-controls")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.sm)

        sort_label = QLabel("Sort by", row)
        sort_label.setObjectName("collections-card-controls-label")
        layout.addWidget(sort_label, 0)

        sort_combo = QComboBox(row)
        sort_combo.setObjectName("collections-card-sort-combo")
        for sort_key, sort_text in _SORT_LABELS:
            sort_combo.addItem(sort_text, sort_key)
        sort_combo.setCurrentIndex(sort_combo.findData(controller.card_sort))
        sort_combo.currentIndexChanged.connect(
            lambda index: controller.set_card_sort(sort_combo.itemData(index))
        )
        layout.addWidget(sort_combo, 0)

        size_label = QLabel("Cards per page", row)
        size_label.setObjectName("collections-card-controls-label")
        layout.addWidget(size_label, 0)

        size_combo = QComboBox(row)
        size_combo.setObjectName("collections-card-page-size-combo")
        for size in CARD_PAGE_SIZE_OPTIONS:
            size_combo.addItem(str(size), size)
        size_combo.setCurrentIndex(size_combo.findData(controller.card_page_size))
        size_combo.currentIndexChanged.connect(
            lambda index: controller.set_card_page_size(size_combo.itemData(index))
        )
        layout.addWidget(size_combo, 0)

        layout.addStretch(1)

        previous_button = QPushButton("Previous", row)
        previous_button.setObjectName("collections-card-previous-button")
        previous_button.setEnabled(page["page"] > 1)
        previous_button.clicked.connect(lambda: controller.set_card_page(page["page"] - 1))
        layout.addWidget(previous_button, 0)

        page_label = QLabel(f"Page {page['page']} of {page['total_pages']}", row)
        page_label.setObjectName("collections-card-page-label")
        layout.addWidget(page_label, 0)

        next_button = QPushButton("Next", row)
        next_button.setObjectName("collections-card-next-button")
        next_button.setEnabled(page["page"] < page["total_pages"])
        next_button.clicked.connect(lambda: controller.set_card_page(page["page"] + 1))
        layout.addWidget(next_button, 0)

        return row

    def _build_card_row(self, collection_id: int, card: dict) -> QWidget:
        card_number = int(card["card_number"])
        row = QWidget(self._detail_container)
        row.setObjectName("collections-card-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(SPACING.sm, SPACING.xs, SPACING.sm, SPACING.xs)
        layout.setSpacing(SPACING.sm)

        card_name = str(card.get("card_name") or "")
        label_text = f"Card #{card_number}" + (f" · {card_name}" if card_name else "")
        label = QLabel(label_text, row)
        label.setObjectName("collections-card-label")
        layout.addWidget(label, 1)

        count_label = QLabel(f"{int(card.get('entry_count') or 0)} Entries", row)
        count_label.setObjectName("collections-card-count")
        layout.addWidget(count_label, 0)

        rename_button = QPushButton("Rename", row)
        rename_button.setObjectName("collections-card-rename-button")
        rename_button.clicked.connect(lambda: self._on_rename_card(card_number, card_name))
        layout.addWidget(rename_button, 0)

        open_in_study_button = QPushButton("Open in Study", row)
        open_in_study_button.setObjectName("collections-open-in-study-button")
        open_in_study_button.clicked.connect(
            lambda: self.open_in_study_requested.emit(
                StudyTargetIntent(collection_id=collection_id, card_number=card_number)
            )
        )
        layout.addWidget(open_in_study_button, 0)

        return row


class _CollectionsListPane(QWidget):
    """Left selector pane: explicit "Collections" and "Practice Pools"
    sections (M17 Minimum Collection Integration prompt § 6), mirroring
    Entries' Scope Pane "Scope"/"Collections" separation rather than
    inventing new visual language (DESIGN.md § 6.8 point 12)."""

    item_selected = Signal(int, bool)  # collection_id, is_system

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("collections-list-pane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACING.sm, SPACING.md, SPACING.sm, SPACING.md)
        self._layout.setSpacing(2)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[int, QPushButton] = {}

    def render(self, collections: list[dict], system_pools: list[dict], active_id: int | None) -> None:
        _clear_layout(self._layout)
        for button in list(self._group.buttons()):
            self._group.removeButton(button)
        self._buttons = {}

        self._layout.addWidget(_list_heading("Collections"))
        if not collections:
            self._layout.addWidget(_message_label("No Collections yet."))
        for collection in collections:
            self._add_item(collection, active_id, is_system=False)

        self._layout.addWidget(_list_divider())
        self._layout.addWidget(_list_heading("Practice Pools"))
        if not system_pools:
            self._layout.addWidget(_message_label("No practice pools yet."))
        for pool in system_pools:
            self._add_item(pool, active_id, is_system=True)

    def _add_item(self, collection: dict, active_id: int | None, *, is_system: bool) -> None:
        collection_id = int(collection["id"])
        count = int(collection.get("entry_count") or 0)
        name = _pool_display_name(collection.get("name")) if is_system else str(collection.get("name") or "")
        text = f"{name}    {count}"
        button = QPushButton(text, self)
        button.setObjectName("collections-list-item")
        button.setCheckable(True)
        button.setFlat(True)
        button.setChecked(collection_id == active_id)
        button.clicked.connect(
            lambda _checked=False, cid=collection_id, sys_=is_system: self.item_selected.emit(cid, sys_)
        )
        self._group.addButton(button)
        self._buttons[collection_id] = button
        self._layout.addWidget(button)


class _CollectionEditorDialog(QDialog):
    """P5 Focused Editor for Collection create/edit (DESIGN.md § 10:
    "focused multi-field edit with clear Save/Cancel and moderate
    complexity -> modal / focused dialog"), inheriting Entries'
    ``_EntryEditorDialog`` grammar: a pinned error label plus Save/Cancel
    footer. ``collection is None`` means create; otherwise edit the
    currently selected Collection. A card-size change large enough to
    reorganize Cards raises ``CrossCardMoveConfirmationRequired``, handled
    with the same confirm-and-retry ``QMessageBox`` pattern Entries uses
    for its own cross-Card operations."""

    def __init__(self, controller: CollectionsController, collection: dict | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("collections-editor-dialog")
        self.setWindowTitle("New Collection" if collection is None else "Edit Collection")
        self.setMinimumWidth(420)

        self._controller = controller
        self._collection = collection

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_input = QLineEdit(self)
        self._name_input.setText(str(collection.get("name") or "") if collection else "")
        form.addRow("Name", self._name_input)

        self._description_input = QPlainTextEdit(self)
        self._description_input.setPlainText(str(collection.get("description") or "") if collection else "")
        self._description_input.setFixedHeight(80)
        form.addRow("Description", self._description_input)

        self._card_size_input = QSpinBox(self)
        self._card_size_input.setRange(1, 1000)
        self._card_size_input.setValue(int(collection.get("card_size") or 8) if collection else 8)
        self._card_size_input.setToolTip(
            "Recommended default: 8 entries per card. Choose a smaller number "
            "for heavier materials such as French conjugations."
        )
        form.addRow("Card size", self._card_size_input)

        layout.addLayout(form)

        self._error_label = QLabel("", self)
        self._error_label.setObjectName("collections-editor-error")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        save_button = QPushButton("Save", self)
        save_button.setObjectName("collections-editor-save-button")
        save_button.clicked.connect(lambda: self._save(confirm_cross_card=False))
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def _save(self, *, confirm_cross_card: bool) -> None:
        self._error_label.setText("")
        name = self._name_input.text()
        description = self._description_input.toPlainText()
        card_size = self._card_size_input.value()
        try:
            if self._collection is None:
                self._controller.create_new_collection(name, description, card_size)
            else:
                self._controller.update_selected_collection(
                    name, description, card_size, confirm_cross_card=confirm_cross_card
                )
        except CrossCardMoveConfirmationRequired:
            if _confirm_cross_card(self):
                self._save(confirm_cross_card=True)
            return
        except ValueError as error:
            self._error_label.setText(str(error))
            return
        self.accept()


class _DeleteCollectionDialog(QDialog):
    """P6 destructive confirmation (DESIGN.md § 8 P6). Deleting a
    Collection is more consequential than deleting an Entry -- it also
    deletes Card identity/revision history, legacy Review history, and
    Quiz sessions/logs (Entries themselves are kept) -- so this reuses the
    exact typed-name + checkbox safety gate the Streamlit Collections page
    already established (``COLLECTION_DELETE_WARNING`` /
    ``COLLECTION_DELETE_CONFIRMATION``) rather than a plain
    ``QMessageBox.question``, which has no room for a typed-name field."""

    def __init__(self, controller: CollectionsController, collection: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("collections-delete-dialog")
        self.setWindowTitle("Delete Collection")
        self.setMinimumWidth(420)

        self._controller = controller
        self._collection_name = str(collection.get("name") or "")

        layout = QVBoxLayout(self)

        warning = QLabel(COLLECTION_DELETE_WARNING, self)
        warning.setWordWrap(True)
        layout.addWidget(warning)

        name_label = QLabel(f"Type the Collection name to confirm: {self._collection_name}", self)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        self._name_input = QLineEdit(self)
        self._name_input.textChanged.connect(self._update_delete_enabled)
        layout.addWidget(self._name_input)

        self._confirm_checkbox = QCheckBox(COLLECTION_DELETE_CONFIRMATION, self)
        self._confirm_checkbox.setObjectName("collections-delete-checkbox")
        self._confirm_checkbox.toggled.connect(self._update_delete_enabled)
        layout.addWidget(self._confirm_checkbox)

        self._error_label = QLabel("", self)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        self._delete_button = QPushButton("Delete Collection", self)
        self._delete_button.setObjectName("collections-delete-confirm-button")
        self._delete_button.setProperty("destructive", "true")
        self._delete_button.setEnabled(False)
        self._delete_button.clicked.connect(self._on_delete)
        buttons.addWidget(self._delete_button)
        layout.addLayout(buttons)

    def _update_delete_enabled(self) -> None:
        name_matches = self._name_input.text().strip() == self._collection_name
        self._delete_button.setEnabled(name_matches and self._confirm_checkbox.isChecked())

    def _on_delete(self) -> None:
        try:
            self._controller.delete_selected_collection()
        except ValueError as error:
            self._error_label.setText(str(error))
            return
        self.accept()


class _CardOrganizationDialog(QDialog):
    """Card Organization Workspace (DESIGN.md § 7.3 "B, P2 + P5"), scoped
    to one P6 dialog (§ 10: "keep list/selection context visible while
    making a bounded change") rather than a second full workspace window.
    Remove and Move both call the exact same ``src.collections`` functions
    the Streamlit "Remove Entries from Collection" / "Reorder Entries in
    Collection" sections use, including the same
    ``CrossCardMoveConfirmationRequired`` confirm-and-retry gate."""

    def __init__(self, controller: CollectionsController, collection: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("collections-organize-dialog")
        self.setWindowTitle(f"Organize Entries — {collection.get('name') or ''}")
        self.setMinimumSize(520, 480)

        self._controller = controller
        self._checks: dict[int, QCheckBox] = {}

        layout = QVBoxLayout(self)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_body = QWidget(scroll)
        self._list_layout = QVBoxLayout(self._list_body)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        scroll.setWidget(self._list_body)
        layout.addWidget(scroll, 1)

        remove_row = QHBoxLayout()
        remove_button = QPushButton("Remove Selected from Collection", self)
        remove_button.setObjectName("collections-organize-remove-button")
        remove_button.setProperty("destructive", "true")
        remove_button.clicked.connect(lambda: self._on_remove(confirm_cross_card=False))
        remove_row.addWidget(remove_button)
        remove_row.addStretch(1)
        layout.addLayout(remove_row)

        move_form = QFormLayout()
        self._move_combo = QComboBox(self)
        move_form.addRow("Move Entry", self._move_combo)
        self._move_position = QSpinBox(self)
        self._move_position.setMinimum(1)
        move_form.addRow("New position", self._move_position)
        layout.addLayout(move_form)

        move_row = QHBoxLayout()
        move_button = QPushButton("Move", self)
        move_button.setObjectName("collections-organize-move-button")
        move_button.clicked.connect(lambda: self._on_move(confirm_cross_card=False))
        move_row.addWidget(move_button)
        move_row.addStretch(1)
        layout.addLayout(move_row)

        self._error_label = QLabel("", self)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

        self._reload()

    def _reload(self) -> None:
        self._error_label.setText("")
        entries = self._controller.organization_entries()

        _clear_layout(self._list_layout)
        self._checks = {}
        if not entries:
            self._list_layout.addWidget(_message_label("No Entries in this Collection."))
        for entry in entries:
            entry_id = int(entry["id"])
            checkbox = QCheckBox(f"#{entry['position']} · {entry.get('term') or ''}", self._list_body)
            self._checks[entry_id] = checkbox
            self._list_layout.addWidget(checkbox)
        self._list_layout.addStretch(1)

        self._move_combo.clear()
        for entry in entries:
            self._move_combo.addItem(f"#{entry['position']} · {entry.get('term') or ''}", int(entry["id"]))
        self._move_position.setMaximum(max(1, len(entries)))

    def _on_remove(self, *, confirm_cross_card: bool) -> None:
        entry_ids = [entry_id for entry_id, checkbox in self._checks.items() if checkbox.isChecked()]
        if not entry_ids:
            return
        if not confirm_cross_card:
            confirmed = QMessageBox.question(
                self,
                "Remove Entries",
                f"Remove {len(entry_ids)} Entries from this Collection? "
                "They remain in Vocabulary App and any other Collection.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirmed != QMessageBox.StandardButton.Yes:
                return
        try:
            self._controller.remove_organization_entries(entry_ids, confirm_cross_card=confirm_cross_card)
        except CrossCardMoveConfirmationRequired:
            if _confirm_cross_card(self):
                self._on_remove(confirm_cross_card=True)
            return
        except ValueError as error:
            self._error_label.setText(str(error))
            return
        self._reload()

    def _on_move(self, *, confirm_cross_card: bool) -> None:
        entry_id = self._move_combo.currentData()
        if entry_id is None:
            return
        new_position = self._move_position.value()
        try:
            self._controller.move_organization_entry(
                int(entry_id), new_position, confirm_cross_card=confirm_cross_card
            )
        except CrossCardMoveConfirmationRequired:
            if _confirm_cross_card(self):
                self._on_move(confirm_cross_card=True)
            return
        except ValueError as error:
            self._error_label.setText(str(error))
            return
        self._reload()


def _confirm_cross_card(parent: QWidget) -> bool:
    """Same confirm-and-retry grammar as Entries'
    ``_confirm_cross_card_reorganization`` -- kept as a small local
    duplicate rather than a cross-view-module import, matching this
    repository's existing per-view dialog-helper convention."""
    result = QMessageBox.question(
        parent,
        "Confirm Card Reorganization",
        CROSS_CARD_CONFIRMATION_MESSAGE,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return result == QMessageBox.StandardButton.Yes


def _list_heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("collections-list-heading")
    return label


def _list_divider() -> QWidget:
    divider = QWidget()
    divider.setObjectName("collections-list-divider")
    divider.setFixedHeight(1)
    divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return divider


def _pool_display_name(name: str | None) -> str:
    """"★ " prefix on the Starred pool is presentation-only (M17 Minimum
    Collection Integration corrective pass § 12) -- the underlying
    ``name``/``system_type`` persistence keys are untouched."""
    clean_name = str(name or "")
    return f"★ {clean_name}" if clean_name == "Starred" else clean_name


def _message_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("collections-empty-state")
    label.setWordWrap(True)
    return label


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()

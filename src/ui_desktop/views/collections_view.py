from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.collections import CARD_PAGE_SIZE_OPTIONS
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

        self._list_pane = _CollectionsListPane(self)
        self._list_pane.setFixedWidth(LIST_PANE_WIDTH)
        self._list_pane.item_selected.connect(self._on_item_selected)
        root.addWidget(self._list_pane, 0)

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

        open_entries_button = QPushButton("Open Entries", self._detail_container)
        open_entries_button.setObjectName("collections-open-entries-button")
        open_entries_button.clicked.connect(
            lambda: self.open_entries_requested.emit(EntriesScopeIntent(scope=f"collection:{collection_id}"))
        )
        self._detail_layout.addWidget(open_entries_button, 0)

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

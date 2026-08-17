from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.collections import (
    CARD_PAGE_SIZE_OPTIONS,
    CARD_SORT_MODES,
    DEFAULT_CARD_PAGE_SIZE,
    SYSTEM_COLLECTION_TYPES,
    get_card_page_for_collection,
    get_collection_by_id,
    get_collections,
)

"""
CollectionsController owns the Collections Navigator's transient
selection/pagination state only, calling existing ``src.collections``
reads for every fact it projects -- no SQL, no second Collection-
membership model, no mutation (M17 Minimum Collection Integration prompt
§ 5/§ 12: "Browsing this surface must not mutate SQLite").

Normal user Collections and system practice pools (Starred/Mistake
Book/Proficient Pool) are kept as two separate lists throughout, never one
flat mixed collection -- the same semantic separation
``EntriesController``/``_ScopePane`` already established for the Scope
Pane (prompt § 6).

Corrective pass (M17_Minimum_Collection_Integration_Corrective_Pass.md
§ 2/§ 3): the Card list is no longer read/rendered in full for large
Collections. ``card_sort``/``card_page_size``/``card_page`` are transient
controller state; the actual page is produced by the new
``get_card_page_for_collection`` read-only paged core query, which
computes Entry counts via SQL aggregation rather than loading every
Entry row -- this controller never slices a full-collection Python list
itself.
"""


class CollectionsController(QObject):
    collections_changed = Signal()
    selection_changed = Signal()
    card_page_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.collections: list[dict] = []
        self.system_pools: list[dict] = []
        self.selected_id: int | None = None
        self.selected_is_system: bool = False
        self.card_sort: str = "card_number"
        self.card_page_size: int = DEFAULT_CARD_PAGE_SIZE
        self.card_page: int = 1

    def refresh(self) -> None:
        all_collections = get_collections()
        self.collections = [c for c in all_collections if not c["is_system"]]
        self.system_pools = [c for c in all_collections if c["is_system"]]
        if self.selected_id is not None and not any(
            c["id"] == self.selected_id for c in (*self.collections, *self.system_pools)
        ):
            self.selected_id = None
            self.selected_is_system = False
        self.collections_changed.emit()
        self.selection_changed.emit()

    def select_collection(self, collection_id: int, *, is_system: bool) -> None:
        self.selected_id = collection_id
        self.selected_is_system = is_system
        self.card_page = 1
        self.selection_changed.emit()

    def clear_selection(self) -> None:
        self.selected_id = None
        self.selected_is_system = False
        self.card_page = 1
        self.selection_changed.emit()

    def selected_collection(self) -> dict | None:
        if self.selected_id is None:
            return None
        return get_collection_by_id(self.selected_id)

    # -- Card pagination (§ 2/§ 3/§ 4) --------------------------------------

    def set_card_sort(self, sort_by: str) -> None:
        if sort_by not in CARD_SORT_MODES or sort_by == self.card_sort:
            return
        self.card_sort = sort_by
        self.card_page = 1
        self.card_page_changed.emit()

    def set_card_page_size(self, page_size: int) -> None:
        if page_size not in CARD_PAGE_SIZE_OPTIONS or page_size == self.card_page_size:
            return
        self.card_page_size = page_size
        self.card_page = 1
        self.card_page_changed.emit()

    def set_card_page(self, page: int) -> None:
        if page == self.card_page:
            return
        self.card_page = page
        self.card_page_changed.emit()

    def current_card_page(self) -> dict:
        """The current page of Cards for the selected *normal* Collection,
        via the paged read-only core projection -- never
        ``get_card_groups_for_collection``'s "load every Entry, group in
        Python" path (§ 2/§ 3). Empty for a system pool (§ 6: system
        pools do not get ordinary Card-browsing semantics)."""
        if self.selected_id is None or self.selected_is_system:
            return {"cards": [], "total_cards": 0, "total_pages": 1, "page": 1, "page_size": self.card_page_size}
        page = get_card_page_for_collection(
            self.selected_id,
            page=self.card_page,
            page_size=self.card_page_size,
            sort_by=self.card_sort,
        )
        if page["page"] != self.card_page:
            self.card_page = page["page"]
        return page

    def system_type_for_selected(self) -> str | None:
        """The ``system_type`` key (``starred``/``mistake_book``/
        ``proficient_pool``) for the selected system pool, if any --
        needed to build the ``system:<type>`` Entries scope."""
        if not self.selected_is_system or self.selected_id is None:
            return None
        collection = get_collection_by_id(self.selected_id)
        if collection is None:
            return None
        system_type = collection.get("system_type")
        return system_type if system_type in SYSTEM_COLLECTION_TYPES else None

    def entries_scope_for(self, collection_id: int, *, is_system: bool) -> str | None:
        """The Entries scope key for a given list entry -- reuses
        Entries' existing scope contract exactly (``collection:<id>`` /
        ``system:<type>``), never a second filter implementation (prompt
        § 7)."""
        if not is_system:
            return f"collection:{collection_id}"
        collection = get_collection_by_id(collection_id)
        if collection is None:
            return None
        system_type = collection.get("system_type")
        if system_type not in SYSTEM_COLLECTION_TYPES:
            return None
        return f"system:{system_type}"

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.collections import (
    CARD_PAGE_SIZE_OPTIONS,
    CARD_SORT_MODES,
    DEFAULT_CARD_PAGE_SIZE,
    SYSTEM_COLLECTION_TYPES,
    create_collection,
    delete_collection,
    get_card_page_for_collection,
    get_collection_by_id,
    get_collections,
    get_entries_in_collection,
    move_entry_in_collection,
    remove_entries_from_collection,
    set_card_name,
    update_collection,
)
from src.learning_workflow import get_collection_learning_progress

"""
CollectionsController owns the Collections workspace's transient
selection/pagination state, calling existing ``src.collections``
reads/writes for every fact it projects or mutates -- no SQL, no second
Collection-membership model. Browsing (M17 Minimum Collection Integration)
remains read-only exactly as before; M18.1 adds Collection Manager and
Card Organization writes (create/rename/edit/delete Collection, rename
Card, remove/move Entries), each delegating straight to the same core
functions the Streamlit Collections page already uses.

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
        progress_by_collection = get_collection_learning_progress()
        self.collections = []
        for collection in all_collections:
            if collection["is_system"]:
                continue
            progress = progress_by_collection.get(
                int(collection["id"]),
                {"learned_cards": 0, "total_cards": 0, "percent": 0},
            )
            self.collections.append(
                {
                    **collection,
                    "learned_cards": int(progress["learned_cards"]),
                    "total_cards": int(progress["total_cards"]),
                    "learning_percent": int(progress["percent"]),
                }
            )
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
        collection = get_collection_by_id(self.selected_id)
        if collection is None or self.selected_is_system:
            return collection
        projected = next(
            (row for row in self.collections if int(row["id"]) == int(self.selected_id)),
            None,
        )
        return projected or collection

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

    # -- Collection Manager (M18.1) --------------------------------------
    # Every write below calls the exact same `src.collections` functions
    # the Streamlit Collections page uses -- no SQL, no second
    # create/update/delete implementation. `CrossCardMoveConfirmationRequired`
    # is never caught here; it propagates to the view exactly like
    # `EntriesController`'s equivalent calls, so the one shared
    # confirm-and-retry dialog pattern stays the single implementation.

    def create_new_collection(self, name: str, description: str, card_size: int) -> int:
        """May raise ``ValueError`` (blank name, invalid card_size, or a
        duplicate name) -- the caller surfaces it as a focused-editor
        error, never a silent failure."""
        collection_id = create_collection(name=name, description=description, card_size=card_size)
        self.refresh()
        self.select_collection(collection_id, is_system=False)
        return collection_id

    def update_selected_collection(
        self, name: str, description: str, card_size: int, *, confirm_cross_card: bool = False
    ) -> None:
        """May raise ``CrossCardMoveConfirmationRequired`` or ``ValueError``."""
        if self.selected_id is None or self.selected_is_system:
            raise ValueError("No editable Collection is selected.")
        update_collection(
            collection_id=self.selected_id,
            name=name,
            description=description,
            card_size=card_size,
            confirm_cross_card=confirm_cross_card,
        )
        self.refresh()
        self.card_page_changed.emit()

    def delete_selected_collection(self) -> dict:
        """May raise ``ValueError`` (not found, or a system Collection)."""
        if self.selected_id is None or self.selected_is_system:
            raise ValueError("No deletable Collection is selected.")
        result = delete_collection(self.selected_id)
        self.clear_selection()
        self.refresh()
        return result

    def rename_selected_card(self, card_number: int, name: str) -> None:
        if self.selected_id is None or self.selected_is_system:
            raise ValueError("No Collection is selected.")
        set_card_name(self.selected_id, card_number, name)
        self.card_page_changed.emit()

    # -- Card Organization (M18.1): entry remove/reorder within the
    # selected Collection. Reuses `get_entries_in_collection` and the
    # same remove/move core functions the Streamlit "Reorder Entries in
    # Collection" workflow already uses -- no second membership/position
    # model.

    def organization_entries(self) -> list[dict]:
        if self.selected_id is None or self.selected_is_system:
            return []
        return get_entries_in_collection(self.selected_id)

    def remove_organization_entries(self, entry_ids: list[int], *, confirm_cross_card: bool = False) -> int:
        """May raise ``CrossCardMoveConfirmationRequired``."""
        if self.selected_id is None or self.selected_is_system:
            raise ValueError("No Collection is selected.")
        count = remove_entries_from_collection(entry_ids, self.selected_id, confirm_cross_card=confirm_cross_card)
        self.refresh()
        self.card_page_changed.emit()
        return count

    def move_organization_entry(
        self, entry_id: int, new_position: int, *, confirm_cross_card: bool = False
    ) -> None:
        """May raise ``CrossCardMoveConfirmationRequired`` or ``ValueError``."""
        if self.selected_id is None or self.selected_is_system:
            raise ValueError("No Collection is selected.")
        move_entry_in_collection(
            self.selected_id, entry_id, new_position, confirm_cross_card=confirm_cross_card
        )
        self.card_page_changed.emit()

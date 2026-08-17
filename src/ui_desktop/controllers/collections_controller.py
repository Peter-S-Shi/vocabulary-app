from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.collections import SYSTEM_COLLECTION_TYPES, get_card_groups_for_collection, get_collection_by_id, get_collections

"""
CollectionsController owns the Collections Navigator's transient
selection state only, calling existing ``src.collections`` reads for
every fact it projects -- no SQL, no second Collection-membership model,
no mutation (M17 Minimum Collection Integration prompt § 5/§ 12: "Browsing
this surface must not mutate SQLite").

Normal user Collections and system practice pools (Starred/Mistake
Book/Proficient Pool) are kept as two separate lists throughout, never one
flat mixed collection -- the same semantic separation
``EntriesController``/``_ScopePane`` already established for the Scope
Pane (prompt § 6).
"""


class CollectionsController(QObject):
    collections_changed = Signal()
    selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.collections: list[dict] = []
        self.system_pools: list[dict] = []
        self.selected_id: int | None = None
        self.selected_is_system: bool = False

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
        self.selection_changed.emit()

    def clear_selection(self) -> None:
        self.selected_id = None
        self.selected_is_system = False
        self.selection_changed.emit()

    def selected_collection(self) -> dict | None:
        if self.selected_id is None:
            return None
        return get_collection_by_id(self.selected_id)

    def selected_card_groups(self) -> list[dict]:
        """Current Cards for the selected *normal* Collection, from the
        same reusable-core Card composition Review/Entries already use --
        never a second derived Card model (prompt § 5)."""
        if self.selected_id is None or self.selected_is_system:
            return []
        return get_card_groups_for_collection(self.selected_id)

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

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.collections import (
    SYSTEM_COLLECTION_TYPES,
    add_entries_to_collection,
    add_entries_to_system_collection,
    add_entry_to_collections,
    get_collection_ids_for_entry,
    get_collection_names_for_entries,
    get_collections,
    get_entries_in_collection,
    get_entries_in_system_collection,
    get_entry_ids_in_system_collection,
    get_system_collection_by_type_or_name,
    remove_entries_from_system_collection,
    resolve_collection_names,
    update_entry_collections,
)
from src.entries import (
    add_entry,
    create_entry_with_template,
    delete_entries,
    get_entry_with_template_values,
    search_entries,
    update_entry_with_template,
)
from src.entry_templates import GENERAL_ENTRY_TEMPLATE_NAME, get_canonical_mapping, get_entry_templates, get_template_fields
from src.text_parser import parse_and_validate_entry_card
from src.ui_desktop.qt_models.entries_table_model import EntriesTableModel

"""
EntriesController owns the Entries workspace's transient scope/filter/
selection/editor-draft state (M17 Feature 4 prompt § 11) and calls existing
reusable core directly for every read/write -- no raw SQL, no duplicated
template validation, canonical-field resolution, or Card-history
reconciliation logic. `CrossCardMoveConfirmationRequired` (delete/collection
removal) is never caught here; it propagates to the view exactly like the
existing `src.entries`/`src.collections` contract (mirrors the
raise-then-retry-with-confirm_cross_card=True pattern already used by
`src/ui_streamlit/entries_page.py` and the reusable-core tests).

Scope keys: ``"all"``, ``"system:<starred|mistake_book|proficient_pool>"``,
``"collection:<id>"``. Since ``search_entries()`` has no collection-scope
parameter, a non-"all" scope is applied as a client-side id intersection
against the same ``search_entries()`` result -- reusing its own
search_text/language/entry_type/status filtering rather than duplicating
it, per the M17 Feature 4 prompt's explicit "do not solve such a gap with
SQL in EntriesController" boundary.

M17 Minimum Collection Integration corrective pass (§ 5-10): row
inspection and batch selection are two independent transient truths, not
one shared concept --

  ``focused_id``    -- the single Entry the bottom detail pane currently
                       shows (set by a plain row click); drives Edit.
  ``checked_ids``   -- the batch-selection truth the checkbox column and
                       header "select all" write to; drives Delete/Add to
                       Collection/Star (batch). Never derived from, or
                       required to depend on, native Ctrl/Shift row
                       selection.

Each row also carries a ``starred`` flag (attached in ``refresh()`` via
the batched ``get_entry_ids_in_system_collection`` read) so the table can
render a direct per-row Star affordance without a second N+1 read.
"""

SCOPE_ALL = "all"

# M17 Final Parity + Exit Verification (EXIT-BUG-002): (label, sort_by,
# sort_direction) triples for the desktop "Sort by" control, in display
# order. sort_by/sort_direction values match
# ``src.entries.SORT_COLUMNS``'s allowlist -- this combo is a desktop
# presentation convenience over that core capability, not a duplicated
# sort implementation. The first option matches the pre-existing default
# order exactly, so a freshly opened Entries workspace looks unchanged
# until the user actually picks something else.
SORT_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("Newest first", "created_at", "desc"),
    ("Oldest first", "created_at", "asc"),
    ("Term (A-Z)", "term", "asc"),
    ("Term (Z-A)", "term", "desc"),
    ("Recently updated", "updated_at", "desc"),
    ("Least recently updated", "updated_at", "asc"),
)
DEFAULT_SORT_BY = SORT_OPTIONS[0][1]
DEFAULT_SORT_DIRECTION = SORT_OPTIONS[0][2]


class EntriesController(QObject):
    rows_changed = Signal(int)
    checked_changed = Signal(object)  # list[dict] of currently checked (batch) entries
    focused_changed = Signal(object)  # dict | None -- the focused Entry, or None
    scopes_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.model = EntriesTableModel()
        self.search_text = ""
        self.language = "All"
        self.entry_type = "All"
        self.status = "All"
        self.template_id: int | str | None = None
        self.sort_by = DEFAULT_SORT_BY
        self.sort_direction = DEFAULT_SORT_DIRECTION
        self.scope = SCOPE_ALL
        self.checked_ids: set[int] = set()
        self.focused_id: int | None = None
        self.scopes: list[dict] = []

    # -- scope pane ------------------------------------------------------

    def refresh_scopes(self) -> None:
        scopes = [{"key": SCOPE_ALL, "label": "All Entries", "count": len(search_entries())}]
        for system_type, label in SYSTEM_COLLECTION_TYPES.items():
            collection = get_system_collection_by_type_or_name(system_type)
            scopes.append(
                {
                    "key": f"system:{system_type}",
                    "label": label,
                    "count": collection.get("entry_count", 0) if collection else 0,
                }
            )
        for collection in self.collection_options():
            scopes.append({"key": f"collection:{collection['id']}", "label": collection["name"], "count": collection["entry_count"]})
        self.scopes = scopes
        self.scopes_changed.emit()

    def set_scope(self, scope_key: str) -> int:
        if scope_key == self.scope:
            return len(self.model.rows())
        self.scope = scope_key
        return self.refresh()

    def _scope_entry_ids(self) -> set[int] | None:
        if self.scope == SCOPE_ALL:
            return None
        if self.scope.startswith("system:"):
            entries = get_entries_in_system_collection(self.scope.split(":", 1)[1])
        elif self.scope.startswith("collection:"):
            entries = get_entries_in_collection(int(self.scope.split(":", 1)[1]))
        else:
            return None
        return {int(entry["id"]) for entry in entries}

    # -- browse / filter ---------------------------------------------------

    def refresh(self) -> int:
        rows = search_entries(
            search_text=self.search_text,
            language=self.language,
            entry_type=self.entry_type,
            status=self.status,
            template_id=self.template_id,
            sort_by=self.sort_by,
            sort_direction=self.sort_direction,
        )
        scope_ids = self._scope_entry_ids()
        if scope_ids is not None:
            rows = [row for row in rows if row["id"] in scope_ids]

        row_ids = [row["id"] for row in rows]
        collection_names = get_collection_names_for_entries(row_ids)
        starred_ids = get_entry_ids_in_system_collection(row_ids, "starred")
        for row in rows:
            row["collection_names"] = collection_names.get(row["id"], [])
            row["starred"] = row["id"] in starred_ids
        self.model.set_rows(rows)

        visible_ids = {row["id"] for row in rows}
        if not self.checked_ids <= visible_ids:
            self.checked_ids &= visible_ids
        if self.focused_id is not None and self.focused_id not in visible_ids:
            self.focused_id = None
        self.checked_changed.emit(self.checked_entries())
        self.focused_changed.emit(self.focused_entry())
        self.rows_changed.emit(len(rows))
        return len(rows)

    def set_search_text(self, text: str) -> int:
        self.search_text = text
        return self.refresh()

    def set_language(self, value: str) -> int:
        self.language = value
        return self.refresh()

    def set_entry_type(self, value: str) -> int:
        self.entry_type = value
        return self.refresh()

    def set_status(self, value: str) -> int:
        self.status = value
        return self.refresh()

    def set_sort(self, sort_by: str, sort_direction: str) -> int:
        """EXIT-BUG-002: presentation/query state only -- reorders the
        same result set through the existing ``search_entries()`` read;
        never mutates Entry identity, checked/focused truths, Star, or
        Collection membership (``refresh()`` already preserves
        ``checked_ids``/``focused_id`` whenever the reordered result set
        still contains them, which a pure resort always does)."""
        if sort_by == self.sort_by and sort_direction == self.sort_direction:
            return len(self.model.rows())
        self.sort_by = sort_by
        self.sort_direction = sort_direction
        return self.refresh()

    # -- focused Entry (inspection truth) -------------------------------

    def set_focused_id(self, entry_id: int | None) -> None:
        if entry_id == self.focused_id:
            return
        self.focused_id = entry_id
        self.focused_changed.emit(self.focused_entry())

    def focused_entry(self) -> dict | None:
        if self.focused_id is None:
            return None
        return next((row for row in self.model.rows() if row["id"] == self.focused_id), None)

    # -- checked Entries (batch-selection truth) -------------------------

    def set_checked_ids(self, ids: set[int]) -> None:
        self.checked_ids = set(ids)
        self.checked_changed.emit(self.checked_entries())

    def checked_entries(self) -> list[dict]:
        by_id = {row["id"]: row for row in self.model.rows()}
        return [by_id[entry_id] for entry_id in self.checked_ids if entry_id in by_id]

    def select_all_visible(self) -> None:
        self.set_checked_ids({row["id"] for row in self.model.rows()})

    def clear_checked(self) -> None:
        self.set_checked_ids(set())

    def entry_detail(self, entry_id: int) -> dict | None:
        return get_entry_with_template_values(entry_id)

    # -- templates / collections for editors --------------------------------

    def template_options(self) -> list[dict]:
        return get_entry_templates()

    def default_template_id(self) -> int | None:
        templates = self.template_options()
        for template in templates:
            if template["name"] == GENERAL_ENTRY_TEMPLATE_NAME:
                return template["id"]
        return templates[0]["id"] if templates else None

    def template_fields(self, template_id: int) -> list[dict]:
        return get_template_fields(template_id)

    def canonical_mapping(self, template_id: int) -> dict:
        return get_canonical_mapping(template_id)

    def collection_options(self) -> list[dict]:
        return [collection for collection in get_collections() if not collection["is_system"]]

    def get_entry_collection_ids(self, entry_id: int) -> list[int]:
        return get_collection_ids_for_entry(entry_id)

    # -- create / edit -------------------------------------------------------

    def create_entry(
        self,
        entry_data: dict,
        template_values: dict,
        manual_term: str,
        manual_meaning: str,
        collection_ids: list[int],
    ) -> tuple[int | None, list[str]]:
        try:
            entry_id = create_entry_with_template(entry_data, template_values, manual_term, manual_meaning)
        except ValueError as error:
            return None, str(error).splitlines()
        if collection_ids:
            add_entry_to_collections(entry_id, collection_ids)
        self.refresh_scopes()
        self.refresh()
        return entry_id, []

    def update_entry_core(
        self,
        entry_id: int,
        entry_data: dict,
        template_values: dict,
        manual_term: str,
        manual_meaning: str,
    ) -> list[str]:
        """Base Entry fields + template values only. Core validates before
        writing anything, so a validation failure here mutates nothing
        (M17 Feature 4 prompt § 8)."""
        try:
            update_entry_with_template(entry_id, entry_data, template_values, manual_term, manual_meaning)
        except ValueError as error:
            return str(error).splitlines()
        return []

    def sync_entry_collections(self, entry_id: int, collection_ids: list[int], *, confirm_cross_card: bool = False) -> None:
        """May raise ``CrossCardMoveConfirmationRequired`` (``src.collections``)
        -- the view catches it, shows the required confirmation, and
        retries with ``confirm_cross_card=True``. Only the non-system
        Collections shown/edited by this workspace are ever added/removed
        (``managed_collection_ids``); system collections (Starred/Mistake
        Book/Proficient Pool) are always left untouched by this call."""
        managed_ids = [collection["id"] for collection in self.collection_options()]
        update_entry_collections(entry_id, collection_ids, managed_ids, confirm_cross_card=confirm_cross_card)

    def finish_edit(self) -> None:
        self.refresh_scopes()
        self.refresh()

    # -- Quick Add -----------------------------------------------------------

    def quick_add(self, text: str) -> tuple[int | None, list[str]]:
        parsed, errors = parse_and_validate_entry_card(text)
        if errors:
            return None, errors

        collections, unknown_names = resolve_collection_names(parsed["collections"])
        if unknown_names:
            return None, [f"Unknown collection: {name}" for name in unknown_names]

        entry_id = add_entry(
            parsed["language"],
            parsed["explanation_language"],
            parsed["entry_type"],
            parsed["term"],
            parsed["meaning"],
            parsed["example"],
            parsed["notes"],
            parsed["tags"],
            parsed["source"],
            parsed["status"],
        )
        if collections:
            add_entry_to_collections(entry_id, [collection["id"] for collection in collections])
        self.refresh_scopes()
        self.refresh()
        return entry_id, []

    # -- batch / destructive ------------------------------------------------

    def delete_selected(self, *, confirm_cross_card: bool = False) -> int:
        """May raise ``CrossCardMoveConfirmationRequired`` -- never caught
        here (M17 Feature 4 prompt § 9: "never bypass the core's
        confirmation gate"). Operates on ``checked_ids`` (batch truth),
        never ``focused_id``."""
        count = delete_entries(list(self.checked_ids), confirm_cross_card=confirm_cross_card)
        self.checked_ids = set()
        self.refresh_scopes()
        self.refresh()
        return count

    def add_selected_to_starred(self) -> int:
        count = add_entries_to_system_collection(list(self.checked_ids), "starred")
        self.refresh_scopes()
        self.refresh()
        return count

    def add_selected_to_proficient_pool(self) -> int:
        count = add_entries_to_system_collection(list(self.checked_ids), "proficient_pool")
        self.refresh_scopes()
        self.refresh()
        return count

    def add_selected_to_collection(self, collection_id: int) -> int:
        count = add_entries_to_collection(list(self.checked_ids), collection_id)
        self.refresh_scopes()
        self.refresh()
        return count

    # -- direct per-row Star affordance (§ 9/§ 10) ---------------------------

    def toggle_star(self, entry_id: int, *, confirm_cross_card: bool = False) -> bool:
        """Toggles one Entry's Starred membership directly (independent of
        ``checked_ids``). May raise ``CrossCardMoveConfirmationRequired``
        on unstar -- never caught here, same raise-then-retry contract as
        delete/collection-removal (§ 10). Reuses the exact system-
        Collection core already used everywhere else Starred is
        touched -- no duplicated membership logic. Returns the new
        Starred state."""
        row = next((r for r in self.model.rows() if r["id"] == entry_id), None)
        currently_starred = bool(row.get("starred")) if row is not None else False
        if currently_starred:
            remove_entries_from_system_collection([entry_id], "starred", confirm_cross_card=confirm_cross_card)
        else:
            add_entries_to_system_collection([entry_id], "starred")
        self.refresh_scopes()
        self.refresh()
        return not currently_starred

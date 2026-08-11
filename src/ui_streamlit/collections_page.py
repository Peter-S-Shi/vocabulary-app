import streamlit as st
from math import ceil

from src.entries import get_entry_detail_with_template_values
from src.collections import (
    CROSS_CARD_CONFIRMATION_MESSAGE,
    CrossCardMoveConfirmationRequired,
    create_collection,
    delete_collection,
    get_card_groups_for_collection,
    get_collection_by_id,
    get_collections,
    get_entries_in_collection,
    get_entries_in_special_collection_filtered,
    move_entry_in_collection,
    remove_entries_from_collection,
    search_cards_by_name,
    set_card_name,
    update_collection,
)
from src.ui_streamlit.common import (
    COLLECTION_ENTRY_TABLE_COLUMNS,
    COLLECTION_TABLE_COLUMNS,
    collection_entry_label,
    collection_label,
)
from src.ui_streamlit.i18n import t


def _render_create_collection() -> None:
    st.header(t("Create Collection"))

    with st.form("create_collection_form", clear_on_submit=True):
        collection_name = st.text_input(t("Collection name"))
        collection_description = st.text_area(t("Description (optional)"))
        collection_card_size = st.number_input(
            t("Card size"),
            min_value=1,
            value=8,
            step=1,
            help=(
                "Recommended default: 8 entries per card. You can choose a smaller "
                "number for heavier materials such as French conjugations."
            ),
        )
        submitted = st.form_submit_button(t("Create Collection"))

    if submitted:
        try:
            create_collection(
                name=collection_name,
                description=collection_description,
                card_size=int(collection_card_size),
            )
            st.success(t("Collection created."))
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def _render_collection_list(collections: list[dict]) -> None:
    st.header(t("Collection List"))

    if not collections:
        st.info(t("No collections yet. Create your first collection above."))
        return

    collection_rows = [
        {column: collection[column] for column in COLLECTION_TABLE_COLUMNS}
        for collection in collections
    ]
    st.dataframe(collection_rows, use_container_width=True, hide_index=True)




def _is_special_collection(collection: dict) -> bool:
    return bool(collection.get("is_system")) and collection.get("system_type") in {
        "mistake_book",
        "starred",
        "proficient_pool",
    }



def _render_collection_entry_detail_preview(entries: list[dict], key_prefix: str) -> None:
    if not entries:
        return

    st.subheader(t("Entry Template Detail"))
    selected_entry = st.selectbox(
        t("Select entry to preview template fields"),
        entries,
        format_func=collection_entry_label,
        key=f"{key_prefix}_entry_detail_preview",
    )
    detail = get_entry_detail_with_template_values(selected_entry["id"])
    if detail is None:
        st.warning(t("The selected entry no longer exists."))
        return

    st.caption(f"Template: {detail.get('template_name') or 'Unknown'}")
    with st.expander(t("Template Field Values"), expanded=False):
        value_rows = [
            {
                "display_order": value_data["display_order"],
                "field_label": value_data["field_label"],
                "field_key": field_key,
                "field_value": value_data["field_value"],
            }
            for field_key, value_data in detail["template_values"].items()
        ]
        if value_rows:
            st.dataframe(value_rows, use_container_width=True, hide_index=True)
        else:
            st.info(t("No template field values found for this entry."))


def _card_label(card_group: dict) -> str:
    card_number = card_group["card_number"]
    card_name = str(card_group.get("card_name") or "").strip()
    if card_name:
        return f"Card #{card_number} - {card_name}"
    return f"Card #{card_number}"


def _render_card_name_search() -> None:
    st.subheader(t("Find Card by Name"))
    search_text = st.text_input(
        t("Search card names"),
        key="collection_card_name_search",
        placeholder="weather",
    )
    if not search_text.strip():
        return

    results = search_cards_by_name(search_text)
    if not results:
        st.info(t("No card names match this search."))
        return

    st.dataframe(
        [
            {
                "collection": row["collection_name"],
                "card": f"Card #{row['card_number']}",
                "card_name": row["card_name"],
                "entry_count": row["entry_count"],
            }
            for row in results
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_card_name_editor(view_collection: dict, card_group: dict) -> None:
    card_number = int(card_group["card_number"])
    current_name = str(card_group.get("card_name") or "")
    with st.form(f"card_name_form_{view_collection['id']}_{card_number}"):
        new_name = st.text_input(
            t("Card name"),
            value=current_name,
            placeholder="weather",
            key=f"card_name_input_{view_collection['id']}_{card_number}",
        )
        submitted = st.form_submit_button(t("Save Card Name"))

    if submitted:
        try:
            set_card_name(view_collection["id"], card_number, new_name)
            st.success(t("Card name saved.") if new_name.strip() else t("Card name cleared."))
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def _sort_card_groups(card_groups: list[dict], sort_label: str) -> list[dict]:
    if sort_label == "Card name created time":
        return sorted(
            card_groups,
            key=lambda group: (
                group.get("card_created_at") or "9999",
                group["card_number"],
            ),
        )
    if sort_label == "Card name updated time":
        return sorted(
            card_groups,
            key=lambda group: (
                group.get("card_updated_at") or "9999",
                group["card_number"],
            ),
        )
    return sorted(card_groups, key=lambda group: group["card_number"])


def _render_card_display_controls(card_groups: list[dict], collection_id: int) -> list[dict]:
    st.subheader(t("Card Display"))
    control_col1, control_col2, control_col3 = st.columns(3)
    sort_options = ["Card number", "Card name created time", "Card name updated time"]
    with control_col1:
        selected_sort = st.selectbox(
            t("Sort cards by"),
            sort_options,
            format_func=t,
            key=f"card_sort_{collection_id}",
        )
    with control_col2:
        cards_per_page = st.selectbox(
            t("Cards per page"),
            [1, 2, 3, 5, 10, 20],
            index=2,
            key=f"cards_per_page_{collection_id}",
        )

    sorted_groups = _sort_card_groups(card_groups, selected_sort)
    page_count = max(ceil(len(sorted_groups) / int(cards_per_page)), 1)
    page_state_key = f"card_page_{collection_id}"
    current_page = min(max(int(st.session_state.get(page_state_key, 1)), 1), page_count)
    st.session_state[page_state_key] = current_page

    page_input_key = f"card_page_input_{collection_id}"
    if int(st.session_state.get(page_input_key, current_page)) > page_count:
        st.session_state[page_input_key] = page_count
    if int(st.session_state.get(page_input_key, current_page)) < 1:
        st.session_state[page_input_key] = 1

    with control_col3:
        selected_page = st.number_input(
            t("Card page"),
            min_value=1,
            max_value=page_count,
            value=current_page,
            step=1,
            key=page_input_key,
        )
    current_page = int(selected_page)
    st.session_state[page_state_key] = current_page

    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    with nav_col1:
        if st.button(t("Previous"), disabled=current_page <= 1, key=f"card_prev_{collection_id}"):
            st.session_state[page_state_key] = current_page - 1
            st.rerun()
    with nav_col2:
        start_number = (current_page - 1) * int(cards_per_page) + 1
        end_number = min(start_number + int(cards_per_page) - 1, len(sorted_groups))
        st.caption(
            f"{t('Showing cards')} {start_number}-{end_number} {t('of')} {len(sorted_groups)}"
        )
    with nav_col3:
        if st.button(t("Next"), disabled=current_page >= page_count, key=f"card_next_{collection_id}"):
            st.session_state[page_state_key] = current_page + 1
            st.rerun()

    start_index = (current_page - 1) * int(cards_per_page)
    end_index = start_index + int(cards_per_page)
    return sorted_groups[start_index:end_index]


def _render_special_collection_filter(
    view_collection: dict,
    collections: list[dict],
) -> list[dict] | None:
    if not _is_special_collection(view_collection):
        return None

    normal_collections = [
        collection
        for collection in collections
        if not collection.get("is_system") and collection["id"] != view_collection["id"]
    ]
    filter_options = [{"id": None, "name": "All"}] + normal_collections
    selected_related_collection = st.selectbox(
        f"Filter {view_collection['name']} entries by related collection",
        filter_options,
        format_func=lambda collection: collection["name"],
        key="special_collection_related_filter",
    )

    if selected_related_collection["id"] is None:
        return None

    return get_entries_in_special_collection_filtered(
        view_collection["system_type"],
        selected_related_collection["id"],
    )

def _render_collection_settings(collections: list[dict]) -> None:
    st.header(t("Edit Collection Settings"))

    selected_collection = st.selectbox(
        t("Select a collection to edit"),
        collections,
        format_func=collection_label,
        key="collection_settings_select",
    )
    settings_collection = get_collection_by_id(selected_collection["id"])

    if settings_collection is None:
        st.warning(t("The selected collection no longer exists."))
        return

    pending_key = f"pending_card_size_change_{settings_collection['id']}"
    pending_change = st.session_state.get(pending_key)
    if pending_change:
        st.warning(CROSS_CARD_CONFIRMATION_MESSAGE)
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Confirm Card reorganization", key=f"confirm_{pending_key}"):
                update_collection(**pending_change, confirm_cross_card=True)
                del st.session_state[pending_key]
                st.success(t("Collection updated."))
                st.rerun()
        with cancel_col:
            if st.button("Cancel", key=f"cancel_{pending_key}"):
                del st.session_state[pending_key]
                st.rerun()

    with st.form("edit_collection_form"):
        settings_name = st.text_input(t("Name"), value=settings_collection["name"])
        settings_description = st.text_area(
            t("Description"),
            value=settings_collection["description"] or "",
        )
        settings_card_size = st.number_input(
            "Card size",
            min_value=1,
            value=int(settings_collection["card_size"]),
            step=1,
            help=(
                "Recommended default: 8 entries per card. You can choose a smaller "
                "number for heavier materials such as French conjugations."
            ),
        )
        submitted = st.form_submit_button(t("Update Collection"))

    if submitted:
        try:
            update_collection(
                collection_id=settings_collection["id"],
                name=settings_name,
                description=settings_description,
                card_size=int(settings_card_size),
            )
            st.success(t("Collection updated."))
            st.rerun()
        except CrossCardMoveConfirmationRequired:
            st.session_state[pending_key] = {
                "collection_id": settings_collection["id"],
                "name": settings_name,
                "description": settings_description,
                "card_size": int(settings_card_size),
            }
            st.warning(CROSS_CARD_CONFIRMATION_MESSAGE)
        except ValueError as error:
            st.error(str(error))

    _render_delete_collection(settings_collection)


def _render_delete_collection(settings_collection: dict) -> None:
    st.subheader(t("Delete Collection"))
    if settings_collection.get("is_system"):
        st.info(t("System collections are protected and cannot be deleted."))
        return

    with st.expander(t("Delete this collection"), expanded=False):
        st.warning(
            "Deleting this collection removes its entry membership, card review schedule/history, "
            "and quiz sessions. The vocabulary entries themselves are not deleted."
        )
        confirmation_name = st.text_input(
            t("Type the collection name to confirm"),
            key=f"delete_collection_name_{settings_collection['id']}",
        )
        confirmed = st.checkbox(
            t("I understand the collection and its associated review/quiz history will be deleted."),
            key=f"delete_collection_confirm_{settings_collection['id']}",
        )
        name_matches = confirmation_name.strip() == settings_collection["name"]
        if st.button(
            t("Delete Collection"),
            type="primary",
            disabled=not confirmed or not name_matches,
            key=f"delete_collection_button_{settings_collection['id']}",
        ):
            try:
                result = delete_collection(int(settings_collection["id"]))
                st.success(
                    f"Collection '{result['collection_name']}' deleted. "
                    f"{result['detached_entry_count']} entries were kept in the vocabulary database."
                )
                st.rerun()
            except ValueError as error:
                st.error(str(error))


def _render_collection_entries(view_collection: dict, collection_entries: list[dict]) -> None:
    pending_remove_key = f"pending_cross_card_remove_{view_collection['id']}"
    pending_remove = st.session_state.get(pending_remove_key)
    if pending_remove:
        st.warning(CROSS_CARD_CONFIRMATION_MESSAGE)
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button(
                "Confirm removal and Card reorganization",
                key=f"confirm_{pending_remove_key}",
            ):
                removed_count = remove_entries_from_collection(
                    pending_remove,
                    view_collection["id"],
                    confirm_cross_card=True,
                )
                del st.session_state[pending_remove_key]
                st.success(f"{removed_count} entries removed from collection.")
                st.rerun()
        with cancel_col:
            if st.button("Cancel", key=f"cancel_{pending_remove_key}"):
                del st.session_state[pending_remove_key]
                st.rerun()

    st.subheader(t("Remove Entries from Collection"))
    selected_entries_to_remove = st.multiselect(
        t("Select entries to remove from this collection"),
        collection_entries,
        format_func=collection_entry_label,
    )
    confirm_remove = st.checkbox(
        t("I confirm I want to remove the selected entries from this collection."),
        key="confirm_remove_from_collection",
    )

    if st.button(t("Remove from Collection"), disabled=not selected_entries_to_remove):
        if not confirm_remove:
            st.warning(t("Confirm before removing entries from this collection."))
        else:
            try:
                removed_count = remove_entries_from_collection(
                    [entry["id"] for entry in selected_entries_to_remove],
                    view_collection["id"],
                )
            except CrossCardMoveConfirmationRequired:
                st.session_state[pending_remove_key] = [
                    int(entry["id"]) for entry in selected_entries_to_remove
                ]
                st.warning(CROSS_CARD_CONFIRMATION_MESSAGE)
            else:
                st.success(f"{removed_count} entries removed from collection.")
                st.rerun()

    st.subheader(t("Reorder Entries in Collection"))
    selected_move_entry = st.selectbox(
        t("Select entry to move"),
        collection_entries,
        format_func=collection_entry_label,
    )
    new_position = st.number_input(
        t("New position"),
        min_value=1,
        max_value=len(collection_entries),
        value=int(selected_move_entry["position"]),
        step=1,
    )

    pending_move_key = f"pending_cross_card_move_{view_collection['id']}"
    pending_move = st.session_state.get(pending_move_key)
    if pending_move:
        st.warning(CROSS_CARD_CONFIRMATION_MESSAGE)
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button(
                "Confirm move and Card reorganization",
                key=f"confirm_{pending_move_key}",
            ):
                move_entry_in_collection(**pending_move, confirm_cross_card=True)
                del st.session_state[pending_move_key]
                st.success(t("Entry moved."))
                st.rerun()
        with cancel_col:
            if st.button("Cancel", key=f"cancel_{pending_move_key}"):
                del st.session_state[pending_move_key]
                st.rerun()

    if st.button(t("Move Entry")):
        try:
            move_entry_in_collection(
                collection_id=view_collection["id"],
                entry_id=selected_move_entry["id"],
                new_position=int(new_position),
            )
            st.success(t("Entry moved."))
            st.rerun()
        except CrossCardMoveConfirmationRequired:
            st.session_state[pending_move_key] = {
                "collection_id": view_collection["id"],
                "entry_id": selected_move_entry["id"],
                "new_position": int(new_position),
            }
            st.warning(CROSS_CARD_CONFIRMATION_MESSAGE)
        except ValueError as error:
            st.error(str(error))

    card_groups = get_card_groups_for_collection(view_collection["id"])

    visible_card_groups = _render_card_display_controls(card_groups, view_collection["id"])

    for card_group in visible_card_groups:
        st.markdown(f"### {_card_label(card_group)}")
        _render_card_name_editor(view_collection, card_group)
        card_rows = [
            {column: entry[column] for column in COLLECTION_ENTRY_TABLE_COLUMNS}
            for entry in card_group["entries"]
        ]
        st.dataframe(card_rows, use_container_width=True, hide_index=True)


def _render_view_collection(collections: list[dict]) -> None:
    st.header(t("View Collection"))
    _render_card_name_search()

    selected_collection = st.selectbox(
        t("Select collection to view"),
        collections,
        format_func=collection_label,
        key="view_collection_select",
    )
    view_collection = get_collection_by_id(selected_collection["id"])

    if view_collection is None:
        st.warning(t("The selected collection no longer exists."))
        return

    st.write(f"Card size: {view_collection['card_size']}")
    filtered_special_entries = _render_special_collection_filter(view_collection, collections)

    if filtered_special_entries is not None:
        if filtered_special_entries:
            st.dataframe(
                [
                    {column: entry[column] for column in COLLECTION_ENTRY_TABLE_COLUMNS}
                    for entry in filtered_special_entries
                ],
                use_container_width=True,
                hide_index=True,
            )
            _render_collection_entry_detail_preview(
                filtered_special_entries,
                f"special_{view_collection['id']}",
            )
        else:
            st.info("No special collection entries match the selected related collection.")
        return

    collection_entries = get_entries_in_collection(view_collection["id"])

    if collection_entries:
        _render_collection_entry_detail_preview(
            collection_entries,
            f"collection_{view_collection['id']}",
        )
        _render_collection_entries(view_collection, collection_entries)
    else:
        st.info(t("This collection has no entries yet."))


def render_collections_page() -> None:
    st.title(t("Collections"))
    selected_section = st.radio(
        t("Collections section"),
        ["Create & List", "Edit"],
        horizontal=True,
        label_visibility="collapsed",
        format_func=t,
    )

    collections = get_collections()

    if selected_section == "Create & List":
        _render_create_collection()
        collections = get_collections()
        _render_collection_list(collections)
    else:
        if collections:
            _render_collection_settings(collections)
            _render_view_collection(collections)
        else:
            st.info(t("Create a collection before editing or viewing collections."))

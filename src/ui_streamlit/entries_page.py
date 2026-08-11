import streamlit as st

from src.collections import (
    add_entries_to_collection,
    add_entries_to_system_collection,
    add_entry_to_collections,
    get_collection_ids_for_entry,
    get_collections,
    resolve_collection_names,
    update_entry_collections,
)
from src.entries import (
    add_entry,
    create_entry_with_template,
    delete_entries,
    get_entry_detail_with_template_values,
    get_entry_with_template_values,
    search_entries,
    update_entry_with_template,
)
from src.entry_templates import (
    GENERAL_ENTRY_TEMPLATE_NAME,
    get_canonical_mapping,
    get_entry_templates,
    get_template_fields,
)
from src.text_parser import parse_and_validate_entry_card
from src.ui_streamlit.templates_page import render_templates_page
from src.ui_streamlit.common import (
    ENTRY_TYPES,
    EXPLANATION_LANGUAGES,
    LANGUAGES,
    STATUSES,
    TABLE_COLUMNS,
    collection_label,
    entry_label,
    option_index,
)


def _clear_selection() -> None:
    st.session_state.selection_mode = False
    st.session_state.selected_entry_ids = set()
    st.session_state.selection_token += 1


def _checkbox_key(entry_id: int) -> str:
    return f"select_entry_{st.session_state.selection_token}_{entry_id}"


def _edit_widget_key(entry_id: int, field_name: str) -> str:
    return f"edit_entry_{int(entry_id)}_{field_name}"


def _sync_visible_selection(entries: list[dict]) -> None:
    for entry in entries:
        checkbox_key = _checkbox_key(entry["id"])

        if checkbox_key not in st.session_state:
            continue

        if st.session_state[checkbox_key]:
            st.session_state.selected_entry_ids.add(entry["id"])
        else:
            st.session_state.selected_entry_ids.discard(entry["id"])


def _ensure_selection_state() -> None:
    if "selection_mode" not in st.session_state:
        st.session_state.selection_mode = False

    if "selected_entry_ids" not in st.session_state:
        st.session_state.selected_entry_ids = set()

    if "selection_token" not in st.session_state:
        st.session_state.selection_token = 0


def _template_label(template: dict) -> str:
    return f"{template['id']} - {template['name']}"


def _general_template_index(templates: list[dict]) -> int:
    for index, template in enumerate(templates):
        if template["name"] == GENERAL_ENTRY_TEMPLATE_NAME:
            return index
    return 0


def _render_template_value_inputs(
    fields: list[dict],
    defaults: dict | None = None,
    key_prefix: str = "template_value",
) -> dict:
    defaults = defaults or {}
    template_values = {}

    for field in fields:
        field_key = field["field_key"]
        label = field["field_label"]
        if field["required"]:
            label = f"{label} *"

        default_value = str(defaults.get(field_key, "") or "")
        widget_key = f"{key_prefix}_{field['id']}"
        if field["field_type"] == "long_text":
            value = st.text_area(label, value=default_value, key=widget_key)
        else:
            value = st.text_input(label, value=default_value, key=widget_key)

        template_values[field_key] = value

    return template_values


def _render_mapping_note(template_id: int) -> dict:
    mapping = get_canonical_mapping(template_id)
    term_source = mapping["term_source"] or "manual input"
    meaning_source = mapping["meaning_source"] or "manual input"
    st.caption(
        f"Canonical mapping: term <- {term_source}; meaning <- {meaning_source}."
    )
    return mapping


def _show_errors(error: ValueError) -> None:
    st.error("Validation failed. Please fix the highlighted issue(s) below; your input has been kept.")
    for message in str(error).splitlines():
        if message.strip():
            st.error(message)



def _render_entry_template_values_preview(entries: list[dict]) -> None:
    if not entries:
        return

    st.subheader("Entry Detail Preview")
    selected_entry = st.selectbox(
        "Select entry to preview",
        entries,
        format_func=entry_label,
        key="management_entry_detail_preview",
    )
    detail = get_entry_detail_with_template_values(selected_entry["id"])
    if detail is None:
        st.warning("The selected entry no longer exists.")
        return

    canonical_rows = [
        {"field": "template", "value": detail.get("template_name") or ""},
        {"field": "term", "value": detail.get("term") or ""},
        {"field": "meaning", "value": detail.get("meaning") or ""},
        {"field": "example", "value": detail.get("example") or ""},
        {"field": "notes", "value": detail.get("notes") or ""},
        {"field": "tags", "value": detail.get("tags") or ""},
        {"field": "source", "value": detail.get("source") or ""},
    ]
    st.dataframe(canonical_rows, use_container_width=True, hide_index=True)

    with st.expander("Template Field Values", expanded=False):
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
            st.info("No template field values found for this entry.")


def _render_add_entry(collections: list[dict]) -> None:
    st.header("Add Entry")

    templates = get_entry_templates()
    if not templates:
        st.warning("No entry templates found. Restart the app to initialize templates.")
        return

    selected_template = st.selectbox(
        "Select Entry Template",
        templates,
        index=_general_template_index(templates),
        format_func=_template_label,
        key="add_entry_template_select",
    )
    fields = get_template_fields(selected_template["id"])
    mapping = _render_mapping_note(selected_template["id"])

    with st.form("add_entry_form"):
        meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
        with meta_col1:
            language = st.selectbox("Language", LANGUAGES)
        with meta_col2:
            explanation_language = st.selectbox("Explanation Language", EXPLANATION_LANGUAGES)
        with meta_col3:
            entry_type = st.selectbox("Entry Type", ENTRY_TYPES)
        with meta_col4:
            status = st.selectbox("Status", STATUSES)

        st.subheader("Template Fields")
        template_values = _render_template_value_inputs(
            fields,
            key_prefix=f"add_template_{selected_template['id']}",
        )

        manual_term = ""
        manual_meaning = ""
        if mapping["needs_manual_term"] or mapping["needs_manual_meaning"]:
            st.subheader("Canonical Fields")
            if mapping["needs_manual_term"]:
                manual_term = st.text_input("Canonical Term *")
            if mapping["needs_manual_meaning"]:
                manual_meaning = st.text_area("Canonical Meaning *")

        if collections:
            selected_add_collections = st.multiselect(
                "Collections",
                collections,
                format_func=collection_label,
            )
        else:
            selected_add_collections = []
            st.info("No collections yet. You can still create the entry now.")

        submitted = st.form_submit_button("Add Entry")

    if submitted:
        try:
            entry_id = create_entry_with_template(
                entry_data={
                    "template_id": selected_template["id"],
                    "language": language,
                    "explanation_language": explanation_language,
                    "entry_type": entry_type,
                    "status": status,
                },
                template_values=template_values,
                manual_term=manual_term,
                manual_meaning=manual_meaning,
            )
        except ValueError as error:
            _show_errors(error)
        else:
            if selected_add_collections:
                add_result = add_entry_to_collections(
                    entry_id,
                    [collection["id"] for collection in selected_add_collections],
                )
                st.success(
                    f"Entry saved and added to {add_result['added_count']} collection(s)."
                )
            else:
                st.success("Entry saved.")


def _render_quick_add() -> None:
    st.header("Quick Add from Text Card")
    st.caption("Quick Add currently creates General Entry items.")

    quick_add_placeholder = """language: English
explanation_language: Chinese
entry_type: phrase
term: cope with stress
meaning: cope with pressure or difficulty
example: I am learning how to cope with stress.
notes: phrase test
tags: speaking, emotion
source: manual test
status: learning
collections: IELTS Speaking; French TCF"""

    with st.form("quick_add_entry_form"):
        entry_card_text = st.text_area(
            "Paste structured entry card",
            placeholder=quick_add_placeholder,
            height=220,
        )
        quick_add_submitted = st.form_submit_button("Create Entry from Text Card")

    if quick_add_submitted:
        parsed_entry, parse_errors = parse_and_validate_entry_card(entry_card_text)

        if parse_errors:
            for error in parse_errors:
                st.error(error)
        elif parsed_entry is not None:
            quick_add_collections, missing_collection_names = resolve_collection_names(
                parsed_entry["collections"]
            )

            if missing_collection_names:
                st.error(
                    "Unknown collection(s): " + ", ".join(missing_collection_names)
                )
            else:
                entry_id = add_entry(
                    language=parsed_entry["language"],
                    explanation_language=parsed_entry["explanation_language"],
                    entry_type=parsed_entry["entry_type"],
                    term=parsed_entry["term"],
                    meaning=parsed_entry["meaning"],
                    example=parsed_entry["example"],
                    notes=parsed_entry["notes"],
                    tags=parsed_entry["tags"],
                    source=parsed_entry["source"],
                    status=parsed_entry["status"],
                )
                if quick_add_collections:
                    add_result = add_entry_to_collections(
                        entry_id,
                        [collection["id"] for collection in quick_add_collections],
                    )
                    st.success(
                        "Entry created from text card and added to "
                        f"{add_result['added_count']} collection(s)."
                    )
                else:
                    st.success("Entry created from text card.")
                st.rerun()


def _render_entries_table(entries: list[dict], collections: list[dict]) -> None:
    entries_title_col, entries_action_col = st.columns([5, 1])

    with entries_title_col:
        st.header("Entries")

    with entries_action_col:
        if not st.session_state.selection_mode:
            if st.button("Select"):
                st.session_state.selection_mode = True
                st.session_state.selected_entry_ids = set()
                st.session_state.selection_token += 1
                st.rerun()

    visible_entry_ids = {entry["id"] for entry in entries}
    st.session_state.selected_entry_ids = {
        entry_id
        for entry_id in st.session_state.selected_entry_ids
        if entry_id in visible_entry_ids
    }

    if entries and not st.session_state.selection_mode:
        table_rows = [{column: entry.get(column, "") for column in TABLE_COLUMNS} for entry in entries]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)
    elif entries:
        _sync_visible_selection(entries)
        selected_count = len(st.session_state.selected_entry_ids)
        action_col1, action_col2, action_col3, action_col4, action_col5, action_col6 = st.columns(
            [1.2, 2.0, 1.5, 1.9, 2.4, 1.2]
        )

        with action_col1:
            st.write(f"Selected count: {selected_count}")

        with action_col2:
            if collections:
                target_collection = st.selectbox(
                    "Target collection",
                    collections,
                    format_func=collection_label,
                    key="select_mode_target_collection",
                )
                if st.button("Add to Collection"):
                    if selected_count == 0:
                        st.warning("Select at least one entry to add to a collection.")
                    else:
                        added_count = add_entries_to_collection(
                            sorted(st.session_state.selected_entry_ids),
                            target_collection["id"],
                        )
                        st.success(f"{added_count} entries added to collection.")
                        _clear_selection()
                        st.rerun()
            else:
                st.info("Please create a collection first.")

        with action_col3:
            if st.button("Add to Starred", disabled=selected_count == 0):
                added_count = add_entries_to_system_collection(
                    sorted(st.session_state.selected_entry_ids),
                    "starred",
                )
                st.success(f"{added_count} entries added to Starred.")
                _clear_selection()
                st.rerun()

        with action_col4:
            if st.button("Add to Proficient Pool", disabled=selected_count == 0):
                added_count = add_entries_to_system_collection(
                    sorted(st.session_state.selected_entry_ids),
                    "proficient_pool",
                )
                st.success(f"{added_count} entries added to Proficient Pool.")
                _clear_selection()
                st.rerun()

        with action_col5:
            confirm_selection_delete = st.checkbox(
                "I confirm I want to delete the selected entries.",
                key="confirm_selection_delete",
            )
            if st.button("Delete Selected", disabled=selected_count == 0):
                if not confirm_selection_delete:
                    st.warning("Confirm deletion before deleting selected entries.")
                else:
                    deleted_count = delete_entries(
                        sorted(st.session_state.selected_entry_ids)
                    )
                    st.success(f"{deleted_count} entries deleted.")
                    _clear_selection()
                    st.rerun()

        with action_col6:
            if st.button("Cancel Selection"):
                _clear_selection()
                st.rerun()

        if selected_count > 0:
            selected_preview = [
                {column: entry.get(column, "") for column in TABLE_COLUMNS}
                for entry in entries
                if entry["id"] in st.session_state.selected_entry_ids
            ]
            st.dataframe(selected_preview, use_container_width=True, hide_index=True)

        header_cols = st.columns([0.6, 0.8, 1.2, 1.3, 1.5, 2.2, 3, 1.5, 1.5, 1.1])
        for column, label in zip(
            header_cols,
            [
                "Select",
                "ID",
                "Language",
                "Type",
                "Template",
                "Term",
                "Meaning",
                "Tags",
                "Source",
                "Status",
            ],
            strict=False,
        ):
            column.markdown(f"**{label}**")

        for entry in entries:
            row_cols = st.columns([0.6, 0.8, 1.2, 1.3, 1.5, 2.2, 3, 1.5, 1.5, 1.1])
            checkbox_key = _checkbox_key(entry["id"])
            is_selected = entry["id"] in st.session_state.selected_entry_ids

            selected_now = row_cols[0].checkbox(
                "Select entry",
                value=is_selected,
                key=checkbox_key,
                label_visibility="collapsed",
            )

            if selected_now:
                st.session_state.selected_entry_ids.add(entry["id"])
            else:
                st.session_state.selected_entry_ids.discard(entry["id"])

            row_cols[1].write(entry["id"])
            row_cols[2].write(entry["language"])
            row_cols[3].write(entry["entry_type"])
            row_cols[4].write(entry.get("template_name", ""))
            row_cols[5].write(entry["term"])
            row_cols[6].write(entry["meaning"])
            row_cols[7].write(entry["tags"] or "")
            row_cols[8].write(entry["source"] or "")
            row_cols[9].write(entry["status"])
    else:
        st.info("No entries match the current search and filters.")


def _render_edit_entry(all_entries: list[dict]) -> None:
    st.header("Edit Entry")

    if not all_entries:
        st.info("No entries available to edit.")
        return

    selected_edit_entry = st.selectbox(
        "Select an entry to edit",
        all_entries,
        format_func=entry_label,
        key="edit_entry_select",
    )
    edit_entry = get_entry_with_template_values(selected_edit_entry["id"])

    if edit_entry is None:
        st.warning("The selected entry no longer exists.")
        return

    st.write(f"Template: {edit_entry.get('template_name') or 'Unknown'}")
    st.caption("Entry template cannot be changed in this milestone.")

    fields = get_template_fields(edit_entry["template_id"])
    mapping = _render_mapping_note(edit_entry["template_id"])
    value_defaults = {
        key: value_data["field_value"]
        for key, value_data in edit_entry["template_values"].items()
    }
    collections = get_collections()
    editable_collections = [
        collection for collection in collections if not collection.get("is_system")
    ]
    current_collection_ids = set(get_collection_ids_for_entry(edit_entry["id"]))
    current_editable_collections = [
        collection
        for collection in editable_collections
        if int(collection["id"]) in current_collection_ids
    ]

    entry_id = int(edit_entry["id"])
    with st.form(f"edit_entry_form_{entry_id}"):
        meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
        with meta_col1:
            edit_language = st.selectbox(
                "Language",
                LANGUAGES,
                index=option_index(LANGUAGES, edit_entry["language"]),
                key=_edit_widget_key(entry_id, "language"),
            )
        with meta_col2:
            edit_explanation_language = st.selectbox(
                "Explanation Language",
                EXPLANATION_LANGUAGES,
                index=option_index(
                    EXPLANATION_LANGUAGES,
                    edit_entry["explanation_language"],
                ),
                key=_edit_widget_key(entry_id, "explanation_language"),
            )
        with meta_col3:
            edit_entry_type = st.selectbox(
                "Entry Type",
                ENTRY_TYPES,
                index=option_index(ENTRY_TYPES, edit_entry["entry_type"]),
                key=_edit_widget_key(entry_id, "entry_type"),
            )
        with meta_col4:
            edit_status = st.selectbox(
                "Status",
                STATUSES,
                index=option_index(STATUSES, edit_entry["status"]),
                key=_edit_widget_key(entry_id, "status"),
            )

        st.subheader("Template Fields")
        template_values = _render_template_value_inputs(
            fields,
            defaults=value_defaults,
            key_prefix=f"edit_template_{edit_entry['id']}",
        )

        manual_term = ""
        manual_meaning = ""
        if mapping["needs_manual_term"] or mapping["needs_manual_meaning"]:
            st.subheader("Canonical Fields")
            if mapping["needs_manual_term"]:
                manual_term = st.text_input(
                    "Canonical Term *",
                    value=edit_entry["term"] or "",
                    key=_edit_widget_key(entry_id, "canonical_term"),
                )
            if mapping["needs_manual_meaning"]:
                manual_meaning = st.text_area(
                    "Canonical Meaning *",
                    value=edit_entry["meaning"] or "",
                    key=_edit_widget_key(entry_id, "canonical_meaning"),
                )

        st.subheader("Collections")
        if editable_collections:
            selected_edit_collections = st.multiselect(
                "Entry Collections",
                editable_collections,
                default=current_editable_collections,
                format_func=collection_label,
                key=_edit_widget_key(entry_id, "collections"),
            )
        else:
            selected_edit_collections = []
            st.info("No editable user collections exist yet.")

        edit_submitted = st.form_submit_button("Save Changes")

    if edit_submitted:
        try:
            update_entry_with_template(
                entry_id=edit_entry["id"],
                entry_data={
                    "language": edit_language,
                    "explanation_language": edit_explanation_language,
                    "entry_type": edit_entry_type,
                    "status": edit_status,
                },
                template_values=template_values,
                manual_term=manual_term,
                manual_meaning=manual_meaning,
            )
            if editable_collections:
                update_entry_collections(
                    entry_id=edit_entry["id"],
                    desired_collection_ids=[
                        collection["id"] for collection in selected_edit_collections
                    ],
                    managed_collection_ids=[
                        collection["id"] for collection in editable_collections
                    ],
                )
        except ValueError as error:
            _show_errors(error)
        else:
            st.success("Entry updated.")
            st.rerun()


def _render_entries_management(collections: list[dict]) -> None:
    st.header("Search and Filter")
    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(5)
    templates = get_entry_templates()
    template_options = [{"id": "All", "name": "All"}] + templates

    with filter_col1:
        search_text = st.text_input("Search term, meaning, tags, source, or template fields")
    with filter_col2:
        language_filter = st.selectbox("Filter by language", ["All"] + LANGUAGES)
    with filter_col3:
        entry_type_filter = st.selectbox("Filter by entry type", ["All"] + ENTRY_TYPES)
    with filter_col4:
        status_filter = st.selectbox("Filter by status", ["All"] + STATUSES)
    with filter_col5:
        template_filter = st.selectbox(
            "Filter by template",
            template_options,
            format_func=lambda template: template["name"],
        )

    entries = search_entries(
        search_text=search_text,
        language=language_filter,
        entry_type=entry_type_filter,
        status=status_filter,
        template_id=template_filter["id"],
    )
    _render_entries_table(entries, collections)
    _render_entry_template_values_preview(entries)


def render_entries_page() -> None:
    _ensure_selection_state()
    st.title("Entries")
    selected_section = st.radio(
        "Entries section",
        ["Add", "Management", "Edit", "Templates"],
        horizontal=True,
        label_visibility="collapsed",
    )

    collections = get_collections()

    if selected_section == "Add":
        _render_add_entry(collections)
        _render_quick_add()
    elif selected_section == "Management":
        _render_entries_management(collections)
    elif selected_section == "Edit":
        all_entries = search_entries()
        _render_edit_entry(all_entries)
    else:
        render_templates_page()

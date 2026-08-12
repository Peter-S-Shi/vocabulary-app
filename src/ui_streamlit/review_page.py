import streamlit as st


from src.collections import get_card_groups_for_collection
from src.db import get_connection
from src.entries import update_entry
from src.learning_workflow import get_review_focus_payload, get_study_cards
from src.ui_streamlit.common import (
    ENTRY_TYPES,
    EXPLANATION_LANGUAGES,
    LANGUAGES,
    REVIEW_ENTRY_TABLE_COLUMNS,
    STATUSES,
    option_index,
    render_back_to_today_button,
    set_page_focus,
)


REVIEW_FOCUS_KEYS = [
    "review_focus_collection_id",
    "review_focus_card_number",
    "review_focus_card_id",
    "review_focus_source",
    "review_focus_created_at",
    "review_focus_return_page",
    "review_focus_reason",
    "focus_review_collection_id",
    "focus_review_card_number",
]


def _find_card_entries(collection_id: int, card_number: int) -> list[dict]:
    card_groups = get_card_groups_for_collection(collection_id)

    for card_group in card_groups:
        if card_group["card_number"] == card_number:
            return card_group["entries"]

    return []


def _clear_review_focus() -> None:
    for key in REVIEW_FOCUS_KEYS:
        st.session_state.pop(key, None)


def _get_review_focus() -> dict | None:
    collection_id = st.session_state.get("review_focus_collection_id")
    if collection_id is None:
        collection_id = st.session_state.get("focus_review_collection_id")
    card_number = st.session_state.get("review_focus_card_number")
    if card_number is None:
        card_number = st.session_state.get("focus_review_card_number")

    if collection_id is None or card_number is None:
        return None

    try:
        with get_connection() as conn:
            payload = get_review_focus_payload(
                conn,
                int(collection_id),
                int(card_number),
            )
    except (TypeError, ValueError):
        _clear_review_focus()
        return None

    if payload is None:
        return None

    expected_card_id = st.session_state.get("review_focus_card_id")
    if expected_card_id is None or int(expected_card_id) != int(payload["card_id"]):
        return None

    payload["source"] = st.session_state.get("review_focus_source")
    payload["reason"] = st.session_state.get("review_focus_reason")
    payload["created_at"] = st.session_state.get("review_focus_created_at")
    return payload


def _is_focus_for_card(card: dict) -> bool:
    focus_collection_id = st.session_state.get("review_focus_collection_id")
    if focus_collection_id is None:
        focus_collection_id = st.session_state.get("focus_review_collection_id")
    focus_card_number = st.session_state.get("review_focus_card_number")
    if focus_card_number is None:
        focus_card_number = st.session_state.get("focus_review_card_number")
    return (
        focus_collection_id == card["collection_id"]
        and focus_card_number == card["card_number"]
    )


def _find_matching_card(study_cards: list[dict], focus_payload: dict) -> dict | None:
    for card in study_cards:
        if (
            card["collection_id"] == focus_payload["collection_id"]
            and card["card_number"] == focus_payload["card_number"]
        ):
            return card
    return None


def _focused_card_index(study_cards: list[dict], focus_payload: dict | None) -> int:
    if focus_payload is None:
        return 0

    for index, card in enumerate(study_cards):
        if (
            card["collection_id"] == focus_payload["collection_id"]
            and card["card_number"] == focus_payload["card_number"]
        ):
            return index

    return 0


def _render_focus_banner(focus_payload: dict | None, study_cards: list[dict]) -> None:
    if (
        st.session_state.get("review_focus_collection_id") is None
        and st.session_state.get("focus_review_collection_id") is None
    ):
        return

    if focus_payload is None:
        st.warning("The focused card from Today is no longer available. The focus was cleared.")
        _clear_review_focus()
        return

    focus_match = _find_matching_card(study_cards, focus_payload)
    availability = (
        "This Card is available to study or quiz."
        if focus_match is not None
        else "This Card is no longer available in its current Collection position."
    )

    st.info(
        "Focused from Today: "
        f"{focus_payload['collection_name']} / Card #{focus_payload['card_number']}. "
        f"{availability}"
    )

    if st.button("Clear Today focus", key="clear_today_review_focus"):
        _clear_review_focus()
        st.success("Today focus cleared.")
        st.rerun()


def _review_card_state_prefix(selected_due_card: dict) -> str:
    return f"review_card_{selected_due_card['collection_id']}_{selected_due_card['card_number']}"


def _clamp_review_card_index(selected_due_card: dict, entries: list[dict]) -> int:
    prefix = _review_card_state_prefix(selected_due_card)
    index_key = f"{prefix}_index"
    current_index = int(st.session_state.get(index_key, 0) or 0)
    max_index = max(len(entries) - 1, 0)
    current_index = min(max(current_index, 0), max_index)
    st.session_state[index_key] = current_index
    return current_index


def _set_review_card_index(selected_due_card: dict, entries: list[dict], index: int) -> None:
    prefix = _review_card_state_prefix(selected_due_card)
    max_index = max(len(entries) - 1, 0)
    st.session_state[f"{prefix}_index"] = min(max(index, 0), max_index)
    st.session_state[f"{prefix}_flipped"] = False


def _handle_flashcard_click(selected_due_card: dict, entries: list[dict]) -> None:
    prefix = _review_card_state_prefix(selected_due_card)
    flipped_key = f"{prefix}_flipped"
    current_index = _clamp_review_card_index(selected_due_card, entries)

    if st.session_state.get(flipped_key):
        next_index = current_index + 1
        if next_index >= len(entries):
            next_index = 0
        _set_review_card_index(selected_due_card, entries, next_index)
    else:
        st.session_state[flipped_key] = True

    st.rerun()


def _render_flashcard_navigation(selected_due_card: dict, entries: list[dict]) -> None:
    prefix = _review_card_state_prefix(selected_due_card)
    current_index = _clamp_review_card_index(selected_due_card, entries)
    last_index = max(len(entries) - 1, 0)
    nav_cols = st.columns(4)

    with nav_cols[0]:
        if st.button("|<", key=f"{prefix}_first"):
            _set_review_card_index(selected_due_card, entries, 0)
            st.rerun()
    with nav_cols[1]:
        if st.button("<", key=f"{prefix}_prev"):
            _set_review_card_index(selected_due_card, entries, current_index - 1)
            st.rerun()
    with nav_cols[2]:
        if st.button(">", key=f"{prefix}_next"):
            _set_review_card_index(selected_due_card, entries, current_index + 1)
            st.rerun()
    with nav_cols[3]:
        if st.button(">|", key=f"{prefix}_last"):
            _set_review_card_index(selected_due_card, entries, last_index)
            st.rerun()


def _render_entry_extra_info(entry: dict) -> None:
    detail_rows = [
        {"field": "id", "value": entry.get("id", "")},
        {"field": "position", "value": entry.get("position", "")},
        {"field": "language", "value": entry.get("language", "")},
        {"field": "explanation_language", "value": entry.get("explanation_language", "")},
        {"field": "entry_type", "value": entry.get("entry_type", "")},
        {"field": "template_name", "value": entry.get("template_name", "")},
        {"field": "example", "value": entry.get("example", "")},
        {"field": "notes", "value": entry.get("notes", "")},
        {"field": "tags", "value": entry.get("tags", "")},
        {"field": "source", "value": entry.get("source", "")},
        {"field": "status", "value": entry.get("status", "")},
        {"field": "correct_count", "value": entry.get("correct_count", "")},
        {"field": "wrong_count", "value": entry.get("wrong_count", "")},
        {"field": "created_at", "value": entry.get("created_at", "")},
        {"field": "updated_at", "value": entry.get("updated_at", "")},
    ]
    with st.expander("Other item properties", expanded=False):
        st.dataframe(detail_rows, use_container_width=True, hide_index=True)


def _render_review_entry_editor(selected_due_card: dict, entry: dict) -> None:
    prefix = _review_card_state_prefix(selected_due_card)
    edit_key = f"{prefix}_edit_entry_{entry['id']}"

    if not st.session_state.get(edit_key):
        if st.button("Edit", key=f"{edit_key}_open"):
            st.session_state[edit_key] = True
            st.rerun()
        return

    with st.form(f"{edit_key}_form"):
        meta_col1, meta_col2 = st.columns(2)
        with meta_col1:
            language = st.selectbox(
                "Language",
                LANGUAGES,
                index=option_index(LANGUAGES, entry.get("language", "")),
                key=f"{edit_key}_language",
            )
            entry_type = st.selectbox(
                "Entry Type",
                ENTRY_TYPES,
                index=option_index(ENTRY_TYPES, entry.get("entry_type", "")),
                key=f"{edit_key}_entry_type",
            )
        with meta_col2:
            explanation_language = st.selectbox(
                "Explanation Language",
                EXPLANATION_LANGUAGES,
                index=option_index(EXPLANATION_LANGUAGES, entry.get("explanation_language", "")),
                key=f"{edit_key}_explanation_language",
            )
            status = st.selectbox(
                "Status",
                STATUSES,
                index=option_index(STATUSES, entry.get("status", "")),
                key=f"{edit_key}_status",
            )

        term = st.text_input("Term", value=entry.get("term", ""), key=f"{edit_key}_term")
        meaning = st.text_area("Meaning", value=entry.get("meaning", ""), key=f"{edit_key}_meaning")
        example = st.text_area("Example", value=entry.get("example", ""), key=f"{edit_key}_example")
        notes = st.text_area("Notes", value=entry.get("notes", ""), key=f"{edit_key}_notes")
        tags = st.text_input("Tags", value=entry.get("tags", ""), key=f"{edit_key}_tags")
        source = st.text_input("Source", value=entry.get("source", ""), key=f"{edit_key}_source")

        save_col, cancel_col = st.columns(2)
        with save_col:
            save_submitted = st.form_submit_button("Save Changes")
        with cancel_col:
            cancel_submitted = st.form_submit_button("Cancel")

    if cancel_submitted:
        st.session_state[edit_key] = False
        st.rerun()

    if save_submitted:
        try:
            update_entry(
                entry_id=int(entry["id"]),
                language=language,
                explanation_language=explanation_language,
                entry_type=entry_type,
                term=term,
                meaning=meaning,
                example=example,
                notes=notes,
                tags=tags,
                source=source,
                status=status,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state[edit_key] = False
            st.success("Entry updated.")
            st.rerun()


def _render_review_flashcard_panel(selected_due_card: dict, entries: list[dict]) -> None:
    if not entries:
        return

    prefix = _review_card_state_prefix(selected_due_card)
    current_index = _clamp_review_card_index(selected_due_card, entries)
    current_entry = entries[current_index]
    is_flipped = bool(st.session_state.get(f"{prefix}_flipped"))
    face_label = "Meaning" if is_flipped else "Term"
    face_value = current_entry.get("meaning", "") if is_flipped else current_entry.get("term", "")

    st.subheader("Card View")
    st.caption(f"Item {current_index + 1} / {len(entries)} - {face_label}")
    if st.button(
        str(face_value or "(empty)"),
        key=f"{prefix}_flashcard_face",
        use_container_width=True,
    ):
        _handle_flashcard_click(selected_due_card, entries)

    st.caption(
        "Click again to move to the next item."
        if is_flipped
        else "Click once to reveal the meaning."
    )

    _render_flashcard_navigation(selected_due_card, entries)
    _render_entry_extra_info(current_entry)
    _render_review_entry_editor(selected_due_card, current_entry)


def _render_selected_card_review(selected_due_card: dict, entries: list[dict]) -> None:
    if not entries:
        st.warning("This card has no entries to review.")
        return

    card_view_tab, table_view_tab = st.tabs(["Card View", "Table View"])

    with card_view_tab:
        _render_review_flashcard_panel(selected_due_card, entries)

    with table_view_tab:
        review_rows = [
            {column: entry.get(column, "") for column in REVIEW_ENTRY_TABLE_COLUMNS}
            for entry in entries
        ]
        st.dataframe(review_rows, use_container_width=True, hide_index=True)


def _review_quiz_focus_values(selected_card: dict, autostart: bool) -> dict:
    reason = "review_quick_quiz" if autostart else "review_choose_quiz_type"
    return {
        "quiz_focus_collection_id": selected_card["collection_id"],
        "quiz_focus_card_number": selected_card["card_number"],
        "quiz_focus_card_id": selected_card.get("card_id"),
        "quiz_focus_type": "mixed_mcq",
        "quiz_focus_source": "review_selected_card",
        "quiz_focus_reason": reason,
        "quiz_focus_title": (
            f"{selected_card['collection_name']} / Card #{selected_card['card_number']}"
        ),
        "focus_quiz_collection_id": selected_card["collection_id"],
        "focus_quiz_card_number": selected_card["card_number"],
        "focus_quiz_source": reason,
    }


def _save_review_card_quiz_focus(selected_due_card: dict, autostart: bool) -> None:
    for key, value in _review_quiz_focus_values(selected_due_card, autostart).items():
        st.session_state[key] = value
    if autostart:
        st.session_state["quiz_autostart_focus"] = True
    else:
        st.session_state.pop("quiz_autostart_focus", None)
    set_page_focus("Quiz")
    st.info("Quiz focus saved. Continue on the Quiz page.")
    st.rerun()


def render_review_page() -> None:
    st.title("Review")
    st.caption(
        "Browse and study a Card here. Browsing does not complete learning; "
        "a completed Card-scoped Quiz records the Card learning event."
    )
    render_back_to_today_button("review_back_to_today_top")

    with get_connection() as conn:
        study_cards = get_study_cards(conn)
    focus_payload = _get_review_focus()

    st.header("Available Study Cards")
    _render_focus_banner(focus_payload, study_cards)

    if not study_cards:
        st.info("No Cards are available. Add entries to a Collection first.")
        return

    study_card_rows = [
        {
            "collection_name": card["collection_name"],
            "card_number": card["card_number"],
            "card_size": card["card_size"],
            "entry_count": card["entry_count"],
            "card_quiz_completions": card["completion_count"],
            "last_card_quiz": card["last_completed_at"],
        }
        for card in study_cards
    ]
    st.dataframe(study_card_rows, use_container_width=True, hide_index=True)

    selected_due_card = st.selectbox(
        "Select a Card to study",
        study_cards,
        index=_focused_card_index(study_cards, focus_payload),
        format_func=lambda card: (
            f"{card['collection_name']} | Card #{card['card_number']} | "
            f"{card['entry_count']} entries"
        ),
    )

    st.header("Study Selected Card")
    st.write(
        f"{selected_due_card['collection_name']} - Card #{selected_due_card['card_number']}"
    )
    quiz_col1, quiz_col2 = st.columns(2)
    with quiz_col1:
        if st.button("Quick Quiz", key="review_quick_quiz", type="primary"):
            _save_review_card_quiz_focus(selected_due_card, autostart=True)
    with quiz_col2:
        if st.button("Choose Quiz Type", key="review_choose_quiz_type"):
            _save_review_card_quiz_focus(selected_due_card, autostart=False)

    selected_card_entries = _find_card_entries(
        selected_due_card["collection_id"],
        selected_due_card["card_number"],
    )

    _render_selected_card_review(selected_due_card, selected_card_entries)

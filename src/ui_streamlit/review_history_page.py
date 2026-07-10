from datetime import date

import streamlit as st

from src.collections import get_card_groups_for_collection, get_collections
from src.review import (
    get_card_review_logs,
    get_card_review_state,
    sync_all_card_review_states,
    update_card_next_due_at,
)
from src.ui_streamlit.common import collection_label


def _find_index_by_id(items: list[dict], item_id: int | None) -> int:
    if item_id is None:
        return 0

    for index, item in enumerate(items):
        if item["id"] == item_id:
            return index

    return 0


def _find_index_by_value(values: list[int], selected_value: int | None) -> int:
    if selected_value is None:
        return 0

    if selected_value in values:
        return values.index(selected_value)

    return 0


def _prepare_review_schedule_focus() -> tuple[int | None, int | None]:
    focus_collection_id = st.session_state.get("review_schedule_focus_collection_id")
    focus_card_number = st.session_state.get("review_schedule_focus_card_number")
    focus_token = (focus_collection_id, focus_card_number)

    if focus_collection_id is not None and st.session_state.get(
        "review_schedule_focus_applied"
    ) != focus_token:
        st.session_state.pop("manage_review_collection_select", None)
        st.session_state.pop("manage_review_card_select", None)
        st.session_state.pop("manual_next_due_at", None)
        st.session_state["review_schedule_focus_applied"] = focus_token

    return focus_collection_id, focus_card_number


def _render_manage_schedule(collections: list[dict]) -> None:
    st.header("Manage Card Review Schedule")

    if not collections:
        st.info("Create a collection before managing review dates.")
        return

    focus_collection_id, focus_card_number = _prepare_review_schedule_focus()
    focused = focus_collection_id is not None and focus_card_number is not None

    if focused:
        st.info("Focused on the card selected from Quiz Summary.")

    management_collection = st.selectbox(
        "Select collection to manage",
        collections,
        index=_find_index_by_id(collections, focus_collection_id),
        format_func=collection_label,
        key="manage_review_collection_select",
    )
    management_groups = get_card_groups_for_collection(management_collection["id"])

    if not management_groups:
        st.info("This collection has no cards yet.")
        return

    management_card_numbers = [group["card_number"] for group in management_groups]
    card_index = 0
    if management_collection["id"] == focus_collection_id:
        card_index = _find_index_by_value(management_card_numbers, focus_card_number)

    management_card_number = st.selectbox(
        "Select card number to manage",
        management_card_numbers,
        index=card_index,
        format_func=lambda card_number: f"Card #{card_number}",
        key="manage_review_card_select",
    )
    current_state = get_card_review_state(
        management_collection["id"],
        management_card_number,
    )

    if current_state is None:
        sync_all_card_review_states()
        current_state = get_card_review_state(
            management_collection["id"],
            management_card_number,
        )

    if current_state is None:
        st.warning("Review state is not available for this card.")
        return

    state_rows = [
        {
            "status": current_state["status"],
            "review_count": current_state["review_count"],
            "current_interval_days": current_state["current_interval_days"],
            "next_due_at": current_state["next_due_at"],
        }
    ]
    st.dataframe(state_rows, use_container_width=True, hide_index=True)

    current_next_due_at = current_state["next_due_at"]
    if current_next_due_at:
        date_value = date.fromisoformat(current_next_due_at)
    else:
        date_value = date.today()

    manual_next_due_at = st.date_input(
        "Next review date",
        value=date_value,
        key="manual_next_due_at",
    )

    if st.button("Update Review Date"):
        try:
            result = update_card_next_due_at(
                management_collection["id"],
                management_card_number,
                manual_next_due_at.isoformat(),
            )
            st.success(f"Review date updated to {result['next_due_at']}.")
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def _render_review_history(collections: list[dict]) -> None:
    st.header("Review History")

    if not collections:
        st.info("Create a collection before reviewing cards.")
        return

    history_collection = st.selectbox(
        "Select collection for review history",
        collections,
        format_func=collection_label,
        key="review_history_collection_select",
    )
    history_groups = get_card_groups_for_collection(history_collection["id"])

    if not history_groups:
        st.info("This collection has no cards yet.")
        return

    history_card_numbers = [group["card_number"] for group in history_groups]
    history_card_number = st.selectbox(
        "Select card number",
        history_card_numbers,
        format_func=lambda card_number: f"Card #{card_number}",
    )
    review_logs = get_card_review_logs(
        history_collection["id"],
        history_card_number,
    )

    if review_logs:
        st.dataframe(review_logs, use_container_width=True, hide_index=True)
    else:
        st.info("No review history for this card yet.")


def render_review_history_page() -> None:
    st.title("Review History / Schedule")

    collections = get_collections()
    _render_manage_schedule(collections)
    _render_review_history(collections)

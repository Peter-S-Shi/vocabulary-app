import streamlit as st

from src.collections import get_card_groups_for_collection, get_collections
from src.db import get_connection
from src.learning_workflow import get_card_learning_history
from src.review import get_card_review_logs
from src.ui_streamlit.common import collection_label


def render_review_history_page() -> None:
    st.title("Learning History")
    st.caption(
        "Completed Card-scoped Quiz sessions are the current Card learning history. "
        "Legacy Review records are preserved separately for compatibility."
    )

    collections = get_collections()
    if not collections:
        st.info("Create a Collection before viewing Card learning history.")
        return

    collection = st.selectbox(
        "Collection",
        collections,
        format_func=collection_label,
        key="learning_history_collection",
    )
    card_groups = get_card_groups_for_collection(collection["id"])
    if not card_groups:
        st.info("This Collection has no Cards.")
        return

    card_number = st.selectbox(
        "Card",
        [group["card_number"] for group in card_groups],
        format_func=lambda value: f"Card #{value}",
        key="learning_history_card",
    )

    with get_connection() as conn:
        history = get_card_learning_history(conn, collection["id"], card_number)

    st.subheader("Card Learning Completions")
    if history:
        st.dataframe(history, use_container_width=True, hide_index=True)
    else:
        st.info("This Card has no completed Card-scoped Quiz yet.")

    legacy_logs = get_card_review_logs(collection["id"], card_number)
    with st.expander("Legacy Review History (compatibility only)", expanded=False):
        st.caption(
            "These records came from the retired independent Review scheduler. "
            "They are not Quiz-backed Card learning completions."
        )
        if legacy_logs:
            st.dataframe(legacy_logs, use_container_width=True, hide_index=True)
        else:
            st.info("No legacy Review records for this Card.")

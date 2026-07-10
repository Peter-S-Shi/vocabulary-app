import streamlit as st

from src.collections import get_collections
from src.entries import search_entries
from src.review import get_due_cards, sync_all_card_review_states


def render_dashboard_page() -> None:
    st.title("Dashboard")

    sync_all_card_review_states()
    entries = search_entries()
    collections = get_collections()
    due_cards = get_due_cards()

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Entries", len(entries))
    metric_col2.metric("Collections", len(collections))
    metric_col3.metric("Due Cards Today", len(due_cards))

    st.header("Recent Entries")
    recent_entries = entries[:5]
    if recent_entries:
        st.dataframe(
            [
                {
                    "id": entry["id"],
                    "language": entry["language"],
                    "type": entry["entry_type"],
                    "term": entry["term"],
                    "meaning": entry["meaning"],
                    "status": entry["status"],
                    "created_at": entry["created_at"],
                }
                for entry in recent_entries
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No entries yet.")

    st.caption("Milestone 4.4 - sidebar UI organization, Streamlit MVP layer only.")

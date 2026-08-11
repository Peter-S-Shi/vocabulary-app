import streamlit as st

from src.collections import get_collections
from src.db import get_connection
from src.entries import search_entries
from src.learning_workflow import get_study_workload


def render_dashboard_page() -> None:
    st.title("Dashboard")

    entries = search_entries()
    collections = get_collections()
    with get_connection() as conn:
        study_workload = get_study_workload(conn)

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Entries", len(entries))
    metric_col2.metric("Collections", len(collections))
    metric_col3.metric("Available Cards", study_workload["total_cards"])

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

    st.caption("Streamlit compatibility UI; Card learning completion comes from completed Card Quiz sessions.")

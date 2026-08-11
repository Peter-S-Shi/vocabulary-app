import streamlit as st

from src.db import init_db
from src.ui_streamlit.collections_page import render_collections_page
from src.ui_streamlit.dashboard_page import render_dashboard_page
from src.ui_streamlit.entries_page import render_entries_page
from src.ui_streamlit.import_export_page import render_import_export_page
from src.ui_streamlit.review_history_page import render_review_history_page
from src.ui_streamlit.review_page import render_review_page
from src.ui_streamlit.quiz_page import render_quiz_page
from src.ui_streamlit.settings_page import render_settings_page
from src.ui_streamlit.statistics_page import render_statistics_page
from src.ui_streamlit.today_page import render_today_page
from src.ui_streamlit.i18n import render_language_selector, t


PAGES = {
    "Today": render_today_page,
    "Entries": render_entries_page,
    "Collections": render_collections_page,
    "Review": render_review_page,
    "Quiz": render_quiz_page,
    "Statistics": render_statistics_page,
    "Import / Export": render_import_export_page,
    "Learning History": render_review_history_page,
    "Dashboard": render_dashboard_page,
    "Settings / Data": render_settings_page,
}


st.set_page_config(page_title="Vocabulary App", layout="wide")
if not st.session_state.get("app_initialized"):
    init_db()
    st.session_state["app_initialized"] = True

requested_page = st.session_state.pop("requested_page", None)
if requested_page in PAGES:
    st.session_state["current_page"] = requested_page

if "current_page" not in st.session_state or st.session_state["current_page"] not in PAGES:
    st.session_state["current_page"] = "Today"

st.sidebar.title("Vocabulary App")
render_language_selector()
selected_page = st.sidebar.radio(
    t("Navigate"),
    list(PAGES.keys()),
    key="current_page",
    format_func=t,
)
st.sidebar.caption(t("Local-first compatibility UI | Milestone 11.2"))

PAGES[selected_page]()


import streamlit as st


LANGUAGES = ["English", "French"]
EXPLANATION_LANGUAGES = ["Chinese", "English"]
ENTRY_TYPES = ["word", "phrase", "chunk", "sentence_frame", "conjugation"]
STATUSES = ["new", "learning", "familiar", "mastered"]

TABLE_COLUMNS = [
    "id",
    "language",
    "explanation_language",
    "entry_type",
    "template_name",
    "term",
    "meaning",
    "tags",
    "source",
    "status",
    "created_at",
    "updated_at",
]

COLLECTION_TABLE_COLUMNS = [
    "id",
    "name",
    "description",
    "card_size",
    "entry_count",
    "created_at",
    "updated_at",
]

COLLECTION_ENTRY_TABLE_COLUMNS = [
    "position",
    "id",
    "language",
    "entry_type",
    "term",
    "meaning",
    "template_name",
    "tags",
    "status",
]

REVIEW_ENTRY_TABLE_COLUMNS = [
    "position",
    "language",
    "entry_type",
    "term",
    "meaning",
    "example",
    "tags",
    "status",
]


def entry_label(entry: dict) -> str:
    return f"{entry['id']} - {entry['term']}"


def collection_label(collection: dict) -> str:
    return f"{collection['id']} - {collection['name']}"


def collection_entry_label(entry: dict) -> str:
    return f"{entry['position']} | {entry['id']} | {entry['term']}"


def option_index(options: list[str], value: str) -> int:
    if value in options:
        return options.index(value)
    return 0


def set_page_focus(page_name: str, **focus_values) -> None:
    st.session_state["requested_page"] = page_name
    for key, value in focus_values.items():
        st.session_state[key] = value


def render_back_to_today_button(key: str = "back_to_today") -> None:
    if st.button("Back to Today", key=key):
        set_page_focus("Today")
        st.rerun()

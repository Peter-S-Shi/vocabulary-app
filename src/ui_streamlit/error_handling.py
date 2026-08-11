from __future__ import annotations

import logging

import streamlit as st


LOGGER = logging.getLogger("vocabulary_app.ui")


def show_unexpected_error(
    context: str,
    user_message: str = "This action could not be completed safely.",
) -> None:
    """Keep internal exception details in local diagnostics, not the UI."""
    LOGGER.exception("Unexpected UI error while %s", context)
    st.error(user_message)

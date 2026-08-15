from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src import db
from src.learning_workflow import get_today_overview, normalize_today

"""
TodayController calls the existing reusable Today/learning-workflow core
exactly as src/ui_streamlit/today_page.py does, and owns no domain state of
its own -- only the last-fetched overview, which is transient presentation
state (M16.1 contract § 10/§ 11.C).
"""


class TodayController(QObject):
    overview_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.overview: dict | None = None

    def refresh(self) -> dict:
        with db.get_connection() as connection:
            overview = get_today_overview(connection, normalize_today())
        self.overview = overview
        self.overview_changed.emit(overview)
        return overview

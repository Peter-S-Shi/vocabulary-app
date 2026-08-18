from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QObject, Signal

from src.db import get_connection
from src.learning_workflow import get_card_learning_history
from src.review import get_card_review_logs
from src.statistics import get_card_learning_sessions_between_dates

"""
ReviewCalendarController owns the Review Calendar / Card History
workspace's transient date-range/selection state, calling existing
``src.statistics``/``src.learning_workflow``/``src.review`` reads for
every fact it projects -- no SQL, no mutation, no second learning-
completion model.

Primary evidence (DESIGN.md § 8 P7 "primary evidence surface"):
``get_card_learning_sessions_between_dates`` -- completed Card-scoped
Quiz sessions, the single authoritative Card learning/review completion
event (frozen semantic boundary), never legacy due/interval/rating data.
This is historical exposure browsing, not a revived due-date scheduler.

Secondary detail (DESIGN.md § 8 P7 "secondary selected-item detail",
"Card History"): selecting a Collection/Card shows its full completion
history (``get_card_learning_history``) plus legacy Review log records
(``get_card_review_logs``) kept clearly separate and labeled
compatibility-only, exactly like the existing Streamlit Learning History
page already does -- Quiz history and Review exposure remain distinct
evidence.
"""

DATE_RANGE_PRESETS: tuple[tuple[str, int], ...] = (
    ("Last 7 days", 7),
    ("Last 30 days", 30),
    ("Last 90 days", 90),
    ("Last 365 days", 365),
)
DEFAULT_RANGE_DAYS = 30


class ReviewCalendarController(QObject):
    entries_changed = Signal()
    selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.range_days: int = DEFAULT_RANGE_DAYS
        self.entries: list[dict] = []
        self.selected_collection_id: int | None = None
        self.selected_card_number: int | None = None
        self.selected_collection_name: str = ""
        self.card_history: list[dict] = []
        self.legacy_logs: list[dict] = []

    def refresh(self) -> None:
        end_date = date.today()
        start_date = end_date - timedelta(days=self.range_days)
        with get_connection() as connection:
            self.entries = get_card_learning_sessions_between_dates(connection, start_date, end_date)
        # The primary evidence table is a chronological *event* log, not a
        # list of stable entities -- multiple rows can share the same
        # (collection_id, card_number), so "the row that was selected" has
        # no well-defined match after entries reload. Always clear
        # selection here rather than trying to preserve it (independent
        # review finding: the view's table previously left a stale
        # row-index visually "selected" with detail data from whichever
        # different entry now occupied that index after a refresh).
        self.clear_selection()
        self.entries_changed.emit()

    def set_range_days(self, days: int) -> None:
        if days == self.range_days:
            return
        self.range_days = days
        self.refresh()

    def select_card(self, collection_id: int, card_number: int, collection_name: str = "") -> None:
        self.selected_collection_id = collection_id
        self.selected_card_number = card_number
        self.selected_collection_name = collection_name
        self._reload_selection()

    def clear_selection(self) -> None:
        self.selected_collection_id = None
        self.selected_card_number = None
        self.selected_collection_name = ""
        self.card_history = []
        self.legacy_logs = []
        self.selection_changed.emit()

    def _reload_selection(self) -> None:
        if self.selected_collection_id is None or self.selected_card_number is None:
            return
        with get_connection() as connection:
            self.card_history = get_card_learning_history(
                connection, self.selected_collection_id, self.selected_card_number
            )
        self.legacy_logs = get_card_review_logs(self.selected_collection_id, self.selected_card_number)
        self.selection_changed.emit()

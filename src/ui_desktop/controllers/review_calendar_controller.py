from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QObject, Signal

from src.db import get_connection
from src.card_history import get_current_card_identity
from src.learning_workflow import get_card_learning_history, get_card_learning_history_by_id
from src.review import get_card_review_logs
from src.review_schedule import (
    clear_card_schedule,
    get_card_schedule,
    list_card_schedules,
    set_card_next_review,
)
from src.statistics import get_card_learning_sessions_between_dates

"""
ReviewCalendarController owns the Review Calendar / Card History
workspace's transient date-range/selection state, calling existing
``src.statistics``/``src.learning_workflow``/``src.review`` reads for
historical evidence and delegates active next-review changes to
``src.review_schedule`` -- no SQL and no second learning-completion model.

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
        self.schedules: list[dict] = []
        self.selected_collection_id: int | None = None
        self.selected_card_number: int | None = None
        self.selected_card_id: int | None = None
        self.selected_collection_name: str = ""
        self.selected_from_history: bool = False
        self.card_history: list[dict] = []
        self.legacy_logs: list[dict] = []
        self.current_schedule: dict | None = None

    def refresh(self) -> None:
        end_date = date.today()
        start_date = end_date - timedelta(days=self.range_days)
        with get_connection() as connection:
            self.entries = get_card_learning_sessions_between_dates(connection, start_date, end_date)
        self.schedules = list_card_schedules()
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
        with get_connection() as connection:
            identity = get_current_card_identity(connection, collection_id, card_number)
        self.select_current_card(
            card_id=None if identity is None else int(identity["card_id"]),
            collection_id=collection_id,
            card_number=card_number,
            collection_name=collection_name,
        )

    def select_current_card(
        self,
        *,
        card_id: int | None,
        collection_id: int,
        card_number: int,
        collection_name: str = "",
    ) -> None:
        self.selected_collection_id = collection_id
        self.selected_card_number = card_number
        self.selected_card_id = card_id
        self.selected_collection_name = collection_name
        self.selected_from_history = False
        self._reload_selection()

    def select_card_event(
        self,
        *,
        card_id: int,
        collection_id: int,
        card_number: int,
        collection_name: str = "",
    ) -> None:
        self.selected_collection_id = collection_id
        self.selected_card_number = card_number
        self.selected_card_id = int(card_id)
        self.selected_collection_name = collection_name
        self.selected_from_history = True
        self._reload_selection()

    def clear_selection(self) -> None:
        self.selected_collection_id = None
        self.selected_card_number = None
        self.selected_card_id = None
        self.selected_collection_name = ""
        self.selected_from_history = False
        self.card_history = []
        self.legacy_logs = []
        self.current_schedule = None
        self.selection_changed.emit()

    def _reload_selection(self) -> None:
        if self.selected_collection_id is None or self.selected_card_number is None:
            return
        with get_connection() as connection:
            self.card_history = (
                get_card_learning_history_by_id(connection, self.selected_card_id)
                if self.selected_card_id is not None
                else get_card_learning_history(
                    connection,
                    self.selected_collection_id,
                    self.selected_card_number,
                )
            )
        self.legacy_logs = (
            []
            if self.selected_from_history
            else get_card_review_logs(self.selected_collection_id, self.selected_card_number)
        )
        schedule = (
            None
            if self.selected_card_id is None
            else get_card_schedule(self.selected_card_id)
        )
        self.current_schedule = (
            schedule if schedule is not None and int(schedule["is_active"]) else None
        )
        self.selection_changed.emit()

    def set_selected_next_review(
        self,
        next_due_at: str,
        *,
        today: str | None = None,
    ) -> dict:
        if self.current_schedule is None:
            raise ValueError("Select a current Card before setting its schedule.")
        self.current_schedule = set_card_next_review(
            int(self.current_schedule["card_id"]),
            next_due_at,
            today=today,
        )
        self.schedules = list_card_schedules(today=today)
        self.entries_changed.emit()
        self.selection_changed.emit()
        return self.current_schedule

    def clear_selected_schedule(self, *, today: str | None = None) -> dict:
        if self.current_schedule is None:
            raise ValueError("Select a current Card before clearing its schedule.")
        self.current_schedule = clear_card_schedule(
            int(self.current_schedule["card_id"]),
            today=today,
        )
        self.schedules = list_card_schedules(today=today)
        self.entries_changed.emit()
        self.selection_changed.emit()
        return self.current_schedule

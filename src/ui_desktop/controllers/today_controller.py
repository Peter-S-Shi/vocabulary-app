from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src import db
from src.learning_workflow import get_today_overview, normalize_today
from src.review_schedule import list_actionable_schedules
from src.ui_desktop.state.handoff import LearningActionIntent, learning_action_intent_from_recommendation

"""
TodayController combines the reusable Today/learning-workflow overview
with the active stable-Card schedule query. It owns no domain state of its
own -- only the last-fetched read-only presentation projection. It performs
no SQL and no learning-completion logic.
"""


class TodayController(QObject):
    overview_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.overview: dict | None = None

    def refresh(self, *, today: str | None = None) -> dict:
        today_iso = normalize_today(today)
        with db.get_connection() as connection:
            overview = get_today_overview(connection, today_iso)
        due_schedules = list_actionable_schedules(today=today_iso)
        overview["due_schedules"] = due_schedules
        self.overview = overview
        self.overview_changed.emit(overview)
        return overview

    def queue_items(self) -> list[dict]:
        """Today's Learning Queue: prioritized actionable items (a
        never-quizzed Card, a Mistake Book drill, a Proficient Pool audit,
        a Starred review, or an "organize new entries" suggestion) -- the
        DESIGN.md § 4.1 dominant area. This is
        ``daily_quiz_recommendations``, not the raw current-Card listing:
        the raw listing has no priority/actionability and is not a queue."""
        if self.overview is None:
            return []
        due_items = [
            {
                "recommendation_type": "scheduled_review",
                "collection_id": schedule["collection_id"],
                "collection_name": schedule["collection_name"],
                "card_number": schedule["card_number"],
                "card_id": schedule["card_id"],
                "entry_count": schedule["entry_count"],
                "quiz_mode": "card",
                "preferred_quiz_type": "mixed_mcq",
                "reason": "Scheduled review is due." if schedule["state"] == "due_today" else "Scheduled review is overdue.",
                "next_due_at": schedule["next_due_at"],
                "schedule_state": schedule["state"],
            }
            for schedule in self.overview.get("due_schedules") or []
        ]
        return due_items + list(self.overview.get("daily_quiz_recommendations") or [])

    def primary_recommendation(self) -> dict | None:
        """The single top suggested next action (DESIGN.md § 4.1 hierarchy
        item 3), distinct from the Learning Queue: a short, explainable
        "what should I do right now" recommendation with a target
        workflow (``target_page``: Entries/Review/Quiz)."""
        if self.overview is None:
            return None
        recommendations = self.overview.get("recommendations") or []
        return recommendations[0] if recommendations else None

    def recent_activity(self) -> list[dict]:
        """Today's factually completed Card-scoped Quiz sessions -- never
        Review-exposure state (ARCHITECTURE.md Learning Completion
        Semantics; DESIGN.md § 4.1)."""
        if self.overview is None:
            return []
        review_activity = self.overview.get("review_activity") or {}
        return list(review_activity.get("recent_reviewed_cards") or [])

    def collections_needing_attention(self) -> list[dict]:
        """Special-pool collections (Mistake Book, Proficient Pool,
        Starred) that currently hold practiceable entries. ``system_type``
        is included so a view can complete the handoff into the matching
        Entries ``system:<type>`` scope (M17 Minimum Collection
        Integration prompt § 8) without re-deriving it from the label."""
        if self.overview is None:
            return []
        special = self.overview.get("special_collections") or {}
        attention = []
        for system_type, label in (
            ("mistake_book", "Mistake Book"),
            ("proficient_pool", "Proficient Pool"),
            ("starred", "Starred"),
        ):
            status = special.get(system_type) or {}
            if status.get("exists") and int(status.get("entry_count") or 0) > 0:
                attention.append(
                    {
                        "label": label,
                        "collection_id": status.get("collection_id"),
                        "entry_count": int(status.get("entry_count") or 0),
                        "system_type": system_type,
                    }
                )
        return attention

    def build_learning_action_intent(self, queue_item: dict) -> LearningActionIntent:
        """Typed handoff (state/handoff.py) for a future Review/Quiz
        feature to consume. Today never acts on this itself -- it is
        constructed so a later M17 checkpoint can wire it into real
        navigation without redesigning this contract (M17 Feature 1
        prompt § 7)."""
        return learning_action_intent_from_recommendation(queue_item)

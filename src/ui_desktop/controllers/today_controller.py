from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src import db
from src.learning_workflow import get_today_overview, normalize_today
from src.ui_desktop.state.handoff import LearningActionIntent, learning_action_intent_from_recommendation

"""
TodayController calls the existing reusable Today/learning-workflow core
exactly as src/ui_streamlit/today_page.py does, and owns no domain state of
its own -- only the last-fetched overview and read-only presentation
projections over it, all transient presentation state (M16.1 contract
§ 10/§ 11.C). It performs no SQL and no learning-completion logic; every
number and recommendation below is read directly from
src.learning_workflow.get_today_overview().
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

    def queue_items(self) -> list[dict]:
        """Today's Learning Queue: prioritized actionable items (a
        never-quizzed Card, a Mistake Book drill, a Proficient Pool audit,
        a Starred review, or an "organize new entries" suggestion) -- the
        DESIGN.md § 4.1 dominant area. This is
        ``daily_quiz_recommendations``, not the raw current-Card listing:
        the raw listing has no priority/actionability and is not a queue."""
        if self.overview is None:
            return []
        return list(self.overview.get("daily_quiz_recommendations") or [])

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
        Starred) that currently hold practiceable entries."""
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

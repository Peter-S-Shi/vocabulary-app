from __future__ import annotations

from dataclasses import dataclass

"""
Minimal typed cross-feature handoff shape (M17 Feature 1 prompt § 7).

Today can identify a specific recommended learning action (a Card to quiz,
a special-pool drill) before a native Review/Quiz workspace exists to act on
it. ``LearningActionIntent`` lets Today express *what* it would hand off
without fabricating a Review/Quiz session, a fake AppState navigation
target, or a second session-state system: it is plain, inert data, not a
live request. A later M17 checkpoint that implements Review/Quiz can accept
this same shape without Today's architecture changing.
"""


@dataclass(frozen=True)
class LearningActionIntent:
    action: str
    collection_id: int | None
    collection_name: str
    card_number: int | None
    card_id: int | None
    quiz_type: str | None
    quiz_mode: str | None
    reason: str
    entry_count: int


def learning_action_intent_from_recommendation(recommendation: dict) -> LearningActionIntent:
    """Build a ``LearningActionIntent`` from one item of
    ``src.learning_workflow.get_daily_quiz_candidates()`` (the Today
    Learning Queue's underlying data)."""
    quiz_mode = recommendation.get("quiz_mode")
    action = "quiz" if quiz_mode in ("card", "random") else "review"
    return LearningActionIntent(
        action=action,
        collection_id=recommendation.get("collection_id"),
        collection_name=str(recommendation.get("collection_name") or ""),
        card_number=recommendation.get("card_number"),
        card_id=recommendation.get("card_id"),
        quiz_type=recommendation.get("preferred_quiz_type"),
        quiz_mode=quiz_mode,
        reason=str(recommendation.get("reason") or ""),
        entry_count=int(recommendation.get("entry_count") or 0),
    )

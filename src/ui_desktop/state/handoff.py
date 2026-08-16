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

Not every Learning Queue item is a Review/Quiz candidate.
``src.learning_workflow.get_daily_quiz_candidates()`` also emits a
``recommendation_type = "recent_entries_suggestion"`` item
(``quiz_mode = "suggestion"``) whose actual next step is organizing recent
Entries into a Collection, not reviewing or quizzing anything -- mapping it
to ``action="review"`` would be a false claim about what the item is for.
That case maps to ``action="organize"`` instead. Collection management
itself is not implemented by this contract or by Today; ``"organize"`` is
recorded so a later checkpoint can route it correctly, the same way
``"quiz"`` is recorded for a future Review/Quiz checkpoint.

An unrecognized ``quiz_mode`` (one that is neither of the two known Quiz
modes nor ``"suggestion"``) maps to ``action="unknown"``, never to
``"quiz"`` or ``"review"``. Guessing a specific action for a mode this
contract does not yet recognize would assert semantics nobody has verified;
``"unknown"`` lets a caller detect and handle the gap explicitly instead of
silently mislabeling it. No current
``get_daily_quiz_candidates()`` item reaches this branch.
"""

# The two quiz_mode values get_daily_quiz_candidates() uses for an actual
# launchable Quiz (a specific Card, or a random special-pool audit).
_QUIZ_MODES = ("card", "random")

UNKNOWN_ACTION = "unknown"


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


# Shared across every feature whose UI points at Quiz before Quiz itself is
# implemented (Today's queue/tile actions; Review's Quick Quiz action).
# One wording, centrally owned, so the honest-unavailable message can never
# drift between features that all describe the same real product state.
QUIZ_UNAVAILABLE_TOOLTIP = "Quiz is not implemented yet in the desktop app."

# Shown as a persistent, explicit in-dialog message -- not a tooltip -- when
# a user actively confirms a real choice (Review's "Choose Quiz Type" ->
# "Start Quiz") that cannot yet be fulfilled. Added after the Review human-
# acceptance functional-honesty finding: a disabled button's tooltip after a
# deliberate choose-then-confirm flow is easy to miss and does not "clearly
# tell the user" what happened -- an enabled, clickable confirmation that
# answers with an unmissable, honest message does.
QUIZ_UNAVAILABLE_MESSAGE = (
    "Native Quiz is the next M17 checkpoint and has not been implemented "
    "yet. No quiz session was started."
)


@dataclass(frozen=True)
class QuizLaunchIntent:
    """Typed handoff describing a Card-scoped Quiz a user asked to start,
    for a future Quiz checkpoint to consume (M17 Feature 2 prompt §
    "Quick Quiz" / "Choose Quiz Type"). Built by ``ReviewController`` and
    never acted on by Review itself -- Quiz does not exist yet in the
    desktop app, so this is inert data, not a live session request, the
    same non-fabrication discipline ``LearningActionIntent`` already
    follows for Today.

    ``quiz_type`` is ``None`` only for a Quick Quiz request where the
    caller intends the product's own deterministic default type rather
    than a user-chosen one; Review does not invent or hardcode that
    default itself.
    """

    source: str  # "review_quick_quiz" | "review_choose_quiz_type"
    collection_id: int
    collection_name: str
    card_number: int
    card_id: int | None
    quiz_type: str | None
    reason: str


def learning_action_intent_from_recommendation(recommendation: dict) -> LearningActionIntent:
    """Build a ``LearningActionIntent`` from one item of
    ``src.learning_workflow.get_daily_quiz_candidates()`` (the Today
    Learning Queue's underlying data)."""
    quiz_mode = recommendation.get("quiz_mode")
    if quiz_mode in _QUIZ_MODES:
        action = "quiz"
    elif quiz_mode == "suggestion":
        action = "organize"
    else:
        # Fail closed: an unrecognized quiz_mode is reported as unknown,
        # never guessed at as "quiz" or "review" -- see the module
        # docstring for why.
        action = UNKNOWN_ACTION
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

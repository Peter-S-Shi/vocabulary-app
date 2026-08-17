from __future__ import annotations

from dataclasses import dataclass, field

from src.quiz import QUIZ_TYPES

"""
Minimal typed cross-feature handoff shapes (M17 Feature 1 prompt § 7;
extended by M17 Feature 3 into a live Quiz launch payload).

Today can identify a specific recommended learning action (a Card to quiz,
a special-pool drill) before Review/Quiz act on it. ``LearningActionIntent``
lets Today express *what* it would hand off without duplicating a second
session-state system: it is plain, inert data. Review's ``QuizLaunchIntent``
is the same idea for the "which Quiz should start" decision -- both Review
and Today build one, and exactly one thing (``QuizController.start()``)
consumes it, per the M17 Feature 3 prompt § 11 ("One Quiz controller/
workflow should consume these launch sources; Review and Today should not
each invent their own session machinery").

Not every Learning Queue item is a Quiz candidate.
``src.learning_workflow.get_daily_quiz_candidates()`` also emits a
``recommendation_type = "recent_entries_suggestion"`` item
(``quiz_mode = "suggestion"``) whose actual next step is organizing recent
Entries into a Collection, not quizzing anything -- mapping it to
``action="review"``/``"quiz"`` would be a false claim about what the item is
for. That case maps to ``action="organize"`` instead.

An unrecognized ``quiz_mode`` (one that is neither of the two known Quiz
modes nor ``"suggestion"``) maps to ``action="unknown"``, never to
``"quiz"``. Guessing a specific action for a mode this contract does not yet
recognize would assert semantics nobody has verified; ``"unknown"`` lets a
caller detect and handle the gap explicitly instead of silently
mislabeling it. No current ``get_daily_quiz_candidates()`` item reaches
this branch.
"""

# The two quiz_mode values get_daily_quiz_candidates() uses for an actual
# launchable Quiz (a specific Card, or a random special-pool audit).
_QUIZ_MODES = ("card", "random")

UNKNOWN_ACTION = "unknown"


@dataclass(frozen=True)
class EntriesScopeIntent:
    """Typed navigation intent for "open Entries already scoped to X"
    (M17 Minimum Collection Integration prompt § 7/§ 8). Carries only the
    minimum factual target Entries' own existing scope contract already
    understands -- a scope key exactly as ``EntriesController``/
    ``_ScopePane`` already produce/consume it (``"all"``,
    ``"system:<starred|mistake_book|proficient_pool>"``,
    ``"collection:<id>"``) -- never an ad-hoc dict, and never a second
    Collection-filter implementation. Built by both the Collections
    Navigator (a chosen Collection or practice pool) and Today (an
    actionable "Collections Needing Attention" pool), consumed only by
    ``MainWindow`` handing the scope straight to the existing
    ``EntriesController.set_scope()``."""

    scope: str


@dataclass(frozen=True)
class StudyTargetIntent:
    """Typed navigation intent for "open this exact Collection/Card in
    Study" (M17 Minimum Collection Integration prompt § 9). Consumed only
    by ``ReviewController.open_card(collection_id, card_number)`` -- never
    a fallback to ``open_default()``. If the Card no longer exists when
    this is consumed, the caller must fail honestly rather than silently
    opening a different Card (prompt § 9)."""

    collection_id: int
    card_number: int


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


# Deterministic default type for a "Quick Quiz" launch -- matches the
# existing Streamlit Review page's hardcoded quick-quiz default
# (``_review_quiz_focus_values``) and Today's ``preferred_quiz_type``, not a
# new product decision. Centralized here so Review, Today, and Quiz all
# agree on the same fallback.
QUICK_QUIZ_DEFAULT_TYPE = "mixed_mcq"

# Presentational labels only (no prompt/answer-field or scoring logic) for
# quiz-type choosers. src.quiz.QUIZ_TYPES remains the sole authority for
# which quiz_type values are valid.
QUIZ_TYPE_LABELS: dict[str, str] = {
    "term_to_meaning": "Term → Meaning",
    "meaning_to_term": "Meaning → Term",
    "term_to_meaning_mcq": "Term → Meaning (multiple choice)",
    "meaning_to_term_mcq": "Meaning → Term (multiple choice)",
    "mixed_mcq": "Mixed (multiple choice)",
    "matching": "Matching (whole Collection)",
    "template_field_self_graded": "Custom field (self-graded)",
    "template_field_mcq": "Custom field (multiple choice)",
    "template_field_matching": "Custom field (matching)",
}

# Shown on a Quiz-shaped action that genuinely has no specific launch target
# yet (e.g. Today's contextless "Start Quiz" quick action, or a Suggested
# Next Action that names "Quiz" without a Collection/Card) -- Quiz itself is
# real and implemented, so this is deliberately not phrased as
# "not implemented"; it explains where a real target *is* available instead.
QUIZ_NO_TARGET_TOOLTIP = "Open a Learning Queue item or Study to start a Quiz."


@dataclass(frozen=True)
class QuizLaunchIntent:
    """Typed handoff describing a Quiz to start, consumed only by
    ``QuizController.start()`` (M17 Feature 3). Built by both
    ``ReviewController`` (Quick Quiz / Choose Quiz Type) and
    ``TodayController``-driven views (a Learning Queue "quiz" action) via
    ``quiz_launch_intent_from_learning_action_intent`` below, so both
    sources produce the exact same shape.

    ``card_number == 0`` means whole-Collection/random, matching the
    existing core convention (``create_quiz_session``,
    ``get_daily_quiz_candidates``'s ``quiz_mode="random"``).

    The ``template_*`` fields are populated only for
    ``template_field_self_graded``/``template_field_mcq``/
    ``template_field_matching``; they are ignored for every other
    ``quiz_type``.
    """

    source: str  # "review_quick_quiz" | "review_choose_quiz_type" | "today_queue"
    collection_id: int
    collection_name: str
    card_number: int
    card_id: int | None
    quiz_type: str
    item_count: int
    reason: str
    template_id: int | None = None
    template_type: str | None = None
    template_rule_ids: tuple[str, ...] = field(default_factory=tuple)
    template_difficulty: str = "Normal"


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


def quiz_launch_intent_from_learning_action_intent(intent: LearningActionIntent) -> QuizLaunchIntent | None:
    """Convert a real, supported Today Quiz action into the same
    ``QuizLaunchIntent`` shape Review builds, so ``QuizController`` never
    needs to know which feature launched it (M17 Feature 3 prompt §
    "Today"). Returns ``None`` for ``organize``/``unknown``/malformed
    intents rather than fabricating a launch for a target this contract
    does not represent as quiz-shaped.
    """
    if intent.action != "quiz" or intent.collection_id is None:
        return None
    quiz_type = intent.quiz_type if intent.quiz_type in QUIZ_TYPES else QUICK_QUIZ_DEFAULT_TYPE
    card_number = intent.card_number if intent.quiz_mode == "card" and intent.card_number else 0
    return QuizLaunchIntent(
        source="today_queue",
        collection_id=intent.collection_id,
        collection_name=intent.collection_name,
        card_number=card_number,
        card_id=intent.card_id if card_number else None,
        quiz_type=quiz_type,
        item_count=max(intent.entry_count, 1),
        reason=intent.reason or "Requested from Today's Learning Queue.",
    )

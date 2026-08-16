from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src import db
from src.collections import get_card_groups_for_collection
from src.learning_workflow import get_card_learning_history, get_study_cards
from src.quiz import QUIZ_TYPES
from src.ui_desktop.state.handoff import QuizLaunchIntent

"""
ReviewController owns the Study Mode / Review workspace's transient
browse-position state (current Card, current Entry index, drawer-open
bookkeeping) and calls existing reusable core exactly as
``src/ui_streamlit/review_page.py`` does -- ``src.learning_workflow`` for
the current Card roster and factual completed-Quiz history,
``src.collections`` for a Card's real Entry composition (M17 Feature 2
prompt § "Architecture boundaries"). It performs no SQL, no learning-
completion writes, and no legacy ``src/review.py`` scheduler calls: that
module is SRS/due-date compatibility-only and does not represent current
learning truth (ARCHITECTURE.md § Learning Completion Semantics).

Card identity is always resolved through the current Card roster
(``get_study_cards``), never assumed from ``card_number`` alone, per
ARCHITECTURE.md's stable-``card_id`` contract: a retired Card's Quiz
history must never be attributed to a later Card that reuses the same
display number.
"""

# Deterministic default type for a "Quick Quiz" launch -- matches the
# existing Streamlit Review page's hardcoded quick-quiz default
# (``_review_quiz_focus_values``), not a new product decision.
QUICK_QUIZ_DEFAULT_TYPE = "mixed_mcq"

# Presentational labels only (no prompt/answer-field or scoring logic) for
# the Choose Quiz Type utility -- src.quiz.QUIZ_TYPES remains the sole
# authority for which quiz_type values are valid.
QUIZ_TYPE_LABELS: dict[str, str] = {
    "term_to_meaning": "Term → Meaning",
    "meaning_to_term": "Meaning → Term",
    "term_to_meaning_mcq": "Term → Meaning (multiple choice)",
    "meaning_to_term_mcq": "Meaning → Term (multiple choice)",
    "mixed_mcq": "Mixed (multiple choice)",
    "matching": "Matching",
    "template_field_self_graded": "Custom field (self-graded)",
    "template_field_mcq": "Custom field (multiple choice)",
    "template_field_matching": "Custom field (matching)",
}


class ReviewController(QObject):
    state_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._study_cards: list[dict] = []
        self._card_index: int = -1
        self._entries: list[dict] = []
        self._entry_index: int = 0
        self._visited_entry_ids: set[int] = set()
        self._history: list[dict] = []

    # -- loading -----------------------------------------------------------

    def refresh_study_cards(self) -> list[dict]:
        with db.get_connection() as connection:
            self._study_cards = get_study_cards(connection)
        return self._study_cards

    def open_default(self) -> bool:
        """Load the current Card roster and choose a starting Card.

        Prefers the first never-quizzed Card (the same priority Today's
        Learning Queue gives a never-quizzed Card) so entering Review
        surfaces genuinely useful work rather than an arbitrary Card.
        Returns False -- an honest empty state, not a crash -- when no
        Study Cards exist at all.
        """
        self.refresh_study_cards()
        if not self._study_cards:
            self._card_index = -1
            self._entries = []
            self._entry_index = 0
            self._visited_entry_ids = set()
            self._history = []
            self.state_changed.emit()
            return False

        index = next(
            (i for i, card in enumerate(self._study_cards) if card["status"] == "never_quizzed"),
            0,
        )
        self._select_card_index(index)
        return True

    def open_card(self, collection_id: int, card_number: int) -> bool:
        """Jump to a specific Card (the Study Collection/Card selector's
        target). Returns False -- without disturbing current state -- if
        that Card is no longer available, e.g. removed since the roster
        was last loaded."""
        self.refresh_study_cards()
        index = next(
            (
                i
                for i, card in enumerate(self._study_cards)
                if card["collection_id"] == collection_id and card["card_number"] == card_number
            ),
            None,
        )
        if index is None:
            return False
        self._select_card_index(index)
        return True

    def _select_card_index(self, index: int) -> None:
        self._card_index = index
        card = self._study_cards[index]
        self._entries = self._entries_for_card(card["collection_id"], card["card_number"])
        self._entry_index = 0
        self._visited_entry_ids = set()
        self._mark_current_entry_visited()
        with db.get_connection() as connection:
            self._history = get_card_learning_history(connection, card["collection_id"], card["card_number"])
        self.state_changed.emit()

    @staticmethod
    def _entries_for_card(collection_id: int, card_number: int) -> list[dict]:
        for group in get_card_groups_for_collection(collection_id):
            if group["card_number"] == card_number:
                return list(group["entries"])
        return []

    # -- current state -------------------------------------------------------

    def current_card(self) -> dict | None:
        if self._card_index < 0 or self._card_index >= len(self._study_cards):
            return None
        return self._study_cards[self._card_index]

    def study_cards(self) -> list[dict]:
        return list(self._study_cards)

    def entries(self) -> list[dict]:
        return list(self._entries)

    def entry_index(self) -> int:
        return self._entry_index

    def current_entry(self) -> dict | None:
        if not self._entries:
            return None
        return self._entries[self._entry_index]

    def entry_progress(self) -> tuple[int, int]:
        return (self._entry_index + 1 if self._entries else 0, len(self._entries))

    def history(self) -> list[dict]:
        return list(self._history)

    def is_entry_visited(self, entry_id: int) -> bool:
        return entry_id in self._visited_entry_ids

    # -- entry navigation ------------------------------------------------

    def can_go_previous(self) -> bool:
        return self._entry_index > 0

    def can_go_next(self) -> bool:
        return self._entry_index < len(self._entries) - 1

    def go_previous(self) -> None:
        if not self.can_go_previous():
            return
        self._entry_index -= 1
        self._mark_current_entry_visited()
        self.state_changed.emit()

    def go_next(self) -> None:
        if not self.can_go_next():
            return
        self._entry_index += 1
        self._mark_current_entry_visited()
        self.state_changed.emit()

    def go_to_entry_index(self, index: int) -> None:
        if index < 0 or index >= len(self._entries) or index == self._entry_index:
            return
        self._entry_index = index
        self._mark_current_entry_visited()
        self.state_changed.emit()

    def _mark_current_entry_visited(self) -> None:
        entry = self.current_entry()
        if entry is not None:
            self._visited_entry_ids.add(entry["id"])

    # -- Quiz handoff (inert -- Quiz is not implemented yet) --------------

    def quiz_type_options(self) -> list[str]:
        return list(QUIZ_TYPES.keys())

    def build_quick_quiz_intent(self) -> QuizLaunchIntent | None:
        return self._build_quiz_launch_intent("review_quick_quiz", QUICK_QUIZ_DEFAULT_TYPE)

    def build_choose_quiz_type_intent(self, quiz_type: str) -> QuizLaunchIntent | None:
        return self._build_quiz_launch_intent("review_choose_quiz_type", quiz_type)

    def _build_quiz_launch_intent(self, source: str, quiz_type: str) -> QuizLaunchIntent | None:
        card = self.current_card()
        if card is None:
            return None
        return QuizLaunchIntent(
            source=source,
            collection_id=card["collection_id"],
            collection_name=card["collection_name"],
            card_number=card["card_number"],
            card_id=card["card_id"],
            quiz_type=quiz_type,
            reason="Requested from Review for the currently displayed Card.",
        )

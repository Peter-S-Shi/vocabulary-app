from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src import db
from src.collections import (
    add_entries_to_system_collection,
    get_card_entries_for_study,
    get_card_groups_for_collection,
    get_entries_in_collection,
    get_entry_ids_in_system_collection,
    is_system_collection_id,
    remove_entries_from_system_collection,
)
from src.learning_workflow import get_card_learning_history, get_study_cards
from src.quiz import QUIZ_TYPES
from src.template_quiz import get_available_template_quiz_sources_for_card, get_template_quiz_rules
from src.ui_desktop.state.handoff import QUICK_QUIZ_DEFAULT_TYPE, QUIZ_TYPE_LABELS, QuizLaunchIntent
from src.ui_desktop.state.preferences import Preferences

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

Since M17 Feature 3, Quick Quiz and Choose Quiz Type build a real
``QuizLaunchIntent`` (``state/handoff.py``) that ``QuizController`` and
``MainWindow`` actually act on -- Review still never starts a Quiz session
itself (no ``src.quiz``/``src.template_quiz`` write calls in this file);
it only builds the typed request.

``QUICK_QUIZ_DEFAULT_TYPE``/``QUIZ_TYPE_LABELS`` now live in
``state/handoff.py`` (re-exported here for existing importers) since Quiz
completion/setup surfaces need the same labels Review does.
"""

# Matches src/ui_streamlit/quiz_page.py's MATCHING_ITEM_COUNTS -- plain
# Matching is whole-Collection only (see build_choose_quiz_type_intent),
# so its size is chosen independently of the current Card's entry count.
MATCHING_ITEM_COUNT_OPTIONS: tuple[int, ...] = (4, 6, 8, 10)


class ReviewController(QObject):
    state_changed = Signal()
    starred_changed = Signal(int, bool)
    proficient_changed = Signal(int, bool)

    def __init__(self, preferences: Preferences | None = None) -> None:
        super().__init__()
        self.preferences = preferences
        self._study_cards: list[dict] = []
        self._card_index: int = -1
        self._entries: list[dict] = []
        self._entry_index: int = 0
        self._visited_entry_ids: set[int] = set()
        self._starred_entry_ids: set[int] = set()
        self._proficient_entry_ids: set[int] = set()
        self._history: list[dict] = []

    @property
    def include_proficient_in_study(self) -> bool:
        if self.preferences is not None:
            return bool(self.preferences.include_proficient_in_study)
        return True

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
            self._starred_entry_ids = set()
            self._proficient_entry_ids = set()
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

    def reload_current_card(self) -> None:
        """Re-read entries for the currently selected Card (e.g. after preference change)."""
        if self._card_index >= 0 and self._card_index < len(self._study_cards):
            self._select_card_index(self._card_index)

    def _select_card_index(self, index: int) -> None:
        self._card_index = index
        card = self._study_cards[index]
        self._entries = self._entries_for_card(card["collection_id"], card["card_number"])
        self._entry_index = 0
        self._visited_entry_ids = set()
        self._mark_current_entry_visited()
        self._starred_entry_ids = set(
            get_entry_ids_in_system_collection(
                [entry["id"] for entry in self._entries],
                "starred",
            )
        )
        self._proficient_entry_ids = set(
            get_entry_ids_in_system_collection(
                [entry["id"] for entry in self._entries],
                "proficient_pool",
            )
        )
        with db.get_connection() as connection:
            self._history = get_card_learning_history(connection, card["collection_id"], card["card_number"])
        self.state_changed.emit()

    def _entries_for_card(self, collection_id: int, card_number: int) -> list[dict]:
        return get_card_entries_for_study(
            collection_id,
            card_number,
            include_proficient=self.include_proficient_in_study,
        )

    def is_current_card_all_proficient(self) -> bool:
        """Return True if the current Card has structural entries, but all of them
        are currently excluded because they reside in the Proficient Pool."""
        card = self.current_card()
        if card is None or bool(self._entries):
            return False
        raw_entries = get_card_entries_for_study(
            card["collection_id"],
            card["card_number"],
            include_proficient=True,
        )
        return len(raw_entries) > 0

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

    def is_entry_starred(self, entry_id: int) -> bool:
        return entry_id in self._starred_entry_ids

    def is_entry_proficient(self, entry_id: int) -> bool:
        return entry_id in self._proficient_entry_ids

    def toggle_current_entry_star(self, *, confirm_cross_card: bool = False) -> bool:
        entry = self.current_entry()
        if entry is None:
            raise ValueError("No current Entry is available")

        entry_id = int(entry["id"])
        if self.is_entry_starred(entry_id):
            remove_entries_from_system_collection(
                [entry_id],
                "starred",
                confirm_cross_card=confirm_cross_card,
            )
            self._starred_entry_ids.remove(entry_id)
            starred = False
        else:
            add_entries_to_system_collection([entry_id], "starred")
            self._starred_entry_ids.add(entry_id)
            starred = True

        self.starred_changed.emit(entry_id, starred)
        return starred

    def toggle_current_entry_proficient(self, *, confirm_cross_card: bool = False) -> bool:
        """Toggle Proficient Pool membership without advancing learning state.

        Membership changes can alter the visible roster when proficient Entries
        are excluded, or when studying the Proficient Pool itself. Re-read only
        the current Card and keep the same logical slot without marking the newly
        displayed Entry visited.
        """
        entry = self.current_entry()
        if entry is None:
            raise ValueError("No current Entry is available")

        entry_id = int(entry["id"])
        if self.is_entry_proficient(entry_id):
            remove_entries_from_system_collection(
                [entry_id],
                "proficient_pool",
                confirm_cross_card=confirm_cross_card,
            )
            proficient = False
        else:
            add_entries_to_system_collection([entry_id], "proficient_pool")
            proficient = True

        old_ids = [int(item["id"]) for item in self._entries]
        old_index = self._entry_index
        card = self.current_card()
        roster_can_change = card is not None and (
            not self.include_proficient_in_study
            or is_system_collection_id(int(card["collection_id"]))
        )
        if roster_can_change and card is not None:
            self._entries = self._entries_for_card(card["collection_id"], card["card_number"])
            new_ids = [int(item["id"]) for item in self._entries]
            if new_ids != old_ids:
                self._entry_index = min(old_index, max(len(self._entries) - 1, 0))
                self._starred_entry_ids = set(
                    get_entry_ids_in_system_collection(new_ids, "starred")
                )
                self._proficient_entry_ids = set(
                    get_entry_ids_in_system_collection(new_ids, "proficient_pool")
                )
                self.state_changed.emit()
                return proficient

        if proficient:
            self._proficient_entry_ids.add(entry_id)
        else:
            self._proficient_entry_ids.discard(entry_id)
        self.proficient_changed.emit(entry_id, proficient)
        return proficient

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

    # -- Quiz handoff --------------------------------------------------------

    def quiz_type_options(self) -> list[str]:
        """Plain (non-template) quiz types offered by Choose Quiz Type.
        Template-aware types are offered separately, only when
        ``available_template_sources()`` is non-empty, because they need a
        template + rule selection the flat type list cannot express."""
        return [quiz_type for quiz_type in QUIZ_TYPES if not quiz_type.startswith("template_field_")]

    def build_quick_quiz_intent(self) -> QuizLaunchIntent | None:
        card = self.current_card()
        if card is None:
            return None
        return QuizLaunchIntent(
            source="review_quick_quiz",
            collection_id=card["collection_id"],
            collection_name=card["collection_name"],
            card_number=card["card_number"],
            card_id=card["card_id"],
            quiz_type=QUICK_QUIZ_DEFAULT_TYPE,
            item_count=card["entry_count"],
            reason="Requested from Review for the currently displayed Card.",
        )

    def build_choose_quiz_type_intent(
        self, quiz_type: str, *, matching_item_count: int | None = None
    ) -> QuizLaunchIntent | None:
        card = self.current_card()
        if card is None:
            return None
        if quiz_type == "matching":
            # Plain Matching is whole-Collection only in the current product
            # (M17 Feature 3 compatibility check: Streamlit always forces
            # card_number=0 for it, and no core function generates a
            # Card-scoped plain-matching set) -- never Card-scoped here
            # either, regardless of which Card Review currently displays.
            return QuizLaunchIntent(
                source="review_choose_quiz_type",
                collection_id=card["collection_id"],
                collection_name=card["collection_name"],
                card_number=0,
                card_id=None,
                quiz_type="matching",
                item_count=matching_item_count or self.matching_item_count_options()[0]
                if self.matching_item_count_options()
                else 0,
                reason="Requested from Review's Choose Quiz Type for the current Collection.",
            )
        return QuizLaunchIntent(
            source="review_choose_quiz_type",
            collection_id=card["collection_id"],
            collection_name=card["collection_name"],
            card_number=card["card_number"],
            card_id=card["card_id"],
            quiz_type=quiz_type,
            item_count=card["entry_count"],
            reason="Requested from Review's Choose Quiz Type for the current Card.",
        )

    def matching_item_count_options(self) -> list[int]:
        card = self.current_card()
        if card is None:
            return []
        available = len(get_entries_in_collection(card["collection_id"]))
        options = [count for count in MATCHING_ITEM_COUNT_OPTIONS if count <= available]
        if not options and available >= 2:
            options = [available]
        return options

    # -- template-aware Quiz options -------------------------------------

    def available_template_sources(self) -> list[dict]:
        """Templates the current Card's Entries actually use that have
        template-aware quiz rules defined (empty when none do -- Choose
        Quiz Type must not offer a template-aware section in that case)."""
        card = self.current_card()
        if card is None:
            return []
        return get_available_template_quiz_sources_for_card(
            card["collection_id"],
            card["card_number"],
            include_proficient=self.include_proficient_in_study,
        )

    def template_rules(self, template_type: str) -> list[dict]:
        return get_template_quiz_rules(template_type)

    def build_template_quiz_intent(
        self, template_id: int, template_type: str, rule_ids: list[str], mode_quiz_type: str
    ) -> QuizLaunchIntent | None:
        card = self.current_card()
        if card is None:
            return None
        return QuizLaunchIntent(
            source="review_choose_quiz_type",
            collection_id=card["collection_id"],
            collection_name=card["collection_name"],
            card_number=card["card_number"],
            card_id=card["card_id"],
            quiz_type=mode_quiz_type,
            item_count=card["entry_count"],
            reason="Requested from Review's Choose Quiz Type (template-aware) for the current Card.",
            template_id=template_id,
            template_type=template_type,
            template_rule_ids=tuple(rule_ids),
        )

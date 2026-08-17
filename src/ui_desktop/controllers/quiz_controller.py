from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from src.quiz import (
    create_quiz_items,
    create_quiz_session,
    generate_mcq_items,
    generate_random_quiz_items,
    get_active_quiz_session,
    get_entries_for_quiz,
    get_quiz_item_log_view,
    grade_mcq_answer,
    mark_quiz_session_cancelled,
    complete_quiz_session,
    record_quiz_answer,
)
from src.template_quiz import generate_template_multi_rule_quiz_items, get_template_quiz_rule
from src.ui_desktop.state.handoff import QuizLaunchIntent

"""
QuizController owns the active-quiz presentation/session-interaction state
(current item index, self-graded reveal/draft, MCQ feedback, matching
selections, completion result) and calls existing reusable core exactly as
``src/ui_streamlit/quiz_page.py`` does -- ``src.quiz``/``src.template_quiz``
for item generation, session creation, answer recording, and completion.
It performs no SQL and duplicates no grading/session logic (M17 Feature 3
prompt § 11 Architecture): every generation call below maps to one existing
core function, and ``record_quiz_answer`` (not a reimplementation) is the
single write path for every quiz family.

Session identity: exactly one *global* active ``quiz_sessions`` row is the
product's real constraint (``src.quiz.get_active_quiz_session()`` is not
scoped by Collection/Card -- confirmed against the current core). The core
itself does not enforce this; ``start()`` replicates the same
check-before-create guard every Streamlit quiz-start entry point already
performs, so a second concurrent active session is never created from the
desktop layer either. When a *foreign* active session is found (e.g. the
app restarted mid-quiz and this controller has no memory of it), ``start()``
refuses and exposes it as ``blocked_session`` -- matching Streamlit's exact
recovery behavior (surfaced, offer only Cancel, never a silent/fake resume;
see the M17 Feature 3 prompt § 7/§ 8).
"""

PLAIN_SELF_GRADED_TYPES = frozenset({"term_to_meaning", "meaning_to_term"})
PLAIN_MCQ_TYPES = frozenset({"term_to_meaning_mcq", "meaning_to_term_mcq", "mixed_mcq"})
TEMPLATE_TYPES = frozenset({"template_field_self_graded", "template_field_mcq", "template_field_matching"})
MATCHING_TYPES = frozenset({"matching", "template_field_matching"})

SELF_GRADED_FAMILY = "self_graded"
MCQ_FAMILY = "mcq"
MATCHING_FAMILY = "matching"

NOT_ENOUGH_ENTRIES_ERROR = "Not enough entries to build this quiz."


class QuizController(QObject):
    state_changed = Signal()
    # A Matching answer pick is transient item state, not a reason to
    # rebuild the whole task surface (VR-STUDY-001 corrective pass § 2B) --
    # QuizView listens for this separately from state_changed so it can
    # refresh only the progress count / Submit button instead of losing the
    # user's scroll position and already-selected answers on every pick.
    matching_selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.session_id: int | None = None
        self.intent: QuizLaunchIntent | None = None
        self.items: list[dict] = []
        self.meaning_choices: list[str] | None = None
        self.generation_warning: str = ""
        self.current_index: int = 0
        self.show_answer: bool = False
        self.answer_draft: str = ""
        self.feedback: dict | None = None
        self.matching_selection: dict[object, str] = {}
        self.completed_session: dict | None = None
        self.mistakes: list[dict] = []
        self.start_error: str | None = None
        self.blocked_session: dict | None = None
        self.pending_intent: QuizLaunchIntent | None = None
        self.reviewing_mistakes: bool = False
        self.mistake_index: int = 0
        # Presentation-orientation cache only (M17 Feature 3B, VR-STUDY-002
        # filmstrip): mirrors the same ``is_correct`` value already passed
        # into ``record_quiz_answer`` for each item, so the filmstrip can
        # show already-answered correct/wrong state without re-deriving it
        # or querying quiz_item_logs from the view. Purely in-memory,
        # rebuilt on every ``start()``, never written to vocab.db, never a
        # second source of grading truth.
        self.item_results: list[bool | None] = []

    # -- family classification --------------------------------------------

    def quiz_family(self) -> str | None:
        quiz_type = self.intent.quiz_type if self.intent else None
        if quiz_type is None:
            return None
        if quiz_type in PLAIN_SELF_GRADED_TYPES or quiz_type == "template_field_self_graded":
            return SELF_GRADED_FAMILY
        if quiz_type in PLAIN_MCQ_TYPES or quiz_type == "template_field_mcq":
            return MCQ_FAMILY
        if quiz_type in MATCHING_TYPES:
            return MATCHING_FAMILY
        return None

    # -- starting ------------------------------------------------------------

    def start(self, intent: QuizLaunchIntent) -> bool:
        """Start a new Quiz session for ``intent``. Returns False (without
        raising) for every honest failure mode: a foreign active session
        blocks the start (``blocked_session`` set), or generation cannot
        produce items (``start_error`` set) -- the caller/view renders
        whichever state resulted rather than assuming success."""
        self.start_error = None

        if intent.quiz_type == "matching" and intent.card_number != 0:
            # Defense in depth for the frozen "plain Matching is never
            # Card-scoped" rule (module docstring) -- normalized here once
            # rather than relied on from the caller, so the session record
            # can never disagree with the whole-Collection item set
            # actually generated.
            intent = replace(intent, card_number=0, card_id=None)

        active = get_active_quiz_session()
        if active is not None and active["id"] != self.session_id:
            self.blocked_session = active
            self.pending_intent = intent
            self.state_changed.emit()
            return False
        self.blocked_session = None

        try:
            generation = self._generate_items(intent)
        except ValueError as error:
            self.start_error = str(error)
            self.state_changed.emit()
            return False

        items = list(generation.get("quiz_items") or [])
        if not items:
            self.start_error = NOT_ENOUGH_ENTRIES_ERROR
            self.state_changed.emit()
            return False

        self.session_id = create_quiz_session(intent.collection_id, intent.card_number, intent.quiz_type, len(items))
        self.intent = intent
        self.items = items
        self.meaning_choices = generation.get("meaning_choices")
        self.generation_warning = str(generation.get("warning") or "")
        self.current_index = 0
        self.show_answer = False
        self.answer_draft = ""
        self.feedback = None
        self.matching_selection = {}
        self.completed_session = None
        self.mistakes = []
        self.pending_intent = None
        self.item_results = [None] * len(items)
        self.state_changed.emit()
        return True

    def _generate_items(self, intent: QuizLaunchIntent) -> dict:
        quiz_type = intent.quiz_type

        if quiz_type in TEMPLATE_TYPES:
            if intent.template_id is None or not intent.template_rule_ids:
                raise ValueError("Choose a template and at least one rule for a template-aware quiz.")
            rules = [
                rule
                for rule_id in intent.template_rule_ids
                if (rule := get_template_quiz_rule(intent.template_type, rule_id)) is not None
            ]
            if not rules:
                raise ValueError("Choose at least one template quiz rule.")
            return generate_template_multi_rule_quiz_items(
                intent.collection_id,
                intent.card_number,
                intent.template_id,
                rules,
                quiz_type,
                intent.template_difficulty,
            )

        if quiz_type == "matching":
            # Plain Matching is whole-Collection only in the current product
            # (confirmed: Streamlit always forces card_number=0 for it; no
            # core function generates a Card-scoped plain-matching set) --
            # honored here rather than inventing Card-scoped Matching.
            return generate_random_quiz_items(intent.collection_id, "matching", intent.item_count)

        if intent.card_number == 0:
            return generate_random_quiz_items(intent.collection_id, quiz_type, intent.item_count)

        if quiz_type in PLAIN_SELF_GRADED_TYPES:
            entries = get_entries_for_quiz(intent.collection_id, intent.card_number)
            return {"quiz_items": create_quiz_items(entries, quiz_type), "meaning_choices": None, "warning": ""}

        if quiz_type in PLAIN_MCQ_TYPES:
            items = generate_mcq_items(intent.collection_id, intent.card_number, quiz_type)
            return {"quiz_items": items, "meaning_choices": None, "warning": ""}

        raise ValueError(f"Unsupported quiz type: {quiz_type}")

    # -- current item / progress --------------------------------------------

    def current_item(self) -> dict | None:
        if self.quiz_family() == MATCHING_FAMILY:
            return None
        if not self.items or self.current_index >= len(self.items):
            return None
        return self.items[self.current_index]

    def progress(self) -> tuple[int, int]:
        if self.quiz_family() == MATCHING_FAMILY:
            answered = sum(1 for item in self.items if self.matching_selection.get(self._matching_key(item)))
            return (answered, len(self.items))
        position = min(self.current_index + 1, len(self.items)) if self.items else 0
        return (position, len(self.items))

    def is_card_scoped(self) -> bool:
        return bool(self.intent and self.intent.card_number > 0)

    def item_status(self, index: int) -> bool | None:
        """``True``/``False`` if item ``index`` has already been answered
        correctly/wrongly this session, ``None`` if not yet reached --
        VR-STUDY-002's filmstrip orientation state (M17 Feature 3B prompt
        § 8B)."""
        if 0 <= index < len(self.item_results):
            return self.item_results[index]
        return None

    # -- self-graded ---------------------------------------------------------

    def set_answer_draft(self, text: str) -> None:
        self.answer_draft = text

    def reveal_answer(self) -> None:
        if self.quiz_family() != SELF_GRADED_FAMILY:
            return
        self.show_answer = True
        self.state_changed.emit()

    def submit_self_graded(self, is_correct: bool) -> bool:
        item = self.current_item()
        if item is None or not self.show_answer:
            return False
        result = record_quiz_answer(
            self.session_id, item["entry_id"], item["prompt"], item["expected_answer"], self.answer_draft, is_correct
        )
        if not result["logged"]:
            return False
        if 0 <= self.current_index < len(self.item_results):
            self.item_results[self.current_index] = is_correct
        self.answer_draft = ""
        self._advance_or_complete()
        return True

    # -- MCQ -------------------------------------------------------------

    def submit_mcq(self, selected_option: str) -> bool:
        item = self.current_item()
        if item is None or self.feedback is not None:
            return False
        is_correct = grade_mcq_answer(selected_option, item["correct_answer"])
        prompt = item["prompt"]
        if self.intent is not None and self.intent.quiz_type == "mixed_mcq":
            # Disambiguates the log identity (session_id, entry_id, prompt)
            # so the same Entry answered in both MCQ directions within one
            # mixed session is never treated as a duplicate of itself --
            # mirrors quiz_page.py's identical prompt-suffix convention.
            direction_label = "Term to Meaning" if item.get("direction") == "term_to_meaning_mcq" else "Meaning to Term"
            prompt = f"{prompt} [{direction_label}]"
        result = record_quiz_answer(self.session_id, item["entry_id"], prompt, item["correct_answer"], selected_option, is_correct)
        if not result["logged"]:
            return False
        if 0 <= self.current_index < len(self.item_results):
            self.item_results[self.current_index] = is_correct
        self.feedback = {
            "is_correct": is_correct,
            "expected_answer": item["correct_answer"],
            "selected": selected_option,
        }
        self.state_changed.emit()
        return True

    def advance_after_mcq(self) -> None:
        self.feedback = None
        self._advance_or_complete()

    def _advance_or_complete(self) -> None:
        next_index = self.current_index + 1
        if next_index >= len(self.items):
            self._complete()
        else:
            self.current_index = next_index
            self.show_answer = False
            self.answer_draft = ""
            self.state_changed.emit()

    # -- matching ----------------------------------------------------------

    @staticmethod
    def _matching_key(item: dict) -> object:
        return item.get("matching_key", item.get("entry_id"))

    def matching_items(self) -> list[dict]:
        return list(self.items) if self.quiz_family() == MATCHING_FAMILY else []

    def matching_choices(self) -> list[str]:
        return list(self.meaning_choices or [])

    def set_matching_selection(self, item: dict, meaning: str) -> None:
        self.matching_selection[self._matching_key(item)] = meaning
        self.matching_selection_changed.emit()

    def matching_selection_for(self, item: dict) -> str:
        return self.matching_selection.get(self._matching_key(item), "")

    def can_submit_matching(self) -> bool:
        return bool(self.items) and all(
            self.matching_selection.get(self._matching_key(item)) for item in self.items
        )

    def submit_matching(self) -> bool:
        if not self.can_submit_matching():
            return False
        for item in self.items:
            selected = self.matching_selection.get(self._matching_key(item), "")
            is_correct = selected == item["expected_meaning"]
            record_quiz_answer(self.session_id, item["entry_id"], item["term"], item["expected_meaning"], selected, is_correct)
        self._complete()
        return True

    # -- completion / cancel / restart --------------------------------------

    def _complete(self) -> None:
        session = complete_quiz_session(self.session_id)
        self.completed_session = session
        self.mistakes = get_quiz_item_log_view(session_id=self.session_id, show_wrong_only=True)
        self.items = []
        self.current_index = 0
        self.feedback = None
        self.matching_selection = {}
        self.reviewing_mistakes = False
        self.mistake_index = 0
        self.state_changed.emit()

    # -- post-Quiz mistake review --------------------------------------------

    def review_mistakes(self) -> None:
        """Enter a read-only mistake-review state inside this same Quiz
        surface (VR-STUDY-001 corrective pass § 3) -- never a navigation
        back to Review, and never a mutation: it only inspects the
        already-recorded ``mistakes`` from ``_complete()``'s
        ``get_quiz_item_log_view`` call, the same data the completion
        summary's mistakes list already shows."""
        if not self.mistakes:
            return
        self.reviewing_mistakes = True
        self.mistake_index = 0
        self.state_changed.emit()

    def exit_mistake_review(self) -> None:
        self.reviewing_mistakes = False
        self.state_changed.emit()

    def current_mistake(self) -> dict | None:
        if not self.mistakes or self.mistake_index >= len(self.mistakes):
            return None
        return self.mistakes[self.mistake_index]

    def mistake_progress(self) -> tuple[int, int]:
        if not self.mistakes:
            return (0, 0)
        return (self.mistake_index + 1, len(self.mistakes))

    def can_go_previous_mistake(self) -> bool:
        return self.mistake_index > 0

    def can_go_next_mistake(self) -> bool:
        return self.mistake_index < len(self.mistakes) - 1

    def go_previous_mistake(self) -> None:
        if self.can_go_previous_mistake():
            self.mistake_index -= 1
            self.state_changed.emit()

    def go_next_mistake(self) -> None:
        if self.can_go_next_mistake():
            self.mistake_index += 1
            self.state_changed.emit()

    def cancel_active(self) -> None:
        if self.session_id is not None and self.completed_session is None:
            mark_quiz_session_cancelled(self.session_id)
        self._reset()

    def restart_active(self) -> bool:
        """Cancel the in-progress session and immediately start a fresh one
        with the same launch parameters (DESIGN.md coverage matrix's
        "Restart/cancel session confirmation" P6 flow)."""
        intent = self.intent
        if self.session_id is not None and self.completed_session is None:
            mark_quiz_session_cancelled(self.session_id)
        self._reset(silent=True)
        if intent is None:
            return False
        return self.start(intent)

    def cancel_blocked_and_retry(self) -> bool:
        """The recovery path for a foreign active session (§ module
        docstring): cancel it, then retry the launch that was blocked."""
        if self.blocked_session is None:
            return False
        mark_quiz_session_cancelled(self.blocked_session["id"])
        self.blocked_session = None
        pending = self.pending_intent
        self.pending_intent = None
        if pending is None:
            self.state_changed.emit()
            return True
        return self.start(pending)

    def exit_active(self) -> None:
        """Leaving an active (never fully answered) Quiz cancels it --
        DESIGN.md's frozen learning semantics: starting/abandoning Quiz is
        never itself a completion event, and this is the only way to leave
        an active session without completing it."""
        self.cancel_active()

    def acknowledge_completion(self) -> None:
        self._reset()

    def _reset(self, *, silent: bool = False) -> None:
        self.session_id = None
        self.intent = None
        self.items = []
        self.meaning_choices = None
        self.generation_warning = ""
        self.current_index = 0
        self.show_answer = False
        self.answer_draft = ""
        self.feedback = None
        self.matching_selection = {}
        self.completed_session = None
        self.mistakes = []
        self.start_error = None
        self.reviewing_mistakes = False
        self.mistake_index = 0
        self.item_results = []
        if not silent:
            self.state_changed.emit()

import streamlit as st


from src.collections import (
    get_card_groups_for_collection,
    get_collection_by_id,
    get_collections,
    get_system_collection,
    remove_entries_from_system_collection,
)
from src.quiz import (
    MCQ_GENERATION_ERROR,
    create_quiz_items,
    create_quiz_session,
    create_random_quiz_session,
    complete_quiz_session,
    generate_matching_items,
    generate_mcq_items,
    generate_random_quiz_items,
    get_active_quiz_session,
    get_entries_for_quiz,
    get_entry_quiz_performance,
    get_failed_proficient_pool_entries_for_session,
    get_mistake_book_mastery_candidates,
    get_proficient_pool_audit_rows,
    get_quiz_item_log_view,
    is_mistake_book_collection,
    is_proficient_pool_collection,
    get_quiz_item_logs,
    get_quiz_progress,
    get_recovered_mistake_book_entries_for_session,
    grade_matching_answers,
    grade_mcq_answer,
    mark_quiz_session_cancelled,
    record_quiz_answer,
)
from src.template_quiz import (
    TEMPLATE_FIELD_SELF_GRADED,
    TEMPLATE_FIELD_MCQ,
    TEMPLATE_FIELD_MATCHING,
    TEMPLATE_QUIZ_DIFFICULTIES,
    TEMPLATE_QUIZ_TYPES,
    generate_template_field_quiz_items,
    generate_template_multi_rule_quiz_items,
    get_available_template_quiz_sources,
    get_available_template_quiz_sources_for_card,
    get_template_quiz_rule,
    get_template_quiz_rules,
)
from src.ui_streamlit.common import collection_label, render_back_to_today_button, set_page_focus


QUIZ_TYPE_OPTIONS = {
    "Term -> Meaning Self-Graded": "term_to_meaning",
    "Meaning -> Term Self-Graded": "meaning_to_term",
    "Term -> Meaning Multiple Choice": "term_to_meaning_mcq",
    "Meaning -> Term Multiple Choice": "meaning_to_term_mcq",
    "Mixed Multiple Choice": "mixed_mcq",
    "Matching": "matching",
}

WHOLE_COLLECTION_QUIZ_TYPES = {"matching"}
REVIEW_CARD_FOCUS_REASONS = {"review_quick_quiz", "review_choose_quiz_type"}

SELF_GRADED_TYPES = {"term_to_meaning", "meaning_to_term", TEMPLATE_FIELD_SELF_GRADED}
MCQ_TYPES = {"term_to_meaning_mcq", "meaning_to_term_mcq", "mixed_mcq", TEMPLATE_FIELD_MCQ}
MATCHING_TYPES = {"matching", TEMPLATE_FIELD_MATCHING}
MATCHING_ITEM_COUNTS = [4, 6, 8, 10]
RANDOM_QUIZ_ITEM_COUNTS = [5, 10, 15, 20]

QUIZ_STATE_KEYS = [
    "quiz_active_session_id",
    "quiz_collection_id",
    "quiz_card_number",
    "quiz_type",
    "quiz_items",
    "quiz_current_index",
    "quiz_show_answer",
    "quiz_feedback",
    "quiz_completed_session",
    "quiz_results",
    "matching_meaning_choices",
    "quiz_generation_warning",
    "quiz_cancel_requested",
    "quiz_restart_requested",
    "matching_submitted",
    "template_quiz_rule",
    "template_quiz_template_id",
    "template_quiz_template_name",
    "template_quiz_template_type",
    "template_quiz_skipped_count",
    "quiz_hint_visible",
]

QUIZ_FOCUS_KEYS = [
    "quiz_focus_collection_id",
    "quiz_focus_card_number",
    "quiz_focus_type",
    "quiz_focus_source",
    "quiz_focus_reason",
    "quiz_focus_title",
    "quiz_focus_created_at",
    "quiz_autostart_focus",
    "focus_quiz_collection_id",
    "focus_quiz_card_number",
    "focus_quiz_source",
]

QUIZ_QUEUE_KEYS = [
    "quiz_queue",
    "quiz_queue_index",
    "quiz_queue_source",
    "quiz_queue_created_at",
]


def _reset_quiz_state() -> None:
    for key in QUIZ_STATE_KEYS:
        st.session_state.pop(key, None)

    for key in list(st.session_state.keys()):
        if (
            key.startswith("quiz_user_answer_")
            or key.startswith("mcq_answer_")
            or key.startswith("matching_answer_")
            or key.startswith("quiz_hint_")
        ):
            st.session_state.pop(key, None)


def _answer_key(session_id: int, item_index: int) -> str:
    return f"quiz_user_answer_{session_id}_{item_index}"


def _mcq_answer_key(session_id: int, item_index: int) -> str:
    return f"mcq_answer_{session_id}_{item_index}"


def _matching_answer_key(session_id: int, entry_id: int) -> str:
    return f"matching_answer_{session_id}_{entry_id}"


def _hint_key(session_id: int, item_index: int) -> str:
    return f"quiz_hint_{session_id}_{item_index}"


def _get_active_quiz_items() -> list[dict]:
    return st.session_state.get("quiz_items", [])


def _render_quiz_hint(item: dict, session_id: int, current_index: int) -> None:
    hint_key = _hint_key(session_id, current_index)
    if st.button("Show Hint", key=f"show_hint_{session_id}_{current_index}"):
        st.session_state[hint_key] = True
        st.rerun()

    if not st.session_state.get(hint_key):
        return

    example = str(item.get("example", "") or "").strip()
    if example:
        st.info(f"Example: {example}")
    else:
        st.info("No example hint is available for this entry.")



def clear_active_quiz_state() -> None:
    for key in [
        "quiz_active_session_id",
        "quiz_collection_id",
        "quiz_card_number",
        "quiz_type",
        "quiz_items",
        "quiz_current_index",
        "quiz_show_answer",
        "quiz_feedback",
        "quiz_results",
        "matching_meaning_choices",
        "quiz_generation_warning",
        "quiz_cancel_requested",
        "quiz_restart_requested",
        "matching_submitted",
        "template_quiz_rule",
        "template_quiz_template_id",
        "template_quiz_template_name",
        "template_quiz_template_type",
        "template_quiz_skipped_count",
        "quiz_hint_visible",
    ]:
        st.session_state.pop(key, None)

    for key in list(st.session_state.keys()):
        if (
            key.startswith("quiz_user_answer_")
            or key.startswith("mcq_answer_")
            or key.startswith("matching_answer_")
            or key.startswith("quiz_hint_")
        ):
            st.session_state.pop(key, None)


def _has_active_quiz_state() -> bool:
    return st.session_state.get("quiz_active_session_id") is not None


def _quiz_generation_signature(
    quiz_items: list[dict],
    meaning_choices: list[str] | None = None,
) -> tuple:
    return (
        tuple(
            (
                item.get("entry_id"),
                item.get("prompt", item.get("term", "")),
                tuple(item.get("options", [])),
                item.get("expected_answer", item.get("expected_meaning", "")),
            )
            for item in quiz_items
        ),
        tuple(meaning_choices or []),
    )


def _remember_quiz_generation(
    quiz_items: list[dict],
    meaning_choices: list[str] | None = None,
) -> None:
    st.session_state["quiz_last_generation_signature"] = _quiz_generation_signature(
        quiz_items,
        meaning_choices,
    )


def _quiz_type_label(quiz_type_value: str) -> str:
    if quiz_type_value == TEMPLATE_FIELD_SELF_GRADED:
        return "Template Field Self-Graded"
    if quiz_type_value == TEMPLATE_FIELD_MCQ:
        return "Template Field Multiple Choice"
    if quiz_type_value == TEMPLATE_FIELD_MATCHING:
        return "Template Field Matching"

    for label, quiz_type in QUIZ_TYPE_OPTIONS.items():
        if quiz_type == quiz_type_value:
            return label

    return quiz_type_value


def _is_review_card_focus(focus: dict | None) -> bool:
    if focus is None or focus.get("reason") not in REVIEW_CARD_FOCUS_REASONS:
        return False
    try:
        return int(focus.get("card_number") or 0) > 0
    except (TypeError, ValueError):
        return False


def _compatible_quiz_type_options(focus: dict | None) -> dict[str, str]:
    if not _is_review_card_focus(focus):
        return dict(QUIZ_TYPE_OPTIONS)
    return {
        label: quiz_type
        for label, quiz_type in QUIZ_TYPE_OPTIONS.items()
        if quiz_type not in WHOLE_COLLECTION_QUIZ_TYPES
    }


def _log_item_result(
    session_id: int,
    item: dict,
    prompt: str,
    expected_answer: str,
    user_answer: str,
    is_correct: bool,
) -> bool:
    record_result = record_quiz_answer(
        session_id=session_id,
        entry_id=item["entry_id"],
        prompt=prompt,
        expected_answer=expected_answer,
        user_answer=user_answer,
        is_correct=is_correct,
    )

    if not record_result["logged"]:
        st.session_state["quiz_feedback"] = {
            "is_correct": is_correct,
            "expected_answer": expected_answer,
            "message": "This answer has already been submitted.",
        }
        return False

    result_item = {
        "entry_id": item["entry_id"],
        "term": item.get("term", ""),
        "prompt": prompt,
        "expected_answer": expected_answer,
        "user_answer": user_answer,
        "result": "Correct" if is_correct else "Wrong",
    }
    for metadata_key in [
        "template_name",
        "template_type",
        "rule_label",
        "source_field_label",
        "source_field_key",
        "target_field_label",
        "target_field_key",
    ]:
        if item.get(metadata_key):
            result_item[metadata_key] = item[metadata_key]
    st.session_state.setdefault("quiz_results", []).append(result_item)
    return True


def _cancel_active_quiz(session_id: int) -> None:
    mark_quiz_session_cancelled(session_id)
    clear_active_quiz_state()
    st.session_state.pop("quiz_completed_session", None)
    st.success("Quiz cancelled. Existing answered item logs are kept.")


def _save_restart_prefill(session: dict) -> None:
    st.session_state["quiz_prefill_collection_id"] = session["collection_id"]
    st.session_state["quiz_prefill_card_number"] = session["card_number"]
    st.session_state["quiz_prefill_type"] = session["quiz_type"]


def _render_cancel_restart_confirmation(session_id: int) -> None:
    if st.session_state.get("quiz_cancel_requested"):
        st.warning("Cancel this quiz? Existing answered item logs will be kept.")
        confirm_col1, confirm_col2 = st.columns(2)
        with confirm_col1:
            if st.button("Confirm Cancel Quiz"):
                _cancel_active_quiz(session_id)
                st.rerun()
        with confirm_col2:
            if st.button("Keep Quiz"):
                st.session_state.pop("quiz_cancel_requested", None)
                st.rerun()

    if st.session_state.get("quiz_restart_requested"):
        st.warning("Restart this quiz? The current session will be marked cancelled and its logs will be kept.")
        confirm_col1, confirm_col2 = st.columns(2)
        with confirm_col1:
            if st.button("Confirm Restart Quiz"):
                session = st.session_state.get("quiz_restart_source_session")
                if session is None:
                    session = {
                        "collection_id": st.session_state.get("quiz_collection_id"),
                        "card_number": st.session_state.get("quiz_card_number"),
                        "quiz_type": st.session_state.get("quiz_type"),
                    }
                mark_quiz_session_cancelled(session_id)
                clear_active_quiz_state()
                st.session_state.pop("quiz_completed_session", None)
                if session.get("collection_id") is not None:
                    _save_restart_prefill(session)
                st.success("Previous quiz cancelled. Choose Start Quiz to begin again with the same settings.")
                st.rerun()
        with confirm_col2:
            if st.button("Keep Current Quiz"):
                st.session_state.pop("quiz_restart_requested", None)
                st.session_state.pop("quiz_restart_source_session", None)
                st.rerun()


def _render_active_quiz_panel(session: dict, can_continue: bool) -> None:
    collection = get_collection_by_id(session["collection_id"])
    try:
        progress = get_quiz_progress(session["id"])
    except ValueError:
        progress = {"answered_items": 0, "total_items": session.get("total_items", 0)}

    collection_name = collection["name"] if collection else session["collection_id"]
    if session["card_number"]:
        card_label = f"Card #{session['card_number']}"
    elif session["card_number"] == 0:
        card_label = "Random / Whole Collection"
    else:
        card_label = "Collection"
    st.warning(
        "You already have an active quiz: "
        f"{collection_name} / {card_label} / {_quiz_type_label(session['quiz_type'])}."
    )
    st.write(f"session_id: {session['id']}")
    st.write(f"collection: {collection_name}")
    st.write(f"card: {card_label}")
    st.write(f"quiz_type: {_quiz_type_label(session['quiz_type'])}")
    st.write(f"progress: {progress['answered_items']} / {progress['total_items']}")
    st.write(f"started_at: {session['started_at']}")

    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if can_continue and st.button("Continue Quiz"):
            st.session_state.pop("quiz_cancel_requested", None)
            st.session_state.pop("quiz_restart_requested", None)
            st.rerun()
    with action_col2:
        if st.button("Cancel Quiz", key=f"cancel_quiz_{session['id']}"):
            st.session_state["quiz_cancel_requested"] = True
            st.session_state.pop("quiz_restart_requested", None)
            st.rerun()
    with action_col3:
        if st.button("Restart Quiz", key=f"restart_quiz_{session['id']}"):
            st.session_state["quiz_restart_requested"] = True
            st.session_state["quiz_restart_source_session"] = session
            st.session_state.pop("quiz_cancel_requested", None)
            st.rerun()

    _render_cancel_restart_confirmation(session["id"])


def _selectbox_index_by_id(options: list[dict], target_id: int | None) -> int:
    if target_id is None:
        return 0

    for index, option in enumerate(options):
        if option["id"] == target_id:
            return index

    return 0


def _clear_quiz_focus() -> None:
    for key in QUIZ_FOCUS_KEYS:
        st.session_state.pop(key, None)


def _clear_quiz_queue() -> None:
    for key in QUIZ_QUEUE_KEYS:
        st.session_state.pop(key, None)


def _get_quiz_queue() -> list[dict]:
    queue = st.session_state.get("quiz_queue", [])
    return queue if isinstance(queue, list) else []


def _get_quiz_queue_index() -> int:
    queue = _get_quiz_queue()
    if not queue:
        st.session_state["quiz_queue_index"] = 0
        return 0

    index = int(st.session_state.get("quiz_queue_index", 0) or 0)
    index = min(max(index, 0), len(queue) - 1)
    st.session_state["quiz_queue_index"] = index
    return index


def _set_quiz_focus_from_queue_item(queue_item: dict) -> None:
    st.session_state["quiz_focus_collection_id"] = queue_item["collection_id"]
    st.session_state["quiz_focus_card_number"] = queue_item["card_number"]
    st.session_state["quiz_focus_type"] = queue_item.get("preferred_quiz_type") or "mixed_mcq"
    st.session_state["quiz_focus_source"] = "ordered_quiz_queue"
    st.session_state["quiz_focus_reason"] = queue_item.get("reason") or "queued_card"
    st.session_state["quiz_focus_title"] = queue_item.get("title") or "Queued quiz card"
    st.session_state["focus_quiz_collection_id"] = queue_item["collection_id"]
    st.session_state["focus_quiz_card_number"] = queue_item["card_number"]
    st.session_state["focus_quiz_source"] = queue_item.get("reason") or "queued_card"


def _start_current_queued_quiz() -> bool:
    queue = _get_quiz_queue()
    if not queue:
        st.warning("No queued quiz cards are available.")
        return False

    index = _get_quiz_queue_index()
    queue_item = queue[index]
    _set_quiz_focus_from_queue_item(queue_item)
    return _start_quiz_from_parameters(
        int(queue_item["collection_id"]),
        int(queue_item["card_number"]),
        queue_item.get("preferred_quiz_type") or "mixed_mcq",
    )


def _advance_quiz_queue() -> bool:
    queue = _get_quiz_queue()
    if not queue:
        return False

    next_index = _get_quiz_queue_index() + 1
    if next_index >= len(queue):
        _clear_quiz_queue()
        _clear_quiz_focus()
        return False

    st.session_state["quiz_queue_index"] = next_index
    _set_quiz_focus_from_queue_item(queue[next_index])
    return True


def _get_quiz_focus() -> dict | None:
    collection_id = st.session_state.get("quiz_focus_collection_id")
    if collection_id is None:
        collection_id = st.session_state.get("focus_quiz_collection_id")
    quiz_type = st.session_state.get("quiz_focus_type")
    if quiz_type is None and collection_id is not None:
        quiz_type = "mixed_mcq"

    if collection_id is None or quiz_type is None:
        return None

    try:
        collection_id = int(collection_id)
    except (TypeError, ValueError):
        _clear_quiz_focus()
        return None

    collection = get_collection_by_id(collection_id)
    if collection is None:
        return None

    card_number = st.session_state.get("quiz_focus_card_number")
    if card_number is None:
        card_number = st.session_state.get("focus_quiz_card_number")
    if card_number is not None:
        try:
            card_number = int(card_number)
        except (TypeError, ValueError):
            card_number = None

    return {
        "collection_id": collection_id,
        "collection_name": collection["name"],
        "card_number": card_number,
        "quiz_type": quiz_type,
        "source": st.session_state.get("quiz_focus_source"),
        "reason": st.session_state.get("quiz_focus_reason")
        or st.session_state.get("focus_quiz_source"),
        "title": st.session_state.get("quiz_focus_title") or "Today quiz focus",
    }


def _apply_quiz_focus_prefill(focus: dict | None) -> None:
    if focus is None:
        return

    st.session_state["quiz_prefill_collection_id"] = focus["collection_id"]
    st.session_state["quiz_prefill_card_number"] = focus["card_number"]
    st.session_state["quiz_prefill_type"] = focus["quiz_type"]


def _render_quiz_focus_banner(focus: dict | None) -> None:
    if (
        st.session_state.get("quiz_focus_collection_id") is None
        and st.session_state.get("focus_quiz_collection_id") is None
    ):
        return

    if focus is None:
        st.warning("The quiz focus from Today is no longer available. The focus was cleared.")
        _clear_quiz_focus()
        return

    card_label = (
        "Random / Whole Collection"
        if focus["card_number"] == 0
        else f"Card #{focus['card_number']}"
        if focus["card_number"] is not None
        else "Collection"
    )
    st.info(
        "Focused Card: "
        f"{focus['collection_name']} / {card_label} / {_quiz_type_label(focus['quiz_type'])}."
    )
    if st.button("Clear Today quiz focus", key="clear_today_quiz_focus"):
        _clear_quiz_focus()
        st.success("Today quiz focus cleared.")
        st.rerun()


def _render_quiz_queue_panel() -> None:
    queue = _get_quiz_queue()
    if not queue:
        return

    index = _get_quiz_queue_index()
    current_item = queue[index]
    st.info(
        "Ordered quiz queue: "
        f"{index + 1} / {len(queue)} - "
        f"{current_item.get('collection_name', current_item['collection_id'])} / "
        f"Card #{current_item['card_number']}."
    )
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("Start Current Queued Quiz", key="start_current_queued_quiz", type="primary"):
            if _start_current_queued_quiz():
                st.rerun()
    with action_col2:
        if st.button("Clear Quiz Queue", key="clear_ordered_quiz_queue"):
            _clear_quiz_queue()
            _clear_quiz_focus()
            st.success("Quiz queue cleared.")
            st.rerun()


def _start_quiz_from_parameters(
    collection_id: int,
    card_number: int,
    quiz_type: str,
    matching_count: int | None = None,
) -> bool:
    database_active_session = get_active_quiz_session()
    if database_active_session is not None:
        st.warning("You already have an active quiz. Continue, cancel, or restart it before starting another quiz.")
        _render_active_quiz_panel(database_active_session, can_continue=False)
        return False

    try:
        meaning_choices = None
        if quiz_type in SELF_GRADED_TYPES:
            entries = get_entries_for_quiz(collection_id, card_number)
            if not entries:
                st.warning("The selected collection card has no entries.")
                return False
            last_signature = st.session_state.get("quiz_last_generation_signature")
            for _ in range(8):
                quiz_items = create_quiz_items(entries, quiz_type)
                if _quiz_generation_signature(quiz_items) != last_signature:
                    break
            session_card_number = card_number
        elif quiz_type in MCQ_TYPES:
            target_entries = get_entries_for_quiz(collection_id, card_number)
            if not target_entries:
                st.warning("The selected collection card has no entries.")
                return False
            last_signature = st.session_state.get("quiz_last_generation_signature")
            for _ in range(8):
                quiz_items = generate_mcq_items(
                    collection_id,
                    card_number,
                    quiz_type,
                )
                if _quiz_generation_signature(quiz_items) != last_signature:
                    break
            if len(quiz_items) < len(target_entries):
                st.session_state["quiz_generation_warning"] = (
                    "Some items were skipped because there were not enough "
                    "unambiguous distractors in the selected card."
                )
            else:
                st.session_state.pop("quiz_generation_warning", None)
            session_card_number = card_number
        else:
            if matching_count is None:
                matching_count = MATCHING_ITEM_COUNTS[0]
            last_signature = st.session_state.get("quiz_last_generation_signature")
            for _ in range(8):
                matching_quiz = generate_matching_items(collection_id, int(matching_count))
                quiz_items = matching_quiz["items"]
                meaning_choices = matching_quiz["meaning_choices"]
                if _quiz_generation_signature(quiz_items, meaning_choices) != last_signature:
                    break
            st.session_state["matching_meaning_choices"] = meaning_choices
            session_card_number = 0

        session_id = create_quiz_session(
            collection_id,
            session_card_number,
            quiz_type,
            len(quiz_items),
        )
    except ValueError as error:
        message = str(error)
        if quiz_type in MCQ_TYPES:
            message = MCQ_GENERATION_ERROR
        st.warning(message)
        return False

    st.session_state["quiz_active_session_id"] = session_id
    st.session_state["quiz_collection_id"] = collection_id
    st.session_state["quiz_card_number"] = session_card_number
    st.session_state["quiz_type"] = quiz_type
    st.session_state["quiz_items"] = quiz_items
    st.session_state["quiz_current_index"] = 0
    st.session_state["quiz_show_answer"] = False
    st.session_state["quiz_hint_visible"] = False
    st.session_state["quiz_feedback"] = None
    st.session_state["quiz_results"] = []
    st.session_state["last_quiz_collection_id"] = collection_id
    st.session_state["last_quiz_card_number"] = session_card_number
    st.session_state["last_quiz_type"] = quiz_type
    if quiz_type not in MATCHING_TYPES:
        st.session_state.pop("matching_meaning_choices", None)
    _remember_quiz_generation(
        quiz_items,
        st.session_state.get("matching_meaning_choices")
        if quiz_type in MATCHING_TYPES
        else None,
    )
    if quiz_type not in MCQ_TYPES:
        st.session_state.pop("quiz_generation_warning", None)
    st.session_state.pop("quiz_completed_session", None)
    st.session_state.pop("quiz_prefill_collection_id", None)
    st.session_state.pop("quiz_prefill_card_number", None)
    st.session_state.pop("quiz_prefill_type", None)
    _clear_quiz_focus()
    return True


def _start_template_quiz_from_parameters(
    collection_id: int,
    card_number: int,
    template_source: dict,
    rules: list[dict],
    quiz_type: str,
    difficulty: str,
) -> bool:
    database_active_session = get_active_quiz_session()
    if database_active_session is not None:
        st.warning("You already have an active quiz. Continue, cancel, or restart it before starting another quiz.")
        _render_active_quiz_panel(database_active_session, can_continue=False)
        return False

    generated_quiz = generate_template_multi_rule_quiz_items(
        collection_id=collection_id,
        card_number=card_number,
        template_id=int(template_source["template_id"]),
        rules=rules,
        quiz_type=quiz_type,
        difficulty=difficulty,
    )
    quiz_items = generated_quiz["quiz_items"]
    meaning_choices = generated_quiz.get("meaning_choices")
    skipped_count = generated_quiz["skipped_count"]
    warning = generated_quiz.get("warning", "")
    if not quiz_items:
        st.warning("No valid template quiz items were found. Fill the fields used by the selected rules first.")
        return False

    session_id = create_quiz_session(
        collection_id,
        card_number,
        quiz_type,
        len(quiz_items),
    )

    st.session_state["quiz_active_session_id"] = session_id
    st.session_state["quiz_collection_id"] = collection_id
    st.session_state["quiz_card_number"] = card_number
    st.session_state["quiz_type"] = quiz_type
    st.session_state["quiz_items"] = quiz_items
    st.session_state["quiz_current_index"] = 0
    st.session_state["quiz_show_answer"] = False
    st.session_state["quiz_hint_visible"] = False
    st.session_state["quiz_feedback"] = None
    st.session_state["quiz_results"] = []
    st.session_state["template_quiz_rule"] = {
        "label": ", ".join(rule["label"] for rule in rules),
        "difficulty": difficulty,
        "quiz_type": quiz_type,
    }
    st.session_state["template_quiz_template_id"] = int(template_source["template_id"])
    st.session_state["template_quiz_template_name"] = template_source["template_name"]
    st.session_state["template_quiz_template_type"] = template_source["template_type"]
    st.session_state["template_quiz_skipped_count"] = skipped_count
    st.session_state["last_quiz_collection_id"] = collection_id
    st.session_state["last_quiz_card_number"] = card_number
    st.session_state["last_quiz_type"] = quiz_type
    if quiz_type in MATCHING_TYPES:
        st.session_state["matching_meaning_choices"] = meaning_choices or []
    else:
        st.session_state.pop("matching_meaning_choices", None)
    warnings = []
    if skipped_count:
        warnings.append(
            f"Skipped {skipped_count} item(s) because the selected prompt or answer field was empty."
        )
    if warning:
        warnings.append(warning)
    if warnings:
        st.session_state["quiz_generation_warning"] = " ".join(warnings)
    else:
        st.session_state.pop("quiz_generation_warning", None)
    _remember_quiz_generation(
        quiz_items,
        st.session_state.get("matching_meaning_choices")
        if quiz_type in MATCHING_TYPES
        else None,
    )
    st.session_state.pop("quiz_completed_session", None)
    _clear_quiz_focus()
    return True


def _start_random_quiz_from_proficient_pool(
    quiz_type: str,
    item_count: int,
) -> bool:
    database_active_session = get_active_quiz_session()
    if database_active_session is not None:
        st.warning("You already have an active quiz. Continue, cancel, or restart it before starting another quiz.")
        _render_active_quiz_panel(database_active_session, can_continue=False)
        return False

    proficient_pool = get_system_collection("proficient_pool")
    if proficient_pool is None:
        st.warning("Proficient Pool does not exist yet. Add entries from Entries Select Mode first.")
        return False

    try:
        generated_quiz = generate_random_quiz_items(
            proficient_pool["id"],
            quiz_type,
            int(item_count),
        )
        quiz_items = generated_quiz["quiz_items"]
        meaning_choices = generated_quiz.get("meaning_choices")
        warning = generated_quiz.get("warning")
        session_id = create_random_quiz_session(
            proficient_pool["id"],
            quiz_type,
            len(quiz_items),
        )
    except ValueError as error:
        message = str(error)
        if quiz_type in MCQ_TYPES and message == MCQ_GENERATION_ERROR:
            message = MCQ_GENERATION_ERROR
        st.warning(message)
        return False

    st.session_state["quiz_active_session_id"] = session_id
    st.session_state["quiz_collection_id"] = proficient_pool["id"]
    st.session_state["quiz_card_number"] = 0
    st.session_state["quiz_type"] = quiz_type
    st.session_state["quiz_items"] = quiz_items
    st.session_state["quiz_current_index"] = 0
    st.session_state["quiz_show_answer"] = False
    st.session_state["quiz_hint_visible"] = False
    st.session_state["quiz_feedback"] = None
    st.session_state["quiz_results"] = []
    st.session_state["last_quiz_collection_id"] = proficient_pool["id"]
    st.session_state["last_quiz_card_number"] = 0
    st.session_state["last_quiz_type"] = quiz_type
    if quiz_type in MATCHING_TYPES:
        st.session_state["matching_meaning_choices"] = meaning_choices or []
    else:
        st.session_state.pop("matching_meaning_choices", None)
    if warning:
        st.session_state["quiz_generation_warning"] = warning
    else:
        st.session_state.pop("quiz_generation_warning", None)
    _remember_quiz_generation(
        quiz_items,
        st.session_state.get("matching_meaning_choices")
        if quiz_type in MATCHING_TYPES
        else None,
    )
    st.session_state.pop("quiz_completed_session", None)
    _clear_quiz_focus()
    return True


def _card_numbers_for_collection(collection_id: int) -> list[int]:
    return [
        card_group["card_number"]
        for card_group in get_card_groups_for_collection(collection_id)
    ]


def _render_card_select(
    label: str,
    collection_id: int,
    key: str,
    preferred_card_number: int | None = None,
) -> int | None:
    card_numbers = _card_numbers_for_collection(collection_id)
    if not card_numbers:
        st.warning("This collection has no cards yet.")
        return None

    return st.selectbox(
        label,
        card_numbers,
        index=card_numbers.index(preferred_card_number)
        if preferred_card_number in card_numbers
        else 0,
        format_func=lambda card_number: f"Card #{card_number}",
        key=key,
    )


def _render_special_collection_preset(
    title: str,
    system_type: str,
    missing_message: str,
    empty_message: str,
    quiz_type: str,
    button_label: str,
) -> None:
    collection = get_system_collection(system_type)
    if collection is None:
        st.info(missing_message)
        return

    card_groups = get_card_groups_for_collection(collection["id"])
    if not card_groups:
        st.info(empty_message)
        return

    st.write(title)
    selected_card_number = st.selectbox(
        "Card",
        [card_group["card_number"] for card_group in card_groups],
        format_func=lambda card_number: f"Card #{card_number}",
        key=f"preset_{system_type}_card_select",
    )
    if st.button(button_label, key=f"preset_{system_type}_start"):
        if _start_quiz_from_parameters(collection["id"], selected_card_number, quiz_type):
            st.rerun()


def _render_quick_quiz_presets(collections: list[dict]) -> None:
    st.subheader("Quick Quiz Presets")

    selected_collection = st.selectbox(
        "Preset Collection",
        collections,
        index=_selectbox_index_by_id(
            collections,
            st.session_state.get("last_quiz_collection_id"),
        ),
        format_func=collection_label,
        key="preset_collection_select",
    )
    selected_card_number = _render_card_select(
        "Preset Card",
        selected_collection["id"],
        "preset_card_select",
        st.session_state.get("last_quiz_card_number"),
    )

    if selected_card_number is not None:
        preset_col1, preset_col2 = st.columns(2)
        with preset_col1:
            if st.button("Quick Self-Graded Quiz"):
                if _start_quiz_from_parameters(
                    selected_collection["id"],
                    selected_card_number,
                    "term_to_meaning",
                ):
                    st.rerun()
        with preset_col2:
            if st.button("Quick MCQ for Selected Card"):
                if _start_quiz_from_parameters(
                    selected_collection["id"],
                    selected_card_number,
                    "mixed_mcq",
                ):
                    st.rerun()

        available_count = sum(
            len(card_group["entries"])
            for card_group in get_card_groups_for_collection(selected_collection["id"])
        )
        available_item_counts = [count for count in MATCHING_ITEM_COUNTS if count <= available_count]
        if not available_item_counts and available_count >= 2:
            available_item_counts = [available_count]

        if available_item_counts:
            matching_col1, matching_col2 = st.columns([1, 1])
            with matching_col1:
                selected_matching_count = st.selectbox(
                    "Matching Practice Count",
                    available_item_counts,
                    index=0,
                    key="preset_matching_count_select",
                )
            with matching_col2:
                if st.button("Matching Practice"):
                    if _start_quiz_from_parameters(
                        selected_collection["id"],
                        0,
                        "matching",
                        int(selected_matching_count),
                    ):
                        st.rerun()
        else:
            st.info("Matching Practice requires at least 2 entries in the selected collection.")

    special_col1, special_col2 = st.columns(2)
    with special_col1:
        _render_special_collection_preset(
            "Mistake Drill",
            "mistake_book",
            "Mistake Book does not exist yet. Wrong quiz answers will create it automatically.",
            "Mistake Book has no entries yet.",
            "mixed_mcq",
            "Start Mistake Drill",
        )
    with special_col2:
        _render_special_collection_preset(
            "Starred Review",
            "starred",
            "Starred collection does not exist yet. Add entries to Starred first.",
            "Starred has no entries yet.",
            "mixed_mcq",
            "Start Starred Review",
        )


def _render_manual_quiz_selection(
    collections: list[dict],
    focus: dict | None = None,
) -> None:
    st.subheader("Manual Quiz Selection")

    selected_collection = st.selectbox(
        "Select Collection",
        collections,
        index=_selectbox_index_by_id(
            collections,
            st.session_state.get("quiz_prefill_collection_id"),
        ),
        format_func=collection_label,
        key="quiz_collection_select",
    )
    card_groups = get_card_groups_for_collection(selected_collection["id"])

    if not card_groups:
        st.warning("This collection has no cards yet.")
        return

    quiz_type_options = _compatible_quiz_type_options(focus)
    quiz_type_labels = list(quiz_type_options.keys())
    prefill_quiz_type = st.session_state.get("quiz_prefill_type")
    prefill_quiz_type_label = next(
        (label for label, quiz_type in quiz_type_options.items() if quiz_type == prefill_quiz_type),
        quiz_type_labels[0],
    )
    selected_quiz_type_label = st.selectbox(
        "Select Quiz Type",
        quiz_type_labels,
        index=quiz_type_labels.index(prefill_quiz_type_label),
        key="quiz_type_select",
    )
    selected_quiz_type = quiz_type_options[selected_quiz_type_label]

    selected_card_number = 1
    selected_matching_count = None
    if selected_quiz_type != "matching":
        selected_card_number = _render_card_select(
            "Select Card Number",
            selected_collection["id"],
            "quiz_card_select",
            st.session_state.get("quiz_prefill_card_number"),
        )
        if selected_card_number is None:
            return
    else:
        available_count = sum(len(card_group["entries"]) for card_group in card_groups)
        available_item_counts = [count for count in MATCHING_ITEM_COUNTS if count <= available_count]
        if not available_item_counts and available_count >= 2:
            available_item_counts = [available_count]

        if available_count < 2:
            st.warning("Matching quiz requires at least 2 entries in the selected collection.")
            return

        selected_matching_count = st.selectbox(
            "Matching item count",
            available_item_counts,
            index=0,
            key="matching_item_count_select",
        )
        selected_card_number = 0

    if st.button("Start Quiz"):
        if _start_quiz_from_parameters(
            selected_collection["id"],
            selected_card_number,
            selected_quiz_type,
            int(selected_matching_count) if selected_matching_count is not None else None,
        ):
            st.rerun()


def _render_template_aware_quiz_setup(
    collections: list[dict],
    focus: dict | None = None,
) -> None:
    st.subheader("Template-Aware Quiz")

    selected_collection = st.selectbox(
        "Template Quiz Collection",
        collections,
        index=_selectbox_index_by_id(
            collections,
            focus.get("collection_id")
            if _is_review_card_focus(focus)
            else st.session_state.get("last_quiz_collection_id"),
        ),
        format_func=collection_label,
        key="template_quiz_collection_select",
    )

    card_groups = get_card_groups_for_collection(selected_collection["id"])
    if not card_groups:
        st.info("This collection has no cards yet.")
        return

    selected_card_number = st.selectbox(
        "Template Quiz Card",
        [card_group["card_number"] for card_group in card_groups],
        index=next(
            (
                index
                for index, card_group in enumerate(card_groups)
                if _is_review_card_focus(focus)
                and card_group["card_number"] == focus.get("card_number")
            ),
            0,
        ),
        format_func=lambda card_number: f"Card #{card_number}",
        key="template_quiz_card_select",
    )

    template_sources = get_available_template_quiz_sources_for_card(
        selected_collection["id"],
        int(selected_card_number),
    )
    if not template_sources:
        st.info("This card has no entries using a template with template-aware quiz rules yet.")
        return

    selected_template_source = st.selectbox(
        "Template",
        template_sources,
        format_func=lambda source: f"{source['template_name']} ({source['entry_count']} entries)",
        key="template_quiz_template_select",
    )
    rules = get_template_quiz_rules(selected_template_source["template_type"])
    if not rules:
        st.info("The selected template has no template-aware quiz rules yet.")
        return

    rule_by_id = {rule["id"]: rule for rule in rules}
    st.session_state["template_quiz_rule_multiselect"] = [
        rule_id
        for rule_id in st.session_state.get("template_quiz_rule_multiselect", [])
        if rule_id in rule_by_id
    ]
    if st.button("Select All Rules", key="template_quiz_select_all_rules"):
        st.session_state["template_quiz_rule_multiselect"] = list(rule_by_id.keys())
        st.rerun()

    selected_rule_ids = st.multiselect(
        "Rules",
        list(rule_by_id.keys()),
        format_func=lambda rule_id: rule_by_id[rule_id]["label"],
        key="template_quiz_rule_multiselect",
    )
    selected_rules = [rule_by_id[rule_id] for rule_id in selected_rule_ids]

    selected_template_quiz_type_label = st.selectbox(
        "Select Quiz Type",
        list(TEMPLATE_QUIZ_TYPES.keys()),
        key="template_quiz_type_select",
    )
    selected_template_quiz_type = TEMPLATE_QUIZ_TYPES[selected_template_quiz_type_label]

    selected_difficulty = st.selectbox(
        "Difficulty",
        TEMPLATE_QUIZ_DIFFICULTIES,
        index=TEMPLATE_QUIZ_DIFFICULTIES.index("Normal"),
        key="template_quiz_difficulty_select",
    )

    if st.button("Start Template-Aware Quiz"):
        if not selected_rules:
            st.warning("Select at least one rule.")
            return
        if _start_template_quiz_from_parameters(
            selected_collection["id"],
            int(selected_card_number),
            selected_template_source,
            selected_rules,
            selected_template_quiz_type,
            selected_difficulty,
        ):
            st.rerun()


def _render_quiz_setup() -> None:
    st.header("Select Quiz Source")
    focus = _get_quiz_focus()
    _apply_quiz_focus_prefill(focus)

    database_active_session = get_active_quiz_session()
    if database_active_session is not None:
        st.warning(
            "An unfinished quiz session exists, but automatic recovery is limited. "
            "You may cancel it or start again after cancelling it."
        )
        _render_active_quiz_panel(database_active_session, can_continue=False)
        return

    collections = get_collections()

    if not collections:
        st.info("Create a collection before starting a quiz.")
        return

    if focus is not None and st.session_state.pop("quiz_autostart_focus", None):
        if _start_quiz_from_parameters(
            int(focus["collection_id"]),
            int(focus["card_number"] or 0),
            focus["quiz_type"],
        ):
            st.rerun()

    _render_quiz_queue_panel()
    if _get_quiz_queue():
        st.divider()

    if _is_review_card_focus(focus):
        st.info(
            "Choose a Quiz type for the selected Review Card. "
            "Whole-Collection modes are not available in this focused flow."
        )
    else:
        _render_quick_quiz_presets(collections)
        st.divider()

    _render_template_aware_quiz_setup(collections, focus)
    st.divider()
    _render_manual_quiz_selection(collections, focus)


def _complete_active_quiz() -> None:
    session_id = st.session_state.get("quiz_active_session_id")
    if session_id is None:
        return

    st.session_state["quiz_completed_session"] = complete_quiz_session(session_id)
    st.session_state.pop("quiz_active_session_id", None)


def _advance_or_complete(next_index: int, total_items: int) -> None:
    st.session_state["quiz_current_index"] = next_index
    st.session_state["quiz_show_answer"] = False
    st.session_state["quiz_feedback"] = None

    if next_index >= total_items:
        _complete_active_quiz()

    st.rerun()


def _mark_current_self_graded_item(is_correct: bool) -> None:
    quiz_items = _get_active_quiz_items()
    current_index = st.session_state.get("quiz_current_index", 0)

    if current_index >= len(quiz_items):
        _complete_active_quiz()
        return

    current_item = quiz_items[current_index]
    session_id = st.session_state["quiz_active_session_id"]
    user_answer = st.session_state.get(_answer_key(session_id, current_index), "")

    logged = _log_item_result(
        session_id,
        current_item,
        current_item["prompt"],
        current_item["expected_answer"],
        user_answer,
        is_correct,
    )
    if logged:
        _advance_or_complete(current_index + 1, len(quiz_items))
    else:
        st.rerun()


def _submit_current_mcq_item() -> None:
    quiz_items = _get_active_quiz_items()
    current_index = st.session_state.get("quiz_current_index", 0)
    current_item = quiz_items[current_index]
    session_id = st.session_state["quiz_active_session_id"]
    selected_option = st.session_state.get(_mcq_answer_key(session_id, current_index))

    if not selected_option:
        st.warning("Select an option before submitting.")
        return

    is_correct = grade_mcq_answer(selected_option, current_item["correct_answer"])
    prompt_for_log = current_item["prompt"]
    if st.session_state.get("quiz_type") == "mixed_mcq":
        prompt_for_log = f"{prompt_for_log} [{_quiz_type_label(current_item['direction'])}]"

    logged = _log_item_result(
        session_id,
        current_item,
        prompt_for_log,
        current_item["correct_answer"],
        selected_option,
        is_correct,
    )
    if logged:
        st.session_state["quiz_feedback"] = {
            "is_correct": is_correct,
            "expected_answer": current_item["correct_answer"],
        }


def _render_self_graded_quiz(quiz_items: list[dict], current_index: int) -> None:
    current_item = quiz_items[current_index]
    if current_item.get("rule_label"):
        st.caption(current_item["rule_label"])
    if current_item.get("source_field_label"):
        st.write(f"Prompt field: {current_item['source_field_label']}")
    st.subheader(current_item["prompt"])

    session_id = st.session_state["quiz_active_session_id"]
    _render_quiz_hint(current_item, session_id, current_index)

    st.text_area(
        "Your Answer",
        key=_answer_key(session_id, current_index),
        height=120,
    )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("Show Answer"):
            st.session_state["quiz_show_answer"] = True
            st.rerun()
    with action_col2:
        if st.button("Cancel Quiz"):
            st.session_state["quiz_cancel_requested"] = True
            st.rerun()

    if st.session_state.get("quiz_show_answer"):
        if current_item.get("target_field_label"):
            st.write(f"Answer field: {current_item['target_field_label']}")
        st.info(current_item["expected_answer"])
        result_col1, result_col2 = st.columns(2)
        with result_col1:
            if st.button("Correct"):
                _mark_current_self_graded_item(True)
        with result_col2:
            if st.button("Wrong"):
                _mark_current_self_graded_item(False)


def _render_mcq_quiz(quiz_items: list[dict], current_index: int) -> None:
    current_item = quiz_items[current_index]
    session_id = st.session_state["quiz_active_session_id"]
    feedback = st.session_state.get("quiz_feedback")

    st.caption(_quiz_type_label(current_item["direction"]))
    st.subheader(current_item["prompt"])
    _render_quiz_hint(current_item, session_id, current_index)

    st.radio(
        "Options",
        current_item["options"],
        key=_mcq_answer_key(session_id, current_index),
        disabled=feedback is not None,
    )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if feedback is None:
            if st.button("Submit Answer"):
                _submit_current_mcq_item()
                st.rerun()
        else:
            if feedback["is_correct"]:
                st.success("Correct")
            else:
                st.error(f"Wrong. Expected answer: {feedback['expected_answer']}")

            if st.button("Next Question"):
                _advance_or_complete(current_index + 1, len(quiz_items))
    with action_col2:
        if st.button("Cancel Quiz"):
            st.session_state["quiz_cancel_requested"] = True
            st.rerun()


def _submit_matching_quiz() -> None:
    if st.session_state.get("matching_submitted"):
        st.warning("This matching quiz has already been submitted.")
        return

    session_id = st.session_state["quiz_active_session_id"]
    quiz_items = _get_active_quiz_items()
    user_matches = {
        item.get("matching_key", item["entry_id"]): st.session_state.get(
            _matching_answer_key(session_id, item.get("matching_key", item["entry_id"])),
            "",
        )
        for item in quiz_items
    }

    if any(not selected_meaning for selected_meaning in user_matches.values()):
        st.warning("Select a meaning for every term before submitting.")
        return

    results = []
    for item in quiz_items:
        match_key = item.get("matching_key", item["entry_id"])
        user_selected_meaning = user_matches.get(match_key, "")
        expected_meaning = item["expected_meaning"]
        results.append(
            {
                "entry_id": item["entry_id"],
                "term": item["term"],
                "expected_meaning": expected_meaning,
                "user_selected_meaning": user_selected_meaning,
                "is_correct": user_selected_meaning == expected_meaning,
            }
        )
    st.session_state["matching_submitted"] = True

    for result in results:
        item = {
            "entry_id": result["entry_id"],
            "term": result["term"],
        }
        _log_item_result(
            session_id,
            item,
            result["term"],
            result["expected_meaning"],
            result["user_selected_meaning"],
            result["is_correct"],
        )

    _complete_active_quiz()
    st.rerun()


def _render_matching_quiz(quiz_items: list[dict]) -> None:
    session_id = st.session_state["quiz_active_session_id"]
    meaning_choices = st.session_state.get("matching_meaning_choices", [])

    st.subheader("Match each term with its meaning")

    for item in quiz_items:
        row_col1, row_col2 = st.columns([1.5, 3])
        row_col1.write(item["term"])
        with row_col2:
            st.selectbox(
                "Meaning",
                [""] + meaning_choices,
                key=_matching_answer_key(
                    session_id,
                    item.get("matching_key", item["entry_id"]),
                ),
                label_visibility="collapsed",
            )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("Submit Matching Quiz", disabled=st.session_state.get("matching_submitted", False)):
            _submit_matching_quiz()
    with action_col2:
        if st.button("Cancel Quiz"):
            st.session_state["quiz_cancel_requested"] = True
            st.rerun()


def _render_active_quiz() -> None:
    quiz_items = _get_active_quiz_items()
    current_index = st.session_state.get("quiz_current_index", 0)
    quiz_type = st.session_state.get("quiz_type")

    if not quiz_items:
        st.warning("Quiz state is empty. Start a new quiz.")
        _reset_quiz_state()
        return

    if quiz_type not in MATCHING_TYPES and current_index >= len(quiz_items):
        _complete_active_quiz()
        st.rerun()

    st.header("Quiz")
    active_session = get_active_quiz_session()
    if active_session is not None and active_session["id"] == st.session_state.get("quiz_active_session_id"):
        _render_active_quiz_panel(active_session, can_continue=True)

    generation_warning = st.session_state.get("quiz_generation_warning")
    if generation_warning:
        st.warning(generation_warning)

    if quiz_type in MATCHING_TYPES:
        st.write(f"Matching items: {len(quiz_items)}")
        _render_matching_quiz(quiz_items)
    else:
        st.write(f"Question {current_index + 1} / {len(quiz_items)}")
        if quiz_type in MCQ_TYPES:
            _render_mcq_quiz(quiz_items, current_index)
        else:
            _render_self_graded_quiz(quiz_items, current_index)


def _render_mistakes_for_session(completed_session: dict) -> None:
    wrong_logs = get_quiz_item_log_view(
        show_wrong_only=True,
        session_id=completed_session["id"],
    )

    st.subheader("Mistakes in this quiz")

    if not wrong_logs:
        st.success("No wrong answers in this quiz.")
        return

    for wrong_log in wrong_logs:
        st.warning(
            "\n".join(
                [
                    f"entry_id: {wrong_log['entry_id']}",
                    f"term: {wrong_log['term']}",
                    f"quiz_type: {wrong_log['quiz_type']}",
                    f"prompt: {wrong_log['prompt']}",
                    f"expected_answer: {wrong_log['expected_answer']}",
                    f"user_answer: {wrong_log['user_answer'] or ''}",
                ]
            )
        )


def _remove_entries_from_mistake_book(entry_ids: list[int]) -> int:
    return remove_entries_from_system_collection(entry_ids, "mistake_book")


def _render_mistake_book_recovery_summary(completed_session: dict) -> None:
    if not is_mistake_book_collection(completed_session["collection_id"]):
        return

    recovered_entries = get_recovered_mistake_book_entries_for_session(
        completed_session["id"]
    )

    st.subheader("Recovered from Mistake Book in this quiz")

    if not recovered_entries:
        st.info("No entries were answered correctly in this Mistake Book quiz, so there is nothing ready to remove yet.")
        return

    st.dataframe(
        [
            {
                "entry_id": row["entry_id"],
                "term": row["term"],
                "meaning": row["meaning"],
                "user_answer": row["user_answer"],
                "expected_answer": row["expected_answer"],
                "mistake_book_correct_count": row["mistake_book_correct_count"],
                "recommendation": row["status"],
                "currently_in_mistake_book": row["currently_in_mistake_book"],
            }
            for row in recovered_entries
        ],
        use_container_width=True,
        hide_index=True,
    )

    active_session = get_active_quiz_session()
    if active_session is not None:
        st.warning("Finish or cancel the active quiz before modifying Mistake Book membership.")
        return

    selectable_entry_ids = [
        row["entry_id"] for row in recovered_entries if row["currently_in_mistake_book"]
    ]
    if not selectable_entry_ids:
        st.info("All recovered entries from this quiz have already been removed from Mistake Book.")
        return

    selected_entry_ids = []
    for row in recovered_entries:
        if not row["currently_in_mistake_book"]:
            st.caption(f"{row['term']} has already been removed from Mistake Book.")
            continue

        if st.checkbox(
            f"Remove {row['term']} from Mistake Book",
            key=f"recovered_remove_{completed_session['id']}_{row['entry_id']}",
        ):
            selected_entry_ids.append(row["entry_id"])

    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button("Remove Selected Recovered", disabled=not selected_entry_ids):
            removed_count = _remove_entries_from_mistake_book(selected_entry_ids)
            st.success(f"Removed {removed_count} entr{'y' if removed_count == 1 else 'ies'} from Mistake Book.")
            st.rerun()
    with action_col2:
        if st.button("Remove All Recovered"):
            removed_count = _remove_entries_from_mistake_book(selectable_entry_ids)
            st.success(f"Removed {removed_count} entr{'y' if removed_count == 1 else 'ies'} from Mistake Book.")
            st.rerun()
    with action_col3:
        if st.button("Keep All Recovered"):
            st.info("Recovered entries are kept in Mistake Book for more practice.")


def _render_mistake_book_mastery() -> None:
    st.header("Mistake Book Mastery")
    active_session = get_active_quiz_session()
    if active_session is not None:
        st.warning("Finish or cancel the active quiz before modifying Mistake Book membership.")

    candidates = get_mistake_book_mastery_candidates()
    if not candidates:
        st.info("Mistake Book has no entries yet.")
        return

    st.dataframe(
        [
            {
                "entry_id": row["entry_id"],
                "term": row["term"],
                "meaning": row["meaning"],
                "wrong_count": row["wrong_count"],
                "correct_count": row["correct_count"],
                "mistake_book_correct_count": row["mistake_book_correct_count"],
                "mistake_book_wrong_count": row["mistake_book_wrong_count"],
                "status": row["status"],
                "last_correct_at": row["last_correct_at"],
                "last_wrong_at": row["last_wrong_at"],
            }
            for row in candidates
        ],
        use_container_width=True,
        hide_index=True,
    )

    selected_entry_ids = []
    for row in candidates:
        option_label = f"{row['term']} - {row['status']}"
        if st.checkbox(
            option_label,
            key=f"mastery_remove_select_{row['entry_id']}",
            disabled=active_session is not None,
        ):
            selected_entry_ids.append(row["entry_id"])

    batch_col1, batch_col2 = st.columns(2)
    with batch_col1:
        if st.button(
            "Remove Selected from Mistake Book",
            disabled=active_session is not None or not selected_entry_ids,
        ):
            removed_count = _remove_entries_from_mistake_book(selected_entry_ids)
            st.success(f"Removed {removed_count} entr{'y' if removed_count == 1 else 'ies'} from Mistake Book.")
            st.rerun()
    with batch_col2:
        recommended_entry_ids = [
            row["entry_id"] for row in candidates if row["status"] == "Recommended to remove"
        ]
        if st.button(
            "Remove All Recommended",
            disabled=active_session is not None or not recommended_entry_ids,
        ):
            removed_count = _remove_entries_from_mistake_book(recommended_entry_ids)
            st.success(f"Removed {removed_count} recommended entr{'y' if removed_count == 1 else 'ies'} from Mistake Book.")
            st.rerun()


def _render_quiz_summary() -> None:
    completed_session = st.session_state.get("quiz_completed_session")

    if completed_session is None:
        return

    collection = get_collection_by_id(completed_session["collection_id"])
    total_items = completed_session["total_items"]
    correct_count = completed_session["correct_count"]
    wrong_count = completed_session["wrong_count"]
    accuracy = (correct_count / total_items * 100) if total_items else 0
    quiz_type_label = _quiz_type_label(completed_session["quiz_type"])

    st.header("Quiz Summary")
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Total", total_items)
    metric_col2.metric("Correct", correct_count)
    metric_col3.metric("Wrong", wrong_count)

    st.write(f"Accuracy: {accuracy:.1f}%")
    st.write(f"Collection: {collection['name'] if collection else completed_session['collection_id']}")
    if completed_session["card_number"]:
        st.write(f"Card: #{completed_session['card_number']}")
    elif completed_session["card_number"] == 0:
        st.write("Card: Random / Whole Collection")
    st.write(f"Quiz Type: {quiz_type_label}")
    st.write(f"Session Status: {completed_session.get('status', 'completed')}")
    if completed_session["quiz_type"] in {
        TEMPLATE_FIELD_SELF_GRADED,
        TEMPLATE_FIELD_MCQ,
        TEMPLATE_FIELD_MATCHING,
    }:
        template_name = st.session_state.get("template_quiz_template_name")
        rule = st.session_state.get("template_quiz_rule") or {}
        skipped_count = st.session_state.get("template_quiz_skipped_count", 0)
        if template_name:
            st.write(f"Template: {template_name}")
        if rule.get("label"):
            st.write(f"Rules: {rule['label']}")
        if rule.get("difficulty"):
            st.write(f"Difficulty: {rule['difficulty']}")
        if skipped_count:
            st.warning(f"Skipped {skipped_count} entr{'y' if skipped_count == 1 else 'ies'} because required rule fields were empty.")

    _render_mistakes_for_session(completed_session)
    _render_mistake_book_recovery_summary(completed_session)
    _render_proficient_pool_failed_summary(completed_session)

    item_logs = get_quiz_item_logs(completed_session["id"])
    if item_logs:
        st.subheader("Item Results")
        st.dataframe(
            [
                {
                    "prompt": item_log["prompt"],
                    "expected_answer": item_log["expected_answer"],
                    "user_answer": item_log["user_answer"],
                    "result": "Correct" if item_log["is_correct"] else "Wrong",
                    "answered_at": item_log["answered_at"],
                }
                for item_log in item_logs
            ],
            use_container_width=True,
            hide_index=True,
        )

    queue = _get_quiz_queue()
    if queue:
        current_queue_index = _get_quiz_queue_index()
        remaining_count = max(len(queue) - current_queue_index - 1, 0)
        st.info(f"Queued quiz progress: {current_queue_index + 1} / {len(queue)}.")
        summary_action_col1, summary_action_col2, summary_action_col3 = st.columns(3)
        with summary_action_col1:
            if st.button("Back to Today's Queue", key="back_to_today_queue_from_summary"):
                _reset_quiz_state()
                set_page_focus("Today", today_focus_reason="return_to_ordered_quiz_queue")
                st.rerun()
        with summary_action_col2:
            if st.button(
                "Start Next Queued Quiz",
                disabled=remaining_count <= 0,
                key="start_next_queued_quiz_from_summary",
                type="primary",
            ):
                _reset_quiz_state()
                if _advance_quiz_queue() and _start_current_queued_quiz():
                    st.rerun()
                st.success("Quiz queue completed.")
                st.rerun()
        with summary_action_col3:
            if st.button("Reset Quiz"):
                _reset_quiz_state()
                st.rerun()
        if remaining_count <= 0:
            if st.button("Clear Completed Quiz Queue", key="clear_completed_quiz_queue"):
                _clear_quiz_queue()
                _clear_quiz_focus()
                _reset_quiz_state()
                st.rerun()
    else:
        if st.button("Reset Quiz"):
            _reset_quiz_state()
            st.rerun()


def _render_mistake_book_quiz_controls() -> None:
    st.header("Mistake Book")
    mistake_book = get_system_collection("mistake_book")
    if mistake_book is None:
        st.info("Mistake Book does not exist yet. Wrong quiz answers will create it automatically.")
        return

    card_groups = get_card_groups_for_collection(mistake_book["id"])
    if not card_groups:
        st.info("Mistake Book has no entries yet.")
        return

    focus = _get_quiz_focus()
    focused_card_number = (
        focus["card_number"]
        if focus is not None and focus["collection_id"] == mistake_book["id"]
        else None
    )
    card_numbers = [card_group["card_number"] for card_group in card_groups]
    st.subheader("Practice Mistake Book")
    selected_card_number = st.selectbox(
        "Mistake Book Card",
        card_numbers,
        index=card_numbers.index(focused_card_number)
        if focused_card_number in card_numbers
        else 0,
        format_func=lambda card_number: f"Card #{card_number}",
        key="mistake_book_card_select",
    )

    practice_col1, practice_col2 = st.columns(2)
    with practice_col1:
        if st.button("Start Mistake Book Self-Graded"):
            if _start_quiz_from_parameters(
                mistake_book["id"],
                selected_card_number,
                "term_to_meaning",
            ):
                st.rerun()
    with practice_col2:
        if st.button("Start Mistake Drill MCQ"):
            if _start_quiz_from_parameters(
                mistake_book["id"],
                selected_card_number,
                "mixed_mcq",
            ):
                st.rerun()

    st.caption("After finishing a Mistake Book quiz, correctly answered entries appear in Quiz Summary with remove/keep actions.")


def _render_mistake_book_section() -> None:
    _render_mistake_book_quiz_controls()
    st.divider()
    _render_mistake_book_mastery()


def _remove_entries_from_proficient_pool(entry_ids: list[int]) -> int:
    return remove_entries_from_system_collection(entry_ids, "proficient_pool")


def _render_proficient_pool_random_quiz_controls() -> None:
    st.header("Proficient Pool")
    proficient_pool = get_system_collection("proficient_pool")
    if proficient_pool is None:
        st.info("Proficient Pool does not exist yet. Add entries from Entries Select Mode first.")
        return

    total_entries = int(proficient_pool.get("entry_count", 0))
    st.write(f"Entries in Proficient Pool: {total_entries}")
    if total_entries == 0:
        st.info("Proficient Pool has no entries yet.")
        return

    st.subheader("Random Quiz from Proficient Pool")
    quiz_type_labels = list(QUIZ_TYPE_OPTIONS.keys())
    focus = _get_quiz_focus()
    focused_quiz_type = (
        focus["quiz_type"]
        if focus is not None and focus["collection_id"] == proficient_pool["id"]
        else "mixed_mcq"
    )
    focused_quiz_type_label = next(
        (label for label, quiz_type in QUIZ_TYPE_OPTIONS.items() if quiz_type == focused_quiz_type),
        "Mixed Multiple Choice",
    )
    selected_quiz_type_label = st.selectbox(
        "Random Quiz Type",
        quiz_type_labels,
        index=quiz_type_labels.index(focused_quiz_type_label),
        key="proficient_random_quiz_type",
    )
    selected_quiz_type = QUIZ_TYPE_OPTIONS[selected_quiz_type_label]

    count_options = RANDOM_QUIZ_ITEM_COUNTS + ["Custom"]
    selected_count_option = st.selectbox(
        "Random Quiz Item Count",
        count_options,
        key="proficient_random_count_option",
    )
    if selected_count_option == "Custom":
        selected_item_count = st.number_input(
            "Custom item count",
            min_value=1,
            max_value=max(total_entries, 1),
            value=min(5, total_entries),
            step=1,
            key="proficient_random_custom_count",
        )
    else:
        selected_item_count = int(selected_count_option)

    if selected_item_count > total_entries:
        st.warning(f"Proficient Pool has only {total_entries} entries. Choose {total_entries} or fewer items.")

    if st.button(
        "Start Random Quiz from Proficient Pool",
        disabled=selected_item_count > total_entries,
    ):
        if _start_random_quiz_from_proficient_pool(
            selected_quiz_type,
            int(selected_item_count),
        ):
            st.rerun()


def _render_proficient_pool_audit() -> None:
    st.subheader("Proficient Pool Audit")
    rows = get_proficient_pool_audit_rows()
    if not rows:
        st.info("No Proficient Pool audit rows yet.")
        return

    st.dataframe(
        [
            {
                "entry_id": row["entry_id"],
                "term": row["term"],
                "meaning": row["meaning"],
                "correct_count": row["correct_count"],
                "wrong_count": row["wrong_count"],
                "total_attempts": row["total_attempts"],
                "accuracy_percentage": row["accuracy_percentage"],
                "in_mistake_book": row["in_mistake_book"],
                "last_proficient_pool_result": row["last_proficient_pool_result"] or "",
            }
            for row in rows
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_proficient_pool_section() -> None:
    _render_proficient_pool_random_quiz_controls()
    st.divider()
    _render_proficient_pool_audit()


def _render_proficient_pool_failed_summary(completed_session: dict) -> None:
    if not is_proficient_pool_collection(completed_session["collection_id"]):
        return

    failed_entries = get_failed_proficient_pool_entries_for_session(
        completed_session["id"]
    )
    st.subheader("Failed Proficient Pool Check")
    if not failed_entries:
        st.success("No failed entries in this Proficient Pool quiz.")
        return

    st.dataframe(
        [
            {
                "entry_id": row["entry_id"],
                "term": row["term"],
                "meaning": row["meaning"],
                "user_answer": row["user_answer"],
                "expected_answer": row["expected_answer"],
                "note": "Added to Mistake Book",
                "currently_in_proficient_pool": row["currently_in_proficient_pool"],
            }
            for row in failed_entries
        ],
        use_container_width=True,
        hide_index=True,
    )

    active_session = get_active_quiz_session()
    if active_session is not None:
        st.warning("Finish or cancel the active quiz before modifying Proficient Pool membership.")
        return

    removable_entry_ids = [
        row["entry_id"]
        for row in failed_entries
        if row["currently_in_proficient_pool"]
    ]
    if not removable_entry_ids:
        st.info("All failed entries from this quiz have already been removed from Proficient Pool.")
        return

    selected_entry_ids = []
    for row in failed_entries:
        if not row["currently_in_proficient_pool"]:
            st.caption(f"{row['term']} has already been removed from Proficient Pool.")
            continue
        if st.checkbox(
            f"Remove {row['term']} from Proficient Pool",
            key=f"failed_proficient_remove_{completed_session['id']}_{row['entry_id']}",
        ):
            selected_entry_ids.append(row["entry_id"])

    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button("Remove Selected Failed", disabled=not selected_entry_ids):
            removed_count = _remove_entries_from_proficient_pool(selected_entry_ids)
            st.success(f"Removed {removed_count} entr{'y' if removed_count == 1 else 'ies'} from Proficient Pool.")
            st.rerun()
    with action_col2:
        if st.button("Remove All Failed"):
            removed_count = _remove_entries_from_proficient_pool(removable_entry_ids)
            st.success(f"Removed {removed_count} entr{'y' if removed_count == 1 else 'ies'} from Proficient Pool.")
            st.rerun()
    with action_col3:
        if st.button("Keep All Failed"):
            st.info("Failed entries are kept in Proficient Pool and were added to Mistake Book.")


def _render_entry_quiz_performance() -> None:
    st.header("Entry Quiz Performance")
    performance_rows = get_entry_quiz_performance()

    if not performance_rows:
        st.info("No quiz performance data yet.")
        return

    st.dataframe(performance_rows, use_container_width=True, hide_index=True)


def _render_quiz_item_log_viewer() -> None:
    st.header("Quiz Item Log Viewer")
    collections = get_collections()

    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(5)
    with filter_col1:
        collection_options = [{"id": None, "name": "All Collections"}] + collections
        selected_collection = st.selectbox(
            "Filter collection",
            collection_options,
            format_func=lambda collection: collection["name"],
            key="quiz_log_collection_filter",
        )
    with filter_col2:
        card_options = [None]
        if selected_collection["id"] is not None:
            if selected_collection.get("system_type") == "proficient_pool":
                card_options.append(0)
            card_options += [
                card_group["card_number"]
                for card_group in get_card_groups_for_collection(selected_collection["id"])
            ]
        selected_card_number = st.selectbox(
            "Filter card",
            card_options,
            format_func=lambda card_number: "All Cards" if card_number is None else ("Random / Whole Collection" if card_number == 0 else f"Card #{card_number}"),
            key="quiz_log_card_filter",
        )
    with filter_col3:
        show_wrong_only = st.checkbox("Show wrong only", key="quiz_log_wrong_only")
    with filter_col4:
        selected_status = st.selectbox(
            "Filter status",
            ["All", "active", "completed", "cancelled", "abandoned"],
            key="quiz_log_status_filter",
        )
    with filter_col5:
        search = st.text_input("Search term or answer", key="quiz_log_search")

    log_rows = get_quiz_item_log_view(
        collection_id=selected_collection["id"],
        card_number=selected_card_number,
        show_wrong_only=show_wrong_only,
        search=search,
        status=selected_status,
    )

    if not log_rows:
        st.info("No quiz item logs match the current filters.")
        return

    st.dataframe(
        [
            {
                "session_id": row["session_id"],
                "collection_name": row["collection_name"],
                "card_number": "Random / Whole Collection" if row["card_number"] == 0 else row["card_number"],
                "quiz_type": row["quiz_type"],
                "session_status": row["session_status"],
                "entry_id": row["entry_id"],
                "term": row["term"],
                "prompt": row["prompt"],
                "expected_answer": row["expected_answer"],
                "user_answer": row["user_answer"],
                "is_correct": bool(row["is_correct"]),
                "answered_at": row["answered_at"],
            }
            for row in log_rows
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_quiz_reference_sections() -> None:
    st.divider()
    _render_entry_quiz_performance()
    st.divider()
    _render_quiz_item_log_viewer()


def render_quiz_page() -> None:
    st.title("Quiz")
    render_back_to_today_button("quiz_back_to_today_top")
    focus = _get_quiz_focus()
    _render_quiz_focus_banner(focus)
    section_options = ["Select Quiz", "Mistake Book", "Proficient Pool", "Logs & Performance"]
    default_section = 0
    if focus is not None:
        if focus["reason"] == "proficient_pool_has_entries":
            default_section = section_options.index("Proficient Pool")
        elif focus["reason"] == "mistake_book_has_entries":
            default_section = section_options.index("Mistake Book")

    selected_section = st.radio(
        "Quiz section",
        section_options,
        index=default_section,
        horizontal=True,
        label_visibility="collapsed",
    )

    if selected_section == "Select Quiz":
        if st.session_state.get("quiz_active_session_id"):
            _render_active_quiz()
        elif st.session_state.get("quiz_completed_session"):
            _render_quiz_summary()
        else:
            _render_quiz_setup()
    elif selected_section == "Mistake Book":
        _render_mistake_book_section()
    elif selected_section == "Proficient Pool":
        _render_proficient_pool_section()
    else:
        _render_quiz_reference_sections()


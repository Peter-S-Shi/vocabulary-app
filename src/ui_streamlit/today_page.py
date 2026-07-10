from datetime import date, datetime, timezone

import streamlit as st

from src.collections import get_card_groups_for_collection, get_collections
from src.db import get_connection
from src.learning_workflow import get_today_overview, normalize_today
from src.ui_streamlit.common import set_page_focus


def _format_accuracy(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def _display_status(status: str) -> str:
    labels = {
        "overdue": "Overdue",
        "due_today": "Due Today",
        "unscheduled": "Unscheduled",
    }
    return labels.get(status, status.replace("_", " ").title())


def _days_overdue(next_due_at: str | None, today_iso: str) -> int:
    if not next_due_at:
        return 0

    try:
        due_date = date.fromisoformat(str(next_due_at)[:10])
        today_date = date.fromisoformat(today_iso)
    except ValueError:
        return 0

    return max((today_date - due_date).days, 0)


def _save_page_focus(page: str, reason: str, success_message: str) -> None:
    set_page_focus(page, today_focus_page=page, today_focus_reason=reason)
    st.info(success_message)
    st.rerun()


def _save_review_focus(card: dict, reason: str) -> None:
    st.session_state["review_focus_collection_id"] = card["collection_id"]
    st.session_state["review_focus_card_number"] = card["card_number"]
    st.session_state["review_focus_source"] = "today"
    st.session_state["review_focus_created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    st.session_state["review_focus_return_page"] = "Today"
    st.session_state["review_focus_reason"] = reason
    st.session_state["focus_review_collection_id"] = card["collection_id"]
    st.session_state["focus_review_card_number"] = card["card_number"]
    set_page_focus("Review")
    st.info("Focused card saved. Continue on the Review page.")
    st.rerun()


def _save_quiz_focus(recommendation: dict) -> None:
    st.session_state["quiz_focus_collection_id"] = recommendation["collection_id"]
    st.session_state["quiz_focus_card_number"] = recommendation["card_number"]
    st.session_state["quiz_focus_type"] = recommendation["preferred_quiz_type"]
    st.session_state["quiz_focus_source"] = "today_daily_quiz"
    st.session_state["quiz_focus_reason"] = recommendation["reason"]
    st.session_state["quiz_focus_title"] = recommendation["title"]
    st.session_state["quiz_focus_created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    st.session_state["focus_quiz_collection_id"] = recommendation["collection_id"]
    st.session_state["focus_quiz_card_number"] = recommendation["card_number"]
    st.session_state["focus_quiz_source"] = recommendation["reason"]
    set_page_focus("Quiz")
    st.info("Quiz focus saved. Continue on the Quiz page.")
    st.rerun()


def _save_ordered_review_quiz_queue(due_cards: list[dict]) -> None:
    quiz_queue = [
        {
            "collection_id": card["collection_id"],
            "collection_name": card["collection_name"],
            "card_number": card["card_number"],
            "entry_count": card["entry_count"],
            "preferred_quiz_type": "mixed_mcq",
            "reason": card["status"],
            "title": f"{card['collection_name']} / Card #{card['card_number']}",
        }
        for card in due_cards
    ]
    first_item = quiz_queue[0]
    st.session_state["quiz_queue"] = quiz_queue
    st.session_state["quiz_queue_index"] = 0
    st.session_state["quiz_queue_source"] = "today_due_review_cards"
    st.session_state["quiz_queue_created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    st.session_state["quiz_focus_collection_id"] = first_item["collection_id"]
    st.session_state["quiz_focus_card_number"] = first_item["card_number"]
    st.session_state["quiz_focus_type"] = first_item["preferred_quiz_type"]
    st.session_state["quiz_focus_source"] = "today_ordered_quiz_queue"
    st.session_state["quiz_focus_reason"] = first_item["reason"]
    st.session_state["quiz_focus_title"] = first_item["title"]
    st.session_state["quiz_focus_created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    st.session_state["focus_quiz_collection_id"] = first_item["collection_id"]
    st.session_state["focus_quiz_card_number"] = first_item["card_number"]
    st.session_state["focus_quiz_source"] = first_item["reason"]
    set_page_focus("Quiz")
    st.info("Today's due-card quiz queue is ready. Continue on the Quiz page.")
    st.rerun()


def _render_focus_metrics(overview: dict) -> None:
    workload = overview["review_workload"]
    special_collections = overview["special_collections"]
    quiz_activity = overview["quiz_activity"]
    review_activity = overview["review_activity"]

    metric_cols = st.columns(4)
    metric_cols[0].metric("Due / Overdue Cards", workload["total_due_cards"])
    metric_cols[1].metric("Due Entries", workload["estimated_due_entries"])
    metric_cols[2].metric(
        "Mistake Book",
        special_collections["mistake_book"]["entry_count"],
    )
    metric_cols[3].metric(
        "Proficient Pool",
        special_collections["proficient_pool"]["entry_count"],
    )

    activity_cols = st.columns(3)
    activity_cols[0].metric("Quiz Items Today", quiz_activity["item_attempts"])
    activity_cols[1].metric("Accuracy Today", _format_accuracy(quiz_activity["accuracy"]))
    activity_cols[2].metric("Reviewed Cards Today", review_activity["reviewed_cards"])


def _render_recommendations(overview: dict) -> None:
    recommendations = overview["recommendations"]

    st.header("Recommended Next Action")
    if not recommendations:
        st.info("No recommendation is available yet.")
        return

    primary = recommendations[0]
    st.subheader(primary["title"])
    st.write(primary["description"])
    st.caption(primary["action_hint"])

    target_page = primary.get("target_page")
    if target_page:
        if st.button(f"Save focus for {target_page}", key="today_primary_focus"):
            _save_page_focus(
                target_page,
                primary["kind"],
                f"Open the {target_page} page from the sidebar. Today's focus has been saved.",
            )

    secondary_recommendations = recommendations[1:]
    if secondary_recommendations:
        with st.expander("Other suggestions"):
            for recommendation in secondary_recommendations:
                st.write(f"**{recommendation['title']}**")
                st.caption(recommendation["description"])


def _render_today_review(overview: dict) -> None:
    today_iso = overview["today"]
    workload = overview["review_workload"]
    review_activity = overview["review_activity"]
    due_cards = overview["due_review_cards"]

    st.header("Today's Review")
    _render_active_ordered_quiz_queue()

    metric_cols = st.columns(5)
    metric_cols[0].metric("Overdue Cards", workload["overdue_cards"])
    metric_cols[1].metric("Due Today", workload["due_today_cards"])
    metric_cols[2].metric("Due Entries", workload["estimated_due_entries"])
    metric_cols[3].metric("Reviewed Cards", review_activity["reviewed_cards"])
    metric_cols[4].metric("Reviewed Entries", review_activity["reviewed_entries"])

    if not due_cards:
        st.info("No review cards due today.")
        _render_no_due_review_suggestions(overview)
        if st.button("Save Review focus", key="today_review_focus_empty"):
            _save_page_focus(
                "Review",
                "review_check",
                "Open the Review page from the sidebar whenever you want to inspect review cards.",
            )
        return

    first_card = due_cards[0]
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("Start Today's Review", key="today_start_review", type="primary"):
            _save_review_focus(first_card, first_card["status"])
    with action_col2:
        if st.button("Start Ordered Quiz Queue", key="today_start_ordered_quiz_queue"):
            _save_ordered_review_quiz_queue(due_cards)

    rows = [
        {
            "Status": _display_status(card["status"]),
            "Collection": card["collection_name"],
            "Card #": card["card_number"],
            "Entry Count": card["entry_count"],
            "Next Due": card["next_due_at"] or "",
            "Days Overdue": _days_overdue(card["next_due_at"], today_iso),
        }
        for card in due_cards
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Choose a specific card"):
        for index, card in enumerate(due_cards, start=1):
            row_cols = st.columns([3, 1, 1, 1])
            row_cols[0].write(
                f"**{_display_status(card['status'])}** - "
                f"{card['collection_name']} / Card #{card['card_number']}"
            )
            row_cols[1].write(f"{card['entry_count']} entries")
            row_cols[2].write(card["next_due_at"] or "Unscheduled")
            with row_cols[3]:
                if st.button("Review this card", key=f"today_review_card_{index}_{card['collection_id']}_{card['card_number']}"):
                    _save_review_focus(card, card["status"])

    if st.button("Save Review focus", key="today_review_focus"):
        _save_page_focus(
            "Review",
            "due_review",
            "Open the Review page from the sidebar. Today's review focus has been saved.",
        )


def _quiz_queue_item_key(item: dict) -> str:
    return f"{int(item['collection_id'])}:{int(item['card_number'])}"


def _sync_quiz_focus_to_current_queue_item() -> None:
    queue = st.session_state.get("quiz_queue", [])
    if not isinstance(queue, list) or not queue:
        return

    queue_index = int(st.session_state.get("quiz_queue_index", 0) or 0)
    queue_index = min(max(queue_index, 0), len(queue) - 1)
    st.session_state["quiz_queue_index"] = queue_index
    current_item = queue[queue_index]
    st.session_state["quiz_focus_collection_id"] = current_item["collection_id"]
    st.session_state["quiz_focus_card_number"] = current_item["card_number"]
    st.session_state["quiz_focus_type"] = current_item.get("preferred_quiz_type", "mixed_mcq")
    st.session_state["quiz_focus_source"] = "today_ordered_quiz_queue"
    st.session_state["quiz_focus_reason"] = current_item.get("reason", "queued_card")
    st.session_state["quiz_focus_title"] = current_item.get("title") or (
        f"{current_item.get('collection_name', current_item['collection_id'])} / "
        f"Card #{current_item['card_number']}"
    )
    st.session_state["focus_quiz_collection_id"] = current_item["collection_id"]
    st.session_state["focus_quiz_card_number"] = current_item["card_number"]
    st.session_state["focus_quiz_source"] = current_item.get("reason", "queued_card")


def _queue_item_from_card(collection: dict, card_group: dict, reason: str = "manual_queue_card") -> dict:
    return {
        "collection_id": collection["id"],
        "collection_name": collection["name"],
        "card_number": card_group["card_number"],
        "entry_count": len(card_group.get("entries", [])),
        "preferred_quiz_type": "mixed_mcq",
        "reason": reason,
        "title": f"{collection['name']} / Card #{card_group['card_number']}",
    }


def _get_available_queue_cards() -> list[dict]:
    cards = []
    for collection in get_collections():
        for card_group in get_card_groups_for_collection(collection["id"]):
            if not card_group.get("entries"):
                continue
            cards.append(_queue_item_from_card(collection, card_group))
    return cards


def _apply_queue_editor_changes(queue: list[dict], edited_rows: list[dict]) -> None:
    edited_by_key = {row["queue_key"]: row for row in edited_rows}
    current_index = int(st.session_state.get("quiz_queue_index", 0) or 0)
    current_index = min(max(current_index, 0), len(queue) - 1)
    current_item_key = _quiz_queue_item_key(queue[current_index])
    kept_items = []

    for original_position, item in enumerate(queue, start=1):
        item_key = _quiz_queue_item_key(item)
        row = edited_by_key.get(item_key, {})
        if row.get("remove"):
            continue
        try:
            order_value = int(row.get("order", original_position))
        except (TypeError, ValueError):
            order_value = original_position
        kept_items.append((order_value, original_position, item))

    kept_items.sort(key=lambda item_tuple: (item_tuple[0], item_tuple[1]))
    new_queue = [item_tuple[2] for item_tuple in kept_items]
    if not new_queue:
        for key in ["quiz_queue", "quiz_queue_index", "quiz_queue_source", "quiz_queue_created_at"]:
            st.session_state.pop(key, None)
        return

    st.session_state["quiz_queue"] = new_queue
    new_keys = [_quiz_queue_item_key(item) for item in new_queue]
    st.session_state["quiz_queue_index"] = (
        new_keys.index(current_item_key) if current_item_key in new_keys else 0
    )
    _sync_quiz_focus_to_current_queue_item()


def _render_queue_editor(queue: list[dict], queue_index: int) -> None:
    edited_rows = st.data_editor(
        [
            {
                "queue_key": _quiz_queue_item_key(item),
                "order": index,
                "remove": False,
                "current": index - 1 == queue_index,
                "collection": item.get("collection_name", item["collection_id"]),
                "card": item["card_number"],
                "entries": item.get("entry_count", ""),
                "quiz_type": item.get("preferred_quiz_type", "mixed_mcq"),
            }
            for index, item in enumerate(queue, start=1)
        ],
        use_container_width=True,
        hide_index=True,
        disabled=["queue_key", "current", "collection", "card", "entries", "quiz_type"],
        column_config={
            "queue_key": None,
            "order": st.column_config.NumberColumn("order", min_value=1, step=1),
            "remove": st.column_config.CheckboxColumn("remove"),
            "current": st.column_config.CheckboxColumn("current"),
        },
        key="today_quiz_queue_editor",
    )
    if st.button("Apply Queue Changes", key="today_apply_quiz_queue_changes"):
        _apply_queue_editor_changes(queue, edited_rows)
        st.rerun()


def _render_add_card_to_queue() -> None:
    available_cards = _get_available_queue_cards()
    if not available_cards:
        st.caption("No collection cards are available to add.")
        return

    existing_keys = {
        _quiz_queue_item_key(item)
        for item in st.session_state.get("quiz_queue", [])
        if isinstance(item, dict)
    }
    addable_cards = [
        card for card in available_cards if _quiz_queue_item_key(card) not in existing_keys
    ]
    if not addable_cards:
        st.caption("All available cards are already in this queue.")
        return

    selected_card = st.selectbox(
        "Add card to queue",
        addable_cards,
        format_func=lambda card: (
            f"{card['collection_name']} / Card #{card['card_number']} "
            f"({card['entry_count']} entries)"
        ),
        key="today_add_card_to_quiz_queue_select",
    )
    if st.button("Add Card to Queue", key="today_add_card_to_quiz_queue"):
        queue = list(st.session_state.get("quiz_queue", []))
        queue.append(selected_card)
        st.session_state["quiz_queue"] = queue
        _sync_quiz_focus_to_current_queue_item()
        st.rerun()


def _render_active_ordered_quiz_queue() -> None:
    queue = st.session_state.get("quiz_queue", [])
    if not isinstance(queue, list) or not queue:
        return

    queue_index = int(st.session_state.get("quiz_queue_index", 0) or 0)
    queue_index = min(max(queue_index, 0), len(queue) - 1)
    current_item = queue[queue_index]

    with st.expander("Today's Ordered Quiz Queue", expanded=True):
        st.caption(
            f"Current: {queue_index + 1} / {len(queue)} - "
            f"{current_item.get('collection_name', current_item['collection_id'])} / "
            f"Card #{current_item['card_number']}"
        )
        st.caption("Edit the order numbers to reorder cards, then apply changes. Check remove to delete a card.")
        _render_queue_editor(queue, queue_index)
        _render_add_card_to_queue()
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            if st.button("Open Quiz Queue", key="today_open_existing_quiz_queue"):
                set_page_focus("Quiz", today_focus_reason="open_ordered_quiz_queue")
                st.rerun()
        with action_col2:
            if st.button("Clear Quiz Queue", key="today_clear_existing_quiz_queue"):
                for key in [
                    "quiz_queue",
                    "quiz_queue_index",
                    "quiz_queue_source",
                    "quiz_queue_created_at",
                ]:
                    st.session_state.pop(key, None)
                st.rerun()


def _render_no_due_review_suggestions(overview: dict) -> None:
    special_collections = overview["special_collections"]
    suggestions = []

    if special_collections["mistake_book"]["entry_count"] > 0:
        suggestions.append("Practice Mistake Book from the Quiz page.")
    if special_collections["proficient_pool"]["entry_count"] > 0:
        suggestions.append("Consider a Proficient Pool audit from the Quiz page.")
    if special_collections["starred"]["entry_count"] > 0:
        suggestions.append("Review Starred entries from the Quiz page.")

    if not suggestions:
        suggestions.append("Add or organize entries when you are ready.")

    for suggestion in suggestions:
        st.caption(suggestion)


def _render_practice_suggestions(overview: dict) -> None:
    special_collections = overview["special_collections"]

    st.header("Practice Suggestions")
    mistake_book = special_collections["mistake_book"]
    proficient_pool = special_collections["proficient_pool"]
    starred = special_collections["starred"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Mistake Book")
        st.metric("Entries", mistake_book["entry_count"])
        if mistake_book["entry_count"] > 0:
            st.write(f"Mistake Book has {mistake_book['entry_count']} entries. Consider a short mistake drill.")
        else:
            st.caption("Mistake Book is empty. No mistake practice is required.")
        if st.button(
            "Open Mistake Drill",
            key="today_mistake_focus",
            disabled=mistake_book["entry_count"] == 0,
        ):
            _save_page_focus(
                "Quiz",
                "mistake_drill",
                "Open the Quiz page from the sidebar. Mistake Drill focus has been saved.",
            )

    with col2:
        st.subheader("Proficient Pool")
        st.metric("Entries", proficient_pool["entry_count"])
        if proficient_pool["entry_count"] > 0:
            st.write(
                f"Proficient Pool has {proficient_pool['entry_count']} entries. "
                "Consider a random audit when review workload is light."
            )
        else:
            st.caption(
                "Proficient Pool is optional. Add mastered entries from Entries Select Mode."
            )
        if st.button(
            "Open Random Audit",
            key="today_proficient_focus",
            disabled=proficient_pool["entry_count"] == 0,
        ):
            _save_page_focus(
                "Quiz",
                "proficient_pool_audit",
                "Open the Quiz page from the sidebar. Random Audit focus has been saved.",
            )

    with col3:
        st.subheader("Starred")
        st.metric("Entries", starred["entry_count"])
        if starred["entry_count"] > 0:
            st.write(f"Starred has {starred['entry_count']} entries. Consider focused review.")
        else:
            st.caption("No starred items yet.")
        if st.button(
            "Open Starred Review",
            key="today_starred_focus",
            disabled=starred["entry_count"] == 0,
        ):
            _save_page_focus(
                "Quiz",
                "starred_review",
                "Open the Quiz page from the sidebar. Starred focus has been saved.",
            )


def _render_daily_quiz(overview: dict) -> None:
    recommendations = overview.get("daily_quiz_recommendations", [])

    st.header("Daily Quiz")
    if not recommendations:
        st.info(
            "No quiz recommendation yet. Complete a review card, add entries to "
            "Mistake Book, Starred, or Proficient Pool, then come back here."
        )
        return

    enabled_recommendations = [
        recommendation for recommendation in recommendations if recommendation.get("enabled")
    ]
    if enabled_recommendations:
        st.caption("Pick a focused quiz source, then open Quiz from the sidebar.")
    else:
        st.info("No quiz-ready source yet.")

    for index, recommendation in enumerate(recommendations, start=1):
        with st.container():
            st.subheader(recommendation["title"])
            st.write(recommendation["description"])

            detail_parts = []
            if recommendation.get("collection_name"):
                detail_parts.append(f"Source: {recommendation['collection_name']}")
            if recommendation.get("card_number") not in (None, 0):
                detail_parts.append(f"Card #{recommendation['card_number']}")
            elif recommendation.get("card_number") == 0:
                detail_parts.append("Random / Whole Collection")
            if recommendation.get("entry_count") is not None:
                detail_parts.append(f"{recommendation['entry_count']} entries")
            if recommendation.get("preferred_quiz_type"):
                detail_parts.append(f"Suggested: {recommendation['preferred_quiz_type']}")
            if detail_parts:
                st.caption(" | ".join(detail_parts))

            if recommendation.get("enabled"):
                if st.button(
                    "Focus in Quiz Page",
                    key=f"today_daily_quiz_{index}_{recommendation['recommendation_type']}",
                ):
                    _save_quiz_focus(recommendation)
            else:
                st.caption("Add these entries to a collection before quizzing.")


def _render_activity_summary(overview: dict) -> None:
    review_activity = overview["review_activity"]
    quiz_activity = overview["quiz_activity"]
    completed_sessions = quiz_activity["completed_sessions"]
    active_sessions = quiz_activity["active_sessions"]
    cancelled_sessions = quiz_activity["cancelled_sessions"]

    st.header("Today's Activity")
    activity_cols = st.columns(4)
    activity_cols[0].metric("Reviewed Cards", review_activity["reviewed_cards"])
    activity_cols[1].metric("Reviewed Entries", review_activity["reviewed_entries"])
    activity_cols[2].metric("Quiz Sessions", completed_sessions + active_sessions + cancelled_sessions)
    activity_cols[3].metric("Quiz Items", quiz_activity["item_attempts"])

    quiz_cols = st.columns(3)
    quiz_cols[0].metric("Correct Today", quiz_activity["correct_count"])
    quiz_cols[1].metric("Wrong Today", quiz_activity["wrong_count"])
    quiz_cols[2].metric("Accuracy Today", _format_accuracy(quiz_activity["accuracy"]))

    if review_activity["reviewed_cards"] == 0 and quiz_activity["item_attempts"] == 0:
        st.info("No learning activity recorded today yet.")

    if review_activity["actions"]:
        with st.expander("Review actions today"):
            st.dataframe(
                [
                    {"Action": action, "Count": count}
                    for action, count in review_activity["actions"].items()
                ],
                use_container_width=True,
                hide_index=True,
            )

    if quiz_activity["by_quiz_type"]:
        with st.expander("Quiz activity by type"):
            st.dataframe(quiz_activity["by_quiz_type"], use_container_width=True, hide_index=True)


def _render_daily_learning_summary(overview: dict) -> None:
    summary = overview.get("today_learning_summary")
    if not summary:
        return

    review_summary = summary["review_summary"]
    quiz_summary = summary["quiz_summary"]
    mistake_summary = summary["mistake_summary"]
    proficient_summary = summary["proficient_pool_summary"]
    remaining = summary["remaining_workload"]

    st.header("Daily Learning Summary")
    st.subheader(summary["completion_status"])

    cols = st.columns(5)
    cols[0].metric("Cards Reviewed", review_summary["reviewed_cards"])
    cols[1].metric("Quiz Attempts", quiz_summary["item_attempts"])
    cols[2].metric("Wrong Today", mistake_summary["wrong_count"])
    cols[3].metric("Recovered", mistake_summary["recovered_count"])
    cols[4].metric("Remaining Due", remaining["total_due_cards"])

    review_cols = st.columns(3)
    review_cols[0].metric("Reviewed Entries", review_summary["reviewed_entries"])
    review_cols[1].metric("Collections Touched", len(review_summary["collections_touched"]))
    review_cols[2].metric("Proficient Failures", proficient_summary["failed_count"])

    if review_summary["reviewed_cards"] == 0:
        st.info("No cards reviewed yet today.")
    if quiz_summary["item_attempts"] == 0:
        st.info("No quiz completed today yet. Try a quick Mistake Drill or a quiz from today's reviewed cards.")
    if mistake_summary["wrong_count"] == 0:
        st.caption("No mistakes logged today. Nice - or maybe you have not quizzed yet.")
    if proficient_summary["failed_count"] == 0:
        st.caption("No Proficient Pool failures today.")
    if quiz_summary["active_quiz_exists"]:
        st.warning("You have an active quiz in progress.")

    st.subheader("Still To Do")
    st.write(
        f"Due cards remaining: {remaining['due_cards_remaining']} | "
        f"Overdue cards: {remaining['overdue_cards']} | "
        f"Mistake Book entries: {remaining['mistake_book_entries']} | "
        f"Active quiz: {'Yes' if remaining['active_quiz'] else 'No'}"
    )

    if review_summary["details"]:
        with st.expander("Review details"):
            st.dataframe(review_summary["details"], use_container_width=True, hide_index=True)

    if quiz_summary["session_details"]:
        with st.expander("Quiz details"):
            st.dataframe(quiz_summary["session_details"], use_container_width=True, hide_index=True)

    if mistake_summary["wrong_items"]:
        with st.expander("Mistakes today"):
            st.dataframe(mistake_summary["wrong_items"], use_container_width=True, hide_index=True)

    if mistake_summary["recovered_items"]:
        with st.expander("Mistake Book recovery signals today"):
            st.dataframe(mistake_summary["recovered_items"], use_container_width=True, hide_index=True)

    if proficient_summary["failed_items"]:
        with st.expander("Proficient Pool failed today"):
            st.dataframe(proficient_summary["failed_items"], use_container_width=True, hide_index=True)


def _render_completion_summary(overview: dict) -> None:
    summary = overview["completion_summary"]

    st.header("Daily Summary")
    st.write(f"Review status: `{summary['review_status']}`")
    st.write(f"Practice status: `{summary['practice_status']}`")
    st.caption(
        f"Remaining due cards: {summary['remaining_due_cards']} | "
        f"Quiz attempts: {summary['quiz_item_attempts']} | "
        f"Quiz accuracy: {_format_accuracy(summary['quiz_accuracy'])}"
    )


def _render_workflow_checklist() -> None:
    st.header("Workflow Checklist")
    st.write("1. Review overdue and due cards.")
    st.write("2. Practice recent mistakes.")
    st.write("3. Audit Proficient Pool if you have energy.")
    st.write("4. Add or organize new entries when needed.")
    st.write("5. Check today's summary before closing the app.")


def _render_workflow_shortcuts() -> None:
    st.header("Shortcuts")
    shortcut_cols = st.columns(4)
    with shortcut_cols[0]:
        if st.button("Open Review", key="today_shortcut_review"):
            set_page_focus("Review", today_focus_reason="manual_review_shortcut")
            st.rerun()
    with shortcut_cols[1]:
        if st.button("Open Quiz", key="today_shortcut_quiz"):
            set_page_focus("Quiz", today_focus_reason="manual_quiz_shortcut")
            st.rerun()
    with shortcut_cols[2]:
        if st.button("Review Calendar", key="today_shortcut_review_calendar"):
            set_page_focus(
                "Statistics",
                focus_statistics_tab="review_calendar",
                today_focus_reason="review_calendar",
            )
            st.rerun()
    with shortcut_cols[3]:
        if st.button("Entry Health", key="today_shortcut_entry_health"):
            set_page_focus(
                "Statistics",
                focus_statistics_tab="entry_health",
                today_focus_reason="entry_health",
            )
            st.rerun()


def _render_empty_start_message(overview: dict) -> None:
    inventory = overview["content_inventory"]

    if inventory["entry_count"] == 0:
        st.info(
            "No entries yet. Start by adding your first vocabulary entries, then "
            "organize them into collections for review and quiz."
        )
        if st.button("Open Entries", key="today_empty_open_entries"):
            set_page_focus("Entries")
            st.rerun()
    elif inventory["collection_count"] == 0:
        st.info(
            "Your entries are ready. Create a collection and add entries to it "
            "to enable card-based review and quiz."
        )
        if st.button("Open Collections", key="today_empty_open_collections"):
            set_page_focus("Collections")
            st.rerun()
    elif inventory["review_state_count"] == 0:
        st.info(
            "Collections are available, but no review cards are scheduled yet. "
            "Open Review and sync review cards when you are ready."
        )
        if st.button("Open Review", key="today_empty_open_review"):
            set_page_focus("Review")
            st.rerun()


def render_today_page() -> None:
    st.title("Today")
    st.caption(
        "Your daily learning home. Review what is due, practice weak items, "
        "and keep your learning workflow moving."
    )

    today_iso = normalize_today()
    st.write(f"Date: {today_iso}")

    try:
        with get_connection() as conn:
            overview = get_today_overview(conn, today_iso)
    except Exception as error:
        st.warning(f"Today could not load a learning overview yet: {error}")
        return

    _render_empty_start_message(overview)
    _render_focus_metrics(overview)
    _render_recommendations(overview)
    _render_today_review(overview)
    _render_daily_quiz(overview)
    _render_practice_suggestions(overview)
    _render_daily_learning_summary(overview)
    _render_workflow_shortcuts()


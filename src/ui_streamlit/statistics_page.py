from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

from src import statistics as stats
from src.db import get_connection
from src.ui_streamlit.common import render_back_to_today_button


QUIZ_TYPE_LABELS = {
    "term_to_meaning": "Term to Meaning",
    "meaning_to_term": "Meaning to Term",
    "term_to_meaning_mcq": "Term to Meaning MCQ",
    "meaning_to_term_mcq": "Meaning to Term MCQ",
    "mixed_mcq": "Mixed MCQ",
    "matching": "Matching",
    "template_field_self_graded": "Template Field Self-Graded",
}

SPECIAL_POOL_LABELS = {
    "mistake_book": "Mistake Book",
    "starred": "Starred",
    "proficient_pool": "Proficient Pool",
}

STATISTICS_FOCUS_LABELS = {
    "review_calendar": "Review Calendar",
    "entry_health": "Entry Health",
    "trends": "Trends & Analytics",
    "special_pools": "Special Pools",
    "template_french_stats": "Template & French Stats",
}


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _format_count(value) -> int:
    return _safe_int(value)


def _format_unknown(value, fallback: str = "N/A"):
    if value is None or (isinstance(value, str) and not value.strip()):
        return fallback
    return value


def _format_bool_flag(value) -> str:
    return "Yes" if bool(value) else "No"


def _format_date(value, empty: str = "N/A") -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        return empty
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    value_text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value_text).date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(value_text[:10]).isoformat()
        except ValueError:
            return "N/A"


def _display_value(value):
    if isinstance(value, bool):
        return _format_bool_flag(value)
    return _format_unknown(value)


def _quiz_type_label(value: str) -> str:
    if value in QUIZ_TYPE_LABELS:
        return QUIZ_TYPE_LABELS[value]
    return str(value or "Unknown").replace("_", " ").title()


def _system_label(row: dict) -> str:
    if row.get("system_type"):
        return SPECIAL_POOL_LABELS.get(row["system_type"], row["system_type"])
    return "System" if row.get("is_system") else "Normal"


def _render_table(rows: list[dict], empty_message: str) -> None:
    if rows:
        display_rows = [
            {column: _display_value(value) for column, value in row.items()}
            for row in rows
        ]
        st.dataframe(display_rows, width="stretch", hide_index=True)
    else:
        st.info(empty_message)


def _section_error(section_name: str, error: Exception) -> None:
    st.error(f"Could not load {section_name}.")
    st.caption(str(error))


def _render_overview_tab(conn) -> None:
    st.subheader("Overview")
    st.caption("A high-level snapshot of your vocabulary system. This view is read-only.")

    try:
        entry_stats = stats.get_entry_overview_stats(conn)
        collection_stats = stats.get_collection_overview_stats(conn)
        card_stats = stats.get_card_count_stats(conn)
        review_stats = stats.get_review_overview_stats(conn)
        quiz_stats = stats.get_quiz_overview_stats(conn)
        special_stats = stats.get_special_collection_stats(conn)
        template_usage = stats.get_template_usage_stats(conn)
    except Exception as error:
        _section_error("overview statistics", error)
        return

    if entry_stats["total_entries"] == 0:
        st.info("No entries found yet. Add entries first to see statistics.")

    st.write("Vocabulary Data")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Entries", _format_count(entry_stats["total_entries"]))
    col2.metric("Languages", _format_count(entry_stats["total_languages"]))
    col3.metric("Collections", _format_count(collection_stats["total_collections"]))
    col4.metric("Cards", _format_count(card_stats["total_cards_estimated"]))
    col5.metric("Templates", len(template_usage))

    st.write("Review Status")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Due Today", review_stats["due_today_count"])
    col2.metric("Overdue", review_stats["overdue_count"])
    col3.metric("Next 7 Days", review_stats["upcoming_7_days_count"])
    col4.metric("Unscheduled", review_stats["unscheduled_count"])

    st.write("Quiz Status")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sessions", quiz_stats["total_sessions"])
    col2.metric("Completed", quiz_stats["completed_sessions"])
    col3.metric("Attempts", quiz_stats["total_item_attempts"])
    col4.metric("Accuracy", _format_percent(quiz_stats["overall_accuracy"]))

    st.write("Special Pools")
    col1, col2, col3 = st.columns(3)
    col1.metric("Mistake Book", special_stats["mistake_book"]["entry_count"])
    col2.metric("Starred", special_stats["starred"]["entry_count"])
    col3.metric("Proficient Pool", special_stats["proficient_pool"]["entry_count"])


def _render_entries_templates_tab(conn) -> None:
    st.subheader("Entries & Templates")
    st.caption("See high-level entry distribution and template usage. This view is read-only.")

    try:
        entry_stats = stats.get_entry_overview_stats(conn)
        template_usage = stats.get_template_usage_stats(conn)
    except Exception as error:
        _section_error("entry and template statistics", error)
        return

    if entry_stats["total_entries"] == 0:
        st.info("No entries found yet. Add entries first to see statistics.")
    if not template_usage:
        st.info("No templates found yet.")

    st.write("Entries by Language")
    _render_table(entry_stats["by_language"], "No language statistics yet.")

    st.write("Entries by Explanation Language")
    _render_table(
        entry_stats["by_explanation_language"],
        "No explanation-language statistics yet.",
    )

    status_col, type_col = st.columns(2)
    with status_col:
        st.write("Entries by Status")
        _render_table(entry_stats["by_status"], "No status statistics yet.")
    with type_col:
        st.write("Entries by Type")
        _render_table(entry_stats["by_entry_type"], "No entry-type statistics yet.")

    st.write("Entries by Template")
    template_rows = [
        {
            "template_id": row.get("template_id"),
            "template_name": row.get("template_name"),
            "template_type": row.get("template_type"),
            "language": row.get("language", ""),
            "system": _format_bool_flag(row.get("is_system")),
            "entry_count": row.get("entry_count", row.get("count", 0)),
        }
        for row in template_usage or entry_stats["by_template"]
    ]
    _render_table(template_rows, "No template usage statistics yet.")


def _review_card_display_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "date": _format_date(row.get("date") or row.get("due_date")),
            "collection": row.get("collection_name"),
            "card": f"#{row.get('card_number')}",
            "entries": row.get("entry_count"),
            "status": row.get("status"),
            "review_count": row.get("review_count"),
            "interval_days": row.get("current_interval_days"),
            "next_due_at": _format_date(row.get("next_due_at")),
        }
        for row in rows
    ]


def _range_dates(selected_range: str, selected_date: date) -> tuple[date, date]:
    today = date.today()
    if selected_range == "Today":
        return today, today
    if selected_range == "Next 7 days":
        return today, today + timedelta(days=7)
    if selected_range == "Next 14 days":
        return today, today + timedelta(days=14)
    if selected_range == "Next 30 days":
        return today, today + timedelta(days=30)
    if selected_range == "This month":
        start_date = selected_date.replace(day=1)
        if selected_date.month == 12:
            next_month = selected_date.replace(year=selected_date.year + 1, month=1, day=1)
        else:
            next_month = selected_date.replace(month=selected_date.month + 1, day=1)
        return start_date, next_month - timedelta(days=1)
    return selected_date, selected_date


def _calendar_summary_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "date": _format_date(row.get("date")),
            "due_cards": row.get("due_card_count", row.get("card_count", 0)),
            "due_entries": row.get("due_entry_count", row.get("entry_count", 0)),
            "overdue_cards": row.get("overdue_card_count", 0),
        }
        for row in rows
    ]


def _analytics_range(selected_range: str) -> tuple[date, date]:
    today = date.today()
    if selected_range == "Last 7 days":
        return today - timedelta(days=6), today
    if selected_range == "Last 90 days":
        return today - timedelta(days=89), today
    return today - timedelta(days=29), today


def _trend_quiz_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "date": _format_date(row.get("date")),
            "total_items": row.get("total_items"),
            "correct": row.get("correct_count"),
            "wrong": row.get("wrong_count"),
            "accuracy": _format_percent(row.get("accuracy")),
        }
        for row in rows
    ]


def _trend_review_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "date": _format_date(row.get("date")),
            "reviewed_cards": row.get("reviewed_card_count"),
            "reviewed_entries": row.get("reviewed_entry_count"),
        }
        for row in rows
    ]


def _performance_rows(rows: list[dict], label_key: str, label_name: str) -> list[dict]:
    return [
        {
            label_name: row.get(label_key),
            "total_items": row.get("total_items"),
            "correct": row.get("correct_count"),
            "wrong": row.get("wrong_count"),
            "accuracy": _format_percent(row.get("accuracy")),
        }
        for row in rows
    ]


def _chart_rows(rows: list[dict], value_keys: list[str]) -> list[dict]:
    return [
        {"date": row.get("date"), **{key: row.get(key) for key in value_keys}}
        for row in rows
    ]


def _render_collections_review_tab(conn) -> None:
    st.subheader("Collections & Review")
    st.caption("Review collection sizes, card counts, and current schedule status. This view is read-only.")

    try:
        collection_sizes = stats.get_collection_size_stats(conn)
        review_stats = stats.get_review_overview_stats(conn)
        due_stats = stats.get_due_review_stats(conn)
        upcoming_cards = stats.get_upcoming_review_cards(conn, days=7)
    except Exception as error:
        _section_error("collection and review statistics", error)
        return

    if not collection_sizes:
        st.info("No collections found yet. Create collections to see collection statistics.")
    if review_stats["total_review_states"] == 0:
        st.info("No review schedule data found yet. Review states will appear after collections/cards are synced.")

    st.write("Collection Sizes")
    collection_rows = [
        {
            "collection_id": row.get("collection_id"),
            "collection": row.get("collection_name"),
            "type": _system_label(row),
            "entries": row.get("entry_count"),
            "card_size": row.get("card_size"),
            "estimated_cards": row.get("estimated_card_count"),
            "review_states": row.get("review_state_count"),
        }
        for row in collection_sizes
    ]
    _render_table(collection_rows, "No collections yet.")

    st.write("Review Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Review States", review_stats["total_review_states"])
    col2.metric("Due Today", review_stats["due_today_count"])
    col3.metric("Overdue", review_stats["overdue_count"])
    col4.metric("Next 7 Days", review_stats["upcoming_7_days_count"])
    col5.metric("Next 30 Days", review_stats["upcoming_30_days_count"])

    due_col, overdue_col = st.columns(2)
    with due_col:
        st.write("Cards Due Today")
        _render_table(
            _review_card_display_rows(due_stats["due_today"]),
            "No review cards are due today.",
        )
    with overdue_col:
        st.write("Overdue Cards")
        _render_table(
            _review_card_display_rows(due_stats["overdue"]),
            "No overdue review cards.",
        )

    st.write("Upcoming Review Cards - Next 7 Days")
    _render_table(
        _review_card_display_rows(upcoming_cards),
        "No scheduled review cards in the next 7 days.",
    )
    st.info("Open the Review Calendar tab for date selection and range-based schedule details.")


def _render_quiz_performance_tab(conn) -> None:
    st.subheader("Quiz Performance")
    st.caption("Review overall quiz results by quiz type and collection. This view is read-only.")

    try:
        quiz_stats = stats.get_quiz_overview_stats(conn)
        by_type = stats.get_quiz_accuracy_by_type(conn)
        by_collection = stats.get_quiz_accuracy_by_collection(conn)
    except Exception as error:
        _section_error("quiz performance statistics", error)
        return

    if quiz_stats["total_item_attempts"] == 0:
        st.info("No quiz activity found yet.")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Sessions", quiz_stats["total_sessions"])
    col2.metric("Completed", quiz_stats["completed_sessions"])
    col3.metric("Attempts", quiz_stats["total_item_attempts"])
    col4.metric("Correct", quiz_stats["correct_items"])
    col5.metric("Wrong", quiz_stats["wrong_items"])
    col6.metric("Accuracy", _format_percent(quiz_stats["overall_accuracy"]))

    st.write("Accuracy by Quiz Type")
    type_rows = [
        {
            "quiz_type": _quiz_type_label(row.get("quiz_type")),
            "attempts": row.get("attempts"),
            "correct": row.get("correct"),
            "wrong": row.get("wrong"),
            "accuracy": _format_percent(row.get("accuracy")),
        }
        for row in by_type
    ]
    _render_table(type_rows, "No quiz data yet. Complete a quiz session to see performance statistics.")

    st.write("Accuracy by Collection")
    collection_rows = [
        {
            "collection_id": row.get("collection_id"),
            "collection": row.get("collection_name"),
            "attempts": row.get("attempts"),
            "correct": row.get("correct"),
            "wrong": row.get("wrong"),
            "accuracy": _format_percent(row.get("accuracy")),
        }
        for row in by_collection
    ]
    _render_table(collection_rows, "No collection-level quiz statistics yet.")


def _render_special_pools_tab(conn) -> None:
    st.subheader("Special Pools")
    st.caption("Monitor Mistake Book, Starred, and Proficient Pool membership. This view is read-only.")

    try:
        special_stats = stats.get_special_collection_stats(conn)
        audit_stats = stats.get_proficient_pool_audit_stats(conn)
        proficient_risk_count = len(stats.get_proficient_risk_entries(conn))
    except Exception as error:
        _section_error("special pool statistics", error)
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Mistake Book", special_stats["mistake_book"]["entry_count"])
    col2.metric("Starred", special_stats["starred"]["entry_count"])
    col3.metric("Proficient Pool", special_stats["proficient_pool"]["entry_count"])
    col4.metric("Also in Mistake Book", audit_stats["also_in_mistake_book_count"])
    col5.metric("Proficient Risk", proficient_risk_count)

    pool_rows = [
        {
            "pool": SPECIAL_POOL_LABELS[system_type],
            "collection_id": pool_data.get("collection_id"),
            "name": pool_data.get("name"),
            "entry_count": pool_data.get("entry_count"),
        }
        for system_type, pool_data in special_stats.items()
    ]
    _render_table(pool_rows, "No special pool statistics yet.")
    st.caption("This page is read-only. Manage special pool membership from Entries, Collections, or Quiz flows.")


def _render_review_calendar_tab(conn) -> None:
    st.subheader("Review Calendar")
    st.caption("See which collection cards are scheduled for review on each date. This view is read-only.")

    try:
        today = date.today()
        control_col1, control_col2 = st.columns([1, 1])
        with control_col1:
            selected_date = st.date_input(
                "Selected Date",
                value=today,
                key="statistics_review_calendar_selected_date",
            )
        with control_col2:
            selected_range = st.selectbox(
                "Quick Range",
                ["Today", "Next 7 days", "Next 14 days", "Next 30 days", "This month"],
                index=1,
                key="statistics_review_calendar_range",
            )

        range_start, range_end = _range_dates(selected_range, selected_date)
        selected_date_cards = stats.get_review_cards_for_date(conn, selected_date)
        range_summary = stats.get_review_calendar_summary(conn, range_start, range_end)
        range_cards = stats.get_review_cards_between_dates(conn, range_start, range_end)
        overdue_cards = stats.get_overdue_review_cards(conn, today)
    except Exception as error:
        _section_error("review calendar", error)
        return

    selected_due_entries = sum(_safe_int(row.get("entry_count")) for row in selected_date_cards)
    selected_collections = len({row.get("collection_id") for row in selected_date_cards if row.get("collection_id") is not None})

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Due Cards", len(selected_date_cards))
    metric_col2.metric("Due Entries", selected_due_entries)
    metric_col3.metric("Overdue Cards", len(overdue_cards))
    metric_col4.metric("Collections", selected_collections)

    st.write(f"Selected Date Detail - {selected_date.isoformat()}")
    _render_table(
        _review_card_display_rows(selected_date_cards),
        "No review cards scheduled for this date.",
    )

    st.write(f"Upcoming Workload - {range_start.isoformat()} to {range_end.isoformat()}")
    _render_table(
        _calendar_summary_rows(range_summary),
        "No review workload in the selected range.",
    )

    with st.expander("Scheduled Cards in Selected Range", expanded=False):
        _render_table(
            _review_card_display_rows(range_cards),
            "No scheduled cards in the selected range.",
        )

    st.write("Overdue Review Cards")
    if overdue_cards:
        st.warning(f"{len(overdue_cards)} review card{' is' if len(overdue_cards) == 1 else 's are'} overdue. This calendar does not reschedule them automatically.")
    _render_table(
        _review_card_display_rows(overdue_cards),
        "No overdue review cards.",
    )


def _render_trends_analytics_tab(conn) -> None:
    st.subheader("Trends & Analytics")
    st.caption("Track quiz accuracy, review activity, and recent learning momentum over time. This view is read-only.")

    range_col1, range_col2, range_col3 = st.columns([1, 1, 1])
    with range_col1:
        selected_range = st.selectbox(
            "Date Range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "Custom range"],
            index=1,
            key="statistics_trends_range",
        )

    if selected_range == "Custom range":
        default_start, default_end = _analytics_range("Last 30 days")
        with range_col2:
            start_date = st.date_input("Start Date", value=default_start, key="statistics_trends_start")
        with range_col3:
            end_date = st.date_input("End Date", value=default_end, key="statistics_trends_end")
        if end_date < start_date:
            st.warning("End Date must be on or after Start Date.")
            return
    else:
        start_date, end_date = _analytics_range(selected_range)
        with range_col2:
            st.metric("Start", start_date.isoformat())
        with range_col3:
            st.metric("End", end_date.isoformat())

    days = (end_date - start_date).days + 1

    try:
        momentum = stats.get_recent_learning_momentum(conn, days=days)
        quiz_trend = stats.get_quiz_activity_trend(conn, start_date, end_date)
        review_trend = stats.get_review_activity_trend(conn, start_date, end_date)
        quiz_type_performance = stats.get_quiz_type_performance(conn, start_date, end_date)
        collection_performance = stats.get_collection_quiz_performance(conn, start_date, end_date)
        review_actions = stats.get_review_action_distribution(conn, start_date, end_date)
        template_performance = stats.get_template_quiz_performance(conn, start_date, end_date)
    except Exception as error:
        _section_error("trend analytics", error)
        return

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
    metric_col1.metric("Quiz Items", momentum["quiz_items_answered"])
    metric_col2.metric("Quiz Accuracy", _format_percent(momentum["quiz_accuracy"]))
    metric_col3.metric("Reviewed Cards", momentum["reviewed_cards"])
    metric_col4.metric("Reviewed Entries", momentum["reviewed_entries"])
    metric_col5.metric("Active Days", momentum["active_days"])

    st.write("Quiz Activity Trend")
    active_quiz_rows = [row for row in quiz_trend if _safe_int(row.get("total_items")) > 0]
    if active_quiz_rows:
        st.bar_chart(_chart_rows(quiz_trend, ["total_items", "correct_count", "wrong_count"]), x="date", y=["total_items", "correct_count", "wrong_count"])
        st.line_chart(_chart_rows(quiz_trend, ["accuracy"]), x="date", y="accuracy")
    _render_table(
        _trend_quiz_rows(quiz_trend),
        "No quiz activity found in this date range.",
    )

    st.write("Review Activity Trend")
    active_review_rows = [row for row in review_trend if _safe_int(row.get("reviewed_card_count")) > 0]
    if active_review_rows:
        st.bar_chart(_chart_rows(review_trend, ["reviewed_card_count", "reviewed_entry_count"]), x="date", y=["reviewed_card_count", "reviewed_entry_count"])
    _render_table(
        _trend_review_rows(review_trend),
        "No review activity found in this date range.",
    )

    st.write("Quiz Type Performance")
    quiz_type_rows = [
        {
            "quiz_type": _quiz_type_label(row.get("quiz_type")),
            "total_items": row.get("total_items"),
            "correct": row.get("correct_count"),
            "wrong": row.get("wrong_count"),
            "accuracy": _format_percent(row.get("accuracy")),
        }
        for row in quiz_type_performance
    ]
    _render_table(
        quiz_type_rows,
        "No quiz type performance found in this date range.",
    )

    st.write("Collection Quiz Performance")
    collection_rows = [
        {
            "collection_id": row.get("collection_id"),
            "collection": row.get("collection_name"),
            "total_items": row.get("total_items"),
            "correct": row.get("correct_count"),
            "wrong": row.get("wrong_count"),
            "accuracy": _format_percent(row.get("accuracy")),
        }
        for row in collection_performance
    ]
    _render_table(
        collection_rows,
        "No collection quiz performance found in this date range.",
    )

    st.write("Review Action Distribution")
    _render_table(
        review_actions,
        "No review actions found in this date range.",
    )

    st.write("Template Quiz Performance")
    template_rows = [
        {
            "template_id": row.get("template_id"),
            "template": row.get("template_name"),
            "total_items": row.get("total_items"),
            "correct": row.get("correct_count"),
            "wrong": row.get("wrong_count"),
            "accuracy": _format_percent(row.get("accuracy")),
        }
        for row in template_performance
    ]
    _render_table(
        template_rows,
        "No template-level quiz performance found in this date range.",
    )



def _date_display(value) -> str:
    return _format_date(value, empty="Never")


def _flags_display(row: dict) -> str:
    flags = []
    if row.get("in_mistake_book"):
        flags.append("Mistake Book")
    if row.get("in_starred"):
        flags.append("Starred")
    if row.get("in_proficient_pool"):
        flags.append("Proficient Pool")
    return "; ".join(flags)


def _entry_health_common_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "entry_id": row.get("entry_id"),
            "term": row.get("term"),
            "meaning": row.get("meaning"),
            "language": row.get("language"),
            "template": row.get("template_name"),
            "attempts": row.get("attempt_count"),
            "correct": row.get("correct_count"),
            "wrong": row.get("wrong_count"),
            "accuracy": _format_percent(row.get("accuracy")),
            "last_quizzed": _date_display(row.get("last_quizzed_at")),
            "collections": row.get("collections"),
            "flags": row.get("flags") or _flags_display(row),
            "reason": row.get("weakness_reason") or row.get("risk_reason") or row.get("recovery_reason") or "",
        }
        for row in rows
    ]


def _neglected_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "entry_id": row.get("entry_id"),
            "term": row.get("term"),
            "meaning": row.get("meaning"),
            "language": row.get("language"),
            "template": row.get("template_name"),
            "created_at": _date_display(row.get("created_at")),
            "last_quizzed": _date_display(row.get("last_quizzed_at")),
            "days_since_last_quiz": "Never" if row.get("days_since_last_quiz") is None else row.get("days_since_last_quiz"),
            "attempts": row.get("attempt_count"),
            "collections": row.get("collections"),
            "reason": row.get("neglect_reason"),
        }
        for row in rows
    ]


def _recent_health_rows(rows: list[dict], reason_key: str) -> list[dict]:
    return [
        {
            "entry_id": row.get("entry_id"),
            "term": row.get("term"),
            "meaning": row.get("meaning"),
            "language": row.get("language"),
            "template": row.get("template_name"),
            "recent_attempts": row.get("recent_attempt_count"),
            "recent_correct": row.get("recent_correct_count"),
            "recent_wrong": row.get("recent_wrong_count"),
            "recent_accuracy": _format_percent(row.get("recent_accuracy")),
            "last_quizzed": _date_display(row.get("last_quizzed_at")),
            "reason": row.get(reason_key),
        }
        for row in rows
    ]


def _strong_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "entry_id": row.get("entry_id"),
            "term": row.get("term"),
            "meaning": row.get("meaning"),
            "language": row.get("language"),
            "template": row.get("template_name"),
            "attempts": row.get("attempt_count"),
            "accuracy": _format_percent(row.get("accuracy")),
            "last_quizzed": _date_display(row.get("last_quizzed_at")),
            "collections": row.get("collections"),
            "in_proficient_pool": "Yes" if row.get("in_proficient_pool") else "No",
        }
        for row in rows
    ]


def _render_entry_health_tab(conn) -> None:
    st.subheader("Entry Health")
    st.caption("Find weak, neglected, strong, and at-risk entries based on quiz history and special collection status. This view is read-only.")

    try:
        entry_stats = stats.get_entry_overview_stats(conn)
        template_usage = stats.get_template_usage_stats(conn)
        collection_sizes = stats.get_collection_size_stats(conn)
    except Exception as error:
        _section_error("entry health filters", error)
        return

    language_options = ["All"] + [row["language"] for row in entry_stats.get("by_language", [])]
    template_options = [{"template_id": "All", "template_name": "All"}] + [
        {"template_id": row.get("template_id"), "template_name": row.get("template_name")}
        for row in template_usage
        if row.get("template_id") is not None
    ]
    collection_options = [{"collection_id": "All", "collection_name": "All"}] + [
        {"collection_id": row.get("collection_id"), "collection_name": row.get("collection_name")}
        for row in collection_sizes
    ]

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        selected_language = st.selectbox("Language", language_options, key="entry_health_language")
    with filter_col2:
        selected_template = st.selectbox(
            "Template",
            template_options,
            format_func=lambda row: row["template_name"],
            key="entry_health_template",
        )
    with filter_col3:
        selected_collection = st.selectbox(
            "Collection",
            collection_options,
            format_func=lambda row: row["collection_name"],
            key="entry_health_collection",
        )

    control_col1, control_col2, control_col3 = st.columns(3)
    with control_col1:
        min_attempts = st.number_input("Min Attempts", min_value=0, max_value=20, value=2, step=1, key="entry_health_min_attempts")
    with control_col2:
        weak_threshold_percent = st.slider("Weak Accuracy Threshold", min_value=0, max_value=100, value=60, step=5, key="entry_health_weak_threshold")
    with control_col3:
        neglected_days = st.number_input("Neglected Cutoff Days", min_value=1, max_value=365, value=30, step=1, key="entry_health_neglected_days")

    language_filter = None if selected_language == "All" else selected_language
    template_filter = selected_template["template_id"]
    collection_filter = selected_collection["collection_id"]
    weak_threshold = weak_threshold_percent / 100

    try:
        overview = stats.get_entry_health_overview(
            conn,
            language=language_filter,
            template_id=template_filter,
            collection_id=collection_filter,
            min_attempts=int(min_attempts),
            weak_accuracy_threshold=weak_threshold,
            neglected_days=int(neglected_days),
        )
        weak_entries = stats.get_weak_entries(
            conn,
            language=language_filter,
            template_id=template_filter,
            collection_id=collection_filter,
            min_attempts=int(min_attempts),
            accuracy_threshold=weak_threshold,
        )
        neglected_entries = stats.get_neglected_entries(
            conn,
            language=language_filter,
            template_id=template_filter,
            collection_id=collection_filter,
            days_since_last_quiz=int(neglected_days),
        )
        risk_entries = stats.get_proficient_risk_entries(conn)
        recovery_candidates = stats.get_mistake_recovery_candidates(conn)
        strong_entries = stats.get_strong_entries(
            conn,
            language=language_filter,
            template_id=template_filter,
            collection_id=collection_filter,
        )
        collection_weakness = stats.get_collection_weakness_summary(
            conn,
            min_attempts=int(min_attempts),
            accuracy_threshold=weak_threshold,
        )
    except Exception as error:
        _section_error("entry health", error)
        return

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Total Entries", overview["total_entries"])
    metric_col2.metric("Weak", overview["weak_entries"])
    metric_col3.metric("Neglected", overview["neglected_entries"])
    metric_col4.metric("Never Quizzed", overview["never_quizzed_entries"])

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Mistake Book", overview["mistake_book_entries"])
    metric_col2.metric("Proficient Risk", overview["proficient_risk_entries"])
    metric_col3.metric("Strong", overview["strong_entries"])

    st.write("Weak Entries")
    _render_table(
        _entry_health_common_rows(weak_entries),
        "No weak entries found with the current filters.",
    )

    st.write("Neglected Entries")
    _render_table(
        _neglected_rows(neglected_entries),
        "No neglected entries found with the current filters.",
    )

    st.write("Proficient Pool Risk")
    _render_table(
        _recent_health_rows(risk_entries, "risk_reason"),
        "No Proficient Pool risk entries found.",
    )

    st.write("Mistake Book Recovery Candidates")
    _render_table(
        _recent_health_rows(recovery_candidates, "recovery_reason"),
        "No Mistake Book recovery candidates found.",
    )

    with st.expander("Strong Entries", expanded=False):
        _render_table(
            _strong_rows(strong_entries),
            "No strong entries found with the current filters.",
        )

    with st.expander("Collection Weakness Summary", expanded=False):
        _render_table(
            [
                {
                    "collection_id": row.get("collection_id"),
                    "collection": row.get("collection_name"),
                    "entries": row.get("entry_count"),
                    "weak_entries": row.get("weak_entry_count"),
                    "weak_ratio": _format_percent(row.get("weak_ratio")),
                }
                for row in collection_weakness
            ],
            "No collection weakness summary available.",
        )




def _template_stats_range(selected_range: str, custom_start: date | None = None, custom_end: date | None = None):
    today = date.today()
    if selected_range == "Last 7 days":
        return today - timedelta(days=6), today
    if selected_range == "Last 30 days":
        return today - timedelta(days=29), today
    if selected_range == "Last 90 days":
        return today - timedelta(days=89), today
    if selected_range == "Custom range":
        return custom_start, custom_end
    return None, None


def _render_template_french_stats_tab(conn) -> None:
    st.subheader("Template & French Stats")
    st.caption("Analyze template usage, completeness, and French-specific learning patterns. This view is read-only.")

    try:
        base_usage = stats.get_template_usage_stats(conn)
        entry_stats = stats.get_entry_overview_stats(conn)
    except Exception as error:
        _section_error("template statistics filters", error)
        return

    language_options = ["All"] + [row["language"] for row in entry_stats.get("by_language", []) if row.get("language")]
    template_options = [{"template_id": "All", "template_name": "All"}] + [
        {"template_id": row["template_id"], "template_name": row["template_name"]}
        for row in base_usage if row.get("template_id") is not None
    ]
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        selected_language = st.selectbox("Language", language_options, key="template_stats_language")
    with filter_col2:
        selected_template = st.selectbox("Template", template_options, format_func=lambda row: row["template_name"], key="template_stats_template")
    with filter_col3:
        selected_range = st.selectbox("Quiz Date Range", ["Last 7 days", "Last 30 days", "Last 90 days", "All time", "Custom range"], index=1, key="template_stats_range")

    custom_start = custom_end = None
    if selected_range == "Custom range":
        date_col1, date_col2 = st.columns(2)
        custom_start = date_col1.date_input("Start Date", date.today() - timedelta(days=29), key="template_stats_start")
        custom_end = date_col2.date_input("End Date", date.today(), key="template_stats_end")
        if custom_end < custom_start:
            st.warning("End Date must be on or after Start Date.")
            return

    language = None if selected_language == "All" else selected_language
    template_id = selected_template["template_id"]
    start_date, end_date = _template_stats_range(selected_range, custom_start, custom_end)

    try:
        usage = stats.get_template_usage_summary(conn, language, start_date, end_date)
        if template_id != "All":
            usage = [row for row in usage if row.get("template_id") == template_id]
        completeness = stats.get_template_completeness_summary(conn, template_id, language)
        incomplete = stats.get_incomplete_template_entries(conn, template_id, language)
        rule_performance = stats.get_template_quiz_rule_performance(conn, template_id=None if template_id == "All" else template_id, start_date=start_date, end_date=end_date)
        french = stats.get_french_template_overview(conn, start_date, end_date)
        verb_fields = stats.get_french_verb_field_performance(conn, start_date, end_date)
        adjective_fields = stats.get_french_adjective_field_performance(conn, start_date, end_date)
        noun_fields = stats.get_french_noun_field_performance(conn, start_date, end_date)
    except Exception as error:
        _section_error("template and French statistics", error)
        return

    attempts = sum(_safe_int(row.get("quiz_attempt_count")) for row in usage)
    correct = sum(_safe_int(row.get("correct_count")) for row in usage)
    french_entries = sum(_safe_int(row.get("entry_count")) for row in usage if row.get("template_type") in stats.FRENCH_TEMPLATE_TYPES)
    general_entries = sum(_safe_int(row.get("entry_count")) for row in usage if row.get("template_type") == "general")

    metric_cols = st.columns(3)
    metric_cols[0].metric("Templates", len(usage))
    metric_cols[1].metric("Template Entries", sum(_safe_int(row.get("entry_count")) for row in usage))
    metric_cols[2].metric("General Entries", general_entries)
    metric_cols = st.columns(3)
    metric_cols[0].metric("French Template Entries", french_entries)
    metric_cols[1].metric("Incomplete Entries", sum(_safe_int(row.get("incomplete_entry_count")) for row in completeness))
    metric_cols[2].metric("Template Quiz Accuracy", _format_percent(correct / attempts if attempts else None))

    st.write("Template Usage Overview")
    _render_table([{
        "template": row.get("template_name"), "type": row.get("template_type"), "language": row.get("language") or "N/A",
        "entries": row.get("entry_count"), "quiz_attempts": row.get("quiz_attempt_count"), "accuracy": _format_percent(row.get("accuracy")),
        "mistake_book": row.get("mistake_book_count"), "proficient_pool": row.get("proficient_pool_count"), "weak_entries": row.get("weak_entry_count"),
    } for row in usage], "No templates match the current filters.")

    st.write("Template Completeness")
    _render_table([{
        "template": row.get("template_name"), "entries": row.get("entry_count"), "complete": row.get("complete_entry_count"),
        "incomplete": row.get("incomplete_entry_count"), "completion_rate": _format_percent(row.get("completion_rate")),
        "commonly_missing_fields": row.get("commonly_missing_fields") or "None",
    } for row in completeness], "No template completeness data found.")

    with st.expander("Incomplete Entries", expanded=False):
        _render_table([{
            "term": row.get("term"), "meaning": row.get("meaning"), "template": row.get("template_name"),
            "missing_fields": row.get("missing_fields"), "collections": row.get("collections") or "N/A", "created_at": _date_display(row.get("created_at")),
        } for row in incomplete], "No incomplete template entries found.")

    st.write("Template Quiz Rule Performance")
    if rule_performance:
        _render_table(rule_performance, "No template quiz rule performance found.")
    else:
        st.info("Field-level rule performance is not available from the current quiz logs. Template-level performance is shown above.")

    st.write("French Overview")
    if french.get("french_template_count") == 0:
        st.info("No French template presets found yet.")
    french_cols = st.columns(4)
    french_cols[0].metric("French Entries", french["french_total_entries"])
    french_cols[1].metric("Verb Present", french["french_verb_present_entries"])
    french_cols[2].metric("Adjective Agreement", french["french_adjective_agreement_entries"])
    french_cols[3].metric("Noun Gender & Plural", french["french_noun_gender_plural_entries"])
    french_cols = st.columns(4)
    french_cols[0].metric("Quiz Attempts", french["french_template_quiz_attempts"])
    french_cols[1].metric("Quiz Accuracy", _format_percent(french["french_template_accuracy"]))
    french_cols[2].metric("Weak Entries", french["french_weak_entries"])
    french_cols[3].metric("Incomplete Entries", french["french_incomplete_entries"])

    st.info("Field-level performance requires template quiz rule metadata in quiz logs. Current data may only support template-level performance.")
    for title, rows in (("French Verb Present Field Performance", verb_fields), ("French Adjective Agreement Field Performance", adjective_fields), ("French Noun Gender & Plural Field Performance", noun_fields)):
        st.write(title)
        _render_table(rows, "Field-level performance is not available from the current quiz logs.")


def render_statistics_page() -> None:
    st.title("Statistics")
    st.caption("Learning overview for entries, reviews, quizzes, templates, and special pools.")
    render_back_to_today_button("statistics_back_to_today_top")

    focus_tab = st.session_state.get("focus_statistics_tab")
    if focus_tab:
        focus_label = STATISTICS_FOCUS_LABELS.get(focus_tab, focus_tab)
        st.info(f"Focused from Today: open the {focus_label} tab for this view.")

    conn = get_connection()
    try:
        tabs = st.tabs([
            "Overview",
            "Entries & Templates",
            "Collections & Review",
            "Quiz Performance",
            "Special Pools",
            "Review Calendar",
            "Trends & Analytics",
            "Entry Health",
            "Template & French Stats",
        ])

        with tabs[0]:
            _render_overview_tab(conn)
        with tabs[1]:
            _render_entries_templates_tab(conn)
        with tabs[2]:
            _render_collections_review_tab(conn)
        with tabs[3]:
            _render_quiz_performance_tab(conn)
        with tabs[4]:
            _render_special_pools_tab(conn)
        with tabs[5]:
            _render_review_calendar_tab(conn)
        with tabs[6]:
            _render_trends_analytics_tab(conn)
        with tabs[7]:
            _render_entry_health_tab(conn)
        with tabs[8]:
            _render_template_french_stats_tab(conn)
    finally:
        conn.close()


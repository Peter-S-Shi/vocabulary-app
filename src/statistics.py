from datetime import date, datetime, timedelta
from sqlite3 import Connection, Row
from typing import Any


SPECIAL_COLLECTIONS = {
    "mistake_book": "Mistake Book",
    "starred": "Starred",
    "proficient_pool": "Proficient Pool",
}


def table_exists(conn: Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    if not table_exists(conn, table_name):
        return False

    return any(row[1] == column_name for row in conn.execute(f"PRAGMA table_info({table_name})"))


def fetch_all_dicts(conn: Connection, query: str, params: tuple = ()) -> list[dict]:
    return [_row_to_dict(row) for row in conn.execute(query, params).fetchall()]


def fetch_one_dict(conn: Connection, query: str, params: tuple = ()) -> dict | None:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def _row_to_dict(row: Any) -> dict:
    if isinstance(row, Row):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _count(conn: Connection, table_name: str, where_sql: str = "", params: tuple = ()) -> int:
    if not table_exists(conn, table_name):
        return 0

    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name} {where_sql}", params).fetchone()
    return int(row[0] if row is not None else 0)


def _accuracy(correct: int, total: int) -> float | None:
    if total <= 0:
        return None
    return correct / total


def _to_iso_date(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    value_text = str(value).strip()
    if not value_text:
        return None

    normalized = value_text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        pass

    try:
        return date.fromisoformat(value_text[:10]).isoformat()
    except ValueError:
        return None


def _today_iso() -> str:
    return date.today().isoformat()


def _date_or_today(value: str | date | datetime | None = None) -> str:
    return _to_iso_date(value) or _today_iso()


def _date_range(start_date: str | date | datetime, end_date: str | date | datetime) -> list[str]:
    start_iso = _to_iso_date(start_date)
    end_iso = _to_iso_date(end_date)
    if start_iso is None or end_iso is None:
        return []

    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    if end < start:
        return []

    days = (end - start).days
    return [(start + timedelta(days=offset)).isoformat() for offset in range(days + 1)]


def _add_days(iso_date: str, days: int) -> str:
    return (date.fromisoformat(iso_date) + timedelta(days=days)).isoformat()


def _group_count(
    conn: Connection,
    table_name: str,
    column_name: str,
    output_key: str,
) -> list[dict]:
    if not column_exists(conn, table_name, column_name):
        return []

    return fetch_all_dicts(
        conn,
        f"""
        SELECT
            COALESCE(NULLIF(TRIM({column_name}), ''), 'Unknown') AS {output_key},
            COUNT(*) AS count
        FROM {table_name}
        GROUP BY COALESCE(NULLIF(TRIM({column_name}), ''), 'Unknown')
        ORDER BY count DESC, {output_key} ASC
        """,
    )


def get_entry_counts_by_language(conn: Connection) -> list[dict]:
    return _group_count(conn, "entries", "language", "language")


def get_entry_counts_by_status(conn: Connection) -> list[dict]:
    return _group_count(conn, "entries", "status", "status")


def get_entry_counts_by_template(conn: Connection) -> list[dict]:
    if not table_exists(conn, "entries") or not column_exists(conn, "entries", "template_id"):
        return []

    if not table_exists(conn, "entry_templates"):
        return [
            {
                "template_id": None,
                "template_name": "Unknown / General Entry",
                "template_type": "unknown",
                "is_system": 0,
                "count": _count(conn, "entries"),
            }
        ]

    return fetch_all_dicts(
        conn,
        """
        SELECT
            templates.id AS template_id,
            COALESCE(templates.name, 'Unknown / General Entry') AS template_name,
            COALESCE(templates.template_type, 'unknown') AS template_type,
            COALESCE(templates.is_system, 0) AS is_system,
            COUNT(entries.id) AS count
        FROM entries
        LEFT JOIN entry_templates AS templates
            ON templates.id = entries.template_id
        GROUP BY entries.template_id, templates.id
        ORDER BY count DESC, template_name ASC
        """,
    )


def get_entry_overview_stats(conn: Connection) -> dict:
    by_language = get_entry_counts_by_language(conn)
    by_explanation_language = _group_count(
        conn,
        "entries",
        "explanation_language",
        "explanation_language",
    )

    return {
        "total_entries": _count(conn, "entries"),
        "total_languages": len(by_language),
        "total_explanation_languages": len(by_explanation_language),
        "by_language": by_language,
        "by_explanation_language": by_explanation_language,
        "by_status": get_entry_counts_by_status(conn),
        "by_entry_type": _group_count(conn, "entries", "entry_type", "entry_type"),
        "by_template": get_entry_counts_by_template(conn),
    }


def get_collection_size_stats(conn: Connection) -> list[dict]:
    if not table_exists(conn, "collections"):
        return []

    entry_join = ""
    entry_count_expr = "0"
    if table_exists(conn, "entry_collections"):
        entry_join = """
        LEFT JOIN entry_collections
            ON entry_collections.collection_id = collections.id
        """
        entry_count_expr = "COALESCE(COUNT(entry_collections.entry_id), 0)"

    review_join = ""
    review_state_expr = "0"
    if table_exists(conn, "card_review_states"):
        review_join = """
        LEFT JOIN (
            SELECT collection_id, COUNT(*) AS review_state_count
            FROM card_review_states
            GROUP BY collection_id
        ) AS review_states
            ON review_states.collection_id = collections.id
        """
        review_state_expr = "COALESCE(review_states.review_state_count, 0)"

    return fetch_all_dicts(
        conn,
        f"""
        SELECT
            collections.id AS collection_id,
            collections.name AS collection_name,
            COALESCE(collections.is_system, 0) AS is_system,
            collections.system_type AS system_type,
            {entry_count_expr} AS entry_count,
            collections.card_size AS card_size,
            CASE
                WHEN {entry_count_expr} = 0 THEN 0
                ELSE CAST((({entry_count_expr} - 1) / collections.card_size) + 1 AS INTEGER)
            END AS estimated_card_count,
            {review_state_expr} AS review_state_count
        FROM collections
        {entry_join}
        {review_join}
        GROUP BY collections.id
        ORDER BY entry_count DESC, collections.name ASC
        """,
    )


def get_card_count_stats(conn: Connection) -> dict:
    cards_by_collection = get_collection_size_stats(conn)
    return {
        "total_cards_estimated": sum(int(row["estimated_card_count"] or 0) for row in cards_by_collection),
        "total_cards_with_review_state": _count(conn, "card_review_states"),
        "cards_by_collection": cards_by_collection,
    }


def get_special_collection_stats(conn: Connection) -> dict:
    result = {
        system_type: {
            "collection_id": None,
            "name": name,
            "entry_count": 0,
        }
        for system_type, name in SPECIAL_COLLECTIONS.items()
    }

    if not table_exists(conn, "collections"):
        return result

    entry_join = ""
    entry_count_expr = "0"
    if table_exists(conn, "entry_collections"):
        entry_join = """
        LEFT JOIN entry_collections
            ON entry_collections.collection_id = collections.id
        """
        entry_count_expr = "COALESCE(COUNT(entry_collections.entry_id), 0)"

    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT
            collections.id AS collection_id,
            collections.name AS name,
            collections.system_type AS system_type,
            {entry_count_expr} AS entry_count
        FROM collections
        {entry_join}
        WHERE collections.system_type IN ('mistake_book', 'starred', 'proficient_pool')
           OR collections.name IN ('Mistake Book', 'Starred', 'Proficient Pool')
        GROUP BY collections.id
        """,
    )

    for row in rows:
        system_type = row.get("system_type")
        if system_type not in result:
            system_type = next(
                (key for key, name in SPECIAL_COLLECTIONS.items() if name == row["name"]),
                None,
            )
        if system_type in result:
            result[system_type] = {
                "collection_id": row["collection_id"],
                "name": row["name"],
                "entry_count": int(row["entry_count"] or 0),
            }

    return result


def get_collection_overview_stats(conn: Connection) -> dict:
    collection_sizes = get_collection_size_stats(conn)
    special_collection_counts = get_special_collection_stats(conn)

    return {
        "total_collections": _count(conn, "collections"),
        "normal_collections": _count(conn, "collections", "WHERE COALESCE(is_system, 0) = 0")
        if column_exists(conn, "collections", "is_system") else _count(conn, "collections"),
        "system_collections": _count(conn, "collections", "WHERE COALESCE(is_system, 0) = 1")
        if column_exists(conn, "collections", "is_system") else 0,
        "total_entry_collection_links": _count(conn, "entry_collections"),
        "total_cards": sum(int(row["estimated_card_count"] or 0) for row in collection_sizes),
        "collection_sizes": collection_sizes,
        "special_collection_counts": special_collection_counts,
    }


def _card_entry_count_sql(conn: Connection) -> str:
    if not table_exists(conn, "entry_collections"):
        return "0"
    return """
        (
            SELECT COUNT(*)
            FROM entry_collections AS card_entries
            WHERE card_entries.collection_id = states.collection_id
              AND card_entries.position >= ((states.card_number - 1) * collections.card_size + 1)
              AND card_entries.position <= (states.card_number * collections.card_size)
        )
    """


def _review_card_rows_where(conn: Connection, where_sql: str, params: tuple = ()) -> list[dict]:
    if not table_exists(conn, "card_review_states") or not table_exists(conn, "collections"):
        return []

    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT
            DATE(states.next_due_at) AS date,
            states.collection_id AS collection_id,
            collections.name AS collection_name,
            states.card_number AS card_number,
            {_card_entry_count_sql(conn)} AS entry_count,
            states.status AS status,
            states.review_count AS review_count,
            states.current_interval_days AS current_interval_days,
            states.next_due_at AS next_due_at
        FROM card_review_states AS states
        JOIN collections
            ON collections.id = states.collection_id
        {where_sql}
        ORDER BY DATE(states.next_due_at) ASC, collections.name ASC, states.card_number ASC
        """,
        params,
    )

    today = date.fromisoformat(_today_iso())
    normalized_rows = []
    for row in rows:
        due_date = _to_iso_date(row.get("date") or row.get("next_due_at"))
        days_from_today = None
        is_overdue = False
        if due_date is not None:
            due_date_obj = date.fromisoformat(due_date)
            days_from_today = (due_date_obj - today).days
            is_overdue = days_from_today < 0

        normalized_rows.append(
            {
                **row,
                "date": due_date,
                "due_date": due_date,
                "entry_count": int(row.get("entry_count") or 0),
                "review_count": int(row.get("review_count") or 0),
                "current_interval_days": int(row.get("current_interval_days") or 0),
                "days_from_today": days_from_today,
                "is_overdue": is_overdue,
            }
        )

    return normalized_rows


def get_review_cards_by_date(conn: Connection, target_date: str | date) -> list[dict]:
    target_iso = _date_or_today(target_date)
    return _review_card_rows_where(
        conn,
        "WHERE states.next_due_at IS NOT NULL AND DATE(states.next_due_at) = DATE(?)",
        (target_iso,),
    )


def get_review_cards_for_date(conn: Connection, target_date: str | date) -> list[dict]:
    return get_review_cards_by_date(conn, target_date)


def get_review_cards_between_dates(
    conn: Connection,
    start_date: str | date,
    end_date: str | date,
) -> list[dict]:
    start_iso = _date_or_today(start_date)
    end_iso = _date_or_today(end_date)
    if end_iso < start_iso:
        start_iso, end_iso = end_iso, start_iso

    return _review_card_rows_where(
        conn,
        """
        WHERE states.next_due_at IS NOT NULL
          AND DATE(states.next_due_at) >= DATE(?)
          AND DATE(states.next_due_at) <= DATE(?)
        """,
        (start_iso, end_iso),
    )


def get_overdue_review_cards(
    conn: Connection,
    reference_date: str | date | None = None,
) -> list[dict]:
    reference_iso = _date_or_today(reference_date)
    return _review_card_rows_where(
        conn,
        "WHERE states.next_due_at IS NOT NULL AND DATE(states.next_due_at) < DATE(?)",
        (reference_iso,),
    )


def get_upcoming_review_cards(
    conn: Connection,
    days: int = 30,
    start_date: str | date | None = None,
) -> list[dict]:
    days = max(int(days), 0)
    start_iso = _date_or_today(start_date)
    end_iso = _add_days(start_iso, days)
    return _review_card_rows_where(
        conn,
        """
        WHERE states.next_due_at IS NOT NULL
          AND DATE(states.next_due_at) >= DATE(?)
          AND DATE(states.next_due_at) <= DATE(?)
        """,
        (start_iso, end_iso),
    )


def get_due_review_stats(conn: Connection, today: str | date | None = None) -> dict:
    today_iso = _date_or_today(today)
    due_today = get_review_cards_by_date(conn, today_iso)
    overdue = get_overdue_review_cards(conn, today_iso)

    return {
        "today": today_iso,
        "due_today": due_today,
        "overdue": overdue,
        "due_today_count": len(due_today),
        "overdue_count": len(overdue),
    }


def get_review_overview_stats(conn: Connection, today: str | date | None = None) -> dict:
    today_iso = _date_or_today(today)
    upcoming_7 = get_upcoming_review_cards(conn, 7, today_iso)
    upcoming_30 = get_upcoming_review_cards(conn, 30, today_iso)
    due_stats = get_due_review_stats(conn, today_iso)

    unscheduled_count = 0
    if table_exists(conn, "card_review_states") and column_exists(conn, "card_review_states", "next_due_at"):
        unscheduled_count = _count(conn, "card_review_states", "WHERE next_due_at IS NULL OR TRIM(next_due_at) = ''")

    return {
        "total_review_states": _count(conn, "card_review_states"),
        "due_today_count": due_stats["due_today_count"],
        "overdue_count": due_stats["overdue_count"],
        "upcoming_7_days_count": len(upcoming_7),
        "upcoming_30_days_count": len(upcoming_30),
        "unscheduled_count": unscheduled_count,
    }


def get_review_calendar_summary(
    conn: Connection,
    start_date: str | date,
    end_date: str | date,
) -> list[dict]:
    dates = _date_range(start_date, end_date)
    summary = {
        calendar_date: {
            "date": calendar_date,
            "card_count": 0,
            "entry_count": 0,
            "due_card_count": 0,
            "due_entry_count": 0,
            "overdue_card_count": 0,
        }
        for calendar_date in dates
    }
    if not dates:
        return []

    if table_exists(conn, "card_review_states") and table_exists(conn, "collections"):
        rows = fetch_all_dicts(
            conn,
            f"""
            SELECT
                DATE(states.next_due_at) AS date,
                COUNT(*) AS card_count,
                COALESCE(SUM({_card_entry_count_sql(conn)}), 0) AS entry_count
            FROM card_review_states AS states
            JOIN collections
                ON collections.id = states.collection_id
            WHERE states.next_due_at IS NOT NULL
              AND DATE(states.next_due_at) >= DATE(?)
              AND DATE(states.next_due_at) <= DATE(?)
            GROUP BY DATE(states.next_due_at)
            """,
            (dates[0], dates[-1]),
        )
        for row in rows:
            row_date = _to_iso_date(row.get("date"))
            if row_date in summary:
                card_count = int(row.get("card_count") or 0)
                entry_count = int(row.get("entry_count") or 0)
                summary[row_date] = {
                    "date": row_date,
                    "card_count": card_count,
                    "entry_count": entry_count,
                    "due_card_count": card_count,
                    "due_entry_count": entry_count,
                    "overdue_card_count": 0,
                }

    return [summary[calendar_date] for calendar_date in dates]


def get_review_activity_over_time(conn: Connection, days: int = 30) -> list[dict]:
    end_iso = _today_iso()
    start_iso = _add_days(end_iso, -max(int(days) - 1, 0))
    dates = _date_range(start_iso, end_iso)
    summary = {calendar_date: {"date": calendar_date, "review_count": 0} for calendar_date in dates}

    if table_exists(conn, "card_review_logs"):
        rows = fetch_all_dicts(
            conn,
            """
            SELECT DATE(reviewed_at) AS date, COUNT(*) AS review_count
            FROM card_review_logs
            WHERE DATE(reviewed_at) >= DATE(?)
              AND DATE(reviewed_at) <= DATE(?)
            GROUP BY DATE(reviewed_at)
            """,
            (start_iso, end_iso),
        )
        for row in rows:
            row_date = _to_iso_date(row.get("date"))
            if row_date in summary:
                summary[row_date]["review_count"] = int(row.get("review_count") or 0)

    return [summary[calendar_date] for calendar_date in dates]


def get_quiz_overview_stats(conn: Connection) -> dict:
    total_sessions = _count(conn, "quiz_sessions")
    completed_sessions = 0
    if column_exists(conn, "quiz_sessions", "status"):
        completed_sessions = _count(conn, "quiz_sessions", "WHERE status = 'completed'")
    elif column_exists(conn, "quiz_sessions", "completed_at"):
        completed_sessions = _count(conn, "quiz_sessions", "WHERE completed_at IS NOT NULL")

    item_counts = _quiz_item_counts(conn)
    return {
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "total_item_attempts": item_counts["attempts"],
        "correct_items": item_counts["correct"],
        "wrong_items": item_counts["wrong"],
        "overall_accuracy": _accuracy(item_counts["correct"], item_counts["attempts"]),
    }


def _quiz_item_counts(conn: Connection, extra_join_sql: str = "", where_sql: str = "", params: tuple = ()) -> dict:
    if not table_exists(conn, "quiz_item_logs"):
        return {"attempts": 0, "correct": 0, "wrong": 0}

    row = fetch_one_dict(
        conn,
        f"""
        SELECT
            COUNT(logs.id) AS attempts,
            COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
            COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong
        FROM quiz_item_logs AS logs
        {extra_join_sql}
        {where_sql}
        """,
        params,
    )
    return {
        "attempts": int(row.get("attempts") or 0),
        "correct": int(row.get("correct") or 0),
        "wrong": int(row.get("wrong") or 0),
    }


def get_quiz_accuracy_by_type(conn: Connection) -> list[dict]:
    if not table_exists(conn, "quiz_item_logs") or not table_exists(conn, "quiz_sessions"):
        return []

    rows = fetch_all_dicts(
        conn,
        """
        SELECT
            sessions.quiz_type AS quiz_type,
            COUNT(logs.id) AS attempts,
            COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
            COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong
        FROM quiz_item_logs AS logs
        JOIN quiz_sessions AS sessions
            ON sessions.id = logs.session_id
        GROUP BY sessions.quiz_type
        ORDER BY attempts DESC, sessions.quiz_type ASC
        """,
    )
    return [_with_accuracy(row) for row in rows]


def get_quiz_accuracy_by_collection(conn: Connection) -> list[dict]:
    if not table_exists(conn, "quiz_item_logs") or not table_exists(conn, "quiz_sessions"):
        return []

    collection_join = "LEFT JOIN collections ON collections.id = sessions.collection_id" if table_exists(conn, "collections") else ""
    collection_name_expr = "COALESCE(collections.name, 'Unknown Collection')" if table_exists(conn, "collections") else "'Unknown Collection'"

    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT
            sessions.collection_id AS collection_id,
            {collection_name_expr} AS collection_name,
            COUNT(logs.id) AS attempts,
            COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
            COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong
        FROM quiz_item_logs AS logs
        JOIN quiz_sessions AS sessions
            ON sessions.id = logs.session_id
        {collection_join}
        GROUP BY sessions.collection_id
        ORDER BY attempts DESC, collection_name ASC
        """,
    )
    return [_with_accuracy(row) for row in rows]


def get_quiz_accuracy_over_time(conn: Connection, days: int = 30) -> list[dict]:
    end_iso = _today_iso()
    start_iso = _add_days(end_iso, -max(int(days) - 1, 0))
    dates = _date_range(start_iso, end_iso)
    summary = {
        calendar_date: {
            "date": calendar_date,
            "attempts": 0,
            "correct": 0,
            "wrong": 0,
            "accuracy": None,
        }
        for calendar_date in dates
    }

    if table_exists(conn, "quiz_item_logs"):
        rows = fetch_all_dicts(
            conn,
            """
            SELECT
                DATE(answered_at) AS date,
                COUNT(id) AS attempts,
                COALESCE(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
                COALESCE(SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong
            FROM quiz_item_logs
            WHERE DATE(answered_at) >= DATE(?)
              AND DATE(answered_at) <= DATE(?)
            GROUP BY DATE(answered_at)
            """,
            (start_iso, end_iso),
        )
        for row in rows:
            row_date = _to_iso_date(row.get("date"))
            if row_date in summary:
                summary[row_date] = _with_accuracy({**row, "date": row_date})

    return [summary[calendar_date] for calendar_date in dates]


def _with_accuracy(row: dict) -> dict:
    attempts = int(row.get("attempts") or 0)
    correct = int(row.get("correct") or 0)
    wrong = int(row.get("wrong") or 0)
    return {
        **row,
        "attempts": attempts,
        "correct": correct,
        "wrong": wrong,
        "accuracy": _accuracy(correct, attempts),
    }



def _default_trend_range(
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    days: int = 30,
) -> tuple[str, str]:
    end_iso = _date_or_today(end_date)
    start_iso = _to_iso_date(start_date)
    if start_iso is None:
        start_iso = _add_days(end_iso, -max(int(days) - 1, 0))
    if end_iso < start_iso:
        start_iso, end_iso = end_iso, start_iso
    return start_iso, end_iso


def _date_filtered_where(
    date_column: str,
    start_date: str,
    end_date: str,
    prefix: str = "WHERE",
) -> str:
    return f"""
        {prefix} {date_column} IS NOT NULL
          AND DATE({date_column}) >= DATE(?)
          AND DATE({date_column}) <= DATE(?)
    """


def get_quiz_activity_trend(
    conn: Connection,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    group_by: str = "day",
) -> list[dict]:
    del group_by
    start_iso, end_iso = _default_trend_range(start_date, end_date)
    dates = _date_range(start_iso, end_iso)
    summary = {
        calendar_date: {
            "date": calendar_date,
            "total_items": 0,
            "correct_count": 0,
            "wrong_count": 0,
            "accuracy": None,
        }
        for calendar_date in dates
    }

    if table_exists(conn, "quiz_item_logs"):
        rows = fetch_all_dicts(
            conn,
            """
            SELECT
                DATE(answered_at) AS date,
                COUNT(id) AS total_items,
                COALESCE(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
                COALESCE(SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count
            FROM quiz_item_logs
            WHERE answered_at IS NOT NULL
              AND DATE(answered_at) >= DATE(?)
              AND DATE(answered_at) <= DATE(?)
            GROUP BY DATE(answered_at)
            """,
            (start_iso, end_iso),
        )
        for row in rows:
            row_date = _to_iso_date(row.get("date"))
            if row_date in summary:
                total_items = int(row.get("total_items") or 0)
                correct_count = int(row.get("correct_count") or 0)
                wrong_count = int(row.get("wrong_count") or 0)
                summary[row_date] = {
                    "date": row_date,
                    "total_items": total_items,
                    "correct_count": correct_count,
                    "wrong_count": wrong_count,
                    "accuracy": _accuracy(correct_count, total_items),
                }

    return [summary[calendar_date] for calendar_date in dates]


def get_quiz_type_performance(
    conn: Connection,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> list[dict]:
    if not table_exists(conn, "quiz_item_logs") or not table_exists(conn, "quiz_sessions"):
        return []

    start_iso, end_iso = _default_trend_range(start_date, end_date)
    rows = fetch_all_dicts(
        conn,
        """
        SELECT
            sessions.quiz_type AS quiz_type,
            COUNT(logs.id) AS total_items,
            COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
            COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count
        FROM quiz_item_logs AS logs
        JOIN quiz_sessions AS sessions
            ON sessions.id = logs.session_id
        WHERE logs.answered_at IS NOT NULL
          AND DATE(logs.answered_at) >= DATE(?)
          AND DATE(logs.answered_at) <= DATE(?)
        GROUP BY sessions.quiz_type
        ORDER BY total_items DESC, sessions.quiz_type ASC
        """,
        (start_iso, end_iso),
    )
    return [_with_total_accuracy(row) for row in rows]


def get_collection_quiz_performance(
    conn: Connection,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> list[dict]:
    if not table_exists(conn, "quiz_item_logs") or not table_exists(conn, "quiz_sessions"):
        return []

    start_iso, end_iso = _default_trend_range(start_date, end_date)
    collection_join = "LEFT JOIN collections ON collections.id = sessions.collection_id" if table_exists(conn, "collections") else ""
    collection_name_expr = "COALESCE(collections.name, '(Unknown collection)')" if table_exists(conn, "collections") else "'(Unknown collection)'"
    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT
            sessions.collection_id AS collection_id,
            {collection_name_expr} AS collection_name,
            COUNT(logs.id) AS total_items,
            COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
            COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count
        FROM quiz_item_logs AS logs
        JOIN quiz_sessions AS sessions
            ON sessions.id = logs.session_id
        {collection_join}
        WHERE logs.answered_at IS NOT NULL
          AND DATE(logs.answered_at) >= DATE(?)
          AND DATE(logs.answered_at) <= DATE(?)
        GROUP BY sessions.collection_id
        ORDER BY total_items DESC, collection_name ASC
        """,
        (start_iso, end_iso),
    )
    return [_with_total_accuracy(row) for row in rows]


def get_review_activity_trend(
    conn: Connection,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    group_by: str = "day",
) -> list[dict]:
    del group_by
    start_iso, end_iso = _default_trend_range(start_date, end_date)
    dates = _date_range(start_iso, end_iso)
    summary = {
        calendar_date: {
            "date": calendar_date,
            "reviewed_card_count": 0,
            "reviewed_entry_count": 0,
        }
        for calendar_date in dates
    }

    if table_exists(conn, "card_review_logs"):
        rows = fetch_all_dicts(
            conn,
            """
            SELECT
                DATE(reviewed_at) AS date,
                COUNT(id) AS reviewed_card_count,
                COALESCE(SUM(entry_count), 0) AS reviewed_entry_count
            FROM card_review_logs
            WHERE reviewed_at IS NOT NULL
              AND DATE(reviewed_at) >= DATE(?)
              AND DATE(reviewed_at) <= DATE(?)
            GROUP BY DATE(reviewed_at)
            """,
            (start_iso, end_iso),
        )
        for row in rows:
            row_date = _to_iso_date(row.get("date"))
            if row_date in summary:
                summary[row_date] = {
                    "date": row_date,
                    "reviewed_card_count": int(row.get("reviewed_card_count") or 0),
                    "reviewed_entry_count": int(row.get("reviewed_entry_count") or 0),
                }

    return [summary[calendar_date] for calendar_date in dates]


def get_review_action_distribution(
    conn: Connection,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> list[dict]:
    if not table_exists(conn, "card_review_logs"):
        return []

    action_column = "rating"
    if column_exists(conn, "card_review_logs", "action"):
        action_column = "action"
    elif not column_exists(conn, "card_review_logs", "rating"):
        return []

    start_iso, end_iso = _default_trend_range(start_date, end_date)
    return fetch_all_dicts(
        conn,
        f"""
        SELECT
            COALESCE(NULLIF(TRIM({action_column}), ''), 'Unknown') AS action,
            COUNT(*) AS count
        FROM card_review_logs
        WHERE reviewed_at IS NOT NULL
          AND DATE(reviewed_at) >= DATE(?)
          AND DATE(reviewed_at) <= DATE(?)
        GROUP BY COALESCE(NULLIF(TRIM({action_column}), ''), 'Unknown')
        ORDER BY count DESC, action ASC
        """,
        (start_iso, end_iso),
    )


def get_recent_learning_momentum(conn: Connection, days: int = 7) -> dict:
    days = max(int(days), 1)
    end_iso = _today_iso()
    start_iso = _add_days(end_iso, -(days - 1))
    quiz_trend = get_quiz_activity_trend(conn, start_iso, end_iso)
    review_trend = get_review_activity_trend(conn, start_iso, end_iso)

    quiz_items_answered = sum(int(row["total_items"] or 0) for row in quiz_trend)
    correct_count = sum(int(row["correct_count"] or 0) for row in quiz_trend)
    reviewed_cards = sum(int(row["reviewed_card_count"] or 0) for row in review_trend)
    reviewed_entries = sum(int(row["reviewed_entry_count"] or 0) for row in review_trend)
    active_days = len(
        {
            row["date"]
            for row in quiz_trend
            if int(row["total_items"] or 0) > 0
        }
        | {
            row["date"]
            for row in review_trend
            if int(row["reviewed_card_count"] or 0) > 0
        }
    )

    return {
        "days": days,
        "quiz_items_answered": quiz_items_answered,
        "quiz_accuracy": _accuracy(correct_count, quiz_items_answered),
        "reviewed_cards": reviewed_cards,
        "reviewed_entries": reviewed_entries,
        "active_days": active_days,
    }


def get_template_quiz_performance(
    conn: Connection,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> list[dict]:
    if not table_exists(conn, "quiz_item_logs") or not table_exists(conn, "entries"):
        return []

    start_iso, end_iso = _default_trend_range(start_date, end_date)
    template_join = ""
    template_select = "NULL AS template_id, 'Unknown / General Entry' AS template_name"
    template_group = "entries.template_id"
    if table_exists(conn, "entry_templates"):
        template_join = "LEFT JOIN entry_templates AS templates ON templates.id = entries.template_id"
        template_select = "entries.template_id AS template_id, COALESCE(templates.name, 'Unknown / General Entry') AS template_name"
        template_group = "entries.template_id, templates.name"

    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT
            {template_select},
            COUNT(logs.id) AS total_items,
            COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
            COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count
        FROM quiz_item_logs AS logs
        JOIN entries
            ON entries.id = logs.entry_id
        {template_join}
        WHERE logs.answered_at IS NOT NULL
          AND DATE(logs.answered_at) >= DATE(?)
          AND DATE(logs.answered_at) <= DATE(?)
        GROUP BY {template_group}
        ORDER BY total_items DESC, template_name ASC
        """,
        (start_iso, end_iso),
    )
    return [_with_total_accuracy(row) for row in rows]


def _with_total_accuracy(row: dict) -> dict:
    total_items = int(row.get("total_items") or 0)
    correct_count = int(row.get("correct_count") or 0)
    wrong_count = int(row.get("wrong_count") or 0)
    return {
        **row,
        "total_items": total_items,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "accuracy": _accuracy(correct_count, total_items),
    }


def _special_collection_exists_sql(system_type: str, entry_alias: str = "entries") -> str:
    fallback_name = SPECIAL_COLLECTIONS[system_type]
    return f"""
        EXISTS (
            SELECT 1
            FROM entry_collections AS special_ec
            JOIN collections AS special_collection
                ON special_collection.id = special_ec.collection_id
            WHERE special_ec.entry_id = {entry_alias}.id
              AND (
                    special_collection.system_type = '{system_type}'
                 OR special_collection.name = '{fallback_name}'
              )
        )
    """


def _entry_collection_names_sql(conn: Connection, entry_alias: str = "entries") -> str:
    if not table_exists(conn, "entry_collections") or not table_exists(conn, "collections"):
        return "''"
    return f"""
        COALESCE((
            SELECT GROUP_CONCAT(collection_names.name, '; ')
            FROM (
                SELECT collections.name AS name
                FROM entry_collections AS collection_ec
                JOIN collections
                    ON collections.id = collection_ec.collection_id
                WHERE collection_ec.entry_id = {entry_alias}.id
                ORDER BY collections.name ASC
            ) AS collection_names
        ), '')
    """


def _entry_health_filters(
    language: str | None = None,
    template_id: int | str | None = None,
    collection_id: int | str | None = None,
) -> tuple[list[str], list]:
    where_clauses = []
    params = []

    if language not in (None, "", "All"):
        where_clauses.append("entries.language = ?")
        params.append(language)

    if template_id not in (None, "", "All"):
        where_clauses.append("entries.template_id = ?")
        params.append(int(template_id))

    if collection_id not in (None, "", "All"):
        where_clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM entry_collections AS filter_ec
                WHERE filter_ec.entry_id = entries.id
                  AND filter_ec.collection_id = ?
            )
            """
        )
        params.append(int(collection_id))

    return where_clauses, params


def _date_filtered_quiz_join(start_date, end_date) -> tuple[str, list]:
    start_iso = _to_iso_date(start_date)
    end_iso = _to_iso_date(end_date)
    join_clauses = []
    params = []
    if start_iso is not None:
        join_clauses.append("DATE(logs.answered_at) >= DATE(?)")
        params.append(start_iso)
    if end_iso is not None:
        join_clauses.append("DATE(logs.answered_at) <= DATE(?)")
        params.append(end_iso)

    if not join_clauses:
        return "", []

    return " AND " + " AND ".join(join_clauses), params


def _normalize_entry_performance_row(row: dict) -> dict:
    attempt_count = int(row.get("attempt_count") or 0)
    correct_count = int(row.get("correct_count") or 0)
    wrong_count = int(row.get("wrong_count") or 0)
    return {
        **row,
        "attempt_count": attempt_count,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "accuracy": _accuracy(correct_count, attempt_count),
        "in_mistake_book": bool(row.get("in_mistake_book")),
        "in_starred": bool(row.get("in_starred")),
        "in_proficient_pool": bool(row.get("in_proficient_pool")),
    }


def get_entry_performance_summary(
    conn: Connection,
    language: str | None = None,
    template_id: int | str | None = None,
    collection_id: int | str | None = None,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    min_attempts: int = 0,
) -> list[dict]:
    if not table_exists(conn, "entries"):
        return []

    template_join = ""
    template_name_expr = "'Unknown / General Entry'"
    if table_exists(conn, "entry_templates"):
        template_join = "LEFT JOIN entry_templates AS templates ON templates.id = entries.template_id"
        template_name_expr = "COALESCE(templates.name, 'Unknown / General Entry')"

    quiz_join_filter, quiz_params = _date_filtered_quiz_join(start_date, end_date)
    collection_names_expr = _entry_collection_names_sql(conn)
    if table_exists(conn, "entry_collections") and table_exists(conn, "collections"):
        mistake_expr = _special_collection_exists_sql("mistake_book")
        starred_expr = _special_collection_exists_sql("starred")
        proficient_expr = _special_collection_exists_sql("proficient_pool")
    else:
        mistake_expr = "0"
        starred_expr = "0"
        proficient_expr = "0"

    where_clauses, filter_params = _entry_health_filters(language, template_id, collection_id)
    params = quiz_params + filter_params
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT
            entries.id AS entry_id,
            entries.term AS term,
            entries.meaning AS meaning,
            entries.language AS language,
            entries.template_id AS template_id,
            {template_name_expr} AS template_name,
            entries.created_at AS created_at,
            COUNT(logs.id) AS attempt_count,
            COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
            COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count,
            MAX(logs.answered_at) AS last_quizzed_at,
            {collection_names_expr} AS collections,
            CASE WHEN {mistake_expr} THEN 1 ELSE 0 END AS in_mistake_book,
            CASE WHEN {starred_expr} THEN 1 ELSE 0 END AS in_starred,
            CASE WHEN {proficient_expr} THEN 1 ELSE 0 END AS in_proficient_pool
        FROM entries
        {template_join}
        LEFT JOIN quiz_item_logs AS logs
            ON logs.entry_id = entries.id
           {quiz_join_filter}
        {where_sql}
        GROUP BY entries.id
        HAVING COUNT(logs.id) >= ?
        ORDER BY wrong_count DESC, attempt_count DESC, entries.term ASC
        """,
        tuple(params + [int(min_attempts)]),
    )
    return [_normalize_entry_performance_row(row) for row in rows]


def _entry_flags(row: dict) -> str:
    flags = []
    if row.get("in_mistake_book"):
        flags.append("Mistake Book")
    if row.get("in_starred"):
        flags.append("Starred")
    if row.get("in_proficient_pool"):
        flags.append("Proficient Pool")
    return "; ".join(flags)


def _weakness_reason(row: dict, min_attempts: int, accuracy_threshold: float) -> str:
    reasons = []
    if row.get("in_mistake_book"):
        reasons.append("in_mistake_book")
    if row.get("in_proficient_pool") and row.get("in_mistake_book"):
        reasons.append("proficient_but_failed")
    if int(row.get("attempt_count") or 0) == 0:
        reasons.append("never_quizzed")
    if int(row.get("wrong_count") or 0) > 0:
        reasons.append("high_wrong_count")
    if int(row.get("attempt_count") or 0) >= min_attempts:
        accuracy = row.get("accuracy")
        if accuracy is not None and accuracy <= accuracy_threshold:
            reasons.append("low_accuracy")
    return "; ".join(dict.fromkeys(reasons))


def get_weak_entries(
    conn: Connection,
    language: str | None = None,
    template_id: int | str | None = None,
    collection_id: int | str | None = None,
    min_attempts: int = 2,
    accuracy_threshold: float = 0.60,
    include_mistake_book: bool = True,
    limit: int = 100,
) -> list[dict]:
    rows = get_entry_performance_summary(conn, language, template_id, collection_id)
    weak_rows = []
    for row in rows:
        accuracy = row.get("accuracy")
        has_low_accuracy = row["attempt_count"] >= min_attempts and accuracy is not None and accuracy <= accuracy_threshold
        in_mistake_book = bool(row.get("in_mistake_book"))
        if has_low_accuracy or (include_mistake_book and in_mistake_book):
            reason = _weakness_reason(row, min_attempts, accuracy_threshold)
            weak_rows.append({**row, "weakness_reason": reason, "flags": _entry_flags(row)})

    weak_rows.sort(
        key=lambda row: (
            0 if row.get("in_mistake_book") else 1,
            999 if row.get("accuracy") is None else row["accuracy"],
            -int(row.get("wrong_count") or 0),
            row.get("last_quizzed_at") or "",
        )
    )
    return weak_rows[: int(limit)]


def get_neglected_entries(
    conn: Connection,
    language: str | None = None,
    template_id: int | str | None = None,
    collection_id: int | str | None = None,
    days_since_last_quiz: int = 30,
    include_never_quizzed: bool = True,
    limit: int = 100,
) -> list[dict]:
    rows = get_entry_performance_summary(conn, language, template_id, collection_id)
    cutoff = date.fromisoformat(_add_days(_today_iso(), -max(int(days_since_last_quiz), 0)))
    neglected_rows = []
    today = date.fromisoformat(_today_iso())

    for row in rows:
        last_quizzed_date = _to_iso_date(row.get("last_quizzed_at"))
        if last_quizzed_date is None:
            if include_never_quizzed:
                neglected_rows.append({**row, "days_since_last_quiz": None, "neglect_reason": "never_quizzed"})
            continue

        last_date = date.fromisoformat(last_quizzed_date)
        if last_date <= cutoff:
            neglected_rows.append(
                {
                    **row,
                    "days_since_last_quiz": (today - last_date).days,
                    "neglect_reason": "not_practiced_recently",
                }
            )

    neglected_rows.sort(
        key=lambda row: (
            0 if row.get("last_quizzed_at") is None else 1,
            row.get("last_quizzed_at") or "",
            row.get("created_at") or "",
        )
    )
    return neglected_rows[: int(limit)]


def get_strong_entries(
    conn: Connection,
    language: str | None = None,
    template_id: int | str | None = None,
    collection_id: int | str | None = None,
    min_attempts: int = 3,
    accuracy_threshold: float = 0.80,
    limit: int = 100,
) -> list[dict]:
    rows = get_entry_performance_summary(conn, language, template_id, collection_id)
    strong_rows = [
        {**row, "flags": _entry_flags(row)}
        for row in rows
        if row["attempt_count"] >= min_attempts
        and row.get("accuracy") is not None
        and row["accuracy"] >= accuracy_threshold
        and not row.get("in_mistake_book")
    ]
    strong_rows.sort(key=lambda row: (-(row.get("accuracy") or 0), -int(row.get("attempt_count") or 0), row.get("term") or ""))
    return strong_rows[: int(limit)]


def _recent_entry_counts(
    conn: Connection,
    entry_ids: list[int],
    recent_days: int,
) -> dict[int, dict]:
    if not entry_ids or not table_exists(conn, "quiz_item_logs"):
        return {}

    start_iso = _add_days(_today_iso(), -max(int(recent_days) - 1, 0))
    placeholders = ",".join("?" for _ in entry_ids)
    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT
            entry_id,
            COUNT(id) AS recent_attempt_count,
            COALESCE(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), 0) AS recent_correct_count,
            COALESCE(SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END), 0) AS recent_wrong_count,
            MAX(answered_at) AS last_quizzed_at
        FROM quiz_item_logs
        WHERE entry_id IN ({placeholders})
          AND answered_at IS NOT NULL
          AND DATE(answered_at) >= DATE(?)
        GROUP BY entry_id
        """,
        tuple(entry_ids + [start_iso]),
    )
    result = {}
    for row in rows:
        attempts = int(row.get("recent_attempt_count") or 0)
        correct = int(row.get("recent_correct_count") or 0)
        wrong = int(row.get("recent_wrong_count") or 0)
        result[int(row["entry_id"])] = {
            "recent_attempt_count": attempts,
            "recent_correct_count": correct,
            "recent_wrong_count": wrong,
            "recent_accuracy": _accuracy(correct, attempts),
            "last_quizzed_at": row.get("last_quizzed_at"),
        }
    return result


def get_proficient_risk_entries(
    conn: Connection,
    recent_days: int = 30,
    limit: int = 100,
) -> list[dict]:
    rows = [row for row in get_entry_performance_summary(conn) if row.get("in_proficient_pool")]
    recent_counts = _recent_entry_counts(conn, [row["entry_id"] for row in rows], recent_days)
    risk_rows = []

    for row in rows:
        recent = recent_counts.get(row["entry_id"], {
            "recent_attempt_count": 0,
            "recent_correct_count": 0,
            "recent_wrong_count": 0,
            "recent_accuracy": None,
            "last_quizzed_at": row.get("last_quizzed_at"),
        })
        reasons = []
        if row.get("in_mistake_book"):
            reasons.append("also_in_mistake_book")
        if recent["recent_wrong_count"] > 0:
            reasons.append("recent_wrong_answer")
        if recent["recent_accuracy"] is not None and recent["recent_accuracy"] < 0.8:
            reasons.append("low_recent_accuracy")
        if reasons:
            risk_rows.append({**row, **recent, "risk_reason": "; ".join(reasons)})

    risk_rows.sort(key=lambda row: (0 if row.get("in_mistake_book") else 1, -int(row.get("recent_wrong_count") or 0), row.get("last_quizzed_at") or ""))
    return risk_rows[: int(limit)]


def get_mistake_recovery_candidates(
    conn: Connection,
    recent_days: int = 30,
    min_recent_correct: int = 2,
    limit: int = 100,
) -> list[dict]:
    rows = [row for row in get_entry_performance_summary(conn) if row.get("in_mistake_book")]
    recent_counts = _recent_entry_counts(conn, [row["entry_id"] for row in rows], recent_days)
    candidates = []

    for row in rows:
        recent = recent_counts.get(row["entry_id"], {
            "recent_attempt_count": 0,
            "recent_correct_count": 0,
            "recent_wrong_count": 0,
            "recent_accuracy": None,
            "last_quizzed_at": row.get("last_quizzed_at"),
        })
        if recent["recent_correct_count"] >= min_recent_correct:
            candidates.append({**row, **recent, "recovery_reason": "recent_correct_answers"})

    candidates.sort(key=lambda row: (-int(row.get("recent_correct_count") or 0), int(row.get("recent_wrong_count") or 0), row.get("term") or ""))
    return candidates[: int(limit)]


def get_entry_health_overview(
    conn: Connection,
    language: str | None = None,
    template_id: int | str | None = None,
    collection_id: int | str | None = None,
    min_attempts: int = 2,
    weak_accuracy_threshold: float = 0.60,
    neglected_days: int = 30,
) -> dict:
    all_rows = get_entry_performance_summary(conn, language, template_id, collection_id)
    weak_entries = get_weak_entries(conn, language, template_id, collection_id, min_attempts, weak_accuracy_threshold)
    neglected_entries = get_neglected_entries(conn, language, template_id, collection_id, neglected_days)
    strong_entries = get_strong_entries(conn, language, template_id, collection_id, max(3, min_attempts), 0.80)
    special_stats = get_special_collection_stats(conn)

    return {
        "total_entries": len(all_rows),
        "weak_entries": len(weak_entries),
        "neglected_entries": len(neglected_entries),
        "strong_entries": len(strong_entries),
        "mistake_book_entries": special_stats["mistake_book"]["entry_count"],
        "proficient_risk_entries": len(get_proficient_risk_entries(conn)),
        "never_quizzed_entries": sum(1 for row in all_rows if int(row.get("attempt_count") or 0) == 0),
    }


def get_collection_weakness_summary(
    conn: Connection,
    min_attempts: int = 2,
    accuracy_threshold: float = 0.60,
) -> list[dict]:
    if not table_exists(conn, "collections") or not table_exists(conn, "entry_collections"):
        return []

    weak_entry_ids = {row["entry_id"] for row in get_weak_entries(conn, min_attempts=min_attempts, accuracy_threshold=accuracy_threshold, limit=100000)}
    collection_rows = get_collection_size_stats(conn)
    rows = []
    for collection in collection_rows:
        entry_rows = fetch_all_dicts(
            conn,
            """
            SELECT entry_id
            FROM entry_collections
            WHERE collection_id = ?
            """,
            (collection["collection_id"],),
        )
        entry_ids = {row["entry_id"] for row in entry_rows}
        weak_count = len(entry_ids & weak_entry_ids)
        entry_count = int(collection.get("entry_count") or 0)
        rows.append(
            {
                "collection_id": collection["collection_id"],
                "collection_name": collection["collection_name"],
                "entry_count": entry_count,
                "weak_entry_count": weak_count,
                "weak_ratio": _accuracy(weak_count, entry_count),
            }
        )

    rows.sort(key=lambda row: (-(row.get("weak_ratio") or 0), -int(row.get("weak_entry_count") or 0), row.get("collection_name") or ""))
    return rows

def get_proficient_pool_audit_stats(conn: Connection) -> dict:
    special_stats = get_special_collection_stats(conn)
    proficient_pool_id = special_stats["proficient_pool"]["collection_id"]
    mistake_book_id = special_stats["mistake_book"]["collection_id"]
    also_in_mistake_book_count = 0

    if proficient_pool_id is not None and mistake_book_id is not None and table_exists(conn, "entry_collections"):
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM entry_collections AS proficient
            JOIN entry_collections AS mistakes
                ON mistakes.entry_id = proficient.entry_id
            WHERE proficient.collection_id = ?
              AND mistakes.collection_id = ?
            """,
            (proficient_pool_id, mistake_book_id),
        ).fetchone()
        also_in_mistake_book_count = int(row[0] if row is not None else 0)

    return {
        "proficient_pool_count": special_stats["proficient_pool"]["entry_count"],
        "also_in_mistake_book_count": also_in_mistake_book_count,
    }


def get_template_usage_stats(conn: Connection) -> list[dict]:
    if not table_exists(conn, "entry_templates"):
        return []

    if not table_exists(conn, "entries") or not column_exists(conn, "entries", "template_id"):
        return fetch_all_dicts(
            conn,
            """
            SELECT
                templates.id AS template_id,
                templates.name AS template_name,
                templates.template_type AS template_type,
                templates.language AS language,
                templates.is_system AS is_system,
                0 AS entry_count
            FROM entry_templates AS templates
            ORDER BY templates.is_system DESC, templates.name ASC
            """,
        )

    rows = fetch_all_dicts(
        conn,
        """
        SELECT
            templates.id AS template_id,
            templates.name AS template_name,
            templates.template_type AS template_type,
            templates.language AS language,
            templates.is_system AS is_system,
            COALESCE(COUNT(entries.id), 0) AS entry_count
        FROM entry_templates AS templates
        LEFT JOIN entries
            ON entries.template_id = templates.id
        GROUP BY templates.id
        ORDER BY entry_count DESC, templates.is_system DESC, templates.name ASC
        """,
    )

    missing_count = _count(conn, "entries", "WHERE template_id IS NULL")
    if missing_count:
        rows.append(
            {
                "template_id": None,
                "template_name": "Unknown / General Entry",
                "template_type": "unknown",
                "language": None,
                "is_system": 0,
                "entry_count": missing_count,
            }
        )

    return rows


def get_template_quiz_stats(conn: Connection) -> list[dict]:
    if not table_exists(conn, "quiz_sessions") or not table_exists(conn, "quiz_item_logs"):
        return []

    if not column_exists(conn, "quiz_sessions", "quiz_type"):
        return []

    rows = fetch_all_dicts(
        conn,
        """
        SELECT
            sessions.quiz_type AS quiz_type,
            COUNT(logs.id) AS attempts,
            COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
            COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong
        FROM quiz_item_logs AS logs
        JOIN quiz_sessions AS sessions
            ON sessions.id = logs.session_id
        WHERE sessions.quiz_type = 'template_field_self_graded'
        GROUP BY sessions.quiz_type
        """,
    )

    return [
        {
            "template_type": None,
            **_with_accuracy(row),
        }
        for row in rows
    ]

FRENCH_TEMPLATE_TYPES = {
    "french_verb_present",
    "french_adjective_agreement",
    "french_noun_gender_plural",
}

FRENCH_IMPORTANT_FIELDS = {
    "french_verb_present": ("infinitive", "meaning", "je", "tu", "il_elle_on", "nous", "vous", "ils_elles"),
    "french_adjective_agreement": ("masculine_singular", "meaning", "feminine_singular", "masculine_plural", "feminine_plural"),
    "french_noun_gender_plural": ("singular", "meaning", "gender", "plural", "article"),
}


def _template_completeness_data(
    conn: Connection,
    template_id: int | str | None = None,
    language: str | None = None,
) -> tuple[list[dict], list[dict]]:
    required_tables = ("entries", "entry_templates", "entry_template_fields", "entry_field_values")
    if not all(table_exists(conn, table_name) for table_name in required_tables):
        return [], []

    clauses = []
    params: list[Any] = []
    if template_id not in (None, "", "All"):
        clauses.append("templates.id = ?")
        params.append(int(template_id))
    if language not in (None, "", "All"):
        clauses.append("templates.language = ?")
        params.append(language)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    templates = fetch_all_dicts(
        conn,
        f"""
        SELECT templates.id AS template_id, templates.name AS template_name,
               templates.template_type, templates.language
        FROM entry_templates AS templates
        {where_sql}
        ORDER BY templates.name
        """,
        tuple(params),
    )
    if not templates:
        return [], []

    template_ids = [int(row["template_id"]) for row in templates]
    placeholders = ",".join("?" for _ in template_ids)
    fields = fetch_all_dicts(
        conn,
        f"""
        SELECT id AS field_id, template_id, field_key, field_label, required, display_order
        FROM entry_template_fields
        WHERE template_id IN ({placeholders})
        ORDER BY template_id, display_order, id
        """,
        tuple(template_ids),
    )
    entry_values = fetch_all_dicts(
        conn,
        f"""
        SELECT entries.id AS entry_id, entries.term, entries.meaning, entries.created_at,
               entries.template_id, fields.field_key, field_values.field_value
        FROM entries
        LEFT JOIN entry_template_fields AS fields ON fields.template_id = entries.template_id
        LEFT JOIN entry_field_values AS field_values
          ON field_values.entry_id = entries.id AND field_values.field_id = fields.id
        WHERE entries.template_id IN ({placeholders})
        ORDER BY entries.id
        """,
        tuple(template_ids),
    )

    fields_by_template: dict[int, list[dict]] = {template_id: [] for template_id in template_ids}
    for field in fields:
        fields_by_template[int(field["template_id"])].append(field)

    template_by_id = {int(row["template_id"]): row for row in templates}
    entries_by_id: dict[int, dict] = {}
    for row in entry_values:
        entry_id = int(row["entry_id"])
        entry = entries_by_id.setdefault(entry_id, {**row, "values": {}})
        if row.get("field_key") is not None:
            entry["values"][row["field_key"]] = row.get("field_value")

    collection_names: dict[int, str] = {}
    if table_exists(conn, "entry_collections") and table_exists(conn, "collections") and entries_by_id:
        entry_ids = list(entries_by_id)
        entry_placeholders = ",".join("?" for _ in entry_ids)
        collection_rows = fetch_all_dicts(
            conn,
            f"""
            SELECT links.entry_id, GROUP_CONCAT(collections.name, '; ') AS collections
            FROM entry_collections AS links
            JOIN collections ON collections.id = links.collection_id
            WHERE links.entry_id IN ({entry_placeholders})
            GROUP BY links.entry_id
            """,
            tuple(entry_ids),
        )
        collection_names = {int(row["entry_id"]): row.get("collections") or "" for row in collection_rows}

    summaries = {template_id: {"missing": {}, "incomplete": 0, "complete": 0} for template_id in template_ids}
    incomplete_entries = []
    for entry in entries_by_id.values():
        current_template_id = int(entry["template_id"])
        template = template_by_id[current_template_id]
        important = set(FRENCH_IMPORTANT_FIELDS.get(template.get("template_type"), ()))
        checked_fields = [field for field in fields_by_template[current_template_id] if field.get("required") or field.get("field_key") in important]
        missing = [field for field in checked_fields if not str(entry["values"].get(field["field_key"]) or "").strip()]
        if missing:
            summaries[current_template_id]["incomplete"] += 1
            for field in missing:
                label = field.get("field_label") or field.get("field_key")
                summaries[current_template_id]["missing"][label] = summaries[current_template_id]["missing"].get(label, 0) + 1
            incomplete_entries.append({
                "entry_id": int(entry["entry_id"]),
                "term": entry.get("term"),
                "meaning": entry.get("meaning"),
                "template_id": current_template_id,
                "template_name": template.get("template_name"),
                "missing_fields": "; ".join((field.get("field_label") or field.get("field_key")) for field in missing),
                "missing_field_count": len(missing),
                "created_at": entry.get("created_at"),
                "collections": collection_names.get(int(entry["entry_id"]), ""),
            })
        else:
            summaries[current_template_id]["complete"] += 1

    summary_rows = []
    for template in templates:
        current_template_id = int(template["template_id"])
        summary = summaries[current_template_id]
        entry_count = summary["complete"] + summary["incomplete"]
        common = sorted(summary["missing"].items(), key=lambda item: (-item[1], item[0]))
        summary_rows.append({
            **template,
            "entry_count": entry_count,
            "complete_entry_count": summary["complete"],
            "incomplete_entry_count": summary["incomplete"],
            "completion_rate": _accuracy(summary["complete"], entry_count),
            "commonly_missing_fields": "; ".join(f"{label} ({count})" for label, count in common),
        })

    incomplete_entries.sort(key=lambda row: (-row["missing_field_count"], row.get("created_at") or "", row.get("term") or ""))
    return summary_rows, incomplete_entries


def get_template_completeness_summary(conn: Connection, template_id=None, language=None) -> list[dict]:
    return _template_completeness_data(conn, template_id, language)[0]


def get_incomplete_template_entries(conn: Connection, template_id=None, language=None, limit: int = 100) -> list[dict]:
    return _template_completeness_data(conn, template_id, language)[1][: max(0, int(limit))]


def get_template_usage_summary(conn: Connection, language=None, start_date=None, end_date=None) -> list[dict]:
    usage = get_template_usage_stats(conn)
    if language not in (None, "", "All"):
        usage = [row for row in usage if row.get("language") == language]
    quiz_by_template = {row.get("template_id"): row for row in get_template_quiz_performance(conn, start_date, end_date)}
    performance_rows = get_entry_performance_summary(conn, language=language)
    weak_ids = {row["entry_id"] for row in get_weak_entries(conn, language=language, limit=100000)}
    by_template: dict[Any, dict] = {}
    for row in performance_rows:
        bucket = by_template.setdefault(row.get("template_id"), {"mistake": 0, "proficient": 0, "weak": 0})
        bucket["mistake"] += int(bool(row.get("in_mistake_book")))
        bucket["proficient"] += int(bool(row.get("in_proficient_pool")))
        bucket["weak"] += int(row.get("entry_id") in weak_ids)

    total_entries = sum(int(row.get("entry_count") or 0) for row in usage)
    result = []
    for row in usage:
        template_id = row.get("template_id")
        quiz = quiz_by_template.get(template_id, {})
        flags = by_template.get(template_id, {})
        entry_count = int(row.get("entry_count") or 0)
        result.append({
            **row,
            "entry_percentage": _accuracy(entry_count, total_entries),
            "quiz_attempt_count": int(quiz.get("total_items") or 0),
            "correct_count": int(quiz.get("correct_items") or 0),
            "wrong_count": int(quiz.get("wrong_items") or 0),
            "accuracy": quiz.get("accuracy"),
            "mistake_book_count": int(flags.get("mistake") or 0),
            "proficient_pool_count": int(flags.get("proficient") or 0),
            "weak_entry_count": int(flags.get("weak") or 0),
        })
    return result


def get_template_weakness_summary(conn: Connection, language=None, min_attempts: int = 2, accuracy_threshold: float = 0.60) -> list[dict]:
    usage = get_template_usage_summary(conn, language)
    rows = [{
        "template_id": row.get("template_id"),
        "template_name": row.get("template_name"),
        "entry_count": int(row.get("entry_count") or 0),
        "weak_entry_count": int(row.get("weak_entry_count") or 0),
        "weak_ratio": _accuracy(int(row.get("weak_entry_count") or 0), int(row.get("entry_count") or 0)),
    } for row in usage]
    rows.sort(key=lambda row: (-(row.get("weak_ratio") or 0), -row["weak_entry_count"], row.get("template_name") or ""))
    return rows


def get_template_quiz_rule_performance(conn: Connection, template_id=None, template_type=None, start_date=None, end_date=None) -> list[dict]:
    # TODO future: persist template_id/source/target field keys in quiz_item_logs for exact rule analytics.
    return []


def get_french_template_overview(conn: Connection, start_date=None, end_date=None) -> dict:
    usage = [row for row in get_template_usage_summary(conn, start_date=start_date, end_date=end_date) if row.get("template_type") in FRENCH_TEMPLATE_TYPES]
    completeness = [row for row in get_template_completeness_summary(conn) if row.get("template_type") in FRENCH_TEMPLATE_TYPES]
    by_type = {row.get("template_type"): row for row in usage}
    attempts = sum(int(row.get("quiz_attempt_count") or 0) for row in usage)
    correct = sum(int(row.get("correct_count") or 0) for row in usage)
    return {
        "french_total_entries": sum(int(row.get("entry_count") or 0) for row in usage),
        "french_verb_present_entries": int(by_type.get("french_verb_present", {}).get("entry_count") or 0),
        "french_adjective_agreement_entries": int(by_type.get("french_adjective_agreement", {}).get("entry_count") or 0),
        "french_noun_gender_plural_entries": int(by_type.get("french_noun_gender_plural", {}).get("entry_count") or 0),
        "french_template_quiz_attempts": attempts,
        "french_template_accuracy": _accuracy(correct, attempts),
        "french_weak_entries": sum(int(row.get("weak_entry_count") or 0) for row in usage),
        "french_incomplete_entries": sum(int(row.get("incomplete_entry_count") or 0) for row in completeness),
        "french_template_count": len(usage),
    }


def get_french_verb_field_performance(conn: Connection, start_date=None, end_date=None) -> list[dict]:
    return []


def get_french_adjective_field_performance(conn: Connection, start_date=None, end_date=None) -> list[dict]:
    return []


def get_french_noun_field_performance(conn: Connection, start_date=None, end_date=None) -> list[dict]:
    return []



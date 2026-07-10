from datetime import date, datetime
from typing import Any


SPECIAL_COLLECTION_TYPES = {
    "mistake_book": "Mistake Book",
    "starred": "Starred",
    "proficient_pool": "Proficient Pool",
}


def normalize_today(today=None) -> str:
    if today is None:
        return date.today().isoformat()

    if isinstance(today, datetime):
        return today.date().isoformat()

    if isinstance(today, date):
        return today.isoformat()

    if isinstance(today, str):
        clean_today = today.strip()
        try:
            return date.fromisoformat(clean_today).isoformat()
        except ValueError as error:
            raise ValueError("today must use YYYY-MM-DD format") from error

    raise ValueError("today must be None, a date, a datetime, or a YYYY-MM-DD string")


def get_today_due_review_cards(
    conn,
    today=None,
    include_overdue: bool = True,
) -> list[dict]:
    today_iso = normalize_today(today)

    if not _has_tables(conn, "card_review_states", "collections", "entry_collections"):
        return []

    overdue_condition = "DATE(s.next_due_at) < DATE(?) OR" if include_overdue else ""
    rows = conn.execute(
        f"""
        SELECT
            s.collection_id,
            c.name AS collection_name,
            s.card_number,
            s.next_due_at,
            s.status AS review_state_status,
            c.card_size,
            COUNT(ec.entry_id) AS entry_count,
            CASE
                WHEN s.next_due_at IS NULL OR TRIM(s.next_due_at) = '' THEN 'unscheduled'
                WHEN DATE(s.next_due_at) < DATE(?) THEN 'overdue'
                WHEN DATE(s.next_due_at) = DATE(?) THEN 'due_today'
                ELSE 'upcoming'
            END AS due_status
        FROM card_review_states s
        JOIN collections c ON c.id = s.collection_id
        LEFT JOIN entry_collections ec
          ON ec.collection_id = s.collection_id
         AND (CAST(((ec.position - 1) / c.card_size) AS INTEGER) + 1) = s.card_number
        WHERE (
            {overdue_condition}
            DATE(s.next_due_at) = DATE(?)
            OR s.next_due_at IS NULL
            OR TRIM(s.next_due_at) = ''
        )
        GROUP BY
            s.collection_id,
            c.name,
            s.card_number,
            s.next_due_at,
            s.status,
            c.card_size
        HAVING COUNT(ec.entry_id) > 0
        ORDER BY
            CASE due_status
                WHEN 'overdue' THEN 0
                WHEN 'due_today' THEN 1
                WHEN 'unscheduled' THEN 2
                ELSE 3
            END,
            DATE(s.next_due_at),
            c.name COLLATE NOCASE,
            s.card_number
        """,
        _due_card_params(today_iso, include_overdue),
    ).fetchall()

    return [
        {
            "collection_id": row["collection_id"],
            "collection_name": row["collection_name"],
            "card_number": row["card_number"],
            "next_due_at": row["next_due_at"],
            "status": row["due_status"],
            "review_state_status": row["review_state_status"],
            "is_overdue": row["due_status"] == "overdue",
            "entry_count": int(row["entry_count"]),
            "card_size": row["card_size"],
        }
        for row in rows
    ]


def get_due_review_cards_for_today_flow(conn, today=None) -> list[dict]:
    return get_today_due_review_cards(conn, today, include_overdue=True)


def get_next_review_candidate(conn, today=None) -> dict | None:
    due_cards = get_due_review_cards_for_today_flow(conn, today)
    if not due_cards:
        return None
    return due_cards[0]


def get_review_focus_payload(
    conn,
    collection_id: int,
    card_number: int,
    today=None,
) -> dict | None:
    today_iso = normalize_today(today)

    if not _has_tables(conn, "collections", "entry_collections"):
        return None

    state_join = ""
    state_select = "NULL AS next_due_at, NULL AS review_state_status"
    if _table_exists(conn, "card_review_states"):
        state_select = "s.next_due_at, s.status AS review_state_status"
        state_join = """
            LEFT JOIN card_review_states s
              ON s.collection_id = c.id
             AND s.card_number = ?
        """

    params = [int(card_number), int(card_number), int(collection_id)]
    if state_join:
        params = [
            int(card_number),
            int(card_number),
            int(card_number),
            int(collection_id),
        ]

    row = conn.execute(
        f"""
        SELECT
            c.id AS collection_id,
            c.name AS collection_name,
            ? AS card_number,
            c.card_size,
            {state_select},
            COUNT(ec.entry_id) AS entry_count
        FROM collections c
        {state_join}
        LEFT JOIN entry_collections ec
          ON ec.collection_id = c.id
         AND (CAST(((ec.position - 1) / c.card_size) AS INTEGER) + 1) = ?
        WHERE c.id = ?
        GROUP BY c.id, c.name, c.card_size
        """,
        tuple(params),
    ).fetchone()

    if row is None or int(row["entry_count"]) <= 0:
        return None

    next_due_at = row["next_due_at"]
    is_unscheduled = next_due_at is None or str(next_due_at).strip() == ""
    is_overdue = False
    is_due_today = False
    days_overdue = 0

    if not is_unscheduled:
        try:
            due_date = date.fromisoformat(str(next_due_at)[:10])
            today_date = date.fromisoformat(today_iso)
            is_overdue = due_date < today_date
            is_due_today = due_date == today_date
            days_overdue = max((today_date - due_date).days, 0)
        except ValueError:
            pass

    return {
        "collection_id": row["collection_id"],
        "collection_name": row["collection_name"],
        "card_number": int(card_number),
        "entry_count": int(row["entry_count"]),
        "card_size": row["card_size"],
        "next_due_at": next_due_at,
        "review_state_status": row["review_state_status"],
        "is_overdue": is_overdue,
        "is_due_today": is_due_today,
        "is_unscheduled": is_unscheduled,
        "days_overdue": days_overdue,
        "status": _focus_due_status(is_overdue, is_due_today, is_unscheduled),
    }


def get_today_review_workload(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    due_cards = get_today_due_review_cards(conn, today_iso, include_overdue=True)

    overdue_cards = sum(1 for card in due_cards if card["status"] == "overdue")
    due_today_cards = sum(1 for card in due_cards if card["status"] == "due_today")
    unscheduled_due_cards = sum(1 for card in due_cards if card["status"] == "unscheduled")

    return {
        "today": today_iso,
        "overdue_cards": overdue_cards,
        "due_today_cards": due_today_cards,
        "unscheduled_due_cards": unscheduled_due_cards,
        "total_due_cards": len(due_cards),
        "estimated_due_entries": sum(int(card["entry_count"]) for card in due_cards),
        "next_upcoming_due_date": _get_next_upcoming_due_date(conn, today_iso),
    }


def get_special_collection_status(conn) -> dict:
    status = {
        system_type: {
            "exists": False,
            "collection_id": None,
            "entry_count": 0,
        }
        for system_type in SPECIAL_COLLECTION_TYPES
    }

    if not _has_tables(conn, "collections", "entry_collections"):
        return status

    has_system_type = _column_exists(conn, "collections", "system_type")
    has_is_system = _column_exists(conn, "collections", "is_system")

    for system_type, fallback_name in SPECIAL_COLLECTION_TYPES.items():
        if has_system_type and has_is_system:
            row = conn.execute(
                """
                SELECT
                    c.id AS collection_id,
                    COUNT(ec.entry_id) AS entry_count
                FROM collections c
                LEFT JOIN entry_collections ec ON ec.collection_id = c.id
                WHERE COALESCE(c.is_system, 0) = 1
                  AND c.system_type = ?
                GROUP BY c.id
                LIMIT 1
                """,
                (system_type,),
            ).fetchone()
        elif has_system_type:
            row = conn.execute(
                """
                SELECT
                    c.id AS collection_id,
                    COUNT(ec.entry_id) AS entry_count
                FROM collections c
                LEFT JOIN entry_collections ec ON ec.collection_id = c.id
                WHERE c.system_type = ?
                GROUP BY c.id
                LIMIT 1
                """,
                (system_type,),
            ).fetchone()
        else:
            row = None

        if row is None:
            row = conn.execute(
                """
                SELECT
                    c.id AS collection_id,
                    COUNT(ec.entry_id) AS entry_count
                FROM collections c
                LEFT JOIN entry_collections ec ON ec.collection_id = c.id
                WHERE c.name = ?
                GROUP BY c.id
                LIMIT 1
                """,
                (fallback_name,),
            ).fetchone()

        if row is not None:
            status[system_type] = {
                "exists": True,
                "collection_id": row["collection_id"],
                "entry_count": int(row["entry_count"]),
            }

    return status


def get_today_review_activity(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    activity = {
        "today": today_iso,
        "reviewed_cards": 0,
        "reviewed_entries": 0,
        "actions": {},
        "recent_reviewed_cards": [],
    }

    if not _has_tables(conn, "card_review_logs"):
        return activity

    action_column = _first_existing_column(conn, "card_review_logs", ("rating", "action"))
    if action_column is None:
        action_column = "''"

    summary_row = conn.execute(
        """
        SELECT
            COUNT(*) AS reviewed_cards,
            COALESCE(SUM(entry_count), 0) AS reviewed_entries
        FROM card_review_logs
        WHERE DATE(reviewed_at) = DATE(?)
        """,
        (today_iso,),
    ).fetchone()
    activity["reviewed_cards"] = int(summary_row["reviewed_cards"] if summary_row else 0)
    activity["reviewed_entries"] = int(summary_row["reviewed_entries"] if summary_row else 0)

    action_rows = conn.execute(
        f"""
        SELECT {action_column} AS action, COUNT(*) AS action_count
        FROM card_review_logs
        WHERE DATE(reviewed_at) = DATE(?)
        GROUP BY {action_column}
        ORDER BY action_count DESC, action ASC
        """,
        (today_iso,),
    ).fetchall()
    activity["actions"] = {
        (row["action"] or "unknown"): int(row["action_count"])
        for row in action_rows
    }

    join_collections = _table_exists(conn, "collections")
    collection_name_select = "c.name AS collection_name" if join_collections else "'' AS collection_name"
    collection_join = "LEFT JOIN collections c ON c.id = l.collection_id" if join_collections else ""
    recent_rows = conn.execute(
        f"""
        SELECT
            l.collection_id,
            {collection_name_select},
            l.card_number,
            l.reviewed_at,
            {action_column.replace('rating', 'l.rating').replace('action', 'l.action')} AS action,
            l.entry_count
        FROM card_review_logs l
        {collection_join}
        WHERE DATE(l.reviewed_at) = DATE(?)
        ORDER BY l.reviewed_at DESC, l.id DESC
        LIMIT 10
        """,
        (today_iso,),
    ).fetchall()
    activity["recent_reviewed_cards"] = [dict(row) for row in recent_rows]

    return activity


def get_reviewed_cards_today(conn, today=None) -> list[dict]:
    today_iso = normalize_today(today)

    if not _has_tables(conn, "card_review_logs", "collections", "entry_collections"):
        return []

    rows = conn.execute(
        """
        SELECT
            l.collection_id,
            c.name AS collection_name,
            l.card_number,
            c.card_size,
            MAX(l.reviewed_at) AS last_reviewed_at,
            COALESCE(MAX(l.entry_count), COUNT(ec.entry_id), 0) AS entry_count
        FROM card_review_logs l
        JOIN collections c ON c.id = l.collection_id
        LEFT JOIN entry_collections ec
          ON ec.collection_id = l.collection_id
         AND (CAST(((ec.position - 1) / c.card_size) AS INTEGER) + 1) = l.card_number
        WHERE DATE(l.reviewed_at) = DATE(?)
        GROUP BY l.collection_id, c.name, l.card_number, c.card_size
        HAVING COALESCE(MAX(l.entry_count), COUNT(ec.entry_id), 0) > 0
        ORDER BY MAX(l.reviewed_at) DESC, c.name COLLATE NOCASE, l.card_number
        """,
        (today_iso,),
    ).fetchall()

    return [
        {
            "collection_id": row["collection_id"],
            "collection_name": row["collection_name"],
            "card_number": row["card_number"],
            "card_size": row["card_size"],
            "entry_count": int(row["entry_count"]),
            "last_reviewed_at": row["last_reviewed_at"],
        }
        for row in rows
    ]


def get_daily_quiz_candidates(conn, today=None) -> list[dict]:
    today_iso = normalize_today(today)
    candidates = []

    for index, card in enumerate(get_reviewed_cards_today(conn, today_iso), start=1):
        candidates.append(
            {
                "recommendation_type": "reviewed_card_quiz",
                "priority": index,
                "title": "Quiz a card reviewed today",
                "description": (
                    f"Practice {card['collection_name']} / Card #{card['card_number']} "
                    "after review."
                ),
                "collection_id": card["collection_id"],
                "collection_name": card["collection_name"],
                "card_number": card["card_number"],
                "entry_count": card["entry_count"],
                "preferred_quiz_type": "mixed_mcq",
                "enabled": True,
                "reason": "reviewed_today",
                "quiz_mode": "card",
            }
        )

    special_collections = get_special_collection_status(conn)
    special_rules = [
        (
            "mistake_book",
            "mistake_book_drill",
            "Mistake Drill",
            "Practice entries currently in Mistake Book.",
            "mistake_book_has_entries",
            "card",
        ),
        (
            "proficient_pool",
            "proficient_pool_audit",
            "Proficient Pool Audit",
            "Run a random audit from Proficient Pool.",
            "proficient_pool_has_entries",
            "random",
        ),
        (
            "starred",
            "starred_review",
            "Starred Review",
            "Practice entries you marked as Starred.",
            "starred_has_entries",
            "card",
        ),
    ]

    next_priority = len(candidates) + 1
    for system_type, recommendation_type, title, description, reason, quiz_mode in special_rules:
        collection = special_collections[system_type]
        if not collection["exists"] or collection["entry_count"] <= 0:
            continue

        card_number = 0 if quiz_mode == "random" else _first_card_number_for_collection(
            conn,
            collection["collection_id"],
        )
        if card_number is None:
            continue

        candidates.append(
            {
                "recommendation_type": recommendation_type,
                "priority": next_priority,
                "title": title,
                "description": description,
                "collection_id": collection["collection_id"],
                "collection_name": SPECIAL_COLLECTION_TYPES[system_type],
                "card_number": card_number,
                "entry_count": collection["entry_count"],
                "preferred_quiz_type": "mixed_mcq",
                "enabled": True,
                "reason": reason,
                "quiz_mode": quiz_mode,
            }
        )
        next_priority += 1

    recent_count = _recent_entry_count(conn, today_iso, days=7)
    if recent_count > 0:
        candidates.append(
            {
                "recommendation_type": "recent_entries_suggestion",
                "priority": next_priority,
                "title": "Recent entries found",
                "description": (
                    f"{recent_count} entr{'y' if recent_count == 1 else 'ies'} were "
                    "created recently. Add them to a collection before quizzing."
                ),
                "collection_id": None,
                "collection_name": "",
                "card_number": None,
                "entry_count": recent_count,
                "preferred_quiz_type": None,
                "enabled": False,
                "reason": "recent_entries_need_collection",
                "quiz_mode": "suggestion",
            }
        )

    return candidates


def get_daily_quiz_recommendations(conn, today=None) -> list[dict]:
    return get_daily_quiz_candidates(conn, today)


def get_today_quiz_activity(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    activity = {
        "today": today_iso,
        "completed_sessions": 0,
        "active_sessions": 0,
        "cancelled_sessions": 0,
        "item_attempts": 0,
        "correct_count": 0,
        "wrong_count": 0,
        "accuracy": None,
        "by_quiz_type": [],
    }

    if not _has_tables(conn, "quiz_sessions"):
        return activity

    has_status = _column_exists(conn, "quiz_sessions", "status")

    if has_status:
        session_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS session_count
            FROM quiz_sessions
            WHERE DATE(started_at) = DATE(?)
               OR DATE(completed_at) = DATE(?)
            GROUP BY status
            """,
            (today_iso, today_iso),
        ).fetchall()
        for row in session_rows:
            key = f"{row['status']}_sessions"
            if key in activity:
                activity[key] = int(row["session_count"])
    else:
        completed_row = conn.execute(
            """
            SELECT COUNT(*) AS completed_sessions
            FROM quiz_sessions
            WHERE completed_at IS NOT NULL
              AND DATE(completed_at) = DATE(?)
            """,
            (today_iso,),
        ).fetchone()
        activity["completed_sessions"] = int(
            completed_row["completed_sessions"] if completed_row else 0
        )

    if not _has_tables(conn, "quiz_item_logs"):
        return activity

    item_summary = conn.execute(
        """
        SELECT
            COUNT(*) AS item_attempts,
            COALESCE(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
            COALESCE(SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count
        FROM quiz_item_logs
        WHERE DATE(answered_at) = DATE(?)
        """,
        (today_iso,),
    ).fetchone()
    activity["item_attempts"] = int(item_summary["item_attempts"] if item_summary else 0)
    activity["correct_count"] = int(item_summary["correct_count"] if item_summary else 0)
    activity["wrong_count"] = int(item_summary["wrong_count"] if item_summary else 0)
    activity["accuracy"] = _calculate_accuracy(
        activity["correct_count"],
        activity["item_attempts"],
    )

    by_type_rows = conn.execute(
        """
        SELECT
            qs.quiz_type,
            COUNT(qil.id) AS item_attempts,
            COALESCE(SUM(CASE WHEN qil.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
            COALESCE(SUM(CASE WHEN qil.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count
        FROM quiz_item_logs qil
        JOIN quiz_sessions qs ON qs.id = qil.session_id
        WHERE DATE(qil.answered_at) = DATE(?)
        GROUP BY qs.quiz_type
        ORDER BY item_attempts DESC, qs.quiz_type ASC
        """,
        (today_iso,),
    ).fetchall()
    activity["by_quiz_type"] = [
        {
            "quiz_type": row["quiz_type"],
            "item_attempts": int(row["item_attempts"]),
            "correct_count": int(row["correct_count"]),
            "wrong_count": int(row["wrong_count"]),
            "accuracy": _calculate_accuracy(
                int(row["correct_count"]),
                int(row["item_attempts"]),
            ),
        }
        for row in by_type_rows
    ]

    return activity


def get_today_review_summary(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    activity = get_today_review_activity(conn, today_iso)
    details = activity["recent_reviewed_cards"]
    return {
        **activity,
        "collections_touched": sorted(
            {
                row["collection_name"]
                for row in details
                if row.get("collection_name")
            }
        ),
        "most_recent_reviewed_at": details[0]["reviewed_at"] if details else None,
        "details": details,
    }


def get_today_quiz_summary(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    activity = get_today_quiz_activity(conn, today_iso)
    session_rows = []

    if _has_tables(conn, "quiz_sessions"):
        collection_join = "LEFT JOIN collections c ON c.id = qs.collection_id" if _table_exists(conn, "collections") else ""
        collection_select = "c.name AS collection_name" if _table_exists(conn, "collections") else "'' AS collection_name"
        session_rows = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT
                    qs.id,
                    qs.started_at,
                    qs.completed_at,
                    qs.status,
                    {collection_select},
                    qs.card_number,
                    qs.quiz_type,
                    qs.total_items,
                    qs.correct_count,
                    qs.wrong_count
                FROM quiz_sessions qs
                {collection_join}
                WHERE DATE(qs.started_at) = DATE(?)
                   OR DATE(qs.completed_at) = DATE(?)
                ORDER BY COALESCE(qs.completed_at, qs.started_at) DESC, qs.id DESC
                """,
                (today_iso, today_iso),
            ).fetchall()
        ]
        for row in session_rows:
            total_items = int(row["total_items"] or 0)
            row["accuracy"] = _calculate_accuracy(int(row["correct_count"] or 0), total_items)

    return {
        **activity,
        "collections_quizzed": sorted(
            {row["collection_name"] for row in session_rows if row.get("collection_name")}
        ),
        "quiz_types_used": sorted(
            {row["quiz_type"] for row in session_rows if row.get("quiz_type")}
        ),
        "active_quiz_exists": activity["active_sessions"] > 0,
        "session_details": session_rows,
    }


def get_today_mistake_summary(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    mistake_book = get_special_collection_status(conn)["mistake_book"]
    wrong_items = []
    recovered_items = []

    if _has_tables(conn, "quiz_item_logs", "quiz_sessions", "entries"):
        collection_join = "LEFT JOIN collections c ON c.id = qs.collection_id" if _table_exists(conn, "collections") else ""
        collection_select = "c.name AS collection_name" if _table_exists(conn, "collections") else "'' AS collection_name"
        wrong_items = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT
                    qil.answered_at,
                    e.id AS entry_id,
                    e.term,
                    e.meaning,
                    {collection_select},
                    qs.quiz_type,
                    qil.prompt,
                    qil.expected_answer,
                    qil.user_answer
                FROM quiz_item_logs qil
                JOIN quiz_sessions qs ON qs.id = qil.session_id
                JOIN entries e ON e.id = qil.entry_id
                {collection_join}
                WHERE DATE(qil.answered_at) = DATE(?)
                  AND qil.is_correct = 0
                ORDER BY qil.answered_at DESC, qil.id DESC
                """,
                (today_iso,),
            ).fetchall()
        ]

        if mistake_book["exists"]:
            recovered_items = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT
                        qil.answered_at,
                        e.id AS entry_id,
                        e.term,
                        e.meaning,
                        qil.prompt,
                        qil.expected_answer,
                        qil.user_answer
                    FROM quiz_item_logs qil
                    JOIN quiz_sessions qs ON qs.id = qil.session_id
                    JOIN entries e ON e.id = qil.entry_id
                    WHERE DATE(qil.answered_at) = DATE(?)
                      AND qil.is_correct = 1
                      AND qs.collection_id = ?
                    ORDER BY qil.answered_at DESC, qil.id DESC
                    """,
                    (today_iso, mistake_book["collection_id"]),
                ).fetchall()
            ]

    return {
        "today": today_iso,
        "wrong_count": len(wrong_items),
        "current_mistake_book_count": mistake_book["entry_count"],
        "recovered_count": len(recovered_items),
        "wrong_items": wrong_items,
        "recovered_items": recovered_items,
    }


def get_today_proficient_pool_summary(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    proficient_pool = get_special_collection_status(conn)["proficient_pool"]
    failed_items = []
    item_attempts = 0

    if proficient_pool["exists"] and _has_tables(conn, "quiz_item_logs", "quiz_sessions", "entries"):
        summary_row = conn.execute(
            """
            SELECT COUNT(*) AS item_attempts
            FROM quiz_item_logs qil
            JOIN quiz_sessions qs ON qs.id = qil.session_id
            WHERE DATE(qil.answered_at) = DATE(?)
              AND qs.collection_id = ?
            """,
            (today_iso, proficient_pool["collection_id"]),
        ).fetchone()
        item_attempts = int(summary_row["item_attempts"] if summary_row else 0)

        failed_items = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    qil.answered_at,
                    e.id AS entry_id,
                    e.term,
                    e.meaning,
                    qil.prompt,
                    qil.expected_answer,
                    qil.user_answer
                FROM quiz_item_logs qil
                JOIN quiz_sessions qs ON qs.id = qil.session_id
                JOIN entries e ON e.id = qil.entry_id
                WHERE DATE(qil.answered_at) = DATE(?)
                  AND qs.collection_id = ?
                  AND qil.is_correct = 0
                ORDER BY qil.answered_at DESC, qil.id DESC
                """,
                (today_iso, proficient_pool["collection_id"]),
            ).fetchall()
        ]

    return {
        "today": today_iso,
        "current_proficient_pool_count": proficient_pool["entry_count"],
        "item_attempts": item_attempts,
        "failed_count": len(failed_items),
        "failed_items": failed_items,
    }


def get_today_remaining_workload(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    workload = get_today_review_workload(conn, today_iso)
    special_collections = get_special_collection_status(conn)
    quiz_activity = get_today_quiz_activity(conn, today_iso)
    return {
        "today": today_iso,
        "due_cards_remaining": workload["due_today_cards"] + workload["unscheduled_due_cards"],
        "overdue_cards": workload["overdue_cards"],
        "total_due_cards": workload["total_due_cards"],
        "estimated_due_entries": workload["estimated_due_entries"],
        "mistake_book_entries": special_collections["mistake_book"]["entry_count"],
        "active_quiz": quiz_activity["active_sessions"] > 0,
    }


def get_today_learning_summary(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    review_summary = get_today_review_summary(conn, today_iso)
    quiz_summary = get_today_quiz_summary(conn, today_iso)
    mistake_summary = get_today_mistake_summary(conn, today_iso)
    proficient_pool_summary = get_today_proficient_pool_summary(conn, today_iso)
    remaining_workload = get_today_remaining_workload(conn, today_iso)
    completion_status = _daily_completion_status(
        review_summary,
        quiz_summary,
        remaining_workload,
    )
    return {
        "today": today_iso,
        "completion_status": completion_status,
        "review_summary": review_summary,
        "quiz_summary": quiz_summary,
        "mistake_summary": mistake_summary,
        "proficient_pool_summary": proficient_pool_summary,
        "remaining_workload": remaining_workload,
    }


def build_today_recommendations(conn, today=None) -> list[dict]:
    today_iso = normalize_today(today)
    workload = get_today_review_workload(conn, today_iso)
    special_collections = get_special_collection_status(conn)

    if workload["overdue_cards"] > 0:
        return [
            _recommendation(
                1,
                "review_overdue",
                "Review overdue cards",
                f"You have {workload['overdue_cards']} overdue card(s) waiting.",
                "Review",
                "Open Review and start with overdue cards.",
            )
        ]

    if workload["due_today_cards"] > 0 or workload["unscheduled_due_cards"] > 0:
        due_count = workload["due_today_cards"] + workload["unscheduled_due_cards"]
        return [
            _recommendation(
                1,
                "review_due_today",
                "Review today's cards",
                f"You have {due_count} card(s) due today.",
                "Review",
                "Open Review and complete today's scheduled cards.",
            )
        ]

    mistake_book = special_collections["mistake_book"]
    if mistake_book["entry_count"] > 0:
        return [
            _recommendation(
                1,
                "mistake_drill",
                "Practice Mistake Book",
                f"You have {mistake_book['entry_count']} item(s) in Mistake Book.",
                "Quiz",
                "Start a quiz from Mistake Book.",
            )
        ]

    proficient_pool = special_collections["proficient_pool"]
    if proficient_pool["entry_count"] > 0:
        return [
            _recommendation(
                1,
                "proficient_pool_audit",
                "Audit Proficient Pool",
                f"You have {proficient_pool['entry_count']} item(s) available for audit.",
                "Quiz",
                "Start a random quiz from Proficient Pool.",
            )
        ]

    starred = special_collections["starred"]
    if starred["entry_count"] > 0:
        return [
            _recommendation(
                1,
                "starred_review",
                "Review Starred entries",
                f"You have {starred['entry_count']} starred item(s).",
                "Quiz",
                "Practice entries from Starred.",
            )
        ]

    return [
        _recommendation(
            1,
            "add_or_organize_entries",
            "Add or organize entries",
            "No review or practice source is waiting right now.",
            "Entries",
            "Add entries or organize existing entries into collections.",
        )
    ]


def build_today_completion_summary(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    workload = get_today_review_workload(conn, today_iso)
    review_activity = get_today_review_activity(conn, today_iso)
    quiz_activity = get_today_quiz_activity(conn, today_iso)
    special_collections = get_special_collection_status(conn)

    if workload["total_due_cards"] == 0:
        review_status = "no_due_review"
    elif review_activity["reviewed_cards"] >= workload["total_due_cards"]:
        review_status = "review_complete"
    else:
        review_status = "review_remaining"

    if quiz_activity["item_attempts"] > 0:
        practice_status = "practice_done"
    elif any(
        special_collections[key]["entry_count"] > 0
        for key in ("mistake_book", "proficient_pool", "starred")
    ):
        practice_status = "practice_available"
    else:
        practice_status = "no_practice_source"

    remaining_due_cards = max(
        workload["total_due_cards"] - review_activity["reviewed_cards"],
        0,
    )

    return {
        "today": today_iso,
        "review_status": review_status,
        "practice_status": practice_status,
        "reviewed_cards": review_activity["reviewed_cards"],
        "remaining_due_cards": remaining_due_cards,
        "quiz_item_attempts": quiz_activity["item_attempts"],
        "quiz_accuracy": quiz_activity["accuracy"],
    }


def get_today_overview(conn, today=None) -> dict:
    today_iso = normalize_today(today)
    return {
        "today": today_iso,
        "content_inventory": get_content_inventory(conn),
        "review_workload": get_today_review_workload(conn, today_iso),
        "due_review_cards": get_today_due_review_cards(conn, today_iso),
        "special_collections": get_special_collection_status(conn),
        "review_activity": get_today_review_activity(conn, today_iso),
        "quiz_activity": get_today_quiz_activity(conn, today_iso),
        "daily_quiz_recommendations": get_daily_quiz_recommendations(conn, today_iso),
        "today_learning_summary": get_today_learning_summary(conn, today_iso),
        "recommendations": build_today_recommendations(conn, today_iso),
        "completion_summary": build_today_completion_summary(conn, today_iso),
    }


def get_content_inventory(conn) -> dict:
    """Return read-only counts used to explain Today page setup states."""
    entry_count = 0
    collection_count = 0
    review_state_count = 0

    if _table_exists(conn, "entries"):
        entry_count = int(conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0])

    if _table_exists(conn, "collections"):
        where_clause = "WHERE is_system = 0" if _column_exists(
            conn, "collections", "is_system"
        ) else ""
        collection_count = int(
            conn.execute(f"SELECT COUNT(*) FROM collections {where_clause}").fetchone()[0]
        )

    if _table_exists(conn, "card_review_states"):
        review_state_count = int(
            conn.execute("SELECT COUNT(*) FROM card_review_states").fetchone()[0]
        )

    return {
        "entry_count": entry_count,
        "collection_count": collection_count,
        "review_state_count": review_state_count,
    }


def _table_exists(conn, table_name: str) -> bool:
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


def _has_tables(conn, *table_names: str) -> bool:
    return all(_table_exists(conn, table_name) for table_name in table_names)


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False

    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return column_name in {row["name"] for row in rows}


def _first_existing_column(
    conn,
    table_name: str,
    column_names: tuple[str, ...],
) -> str | None:
    for column_name in column_names:
        if _column_exists(conn, table_name, column_name):
            return column_name
    return None


def _due_card_params(today_iso: str, include_overdue: bool) -> tuple[str, ...]:
    params = [today_iso, today_iso]
    if include_overdue:
        params.append(today_iso)
    params.append(today_iso)
    return tuple(params)


def _get_next_upcoming_due_date(conn, today_iso: str) -> str | None:
    if not _has_tables(conn, "card_review_states", "collections", "entry_collections"):
        return None

    row = conn.execute(
        """
        SELECT MIN(DATE(s.next_due_at)) AS next_due_at
        FROM card_review_states s
        JOIN collections c ON c.id = s.collection_id
        JOIN entry_collections ec
          ON ec.collection_id = s.collection_id
         AND (CAST(((ec.position - 1) / c.card_size) AS INTEGER) + 1) = s.card_number
        WHERE s.next_due_at IS NOT NULL
          AND TRIM(s.next_due_at) != ''
          AND DATE(s.next_due_at) > DATE(?)
        """,
        (today_iso,),
    ).fetchone()

    return row["next_due_at"] if row and row["next_due_at"] else None


def _first_card_number_for_collection(conn, collection_id: int) -> int | None:
    if not _has_tables(conn, "collections", "entry_collections"):
        return None

    row = conn.execute(
        """
        SELECT MIN(CAST(((ec.position - 1) / c.card_size) AS INTEGER) + 1) AS card_number
        FROM entry_collections ec
        JOIN collections c ON c.id = ec.collection_id
        WHERE ec.collection_id = ?
        """,
        (int(collection_id),),
    ).fetchone()

    if row is None or row["card_number"] is None:
        return None
    return int(row["card_number"])


def _recent_entry_count(conn, today_iso: str, days: int = 7) -> int:
    if not _table_exists(conn, "entries"):
        return 0

    row = conn.execute(
        """
        SELECT COUNT(*) AS entry_count
        FROM entries
        WHERE DATE(created_at) >= DATE(?, ?)
          AND DATE(created_at) <= DATE(?)
        """,
        (today_iso, f"-{int(days) - 1} days", today_iso),
    ).fetchone()

    return int(row["entry_count"] if row else 0)


def _calculate_accuracy(correct_count: int, total_count: int) -> float | None:
    if total_count <= 0:
        return None
    return round(correct_count * 100.0 / total_count, 1)


def _focus_due_status(
    is_overdue: bool,
    is_due_today: bool,
    is_unscheduled: bool,
) -> str:
    if is_overdue:
        return "overdue"
    if is_due_today:
        return "due_today"
    if is_unscheduled:
        return "unscheduled"
    return "not_due"


def _daily_completion_status(
    review_summary: dict,
    quiz_summary: dict,
    remaining_workload: dict,
) -> str:
    has_review = review_summary["reviewed_cards"] > 0
    has_quiz = quiz_summary["item_attempts"] > 0
    has_completed_quiz = quiz_summary["completed_sessions"] > 0
    has_due_work = remaining_workload["total_due_cards"] > 0

    if not has_review and not has_quiz:
        return "Not started"
    if not has_due_work and has_completed_quiz:
        return "Daily work mostly complete"
    if not has_due_work:
        return "Review cleared"
    if has_quiz:
        return "Quiz practiced"
    return "In progress"


def _recommendation(
    priority: int,
    kind: str,
    title: str,
    description: str,
    target_page: str,
    action_hint: str,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "kind": kind,
        "title": title,
        "description": description,
        "target_page": target_page,
        "action_hint": action_hint,
    }

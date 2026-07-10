from datetime import datetime, timezone
import random

from src.collections import (
    add_entries_to_system_collection,
    get_card_groups_for_collection,
    get_entries_in_collection,
    get_system_collection_by_type_or_name,
    is_entry_in_system_collection,
)
from src.db import get_connection


QUIZ_TYPES = {
    "term_to_meaning": {"prompt_field": "term", "answer_field": "meaning"},
    "meaning_to_term": {"prompt_field": "meaning", "answer_field": "term"},
    "term_to_meaning_mcq": {"prompt_field": "term", "answer_field": "meaning"},
    "meaning_to_term_mcq": {"prompt_field": "meaning", "answer_field": "term"},
    "mixed_mcq": {"prompt_field": "", "answer_field": ""},
    "matching": {"prompt_field": "term", "answer_field": "meaning"},
    "template_field_self_graded": {"prompt_field": "", "answer_field": ""},
    "template_field_mcq": {"prompt_field": "", "answer_field": ""},
    "template_field_matching": {"prompt_field": "", "answer_field": ""},
}

MCQ_DIRECTIONS = {
    "term_to_meaning_mcq": {"prompt_field": "term", "answer_field": "meaning"},
    "meaning_to_term_mcq": {"prompt_field": "meaning", "answer_field": "term"},
}

QUIZ_SESSION_COLUMNS = """
    id,
    collection_id,
    card_number,
    quiz_type,
    started_at,
    completed_at,
    total_items,
    correct_count,
    wrong_count,
    status
"""

QUIZ_ITEM_LOG_COLUMNS = """
    id,
    session_id,
    entry_id,
    prompt,
    expected_answer,
    user_answer,
    is_correct,
    answered_at
"""


_RANDOM = random.SystemRandom()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _shuffled(items: list) -> list:
    return shuffle_sequence(items)


def _sample(items: list, count: int) -> list:
    return _RANDOM.sample(list(items), count)


def _rotated(items: list) -> list:
    if len(items) <= 1:
        return list(items)
    return [*items[1:], items[0]]


def shuffle_sequence(items: list, avoid_order: list | None = None, max_attempts: int = 8) -> list:
    original_items = list(items)
    if len(original_items) <= 1:
        return original_items

    avoided_items = list(avoid_order) if avoid_order is not None else original_items
    shuffled_items = list(original_items)
    for _ in range(max(max_attempts, 1)):
        shuffled_items = list(original_items)
        _RANDOM.shuffle(shuffled_items)
        if shuffled_items != avoided_items:
            return shuffled_items

    return _rotated(original_items) if original_items == avoided_items else shuffled_items


def shuffle_quiz_items(
    quiz_items: list[dict],
    avoid_entry_id_order: list[int] | None = None,
) -> list[dict]:
    if avoid_entry_id_order is None:
        avoided_items = None
    else:
        avoided_items = [
            item
            for entry_id in avoid_entry_id_order
            for item in quiz_items
            if item.get("entry_id") == entry_id
        ]
        if len(avoided_items) != len(quiz_items):
            avoided_items = None

    return shuffle_sequence(quiz_items, avoid_order=avoided_items)


def shuffle_mcq_options(correct_answer: str, distractor_options: list[str]) -> list[str]:
    options = [correct_answer, *distractor_options]
    return shuffle_sequence(options, avoid_order=options)


def _validate_quiz_type(quiz_type: str) -> None:
    if quiz_type not in QUIZ_TYPES:
        allowed_types = ", ".join(QUIZ_TYPES)
        raise ValueError(f"Unsupported quiz_type: {quiz_type}. Use one of: {allowed_types}")


def create_quiz_session(
    collection_id: int,
    card_number: int,
    quiz_type: str,
    total_items: int,
) -> int:
    _validate_quiz_type(quiz_type)

    if card_number < 0:
        raise ValueError("card_number cannot be negative")

    if total_items < 0:
        raise ValueError("total_items cannot be negative")

    now = _now_iso()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO quiz_sessions (
                collection_id,
                card_number,
                quiz_type,
                started_at,
                total_items,
                status
            )
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (collection_id, card_number, quiz_type, now, total_items),
        )

    return int(cursor.lastrowid)


def get_entries_for_quiz(collection_id: int, card_number: int) -> list[dict]:
    if card_number < 1:
        raise ValueError("card_number must be at least 1")

    card_groups = get_card_groups_for_collection(collection_id)

    for card_group in card_groups:
        if card_group["card_number"] == card_number:
            return card_group["entries"]

    return []


def get_random_entries_from_collection(collection_id: int, item_count: int) -> list[dict]:
    if item_count < 1:
        raise ValueError("item_count must be at least 1")

    entries = get_entries_in_collection(collection_id)
    if len(entries) < item_count:
        raise ValueError(
            f"The selected collection has only {len(entries)} entries. Choose {len(entries)} or fewer items."
        )

    return _sample(entries, item_count)


def create_random_quiz_session(collection_id: int, quiz_type: str, total_items: int) -> int:
    return create_quiz_session(collection_id, 0, quiz_type, total_items)


def create_quiz_items(entries: list[dict], quiz_type: str) -> list[dict]:
    _validate_quiz_type(quiz_type)
    quiz_config = QUIZ_TYPES[quiz_type]
    prompt_field = quiz_config["prompt_field"]
    answer_field = quiz_config["answer_field"]

    quiz_items = [
        {
            "entry_id": entry["id"],
            "prompt": entry[prompt_field],
            "expected_answer": entry[answer_field],
            "term": entry["term"],
            "meaning": entry["meaning"],
            "example": entry.get("example", ""),
        }
        for entry in entries
    ]
    return shuffle_quiz_items(
        quiz_items,
        avoid_entry_id_order=[entry["id"] for entry in entries],
    )


def has_answer_been_logged(session_id: int, entry_id: int, prompt: str) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM quiz_item_logs
            WHERE session_id = ?
              AND entry_id = ?
              AND prompt = ?
            LIMIT 1
            """,
            (session_id, entry_id, prompt),
        ).fetchone()

    return row is not None


def can_log_answer(
    session_id: int,
    entry_id: int,
    prompt: str,
    question_index: int | None = None,
) -> bool:
    del question_index
    session = get_quiz_session(session_id)
    if session is None or session.get("status") != "active":
        return False

    return not has_answer_been_logged(session_id, entry_id, prompt)


def log_quiz_answer(
    session_id: int,
    entry_id: int,
    prompt: str,
    expected_answer: str,
    user_answer: str,
    is_correct: bool,
) -> int | None:
    if not can_log_answer(session_id, entry_id, prompt):
        return None

    now = _now_iso()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO quiz_item_logs (
                session_id,
                entry_id,
                prompt,
                expected_answer,
                user_answer,
                is_correct,
                answered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                entry_id,
                prompt,
                expected_answer,
                user_answer.strip(),
                int(is_correct),
                now,
            ),
        )

    return int(cursor.lastrowid)


def update_entry_quiz_counts(entry_id: int, is_correct: bool) -> None:
    column_name = "correct_count" if is_correct else "wrong_count"
    now = _now_iso()

    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE entries
            SET
                {column_name} = COALESCE({column_name}, 0) + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (now, entry_id),
        )


def _get_quiz_answer_counts(connection, session_id: int):
    return connection.execute(
        """
        SELECT
            COUNT(*) AS logged_items,
            COALESCE(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
            COALESCE(SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count
        FROM quiz_item_logs
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()


def mark_quiz_session_completed(session_id: int) -> None:
    now = _now_iso()

    with get_connection() as connection:
        counts = _get_quiz_answer_counts(connection, session_id)
        connection.execute(
            """
            UPDATE quiz_sessions
            SET
                completed_at = ?,
                total_items = ?,
                correct_count = ?,
                wrong_count = ?,
                status = 'completed'
            WHERE id = ?
            """,
            (
                now,
                counts["logged_items"],
                counts["correct_count"],
                counts["wrong_count"],
                session_id,
            ),
        )


def mark_quiz_session_cancelled(session_id: int) -> None:
    with get_connection() as connection:
        counts = _get_quiz_answer_counts(connection, session_id)
        connection.execute(
            """
            UPDATE quiz_sessions
            SET
                correct_count = ?,
                wrong_count = ?,
                status = 'cancelled'
            WHERE id = ?
              AND status = 'active'
            """,
            (
                counts["correct_count"],
                counts["wrong_count"],
                session_id,
            ),
        )


def complete_quiz_session(session_id: int) -> dict:
    mark_quiz_session_completed(session_id)

    session = get_quiz_session(session_id)
    if session is None:
        raise ValueError("Quiz session was not found")

    return session


def get_quiz_session(session_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT {QUIZ_SESSION_COLUMNS}
            FROM quiz_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def reconcile_finished_active_quiz_sessions() -> int:
    now = _now_iso()
    reconciled_count = 0
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                session.id,
                session.completed_at,
                session.total_items,
                COUNT(logs.id) AS logged_items,
                COALESCE(SUM(CASE WHEN logs.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
                COALESCE(SUM(CASE WHEN logs.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count
            FROM quiz_sessions AS session
            LEFT JOIN quiz_item_logs AS logs ON logs.session_id = session.id
            WHERE session.status = 'active'
            GROUP BY session.id
            HAVING session.completed_at IS NOT NULL
                OR (
                    session.total_items > 0
                    AND COUNT(logs.id) >= session.total_items
                )
            """
        ).fetchall()

        for row in rows:
            connection.execute(
                """
                UPDATE quiz_sessions
                SET
                    completed_at = COALESCE(completed_at, ?),
                    total_items = ?,
                    correct_count = ?,
                    wrong_count = ?,
                    status = 'completed'
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    now,
                    int(row["logged_items"]),
                    int(row["correct_count"]),
                    int(row["wrong_count"]),
                    int(row["id"]),
                ),
            )
            reconciled_count += 1

    return reconciled_count


def get_active_quiz_session() -> dict | None:
    reconcile_finished_active_quiz_sessions()

    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT {QUIZ_SESSION_COLUMNS}
            FROM quiz_sessions
            WHERE status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_quiz_progress(session_id: int) -> dict:
    with get_connection() as connection:
        session = connection.execute(
            f"""
            SELECT {QUIZ_SESSION_COLUMNS}
            FROM quiz_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if session is None:
            raise ValueError("Quiz session was not found")

        counts = _get_quiz_answer_counts(connection, session_id)

    return {
        "session_id": session_id,
        "status": session["status"],
        "answered_items": counts["logged_items"],
        "total_items": session["total_items"],
        "correct_count": counts["correct_count"],
        "wrong_count": counts["wrong_count"],
    }


def record_quiz_answer(
    session_id: int,
    entry_id: int,
    prompt: str,
    expected_answer: str,
    user_answer: str,
    is_correct: bool,
) -> dict:
    now = _now_iso()

    with get_connection() as connection:
        session = connection.execute(
            """
            SELECT status
            FROM quiz_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if session is None:
            raise ValueError("Quiz session was not found")

        if session["status"] != "active":
            return {"logged": False, "log_id": None, "reason": "session_not_active"}

        existing_log = connection.execute(
            """
            SELECT id
            FROM quiz_item_logs
            WHERE session_id = ?
              AND entry_id = ?
              AND prompt = ?
            LIMIT 1
            """,
            (session_id, entry_id, prompt),
        ).fetchone()
        if existing_log is not None:
            return {
                "logged": False,
                "log_id": existing_log["id"],
                "reason": "already_logged",
            }

        cursor = connection.execute(
            """
            INSERT INTO quiz_item_logs (
                session_id,
                entry_id,
                prompt,
                expected_answer,
                user_answer,
                is_correct,
                answered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                entry_id,
                prompt,
                expected_answer,
                user_answer.strip(),
                int(is_correct),
                now,
            ),
        )

        column_name = "correct_count" if is_correct else "wrong_count"
        connection.execute(
            f"""
            UPDATE entries
            SET
                {column_name} = COALESCE({column_name}, 0) + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (now, entry_id),
        )

    if not is_correct:
        add_wrong_entry_to_mistake_book(entry_id)

    return {"logged": True, "log_id": int(cursor.lastrowid), "reason": "logged"}


def get_quiz_item_logs(session_id: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT {QUIZ_ITEM_LOG_COLUMNS}
            FROM quiz_item_logs
            WHERE session_id = ?
            ORDER BY answered_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_entry_quiz_performance() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id AS entry_id,
                term,
                meaning,
                COALESCE(correct_count, 0) AS correct_count,
                COALESCE(wrong_count, 0) AS wrong_count,
                COALESCE(correct_count, 0) + COALESCE(wrong_count, 0) AS total_attempts,
                CASE
                    WHEN COALESCE(correct_count, 0) + COALESCE(wrong_count, 0) = 0 THEN 0
                    ELSE ROUND(
                        COALESCE(correct_count, 0) * 100.0 /
                        (COALESCE(correct_count, 0) + COALESCE(wrong_count, 0)),
                        1
                    )
                END AS accuracy_percentage
            FROM entries
            WHERE COALESCE(correct_count, 0) + COALESCE(wrong_count, 0) > 0
            ORDER BY wrong_count DESC, total_attempts DESC, term ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_entry_quiz_performance_by_entry(entry_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id AS entry_id,
                term,
                meaning,
                COALESCE(correct_count, 0) AS correct_count,
                COALESCE(wrong_count, 0) AS wrong_count,
                COALESCE(correct_count, 0) + COALESCE(wrong_count, 0) AS total_attempts,
                CASE
                    WHEN COALESCE(correct_count, 0) + COALESCE(wrong_count, 0) = 0 THEN 0
                    ELSE ROUND(
                        COALESCE(correct_count, 0) * 100.0 /
                        (COALESCE(correct_count, 0) + COALESCE(wrong_count, 0)),
                        1
                    )
                END AS accuracy_percentage
            FROM entries
            WHERE id = ?
            """,
            (entry_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_quiz_item_log_view(
    collection_id: int | None = None,
    card_number: int | None = None,
    show_wrong_only: bool = False,
    search: str = "",
    session_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    where_clauses = []
    params = []

    if show_wrong_only:
        where_clauses.append("qil.is_correct = 0")

    if search.strip():
        search_pattern = f"%{search.strip().lower()}%"
        where_clauses.append(
            """
            (
                LOWER(e.term) LIKE ?
                OR LOWER(qil.prompt) LIKE ?
                OR LOWER(qil.expected_answer) LIKE ?
                OR LOWER(COALESCE(qil.user_answer, '')) LIKE ?
            )
            """
        )
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    if collection_id is not None:
        where_clauses.append("qs.collection_id = ?")
        params.append(collection_id)

    if card_number is not None:
        where_clauses.append("qs.card_number = ?")
        params.append(card_number)

    if session_id is not None:
        where_clauses.append("qil.session_id = ?")
        params.append(session_id)

    if status is not None and status != "All":
        where_clauses.append("qs.status = ?")
        params.append(status)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT
                qil.session_id,
                c.name AS collection_name,
                qs.card_number,
                qs.quiz_type,
                qs.status AS session_status,
                qil.entry_id,
                e.term,
                qil.prompt,
                qil.expected_answer,
                qil.user_answer,
                qil.is_correct,
                qil.answered_at
            FROM quiz_item_logs qil
            JOIN quiz_sessions qs ON qs.id = qil.session_id
            JOIN entries e ON e.id = qil.entry_id
            LEFT JOIN collections c ON c.id = qs.collection_id
            {where_sql}
            ORDER BY qil.answered_at DESC, qil.id DESC
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def add_wrong_entry_to_mistake_book(entry_id: int) -> None:
    add_entries_to_system_collection([entry_id], "mistake_book")


def get_mistake_book_collection() -> dict | None:
    return get_system_collection_by_type_or_name("mistake_book")


def is_mistake_book_collection(collection_id: int | None) -> bool:
    if collection_id is None:
        return False

    mistake_book = get_mistake_book_collection()
    return mistake_book is not None and int(mistake_book["id"]) == int(collection_id)


def _mastery_status(correct_count: int, wrong_count: int = 0) -> str:
    del wrong_count
    if correct_count >= 2:
        return "Recommended to remove"
    if correct_count >= 1:
        return "Recovered this time"
    return "Keep practicing"


def get_recent_mistake_book_correct_count(entry_id: int) -> int:
    mistake_book = get_mistake_book_collection()
    if mistake_book is None:
        return 0

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS correct_count
            FROM quiz_item_logs qil
            JOIN quiz_sessions qs ON qs.id = qil.session_id
            WHERE qil.entry_id = ?
              AND qil.is_correct = 1
              AND qs.collection_id = ?
            """,
            (entry_id, mistake_book["id"]),
        ).fetchone()

    return int(row["correct_count"] if row is not None else 0)


def get_mistake_book_recovery_status(entry_id: int) -> dict:
    mistake_book = get_mistake_book_collection()
    if mistake_book is None:
        return {
            "entry_id": entry_id,
            "currently_in_mistake_book": False,
            "mistake_book_correct_count": 0,
            "mistake_book_wrong_count": 0,
            "status": "Keep practicing",
        }

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1
                    FROM entry_collections ec
                    WHERE ec.entry_id = ?
                      AND ec.collection_id = ?
                ) AS currently_in_mistake_book,
                COALESCE(SUM(CASE WHEN qil.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_count,
                COALESCE(SUM(CASE WHEN qil.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count,
                MAX(CASE WHEN qil.is_correct = 1 THEN qil.answered_at ELSE NULL END) AS last_correct_at,
                MAX(CASE WHEN qil.is_correct = 0 THEN qil.answered_at ELSE NULL END) AS last_wrong_at
            FROM quiz_item_logs qil
            JOIN quiz_sessions qs ON qs.id = qil.session_id
            WHERE qil.entry_id = ?
              AND qs.collection_id = ?
            """,
            (entry_id, mistake_book["id"], entry_id, mistake_book["id"]),
        ).fetchone()

    correct_count = int(row["correct_count"] if row is not None else 0)
    wrong_count = int(row["wrong_count"] if row is not None else 0)
    return {
        "entry_id": entry_id,
        "currently_in_mistake_book": bool(row["currently_in_mistake_book"] if row is not None else False),
        "mistake_book_correct_count": correct_count,
        "mistake_book_wrong_count": wrong_count,
        "last_correct_at": row["last_correct_at"] if row is not None else None,
        "last_wrong_at": row["last_wrong_at"] if row is not None else None,
        "status": _mastery_status(correct_count, wrong_count),
    }


def get_mistake_book_mastery_candidates() -> list[dict]:
    mistake_book = get_mistake_book_collection()
    if mistake_book is None:
        return []

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                e.id AS entry_id,
                e.term,
                e.meaning,
                COALESCE(e.correct_count, 0) AS correct_count,
                COALESCE(e.wrong_count, 0) AS wrong_count,
                COALESCE(SUM(CASE WHEN qs.id IS NOT NULL AND qil.is_correct = 1 THEN 1 ELSE 0 END), 0) AS mistake_book_correct_count,
                COALESCE(SUM(CASE WHEN qs.id IS NOT NULL AND qil.is_correct = 0 THEN 1 ELSE 0 END), 0) AS mistake_book_wrong_count,
                MAX(CASE WHEN qs.id IS NOT NULL AND qil.is_correct = 1 THEN qil.answered_at ELSE NULL END) AS last_correct_at,
                MAX(CASE WHEN qs.id IS NOT NULL AND qil.is_correct = 0 THEN qil.answered_at ELSE NULL END) AS last_wrong_at
            FROM entry_collections ec
            JOIN entries e ON e.id = ec.entry_id
            LEFT JOIN quiz_item_logs qil ON qil.entry_id = e.id
            LEFT JOIN quiz_sessions qs
              ON qs.id = qil.session_id
             AND qs.collection_id = ec.collection_id
            WHERE ec.collection_id = ?
            GROUP BY e.id, ec.position
            ORDER BY
                CASE
                    WHEN COALESCE(SUM(CASE WHEN qs.id IS NOT NULL AND qil.is_correct = 1 THEN 1 ELSE 0 END), 0) >= 2 THEN 0
                    WHEN COALESCE(SUM(CASE WHEN qs.id IS NOT NULL AND qil.is_correct = 1 THEN 1 ELSE 0 END), 0) = 1 THEN 1
                    ELSE 2
                END,
                ec.position ASC,
                e.term ASC
            """,
            (mistake_book["id"],),
        ).fetchall()

    candidates = []
    for row in rows:
        item = dict(row)
        item["currently_in_mistake_book"] = True
        item["status"] = _mastery_status(
            int(item["mistake_book_correct_count"]),
            int(item["mistake_book_wrong_count"]),
        )
        candidates.append(item)

    return candidates


def get_recovered_mistake_book_entries_for_session(session_id: int) -> list[dict]:
    session = get_quiz_session(session_id)
    if session is None or not is_mistake_book_collection(session["collection_id"]):
        return []

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                qil.entry_id,
                e.term,
                e.meaning,
                qil.prompt,
                qil.expected_answer,
                qil.user_answer,
                qil.answered_at,
                EXISTS (
                    SELECT 1
                    FROM entry_collections ec
                    WHERE ec.entry_id = qil.entry_id
                      AND ec.collection_id = qs.collection_id
                ) AS currently_in_mistake_book
            FROM quiz_item_logs qil
            JOIN quiz_sessions qs ON qs.id = qil.session_id
            JOIN entries e ON e.id = qil.entry_id
            WHERE qil.session_id = ?
              AND qil.is_correct = 1
            ORDER BY qil.answered_at ASC, qil.id ASC
            """,
            (session_id,),
        ).fetchall()

    recovered_entries = []
    for row in rows:
        item = dict(row)
        status = get_mistake_book_recovery_status(item["entry_id"])
        item.update(
            {
                "currently_in_mistake_book": bool(item["currently_in_mistake_book"]),
                "mistake_book_correct_count": status["mistake_book_correct_count"],
                "mistake_book_wrong_count": status["mistake_book_wrong_count"],
                "status": status["status"],
            }
        )
        recovered_entries.append(item)

    return recovered_entries


def get_collection_entries_for_distractors(collection_id: int) -> list[dict]:
    entries = []

    for card_group in get_card_groups_for_collection(collection_id):
        entries.extend(card_group["entries"])

    return entries


MCQ_GENERATION_ERROR = (
    "Cannot generate this multiple-choice quiz. "
    "This collection does not have enough unique, unambiguous options."
)


def normalize_answer_text(text: str) -> str:
    normalized_text = " ".join((text or "").strip().split())
    if normalized_text.isascii():
        normalized_text = normalized_text.lower()
    return normalized_text


def get_safe_distractors_for_term_to_meaning(
    target_entry: dict,
    candidate_entries: list[dict],
    count: int = 3,
) -> list[str]:
    target_meaning = normalize_answer_text(target_entry.get("meaning", ""))
    distractors = []
    seen_options = {target_meaning}

    for candidate_entry in _shuffled(candidate_entries):
        if candidate_entry["id"] == target_entry["id"]:
            continue

        candidate_meaning = candidate_entry.get("meaning", "")
        normalized_meaning = normalize_answer_text(candidate_meaning)
        if not normalized_meaning or normalized_meaning in seen_options:
            continue

        distractors.append(candidate_meaning)
        seen_options.add(normalized_meaning)

        if len(distractors) == count:
            break

    return distractors


def get_safe_distractors_for_meaning_to_term(
    target_entry: dict,
    candidate_entries: list[dict],
    count: int = 3,
) -> list[str]:
    target_meaning = normalize_answer_text(target_entry.get("meaning", ""))
    target_term = normalize_answer_text(target_entry.get("term", ""))
    distractors = []
    seen_options = {target_term}

    for candidate_entry in _shuffled(candidate_entries):
        if candidate_entry["id"] == target_entry["id"]:
            continue

        candidate_meaning = normalize_answer_text(candidate_entry.get("meaning", ""))
        if candidate_meaning == target_meaning:
            continue

        candidate_term = candidate_entry.get("term", "")
        normalized_term = normalize_answer_text(candidate_term)
        if not normalized_term or normalized_term in seen_options:
            continue

        distractors.append(candidate_term)
        seen_options.add(normalized_term)

        if len(distractors) == count:
            break

    return distractors


def generate_mcq_item(
    target_entry: dict,
    candidate_entries: list[dict],
    mode: str,
) -> dict | None:
    if mode not in MCQ_DIRECTIONS:
        raise ValueError(f"Unsupported MCQ direction: {mode}")

    quiz_config = MCQ_DIRECTIONS[mode]
    prompt_field = quiz_config["prompt_field"]
    answer_field = quiz_config["answer_field"]
    correct_answer = target_entry[answer_field]

    if mode == "term_to_meaning_mcq":
        distractor_options = get_safe_distractors_for_term_to_meaning(
            target_entry,
            candidate_entries,
        )
    else:
        distractor_options = get_safe_distractors_for_meaning_to_term(
            target_entry,
            candidate_entries,
        )

    if len(distractor_options) < 3:
        return None

    options = shuffle_mcq_options(correct_answer, distractor_options)

    return {
        "entry_id": target_entry["id"],
        "prompt": target_entry[prompt_field],
        "options": options,
        "correct_answer": correct_answer,
        "expected_answer": correct_answer,
        "quiz_type": mode,
        "direction": mode,
        "term": target_entry["term"],
        "meaning": target_entry["meaning"],
        "example": target_entry.get("example", ""),
    }


def generate_mcq_items_from_entries(
    target_entries: list[dict],
    candidate_entries: list[dict],
    mode: str,
) -> list[dict]:
    if mode not in {"term_to_meaning_mcq", "meaning_to_term_mcq", "mixed_mcq"}:
        raise ValueError(f"Unsupported MCQ mode: {mode}")

    generated_items = []

    shuffled_target_entries = _shuffled(target_entries)
    for target_entry in shuffled_target_entries:
        direction = mode
        if mode == "mixed_mcq":
            direction = _RANDOM.choice(list(MCQ_DIRECTIONS.keys()))

        generated_item = generate_mcq_item(target_entry, candidate_entries, direction)
        if generated_item is not None:
            generated_items.append(generated_item)

    if not generated_items:
        raise ValueError(MCQ_GENERATION_ERROR)

    return shuffle_quiz_items(
        generated_items,
        avoid_entry_id_order=[entry["id"] for entry in target_entries],
    )


def generate_mcq_items(
    collection_id: int,
    card_number: int,
    mode: str,
) -> list[dict]:
    if mode not in {"term_to_meaning_mcq", "meaning_to_term_mcq", "mixed_mcq"}:
        raise ValueError(f"Unsupported MCQ mode: {mode}")

    target_entries = get_entries_for_quiz(collection_id, card_number)
    if not target_entries:
        return []

    return generate_mcq_items_from_entries(target_entries, target_entries, mode)


def generate_random_quiz_items(
    collection_id: int,
    quiz_type: str,
    item_count: int,
) -> dict:
    _validate_quiz_type(quiz_type)

    if quiz_type == "matching":
        matching_quiz = generate_matching_items(collection_id, item_count)
        return {
            "quiz_items": matching_quiz["items"],
            "meaning_choices": matching_quiz["meaning_choices"],
            "warning": "",
        }

    sampled_entries = get_random_entries_from_collection(collection_id, item_count)

    if quiz_type in {"term_to_meaning", "meaning_to_term"}:
        return {
            "quiz_items": create_quiz_items(sampled_entries, quiz_type),
            "meaning_choices": None,
            "warning": "",
        }

    collection_entries = get_entries_in_collection(collection_id)
    quiz_items = generate_mcq_items_from_entries(
        sampled_entries,
        collection_entries,
        quiz_type,
    )
    warning = ""
    if len(quiz_items) < len(sampled_entries):
        warning = (
            "Some Proficient Pool items were skipped because there were not enough "
            "unambiguous distractors."
        )

    return {"quiz_items": quiz_items, "meaning_choices": None, "warning": warning}


def grade_mcq_answer(selected_option: str, correct_option: str) -> bool:
    return selected_option == correct_option


def generate_matching_items(collection_id: int, item_count: int) -> dict:
    if item_count < 2:
        raise ValueError("Matching quiz requires at least 2 items.")

    collection_entries = get_collection_entries_for_distractors(collection_id)

    if len(collection_entries) < 2:
        raise ValueError("Matching quiz requires at least 2 entries in the selected collection.")

    unique_meaning_entries = []
    seen_meanings = set()
    for entry in _shuffled(collection_entries):
        normalized_meaning = normalize_answer_text(entry.get("meaning", ""))
        if not normalized_meaning or normalized_meaning in seen_meanings:
            continue
        seen_meanings.add(normalized_meaning)
        unique_meaning_entries.append(entry)

    if len(unique_meaning_entries) < item_count:
        raise ValueError(
            f"The selected collection has only {len(unique_meaning_entries)} entries with unique meanings. Choose a smaller item count."
        )

    sampled_entries = _sample(unique_meaning_entries, item_count)
    meaning_choices = shuffle_sequence([entry["meaning"] for entry in sampled_entries])

    return {
        "items": [
            {
                "entry_id": entry["id"],
                "term": entry["term"],
                "expected_meaning": entry["meaning"],
            }
            for entry in sampled_entries
        ],
        "meaning_choices": meaning_choices,
    }


def get_proficient_pool_collection() -> dict | None:
    return get_system_collection_by_type_or_name("proficient_pool")


def is_proficient_pool_collection(collection_id: int | None) -> bool:
    if collection_id is None:
        return False

    proficient_pool = get_proficient_pool_collection()
    return proficient_pool is not None and int(proficient_pool["id"]) == int(collection_id)


def get_failed_proficient_pool_entries_for_session(session_id: int) -> list[dict]:
    session = get_quiz_session(session_id)
    if session is None or not is_proficient_pool_collection(session["collection_id"]):
        return []

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                qil.entry_id,
                e.term,
                e.meaning,
                qil.prompt,
                qil.expected_answer,
                qil.user_answer,
                qil.answered_at,
                EXISTS (
                    SELECT 1
                    FROM entry_collections ec
                    WHERE ec.entry_id = qil.entry_id
                      AND ec.collection_id = qs.collection_id
                ) AS currently_in_proficient_pool
            FROM quiz_item_logs qil
            JOIN quiz_sessions qs ON qs.id = qil.session_id
            JOIN entries e ON e.id = qil.entry_id
            WHERE qil.session_id = ?
              AND qil.is_correct = 0
            ORDER BY qil.answered_at ASC, qil.id ASC
            """,
            (session_id,),
        ).fetchall()

    return [
        {**dict(row), "currently_in_proficient_pool": bool(row["currently_in_proficient_pool"])}
        for row in rows
    ]


def get_proficient_pool_audit_rows() -> list[dict]:
    proficient_pool = get_proficient_pool_collection()
    if proficient_pool is None:
        return []

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                e.id AS entry_id,
                e.term,
                e.meaning,
                COALESCE(e.correct_count, 0) AS correct_count,
                COALESCE(e.wrong_count, 0) AS wrong_count,
                COALESCE(e.correct_count, 0) + COALESCE(e.wrong_count, 0) AS total_attempts,
                CASE
                    WHEN COALESCE(e.correct_count, 0) + COALESCE(e.wrong_count, 0) = 0 THEN 0
                    ELSE ROUND(
                        COALESCE(e.correct_count, 0) * 100.0 /
                        (COALESCE(e.correct_count, 0) + COALESCE(e.wrong_count, 0)),
                        1
                    )
                END AS accuracy_percentage,
                EXISTS (
                    SELECT 1
                    FROM entry_collections mb_ec
                    JOIN collections mb ON mb.id = mb_ec.collection_id
                    WHERE mb_ec.entry_id = e.id
                      AND mb.system_type = 'mistake_book'
                ) AS in_mistake_book,
                (
                    SELECT CASE WHEN qil.is_correct = 1 THEN 'Correct' ELSE 'Wrong' END
                    FROM quiz_item_logs qil
                    JOIN quiz_sessions qs ON qs.id = qil.session_id
                    WHERE qil.entry_id = e.id
                      AND qs.collection_id = ?
                    ORDER BY qil.answered_at DESC, qil.id DESC
                    LIMIT 1
                ) AS last_proficient_pool_result
            FROM entry_collections ec
            JOIN entries e ON e.id = ec.entry_id
            WHERE ec.collection_id = ?
            ORDER BY ec.position ASC, e.term ASC
            """,
            (proficient_pool["id"], proficient_pool["id"]),
        ).fetchall()

    return [
        {**dict(row), "in_mistake_book": bool(row["in_mistake_book"])}
        for row in rows
    ]


def grade_matching_answers(items: list[dict], user_matches: dict) -> list[dict]:
    results = []

    for item in items:
        entry_id = item["entry_id"]
        user_selected_meaning = user_matches.get(entry_id, "")
        expected_meaning = item["expected_meaning"]
        results.append(
            {
                "entry_id": entry_id,
                "term": item["term"],
                "expected_meaning": expected_meaning,
                "user_selected_meaning": user_selected_meaning,
                "is_correct": user_selected_meaning == expected_meaning,
            }
        )

    return results


"""Legacy Review scheduler compatibility APIs.

M11.2 removes all active UI and workflow call sites for these mutation and SRS
helpers. They remain isolated temporarily so existing installations and legacy
history can be inspected without destructive schema or data changes. Current
Card learning completion comes only from completed Card-scoped Quiz sessions.
"""

from datetime import date, datetime, timedelta, timezone

from src.collections import (
    get_card_groups_for_collection,
    get_collection_by_id,
    get_collections,
)
from src.db import get_connection


LEGACY_SRS_COMPATIBILITY_ONLY = True


RATINGS = {"Again", "Hard", "Good", "Easy"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today_iso(today: str | None = None) -> str:
    return today or date.today().isoformat()


def _entry_count_for_card(collection_id: int, card_number: int) -> int:
    for card_group in get_card_groups_for_collection(collection_id):
        if card_group["card_number"] == card_number:
            return len(card_group["entries"])
    return 0


def sync_card_review_states(collection_id: int) -> int:
    card_groups = get_card_groups_for_collection(collection_id)

    if not card_groups:
        return 0

    now = _now_iso()
    rows_to_insert = [
        (collection_id, card_group["card_number"], now, now)
        for card_group in card_groups
    ]

    with get_connection() as connection:
        cursor = connection.executemany(
            """
            INSERT OR IGNORE INTO card_review_states (
                collection_id,
                card_number,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            rows_to_insert,
        )

    return cursor.rowcount


def sync_all_card_review_states() -> int:
    return sum(
        sync_card_review_states(collection["id"])
        for collection in get_collections()
    )


def get_due_cards(today: str | None = None) -> list[dict]:
    due_today = _today_iso(today)
    sync_all_card_review_states()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                s.id,
                s.collection_id,
                c.name AS collection_name,
                c.card_size,
                s.card_number,
                s.status,
                s.review_count,
                s.current_interval_days,
                s.ease_factor,
                s.next_due_at,
                s.created_at,
                s.updated_at
            FROM card_review_states s
            JOIN collections c ON c.id = s.collection_id
            WHERE s.next_due_at IS NULL
               OR s.next_due_at <= ?
            ORDER BY s.next_due_at IS NOT NULL, s.next_due_at, c.name, s.card_number
            """,
            (due_today,),
        ).fetchall()

    due_cards = []
    for row in rows:
        card = dict(row)
        card["entry_count"] = _entry_count_for_card(
            card["collection_id"],
            card["card_number"],
        )
        if card["entry_count"] > 0:
            due_cards.append(card)

    return due_cards


def get_due_cards_for_collection(
    collection_id: int,
    today: str | None = None,
) -> list[dict]:
    return [
        card for card in get_due_cards(today)
        if card["collection_id"] == collection_id
    ]


def get_card_review_state(collection_id: int, card_number: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                collection_id,
                card_number,
                status,
                review_count,
                current_interval_days,
                ease_factor,
                next_due_at,
                created_at,
                updated_at
            FROM card_review_states
            WHERE collection_id = ?
              AND card_number = ?
            """,
            (collection_id, card_number),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def calculate_direct_schedule(
    days_until_next_review: int,
    today: str | None = None,
) -> dict:
    if days_until_next_review < 0:
        raise ValueError("days_until_next_review must be 0 or greater")

    due_from = date.fromisoformat(_today_iso(today))
    next_due_at = (due_from + timedelta(days=days_until_next_review)).isoformat()

    if days_until_next_review >= 30:
        status = "mastered"
    elif days_until_next_review >= 7:
        status = "familiar"
    else:
        status = "learning"

    return {
        "new_interval_days": days_until_next_review,
        "next_due_at": next_due_at,
        "status": status,
    }


def schedule_card_review(
    collection_id: int,
    card_number: int,
    days_until_next_review: int,
    action_label: str,
) -> dict:
    sync_card_review_states(collection_id)
    state = get_card_review_state(collection_id, card_number)

    if state is None:
        raise ValueError("Review state does not exist for this card")

    entry_count = _entry_count_for_card(collection_id, card_number)
    if entry_count <= 0:
        raise ValueError("Cannot review an empty card")

    previous_interval_days = state["current_interval_days"]
    previous_due_at = state["next_due_at"]
    next_review = calculate_direct_schedule(days_until_next_review)
    reviewed_at = _now_iso()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE card_review_states
            SET
                status = ?,
                review_count = review_count + 1,
                current_interval_days = ?,
                next_due_at = ?,
                updated_at = ?
            WHERE collection_id = ?
              AND card_number = ?
            """,
            (
                next_review["status"],
                next_review["new_interval_days"],
                next_review["next_due_at"],
                reviewed_at,
                collection_id,
                card_number,
            ),
        )
        connection.execute(
            """
            INSERT INTO card_review_logs (
                collection_id,
                card_number,
                reviewed_at,
                rating,
                previous_interval_days,
                new_interval_days,
                previous_due_at,
                next_due_at,
                entry_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                collection_id,
                card_number,
                reviewed_at,
                action_label,
                previous_interval_days,
                next_review["new_interval_days"],
                previous_due_at,
                next_review["next_due_at"],
                entry_count,
            ),
        )

    updated_state = get_card_review_state(collection_id, card_number)
    collection = get_collection_by_id(collection_id)

    return {
        "collection_id": collection_id,
        "collection_name": collection["name"] if collection else "",
        "card_number": card_number,
        "entry_count": entry_count,
        "action_label": action_label,
        "previous_interval_days": previous_interval_days,
        "new_interval_days": next_review["new_interval_days"],
        "previous_due_at": previous_due_at,
        "next_due_at": next_review["next_due_at"],
        "status": next_review["status"],
        "state": updated_state,
    }


def update_card_next_due_at(
    collection_id: int,
    card_number: int,
    next_due_at: str,
) -> dict:
    sync_card_review_states(collection_id)
    state = get_card_review_state(collection_id, card_number)

    if state is None:
        raise ValueError("Review state does not exist for this card")

    entry_count = _entry_count_for_card(collection_id, card_number)
    if entry_count <= 0:
        raise ValueError("Cannot update an empty card")

    try:
        date.fromisoformat(next_due_at)
    except ValueError as error:
        raise ValueError("next_due_at must use YYYY-MM-DD format") from error

    previous_interval_days = state["current_interval_days"]
    previous_due_at = state["next_due_at"]
    updated_at = _now_iso()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE card_review_states
            SET
                next_due_at = ?,
                updated_at = ?
            WHERE collection_id = ?
              AND card_number = ?
            """,
            (next_due_at, updated_at, collection_id, card_number),
        )
        connection.execute(
            """
            INSERT INTO card_review_logs (
                collection_id,
                card_number,
                reviewed_at,
                rating,
                previous_interval_days,
                new_interval_days,
                previous_due_at,
                next_due_at,
                entry_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                collection_id,
                card_number,
                updated_at,
                "manual_schedule_update",
                previous_interval_days,
                previous_interval_days,
                previous_due_at,
                next_due_at,
                entry_count,
            ),
        )

    updated_state = get_card_review_state(collection_id, card_number)
    collection = get_collection_by_id(collection_id)

    return {
        "collection_id": collection_id,
        "collection_name": collection["name"] if collection else "",
        "card_number": card_number,
        "entry_count": entry_count,
        "previous_due_at": previous_due_at,
        "next_due_at": next_due_at,
        "state": updated_state,
    }
def calculate_next_review(
    previous_interval_days: int,
    ease_factor: float,
    rating: str,
    today: str | None = None,
) -> dict:
    if rating not in RATINGS:
        raise ValueError("rating must be one of: Again, Hard, Good, Easy")

    if rating == "Again":
        new_interval_days = 1
        new_ease_factor = max(1.3, ease_factor - 0.2)
        status = "learning"
    elif rating == "Hard":
        if previous_interval_days <= 1:
            new_interval_days = 2
        else:
            new_interval_days = max(2, round(previous_interval_days * 1.2))
        new_ease_factor = max(1.3, ease_factor - 0.1)
        status = "learning"
    elif rating == "Good":
        if previous_interval_days <= 0:
            new_interval_days = 3
        else:
            new_interval_days = round(previous_interval_days * ease_factor)
        new_ease_factor = ease_factor
        status = "familiar"
    else:
        if previous_interval_days <= 0:
            new_interval_days = 5
        else:
            new_interval_days = round(previous_interval_days * ease_factor * 1.3)
        new_ease_factor = ease_factor + 0.1
        status = "mastered"

    due_from = date.fromisoformat(_today_iso(today))
    next_due_at = (due_from + timedelta(days=new_interval_days)).isoformat()

    return {
        "new_interval_days": new_interval_days,
        "new_ease_factor": new_ease_factor,
        "next_due_at": next_due_at,
        "status": status,
    }


def review_card(collection_id: int, card_number: int, rating: str) -> dict:
    sync_card_review_states(collection_id)
    state = get_card_review_state(collection_id, card_number)

    if state is None:
        raise ValueError("Review state does not exist for this card")

    entry_count = _entry_count_for_card(collection_id, card_number)
    if entry_count <= 0:
        raise ValueError("Cannot review an empty card")

    previous_interval_days = state["current_interval_days"]
    previous_due_at = state["next_due_at"]
    next_review = calculate_next_review(
        previous_interval_days=previous_interval_days,
        ease_factor=state["ease_factor"],
        rating=rating,
    )
    reviewed_at = _now_iso()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE card_review_states
            SET
                status = ?,
                review_count = review_count + 1,
                current_interval_days = ?,
                ease_factor = ?,
                next_due_at = ?,
                updated_at = ?
            WHERE collection_id = ?
              AND card_number = ?
            """,
            (
                next_review["status"],
                next_review["new_interval_days"],
                next_review["new_ease_factor"],
                next_review["next_due_at"],
                reviewed_at,
                collection_id,
                card_number,
            ),
        )
        connection.execute(
            """
            INSERT INTO card_review_logs (
                collection_id,
                card_number,
                reviewed_at,
                rating,
                previous_interval_days,
                new_interval_days,
                previous_due_at,
                next_due_at,
                entry_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                collection_id,
                card_number,
                reviewed_at,
                rating,
                previous_interval_days,
                next_review["new_interval_days"],
                previous_due_at,
                next_review["next_due_at"],
                entry_count,
            ),
        )

    updated_state = get_card_review_state(collection_id, card_number)
    collection = get_collection_by_id(collection_id)

    return {
        "collection_id": collection_id,
        "collection_name": collection["name"] if collection else "",
        "card_number": card_number,
        "entry_count": entry_count,
        "rating": rating,
        "previous_interval_days": previous_interval_days,
        "new_interval_days": next_review["new_interval_days"],
        "previous_due_at": previous_due_at,
        "next_due_at": next_review["next_due_at"],
        "status": next_review["status"],
        "state": updated_state,
    }


def get_card_review_logs(collection_id: int, card_number: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                collection_id,
                card_number,
                reviewed_at,
                rating,
                previous_interval_days,
                new_interval_days,
                previous_due_at,
                next_due_at,
                entry_count
            FROM card_review_logs
            WHERE collection_id = ?
              AND card_number = ?
            ORDER BY reviewed_at DESC, id DESC
            """,
            (collection_id, card_number),
        ).fetchall()

    return [dict(row) for row in rows]

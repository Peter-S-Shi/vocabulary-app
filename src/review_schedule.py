"""Active user-managed review scheduling keyed by stable Card identity."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from src.db import get_connection


def _state_for(next_due_at: str | None, today: str) -> str:
    if next_due_at is None:
        return "unscheduled"
    if next_due_at < today:
        return "overdue"
    if next_due_at == today:
        return "due_today"
    return "upcoming"


def _today_iso(today: str | None) -> str:
    value = today or date.today().isoformat()
    date.fromisoformat(value)
    return value


def get_card_schedule(card_id: int, *, today: str | None = None) -> dict:
    today_iso = _today_iso(today)
    with get_connection() as conn:
        card = conn.execute(
            """
            SELECT cards.id AS card_id, cards.collection_id, cards.card_number,
                   cards.is_active, collections.name AS collection_name,
                   schedules.next_due_at,
                   (
                       SELECT COUNT(*)
                       FROM card_revision_entries AS membership
                       JOIN card_revisions AS revision ON revision.id = membership.revision_id
                       WHERE revision.card_id = cards.id
                         AND revision.revision_number = (
                             SELECT MAX(latest.revision_number)
                             FROM card_revisions AS latest
                             WHERE latest.card_id = cards.id
                         )
                   ) AS entry_count
            FROM cards
            JOIN collections ON collections.id = cards.collection_id
            LEFT JOIN card_review_schedules AS schedules ON schedules.card_id = cards.id
            WHERE cards.id = ?
            """,
            (int(card_id),),
        ).fetchone()
    if card is None:
        raise ValueError("Card not found.")
    result = dict(card)
    result["state"] = (
        _state_for(result["next_due_at"], today_iso)
        if int(result["is_active"])
        else "retired"
    )
    return result


def set_card_next_review(
    card_id: int,
    next_due_at: str,
    *,
    today: str | None = None,
) -> dict:
    _today_iso(next_due_at)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as conn:
        card = conn.execute(
            "SELECT id, is_active FROM cards WHERE id = ?",
            (int(card_id),),
        ).fetchone()
        if card is None or not int(card["is_active"]):
            raise ValueError("Active Card not found.")
        conn.execute(
            """
            INSERT INTO card_review_schedules (card_id, next_due_at, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(card_id) DO UPDATE SET
                next_due_at = excluded.next_due_at,
                updated_at = excluded.updated_at
            """,
            (int(card_id), next_due_at, now, now),
        )
    return get_card_schedule(card_id, today=today)


def clear_card_schedule(card_id: int, *, today: str | None = None) -> dict:
    with get_connection() as conn:
        card = conn.execute(
            "SELECT id, is_active FROM cards WHERE id = ?",
            (int(card_id),),
        ).fetchone()
        if card is None or not int(card["is_active"]):
            raise ValueError("Active Card not found.")
        conn.execute(
            "DELETE FROM card_review_schedules WHERE card_id = ?",
            (int(card_id),),
        )
    return get_card_schedule(card_id, today=today)


def schedule_card_after_days(
    card_id: int,
    days: int,
    *,
    today: str | None = None,
) -> dict:
    if days < 0:
        raise ValueError("days must be 0 or greater.")
    today_iso = _today_iso(today)
    next_due_at = (date.fromisoformat(today_iso) + timedelta(days=days)).isoformat()
    return set_card_next_review(card_id, next_due_at, today=today_iso)


def list_actionable_schedules(*, today: str | None = None) -> list[dict]:
    today_iso = _today_iso(today)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cards.id AS card_id, cards.collection_id, cards.card_number,
                   cards.is_active, collections.name AS collection_name,
                   schedules.next_due_at,
                   (
                       SELECT COUNT(*)
                       FROM card_revision_entries AS membership
                       JOIN card_revisions AS revision ON revision.id = membership.revision_id
                       WHERE revision.card_id = cards.id
                         AND revision.revision_number = (
                             SELECT MAX(latest.revision_number)
                             FROM card_revisions AS latest
                             WHERE latest.card_id = cards.id
                         )
                   ) AS entry_count
            FROM card_review_schedules AS schedules
            JOIN cards ON cards.id = schedules.card_id
            JOIN collections ON collections.id = cards.collection_id
            WHERE cards.is_active = 1
              AND DATE(schedules.next_due_at) <= DATE(?)
            ORDER BY DATE(schedules.next_due_at), collections.name, cards.card_number
            """,
            (today_iso,),
        ).fetchall()
    schedules = [dict(row) for row in rows]
    for schedule in schedules:
        schedule["state"] = _state_for(schedule["next_due_at"], today_iso)
    return schedules


def list_card_schedules(*, today: str | None = None) -> list[dict]:
    today_iso = _today_iso(today)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cards.id AS card_id, cards.collection_id, cards.card_number,
                   cards.is_active, collections.name AS collection_name,
                   schedules.next_due_at,
                   (
                       SELECT COUNT(*)
                       FROM card_revision_entries AS membership
                       JOIN card_revisions AS revision ON revision.id = membership.revision_id
                       WHERE revision.card_id = cards.id
                         AND revision.revision_number = (
                             SELECT MAX(latest.revision_number)
                             FROM card_revisions AS latest
                             WHERE latest.card_id = cards.id
                         )
                   ) AS entry_count
            FROM cards
            JOIN collections ON collections.id = cards.collection_id
            LEFT JOIN card_review_schedules AS schedules ON schedules.card_id = cards.id
            WHERE cards.is_active = 1
            ORDER BY collections.name, cards.card_number
            """
        ).fetchall()
    schedules = [dict(row) for row in rows]
    for schedule in schedules:
        schedule["state"] = _state_for(schedule["next_due_at"], today_iso)
    return schedules

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from sqlite3 import Connection
from typing import Iterable

from src.card_history import (
    get_card_revision_entry_ids,
    get_current_card_identity,
    get_quiz_session_card_revision,
)


EVIDENCE_STATE_ORDER = {
    "none": 0,
    "sparse": 1,
    "developing": 2,
    "sufficient": 3,
    "strong": 4,
}
MAX_RECENT_ATTEMPTS = 5
MAX_BASELINE_ATTEMPTS = 50


def _to_date(value: str | date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    normalized = str(value).strip().replace("Z", "+00:00")
    if not normalized:
        raise ValueError("A non-empty ISO date or datetime is required.")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return date.fromisoformat(normalized[:10])


def _event_date(event: dict) -> date:
    return _to_date(event["answered_at"])


def _accuracy(correct: int, attempts: int) -> float | None:
    return None if attempts <= 0 else correct / attempts


def _evidence_state(attempts: int, sessions: int, days: int) -> str:
    if attempts == 0:
        return "none"
    if attempts >= 8 and sessions >= 4 and days >= 2:
        return "strong"
    if attempts >= 5 and sessions >= 3:
        return "sufficient"
    if attempts >= 3 and sessions >= 2:
        return "developing"
    return "sparse"


def _performance_state(accuracy: float | None, eligible: bool) -> str:
    if not eligible or accuracy is None:
        return "unavailable"
    if accuracy >= 0.80:
        return "positive"
    if accuracy >= 0.60:
        return "mixed"
    return "negative"


def _window_profile(events: list[dict]) -> dict:
    attempts = len(events)
    correct = sum(int(event["is_correct"]) for event in events)
    sessions = len({int(event["session_id"]) for event in events})
    eligible = attempts >= 3 and sessions >= 2
    accuracy = _accuracy(correct, attempts)
    return {
        "attempts": attempts,
        "correct": correct,
        "wrong": attempts - correct,
        "accuracy": accuracy,
        "distinct_sessions": sessions,
        "eligible": eligible,
        "performance": _performance_state(accuracy, eligible),
    }


def _trajectory(recent: dict, prior: dict) -> tuple[str, float | None]:
    if not recent["eligible"] or not prior["eligible"]:
        return "unavailable", None
    delta_pp = round((recent["accuracy"] - prior["accuracy"]) * 100, 10)
    if delta_pp >= 20:
        return "improving", delta_pp
    if delta_pp <= -20:
        return "declining", delta_pp
    return "stable", delta_pp


def _load_current_entry_metadata(conn: Connection) -> dict[int, dict]:
    rows = conn.execute(
        """
        SELECT
            entries.id AS entry_id,
            entries.language,
            entries.template_id,
            GROUP_CONCAT(entry_collections.collection_id) AS collection_ids,
            MAX(CASE WHEN collections.system_type = 'mistake_book' THEN 1 ELSE 0 END)
                AS in_mistake_book,
            MAX(CASE WHEN collections.system_type = 'proficient_pool' THEN 1 ELSE 0 END)
                AS in_proficient_pool,
            MAX(CASE WHEN collections.system_type = 'starred' THEN 1 ELSE 0 END)
                AS in_starred
        FROM entries
        LEFT JOIN entry_collections ON entry_collections.entry_id = entries.id
        LEFT JOIN collections ON collections.id = entry_collections.collection_id
        GROUP BY entries.id
        ORDER BY entries.id
        """
    ).fetchall()

    metadata: dict[int, dict] = {}
    for row in rows:
        item = dict(row)
        raw_collection_ids = item.pop("collection_ids") or ""
        item["collection_ids"] = sorted(
            {int(value) for value in raw_collection_ids.split(",") if value}
        )
        for flag in ("in_mistake_book", "in_proficient_pool", "in_starred"):
            item[flag] = bool(item[flag])
        metadata[int(item["entry_id"])] = item
    return metadata


def load_eligible_evidence_events(
    conn: Connection,
    *,
    entry_ids: Iterable[int] | None = None,
    as_of_date: str | date | datetime | None = None,
) -> list[dict]:
    """Load current-Entry Quiz evidence in deterministic chronological order.

    Explicitly answered Items remain eligible even when their parent session is
    active or cancelled. The session status is returned as context only.
    """

    params: list[object] = []
    entry_filter = ""
    if entry_ids is not None:
        normalized_ids = sorted({int(entry_id) for entry_id in entry_ids})
        if not normalized_ids:
            return []
        placeholders = ", ".join("?" for _ in normalized_ids)
        entry_filter = f"AND quiz_item_logs.entry_id IN ({placeholders})"
        params.extend(normalized_ids)

    rows = conn.execute(
        f"""
        SELECT
            quiz_item_logs.id AS log_id,
            quiz_item_logs.entry_id,
            quiz_item_logs.session_id,
            quiz_item_logs.answered_at,
            quiz_item_logs.is_correct,
            quiz_sessions.collection_id,
            quiz_sessions.card_number,
            quiz_sessions.card_id,
            quiz_sessions.card_revision_id,
            quiz_sessions.status AS session_status
        FROM quiz_item_logs
        JOIN entries ON entries.id = quiz_item_logs.entry_id
        JOIN quiz_sessions ON quiz_sessions.id = quiz_item_logs.session_id
        WHERE quiz_item_logs.is_correct IN (0, 1)
        {entry_filter}
        ORDER BY quiz_item_logs.answered_at ASC, quiz_item_logs.id ASC
        """,
        tuple(params),
    ).fetchall()

    reference_date = _to_date(as_of_date)
    events = [dict(row) for row in rows]
    return [event for event in events if _event_date(event) <= reference_date]


def _excluded_entry_ids(
    metadata: dict[int, dict],
    target_scope_type: str,
    target_scope_id: int | None,
) -> set[int]:
    if target_scope_type not in {"entry", "collection", "template"}:
        raise ValueError("target_scope_type must be entry, collection, or template")
    if target_scope_id is None:
        raise ValueError("target_scope_id is required")

    scope_id = int(target_scope_id)
    if target_scope_type == "entry":
        return {scope_id}
    if target_scope_type == "collection":
        return {
            entry_id
            for entry_id, item in metadata.items()
            if scope_id in item["collection_ids"]
        }
    return {
        entry_id
        for entry_id, item in metadata.items()
        if item["template_id"] is not None and int(item["template_id"]) == scope_id
    }


def _personal_baseline_from_loaded(
    metadata: dict[int, dict],
    events: list[dict],
    *,
    language: str,
    target_accuracy: float | None,
    target_scope_type: str,
    target_scope_id: int,
) -> dict:
    excluded_ids = _excluded_entry_ids(
        metadata,
        target_scope_type,
        target_scope_id,
    )
    comparator_events = []
    for event in reversed(events):
        entry_id = int(event["entry_id"])
        if entry_id in excluded_ids or metadata[entry_id]["language"] != language:
            continue
        comparator_events.append(event)
        if len(comparator_events) == MAX_BASELINE_ATTEMPTS:
            break
    comparator_events.reverse()

    attempts = len(comparator_events)
    correct = sum(int(event["is_correct"]) for event in comparator_events)
    sessions = len({int(event["session_id"]) for event in comparator_events})
    days = len({_event_date(event) for event in comparator_events})
    accuracy = _accuracy(correct, attempts)
    eligible = attempts >= 20 and sessions >= 5 and days >= 3
    comparison = "unavailable"
    delta_pp = None
    if eligible and target_accuracy is not None and accuracy is not None:
        delta_pp = round((target_accuracy - accuracy) * 100, 10)
        if delta_pp >= 15:
            comparison = "above_baseline"
        elif delta_pp <= -15:
            comparison = "below_baseline"
        else:
            comparison = "near_baseline"

    return {
        "eligible": eligible,
        "attempts": attempts,
        "correct": correct,
        "wrong": attempts - correct,
        "accuracy": accuracy,
        "distinct_sessions": sessions,
        "distinct_days": days,
        "comparison": comparison,
        "delta_pp": delta_pp,
        "target_scope_type": target_scope_type,
        "target_scope_id": int(target_scope_id),
        "excluded_entry_count": len(excluded_ids),
        "max_attempts": MAX_BASELINE_ATTEMPTS,
    }


def get_personal_baseline(
    conn: Connection,
    language: str,
    target_accuracy: float | None,
    *,
    target_scope_type: str,
    target_scope_id: int,
    as_of_date: str | date | datetime | None = None,
) -> dict:
    """Return a same-language comparator after excluding the current target scope."""

    metadata = _load_current_entry_metadata(conn)
    events = load_eligible_evidence_events(conn, as_of_date=as_of_date)
    return _personal_baseline_from_loaded(
        metadata,
        events,
        language=language,
        target_accuracy=target_accuracy,
        target_scope_type=target_scope_type,
        target_scope_id=target_scope_id,
    )


def _entry_profile(
    item: dict,
    events: list[dict],
    all_metadata: dict[int, dict],
    all_events: list[dict],
    reference_date: date,
) -> dict:
    attempts = len(events)
    correct = sum(int(event["is_correct"]) for event in events)
    sessions = len({int(event["session_id"]) for event in events})
    days = len({_event_date(event) for event in events})
    accuracy = _accuracy(correct, attempts)
    evidence_state = _evidence_state(attempts, sessions, days)

    recent_events = events[-MAX_RECENT_ATTEMPTS:]
    prior_events = events[-(MAX_RECENT_ATTEMPTS * 2):-MAX_RECENT_ATTEMPTS]
    recent = _window_profile(recent_events)
    prior = _window_profile(prior_events)
    trajectory, trajectory_delta_pp = _trajectory(recent, prior)

    if events:
        first_attempt_at = events[0]["answered_at"]
        last_attempt_at = events[-1]["answered_at"]
        last_attempt_age_days = (reference_date - _event_date(events[-1])).days
        if last_attempt_age_days <= 30:
            freshness = "fresh"
        elif last_attempt_age_days <= 89:
            freshness = "aging"
        else:
            freshness = "stale"
    else:
        first_attempt_at = None
        last_attempt_at = None
        last_attempt_age_days = None
        freshness = "unavailable"

    recent_wrong_sessions = {
        int(event["session_id"])
        for event in recent_events
        if int(event["is_correct"]) == 0
    }
    recent_correct_sessions = {
        int(event["session_id"])
        for event in recent_events
        if int(event["is_correct"]) == 1
    }
    repeated_recent_errors = (
        recent["eligible"]
        and recent["wrong"] >= 3
        and len(recent_wrong_sessions) >= 2
    )
    repeated_recent_success = (
        recent["eligible"]
        and recent["correct"] >= 4
        and len(recent_correct_sessions) >= 2
    )
    overall_eligible = EVIDENCE_STATE_ORDER[evidence_state] >= EVIDENCE_STATE_ORDER["sufficient"]

    profile = {
        **item,
        "as_of_date": reference_date.isoformat(),
        "attempts": attempts,
        "correct": correct,
        "wrong": attempts - correct,
        "accuracy": accuracy,
        "distinct_sessions": sessions,
        "distinct_days": days,
        "first_attempt_at": first_attempt_at,
        "last_attempt_at": last_attempt_at,
        "last_attempt_age_days": last_attempt_age_days,
        "evidence_state": evidence_state,
        "freshness": freshness,
        "recent": recent,
        "prior": prior,
        "overall_performance": _performance_state(accuracy, overall_eligible),
        "trajectory": trajectory,
        "trajectory_delta_pp": trajectory_delta_pp,
        "repeated_recent_errors": repeated_recent_errors,
        "repeated_recent_success": repeated_recent_success,
    }
    profile["baseline"] = _personal_baseline_from_loaded(
        all_metadata,
        all_events,
        language=item["language"],
        target_accuracy=accuracy,
        target_scope_type="entry",
        target_scope_id=int(item["entry_id"]),
    )
    return profile


def get_entry_evidence_profiles(
    conn: Connection,
    *,
    as_of_date: str | date | datetime | None = None,
    language: str | None = None,
    template_id: int | None = None,
    collection_id: int | None = None,
) -> list[dict]:
    metadata = _load_current_entry_metadata(conn)
    events = load_eligible_evidence_events(conn, as_of_date=as_of_date)
    events_by_entry: dict[int, list[dict]] = defaultdict(list)
    for event in events:
        events_by_entry[int(event["entry_id"])].append(event)

    selected = []
    for item in metadata.values():
        if language is not None and item["language"] != language:
            continue
        if template_id is not None and item["template_id"] != int(template_id):
            continue
        if collection_id is not None and int(collection_id) not in item["collection_ids"]:
            continue
        selected.append(item)

    reference_date = _to_date(as_of_date)
    return [
        _entry_profile(
            item,
            events_by_entry[int(item["entry_id"])],
            metadata,
            events,
            reference_date,
        )
        for item in selected
    ]


def get_entry_evidence_profile(
    conn: Connection,
    entry_id: int,
    *,
    as_of_date: str | date | datetime | None = None,
) -> dict | None:
    metadata = _load_current_entry_metadata(conn)
    item = metadata.get(int(entry_id))
    if item is None:
        return None
    events = load_eligible_evidence_events(conn, as_of_date=as_of_date)
    entry_events = [
        event for event in events if int(event["entry_id"]) == int(entry_id)
    ]
    return _entry_profile(
        item,
        entry_events,
        metadata,
        events,
        _to_date(as_of_date),
    )


def _coverage_state(ratio: float | None, boundaries: tuple[float, float]) -> str:
    if ratio is None:
        return "unavailable"
    if ratio == 0:
        return "none"
    if ratio < boundaries[0]:
        return "limited"
    if ratio < boundaries[1]:
        return "partial"
    return "broad" if boundaries == (0.50, 0.80) else "substantial"


def _coverage_profile(
    profiles: list[dict],
    *,
    scope_type: str,
    scope_id: int | None,
    extra: dict | None = None,
) -> dict:
    total = len(profiles)
    touched = sum(1 for profile in profiles if profile["attempts"] >= 1)
    interpretable = sum(
        1
        for profile in profiles
        if EVIDENCE_STATE_ORDER[profile["evidence_state"]]
        >= EVIDENCE_STATE_ORDER["sufficient"]
    )
    touched_ratio = _accuracy(touched, total)
    interpretable_ratio = _accuracy(interpretable, total)
    result = {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "total_current_entries": total,
        "touched_count": touched,
        "touched_ratio": touched_ratio,
        "touched_state": _coverage_state(touched_ratio, (0.50, 0.80)),
        "touched_complete": total > 0 and touched == total,
        "interpretable_count": interpretable,
        "interpretable_ratio": interpretable_ratio,
        "interpretable_state": _coverage_state(interpretable_ratio, (0.30, 0.60)),
        "interpretable_complete": total > 0 and interpretable == total,
        "never_quizzed_count": total - touched,
        "never_quizzed_ratio": None if total == 0 else (total - touched) / total,
    }
    if extra:
        result.update(extra)
    return result


def get_collection_scope_activity_profile(
    conn: Connection,
    collection_id: int,
    *,
    as_of_date: str | date | datetime | None = None,
) -> dict:
    current_entry_ids = {
        int(row[0])
        for row in conn.execute(
            "SELECT entry_id FROM entry_collections WHERE collection_id = ?",
            (int(collection_id),),
        ).fetchall()
    }
    events = [
        event
        for event in load_eligible_evidence_events(
            conn,
            entry_ids=current_entry_ids,
            as_of_date=as_of_date,
        )
        if int(event["collection_id"]) == int(collection_id)
    ]
    return {
        "collection_id": int(collection_id),
        "eligible_attempts": len(events),
        "distinct_entries": len({int(event["entry_id"]) for event in events}),
        "distinct_sessions": len({int(event["session_id"]) for event in events}),
    }


def get_collection_coverage_profile(
    conn: Connection,
    collection_id: int,
    *,
    as_of_date: str | date | datetime | None = None,
) -> dict:
    profiles = get_entry_evidence_profiles(
        conn,
        as_of_date=as_of_date,
        collection_id=int(collection_id),
    )
    activity = get_collection_scope_activity_profile(
        conn,
        int(collection_id),
        as_of_date=as_of_date,
    )
    return _coverage_profile(
        profiles,
        scope_type="collection",
        scope_id=int(collection_id),
        extra={"scope_activity": activity},
    )


def get_template_coverage_profile(
    conn: Connection,
    template_id: int,
    *,
    as_of_date: str | date | datetime | None = None,
) -> dict:
    profiles = get_entry_evidence_profiles(
        conn,
        as_of_date=as_of_date,
        template_id=int(template_id),
    )
    return _coverage_profile(
        profiles,
        scope_type="template",
        scope_id=int(template_id),
    )


def get_card_coverage_profile(
    conn: Connection,
    collection_id: int,
    card_number: int,
    *,
    as_of_date: str | date | datetime | None = None,
) -> dict:
    collection = conn.execute(
        "SELECT card_size FROM collections WHERE id = ?",
        (int(collection_id),),
    ).fetchone()
    if collection is None:
        raise ValueError("Collection not found.")
    if int(card_number) < 1:
        raise ValueError("card_number must be at least 1")

    card_size = max(int(collection["card_size"]), 1)
    start_position = (int(card_number) - 1) * card_size + 1
    end_position = start_position + card_size - 1
    entry_ids = {
        int(row[0])
        for row in conn.execute(
            """
            SELECT entry_id
            FROM entry_collections
            WHERE collection_id = ?
              AND position BETWEEN ? AND ?
            ORDER BY position, entry_id
            """,
            (int(collection_id), start_position, end_position),
        ).fetchall()
    }
    profiles = [
        profile
        for profile in get_entry_evidence_profiles(conn, as_of_date=as_of_date)
        if int(profile["entry_id"]) in entry_ids
    ]
    identity = get_current_card_identity(conn, int(collection_id), int(card_number))
    return _coverage_profile(
        profiles,
        scope_type="card",
        scope_id=None if identity is None else int(identity["card_id"]),
        extra={
            "collection_id": int(collection_id),
            "card_number": int(card_number),
            "card_revision_id": None
            if identity is None
            else int(identity["card_revision_id"]),
        },
    )


def get_historical_card_evidence_context(conn: Connection, session_id: int) -> dict | None:
    """Resolve historical Card membership only from the stored revision identity."""

    session = get_quiz_session_card_revision(conn, int(session_id))
    if session is None:
        return None
    revision_id = session.get("card_revision_id")
    if revision_id is None:
        return {
            **session,
            "entry_ids": [],
            "membership_known": False,
            "membership_source": "unknown_legacy_composition",
        }
    return {
        **session,
        "entry_ids": get_card_revision_entry_ids(conn, int(revision_id)),
        "membership_known": True,
        "membership_source": "historical_card_revision",
    }

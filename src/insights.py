from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from sqlite3 import Connection
from typing import Iterable

from src.analytics import (
    EVIDENCE_STATE_ORDER,
    get_card_coverage_profile,
    get_collection_coverage_profile,
    get_entry_evidence_profiles,
    get_template_coverage_profile,
)


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
FINDING_ORDER = {
    "needs_attention": 0,
    "coverage_gap": 1,
    "stale_evidence": 2,
    "never_quizzed": 3,
    "insufficient_evidence": 3,
    "recovery": 4,
    "strength": 5,
    "none": 6,
}
BRIEF_CAPS = {
    "needs_attention": 3,
    "coverage_gap": 2,
    "stale_evidence": 2,
    "evidence_gap": 1,
    "recovery": 2,
    "strength": 1,
}


def _context_flags(profile: dict) -> dict:
    return {
        "in_mistake_book": bool(profile["in_mistake_book"]),
        "in_proficient_pool": bool(profile["in_proficient_pool"]),
        "in_starred": bool(profile["in_starred"]),
    }


def _pool_reason_codes(primary_finding: str, context: dict) -> list[str]:
    reasons = []
    if primary_finding == "strength" and context["in_mistake_book"]:
        reasons.extend(["mistake_book_context", "pool_conflict"])
    if primary_finding == "needs_attention" and context["in_proficient_pool"]:
        reasons.extend(["proficient_pool_conflict", "pool_conflict"])
    return reasons


def _entry_finding(profile: dict) -> dict:
    evidence_state = profile["evidence_state"]
    freshness = profile["freshness"]
    recent = profile["recent"]
    prior = profile["prior"]
    trajectory = profile["trajectory"]
    context = _context_flags(profile)
    historical_context = None

    if profile["attempts"] == 0:
        primary = "never_quizzed"
        priority = "low"
        reasons = ["no_eligible_attempts"]
        action_type = "collect_quiz_evidence"
    elif EVIDENCE_STATE_ORDER[evidence_state] < EVIDENCE_STATE_ORDER["sufficient"]:
        primary = "insufficient_evidence"
        priority = "low"
        reasons = ["evidence_below_sufficient"]
        action_type = "collect_more_evidence"
    elif freshness == "stale":
        primary = "stale_evidence"
        priority = "medium"
        reasons = ["evidence_stale"]
        action_type = "verify_knowledge"
        historical_context = {
            "previous_performance": profile["overall_performance"],
            "historical_trajectory": trajectory,
            "recent_performance": recent["performance"],
        }
    elif (
        prior["eligible"]
        and recent["eligible"]
        and prior["performance"] == "negative"
        and recent["performance"] == "positive"
        and trajectory == "improving"
        and profile["repeated_recent_success"]
    ):
        primary = "recovery"
        priority = "low"
        reasons = [
            "prior_negative_performance",
            "recent_positive_performance",
            "improving_trajectory",
            "repeated_recent_success",
        ]
        action_type = "continue_practice"
    elif (
        recent["eligible"]
        and recent["performance"] == "negative"
        and profile["repeated_recent_errors"]
    ):
        primary = "needs_attention"
        reasons = ["recent_negative_performance", "repeated_recent_errors"]
        if trajectory == "declining":
            reasons.append("declining_trajectory")
        if prior["performance"] == "positive":
            reasons.append("previously_positive")
        if profile["baseline"]["comparison"] == "below_baseline":
            reasons.append("below_personal_baseline")
        priority = (
            "high"
            if freshness == "fresh"
            and (trajectory == "declining" or recent["wrong"] >= 4)
            else "medium"
        )
        action_type = "focused_practice"
    elif (
        evidence_state == "strong"
        and profile["overall_performance"] == "positive"
        and recent["performance"] == "positive"
        and profile["repeated_recent_success"]
        and trajectory != "declining"
    ):
        primary = "strength"
        priority = "low"
        reasons = [
            "strong_evidence",
            "positive_overall_performance",
            "positive_recent_performance",
            "repeated_recent_success",
        ]
        action_type = "none"
    else:
        primary = "none"
        priority = "low"
        reasons = []
        action_type = "none"

    reasons.extend(_pool_reason_codes(primary, context))
    finding = {
        "scope_type": "entry",
        "scope_id": int(profile["entry_id"]),
        "primary_finding": primary,
        "priority": priority,
        "evidence_state": evidence_state,
        "freshness": freshness,
        "reason_codes": reasons,
        "metrics": {
            "attempts": int(profile["attempts"]),
            "accuracy": profile["accuracy"],
            "recent_accuracy": recent["accuracy"],
            "prior_accuracy": prior["accuracy"],
            "trajectory_delta_pp": profile["trajectory_delta_pp"],
        },
        "context": context,
        "suggested_action": {
            "action_type": action_type,
            "entry_ids": [int(profile["entry_id"])],
        },
    }
    if historical_context is not None:
        finding["historical_context"] = historical_context
    return finding


def get_entry_findings(
    conn: Connection,
    *,
    as_of_date: str | date | datetime | None = None,
    language: str | None = None,
    template_id: int | None = None,
    collection_id: int | None = None,
) -> list[dict]:
    """Return exactly one deterministic Primary Finding per current Entry."""

    profiles = get_entry_evidence_profiles(
        conn,
        as_of_date=as_of_date,
        language=language,
        template_id=template_id,
        collection_id=collection_id,
    )
    return [_entry_finding(profile) for profile in profiles]


def _coverage_finding(profile: dict) -> dict | None:
    touched = profile["touched_ratio"]
    interpretable = profile["interpretable_ratio"]
    if touched is None or interpretable is None:
        return None
    if touched < 0.80:
        gap_type = "breadth_gap"
        action_type = "quiz_uncovered_content"
        priority = "high" if touched < 0.50 else "medium"
        target_key = "uncovered_entry_ids"
    elif interpretable < 0.60:
        gap_type = "evidence_depth_gap"
        action_type = "deepen_evidence"
        priority = "medium" if interpretable < 0.30 else "low"
        target_key = "shallow_entry_ids"
    else:
        return None

    action = {
        "action_type": action_type,
        "scope_type": profile["scope_type"],
        "scope_id": profile["scope_id"],
        target_key: list(profile.get(target_key, [])),
    }
    finding = {
        "scope_type": profile["scope_type"],
        "scope_id": profile["scope_id"],
        "primary_finding": "coverage_gap",
        "coverage_gap_type": gap_type,
        "priority": priority,
        "reason_codes": [gap_type],
        "metrics": {
            "total_current_entries": profile["total_current_entries"],
            "touched_count": profile["touched_count"],
            "touched_ratio": touched,
            "interpretable_count": profile["interpretable_count"],
            "interpretable_ratio": interpretable,
        },
        "suggested_action": action,
    }
    for key in ("collection_id", "card_number", "card_revision_id"):
        if key in profile:
            finding[key] = profile[key]
    return finding


def _entry_ids_for_scope(conn: Connection, scope_type: str, scope_id: int) -> list[int]:
    if scope_type == "collection":
        rows = conn.execute(
            "SELECT entry_id FROM entry_collections WHERE collection_id = ? ORDER BY position, entry_id",
            (int(scope_id),),
        ).fetchall()
    elif scope_type == "template":
        rows = conn.execute(
            "SELECT id FROM entries WHERE template_id = ? ORDER BY id",
            (int(scope_id),),
        ).fetchall()
    else:
        raise ValueError("scope_type must be collection or template")
    return [int(row[0]) for row in rows]


def _add_coverage_targets(
    conn: Connection,
    profile: dict,
    *,
    as_of_date: str | date | datetime | None = None,
) -> dict:
    scope_type = profile["scope_type"]
    if scope_type == "card":
        collection_id = int(profile["collection_id"])
        card_number = int(profile["card_number"])
        card_size = int(conn.execute(
            "SELECT card_size FROM collections WHERE id = ?", (collection_id,)
        ).fetchone()[0])
        start = (card_number - 1) * max(card_size, 1) + 1
        rows = conn.execute(
            "SELECT entry_id FROM entry_collections WHERE collection_id = ? AND position BETWEEN ? AND ? ORDER BY position, entry_id",
            (collection_id, start, start + max(card_size, 1) - 1),
        ).fetchall()
        entry_ids = [int(row[0]) for row in rows]
    else:
        entry_ids = _entry_ids_for_scope(conn, scope_type, int(profile["scope_id"]))
    entry_profiles = {
        int(item["entry_id"]): item
        for item in get_entry_evidence_profiles(conn, as_of_date=as_of_date)
        if int(item["entry_id"]) in set(entry_ids)
    }
    return {
        **profile,
        "uncovered_entry_ids": [
            entry_id for entry_id in entry_ids
            if entry_id in entry_profiles and entry_profiles[entry_id]["attempts"] == 0
        ],
        "shallow_entry_ids": [
            entry_id for entry_id in entry_ids
            if entry_id in entry_profiles
            and entry_profiles[entry_id]["attempts"] >= 1
            and EVIDENCE_STATE_ORDER[entry_profiles[entry_id]["evidence_state"]]
            < EVIDENCE_STATE_ORDER["sufficient"]
        ],
    }


def get_scope_coverage_findings(
    conn: Connection,
    *,
    as_of_date: str | date | datetime | None = None,
    collection_id: int | None = None,
    template_id: int | None = None,
    include_cards: bool = True,
) -> list[dict]:
    """Return all current Card, Collection, and Template Coverage Gaps."""

    if collection_id is not None and template_id is not None:
        raise ValueError("Choose either collection_id or template_id, not both.")
    findings = []
    collections = []
    if template_id is None:
        collections = conn.execute(
            "SELECT id, card_size FROM collections WHERE COALESCE(is_system, 0) = 0 "
            + ("AND id = ? " if collection_id is not None else "")
            + "ORDER BY id",
            () if collection_id is None else (int(collection_id),),
        ).fetchall()
    for collection in collections:
        current_collection_id = int(collection["id"])
        profile = get_collection_coverage_profile(
            conn, current_collection_id, as_of_date=as_of_date
        )
        profile = _add_coverage_targets(conn, profile, as_of_date=as_of_date)
        finding = _coverage_finding(profile)
        if finding is not None:
            findings.append(finding)
        if include_cards:
            entry_count = int(conn.execute(
                "SELECT COUNT(*) FROM entry_collections WHERE collection_id = ?",
                (current_collection_id,),
            ).fetchone()[0])
            card_size = max(int(collection["card_size"]), 1)
            for card_number in range(1, (entry_count + card_size - 1) // card_size + 1):
                card_profile = get_card_coverage_profile(
                    conn, current_collection_id, card_number, as_of_date=as_of_date
                )
                card_profile = _add_coverage_targets(
                    conn, card_profile, as_of_date=as_of_date
                )
                card_finding = _coverage_finding(card_profile)
                if card_finding is not None:
                    findings.append(card_finding)

    templates = []
    if collection_id is None:
        templates = conn.execute(
            "SELECT id FROM entry_templates "
            + ("WHERE id = ? " if template_id is not None else "")
            + "ORDER BY id",
            () if template_id is None else (int(template_id),),
        ).fetchall()
    for template in templates:
        current_template_id = int(template["id"])
        profile = get_template_coverage_profile(
            conn, current_template_id, as_of_date=as_of_date
        )
        profile = _add_coverage_targets(conn, profile, as_of_date=as_of_date)
        finding = _coverage_finding(profile)
        if finding is not None:
            findings.append(finding)
    return findings


def get_all_findings(
    conn: Connection,
    *,
    as_of_date: str | date | datetime | None = None,
    collection_id: int | None = None,
    template_id: int | None = None,
) -> dict:
    entry_findings = get_entry_findings(
        conn,
        as_of_date=as_of_date,
        collection_id=collection_id,
        template_id=template_id,
    )
    coverage_findings = get_scope_coverage_findings(
        conn,
        as_of_date=as_of_date,
        collection_id=collection_id,
        template_id=template_id,
    )
    return {
        "entry_findings": entry_findings,
        "coverage_findings": coverage_findings,
        "full_findings": [*entry_findings, *coverage_findings],
    }


def _entry_card_contexts(
    conn: Connection,
    entry_ids: Iterable[int],
    *,
    collection_id: int | None = None,
) -> dict[int, dict]:
    normalized = sorted({int(entry_id) for entry_id in entry_ids})
    if not normalized:
        return {}
    placeholders = ", ".join("?" for _ in normalized)
    rows = conn.execute(
        f"""
        SELECT ec.entry_id, ec.collection_id, ec.position, c.card_size,
               cards.id AS card_id, cards.card_number
        FROM entry_collections ec
        JOIN collections c ON c.id = ec.collection_id
        LEFT JOIN cards ON cards.collection_id = ec.collection_id
             AND cards.card_number = ((ec.position - 1) / c.card_size) + 1
             AND cards.is_active = 1
        WHERE ec.entry_id IN ({placeholders})
          AND COALESCE(c.is_system, 0) = 0
          {"AND ec.collection_id = ?" if collection_id is not None else ""}
        ORDER BY ec.entry_id, ec.collection_id, cards.card_number, cards.id
        """,
        (*normalized, *(() if collection_id is None else (int(collection_id),))),
    ).fetchall()
    result = {}
    for row in rows:
        entry_id = int(row["entry_id"])
        if entry_id in result or row["card_id"] is None:
            continue
        result[entry_id] = {
            "card_id": int(row["card_id"]),
            "collection_id": int(row["collection_id"]),
            "card_number": int(row["card_number"]),
        }
    return result


def build_action_candidates(
    conn: Connection,
    findings: Iterable[dict],
    *,
    collection_id: int | None = None,
) -> list[dict]:
    """Build candidates without altering Full Findings.

    A scoped Brief uses the requested Collection's current Card context. A
    global Brief deterministically uses the lowest normal Collection/Card
    identity when an Entry currently belongs to more than one Collection.
    """

    findings = [dict(finding) for finding in findings]
    entry_findings = [item for item in findings if item["scope_type"] == "entry"]
    contexts = _entry_card_contexts(
        conn,
        [int(item["scope_id"]) for item in entry_findings],
        collection_id=collection_id,
    )
    cluster_groups = defaultdict(list)
    standalone = []
    for finding in entry_findings:
        if finding["primary_finding"] == "none":
            continue
        context = contexts.get(int(finding["scope_id"]))
        if context is None:
            standalone.append(finding)
            continue
        key = (
            context["card_id"],
            finding["primary_finding"],
            finding["suggested_action"]["action_type"],
        )
        cluster_groups[key].append((finding, context))

    candidates = []
    for members in cluster_groups.values():
        if len(members) == 1:
            finding, context = members[0]
            candidates.append({**finding, "card_context": context})
            continue
        member_findings = sorted(
            (item[0] for item in members),
            key=lambda item: int(item["scope_id"]),
        )
        context = members[0][1]
        priority = min(
            (item["priority"] for item in member_findings),
            key=lambda value: PRIORITY_ORDER[value],
        )
        entry_ids = sorted(int(item["scope_id"]) for item in member_findings)
        evidence_state = max(
            (item["evidence_state"] for item in member_findings),
            key=lambda value: EVIDENCE_STATE_ORDER[value],
        )
        recent_accuracies = [
            item.get("metrics", {}).get("recent_accuracy")
            for item in member_findings
            if item.get("metrics", {}).get("recent_accuracy") is not None
        ]
        recent_accuracy = min(recent_accuracies) if recent_accuracies else None
        candidates.append({
            "scope_type": "entry_cluster",
            "scope_id": context["card_id"],
            "primary_finding": member_findings[0]["primary_finding"],
            "priority": priority,
            "ranking_metadata": {
                "evidence_state": evidence_state,
                "recent_accuracy": recent_accuracy,
                "supporting_entry_count": len(member_findings),
            },
            "supporting_entry_ids": entry_ids,
            "card_context": context,
            "reason_codes": sorted({
                reason for item in member_findings for reason in item["reason_codes"]
            }),
            "suggested_action": {
                "action_type": member_findings[0]["suggested_action"]["action_type"],
                "entry_ids": entry_ids,
                "card_context": context,
            },
            "member_findings": member_findings,
        })
    candidates.extend(standalone)
    candidates.extend(item for item in findings if item["scope_type"] != "entry")
    return candidates


def _category(candidate: dict) -> str:
    primary = candidate["primary_finding"]
    if primary in {"never_quizzed", "insufficient_evidence"}:
        return "evidence_gap"
    return primary


def _brief_section(candidate: dict) -> str:
    primary = candidate["primary_finding"]
    if primary in {"needs_attention", "coverage_gap", "stale_evidence"}:
        return "focus_now"
    if primary in {"never_quizzed", "insufficient_evidence"}:
        return "building_evidence"
    return "progress"


def _stable_identity(candidate: dict) -> tuple:
    return (
        str(candidate["scope_type"]),
        -1 if candidate.get("scope_id") is None else int(candidate["scope_id"]),
        tuple(candidate.get("supporting_entry_ids", [])),
    )


def _rank_key(candidate: dict) -> tuple:
    metrics = candidate.get("metrics", {})
    ranking_metadata = candidate.get("ranking_metadata", {})
    severity = 0.0
    if candidate["primary_finding"] == "coverage_gap":
        severity = 1.0 - float(
            metrics["touched_ratio"]
            if candidate.get("coverage_gap_type") == "breadth_gap"
            else metrics["interpretable_ratio"]
        )
    elif candidate["primary_finding"] == "needs_attention":
        accuracy = ranking_metadata.get(
            "recent_accuracy", metrics.get("recent_accuracy")
        )
        severity = 0.0 if accuracy is None else 1.0 - float(accuracy)
    evidence_state = ranking_metadata.get(
        "evidence_state", candidate.get("evidence_state")
    )
    evidence_rank = -EVIDENCE_STATE_ORDER.get(evidence_state, 0)
    return (
        PRIORITY_ORDER[candidate["priority"]],
        FINDING_ORDER[candidate["primary_finding"]],
        -severity,
        evidence_rank,
        _stable_identity(candidate),
    )


def _suppress_redundant_coverage(candidates: list[dict]) -> list[dict]:
    parents = {
        int(item["scope_id"]): item
        for item in candidates
        if item["primary_finding"] == "coverage_gap"
        and item["scope_type"] == "collection"
        and item.get("scope_id") is not None
    }
    result = []
    for item in candidates:
        if item["primary_finding"] != "coverage_gap" or item["scope_type"] != "card":
            result.append(item)
            continue
        parent = parents.get(int(item["collection_id"]))
        redundant = (
            parent is not None
            and parent["coverage_gap_type"] == item["coverage_gap_type"]
            and PRIORITY_ORDER[parent["priority"]] <= PRIORITY_ORDER[item["priority"]]
            and parent["suggested_action"]["action_type"]
            == item["suggested_action"]["action_type"]
        )
        if not redundant:
            result.append(item)
    return result


def _suppress_individual_evidence_gaps(candidates: list[dict]) -> list[dict]:
    represented = set()
    for item in candidates:
        if item["primary_finding"] != "coverage_gap":
            continue
        action = item["suggested_action"]
        represented.update(action.get("uncovered_entry_ids", []))
        represented.update(action.get("shallow_entry_ids", []))
    result = []
    for item in candidates:
        if item["primary_finding"] not in {"never_quizzed", "insufficient_evidence"}:
            result.append(item)
            continue
        entry_ids = item.get("supporting_entry_ids") or item["suggested_action"].get("entry_ids", [])
        if not entry_ids or not all(int(entry_id) in represented for entry_id in entry_ids):
            result.append(item)
    return result


def build_learning_brief(
    conn: Connection,
    findings: Iterable[dict],
    *,
    collection_id: int | None = None,
) -> list[dict]:
    """Select a deterministic, read-only Brief of no more than five items."""

    candidates = build_action_candidates(
        conn, findings, collection_id=collection_id
    )
    candidates = _suppress_redundant_coverage(candidates)
    candidates = _suppress_individual_evidence_gaps(candidates)
    candidates.sort(key=_rank_key)

    selected = []
    counts = defaultdict(int)
    for candidate in candidates:
        category = _category(candidate)
        if category not in BRIEF_CAPS or counts[category] >= BRIEF_CAPS[category]:
            continue
        selected.append(candidate)
        counts[category] += 1
        if len(selected) == 5:
            break

    if not any(item["primary_finding"] == "recovery" for item in selected):
        recovery = next(
            (item for item in candidates if item["primary_finding"] == "recovery"),
            None,
        )
        if recovery is not None and len(selected) == 5:
            replaceable = [
                (index, item) for index, item in enumerate(selected)
                if item["priority"] == "low" and item["primary_finding"] != "recovery"
            ]
            if replaceable:
                index, removed = replaceable[-1]
                counts[_category(removed)] -= 1
                selected[index] = recovery
                counts["recovery"] += 1
                selected.sort(key=_rank_key)

    return [{**item, "section": _brief_section(item)} for item in selected]

from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

from src import db
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry
from src.insights import (
    _coverage_finding,
    _entry_finding,
    build_action_candidates,
    build_learning_brief,
    get_all_findings,
    get_entry_findings,
)


AS_OF = date(2026, 8, 12)


def profile(**overrides) -> dict:
    base = {
        "entry_id": 1,
        "language": "English",
        "template_id": None,
        "collection_ids": [],
        "in_mistake_book": False,
        "in_proficient_pool": False,
        "in_starred": False,
        "attempts": 8,
        "correct": 7,
        "wrong": 1,
        "accuracy": 0.875,
        "evidence_state": "strong",
        "freshness": "fresh",
        "overall_performance": "positive",
        "recent": {
            "attempts": 5,
            "correct": 4,
            "wrong": 1,
            "accuracy": 0.8,
            "distinct_sessions": 2,
            "eligible": True,
            "performance": "positive",
        },
        "prior": {
            "attempts": 3,
            "correct": 3,
            "wrong": 0,
            "accuracy": 1.0,
            "distinct_sessions": 2,
            "eligible": True,
            "performance": "positive",
        },
        "trajectory": "stable",
        "trajectory_delta_pp": -20.0,
        "repeated_recent_errors": False,
        "repeated_recent_success": True,
        "baseline": {"comparison": "near_baseline"},
    }
    base.update(overrides)
    return base


def coverage_profile(touched: float, interpretable: float, **overrides) -> dict:
    base = {
        "scope_type": "collection",
        "scope_id": 10,
        "total_current_entries": 10,
        "touched_count": round(touched * 10),
        "touched_ratio": touched,
        "interpretable_count": round(interpretable * 10),
        "interpretable_ratio": interpretable,
        "uncovered_entry_ids": [],
        "shallow_entry_ids": [],
    }
    base.update(overrides)
    return base


def entry_finding(entry_id: int, primary: str, priority: str = "low") -> dict:
    actions = {
        "needs_attention": "focused_practice",
        "recovery": "continue_practice",
        "strength": "none",
        "stale_evidence": "verify_knowledge",
        "never_quizzed": "collect_quiz_evidence",
        "insufficient_evidence": "collect_more_evidence",
    }
    return {
        "scope_type": "entry",
        "scope_id": entry_id,
        "primary_finding": primary,
        "priority": priority,
        "evidence_state": "strong",
        "freshness": "fresh",
        "reason_codes": [primary],
        "metrics": {"recent_accuracy": 0.5},
        "context": {},
        "suggested_action": {
            "action_type": actions[primary],
            "entry_ids": [entry_id],
        },
    }


def coverage_finding(
    scope_type: str,
    scope_id: int,
    priority: str,
    *,
    gap_type: str = "breadth_gap",
    collection_id: int | None = None,
    represented: list[int] | None = None,
) -> dict:
    action_type = "quiz_uncovered_content" if gap_type == "breadth_gap" else "deepen_evidence"
    result = {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "primary_finding": "coverage_gap",
        "coverage_gap_type": gap_type,
        "priority": priority,
        "reason_codes": [gap_type],
        "metrics": {
            "touched_ratio": 0.4 if gap_type == "breadth_gap" else 0.9,
            "interpretable_ratio": 0.2,
        },
        "suggested_action": {
            "action_type": action_type,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "uncovered_entry_ids": represented or [],
            "shallow_entry_ids": represented or [],
        },
    }
    if collection_id is not None:
        result["collection_id"] = collection_id
    return result


class M14BatchBInsightsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "m14_batch_b.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _entry(self, label: str) -> int:
        return add_entry("English", "English", "word", label, f"meaning-{label}")

    def test_primary_finding_arbitration_covers_frozen_entry_cases(self) -> None:
        never = _entry_finding(profile(attempts=0, evidence_state="none", freshness="unavailable"))
        sparse = _entry_finding(profile(attempts=2, evidence_state="sparse"))
        developing = _entry_finding(profile(attempts=3, evidence_state="developing"))
        mixed = _entry_finding(profile(
            attempts=5,
            evidence_state="sufficient",
            accuracy=0.6,
            overall_performance="mixed",
            recent={**profile()["recent"], "performance": "mixed", "accuracy": 0.6},
            repeated_recent_success=False,
        ))
        self.assertEqual(never["primary_finding"], "never_quizzed")
        self.assertEqual(sparse["primary_finding"], "insufficient_evidence")
        self.assertEqual(developing["primary_finding"], "insufficient_evidence")
        self.assertEqual(mixed["primary_finding"], "none")

    def test_needs_attention_priority_and_pool_conflict(self) -> None:
        recent = {**profile()["recent"], "correct": 1, "wrong": 4, "accuracy": 0.2, "performance": "negative"}
        finding = _entry_finding(profile(
            recent=recent,
            trajectory="declining",
            trajectory_delta_pp=-60,
            repeated_recent_errors=True,
            in_proficient_pool=True,
            baseline={"comparison": "below_baseline"},
        ))
        self.assertEqual(finding["primary_finding"], "needs_attention")
        self.assertEqual(finding["priority"], "high")
        self.assertIn("declining_trajectory", finding["reason_codes"])
        self.assertIn("pool_conflict", finding["reason_codes"])

    def test_recovery_requires_adjacent_negative_to_positive_windows(self) -> None:
        prior = {**profile()["prior"], "correct": 1, "wrong": 4, "accuracy": 0.2, "performance": "negative"}
        finding = _entry_finding(profile(
            attempts=10,
            prior=prior,
            trajectory="improving",
            trajectory_delta_pp=60,
        ))
        stabilized = _entry_finding(profile(attempts=10))
        self.assertEqual(finding["primary_finding"], "recovery")
        self.assertNotEqual(stabilized["primary_finding"], "recovery")

    def test_strength_allows_aging_and_reports_mistake_book_conflict(self) -> None:
        finding = _entry_finding(profile(freshness="aging", in_mistake_book=True))
        self.assertEqual(finding["primary_finding"], "strength")
        self.assertIn("mistake_book_context", finding["reason_codes"])
        self.assertIn("pool_conflict", finding["reason_codes"])

    def test_stale_wins_and_moves_old_signals_to_historical_context(self) -> None:
        finding = _entry_finding(profile(
            freshness="stale",
            trajectory="declining",
            repeated_recent_errors=True,
        ))
        self.assertEqual(finding["primary_finding"], "stale_evidence")
        self.assertEqual(finding["priority"], "medium")
        self.assertNotIn("declining_trajectory", finding["reason_codes"])
        self.assertEqual(finding["historical_context"]["historical_trajectory"], "declining")

    def test_coverage_gap_boundaries_and_priorities(self) -> None:
        cases = [
            (0.40, 0.20, "breadth_gap", "high"),
            (0.60, 0.20, "breadth_gap", "medium"),
            (0.90, 0.20, "evidence_depth_gap", "medium"),
            (0.90, 0.45, "evidence_depth_gap", "low"),
        ]
        for touched, interpretable, gap_type, priority in cases:
            finding = _coverage_finding(coverage_profile(touched, interpretable))
            self.assertEqual(finding["coverage_gap_type"], gap_type)
            self.assertEqual(finding["priority"], priority)
        self.assertIsNone(_coverage_finding(coverage_profile(0.90, 0.65)))
        for scope_type in ("collection", "card", "template"):
            finding = _coverage_finding(
                coverage_profile(0.40, 0.20, scope_type=scope_type)
            )
            self.assertEqual(finding["scope_type"], scope_type)

    def test_same_card_compatible_findings_cluster_without_rewriting_members(self) -> None:
        collection_id = create_collection("Cluster", card_size=10)
        entry_ids = [self._entry(f"cluster-{index}") for index in range(3)]
        add_entries_to_collection(entry_ids, collection_id)
        findings = [entry_finding(entry_id, "needs_attention", "medium") for entry_id in entry_ids]
        findings[0]["priority"] = "high"
        with db.get_connection() as conn:
            candidates = build_action_candidates(conn, findings)
        self.assertEqual(len(candidates), 1)
        cluster = candidates[0]
        self.assertEqual(cluster["scope_type"], "entry_cluster")
        self.assertEqual(cluster["priority"], "high")
        self.assertEqual(cluster["supporting_entry_ids"], entry_ids)
        self.assertEqual([item["priority"] for item in cluster["member_findings"]], ["high", "medium", "medium"])
        self.assertEqual(cluster["suggested_action"]["action_type"], "focused_practice")

    def test_different_findings_on_same_card_do_not_cluster(self) -> None:
        collection_id = create_collection("No semantic cluster", card_size=10)
        first, second = self._entry("attention"), self._entry("recovery")
        add_entries_to_collection([first, second], collection_id)
        with db.get_connection() as conn:
            candidates = build_action_candidates(
                conn,
                [entry_finding(first, "needs_attention", "medium"), entry_finding(second, "recovery")],
            )
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(item["scope_type"] == "entry" for item in candidates))

    def test_multi_collection_card_context_is_deterministic_and_scope_aware(self) -> None:
        first_collection = create_collection("First context", card_size=10)
        second_collection = create_collection("Second context", card_size=10)
        target = self._entry("multi-context")
        add_entries_to_collection([target], first_collection)
        add_entries_to_collection([target], second_collection)
        finding = entry_finding(target, "needs_attention", "medium")
        with db.get_connection() as conn:
            global_candidate = build_action_candidates(conn, [finding])[0]
            scoped_candidate = build_action_candidates(
                conn, [finding], collection_id=second_collection
            )[0]
        self.assertEqual(global_candidate["card_context"]["collection_id"], first_collection)
        self.assertEqual(scoped_candidate["card_context"]["collection_id"], second_collection)

    def test_coverage_hierarchy_suppression_is_brief_only_and_directional(self) -> None:
        parent = coverage_finding("collection", 10, "high")
        child = coverage_finding("card", 100, "medium", collection_id=10)
        brief = build_learning_brief(db.get_connection(), [parent, child])
        self.assertEqual([(item["scope_type"], item["scope_id"]) for item in brief], [("collection", 10)])
        self.assertEqual(len([parent, child]), 2)

        healthy_parent_absent_child = coverage_finding("card", 101, "high", collection_id=11)
        self.assertEqual(len(build_learning_brief(db.get_connection(), [healthy_parent_absent_child])), 1)
        lower_parent = coverage_finding("collection", 12, "low")
        higher_child = coverage_finding("card", 102, "high", collection_id=12)
        result = build_learning_brief(db.get_connection(), [lower_parent, higher_child])
        self.assertIn(102, [item["scope_id"] for item in result])

    def test_brief_caps_total_and_categories_deterministically(self) -> None:
        findings = [entry_finding(index, "needs_attention", "high") for index in range(1, 6)]
        findings += [coverage_finding("collection", index, "medium") for index in range(20, 24)]
        findings += [entry_finding(40, "stale_evidence", "medium")]
        first = build_learning_brief(db.get_connection(), findings)
        second = build_learning_brief(db.get_connection(), list(reversed(findings)))
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 5)
        self.assertLessEqual(sum(item["primary_finding"] == "needs_attention" for item in first), 3)
        self.assertLessEqual(sum(item["primary_finding"] == "coverage_gap" for item in first), 2)

    def test_recovery_diversity_replaces_only_low_priority_candidate(self) -> None:
        urgent = [entry_finding(index, "needs_attention", "high") for index in range(1, 5)]
        low_gap = entry_finding(10, "never_quizzed")
        recovery = entry_finding(11, "recovery")
        brief = build_learning_brief(db.get_connection(), [*urgent, low_gap, recovery])
        self.assertIn("recovery", [item["primary_finding"] for item in brief])

        five_urgent = [entry_finding(index, "needs_attention", "high") for index in range(20, 25)]
        five_urgent[3] = coverage_finding("collection", 30, "medium")
        five_urgent[4] = entry_finding(31, "stale_evidence", "medium")
        brief = build_learning_brief(db.get_connection(), [*five_urgent, recovery])
        self.assertNotIn("recovery", [item["primary_finding"] for item in brief])

    def test_scope_gap_suppresses_redundant_individual_evidence_spam(self) -> None:
        individual = [entry_finding(index, "never_quizzed") for index in range(1, 10)]
        gap = coverage_finding("collection", 50, "high", represented=list(range(1, 10)))
        brief = build_learning_brief(db.get_connection(), [*individual, gap])
        self.assertEqual(len(brief), 1)
        self.assertEqual(brief[0]["primary_finding"], "coverage_gap")

    def test_empty_brief_is_valid(self) -> None:
        none = {**entry_finding(1, "strength"), "primary_finding": "none", "suggested_action": {"action_type": "none", "entry_ids": [1]}}
        self.assertEqual(build_learning_brief(db.get_connection(), [none]), [])

    def test_public_pipeline_is_read_only_and_excludes_deleted_entries(self) -> None:
        current = self._entry("current")
        conn = db.get_connection()
        try:
            tables = ["entries", "entry_collections", "collections", "quiz_sessions", "quiz_item_logs", "cards", "card_revisions"]
            before = {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}
            result = get_all_findings(conn, as_of_date=AS_OF)
            after = {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}
        finally:
            conn.close()
        self.assertEqual(before, after)
        self.assertEqual([item["scope_id"] for item in result["entry_findings"]], [current])
        with db.get_connection() as conn:
            self.assertEqual(len(get_entry_findings(conn, as_of_date=AS_OF)), 1)


if __name__ == "__main__":
    unittest.main()

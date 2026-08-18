from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.analytics import (
    build_evidence_profile_cache,
    get_collection_coverage_profile,
    get_entry_evidence_profiles,
)
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry
from src.insights import get_all_findings

"""
M19 exit criterion: "Analytics outcomes are verified against
representative expected cases."

The M18 desktop Analytics suite proved the controller delegates to the
M14 core and handles the empty/never-quizzed case, but it exercised no
real Quiz evidence at all -- so nothing verified that what the Analytics
workspace actually shows matches the frozen M14 semantic contract
(`docs/design/M14_SEMANTIC_CONTRACT.md`).

This file closes that gap. It builds real `quiz_sessions`/
`quiz_item_logs` evidence with controlled timestamps, hand-computes the
expected outcome for each case directly from the contract's published
gates, and asserts the real pipeline agrees -- end to end, through the
desktop `AnalyticsController` the user actually sees, not only the core
functions.

Representative Primary Finding cases (one per arbitration class, in the
contract's arbitration order):

| case             | evidence built                        | contract gates                                  | expected               |
|------------------|---------------------------------------|-------------------------------------------------|------------------------|
| never            | no attempts                           | 0 attempts                                      | never_quizzed          |
| insufficient     | 4 attempts / 2 sessions               | developing (>=3/2) but below sufficient (>=5/3) | insufficient_evidence  |
| stale            | 6 attempts / 3 sessions, ~120d old    | sufficient evidence + stale freshness (>=90d)   | stale_evidence         |
| recovery         | prior 5 negative -> recent 5 positive | windows eligible, trajectory improving          | recovery               |
| needs_attention  | 8 attempts / 4 sessions, recent 4/5 wrong | recent negative + repeated recent errors     | needs_attention        |
| strength         | 10 attempts / 5 sessions, all correct | strong + positive overall/recent + repeated success | strength           |

Coverage cases use the contract's published bands (Touched: 0/1-49/
50-79/>=80; Interpretable: 0/1-29/30-59/>=60) plus the frozen lock that
an empty scope is `unavailable`, never 0% learning progress.

A cached-vs-uncached equivalence check locks the Human Gate 2
corrective's central claim that `EvidenceProfileCache` is "purely a
performance change": if the cached path ever produced a different
Finding, Brief, or Coverage figure than the uncached path, that would be
a correctness defect hiding behind a performance fix.
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.analytics_controller import AnalyticsController

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app

    def _wait_for_load(controller: "AnalyticsController", timeout_ms: int = 10000) -> None:
        """Pump the Qt event loop until the background Analytics load
        finishes, then block until its QThread has actually stopped --
        the same two-step wait `tests/test_m18_analytics.py` documents
        (event-loop pumping alone can return before the OS thread exits,
        which segfaults once tearDown deletes the temporary database)."""
        from PySide6.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        controller.state_changed.connect(loop.quit)
        controller.loading_failed.connect(loop.quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        loop.exec()
        timer.stop()
        controller.state_changed.disconnect(loop.quit)
        controller.loading_failed.disconnect(loop.quit)
        if controller.is_loading:
            raise AssertionError("Analytics background load did not complete within the timeout.")
        controller.shutdown()
        if controller._inflight:
            raise AssertionError("Analytics background QThread did not fully stop within the timeout.")


class _EvidenceBuilderTestCase(unittest.TestCase):
    """Builds real Quiz evidence with controlled `answered_at` ages.

    Timestamps are relative to `datetime.now()` rather than a frozen
    calendar date, because the desktop controller resolves `as_of_date`
    from the real clock -- the same way the running product does.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m19_analytics.sqlite3"
        db.init_db()
        self.now = datetime.now()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _days_ago(self, days: float) -> str:
        return (self.now - timedelta(days=days)).isoformat(timespec="seconds")

    def _record_sessions(self, conn, collection_id: int, entry_id: int, sessions) -> None:
        """`sessions` is a list of sessions, each a list of
        (was_correct, days_ago) attempts -- one real `quiz_sessions` row
        per session, so distinct-session gates are exercised honestly."""
        for attempts in sessions:
            cursor = conn.execute(
                "INSERT INTO quiz_sessions (collection_id, card_number, quiz_type, started_at, status, total_items)"
                " VALUES (?, 1, 'term_to_meaning', ?, 'completed', 0)",
                (collection_id, self._days_ago(0)),
            )
            session_id = cursor.lastrowid
            for was_correct, days_ago in attempts:
                conn.execute(
                    "INSERT INTO quiz_item_logs"
                    " (session_id, entry_id, prompt, expected_answer, user_answer, is_correct, answered_at)"
                    " VALUES (?, ?, 'prompt', 'expected', 'answer', ?, ?)",
                    (session_id, entry_id, 1 if was_correct else 0, self._days_ago(days_ago)),
                )

    def _build_representative_dataset(self) -> tuple[int, dict[str, int]]:
        collection_id = create_collection("Representative", "", card_size=8)
        entry_ids = {
            "never": add_entry("French", "English", "word", "jamais", "never"),
            "insufficient": add_entry("French", "English", "word", "peu", "few"),
            "stale": add_entry("French", "English", "word", "vieux", "old"),
            "needs_attention": add_entry("French", "English", "word", "faible", "weak"),
            "strength": add_entry("French", "English", "word", "fort", "strong"),
            "recovery": add_entry("French", "English", "word", "retour", "recovery"),
        }
        add_entries_to_collection(list(entry_ids.values()), collection_id)

        conn = db.get_connection()
        try:
            # 4 attempts / 2 sessions: developing, below the sufficient gate.
            self._record_sessions(conn, collection_id, entry_ids["insufficient"], [
                [(True, 5), (True, 5)],
                [(True, 4), (False, 4)],
            ])
            # 6 attempts / 3 sessions, all ~120 days old: sufficient but stale.
            self._record_sessions(conn, collection_id, entry_ids["stale"], [
                [(True, 122), (True, 122)],
                [(True, 121), (True, 121)],
                [(True, 120), (False, 120)],
            ])
            # 8 attempts / 4 sessions; the recent window is 4/5 wrong across 2 sessions.
            self._record_sessions(conn, collection_id, entry_ids["needs_attention"], [
                [(True, 20), (True, 20)],
                [(True, 18), (False, 18)],
                [(False, 5), (False, 5)],
                [(False, 3), (False, 3)],
            ])
            # 10 attempts / 5 sessions spanning weeks, every one correct.
            self._record_sessions(conn, collection_id, entry_ids["strength"], [
                [(True, 20), (True, 20)],
                [(True, 15), (True, 15)],
                [(True, 10), (True, 10)],
                [(True, 5), (True, 5)],
                [(True, 2), (True, 2)],
            ])
            # Prior window negative, recent window fully correct.
            self._record_sessions(conn, collection_id, entry_ids["recovery"], [
                [(False, 30), (False, 30)],
                [(False, 25), (True, 25)],
                [(False, 20), (True, 12)],
                [(True, 8), (True, 8)],
                [(True, 4), (True, 4)],
            ])
            conn.commit()
        finally:
            conn.close()
        return collection_id, entry_ids


class RepresentativeEvidenceProfileTests(_EvidenceBuilderTestCase):
    """The intermediate analytical classifications each Primary Finding
    is derived from, asserted against the contract's published gates --
    so a failure localizes to the specific gate that drifted rather than
    only to the final Finding."""

    def test_evidence_state_freshness_and_windows_match_the_contract(self) -> None:
        _collection_id, entry_ids = self._build_representative_dataset()
        conn = db.get_connection()
        try:
            profiles = {p["entry_id"]: p for p in get_entry_evidence_profiles(conn)}
        finally:
            conn.close()

        never = profiles[entry_ids["never"]]
        self.assertEqual(never["attempts"], 0)
        self.assertEqual(never["evidence_state"], "none")
        self.assertEqual(never["freshness"], "unavailable")

        insufficient = profiles[entry_ids["insufficient"]]
        self.assertEqual((insufficient["attempts"], insufficient["distinct_sessions"]), (4, 2))
        self.assertEqual(insufficient["evidence_state"], "developing")

        stale = profiles[entry_ids["stale"]]
        self.assertEqual((stale["attempts"], stale["distinct_sessions"]), (6, 3))
        self.assertEqual(stale["evidence_state"], "sufficient")
        self.assertEqual(stale["freshness"], "stale")

        needs_attention = profiles[entry_ids["needs_attention"]]
        self.assertEqual(needs_attention["evidence_state"], "strong")
        self.assertEqual(needs_attention["freshness"], "fresh")
        self.assertEqual(needs_attention["recent"]["performance"], "negative")
        self.assertTrue(needs_attention["repeated_recent_errors"])
        self.assertEqual(needs_attention["trajectory"], "declining")

        strength = profiles[entry_ids["strength"]]
        self.assertEqual(strength["evidence_state"], "strong")
        self.assertEqual(strength["overall_performance"], "positive")
        self.assertEqual(strength["recent"]["performance"], "positive")
        self.assertTrue(strength["repeated_recent_success"])
        self.assertEqual(strength["trajectory"], "stable")

        recovery = profiles[entry_ids["recovery"]]
        self.assertEqual(recovery["prior"]["performance"], "negative")
        self.assertEqual(recovery["recent"]["performance"], "positive")
        self.assertEqual(recovery["trajectory"], "improving")
        self.assertTrue(recovery["repeated_recent_success"])


class RepresentativePrimaryFindingTests(_EvidenceBuilderTestCase):
    def test_every_arbitration_class_matches_its_expected_case(self) -> None:
        _collection_id, entry_ids = self._build_representative_dataset()
        conn = db.get_connection()
        try:
            findings = get_all_findings(conn)
        finally:
            conn.close()
        by_entry = {item["scope_id"]: item["primary_finding"] for item in findings["entry_findings"]}

        self.assertEqual(by_entry[entry_ids["never"]], "never_quizzed")
        self.assertEqual(by_entry[entry_ids["insufficient"]], "insufficient_evidence")
        self.assertEqual(by_entry[entry_ids["stale"]], "stale_evidence")
        self.assertEqual(by_entry[entry_ids["needs_attention"]], "needs_attention")
        self.assertEqual(by_entry[entry_ids["strength"]], "strength")
        self.assertEqual(by_entry[entry_ids["recovery"]], "recovery")

    def test_analytics_reads_do_not_mutate_learning_state(self) -> None:
        """Frozen M14 lock: all analytics paths are read-only."""
        collection_id, _entry_ids = self._build_representative_dataset()
        conn = db.get_connection()
        try:
            tables = ("entries", "quiz_sessions", "quiz_item_logs", "entry_collections", "cards")
            before = {t: conn.execute(f"select count(*) from {t}").fetchone()[0] for t in tables}
            get_all_findings(conn)
            get_all_findings(conn, collection_id=collection_id)
            get_collection_coverage_profile(conn, collection_id)
            after = {t: conn.execute(f"select count(*) from {t}").fetchone()[0] for t in tables}
        finally:
            conn.close()
        self.assertEqual(before, after)


class RepresentativeCoverageTests(_EvidenceBuilderTestCase):
    def test_coverage_bands_and_absent_gaps_match_the_contract(self) -> None:
        """5 of 6 Entries touched (83.3%) is `broad` (>=80%), and 4 of 6
        interpretable (66.7%) is `substantial` (>=60%) -- so neither a
        Breadth Gap (touched <80%) nor an Evidence Depth Gap (touched
        >=80% with interpretable <60%) applies, and the scope correctly
        produces no Coverage Gap Finding at all."""
        collection_id, _entry_ids = self._build_representative_dataset()
        conn = db.get_connection()
        try:
            coverage = get_collection_coverage_profile(conn, collection_id)
            scoped = get_all_findings(conn, collection_id=collection_id)
        finally:
            conn.close()

        self.assertEqual((coverage["touched_count"], coverage["total_current_entries"]), (5, 6))
        self.assertEqual(coverage["touched_state"], "broad")
        self.assertEqual(coverage["interpretable_count"], 4)
        self.assertEqual(coverage["interpretable_state"], "substantial")
        self.assertEqual(scoped["coverage_findings"], [])

    def test_a_sparse_collection_produces_the_expected_gap_findings(self) -> None:
        """1 of 5 touched (20%) is `limited` (1-49%) and 0% interpretable
        is `none`, so a Breadth Gap must be reported."""
        collection_id = create_collection("Sparse", "", card_size=8)
        entry_ids = [add_entry("French", "English", "word", f"mot{index}", f"word {index}") for index in range(5)]
        add_entries_to_collection(entry_ids, collection_id)
        conn = db.get_connection()
        try:
            self._record_sessions(conn, collection_id, entry_ids[0], [[(True, 1)]])
            conn.commit()
            coverage = get_collection_coverage_profile(conn, collection_id)
            scoped = get_all_findings(conn, collection_id=collection_id)
        finally:
            conn.close()

        self.assertEqual((coverage["touched_count"], coverage["total_current_entries"]), (1, 5))
        self.assertEqual(coverage["touched_state"], "limited")
        self.assertEqual(coverage["interpretable_count"], 0)
        self.assertEqual(coverage["interpretable_state"], "none")
        scope_types = {item["scope_type"] for item in scoped["coverage_findings"]}
        self.assertIn("collection", scope_types)
        self.assertTrue(all(item["primary_finding"] == "coverage_gap" for item in scoped["coverage_findings"]))

    def test_an_empty_collection_is_unavailable_not_zero_progress(self) -> None:
        """Frozen M14 lock: empty scopes are `unavailable`, never 0%."""
        collection_id = create_collection("Empty", "", card_size=8)
        conn = db.get_connection()
        try:
            coverage = get_collection_coverage_profile(conn, collection_id)
        finally:
            conn.close()
        self.assertEqual(coverage["total_current_entries"], 0)
        self.assertEqual(coverage["touched_state"], "unavailable")
        self.assertEqual(coverage["interpretable_state"], "unavailable")


class EvidenceProfileCacheEquivalenceTests(_EvidenceBuilderTestCase):
    """The Human Gate 2 corrective states `EvidenceProfileCache` is
    "purely a performance change ... without altering which Entries/
    events feed any profile or Finding". These lock that claim in: a
    cache that changed an analytical outcome would be a correctness
    defect wearing a performance fix's clothes."""

    def test_findings_are_identical_with_and_without_the_cache(self) -> None:
        collection_id, _entry_ids = self._build_representative_dataset()
        conn = db.get_connection()
        try:
            uncached_all = get_all_findings(conn)
            uncached_scoped = get_all_findings(conn, collection_id=collection_id)
            cache = build_evidence_profile_cache(conn)
            cached_all = get_all_findings(conn, cache=cache)
            cached_scoped = get_all_findings(conn, collection_id=collection_id, cache=cache)
        finally:
            conn.close()

        self.assertEqual(cached_all, uncached_all)
        self.assertEqual(cached_scoped, uncached_scoped)

    def test_coverage_profiles_are_identical_with_and_without_the_cache(self) -> None:
        collection_id, _entry_ids = self._build_representative_dataset()
        conn = db.get_connection()
        try:
            uncached = get_collection_coverage_profile(conn, collection_id)
            cache = build_evidence_profile_cache(conn)
            cached = get_collection_coverage_profile(conn, collection_id, cache=cache)
        finally:
            conn.close()
        self.assertEqual(cached, uncached)

    def test_one_cache_stays_correct_when_reused_across_scopes(self) -> None:
        """The real Analytics pass builds the cache once and reuses it
        for every scope; reuse must not let one scope's read contaminate
        another's."""
        collection_id, _entry_ids = self._build_representative_dataset()
        second_id = create_collection("Second", "", card_size=8)
        second_entries = [add_entry("French", "English", "word", f"deux{i}", f"two {i}") for i in range(3)]
        add_entries_to_collection(second_entries, second_id)

        conn = db.get_connection()
        try:
            expected_first = get_collection_coverage_profile(conn, collection_id)
            expected_second = get_collection_coverage_profile(conn, second_id)
            cache = build_evidence_profile_cache(conn)
            actual_second = get_collection_coverage_profile(conn, second_id, cache=cache)
            actual_first = get_collection_coverage_profile(conn, collection_id, cache=cache)
            # Re-read the first scope again through the same cache.
            actual_first_again = get_collection_coverage_profile(conn, collection_id, cache=cache)
        finally:
            conn.close()

        self.assertEqual(actual_first, expected_first)
        self.assertEqual(actual_second, expected_second)
        self.assertEqual(actual_first_again, expected_first)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class DesktopAnalyticsWorkspaceRepresentativeTests(_EvidenceBuilderTestCase):
    """The same representative expectations, asserted through the real
    desktop `AnalyticsController` -- the projection the operator
    actually sees in the Analytics workspace."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_workspace_findings_match_the_expected_cases(self) -> None:
        _collection_id, entry_ids = self._build_representative_dataset()
        controller = AnalyticsController()
        controller.refresh()
        _wait_for_load(controller)

        by_entry = {
            item["scope_id"]: item["primary_finding"]
            for item in controller.full_findings["entry_findings"]
        }
        self.assertEqual(by_entry[entry_ids["never"]], "never_quizzed")
        self.assertEqual(by_entry[entry_ids["insufficient"]], "insufficient_evidence")
        self.assertEqual(by_entry[entry_ids["stale"]], "stale_evidence")
        self.assertEqual(by_entry[entry_ids["needs_attention"]], "needs_attention")
        self.assertEqual(by_entry[entry_ids["strength"]], "strength")
        self.assertEqual(by_entry[entry_ids["recovery"]], "recovery")

    def test_brief_respects_the_five_item_cap_and_carries_real_findings(self) -> None:
        _collection_id, _entry_ids = self._build_representative_dataset()
        controller = AnalyticsController()
        controller.refresh()
        _wait_for_load(controller)

        self.assertLessEqual(len(controller.brief), 5)
        valid = {
            "never_quizzed",
            "insufficient_evidence",
            "stale_evidence",
            "recovery",
            "needs_attention",
            "strength",
            "coverage_gap",
        }
        for item in controller.brief:
            self.assertIn(item["primary_finding"], valid)

    def test_actionable_findings_exclude_only_no_finding_entries(self) -> None:
        _collection_id, _entry_ids = self._build_representative_dataset()
        controller = AnalyticsController()
        controller.refresh()
        _wait_for_load(controller)

        actionable = controller.actionable_findings()
        self.assertTrue(all(item["primary_finding"] != "none" for item in actionable))
        no_finding_count = sum(
            1 for item in controller.full_findings["full_findings"] if item["primary_finding"] == "none"
        )
        self.assertEqual(len(actionable) + no_finding_count, len(controller.full_findings["full_findings"]))

    def test_collection_scope_reports_the_expected_coverage_figures(self) -> None:
        collection_id, _entry_ids = self._build_representative_dataset()
        controller = AnalyticsController()
        controller.set_scope("collection", collection_id)
        _wait_for_load(controller)

        self.assertIsNotNone(controller.coverage)
        self.assertEqual(controller.coverage["touched_count"], 5)
        self.assertEqual(controller.coverage["touched_state"], "broad")
        self.assertEqual(controller.coverage["interpretable_state"], "substantial")

    def test_repeated_refreshes_are_deterministic(self) -> None:
        """Same database, same clock-day: the workspace must not drift
        between refreshes (M14 findings are deterministic, not sampled)."""
        _collection_id, _entry_ids = self._build_representative_dataset()
        controller = AnalyticsController()
        controller.refresh()
        _wait_for_load(controller)
        first = controller.full_findings["full_findings"]

        controller.refresh()
        _wait_for_load(controller)
        second = controller.full_findings["full_findings"]

        self.assertEqual(first, second)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

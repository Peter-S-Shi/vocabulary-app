from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from src import analytics, db, quiz
from src.analytics import (
    get_card_coverage_profile,
    get_collection_coverage_profile,
    get_collection_scope_activity_profile,
    get_entry_evidence_profile,
    get_entry_evidence_profiles,
    get_historical_card_evidence_context,
    get_personal_baseline,
    get_template_coverage_profile,
    load_eligible_evidence_events,
)
from src.collections import (
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    remove_entries_from_collection,
)
from src.entries import add_entry, delete_entry


AS_OF = date(2026, 8, 11)


class M14BatchAAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "m14_batch_a.sqlite3"
        db.init_db()
        self.default_collection_id = create_collection("Synthetic Evidence", card_size=10)

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _entry(self, label: str, language: str = "English") -> int:
        return add_entry(language, "English", "word", label, f"meaning-{label}")

    def _session(
        self,
        *,
        collection_id: int | None = None,
        card_number: int = 0,
        status: str = "completed",
        timestamp: str = "2026-08-01T12:00:00+00:00",
    ) -> int:
        collection_id = collection_id or self.default_collection_id
        card_id = None
        card_revision_id = None
        if card_number > 0:
            conn = db.get_connection()
            try:
                identity = conn.execute(
                    """
                    SELECT cards.id AS card_id, revisions.id AS card_revision_id
                    FROM cards
                    JOIN card_revisions AS revisions ON revisions.card_id = cards.id
                    WHERE cards.collection_id = ?
                      AND cards.card_number = ?
                      AND cards.is_active = 1
                    ORDER BY revisions.revision_number DESC
                    LIMIT 1
                    """,
                    (collection_id, card_number),
                ).fetchone()
            finally:
                conn.close()
            if identity is not None:
                card_id = int(identity["card_id"])
                card_revision_id = int(identity["card_revision_id"])

        conn = db.get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO quiz_sessions (
                    collection_id, card_number, quiz_type, started_at,
                    completed_at, total_items, correct_count, wrong_count,
                    status, card_id, card_revision_id
                ) VALUES (?, ?, 'term_to_meaning', ?, ?, 0, 0, 0, ?, ?, ?)
                """,
                (
                    collection_id,
                    card_number,
                    timestamp,
                    timestamp if status == "completed" else None,
                    status,
                    card_id,
                    card_revision_id,
                ),
            )
            conn.commit()
            session_id = int(cursor.lastrowid)
        finally:
            conn.close()
        return session_id

    def _log(
        self,
        session_id: int,
        entry_id: int,
        is_correct: int | None,
        timestamp: str,
    ) -> int:
        conn = db.get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO quiz_item_logs (
                    session_id, entry_id, prompt, expected_answer,
                    user_answer, is_correct, answered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    entry_id,
                    f"prompt-{entry_id}",
                    f"answer-{entry_id}",
                    "synthetic-answer",
                    is_correct,
                    timestamp,
                ),
            )
            conn.commit()
            log_id = int(cursor.lastrowid)
        finally:
            conn.close()
        return log_id

    def _add_outcomes(
        self,
        entry_id: int,
        outcomes: list[int],
        *,
        session_count: int,
        last_age_days: int = 1,
        collection_id: int | None = None,
        same_timestamp: bool = False,
    ) -> list[int]:
        session_ids = [
            self._session(collection_id=collection_id)
            for _ in range(session_count)
        ]
        log_ids = []
        for index, outcome in enumerate(outcomes):
            day_offset = 0 if same_timestamp else index % max(min(session_count, 3), 1)
            timestamp = datetime.combine(
                AS_OF - timedelta(days=last_age_days + day_offset),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ).isoformat()
            log_ids.append(
                self._log(
                    session_ids[index % session_count],
                    entry_id,
                    outcome,
                    timestamp,
                )
            )
        return log_ids

    def test_evidence_gates_use_highest_satisfied_state(self) -> None:
        none_id = self._entry("none")
        one_id = self._entry("one")
        two_id = self._entry("two")
        developing_id = self._entry("developing")
        four_id = self._entry("four")
        sufficient_id = self._entry("sufficient")
        seven_id = self._entry("seven")
        strong_id = self._entry("strong")
        concentrated_id = self._entry("concentrated")

        self._add_outcomes(one_id, [1], session_count=1)
        self._add_outcomes(two_id, [1, 0], session_count=1)
        self._add_outcomes(developing_id, [1, 1, 0], session_count=2)
        self._add_outcomes(four_id, [1, 1, 0, 0], session_count=2)
        self._add_outcomes(sufficient_id, [1, 1, 1, 0, 0], session_count=3)
        self._add_outcomes(seven_id, [1, 1, 1, 1, 0, 0, 0], session_count=3)
        self._add_outcomes(strong_id, [1] * 8, session_count=4)
        self._add_outcomes(concentrated_id, [1] * 5, session_count=1)
        add_entries_to_system_collection([strong_id], "mistake_book")

        with db.get_connection() as conn:
            profiles = {
                row["entry_id"]: row
                for row in get_entry_evidence_profiles(conn, as_of_date=AS_OF)
            }

        self.assertEqual(profiles[none_id]["evidence_state"], "none")
        self.assertEqual(profiles[one_id]["evidence_state"], "sparse")
        self.assertEqual(profiles[two_id]["evidence_state"], "sparse")
        self.assertEqual(profiles[developing_id]["evidence_state"], "developing")
        self.assertEqual(profiles[four_id]["evidence_state"], "developing")
        self.assertEqual(profiles[sufficient_id]["evidence_state"], "sufficient")
        self.assertEqual(profiles[seven_id]["evidence_state"], "sufficient")
        self.assertEqual(profiles[strong_id]["evidence_state"], "strong")
        self.assertTrue(profiles[strong_id]["in_mistake_book"])
        self.assertEqual(profiles[strong_id]["overall_performance"], "positive")
        self.assertEqual(profiles[concentrated_id]["evidence_state"], "sparse")

    def test_explicit_correctness_and_cancelled_item_semantics(self) -> None:
        entry_id = self._entry("cancelled-evidence")
        add_entries_to_collection([entry_id], self.default_collection_id)
        cancelled_session = self._session(card_number=1, status="cancelled")
        self._log(cancelled_session, entry_id, 1, "2026-08-10T10:00:00+00:00")
        self._log(cancelled_session, entry_id, 0, "2026-08-10T10:01:00+00:00")
        self._log(cancelled_session, entry_id, None, "2026-08-10T10:02:00+00:00")

        with db.get_connection() as conn:
            events = load_eligible_evidence_events(conn, as_of_date=AS_OF)
            session = dict(
                conn.execute(
                    "SELECT status, completed_at, card_number FROM quiz_sessions WHERE id = ?",
                    (cancelled_session,),
                ).fetchone()
            )

        self.assertEqual([event["is_correct"] for event in events], [1, 0])
        self.assertTrue(all(event["session_status"] == "cancelled" for event in events))
        self.assertFalse(quiz.is_card_scoped_quiz_session(session))

    def test_freshness_performance_and_future_cutoff_boundaries(self) -> None:
        expected_freshness = {30: "fresh", 31: "aging", 89: "aging", 90: "stale"}
        entry_ids = {}
        for age, expected in expected_freshness.items():
            entry_id = self._entry(f"age-{age}")
            entry_ids[age] = entry_id
            self._add_outcomes(entry_id, [1, 1, 1, 0, 0], session_count=3, last_age_days=age)

        future_id = self._entry("future")
        future_session = self._session()
        self._log(future_session, future_id, 1, "2026-08-12T00:00:00+00:00")

        with db.get_connection() as conn:
            profiles = {
                row["entry_id"]: row
                for row in get_entry_evidence_profiles(conn, as_of_date=AS_OF)
            }

        for age, expected in expected_freshness.items():
            self.assertEqual(profiles[entry_ids[age]]["freshness"], expected)
        self.assertEqual(profiles[future_id]["evidence_state"], "none")
        def window(correct: int, attempts: int) -> dict:
            return analytics._window_profile(
                [
                    {"is_correct": 1 if index < correct else 0, "session_id": index % 5}
                    for index in range(attempts)
                ]
            )

        self.assertEqual(window(59, 100)["performance"], "negative")
        self.assertEqual(window(3, 5)["performance"], "mixed")
        self.assertEqual(window(79, 100)["performance"], "mixed")
        self.assertEqual(window(4, 5)["performance"], "positive")

    def test_recent_prior_tie_break_trajectory_and_repeated_patterns(self) -> None:
        improving_id = self._entry("improving")
        sessions = [self._session() for _ in range(4)]
        outcomes = [1, 1, 1, 0, 0, 1, 1, 1, 1, 0]
        log_ids = []
        for index, outcome in enumerate(outcomes):
            log_ids.append(
                self._log(
                    sessions[index % 4],
                    improving_id,
                    outcome,
                    "2026-08-10T12:00:00+00:00",
                )
            )

        errors_one_session_id = self._entry("errors-one-session")
        self._add_outcomes(
            errors_one_session_id,
            [0, 0, 0, 1, 1],
            session_count=1,
            same_timestamp=True,
        )
        errors_multi_session_id = self._entry("errors-multi-session")
        self._add_outcomes(
            errors_multi_session_id,
            [0, 0, 0, 1, 1],
            session_count=2,
            same_timestamp=True,
        )
        success_one_session_id = self._entry("success-one-session")
        self._add_outcomes(
            success_one_session_id,
            [1, 1, 1, 1, 0],
            session_count=1,
            same_timestamp=True,
        )

        with db.get_connection() as conn:
            profile = get_entry_evidence_profile(conn, improving_id, as_of_date=AS_OF)
            concentrated = get_entry_evidence_profile(
                conn,
                errors_one_session_id,
                as_of_date=AS_OF,
            )
            repeated_errors = get_entry_evidence_profile(
                conn,
                errors_multi_session_id,
                as_of_date=AS_OF,
            )
            concentrated_success = get_entry_evidence_profile(
                conn,
                success_one_session_id,
                as_of_date=AS_OF,
            )
            ordered_ids = [
                event["log_id"]
                for event in load_eligible_evidence_events(
                    conn,
                    entry_ids=[improving_id],
                    as_of_date=AS_OF,
                )
            ]

        self.assertEqual(ordered_ids, log_ids)
        self.assertEqual(profile["prior"]["accuracy"], 0.6)
        self.assertEqual(profile["recent"]["accuracy"], 0.8)
        self.assertEqual(profile["trajectory"], "improving")
        self.assertEqual(profile["trajectory_delta_pp"], 20.0)
        self.assertTrue(profile["repeated_recent_success"])
        self.assertFalse(concentrated["repeated_recent_errors"])
        self.assertTrue(repeated_errors["repeated_recent_errors"])
        self.assertFalse(concentrated_success["repeated_recent_success"])
        self.assertEqual(
            analytics._trajectory(
                {"eligible": True, "accuracy": 0.799},
                {"eligible": True, "accuracy": 0.60},
            )[0],
            "stable",
        )
        self.assertEqual(
            analytics._trajectory(
                {"eligible": True, "accuracy": 0.60},
                {"eligible": True, "accuracy": 0.80},
            )[0],
            "declining",
        )
        self.assertEqual(
            analytics._trajectory(
                {"eligible": False, "accuracy": 0.80},
                {"eligible": True, "accuracy": 0.60},
            ),
            ("unavailable", None),
        )

    def test_personal_baseline_is_same_language_bounded_and_scope_excluding(self) -> None:
        target_id = self._entry("target")
        comparator_id = self._entry("comparator")
        excluded_collection_id = create_collection("Target Scope", card_size=10)
        excluded_id = self._entry("excluded")
        add_entries_to_collection([target_id, excluded_id], excluded_collection_id)
        now = "2026-08-01T00:00:00+00:00"
        conn = db.get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO entry_templates (
                    name, description, language, template_type,
                    is_system, created_at, updated_at
                ) VALUES ('Synthetic Target Template', '', 'English', 'custom', 0, ?, ?)
                """,
                (now, now),
            )
            template_id = int(cursor.lastrowid)
            conn.execute(
                "UPDATE entries SET template_id = ? WHERE id IN (?, ?)",
                (template_id, target_id, excluded_id),
            )
            conn.commit()
        finally:
            conn.close()

        comparator_sessions = [self._session() for _ in range(10)]
        for index in range(60):
            outcome = 0 if index < 10 else 1
            timestamp = (
                datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(days=index // 5)
            ).isoformat()
            self._log(
                comparator_sessions[index % len(comparator_sessions)],
                comparator_id,
                outcome,
                timestamp,
            )
        self._add_outcomes(excluded_id, [0] * 20, session_count=5)

        french_id = self._entry("french-only", language="French")
        self._add_outcomes(french_id, [1] * 5, session_count=3)

        with db.get_connection() as conn:
            entry_baseline = get_personal_baseline(
                conn,
                "English",
                0.85,
                target_scope_type="entry",
                target_scope_id=target_id,
                as_of_date=AS_OF,
            )
            collection_baseline = get_personal_baseline(
                conn,
                "English",
                0.85,
                target_scope_type="collection",
                target_scope_id=excluded_collection_id,
                as_of_date=AS_OF,
            )
            template_baseline = get_personal_baseline(
                conn,
                "English",
                0.85,
                target_scope_type="template",
                target_scope_id=template_id,
                as_of_date=AS_OF,
            )
            template_coverage = get_template_coverage_profile(
                conn,
                template_id,
                as_of_date=AS_OF,
            )
            no_fallback = get_personal_baseline(
                conn,
                "French",
                0.80,
                target_scope_type="entry",
                target_scope_id=french_id,
                as_of_date=AS_OF,
            )

        self.assertTrue(entry_baseline["eligible"])
        self.assertEqual(entry_baseline["attempts"], 50)
        self.assertEqual(entry_baseline["accuracy"], 0.6)
        self.assertEqual(entry_baseline["comparison"], "above_baseline")
        self.assertTrue(collection_baseline["eligible"])
        self.assertEqual(collection_baseline["attempts"], 50)
        self.assertEqual(collection_baseline["accuracy"], 1.0)
        self.assertEqual(collection_baseline["comparison"], "below_baseline")
        self.assertEqual(template_baseline["accuracy"], 1.0)
        self.assertEqual(template_baseline["comparison"], "below_baseline")
        self.assertEqual(template_coverage["total_current_entries"], 2)
        self.assertEqual(template_coverage["touched_count"], 1)
        self.assertFalse(no_fallback["eligible"])
        self.assertEqual(no_fallback["comparison"], "unavailable")

        self.assertEqual(analytics._personal_baseline_from_loaded(
            {1: {"language": "English", "collection_ids": [], "template_id": None}},
            [],
            language="English",
            target_accuracy=0.85,
            target_scope_type="entry",
            target_scope_id=1,
        )["comparison"], "unavailable")

    def test_personal_baseline_exact_comparison_boundaries(self) -> None:
        target_id = self._entry("baseline-boundary-target")
        comparator_id = self._entry("baseline-boundary-comparator")
        outcomes = [1] * 14 + [0] * 6
        self._add_outcomes(comparator_id, outcomes, session_count=5)

        with db.get_connection() as conn:
            above = get_personal_baseline(
                conn,
                "English",
                0.85,
                target_scope_type="entry",
                target_scope_id=target_id,
                as_of_date=AS_OF,
            )
            below = get_personal_baseline(
                conn,
                "English",
                0.55,
                target_scope_type="entry",
                target_scope_id=target_id,
                as_of_date=AS_OF,
            )
            near = get_personal_baseline(
                conn,
                "English",
                0.849,
                target_scope_type="entry",
                target_scope_id=target_id,
                as_of_date=AS_OF,
            )

        self.assertEqual(above["accuracy"], 0.70)
        self.assertEqual(above["delta_pp"], 15.0)
        self.assertEqual(above["comparison"], "above_baseline")
        self.assertEqual(below["delta_pp"], -15.0)
        self.assertEqual(below["comparison"], "below_baseline")
        self.assertEqual(near["delta_pp"], 14.9)
        self.assertEqual(near["comparison"], "near_baseline")

    def test_coverage_boundaries_and_cross_collection_scope_activity(self) -> None:
        self.assertEqual(analytics._coverage_state(0.49, (0.50, 0.80)), "limited")
        self.assertEqual(analytics._coverage_state(0.50, (0.50, 0.80)), "partial")
        self.assertEqual(analytics._coverage_state(0.79, (0.50, 0.80)), "partial")
        self.assertEqual(analytics._coverage_state(0.80, (0.50, 0.80)), "broad")
        self.assertEqual(analytics._coverage_state(0.29, (0.30, 0.60)), "limited")
        self.assertEqual(analytics._coverage_state(0.30, (0.30, 0.60)), "partial")
        self.assertEqual(analytics._coverage_state(0.59, (0.30, 0.60)), "partial")
        self.assertEqual(analytics._coverage_state(0.60, (0.30, 0.60)), "substantial")

        profiles = [
            {
                "attempts": 1 if index < 80 else 0,
                "evidence_state": "sufficient" if index < 60 else "sparse",
            }
            for index in range(100)
        ]
        exact = analytics._coverage_profile(
            profiles,
            scope_type="synthetic",
            scope_id=1,
        )
        self.assertEqual(exact["touched_ratio"], 0.80)
        self.assertEqual(exact["touched_state"], "broad")
        self.assertEqual(exact["interpretable_ratio"], 0.60)
        self.assertEqual(exact["interpretable_state"], "substantial")

        collection_a = create_collection("Collection A", card_size=10)
        collection_b = create_collection("Collection B", card_size=10)
        entry_id = self._entry("cross-collection")
        add_entries_to_collection([entry_id], collection_a)
        add_entries_to_collection([entry_id], collection_b)
        self._add_outcomes(
            entry_id,
            [1],
            session_count=1,
            collection_id=collection_b,
        )

        with db.get_connection() as conn:
            coverage_a = get_collection_coverage_profile(conn, collection_a, as_of_date=AS_OF)
            activity_a = get_collection_scope_activity_profile(conn, collection_a, as_of_date=AS_OF)
            activity_b = get_collection_scope_activity_profile(conn, collection_b, as_of_date=AS_OF)

        self.assertEqual(coverage_a["touched_count"], 1)
        self.assertEqual(activity_a["eligible_attempts"], 0)
        self.assertEqual(activity_b["eligible_attempts"], 1)

    def test_current_card_history_and_deleted_entry_boundaries(self) -> None:
        collection_id = create_collection("Card History", card_size=1)
        original_id = self._entry("original")
        second_id = self._entry("second")
        replacement_id = self._entry("replacement")
        add_entries_to_collection([original_id, second_id], collection_id)
        historical_session = self._session(collection_id=collection_id, card_number=1)
        self._log(historical_session, original_id, 1, "2026-08-10T10:00:00+00:00")

        remove_entries_from_collection(
            [original_id],
            collection_id,
            confirm_cross_card=True,
        )
        add_entries_to_collection([replacement_id], collection_id)

        deleted_id = self._entry("deleted")
        deleted_session = self._session(collection_id=collection_id)
        self._log(deleted_session, deleted_id, 0, "2026-08-10T11:00:00+00:00")
        delete_entry(deleted_id)

        with db.get_connection() as conn:
            current_card = get_card_coverage_profile(
                conn,
                collection_id,
                1,
                as_of_date=AS_OF,
            )
            historical = get_historical_card_evidence_context(conn, historical_session)
            deleted_profile = get_entry_evidence_profile(conn, deleted_id, as_of_date=AS_OF)
            deleted_log = conn.execute(
                "SELECT entry_id, is_correct FROM quiz_item_logs WHERE session_id = ?",
                (deleted_session,),
            ).fetchone()

        self.assertEqual(current_card["total_current_entries"], 1)
        self.assertEqual(current_card["touched_count"], 0)
        self.assertEqual(historical["entry_ids"], [original_id])
        self.assertEqual(historical["membership_source"], "historical_card_revision")
        self.assertIsNone(deleted_profile)
        self.assertEqual(tuple(deleted_log), (deleted_id, 0))

    def test_batch_a_public_analytics_are_read_only(self) -> None:
        entry_id = self._entry("read-only")
        add_entries_to_collection([entry_id], self.default_collection_id)
        self._add_outcomes(entry_id, [1, 0, 1, 1, 0], session_count=3)

        with db.get_connection() as conn:
            before = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "entries",
                    "entry_collections",
                    "quiz_sessions",
                    "quiz_item_logs",
                    "cards",
                    "card_revisions",
                )
            }
            get_entry_evidence_profiles(conn, as_of_date=AS_OF)
            get_collection_coverage_profile(
                conn,
                self.default_collection_id,
                as_of_date=AS_OF,
            )
            get_card_coverage_profile(
                conn,
                self.default_collection_id,
                1,
                as_of_date=AS_OF,
            )
            after = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in before
            }

        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()

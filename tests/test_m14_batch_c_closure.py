from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from src import db, statistics
from src.analytics import (
    get_collection_coverage_profile,
    get_collection_scope_activity_profile,
    get_entry_evidence_profile,
    get_historical_card_evidence_context,
)
from src.card_history import get_current_card_identity
from src.collections import (
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    remove_entries_from_collection,
)
from src.entries import add_entry, delete_entry
from src.entry_templates import create_entry_template, ensure_general_entry_template
from src.insights import build_learning_brief, get_all_findings, get_entry_findings


AS_OF = date(2026, 8, 12)


class M14BatchCClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "m14_batch_c.sqlite3"
        db.init_db()
        self.default_collection_id = create_collection(
            "Synthetic Evidence Context", card_size=10
        )

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _entry(self, label: str, language: str = "English") -> int:
        return add_entry(language, "English", "word", label, f"meaning-{label}")

    def _bulk_entries(self, count: int) -> tuple[list[int], int, int]:
        general_template_id = ensure_general_entry_template()
        custom_template_id = create_entry_template(
            "Synthetic Secondary Template",
            "Privacy-safe integrated acceptance fixture.",
            "French",
        )
        now = "2026-08-01T00:00:00+00:00"
        entry_ids = []
        with db.get_connection() as conn:
            for index in range(count):
                template_id = general_template_id if index < 80 else custom_template_id
                language = "English" if index < 80 else "French"
                cursor = conn.execute(
                    """
                    INSERT INTO entries (
                        template_id, language, explanation_language, entry_type,
                        term, meaning, example, notes, tags, source, status,
                        created_at, updated_at
                    ) VALUES (?, ?, 'English', 'word', ?, ?, '', '', '',
                              'synthetic-fixture', 'new', ?, ?)
                    """,
                    (
                        template_id,
                        language,
                        f"synthetic-{index:03d}",
                        f"meaning-{index:03d}",
                        now,
                        now,
                    ),
                )
                entry_ids.append(int(cursor.lastrowid))
        return entry_ids, general_template_id, custom_template_id

    def _add_outcomes(
        self,
        entry_id: int,
        outcomes: list[int],
        *,
        collection_id: int | None = None,
        card_number: int = 0,
        last_age_days: int = 1,
    ) -> list[int]:
        collection_id = collection_id or self.default_collection_id
        card_id = None
        card_revision_id = None
        if collection_id is not None and card_number > 0:
            with db.get_connection() as conn:
                identity = get_current_card_identity(
                    conn, collection_id, card_number
                )
            if identity is not None:
                card_id = int(identity["card_id"])
                card_revision_id = int(identity["card_revision_id"])

        session_ids = []
        with db.get_connection() as conn:
            for index, outcome in enumerate(outcomes):
                age_days = last_age_days + len(outcomes) - index - 1
                answered_at = datetime.combine(
                    AS_OF - timedelta(days=age_days),
                    time(12, 0),
                    tzinfo=timezone.utc,
                ).isoformat()
                cursor = conn.execute(
                    """
                    INSERT INTO quiz_sessions (
                        collection_id, card_number, quiz_type, started_at,
                        completed_at, total_items, correct_count, wrong_count,
                        status, card_id, card_revision_id
                    ) VALUES (?, ?, 'term_to_meaning', ?, ?, 1, ?, ?,
                              'completed', ?, ?)
                    """,
                    (
                        collection_id,
                        card_number,
                        answered_at,
                        answered_at,
                        int(outcome),
                        1 - int(outcome),
                        card_id,
                        card_revision_id,
                    ),
                )
                session_id = int(cursor.lastrowid)
                session_ids.append(session_id)
                conn.execute(
                    """
                    INSERT INTO quiz_item_logs (
                        session_id, entry_id, prompt, expected_answer,
                        user_answer, is_correct, answered_at
                    ) VALUES (?, ?, ?, ?, 'synthetic-answer', ?, ?)
                    """,
                    (
                        session_id,
                        entry_id,
                        f"prompt-{entry_id}",
                        f"answer-{entry_id}",
                        int(outcome),
                        answered_at,
                    ),
                )
        return session_ids

    def test_entry_health_contradiction_matrix_uses_m14_authority(self) -> None:
        developing = self._entry("developing")
        recovery = self._entry("recovery")
        aging_strength = self._entry("aging-strength")
        mistake_strength = self._entry("mistake-strength")
        mixed_none = self._entry("mixed-none")
        proficient_attention = self._entry("proficient-attention")
        stale_strength = self._entry("stale-strength")

        self._add_outcomes(developing, [1, 1, 1])
        self._add_outcomes(recovery, [0, 0, 0, 0, 1, 1, 1, 1, 1, 0])
        self._add_outcomes(aging_strength, [1, 1, 1, 1, 0, 1, 1, 1, 1, 0], last_age_days=45)
        self._add_outcomes(mistake_strength, [1, 1, 1, 1, 0, 1, 1, 1, 1, 0])
        self._add_outcomes(mixed_none, [1, 0, 1, 0, 1])
        self._add_outcomes(proficient_attention, [1, 1, 1, 1, 1, 0, 0, 0, 0, 1])
        self._add_outcomes(stale_strength, [1, 1, 1, 1, 0, 1, 1, 1, 1, 0], last_age_days=90)
        add_entries_to_system_collection(
            [mistake_strength, recovery], "mistake_book"
        )
        add_entries_to_system_collection([proficient_attention], "proficient_pool")

        with db.get_connection() as conn:
            weak_ids = {
                row["entry_id"]
                for row in statistics.get_weak_entries(conn, as_of_date=AS_OF)
            }
            strong_ids = {
                row["entry_id"]
                for row in statistics.get_strong_entries(conn, as_of_date=AS_OF)
            }
            stale_ids = {
                row["entry_id"]
                for row in statistics.get_neglected_entries(conn, as_of_date=AS_OF)
            }
            risk_ids = {
                row["entry_id"]
                for row in statistics.get_proficient_risk_entries(
                    conn, as_of_date=AS_OF
                )
            }
            recovery_ids = {
                row["entry_id"]
                for row in statistics.get_mistake_recovery_candidates(
                    conn, as_of_date=AS_OF
                )
            }
            overview = statistics.get_entry_health_overview(
                conn, as_of_date=AS_OF
            )

        self.assertNotIn(developing, strong_ids)
        self.assertNotIn(recovery, weak_ids)
        self.assertIn(aging_strength, strong_ids)
        self.assertIn(mistake_strength, strong_ids)
        self.assertNotIn(mistake_strength, weak_ids)
        self.assertNotIn(mixed_none, weak_ids | strong_ids | stale_ids)
        self.assertIn(proficient_attention, weak_ids)
        self.assertIn(proficient_attention, risk_ids)
        self.assertIn(stale_strength, stale_ids)
        self.assertNotIn(stale_strength, strong_ids)
        self.assertIn(recovery, recovery_ids)
        self.assertEqual(overview["insufficient_evidence"], 1)
        self.assertEqual(overview["recovery"], 1)
        self.assertEqual(overview["needs_attention"], 1)
        self.assertEqual(overview["stale_evidence"], 1)
        self.assertEqual(overview["strength"], 2)
        self.assertEqual(overview["none"], 1)

    def test_personal_baseline_remains_context_only_end_to_end(self) -> None:
        positive_target = self._entry("positive-target", "English")
        english_comparator = self._entry("english-comparator", "English")
        negative_target = self._entry("negative-target", "French")
        french_comparator = self._entry("french-comparator", "French")
        self._add_outcomes(positive_target, [1, 1, 1, 1, 0])
        self._add_outcomes(english_comparator, [1] * 20)
        self._add_outcomes(negative_target, [1, 1, 0, 0, 0])
        self._add_outcomes(french_comparator, [0] * 20)

        with db.get_connection() as conn:
            findings = {
                row["scope_id"]: row
                for row in get_entry_findings(conn, as_of_date=AS_OF)
            }
            positive_profile = get_entry_evidence_profile(
                conn, positive_target, as_of_date=AS_OF
            )
            negative_profile = get_entry_evidence_profile(
                conn, negative_target, as_of_date=AS_OF
            )

        self.assertEqual(
            positive_profile["baseline"]["comparison"], "below_baseline"
        )
        self.assertEqual(findings[positive_target]["primary_finding"], "none")
        self.assertEqual(
            negative_profile["baseline"]["comparison"], "above_baseline"
        )
        self.assertNotEqual(
            findings[negative_target]["primary_finding"], "strength"
        )

    def test_cross_collection_activity_survives_membership_removal(self) -> None:
        collection_a = create_collection("Scope A", card_size=8)
        collection_b = create_collection("Scope B", card_size=8)
        entry_id = self._entry("cross-collection")
        add_entries_to_collection([entry_id], collection_a)
        add_entries_to_collection([entry_id], collection_b)
        self._add_outcomes(entry_id, [1, 1, 1, 1, 1], collection_id=collection_b)

        with db.get_connection() as conn:
            a_before = get_collection_coverage_profile(
                conn, collection_a, as_of_date=AS_OF
            )
            b_before = get_collection_coverage_profile(
                conn, collection_b, as_of_date=AS_OF
            )
        self.assertEqual(a_before["touched_count"], 1)
        self.assertEqual(a_before["scope_activity"]["eligible_attempts"], 0)
        self.assertEqual(b_before["touched_count"], 1)
        self.assertEqual(b_before["scope_activity"]["eligible_attempts"], 5)

        remove_entries_from_collection([entry_id], collection_b)
        with db.get_connection() as conn:
            b_after = get_collection_coverage_profile(
                conn, collection_b, as_of_date=AS_OF
            )
            activity_after = get_collection_scope_activity_profile(
                conn, collection_b, as_of_date=AS_OF
            )
        self.assertEqual(b_after["total_current_entries"], 0)
        self.assertEqual(activity_after["eligible_attempts"], 5)

    def test_card_revision_and_deleted_entry_history_remain_non_actionable(self) -> None:
        collection_id = create_collection("Revision acceptance", card_size=3)
        entry_a = self._entry("revision-a")
        entry_b = self._entry("revision-b")
        entry_c = self._entry("revision-c")
        entry_d = self._entry("revision-d")
        add_entries_to_collection([entry_a, entry_b, entry_c], collection_id)
        session_id = self._add_outcomes(
            entry_b,
            [0],
            collection_id=collection_id,
            card_number=1,
        )[0]
        remove_entries_from_collection([entry_b], collection_id)
        add_entries_to_collection([entry_d], collection_id)
        delete_entry(entry_b)

        with db.get_connection() as conn:
            context = get_historical_card_evidence_context(conn, session_id)
            current = get_collection_coverage_profile(
                conn, collection_id, as_of_date=AS_OF
            )
            log = dict(
                conn.execute(
                    """
                    SELECT entry_id, prompt, expected_answer, is_correct
                    FROM quiz_item_logs WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()
            )
            findings = get_entry_findings(conn, as_of_date=AS_OF)

        self.assertEqual(context["entry_ids"], [entry_a, entry_b, entry_c])
        self.assertEqual(current["total_current_entries"], 3)
        self.assertEqual(log["entry_id"], entry_b)
        self.assertEqual(log["prompt"], f"prompt-{entry_b}")
        self.assertEqual(log["expected_answer"], f"answer-{entry_b}")
        self.assertEqual(log["is_correct"], 0)
        self.assertNotIn(entry_b, [row["scope_id"] for row in findings])

    def test_integrated_synthetic_learner_is_deterministic_read_only_and_bounded(self) -> None:
        entry_ids, _, _ = self._bulk_entries(100)
        collection_a = create_collection("Integrated A", card_size=10)
        collection_b = create_collection("Integrated B", card_size=10)
        collection_c = create_collection("Integrated C", card_size=10)
        add_entries_to_collection(entry_ids[:50], collection_a)
        add_entries_to_collection(entry_ids[40:80], collection_b)
        add_entries_to_collection(entry_ids[80:], collection_c)

        self._add_outcomes(entry_ids[1], [1, 1])
        self._add_outcomes(entry_ids[2], [1, 1, 1])
        self._add_outcomes(entry_ids[3], [1, 0, 1, 0, 1])
        self._add_outcomes(entry_ids[4], [1, 1, 1, 1, 1, 0, 0, 0, 0, 1])
        self._add_outcomes(entry_ids[5], [0, 0, 0, 0, 1, 1, 1, 1, 1, 0])
        self._add_outcomes(entry_ids[6], [1, 1, 1, 1, 0, 1, 1, 1, 1, 0])
        self._add_outcomes(entry_ids[7], [1, 1, 1, 1, 0, 1, 1, 1, 1, 0], last_age_days=90)
        self._add_outcomes(entry_ids[8], [1, 1, 1, 1, 0, 1, 1, 1, 1, 0], last_age_days=45)
        self._add_outcomes(entry_ids[9], [1, 1, 1, 1, 0, 1, 1, 1, 1, 0])
        self._add_outcomes(entry_ids[10], [1, 1, 1, 1, 1, 0, 0, 0, 0, 1])
        add_entries_to_system_collection([entry_ids[9]], "mistake_book")
        add_entries_to_system_collection([entry_ids[10]], "proficient_pool")

        durable_tables = (
            "entries",
            "entry_collections",
            "collections",
            "quiz_sessions",
            "quiz_item_logs",
            "cards",
            "card_revisions",
            "card_review_states",
            "card_review_logs",
        )
        with db.get_connection() as conn:
            before = {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in durable_tables
            }
            select_statements = []
            conn.set_trace_callback(
                lambda statement: select_statements.append(statement)
                if statement.lstrip().upper().startswith("SELECT")
                else None
            )
            first = get_all_findings(conn, as_of_date=AS_OF)
            first_brief = build_learning_brief(conn, first["full_findings"])
            conn.set_trace_callback(None)
            second = get_all_findings(conn, as_of_date=AS_OF)
            second_brief = build_learning_brief(conn, second["full_findings"])
            after = {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in durable_tables
            }

        counts = {}
        for finding in first["entry_findings"]:
            key = finding["primary_finding"]
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(len(first["entry_findings"]), 100)
        self.assertEqual(sum(counts.values()), 100)
        self.assertEqual(first, second)
        self.assertEqual(first_brief, second_brief)
        self.assertLessEqual(len(first_brief), 5)
        self.assertEqual(before, after)
        self.assertLess(len(select_statements), 200)
        self.assertGreater(len(first["coverage_findings"]), 0)
        self.assertEqual(
            counts,
            {
                "never_quizzed": 90,
                "insufficient_evidence": 2,
                "none": 1,
                "needs_attention": 2,
                "recovery": 1,
                "strength": 3,
                "stale_evidence": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()

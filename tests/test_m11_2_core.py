from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import db, quiz
from src.card_history import reconcile_collection_card_history
from src.learning_workflow import (
    get_card_learning_history,
    get_study_cards,
    get_today_card_learning_activity,
)
from src.ui_streamlit.entries_page import _edit_widget_key
from src.ui_streamlit.quiz_page import _compatible_quiz_type_options
from src.ui_streamlit.review_page import _review_quiz_focus_values


class M112CoreIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "m11_2_test.sqlite3"
        db.init_db()
        now = "2026-01-02T10:00:00+00:00"
        with db.get_connection() as conn:
            collection_cursor = conn.execute(
                """
                INSERT INTO collections (name, description, card_size, created_at, updated_at)
                VALUES ('Synthetic Collection', '', 8, ?, ?)
                """,
                (now, now),
            )
            self.collection_id = int(collection_cursor.lastrowid)
            entry_cursor = conn.execute(
                """
                INSERT INTO entries (
                    language, explanation_language, entry_type, term, meaning,
                    example, notes, tags, source, status, created_at, updated_at
                ) VALUES ('English', 'English', 'word', 'synthetic-term',
                          'synthetic-meaning', '', '', '', '', 'new', ?, ?)
                """,
                (now, now),
            )
            self.entry_id = int(entry_cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO entry_collections (entry_id, collection_id, position, added_at)
                VALUES (?, ?, 1, ?)
                """,
                (self.entry_id, self.collection_id, now),
            )
            reconcile_collection_card_history(
                conn,
                self.collection_id,
                change_reason="synthetic_test_fixture",
            )

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _completed_session(self, card_number: int = 1) -> dict:
        with patch.object(quiz, "_now_iso", return_value="2026-01-02T10:00:00+00:00"):
            session_id = quiz.create_quiz_session(
                self.collection_id, card_number, "term_to_meaning", 1
            )
        with patch.object(quiz, "_now_iso", return_value="2026-01-02T10:05:00+00:00"):
            result = quiz.record_quiz_answer(
                session_id,
                self.entry_id,
                "synthetic-term",
                "synthetic-meaning",
                "synthetic-meaning",
                True,
            )
        self.assertTrue(result["logged"])
        with patch.object(quiz, "_now_iso", return_value="2026-01-02T10:10:00+00:00"):
            return quiz.complete_quiz_session(session_id)

    def test_completion_is_idempotent_and_uses_answer_time(self) -> None:
        first = self._completed_session()
        self.assertEqual(first["completed_at"], "2026-01-02T10:05:00+00:00")

        with patch.object(quiz, "_now_iso", return_value="2026-01-03T12:00:00+00:00"):
            second = quiz.complete_quiz_session(first["id"])

        self.assertEqual(second["completed_at"], first["completed_at"])
        with db.get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM quiz_sessions WHERE id = ? AND status = 'completed'",
                (first["id"],),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_cancelled_session_cannot_be_completed(self) -> None:
        session_id = quiz.create_quiz_session(
            self.collection_id, 1, "term_to_meaning", 1
        )
        quiz.mark_quiz_session_cancelled(session_id)
        with self.assertRaisesRegex(ValueError, "cancelled"):
            quiz.complete_quiz_session(session_id)
        self.assertEqual(quiz.get_quiz_session(session_id)["status"], "cancelled")

    def test_reconciliation_uses_last_durable_answer_and_runs_once(self) -> None:
        session_id = quiz.create_quiz_session(
            self.collection_id, 1, "term_to_meaning", 2
        )
        with db.get_connection() as conn:
            for index, answered_at in enumerate(
                ("2026-01-02T11:01:00+00:00", "2026-01-02T11:03:00+00:00")
            ):
                conn.execute(
                    """
                    INSERT INTO quiz_item_logs (
                        session_id, entry_id, prompt, expected_answer,
                        user_answer, is_correct, answered_at
                    ) VALUES (?, ?, ?, 'answer', 'answer', 1, ?)
                    """,
                    (session_id, self.entry_id, f"prompt-{index}", answered_at),
                )

        with patch.object(quiz, "_now_iso", return_value="2026-01-05T09:00:00+00:00"):
            self.assertEqual(quiz.reconcile_finished_active_quiz_sessions(), 1)
            self.assertEqual(quiz.reconcile_finished_active_quiz_sessions(), 0)

        session = quiz.get_quiz_session(session_id)
        self.assertEqual(session["completed_at"], "2026-01-02T11:03:00+00:00")
        self.assertEqual(session["status"], "completed")

    def test_non_card_quiz_does_not_create_card_learning_activity(self) -> None:
        self._completed_session(card_number=0)
        with db.get_connection() as conn:
            activity = get_today_card_learning_activity(conn, "2026-01-02")
        self.assertEqual(activity["reviewed_cards"], 0)
        self.assertEqual(activity["reviewed_entries"], 0)

    def test_manual_schedule_log_is_not_card_learning_activity(self) -> None:
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO card_review_logs (
                    collection_id, card_number, reviewed_at, rating,
                    previous_interval_days, new_interval_days,
                    previous_due_at, next_due_at, entry_count
                ) VALUES (?, 1, '2026-01-02T12:00:00+00:00',
                          'manual_schedule_update', 0, 0, NULL, '2026-01-03', 1)
                """,
                (self.collection_id,),
            )
            activity = get_today_card_learning_activity(conn, "2026-01-02")
            legacy_row_count = conn.execute(
                "SELECT COUNT(*) FROM card_review_logs WHERE rating = 'manual_schedule_update'"
            ).fetchone()[0]
        self.assertEqual(activity["reviewed_cards"], 0)
        self.assertEqual(legacy_row_count, 1)

    def test_card_completion_populates_study_and_history_views(self) -> None:
        completed = self._completed_session(card_number=1)
        with db.get_connection() as conn:
            cards = get_study_cards(conn)
            history = get_card_learning_history(conn, self.collection_id, 1)
        self.assertEqual(cards[0]["completion_count"], 1)
        self.assertEqual(cards[0]["last_completed_at"], completed["completed_at"])
        self.assertEqual(history[0]["session_id"], completed["id"])

    def test_browsing_card_without_quiz_does_not_complete_learning(self) -> None:
        with db.get_connection() as conn:
            cards = get_study_cards(conn)
            history = get_card_learning_history(conn, self.collection_id, 1)
            activity = get_today_card_learning_activity(conn, "2026-01-02")
        self.assertEqual(cards[0]["completion_count"], 0)
        self.assertEqual(history, [])
        self.assertEqual(activity["reviewed_cards"], 0)

    def test_entry_edit_keys_are_entry_specific(self) -> None:
        self.assertNotEqual(_edit_widget_key(1, "language"), _edit_widget_key(2, "language"))
        self.assertNotEqual(_edit_widget_key(1, "collections"), _edit_widget_key(2, "collections"))
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "ui_streamlit"
            / "entries_page.py"
        ).read_text(encoding="utf-8")
        self.assertIn("key_prefix=f\"edit_template_{edit_entry['id']}\"", source)
        for field_name in (
            "language",
            "explanation_language",
            "entry_type",
            "status",
            "canonical_term",
            "canonical_meaning",
            "collections",
        ):
            self.assertIn(f'_edit_widget_key(entry_id, "{field_name}")', source)

    def test_entry_edit_app_switch_does_not_leak_widget_state(self) -> None:
        from src.entries import create_entry_with_template, search_entries
        from streamlit.testing.v1 import AppTest

        with db.get_connection() as conn:
            conn.execute("DELETE FROM entries")

        first_entry_id = create_entry_with_template(
            {
                "language": "English",
                "explanation_language": "English",
                "entry_type": "word",
                "status": "new",
            },
            {
                "term": "alpha",
                "meaning": "first",
                "example": "",
                "notes": "",
                "tags": "",
                "source": "",
            },
        )
        second_entry_id = create_entry_with_template(
            {
                "language": "French",
                "explanation_language": "Chinese",
                "entry_type": "phrase",
                "status": "learning",
            },
            {
                "term": "beta",
                "meaning": "second",
                "example": "",
                "notes": "",
                "tags": "",
                "source": "",
            },
        )

        project_root = Path(__file__).resolve().parents[1]
        app = AppTest.from_file(str(project_root / "app.py")).run(timeout=30)
        app.sidebar.radio[0].set_value("Entries")
        app.run(timeout=30)
        app.radio[0].set_value("Edit")
        app.run(timeout=30)

        entry_selector = next(
            widget for widget in app.selectbox if widget.key == "edit_entry_select"
        )
        first_entry = next(
            entry for entry in search_entries() if entry["id"] == first_entry_id
        )
        entry_selector.set_value(first_entry)
        app.run(timeout=30)

        next(
            widget
            for widget in app.selectbox
            if widget.key == _edit_widget_key(first_entry_id, "entry_type")
        ).set_value("conjugation")
        next(
            widget
            for widget in app.text_input
            if widget.key.startswith(f"edit_template_{first_entry_id}_")
            and widget.label == "Term *"
        ).set_value("unsaved-alpha")
        app.run(timeout=30)

        entry_selector = next(
            widget for widget in app.selectbox if widget.key == "edit_entry_select"
        )
        second_entry = next(
            entry for entry in search_entries() if entry["id"] == second_entry_id
        )
        entry_selector.set_value(second_entry)
        app.run(timeout=30)

        second_type = next(
            widget
            for widget in app.selectbox
            if widget.key == _edit_widget_key(second_entry_id, "entry_type")
        )
        second_term = next(
            widget
            for widget in app.text_input
            if widget.key.startswith(f"edit_template_{second_entry_id}_")
            and widget.label == "Term *"
        )
        self.assertEqual(second_type.value, "phrase")
        self.assertEqual(second_term.value, "beta")
        self.assertEqual(list(app.exception), [])

    def test_review_quiz_routes_preserve_card_context(self) -> None:
        card = {
            "collection_id": self.collection_id,
            "collection_name": "Synthetic Collection",
            "card_number": 1,
        }
        quick = _review_quiz_focus_values(card, autostart=True)
        choose = _review_quiz_focus_values(card, autostart=False)
        self.assertEqual(quick["quiz_focus_collection_id"], self.collection_id)
        self.assertEqual(quick["quiz_focus_card_number"], 1)
        self.assertEqual(quick["quiz_focus_reason"], "review_quick_quiz")
        self.assertEqual(choose["quiz_focus_collection_id"], self.collection_id)
        self.assertEqual(choose["quiz_focus_card_number"], 1)
        self.assertEqual(choose["quiz_focus_reason"], "review_choose_quiz_type")

        choose_focus = {
            "collection_id": choose["quiz_focus_collection_id"],
            "card_number": choose["quiz_focus_card_number"],
            "reason": choose["quiz_focus_reason"],
        }
        focused_options = _compatible_quiz_type_options(choose_focus)
        self.assertNotIn("matching", focused_options.values())
        self.assertIn("mixed_mcq", focused_options.values())
        self.assertIn("matching", _compatible_quiz_type_options(None).values())

    def test_review_choose_quiz_app_exposes_only_card_scoped_standard_modes(self) -> None:
        from streamlit.testing.v1 import AppTest

        project_root = Path(__file__).resolve().parents[1]
        app = AppTest.from_file(str(project_root / "app.py")).run(timeout=30)
        app.session_state["quiz_focus_collection_id"] = self.collection_id
        app.session_state["quiz_focus_card_number"] = 1
        app.session_state["quiz_focus_type"] = "mixed_mcq"
        app.session_state["quiz_focus_source"] = "review_selected_card"
        app.session_state["quiz_focus_reason"] = "review_choose_quiz_type"
        app.session_state["quiz_focus_title"] = "Synthetic Collection / Card #1"
        app.sidebar.radio[0].set_value("Quiz")
        app.run(timeout=30)

        collection_selector = next(
            widget for widget in app.selectbox if widget.key == "quiz_collection_select"
        )
        card_selector = next(
            widget for widget in app.selectbox if widget.key == "quiz_card_select"
        )
        type_selector = next(
            widget for widget in app.selectbox if widget.key == "quiz_type_select"
        )
        self.assertEqual(collection_selector.value["id"], self.collection_id)
        self.assertEqual(card_selector.value, 1)
        self.assertNotIn("Matching", type_selector.options)
        self.assertIn("Mixed Multiple Choice", type_selector.options)
        self.assertNotIn("Matching Practice", [button.label for button in app.button])
        self.assertEqual(list(app.exception), [])

        standalone_app = AppTest.from_file(str(project_root / "app.py")).run(timeout=30)
        standalone_app.sidebar.radio[0].set_value("Quiz")
        standalone_app.run(timeout=30)
        standalone_type_selector = next(
            widget
            for widget in standalone_app.selectbox
            if widget.key == "quiz_type_select"
        )
        self.assertIn("Matching", standalone_type_selector.options)
        self.assertEqual(list(standalone_app.exception), [])

    def test_direct_and_both_review_routes_use_one_completion_per_session(self) -> None:
        card = {
            "collection_id": self.collection_id,
            "collection_name": "Synthetic Collection",
            "card_number": 1,
        }
        route_scopes = [
            {"quiz_focus_collection_id": self.collection_id, "quiz_focus_card_number": 1},
            _review_quiz_focus_values(card, autostart=True),
            _review_quiz_focus_values(card, autostart=False),
        ]
        completion_times = []
        for route_scope in route_scopes:
            self.assertEqual(route_scope["quiz_focus_collection_id"], self.collection_id)
            self.assertEqual(route_scope["quiz_focus_card_number"], 1)
            completed = self._completed_session(route_scope["quiz_focus_card_number"])
            completion_times.append(completed["completed_at"])
            quiz.complete_quiz_session(completed["id"])

        with db.get_connection() as conn:
            activity = get_today_card_learning_activity(conn, "2026-01-02")
            session_count = conn.execute(
                """
                SELECT COUNT(*) FROM quiz_sessions
                WHERE collection_id = ? AND card_number = 1 AND status = 'completed'
                """,
                (self.collection_id,),
            ).fetchone()[0]
        self.assertEqual(session_count, 3)
        self.assertEqual(activity["reviewed_cards"], 3)
        self.assertEqual(completion_times, ["2026-01-02T10:05:00+00:00"] * 3)

    def test_active_ui_has_no_legacy_scheduler_mutations(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        active_files = [
            project_root / "src" / "ui_streamlit" / name
            for name in (
                "review_page.py",
                "quiz_page.py",
                "today_page.py",
                "statistics_page.py",
                "dashboard_page.py",
                "review_history_page.py",
            )
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in active_files)
        for retired_text in (
            "update_card_next_due_at",
            "sync_all_card_review_states",
            "Save Next Review Date",
            "Schedule Next Review",
        ):
            self.assertNotIn(retired_text, combined)

    def test_targeted_pages_do_not_render_raw_internal_exceptions(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        for name in ("import_export_page.py", "today_page.py", "statistics_page.py"):
            source = (project_root / "src" / "ui_streamlit" / name).read_text(
                encoding="utf-8"
            )
            self.assertNotIn("st.caption(str(error))", source)
            self.assertNotIn("{error}", source)


if __name__ == "__main__":
    unittest.main()

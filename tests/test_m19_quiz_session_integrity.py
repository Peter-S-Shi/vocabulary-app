from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry
from src.quiz import create_quiz_session, get_active_quiz_session

"""
M19 Phase C -- Quiz session integrity under repeated actions, rapid
re-launch, interruption, and recovery.

The defect this file was written for (found by adversarial probing, not
by a failing test): `QuizController.start()` only rejected a *foreign*
active session. A repeated launch through the same controller -- a
double-clicked Quick Quiz, or a second launch action arriving before the
first session finished -- matched `active["id"] == self.session_id` and
created a second session while the first stayed `active` forever.

Two manifestations of that one root cause:

1. Two concurrently active `quiz_sessions` rows, which the controller's
   own module docstring states can never happen. The orphan was
   unreachable: `get_active_quiz_session()` returns only the newest
   active row, and `reconcile_finished_active_quiz_sessions()` only
   reconciles sessions that are already fully answered, so a
   never-answered orphan was never cleaned up.
2. "Cancel and retry" cancelled only the displayed session, so the user
   was immediately blocked again by the orphan -- a recovery loop with
   nothing on screen explaining it.

The rest of this file records the surrounding behaviors that were
probed and found already correct, so they stay correct: duplicate-answer
protection, idempotent completion, cancel/restart semantics, the
foreign-session block never becoming a fake resume, and the frozen rule
that abandoning a Quiz never fabricates a completion event.
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.quiz_controller import QuizController
    from src.ui_desktop.state.handoff import QuizLaunchIntent

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class _QuizIntegrityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m19_quiz_integrity.sqlite3"
        db.init_db()
        self.collection_id = create_collection("Study", "", card_size=8)
        self.entry_ids = [
            add_entry("French", "English", "word", f"mot{index}", f"word {index}") for index in range(6)
        ]
        add_entries_to_collection(self.entry_ids, self.collection_id)

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _intent(self, **overrides) -> "QuizLaunchIntent":
        base = {
            "source": "review_quick_quiz",
            "collection_id": self.collection_id,
            "collection_name": "Study",
            "card_number": 1,
            "card_id": None,
            "quiz_type": "term_to_meaning",
            "item_count": 5,
            "reason": "m19 integrity probe",
        }
        base.update(overrides)
        return QuizLaunchIntent(**base)

    def _sessions(self) -> list[tuple[int, str]]:
        conn = db.get_connection()
        try:
            return [tuple(row) for row in conn.execute("select id, status from quiz_sessions order by id")]
        finally:
            conn.close()

    def _active_ids(self) -> list[int]:
        return [session_id for session_id, status in self._sessions() if status == "active"]

    def _item_log_count(self, session_id: int | None = None) -> int:
        conn = db.get_connection()
        try:
            if session_id is None:
                return conn.execute("select count(*) from quiz_item_logs").fetchone()[0]
            return conn.execute(
                "select count(*) from quiz_item_logs where session_id = ?", (session_id,)
            ).fetchone()[0]
        finally:
            conn.close()

    def _completed_count(self) -> int:
        conn = db.get_connection()
        try:
            return conn.execute("select count(*) from quiz_sessions where status = 'completed'").fetchone()[0]
        finally:
            conn.close()

    def _answer_through_completion(self, controller: "QuizController") -> None:
        while controller.current_item() is not None:
            controller.reveal_answer()
            controller.submit_self_graded(True)


class RepeatedLaunchLeavesExactlyOneActiveSessionTests(_QuizIntegrityTestCase):
    def test_double_launch_does_not_create_two_active_sessions(self) -> None:
        """Root-cause regression: fails against the pre-fix controller,
        which left the first session `active` forever."""
        controller = QuizController()
        self.assertTrue(controller.start(self._intent()))
        first_session_id = controller.session_id

        self.assertTrue(controller.start(self._intent()))
        second_session_id = controller.session_id

        self.assertNotEqual(first_session_id, second_session_id)
        self.assertEqual(self._active_ids(), [second_session_id])
        statuses = dict(self._sessions())
        self.assertEqual(statuses[first_session_id], "cancelled")

    def test_many_rapid_launches_never_accumulate_active_sessions(self) -> None:
        controller = QuizController()
        for _ in range(5):
            self.assertTrue(controller.start(self._intent()))
            self.assertEqual(len(self._active_ids()), 1)
        self.assertEqual(len(self._active_ids()), 1)
        self.assertEqual(self._completed_count(), 0)

    def test_a_superseded_launch_fabricates_no_completion(self) -> None:
        """Abandoning a Quiz by launching another must cancel, never
        complete -- the frozen learning semantic that only a completed
        Card-scoped Quiz is a learning event."""
        controller = QuizController()
        controller.start(self._intent())
        controller.reveal_answer()
        controller.submit_self_graded(True)
        answered_before = self._item_log_count()

        controller.start(self._intent())

        self.assertEqual(self._completed_count(), 0)
        # The already-recorded answer survives as Entry-level evidence
        # under the now-cancelled session (M14 keeps explicitly answered
        # Items eligible regardless of parent session status).
        self.assertEqual(self._item_log_count(), answered_before)

    def test_a_failed_launch_does_not_destroy_the_session_in_progress(self) -> None:
        """The cancel happens only once the new session is really going
        to be created: a launch that cannot build items must leave the
        running Quiz untouched."""
        controller = QuizController()
        controller.start(self._intent())
        running_session_id = controller.session_id

        empty_collection_id = create_collection("Empty", "", card_size=8)
        self.assertFalse(controller.start(self._intent(collection_id=empty_collection_id)))

        self.assertEqual(controller.session_id, running_session_id)
        self.assertEqual(self._active_ids(), [running_session_id])
        self.assertIsNotNone(controller.start_error)

    def test_restart_active_still_leaves_one_active_session(self) -> None:
        controller = QuizController()
        controller.start(self._intent())
        first_session_id = controller.session_id

        self.assertTrue(controller.restart_active())

        self.assertNotEqual(controller.session_id, first_session_id)
        self.assertEqual(self._active_ids(), [controller.session_id])
        self.assertEqual(dict(self._sessions())[first_session_id], "cancelled")


class BlockedSessionRecoveryTests(_QuizIntegrityTestCase):
    def test_a_foreign_active_session_blocks_without_a_fake_resume(self) -> None:
        first = QuizController()
        first.start(self._intent())
        foreign_session_id = first.session_id

        second = QuizController()  # e.g. after an app restart
        self.assertFalse(second.start(self._intent()))

        self.assertIsNotNone(second.blocked_session)
        self.assertEqual(second.blocked_session["id"], foreign_session_id)
        self.assertIsNone(second.session_id)
        self.assertEqual(second.items, [])

    def test_cancel_and_retry_recovers_from_a_backlog_of_stale_sessions(self) -> None:
        """A database written by an earlier build can hold several
        orphaned active sessions. Recovery must actually recover instead
        of blocking again on the next orphan (the second manifestation of
        the root-cause defect)."""
        stale_ids = [
            create_quiz_session(self.collection_id, 1, "term_to_meaning", 5) for _ in range(3)
        ]
        self.assertEqual(sorted(self._active_ids()), sorted(stale_ids))

        controller = QuizController()
        self.assertFalse(controller.start(self._intent()))
        self.assertIsNotNone(controller.blocked_session)

        self.assertTrue(controller.cancel_blocked_and_retry())

        self.assertIsNone(controller.blocked_session)
        self.assertIsNotNone(controller.session_id)
        self.assertEqual(self._active_ids(), [controller.session_id])
        for stale_id in stale_ids:
            self.assertEqual(dict(self._sessions())[stale_id], "cancelled")

    def test_recovery_cancels_rather_than_completing_stale_sessions(self) -> None:
        stale_ids = [create_quiz_session(self.collection_id, 1, "term_to_meaning", 5) for _ in range(2)]
        controller = QuizController()
        controller.start(self._intent())
        controller.cancel_blocked_and_retry()

        statuses = dict(self._sessions())
        for stale_id in stale_ids:
            self.assertEqual(statuses[stale_id], "cancelled")
        self.assertEqual(self._completed_count(), 0)


class DuplicateAnswerAndCompletionTests(_QuizIntegrityTestCase):
    """Probed and found already correct -- recorded so they stay correct."""

    def test_repeated_self_graded_submit_records_one_answer(self) -> None:
        controller = QuizController()
        controller.start(self._intent())
        controller.reveal_answer()

        self.assertTrue(controller.submit_self_graded(True))
        self.assertFalse(controller.submit_self_graded(True))

        self.assertEqual(self._item_log_count(controller.session_id), 1)

    def test_submitting_before_reveal_records_nothing(self) -> None:
        controller = QuizController()
        controller.start(self._intent())

        self.assertFalse(controller.submit_self_graded(True))

        self.assertEqual(self._item_log_count(controller.session_id), 0)

    def test_completion_is_recorded_once_and_further_submits_are_refused(self) -> None:
        controller = QuizController()
        controller.start(self._intent())
        session_id = controller.session_id
        self._answer_through_completion(controller)

        self.assertIsNotNone(controller.completed_session)
        self.assertFalse(controller.submit_self_graded(True))

        statuses = dict(self._sessions())
        self.assertEqual(statuses[session_id], "completed")
        self.assertEqual(self._completed_count(), 1)

    def test_launching_after_completion_does_not_cancel_the_completed_session(self) -> None:
        controller = QuizController()
        controller.start(self._intent())
        completed_id = controller.session_id
        self._answer_through_completion(controller)

        controller.acknowledge_completion()
        self.assertTrue(controller.start(self._intent()))

        statuses = dict(self._sessions())
        self.assertEqual(statuses[completed_id], "completed")
        self.assertEqual(self._completed_count(), 1)


class AbandonmentNeverCompletesTests(_QuizIntegrityTestCase):
    def test_exiting_an_active_quiz_cancels_it(self) -> None:
        controller = QuizController()
        controller.start(self._intent())
        session_id = controller.session_id

        controller.exit_active()

        self.assertEqual(dict(self._sessions())[session_id], "cancelled")
        self.assertEqual(self._completed_count(), 0)
        self.assertIsNone(controller.session_id)

    def test_repeated_cancel_is_safe(self) -> None:
        controller = QuizController()
        controller.start(self._intent())
        session_id = controller.session_id

        controller.cancel_active()
        controller.cancel_active()

        self.assertEqual(dict(self._sessions())[session_id], "cancelled")
        self.assertEqual(self._completed_count(), 0)

    def test_start_cancel_cycles_leave_no_active_residue(self) -> None:
        """Rapid launch/abandon cycling -- e.g. bouncing in and out of
        Study mode -- must not accumulate active sessions or completions."""
        controller = QuizController()
        for _ in range(4):
            controller.start(self._intent())
            controller.exit_active()

        self.assertEqual(self._active_ids(), [])
        self.assertEqual(self._completed_count(), 0)
        self.assertIsNone(get_active_quiz_session())


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class RapidNavigationLearningEvidenceTests(_QuizIntegrityTestCase):
    """The shell-level counterpart: repeated Study-mode entry/exit and
    workspace switching through a real MainWindow must not fabricate or
    duplicate learning evidence."""

    def test_repeated_study_entry_and_exit_creates_no_learning_evidence(self) -> None:
        from src.ui_desktop.main_window import MainWindow
        from src.ui_desktop.state.app_state import Workspace

        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.analytics_controller.shutdown)

        for _ in range(3):
            window._enter_review()
            window._exit_study_mode()
            window.show_workspace(Workspace.TODAY)

        self.assertEqual(self._sessions(), [])
        self.assertEqual(self._item_log_count(), 0)

    def test_repeated_quiz_launch_through_the_shell_keeps_one_active_session(self) -> None:
        from src.ui_desktop.main_window import MainWindow

        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.analytics_controller.shutdown)

        for _ in range(3):
            window._start_quiz(self._intent())

        self.assertEqual(len(self._active_ids()), 1)
        self.assertEqual(self._completed_count(), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

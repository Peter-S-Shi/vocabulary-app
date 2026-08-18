from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db

"""
M19 Phase B integrated hardening: the fresh/empty-database journey.

M18 Phase F cycled every Workspace through a real MainWindow against a
populated synthetic database. A brand-new user's first launch is the
other honest baseline: a fresh, schema-initialized, completely EMPTY
database. Every workspace, the Study-mode entry, a Quiz launch attempt,
and a simulated restart must all behave as controlled empty states --
never an exception, never fabricated learning state, never a write that
turns "looked at an empty app" into data.

Per DESIGN.md § 2 Rule C this is structural/behavioral proof only;
native visual acceptance of empty-state rendering is a separate gate.
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.state.app_state import ShellMode, Workspace
    from src.ui_desktop.state.handoff import EntriesScopeIntent, QuizLaunchIntent, StudyTargetIntent

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


ALL_MANAGEMENT_WORKSPACES = (
    "TODAY",
    "ENTRIES",
    "COLLECTIONS",
    "TEMPLATES",
    "REVIEW_CALENDAR",
    "DATA_TOOLS",
    "ANALYTICS",
    "SETTINGS",
)


class _EmptyDatabaseTestCase(unittest.TestCase):
    """Fresh schema-initialized database with zero user content, per the
    repository pattern: swap db.DB_PATH to a temporary synthetic
    database, never the user's personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m19_empty.sqlite3"
        db.init_db()
        # A fresh database is not literally row-free: schema
        # initialization seeds the built-in system Templates. The honest
        # invariant is "browsing writes nothing", asserted against this
        # post-init baseline.
        self.baseline_counts = self._all_table_counts()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _all_table_counts(self) -> dict[str, int]:
        conn = db.get_connection()
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "select name from sqlite_master where type='table' and name != 'sqlite_sequence'"
                )
            ]
            return {table: conn.execute(f"select count(*) from {table}").fetchone()[0] for table in tables}
        finally:
            conn.close()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EmptyDatabaseWorkspaceCycleTests(_EmptyDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_every_workspace_renders_on_an_empty_database(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        for name in ALL_MANAGEMENT_WORKSPACES:
            workspace = Workspace[name]
            window.show_workspace(workspace)
            self.assertIs(window.current_workspace(), workspace)
        # And back to Today, twice, to prove repeat navigation is safe.
        window.show_workspace(Workspace.TODAY)
        window.show_workspace(Workspace.TODAY)
        self.assertIs(window.current_workspace(), Workspace.TODAY)

    def test_study_mode_entry_is_a_controlled_empty_state(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        window._enter_review()
        self.assertIs(window.current_workspace(), Workspace.REVIEW)
        self.assertIs(window.app_state.mode, ShellMode.STUDY)
        # Exit restores Management without error.
        window._exit_study_mode()
        self.assertIs(window.app_state.mode, ShellMode.MANAGEMENT)

    def test_stale_study_target_fails_honestly_without_navigation(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        window.show_workspace(Workspace.COLLECTIONS)
        # A Card handoff whose Collection/Card no longer exists (or, on
        # an empty database, never existed) must not enter Study mode.
        # The honest failure surfaces as a modal QMessageBox in the real
        # product; patched here because a real modal blocks offscreen
        # test execution forever.
        with patch("src.ui_desktop.main_window.QMessageBox.warning") as warn:
            window._open_review_at_card(StudyTargetIntent(collection_id=9999, card_number=1))
        warn.assert_called_once()
        self.assertIs(window.current_workspace(), Workspace.COLLECTIONS)
        self.assertIs(window.app_state.mode, ShellMode.MANAGEMENT)

    def test_quiz_launch_attempt_renders_honest_state_not_a_crash(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        intent = QuizLaunchIntent(
            source="review_quick_quiz",
            collection_id=9999,
            collection_name="Missing Collection",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=5,
            reason="empty-database hardening probe",
        )
        window._start_quiz(intent)
        # Quiz workspace renders whichever honest state resulted; the
        # global expectation is only: no exception, no fake session.
        self.assertIs(window.current_workspace(), Workspace.QUIZ)
        self.assertIsNone(window.quiz_controller.session_id)

    def test_entries_scope_handoff_to_missing_collection_is_safe(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        window._open_entries_with_scope(EntriesScopeIntent(scope="collection:9999"))
        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertEqual(window.entries_controller.model.rowCount(), 0)

    def test_full_cycle_writes_nothing_to_the_database(self) -> None:
        """Browsing an empty product must not fabricate learning state:
        after cycling every workspace, entering/exiting Study mode, and
        attempting a Quiz launch, every table is still empty."""
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        for name in ALL_MANAGEMENT_WORKSPACES:
            window.show_workspace(Workspace[name])
        window._enter_review()
        window._exit_study_mode()
        window._start_quiz(
            QuizLaunchIntent(
                source="review_quick_quiz",
                collection_id=1,
                collection_name="Missing Collection",
                card_number=1,
                card_id=None,
                quiz_type="term_to_meaning",
                item_count=5,
                reason="empty-database hardening probe",
            )
        )
        window._exit_study_mode()

        counts = self._all_table_counts()
        changed = {
            table: (self.baseline_counts.get(table), count)
            for table, count in counts.items()
            if count != self.baseline_counts.get(table) and table != "app_metadata"
        }
        self.assertEqual(changed, {}, f"empty-database browse changed rows: {changed}")

    def test_simulated_restart_reopens_the_same_database_cleanly(self) -> None:
        first = MainWindow()
        for name in ALL_MANAGEMENT_WORKSPACES:
            first.show_workspace(Workspace[name])
        first.analytics_controller.shutdown()
        first.deleteLater()

        second = MainWindow()
        self.addCleanup(second.deleteLater)
        for name in ALL_MANAGEMENT_WORKSPACES:
            second.show_workspace(Workspace[name])
        self.assertIs(second.current_workspace(), Workspace.SETTINGS)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

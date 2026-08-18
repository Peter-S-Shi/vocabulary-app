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

"""
M19 Phase C -- background-thread completion after navigation, and
background-thread shutdown behavior (ROADMAP § 19.4 / the M19 contract's
adversarial coverage list, both named explicitly).

AnalyticsController is the one controller whose background QThread can
legitimately still be running when the user navigates elsewhere --
Today/Entries/Collections do not launch background loads. This file
probes exactly that seam through a real MainWindow: navigating away
before a load finishes, navigating back before the first load finishes
(a second generation racing the first), and closing the window while a
load is in flight. All four scenarios were probed adversarially first
and found already correct -- the existing generation-guard and
QThread-lifetime discipline (module docstring in
`analytics_controller.py`, Human Gate 2 corrective) already covers them.
This records that evidence as a regression rather than asserting a
change that was never needed.
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.state.app_state import Workspace

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app

    def _pump(ms: int = 300) -> None:
        from PySide6.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class BackgroundAnalyticsNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m19_bg_nav.sqlite3"
        db.init_db()
        collection_id = create_collection("Probe", "", card_size=8)
        entry_ids = [add_entry("French", "English", "word", f"mot{i}", f"word {i}") for i in range(30)]
        add_entries_to_collection(entry_ids, collection_id)
        self.collection_id = collection_id

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_navigating_away_before_load_finishes_does_not_crash_or_hang(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.analytics_controller.shutdown)

        window.show_workspace(Workspace.ANALYTICS)
        self.assertTrue(window.analytics_controller.is_loading)

        window.show_workspace(Workspace.TODAY)
        _pump()

        self.assertIs(window.current_workspace(), Workspace.TODAY)
        self.assertFalse(window.analytics_controller.is_loading)
        self.assertEqual(window.analytics_controller._inflight, [])

    def test_returning_before_the_first_load_finishes_lands_on_the_second_generation(self) -> None:
        """A second navigation into Analytics before the first load
        returns must never let the stale first result overwrite the
        second -- the exact race the `_generation` guard exists for."""
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.analytics_controller.shutdown)

        window.show_workspace(Workspace.ANALYTICS)
        first_generation = window.analytics_controller._generation
        window.show_workspace(Workspace.ENTRIES)
        window.show_workspace(Workspace.ANALYTICS)
        second_generation = window.analytics_controller._generation

        self.assertGreater(second_generation, first_generation)
        _pump()

        self.assertFalse(window.analytics_controller.is_loading)
        self.assertEqual(len(window.analytics_controller.full_findings["entry_findings"]), 30)
        self.assertEqual(window.analytics_controller._inflight, [])

    def test_closing_the_window_while_a_load_is_in_flight_does_not_hang(self) -> None:
        window = MainWindow()
        window.show_workspace(Workspace.ANALYTICS)
        self.assertTrue(window.analytics_controller.is_loading)

        window.close()  # MainWindow.closeEvent blocks on analytics_controller.shutdown()

        self.assertEqual(window.analytics_controller._inflight, [])
        window.deleteLater()

    def test_rapid_workspace_bouncing_leaves_no_running_background_thread(self) -> None:
        window = MainWindow()
        self.addCleanup(window.deleteLater)

        for _ in range(5):
            window.show_workspace(Workspace.ANALYTICS)
            window.show_workspace(Workspace.TODAY)
        _pump(500)

        self.assertIs(window.current_workspace(), Workspace.TODAY)
        self.assertFalse(window.analytics_controller.is_loading)
        self.assertEqual(window.analytics_controller._inflight, [])
        window.analytics_controller.shutdown()  # must return immediately, nothing in flight


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

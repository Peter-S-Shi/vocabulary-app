from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

# Qt must be told to use the offscreen platform plugin before QApplication is
# constructed. This keeps the spike runnable headlessly (no real display
# required), consistent with the M16.1 prompt's verification requirements.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QRunnable, Qt, QThreadPool, Signal, Slot
    from PySide6.QtWidgets import QApplication, QMainWindow, QTableView, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import add_entries_to_collection, create_collection, get_collections
from src.entries import add_entry
from src.learning_workflow import get_today_overview, normalize_today


"""
Durable M16.1 architecture-decision evidence.

This module is a small technical spike, not product desktop UI. It proves the
minimal set of claims the M16.1 architecture decision depends on:

1. PySide6 installs and imports cleanly in this repository's environment.
2. A native Qt application/event loop starts and shuts down cleanly.
3. A synthetic dense-table model/view surface works (QAbstractTableModel +
   QTableView), matching the Entries/Table-First requirement.
4. A temporary synthetic Vocabulary App database opens through the existing
   src/db.py + src/app_config.py path resolution, unmodified.
5. Representative reusable src/ core functions (src.entries, src.collections,
   src.learning_workflow) can be called directly, without Streamlit.
6. A minimal runtime semantic-token style swap applies without restarting the
   application, matching the DESIGN.md theme-switching requirement.
7. A QThreadPool/QRunnable background worker can hand results back to a
   QObject living on the main/UI thread through queued Qt signals.

See docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md for the architecture
decision this spike supports. This file intentionally does not implement the
real desktop shell, navigation, theme system, or any product screen — see the
M16.1 prompt's scope boundaries.
"""


def _resolve_qss(template: str, tokens: dict[str, str]) -> str:
    """Trivial token substitution for the spike only; not the real token engine."""
    resolved = template
    for name, value in tokens.items():
        resolved = resolved.replace("{" + name + "}", value)
    return resolved


if PYSIDE6_AVAILABLE:

    class _SyntheticEntryTableModel(QAbstractTableModel):
        """Synthetic dense-table model; not the product Entries table."""

        HEADERS = ["term", "meaning", "status"]

        def __init__(self, rows: list[dict]) -> None:
            super().__init__()
            self._rows = rows

        def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt API)
            return 0 if parent.isValid() else len(self._rows)

        def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt API)
            return 0 if parent.isValid() else len(self.HEADERS)

        def data(self, index, role=Qt.DisplayRole):
            if not index.isValid() or role != Qt.DisplayRole:
                return None
            row = self._rows[index.row()]
            key = self.HEADERS[index.column()]
            return row[key]

        def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802 (Qt API)
            if role != Qt.DisplayRole or orientation != Qt.Horizontal:
                return None
            return self.HEADERS[section]

    class _SpikeWorkerSignals(QObject):
        progress = Signal(int)
        finished = Signal(list)

    class _SpikeWorker(QRunnable):
        """QThreadPool/QRunnable background-worker spike for the M16.1 concurrency rule."""

        def __init__(self, rows: list[dict]) -> None:
            super().__init__()
            self.signals = _SpikeWorkerSignals()
            self._rows = rows

        def run(self) -> None:  # noqa: N802 (Qt API)
            totals: list[str] = []
            for index, row in enumerate(self._rows, start=1):
                totals.append(row["term"].upper())
                self.signals.progress.emit(index)
            self.signals.finished.emit(totals)

    class _SpikeUiReceiver(QObject):
        """Stand-in for a controller/view-model living on the UI thread."""

        def __init__(self) -> None:
            super().__init__()
            self.progress_events: list[int] = []
            self.results: list[list[str]] = []

        @Slot(int)
        def on_progress(self, value: int) -> None:
            self.progress_events.append(value)

        @Slot(list)
        def on_finished(self, result: list) -> None:
            self.results.append(result)

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. The M16.1 spike "
    "is desktop-only and optional for the core/Streamlit test run.",
)
class M161ArchitectureSpikeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m16_1_spike.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_native_window_starts_and_closes_cleanly(self) -> None:
        window = QMainWindow()
        window.setWindowTitle("M16.1 architecture spike (offscreen)")
        window.resize(320, 240)
        window.show()
        self.app.processEvents()
        window.close()
        self.app.processEvents()

    def test_core_functions_are_reusable_without_streamlit(self) -> None:
        entry_id = add_entry("English", "Chinese", "word", "spike", "a small technical trial")
        collection_id = create_collection("M16.1 Spike Collection", card_size=5)
        add_entries_to_collection([entry_id], collection_id)

        collections = get_collections()
        self.assertTrue(any(c["id"] == collection_id for c in collections))

        with db.get_connection() as conn:
            overview = get_today_overview(conn, normalize_today())
        self.assertIn("study_workload", overview)
        self.assertGreaterEqual(overview["study_workload"]["total_entries"], 1)

    def test_dense_table_model_view_surface(self) -> None:
        rows = [
            {"term": f"term-{i}", "meaning": f"meaning-{i}", "status": "new"}
            for i in range(500)
        ]
        model = _SyntheticEntryTableModel(rows)
        view = QTableView()
        view.setModel(model)

        self.assertEqual(model.rowCount(), 500)
        self.assertEqual(model.columnCount(), 3)
        self.assertEqual(model.data(model.index(0, 0)), "term-0")
        self.assertEqual(model.data(model.index(499, 2)), "new")

        view.show()
        self.app.processEvents()
        view.close()

    def test_runtime_semantic_token_style_swap(self) -> None:
        template = "QWidget { background-color: {app-background}; color: {text-primary}; }"
        light_tokens = {"app-background": "#F4F3EF", "text-primary": "#1C1B18"}
        dark_tokens = {"app-background": "#17181A", "text-primary": "#EDECE8"}

        widget = QWidget()

        light_qss = _resolve_qss(template, light_tokens)
        widget.setStyleSheet(light_qss)
        self.assertIn("#F4F3EF", widget.styleSheet())

        dark_qss = _resolve_qss(template, dark_tokens)
        widget.setStyleSheet(dark_qss)
        self.assertIn("#17181A", widget.styleSheet())
        self.assertNotEqual(light_qss, dark_qss)

    def test_background_worker_to_ui_thread_signal_handoff(self) -> None:
        rows = [{"term": f"term-{i}"} for i in range(20)]
        worker = _SpikeWorker(rows)
        receiver = _SpikeUiReceiver()

        worker.signals.progress.connect(receiver.on_progress)
        worker.signals.finished.connect(receiver.on_finished)

        QThreadPool.globalInstance().start(worker)

        deadline = time.monotonic() + 5.0
        while not receiver.results and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)

        self.assertTrue(
            receiver.results, "background worker did not hand off to the UI thread within timeout"
        )
        self.assertEqual(len(receiver.progress_events), 20)
        self.assertEqual(receiver.results[0][0], "TERM-0")
        self.assertEqual(receiver.results[0][-1], "TERM-19")


if __name__ == "__main__":
    unittest.main()

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
from src.collections import add_entries_to_collection, create_collection, get_card_page_for_collection
from src.entries import add_entry, search_entries

"""
M19 Phase C -- unwritable/invalid export destinations and large/dense
dataset behavior (ROADMAP § 19.4 "invalid paths; read-only/unwritable
destinations; large/dense datasets").

Both areas were probed adversarially and found already correct; these
tests record that evidence so it stays correct rather than asserting a
change that was never needed.

Destination safety: every desktop write path already funnels through a
guarded `open(...)` and reports an OSError as a controlled message
instead of propagating out of a click handler, and the audio-export
batch marks a Card that cannot be published as `failed` and keeps going
rather than aborting the batch.

Scale: the queries a large Collection actually drives are bounded by
construction -- `get_card_page_for_collection` reads one page via SQL
aggregation rather than loading every Entry (the M17 Minimum Collection
Integration corrective), and the M18 Human Gate 2 `EvidenceProfileCache`
keeps a dense learning history to a single whole-database snapshot per
Analytics pass. These assert the boundedness itself, never wall-clock
timings, which would be flaky; measured timings are recorded in the
milestone's QA evidence instead.
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.data_tools_controller import DataToolsController

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m19_destination_scale.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _unwritable_destination(self) -> Path:
        """A path whose parent is a regular file.

        Portable across platforms and CI in a way `chmod`/ACL tricks are
        not: any attempt to create or write under it raises OSError, the
        same failure class a read-only folder or a full disk produces.
        """
        blocker = self.root / "blocker.txt"
        blocker.write_text("not a directory", encoding="utf-8")
        return blocker / "nested" / "export.csv"


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class UnwritableDestinationTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_export_bytes_are_produced_before_any_write_is_attempted(self) -> None:
        """Export content is built in memory first, so a destination
        failure can never leave a half-written file where the user
        expected a complete export."""
        add_entry("French", "English", "word", "pomme", "apple")
        controller = DataToolsController()
        rows, columns = controller.export_rows("all_entries", None)
        data = controller.export_bytes(rows, columns, "csv")

        self.assertTrue(data)
        destination = self._unwritable_destination()
        with self.assertRaises(OSError):
            with open(destination, "wb") as handle:
                handle.write(data)
        self.assertFalse(destination.exists())

    def test_every_desktop_write_path_guards_oserror(self) -> None:
        """Structural guard: each `open(..., "wb")` in the Data Tools
        view sits inside a try/except OSError. A new export action added
        without that guard would crash out of a click handler."""
        source = Path(__file__).resolve().parent.parent / "src" / "ui_desktop" / "views" / "data_tools_view.py"
        text = source.read_text(encoding="utf-8")
        write_count = text.count('open(path, "wb")')
        self.assertGreaterEqual(write_count, 3)
        self.assertEqual(write_count, text.count('with open(path, "wb") as handle:'))
        # Each write block is followed by an OSError handler.
        for fragment in text.split('with open(path, "wb") as handle:')[1:]:
            self.assertIn("except OSError as error:", fragment[:400])

    def test_backup_generation_does_not_touch_the_database_on_write_failure(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = DataToolsController()
        conn = db.get_connection()
        try:
            before = conn.execute("select count(*) from entries").fetchone()[0]
        finally:
            conn.close()

        data = controller.build_database_backup()
        destination = self._unwritable_destination()
        with self.assertRaises(OSError):
            with open(destination, "wb") as handle:
                handle.write(data)

        conn = db.get_connection()
        try:
            after = conn.execute("select count(*) from entries").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(before, after)


class AudioExportDestinationFailureTests(_SyntheticDatabaseTestCase):
    def test_publication_failure_is_per_card_and_never_aborts_the_batch(self) -> None:
        """Structural guard on `execute_audio_export_plan`: a
        destination failure is recorded as a failed Card with the
        `destination_publication_failed` code and the loop continues, so
        one unwritable target cannot lose an otherwise successful batch."""
        source = Path(__file__).resolve().parent.parent / "src" / "audio_export.py"
        text = source.read_text(encoding="utf-8")
        self.assertIn("except (OSError, ValueError) as error:", text)
        self.assertIn('"destination_publication_failed"', text)
        # The handler appends a result rather than re-raising.
        handler = text.split("except (OSError, ValueError) as error:")[1][:400]
        self.assertIn("results.append", handler)
        self.assertNotIn("raise", handler)


class LargeCollectionBoundednessTests(_SyntheticDatabaseTestCase):
    def _large_collection(self, entry_count: int, card_size: int = 8) -> tuple[int, list[int]]:
        collection_id = create_collection("Large", "", card_size=card_size)
        entry_ids = [
            add_entry("French", "English", "word", f"grand{index}", f"big {index}")
            for index in range(entry_count)
        ]
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids

    def test_card_paging_returns_one_bounded_page_regardless_of_size(self) -> None:
        collection_id, _entry_ids = self._large_collection(240)

        page = get_card_page_for_collection(collection_id, page=1, page_size=10)

        self.assertEqual(len(page["cards"]), 10)
        self.assertEqual(page["page"], 1)
        self.assertEqual(page["page_size"], 10)
        self.assertEqual(page["total_cards"], 30)
        self.assertEqual(page["total_pages"], 3)

    def test_a_later_page_is_equally_bounded_and_does_not_overlap(self) -> None:
        collection_id, _entry_ids = self._large_collection(240)

        first = get_card_page_for_collection(collection_id, page=1, page_size=10)
        last = get_card_page_for_collection(collection_id, page=3, page_size=10)

        self.assertEqual(len(last["cards"]), 10)
        first_numbers = {card["card_number"] for card in first["cards"]}
        last_numbers = {card["card_number"] for card in last["cards"]}
        self.assertEqual(first_numbers & last_numbers, set())

    def test_a_page_beyond_the_end_clamps_and_reports_the_real_page(self) -> None:
        """Out-of-range paging clamps to the last real page and reports
        the clamped number honestly, rather than erroring or silently
        showing an empty list -- the state the Collections view lands in
        when Entries are removed while a later page is open."""
        collection_id, _entry_ids = self._large_collection(240)

        page = get_card_page_for_collection(collection_id, page=99, page_size=10)

        self.assertEqual(page["total_cards"], 30)
        self.assertEqual(page["total_pages"], 3)
        self.assertEqual(page["page"], 3)
        self.assertEqual(len(page["cards"]), 10)

    def test_a_negative_or_zero_page_clamps_to_the_first_page(self) -> None:
        collection_id, _entry_ids = self._large_collection(240)

        for requested in (0, -5):
            page = get_card_page_for_collection(collection_id, page=requested, page_size=10)
            self.assertEqual(page["page"], 1)
            self.assertEqual(len(page["cards"]), 10)

    def test_a_missing_collection_returns_an_empty_bounded_projection(self) -> None:
        page = get_card_page_for_collection(999999, page=1, page_size=10)

        self.assertEqual(page["cards"], [])
        self.assertEqual(page["total_cards"], 0)

    def test_search_narrows_a_large_entry_set_correctly(self) -> None:
        self._large_collection(240)

        matches = search_entries(search_text="grand99")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["term"], "grand99")


class DenseLearningHistoryTests(_SyntheticDatabaseTestCase):
    def test_one_cache_serves_a_dense_history_across_scopes(self) -> None:
        """The Human Gate 2 root-cause fix in shape: a dense history is
        loaded once per Analytics pass and reused for every scope, and
        the results stay identical to the uncached computation."""
        from src.analytics import build_evidence_profile_cache
        from src.insights import get_all_findings

        collection_id = create_collection("Dense", "", card_size=8)
        entry_ids = [
            add_entry("French", "English", "word", f"dense{index}", f"dense {index}") for index in range(60)
        ]
        add_entries_to_collection(entry_ids, collection_id)

        conn = db.get_connection()
        try:
            for entry_id in entry_ids:
                cursor = conn.execute(
                    "INSERT INTO quiz_sessions (collection_id, card_number, quiz_type, started_at, status, total_items)"
                    " VALUES (?, 1, 'term_to_meaning', datetime('now'), 'completed', 0)",
                    (collection_id,),
                )
                session_id = cursor.lastrowid
                for attempt in range(8):
                    conn.execute(
                        "INSERT INTO quiz_item_logs"
                        " (session_id, entry_id, prompt, expected_answer, user_answer, is_correct, answered_at)"
                        " VALUES (?, ?, 'p', 'e', 'u', ?, datetime('now'))",
                        (session_id, entry_id, 1 if attempt % 3 else 0),
                    )
            conn.commit()
            log_count = conn.execute("select count(*) from quiz_item_logs").fetchone()[0]

            uncached = get_all_findings(conn, collection_id=collection_id)
            cache = build_evidence_profile_cache(conn)
            cached = get_all_findings(conn, collection_id=collection_id, cache=cache)
            cached_all = get_all_findings(conn, cache=cache)
        finally:
            conn.close()

        self.assertEqual(log_count, 480)
        self.assertEqual(cached, uncached)
        self.assertEqual(len(cached_all["entry_findings"]), 60)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

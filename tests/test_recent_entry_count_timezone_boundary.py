from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Runs in a fresh subprocess so the TZ environment variable is read by SQLite's
# 'localtime' modifier before any connection is opened. Setting os.environ["TZ"]
# mid-process does not reliably take effect once a 'localtime' query has already
# run once in that process, so an in-process test would be flaky.
_WORKER_SCRIPT = textwrap.dedent(
    """
    import tempfile
    from pathlib import Path

    from src import db
    from src.learning_workflow import _recent_entry_count

    temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db.DB_PATH = Path(temp_dir.name) / "tz_boundary_test.sqlite3"
    db.init_db()

    entries = [
        # UTC-day = 2026-08-10 (before the window), but local day (UTC+9) =
        # 2026-08-11 (the first day of the window). This is the boundary case
        # that a bare DATE(created_at) comparison gets wrong.
        ("2026-08-10T20:00:00+00:00", "2026-08-10T20:00:00+00:00"),
        # Comfortably inside the window under both UTC and local dates.
        ("2026-08-15T10:00:00+00:00", "2026-08-15T10:00:00+00:00"),
        # Comfortably outside the window under both UTC and local dates.
        ("2026-07-20T10:00:00+00:00", "2026-07-20T10:00:00+00:00"),
    ]

    with db.get_connection() as conn:
        for created_at, updated_at in entries:
            conn.execute(
                '''
                INSERT INTO entries (
                    language, explanation_language, entry_type, term, meaning,
                    created_at, updated_at
                ) VALUES ('English', 'English', 'word', 'synthetic-term',
                          'synthetic-meaning', ?, ?)
                ''',
                (created_at, updated_at),
            )

        count = _recent_entry_count(conn, "2026-08-17", days=7)

    print(count)
    """
)


class RecentEntryCountTimezoneBoundaryTests(unittest.TestCase):
    """Regression test for the Today dashboard 'last 7 days' entry count.

    entries.created_at is always stored as a UTC timestamp
    (see src/entries.py `_now_iso`), while the `today_iso` boundary passed
    into _recent_entry_count is a local calendar date. Comparing a bare
    DATE(created_at) against that local-date window misclassifies entries
    created near local midnight when the local timezone differs from UTC.
    """

    def _run_worker(self, tz: str) -> int:
        result = subprocess.run(
            [sys.executable, "-c", _WORKER_SCRIPT],
            cwd=str(REPO_ROOT),
            env={**os.environ, "TZ": tz},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"worker failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        return int(result.stdout.strip().splitlines()[-1])

    def test_boundary_entry_is_counted_under_local_plus_9_offset(self) -> None:
        # local = UTC+9 (fixed offset, no DST): the boundary entry's local day
        # is 2026-08-11 (inside the window) even though its UTC day is
        # 2026-08-10 (outside the window).
        count = self._run_worker("XST-9")
        self.assertEqual(
            count,
            2,
            "expected the boundary entry (local day inside the window) plus "
            "the comfortably-inside entry to be counted",
        )

    def test_boundary_entry_is_counted_under_local_minus_9_offset(self) -> None:
        # local = UTC-9: sanity check in the opposite direction so the fix
        # isn't just tuned to one sign of offset. Under this offset the
        # boundary entry's local day is 2026-08-10 (still outside the
        # window), so only the comfortably-inside entry should count.
        count = self._run_worker("XST+9")
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()

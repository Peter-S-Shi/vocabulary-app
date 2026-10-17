from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from src import app_config


def _create_fictional_app_database(path: Path, item_count: int = 3) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "CREATE TABLE entries ("
            "id INTEGER PRIMARY KEY, "
            "term TEXT NOT NULL, "
            "meaning TEXT NOT NULL"
            ")"
        )
        connection.execute(
            "CREATE TABLE collections (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE app_metadata (key TEXT PRIMARY KEY, "
            "value TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        for i in range(1, item_count + 1):
            connection.execute(
                "INSERT INTO entries (id, term, meaning) VALUES (?, ?, ?)",
                (i, f"term_{i}", f"meaning_{i}"),
            )
        connection.executemany(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
            (
                ("schema_version", "2", "2026-10-17T12:00:00Z"),
                ("app_data_version", "1.1.0", "2026-10-17T12:00:00Z"),
            ),
        )
        connection.commit()


class M23BRecoveryJournalResolutionTests(unittest.TestCase):
    def test_missing_pointer_with_durable_recovery_journal_fails_closed(self) -> None:
        """When data-root.json is missing or deleted after a committed relocation,
        the presence of migration-recovery.json forces startup to fail closed
        with DataRootError, never silently reverting to default or creating a blank DB.
        """
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            default_root = home / "local" / "vocabulary_app"
            target_root = home / "d_drive" / "VocabularyAppData"
            default_root.mkdir(parents=True)
            target_root.mkdir(parents=True)
            _create_fictional_app_database(target_root / "vocab.db")

            journal_data = {
                "version": 1,
                "latest_committed_root": str(target_root),
                "history": [
                    {
                        "sequence": 1,
                        "committed_at": "2026-10-17T12:00:00Z",
                        "source_root": str(default_root),
                        "target_root": str(target_root),
                        "schema_version": "2",
                        "app_data_version": "1.1.0",
                    }
                ],
            }
            (default_root / "migration-recovery.json").write_text(
                json.dumps(journal_data), encoding="utf-8"
            )

            with patch.dict(os.environ, {
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            }):
                with self.assertRaises(app_config.DataRootError) as context:
                    app_config.resolve_data_paths()
                self.assertIn("prior data relocation was committed", str(context.exception))
                self.assertIn("data-root.json", str(context.exception))

    def test_pointer_journal_target_mismatch_fails_closed(self) -> None:
        """If data-root.json and migration-recovery.json point to different roots,
        startup must fail closed rather than guessing which root is authoritative.
        """
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            default_root = home / "local" / "vocabulary_app"
            root_a = home / "drive_d" / "data_a"
            root_b = home / "drive_e" / "data_b"
            default_root.mkdir(parents=True)
            root_a.mkdir(parents=True)
            root_b.mkdir(parents=True)
            _create_fictional_app_database(root_a / "vocab.db")
            _create_fictional_app_database(root_b / "vocab.db")

            (default_root / "data-root.json").write_text(
                json.dumps({"version": 1, "data_root": str(root_a)}), encoding="utf-8"
            )
            journal_data = {
                "version": 1,
                "latest_committed_root": str(root_b),
                "history": [],
            }
            (default_root / "migration-recovery.json").write_text(
                json.dumps(journal_data), encoding="utf-8"
            )

            with patch.dict(os.environ, {
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            }):
                with self.assertRaises(app_config.DataRootError) as context:
                    app_config.resolve_data_paths()
                self.assertIn("conflict", str(context.exception).lower())



class M23BRelocationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.local_root = self.home / "local" / "vocabulary_app"
        self.local_root.mkdir(parents=True)
        _create_fictional_app_database(self.local_root / "vocab.db", item_count=5)
        (self.local_root / "preferences.json").write_text(
            json.dumps({"appearance": "Dark", "custom_theme": {}}), encoding="utf-8"
        )
        backups = self.local_root / "backups"
        backups.mkdir()
        (backups / "backup_1.bak").write_text("fictional backup data", encoding="utf-8")
        audio = self.local_root / "audio-cache"
        audio.mkdir()
        (audio / "sample.mp3").write_bytes(b"fictional audio data")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_plan_relocation_rejects_occupied_target(self) -> None:
        from src.data_relocation import plan_relocation, RelocationError

        occupied = self.home / "existing_folder"
        occupied.mkdir()
        with self.assertRaises(RelocationError) as context:
            plan_relocation(occupied, source_root=self.local_root)
        self.assertIn("occupied", str(context.exception).lower())

    def test_plan_relocation_rejects_target_inside_source(self) -> None:
        from src.data_relocation import plan_relocation, RelocationError

        nested = self.local_root / "subfolder"
        with self.assertRaises(RelocationError) as context:
            plan_relocation(nested, source_root=self.local_root)
        self.assertIn("inside", str(context.exception).lower())

    def test_successful_relocation_and_atomic_promotion(self) -> None:
        from src.data_relocation import plan_relocation, execute_relocation

        target_parent = self.home / "external_drive"
        target_parent.mkdir()
        target = target_parent / "VocabularyAppData"

        plan = plan_relocation(target, source_root=self.local_root)
        # Sibling staging directory must share the parent with target
        self.assertEqual(plan.staging_dir.parent, target_parent)
        self.assertNotEqual(plan.staging_dir, target)

        result = execute_relocation(plan, default_root=self.local_root)
        self.assertTrue(result.success)
        self.assertTrue(result.needs_restart)
        self.assertEqual(result.target_root, target)

        # Target directory exists and has all 4 components
        self.assertTrue((target / "vocab.db").is_file())
        self.assertTrue((target / "preferences.json").is_file())
        self.assertTrue((target / "backups" / "backup_1.bak").is_file())
        self.assertTrue((target / "audio-cache" / "sample.mp3").is_file())
        self.assertTrue((target / ".vocab_app_root_marker.json").is_file())

        # Staging directory must no longer exist (promoted)
        self.assertFalse(plan.staging_dir.exists())

        # Source files must be RETAINED as rollback baseline
        self.assertTrue((self.local_root / "vocab.db").is_file())
        self.assertTrue((self.local_root / "preferences.json").is_file())
        self.assertTrue((self.local_root / "backups" / "backup_1.bak").is_file())
        self.assertTrue((self.local_root / "audio-cache" / "sample.mp3").is_file())

        # Durable journal and pointer written to default root
        pointer_data = json.loads((self.local_root / "data-root.json").read_text(encoding="utf-8"))
        self.assertEqual(pointer_data["data_root"], str(target))
        journal_data = json.loads((self.local_root / "migration-recovery.json").read_text(encoding="utf-8"))
        self.assertEqual(journal_data["latest_committed_root"], str(target))
        self.assertEqual(len(journal_data["history"]), 1)
        self.assertEqual(journal_data["history"][0]["sequence"], 1)
        self.assertEqual(journal_data["history"][0]["schema_version"], "2")
        self.assertEqual(journal_data["history"][0]["app_data_version"], "1.1.0")

        # Verified startup resolution
        with patch.dict(os.environ, {
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }):
            paths = app_config.resolve_data_paths()
            self.assertEqual(paths.data_root, target)
            self.assertEqual(paths.database, target / "vocab.db")
            self.assertTrue(paths.relocated)

    def test_repeated_relocation_chain(self) -> None:
        from src.data_relocation import plan_relocation, execute_relocation

        target_1 = self.home / "drive_d" / "VocabularyData1"
        target_2 = self.home / "drive_e" / "VocabularyData2"
        target_1.parent.mkdir()
        target_2.parent.mkdir()

        plan1 = plan_relocation(target_1, source_root=self.local_root)
        execute_relocation(plan1, default_root=self.local_root)

        # Now migrate from target_1 to target_2
        plan2 = plan_relocation(target_2, source_root=target_1)
        res2 = execute_relocation(plan2, default_root=self.local_root)
        self.assertTrue(res2.success)

        # Journal should now record sequence 2 and history of length 2
        journal_data = json.loads((self.local_root / "migration-recovery.json").read_text(encoding="utf-8"))
        self.assertEqual(journal_data["latest_committed_root"], str(target_2))
        self.assertEqual(len(journal_data["history"]), 2)
        self.assertEqual(journal_data["history"][1]["sequence"], 2)
        self.assertEqual(journal_data["history"][1]["source_root"], str(target_1))
        self.assertEqual(journal_data["history"][1]["target_root"], str(target_2))

        # Both previous locations remain on disk intact
        self.assertTrue((self.local_root / "vocab.db").is_file())
        self.assertTrue((target_1 / "vocab.db").is_file())
        self.assertTrue((target_2 / "vocab.db").is_file())

    def test_fault_injection_corrupt_database_cleans_up_staging(self) -> None:
        from src.data_relocation import plan_relocation, execute_relocation, RelocationError

        # Corrupt source DB before migration
        (self.local_root / "vocab.db").write_text("corrupted non-sqlite data", encoding="utf-8")

        target = self.home / "drive_d" / "DataTarget"
        target.parent.mkdir()
        plan = plan_relocation(target, source_root=self.local_root)

        with self.assertRaises(RelocationError):
            execute_relocation(plan, default_root=self.local_root)

        # Staging directory must be cleaned up
        self.assertFalse(plan.staging_dir.exists())
        # Target must not exist
        self.assertFalse(target.exists())
        # Pointer and journal must not exist
        self.assertFalse((self.local_root / "data-root.json").exists())
        self.assertFalse((self.local_root / "migration-recovery.json").exists())


    def test_relocation_concurrency_lock_prevents_simultaneous_migration(self) -> None:
        from src.data_relocation import plan_relocation, execute_relocation, acquire_quiescence_lock, RelocationError

        target = self.home / "drive_d" / "DataTargetConcurrent"
        target.parent.mkdir()
        plan = plan_relocation(target, source_root=self.local_root)

        with acquire_quiescence_lock(self.local_root):
            with self.assertRaises(RelocationError) as context:
                execute_relocation(plan, default_root=self.local_root)
            self.assertIn("actively using", str(context.exception))

    def test_sqlite_wal_consistency_without_raw_wal_copy(self) -> None:
        from src.data_relocation import plan_relocation, execute_relocation

        # Enable WAL mode on source database and insert records without explicit checkpoint
        source_db = self.local_root / "vocab.db"
        with closing(sqlite3.connect(source_db)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("INSERT INTO entries (id, term, meaning) VALUES (999, 'wal_term', 'wal_meaning')")
            conn.commit()

        # Confirm wal file exists on source
        wal_file = self.local_root / "vocab.db-wal"
        # It may or may not exist depending on WAL size, but WAL mode is set

        target = self.home / "drive_d" / "DataTargetWal"
        target.parent.mkdir()
        plan = plan_relocation(target, source_root=self.local_root)

        result = execute_relocation(plan, default_root=self.local_root)
        self.assertTrue(result.success)

        # Verify target directory should not contain copied raw -wal or -shm files from source
        self.assertFalse((target / "vocab.db-wal").exists())
        self.assertFalse((target / "vocab.db-shm").exists())

        # Target database has the wal_term record
        target_db = target / "vocab.db"
        with closing(sqlite3.connect(target_db.as_uri() + "?mode=ro", uri=True)) as conn:
            row = conn.execute("SELECT meaning FROM entries WHERE id = 999").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "wal_meaning")


if __name__ == "__main__":
    unittest.main()



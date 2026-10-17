from __future__ import annotations

import json
import os
import sqlite3
import sys
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


    def test_subprocess_normal_writer_blocks_relocation_and_vice_versa(self) -> None:
        """Verify across real separate OS processes that an active normal SQLite transaction
        blocks relocation (which requires an exclusive lock), and active relocation blocks writers.
        """
        import subprocess
        from src.data_lock import acquire_data_lock, DataLockError
        from src.data_relocation import plan_relocation, execute_relocation, RelocationError

        target = self.home / "drive_d" / "SubprocessDataTarget"
        target.parent.mkdir()
        plan = plan_relocation(target, source_root=self.local_root)

        # 1. Launch a separate OS subprocess holding an active SQLite connection / transaction
        worker_code = (
            "import os, sys, time, sqlite3\n"
            "from pathlib import Path\n"
            "from src import app_config, db\n"
            "conn = db.get_connection()\n"
            "sys.stdout.write('READY\\n')\n"
            "sys.stdout.flush()\n"
            "time.sleep(3)\n"
            "conn.close()\n"
        )
        env = dict(os.environ)
        env.update({
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        })
        proc = subprocess.Popen(
            [sys.executable, "-c", worker_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            ready_line = proc.stdout.readline()
            self.assertEqual(ready_line.strip(), "READY")

            # While the external process holds the DB connection, relocation MUST fail
            with self.assertRaises(RelocationError) as ctx:
                execute_relocation(plan, default_root=self.local_root)
            self.assertIn("actively using", str(ctx.exception))
        finally:
            proc.terminate()
            proc.wait(timeout=5)
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

        # 2. While relocation holds exclusive lock, an external writer process must fail to connect
        with acquire_data_lock(self.local_root, exclusive=True):
            writer_attempt_code = (
                "import os, sys\n"
                "from src import app_config, db\n"
                "try:\n"
                "    conn = db.get_connection()\n"
                "    sys.exit(0)\n"
                "except Exception as e:\n"
                "    sys.stderr.write(str(e))\n"
                "    sys.exit(42)\n"
            )
            writer_res = subprocess.run(
                [sys.executable, "-c", writer_attempt_code],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(writer_res.returncode, 42)
            self.assertIn("locked for relocation", writer_res.stderr)

    def test_subprocess_audio_cache_and_db_import_writers_respect_relocation_quiescence(self) -> None:
        """Verify across real OS subprocesses that AudioAssetStore.materialize and
        import_existing_database participate in the cross-process data relocation lock.
        """
        import subprocess
        from src.data_lock import acquire_data_lock
        from src.data_relocation import plan_relocation, execute_relocation, RelocationError
        from src.db_import import import_existing_database, DatabaseImportError

        target = self.home / "drive_d" / "AudioSubprocessTarget"
        target.parent.mkdir()
        plan = plan_relocation(target, source_root=self.local_root)

        env = dict(os.environ)
        env.update({
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        })

        # 1. Spawn a real subprocess that is mid-materialization inside AudioAssetStore.materialize
        audio_worker_code = (
            "import os, sys, time, wave\n"
            "from pathlib import Path\n"
            "from src.audio_assets import AudioAssetRequest, AudioAssetStore, CANONICAL_CHANNELS, CANONICAL_SAMPLE_RATE_HZ, CANONICAL_SAMPLE_WIDTH_BYTES\n"
            "from src.tts_providers import ProviderRegistry, ProviderSpec, SynthesisResult, ProviderAvailability\n"
            "class SlowFakeProvider:\n"
            "    def __init__(self):\n"
            "        self.spec = ProviderSpec('en', 'fake-tts', 'voice-en')\n"
            "    def preflight(self) -> ProviderAvailability:\n"
            "        return ProviderAvailability(True, 'ok')\n"
            "    def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult:\n"
            "        sys.stdout.write('SYNTH_IN_PROGRESS\\n')\n"
            "        sys.stdout.flush()\n"
            "        time.sleep(3)\n"
            "        with wave.open(str(output_path), 'wb') as w:\n"
            "            w.setnchannels(CANONICAL_CHANNELS)\n"
            "            w.setsampwidth(CANONICAL_SAMPLE_WIDTH_BYTES)\n"
            "            w.setframerate(CANONICAL_SAMPLE_RATE_HZ)\n"
            "            w.writeframes(b'\\x00\\x00' * 2400)\n"
            "        return SynthesisResult('fake-tts', 'voice-en', 'en', output_path, 'audio/wav', 24000)\n"
            "store = AudioAssetStore()\n"
            "reg = ProviderRegistry([SlowFakeProvider()])\n"
            "req = AudioAssetRequest('bonjour', 'en', 'fake-tts', 'voice-en')\n"
            "store.materialize(req, reg)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", audio_worker_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            line = proc.stdout.readline()
            self.assertEqual(line.strip(), "SYNTH_IN_PROGRESS")

            # Relocation must fail while external process is materializing into audio-cache
            with self.assertRaises(RelocationError) as ctx:
                execute_relocation(plan, default_root=self.local_root)
            self.assertIn("actively using", str(ctx.exception))
        finally:
            proc.terminate()
            proc.wait(timeout=5)
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

        # 2. While relocation holds the exclusive lock, external AudioAssetStore.materialize
        # and import_existing_database must be blocked and fail closed without writing files.
        external_db = self.home / "external_source.db"
        _create_fictional_app_database(external_db)

        with acquire_data_lock(self.local_root, exclusive=True):
            audio_attempt_code = (
                "import sys\n"
                "from src.audio_assets import AudioAssetRequest, AudioAssetStore\n"
                "from src.tts_providers import ProviderRegistry\n"
                "store = AudioAssetStore()\n"
                "req = AudioAssetRequest('hello', 'en', 'fake-tts', 'voice-en')\n"
                "res = store.materialize(req, ProviderRegistry([]))\n"
                "if not res.succeeded and res.error_code == 'data_root_locked':\n"
                "    sys.exit(55)\n"
                "sys.exit(1)\n"
            )
            audio_res = subprocess.run(
                [sys.executable, "-c", audio_attempt_code],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(audio_res.returncode, 55)

            with self.assertRaises(DatabaseImportError) as import_ctx:
                import_existing_database(external_db, destination_path=self.local_root / "vocab.db")
            self.assertIn("locked for relocation", str(import_ctx.exception))

    def test_failed_promotion_rolls_back_journal_to_committed_source(self) -> None:
        """If target promotion fails (e.g. target became occupied), the journal
        must be rolled back to its previous state (or removed if absent), so the existing app continues to work.
        """
        from unittest.mock import patch
        from src.data_relocation import plan_relocation, execute_relocation, RelocationError

        target = self.home / "drive_d" / "OccupiedTarget"
        target.parent.mkdir()
        plan = plan_relocation(target, source_root=self.local_root)

        # Intercept _atomic_promote_no_clobber to simulate promotion failure
        with patch("src.data_relocation._atomic_promote_no_clobber", side_effect=RelocationError("Simulated promotion failure")):
            with self.assertRaises(RelocationError) as ctx:
                execute_relocation(plan, default_root=self.local_root)
            self.assertIn("Simulated promotion failure", str(ctx.exception))

        # Staging should be cleaned up
        self.assertFalse(plan.staging_dir.exists())

        # Since no journal existed prior to relocation, temporary journal should have been unlinked
        # so local_root remains the active default root without missing-pointer errors!
        journal_path = self.local_root / app_config.RECOVERY_JOURNAL_NAME
        self.assertFalse(journal_path.exists())

        # Subsequent startup of existing source root must succeed cleanly!
        with patch.dict(os.environ, {
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }):
            paths = app_config.resolve_data_paths()
            self.assertEqual(paths.data_root, self.local_root.resolve())

    def test_abrupt_crash_after_switching_journal_before_promotion_recovers_cleanly(self) -> None:
        """If the process terminates abruptly (SIGKILL / power loss, simulated via BaseException)
        after writing the SWITCHING journal but BEFORE target promotion, startup recovery must
        detect the unpromoted staging directory, roll back the journal to the prior committed
        root (or remove it if first relocation), clean up staging, and open the source root idempotently.
        Also verifies that if neither target nor staging exists (e.g. unplugged promoted drive),
        startup fails closed with DataRootError.
        """
        from unittest.mock import patch
        from src.data_relocation import plan_relocation, execute_relocation

        class SimulatedPowerLoss(BaseException):
            pass

        env_vars = {
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }

        # --- Part 1: First relocation from default root crashes before promotion ---
        target_1 = self.home / "drive_d" / "CrashBeforePromote1"
        target_1.parent.mkdir(parents=True, exist_ok=True)
        plan_1 = plan_relocation(target_1, source_root=self.local_root)

        with patch("src.data_relocation._atomic_promote_no_clobber", side_effect=SimulatedPowerLoss("power lost before MoveFileExW")):
            with self.assertRaises(SimulatedPowerLoss):
                execute_relocation(plan_1, default_root=self.local_root)

        # Verify exact post-crash state on disk:
        # 1) Journal is in SWITCHING state
        journal_path = self.local_root / app_config.RECOVERY_JOURNAL_NAME
        self.assertTrue(journal_path.is_file())
        self.assertEqual(json.loads(journal_path.read_text(encoding="utf-8"))["status"], "SWITCHING")
        # 2) Staging directory is still on disk with its root marker
        self.assertTrue(plan_1.staging_dir.is_dir())
        self.assertTrue((plan_1.staging_dir / app_config.ROOT_MARKER_NAME).is_file())
        # 3) Target directory was never promoted
        self.assertFalse(target_1.exists())

        with patch.dict(os.environ, env_vars):
            # First startup recovers cleanly to local_root and removes unpromoted staging + journal
            paths = app_config.resolve_data_paths()
            self.assertEqual(paths.data_root, self.local_root.resolve())
            self.assertFalse(journal_path.exists())
            self.assertFalse(plan_1.staging_dir.exists())

            # Second startup is idempotent
            paths_again = app_config.resolve_data_paths()
            self.assertEqual(paths_again.data_root, self.local_root.resolve())

        # --- Part 2: Chained relocation (local_root -> committed_1 succeeds; committed_1 -> target_2 crashes before promotion) ---
        committed_1 = self.home / "drive_d" / "CommittedRoot1"
        plan_c1 = plan_relocation(committed_1, source_root=self.local_root)
        res_c1 = execute_relocation(plan_c1, default_root=self.local_root)
        self.assertTrue(res_c1.success)

        target_2 = self.home / "drive_e" / "CrashBeforePromote2"
        target_2.parent.mkdir(parents=True, exist_ok=True)
        plan_2 = plan_relocation(target_2, source_root=committed_1)

        with patch("src.data_relocation._atomic_promote_no_clobber", side_effect=SimulatedPowerLoss("power lost on chained relocation")):
            with self.assertRaises(SimulatedPowerLoss):
                execute_relocation(plan_2, default_root=self.local_root)

        self.assertEqual(json.loads(journal_path.read_text(encoding="utf-8"))["status"], "SWITCHING")
        self.assertTrue(plan_2.staging_dir.is_dir())
        self.assertFalse(target_2.exists())

        with patch.dict(os.environ, env_vars):
            # Startup recovers back to committed_1 and preserves history!
            paths_c1 = app_config.resolve_data_paths()
            self.assertEqual(paths_c1.data_root, committed_1.resolve())
            self.assertFalse(plan_2.staging_dir.exists())
            journal_after = json.loads(journal_path.read_text(encoding="utf-8"))
            self.assertEqual(journal_after["status"], "COMMITTED")
            self.assertEqual(journal_after["latest_committed_root"], str(committed_1))
            self.assertEqual(len(journal_after["history"]), 1)

            # Idempotent on subsequent call
            self.assertEqual(app_config.resolve_data_paths().data_root, committed_1.resolve())

        # --- Part 3: If target was promoted on an external volume that is now offline (neither target nor staging exists), fail closed! ---
        journal_path.write_text(
            json.dumps({
                "version": 1,
                "status": "SWITCHING",
                "pending_target_root": str(self.home / "unplugged_drive" / "VocabularyAppData"),
                "pending_staging_dir": str(self.home / "unplugged_drive" / ".vocab-stage-deadbeef1234"),
                "pending_marker_uuid": "deadbeef1234",
                "latest_committed_root": str(committed_1),
                "history": journal_after["history"],
            }),
            encoding="utf-8",
        )
        with patch.dict(os.environ, env_vars):
            with self.assertRaises(app_config.DataRootError) as ctx:
                app_config.resolve_data_paths()
            self.assertIn("target verification failed", str(ctx.exception))

    def test_crash_recovery_forward_rolls_interrupted_switching_state_and_verifies_all_four_components(self) -> None:
        """If a crash occurred after promoting target and writing SWITCHING journal,
        resolve_data_paths() must verify all 4 components (database, backups, audio-cache,
        preferences.json) and marker provenance (source_root, target_root, marker_uuid)
        before forward-rolling to COMMITTED. Any missing/corrupt component must fail closed.
        """
        from unittest.mock import patch
        from src.data_relocation import plan_relocation, execute_relocation, _atomic_promote_no_clobber

        class SimulatedPostPromotionCrash(BaseException):
            pass

        target = self.home / "drive_d" / "InterruptedSwitchingTarget"
        target.parent.mkdir(parents=True, exist_ok=True)
        plan = plan_relocation(target, source_root=self.local_root)

        def promote_then_crash(staging_dir: Path, target_dir: Path) -> None:
            _atomic_promote_no_clobber(staging_dir, target_dir)
            raise SimulatedPostPromotionCrash("crashed right after MoveFileExW before pointer write")

        with patch("src.data_relocation._atomic_promote_no_clobber", side_effect=promote_then_crash):
            with self.assertRaises(SimulatedPostPromotionCrash):
                execute_relocation(plan, default_root=self.local_root)

        journal_path = self.local_root / app_config.RECOVERY_JOURNAL_NAME
        pointer_path = self.local_root / app_config.DATA_ROOT_POINTER_NAME
        self.assertFalse(pointer_path.exists())
        self.assertTrue(target.is_dir())
        self.assertEqual(json.loads(journal_path.read_text(encoding="utf-8"))["status"], "SWITCHING")

        env_vars = {
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }

        # 1. Tamper with audio-cache file -> must fail closed (not forward-roll!)
        audio_file = target / "audio-cache" / "sample.mp3"
        orig_audio_bytes = audio_file.read_bytes()
        audio_file.unlink()
        with patch.dict(os.environ, env_vars):
            with self.assertRaises(app_config.DataRootError) as ctx:
                app_config.resolve_data_paths()
            self.assertIn("audio_cache", str(ctx.exception))
        audio_file.write_bytes(orig_audio_bytes)

        # 2. Tamper with backups file -> must fail closed
        backup_file = target / "backups" / "backup_1.bak"
        orig_backup_bytes = backup_file.read_bytes()
        backup_file.write_bytes(b"truncated")
        with patch.dict(os.environ, env_vars):
            with self.assertRaises(app_config.DataRootError) as ctx:
                app_config.resolve_data_paths()
            self.assertIn("backups", str(ctx.exception))
        backup_file.write_bytes(orig_backup_bytes)

        # 3. Tamper with preferences.json -> must fail closed
        prefs_file = target / "preferences.json"
        orig_prefs_bytes = prefs_file.read_bytes()
        prefs_file.unlink()
        with patch.dict(os.environ, env_vars):
            with self.assertRaises(app_config.DataRootError) as ctx:
                app_config.resolve_data_paths()
            self.assertIn("preferences", str(ctx.exception))
        prefs_file.write_bytes(orig_prefs_bytes)

        # 4. Tamper with source_root provenance in marker -> must fail closed
        marker_file = target / app_config.ROOT_MARKER_NAME
        orig_marker_bytes = marker_file.read_bytes()
        bad_marker = json.loads(orig_marker_bytes.decode("utf-8"))
        bad_marker["source_root"] = str(self.home / "wrong_source_root")
        marker_file.write_text(json.dumps(bad_marker), encoding="utf-8")
        with patch.dict(os.environ, env_vars):
            with self.assertRaises(app_config.DataRootError) as ctx:
                app_config.resolve_data_paths()
            self.assertIn("source_root", str(ctx.exception))
        marker_file.write_bytes(orig_marker_bytes)

        # 5. Now with all 4 components and marker provenance intact, resolve_data_paths() forward-rolls!
        with patch.dict(os.environ, env_vars):
            paths = app_config.resolve_data_paths()
            self.assertEqual(paths.data_root, target.resolve())

            # Pointer should have been written
            self.assertTrue(pointer_path.exists())
            pointer_data = json.loads(pointer_path.read_text(encoding="utf-8"))
            self.assertEqual(pointer_data["data_root"], str(target))

            # Journal should have been updated to COMMITTED with full metadata
            journal_data = json.loads(journal_path.read_text(encoding="utf-8"))
            self.assertEqual(journal_data["status"], "COMMITTED")
            self.assertEqual(journal_data["latest_committed_root"], str(target))
            self.assertEqual(len(journal_data["history"]), 1)
            self.assertTrue(journal_data["history"][0]["recovered"])
            self.assertEqual(journal_data["history"][0]["schema_version"], "2")
            self.assertEqual(journal_data["history"][0]["app_data_version"], "1.1.0")


    def test_crash_recovery_switching_corrupt_target_fails_closed(self) -> None:
        """If SWITCHING state points to an incomplete/corrupt target, fail closed with DataRootError."""
        target = self.home / "drive_d" / "IncompleteTarget"
        target.mkdir(parents=True)
        # No DB, no marker

        journal_path = self.local_root / app_config.RECOVERY_JOURNAL_NAME
        journal_path.write_text(
            json.dumps({
                "version": 1,
                "status": "SWITCHING",
                "pending_target_root": str(target),
                "pending_marker_uuid": "incomplete_uuid",
                "latest_committed_root": str(self.local_root),
                "history": [],
            }),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }):
            with self.assertRaises(app_config.DataRootError) as ctx:
                app_config.resolve_data_paths()
            self.assertIn("target verification failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()




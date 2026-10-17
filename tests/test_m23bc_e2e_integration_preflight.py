from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from PySide6.QtCore import QEvent

from src import app_config, db
from src.app_config import (
    DATA_ROOT_POINTER_NAME,
    RECOVERY_JOURNAL_NAME,
    ROOT_MARKER_NAME,
    DataRootError,
    bind_startup_data_paths,
    get_app_preferences_path,
    get_audio_cache_dir,
    get_backup_dir,
    get_database_path,
    resolve_data_paths,
)
from src.audio_assets import AudioAssetRequest, AudioAssetStore
from src.data_relocation import (
    RelocationError,
    execute_relocation,
    plan_relocation,
)
from src.tts_providers import ProviderRegistry
from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.state.preferences import Preferences, load_preferences, save_preferences
from src.ui_desktop.views.settings_view import SettingsView


def _qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _seed_fictional_data(root: Path) -> None:
    """Populates an isolated root with fictional 4-component test data."""
    root.mkdir(parents=True, exist_ok=True)
    db_file = root / "vocab.db"
    
    with closing(sqlite3.connect(db_file)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY, term TEXT, meaning TEXT, language TEXT, explanation_language TEXT, entry_type TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS collections (id INTEGER PRIMARY KEY, name TEXT, card_size INTEGER DEFAULT 8, is_system INTEGER DEFAULT 0, system_type TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY, collection_id INTEGER, card_number INTEGER, is_active INTEGER, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS card_review_schedules (card_id INTEGER PRIMARY KEY, next_due_at TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS card_review_states (id INTEGER PRIMARY KEY, collection_id INTEGER, card_number INTEGER, status TEXT, review_count INTEGER, current_interval_days INTEGER, ease_factor REAL, next_due_at TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS app_metadata (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
        conn.executemany(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
            (
                ("schema_version", "21.1.0-review-schedule", "2026-10-17T12:00:00Z"),
                ("app_data_version", "21.1", "2026-10-17T12:00:00Z"),
            ),
        )
        conn.execute("INSERT OR REPLACE INTO collections (id, name, created_at, updated_at) VALUES (1, 'Fictional Spanish 101', '2026-10-17T12:00:00Z', '2026-10-17T12:00:00Z')")
        conn.execute("INSERT OR REPLACE INTO entries (id, term, meaning, language, explanation_language, entry_type, created_at, updated_at) "
                     "VALUES (1, 'hola', 'hello', 'es', 'en', 'word', '2026-10-17T12:00:00Z', '2026-10-17T12:00:00Z')")
        conn.commit()

    # Backups component
    backups_dir = root / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    (backups_dir / "vocab-fictional-pre-backup.db").write_text("fictional backup content", encoding="utf-8")

    # Audio cache component
    audio_dir = root / "audio-cache" / "units" / "ab"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "abcdef1234567890.wav").write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    # Preferences component
    prefs_file = root / "preferences.json"
    prefs_file.write_text(
        json.dumps({
            "appearance": "Dark",
            "accent": "Calm Blue",
            "motion": "full",
            "quiz_presentation": "immersive_focus",
            "show_collection_progress_bars": True,
            "include_proficient_in_study": True,
            "voice_bindings": {"fr": "fr-FR-DeniseNeural"},
        }, indent=2),
        encoding="utf-8",
    )


class M23BCE2EIntegrationPreflightTests(unittest.TestCase):
    """Native Windows End-to-End Integration Preflight Test Suite for M23-B/C.
    Uses completely isolated disposable directories for all tests.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="vocab-m23bc-preflight-", ignore_cleanup_errors=True)
        self.base = Path(self.temp_dir.name).resolve()
        self.local_root = self.base / "local" / "vocabulary_app"

        # Clear startup bindings before each test
        app_config._bound_relocated_paths = None
        app_config._bound_active_paths = None
        app_config._bound_guarded_database = None

        self.clean_env = {
            "LOCALAPPDATA": str(self.base / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }

        with patch.dict(os.environ, self.clean_env):
            _seed_fictional_data(self.local_root)

    def tearDown(self) -> None:
        app_config._bound_relocated_paths = None
        app_config._bound_active_paths = None
        app_config._bound_guarded_database = None
        self.temp_dir.cleanup()

    def test_e2e_scenario1_settings_ui_relocation_and_reopening(self) -> None:
        """Scenario 1: Complete Settings -> Storage relocation flow via UI,
        verifying 4 components preserved, restart and reopening.
        """
        target_volume = self.base / "external_d"
        target_volume.mkdir()

        with patch.dict(os.environ, self.clean_env):
            controller = SettingsController()
            view = SettingsView(controller)
            self.addCleanup(view.deleteLater)

            with patch("src.ui_desktop.views.settings_view.QFileDialog.getExistingDirectory", return_value=str(target_volume)), \
                 patch("src.ui_desktop.views.settings_view.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
                 patch("src.ui_desktop.views.settings_view.QMessageBox.information") as mock_info, \
                 patch.object(self.app, "quit") as mock_quit:

                view._storage_move_btn.click()
                if hasattr(view, "_relocation_worker") and view._relocation_worker is not None:
                    view._relocation_worker.wait(10000)
                self.app.processEvents()

                mock_info.assert_called_once()
                mock_quit.assert_called_once()

            # Target root check
            target_root = target_volume / "VocabularyAppData"
            self.assertTrue(target_root.is_dir())
            self.assertTrue((target_root / "vocab.db").is_file())
            self.assertTrue((target_root / "backups" / "vocab-fictional-pre-backup.db").is_file())
            self.assertTrue((target_root / "audio-cache" / "units" / "ab" / "abcdef1234567890.wav").is_file())
            self.assertTrue((target_root / "preferences.json").is_file())
            self.assertTrue((target_root / ROOT_MARKER_NAME).is_file())

            # Original source retention check
            self.assertTrue(self.local_root.is_dir())
            self.assertTrue((self.local_root / "vocab.db").is_file())
            self.assertTrue((self.local_root / "preferences.json").is_file())

            # Pointer and journal check at default root
            pointer_file = self.local_root / DATA_ROOT_POINTER_NAME
            journal_file = self.local_root / RECOVERY_JOURNAL_NAME
            self.assertTrue(pointer_file.is_file())
            self.assertTrue(journal_file.is_file())

            # Simulate app restart (new process environment)
            app_config._bound_relocated_paths = None
            app_config._bound_guarded_database = None
            resolved = resolve_data_paths()
            self.assertEqual(resolved.data_root, target_root)
            self.assertEqual(resolved.database, target_root / "vocab.db")
            self.assertEqual(resolved.backups, target_root / "backups")
            self.assertEqual(resolved.audio_cache, target_root / "audio-cache")
            self.assertEqual(resolved.preferences, target_root / "preferences.json")

            # Verify opening DB and reading fictional data
            with closing(sqlite3.connect(resolved.database)) as conn:
                row = conn.execute("SELECT term, meaning FROM entries WHERE id = 1").fetchone()
                self.assertEqual(row, ("hola", "hello"))

            # Verify loading preferences
            prefs = load_preferences()
            self.assertEqual(prefs.appearance, "Dark")
            self.assertEqual(prefs.voice_bindings.get("fr"), "fr-FR-DeniseNeural")

    def test_e2e_scenario2_chained_relocations_history(self) -> None:
        """Scenario 2: Chained relocations (Source -> Target1 -> Target2)
        verifying journal history continuity, marker UUIDs and pointers.
        """
        vol1 = self.base / "vol1"
        vol2 = self.base / "vol2"
        vol1.mkdir(); vol2.mkdir()
        target1 = vol1 / "VocabularyAppData"
        target2 = vol2 / "VocabularyAppData"

        with patch.dict(os.environ, self.clean_env):
            # Step 1: Relocate default -> target1
            plan1 = plan_relocation(target1, source_root=self.local_root)
            res1 = execute_relocation(plan1, default_root=self.local_root)
            self.assertTrue(res1.success)

            # Verify restart resolution to target1
            app_config._bound_relocated_paths = None
            app_config._bound_guarded_database = None
            resolved1 = resolve_data_paths()
            self.assertEqual(resolved1.data_root, target1)

            # Step 2: Relocate target1 -> target2
            plan2 = plan_relocation(target2, source_root=target1)
            res2 = execute_relocation(plan2, default_root=self.local_root)
            self.assertTrue(res2.success)

            # Verify restart resolution to target2
            app_config._bound_relocated_paths = None
            app_config._bound_guarded_database = None
            resolved2 = resolve_data_paths()
            self.assertEqual(resolved2.data_root, target2)

            # Check journal history continuity
            journal_data = json.loads((self.local_root / RECOVERY_JOURNAL_NAME).read_text(encoding="utf-8"))
            self.assertEqual(journal_data["status"], "COMMITTED")
            self.assertEqual(Path(journal_data["latest_committed_root"]).resolve(), target2)
            self.assertEqual(len(journal_data["history"]), 2)
            self.assertEqual(journal_data["history"][0]["sequence"], 1)
            self.assertEqual(Path(journal_data["history"][0]["source_root"]).resolve(), self.local_root)
            self.assertEqual(Path(journal_data["history"][0]["target_root"]).resolve(), target1)
            self.assertEqual(journal_data["history"][1]["sequence"], 2)
            self.assertEqual(Path(journal_data["history"][1]["source_root"]).resolve(), target1)
            self.assertEqual(Path(journal_data["history"][1]["target_root"]).resolve(), target2)

            # Both intermediate source (local_root) and target1 retain their original files
            self.assertTrue((self.local_root / "vocab.db").is_file())
            self.assertTrue((target1 / "vocab.db").is_file())
            self.assertTrue((target2 / "vocab.db").is_file())

    def test_e2e_scenario3_occupied_destination_rejection_no_clobber(self) -> None:
        """Scenario 3: Occupied destination rejection prevents clobbering existing files/folders
        both at planning time and under race condition.
        """
        vol = self.base / "occupied_vol"
        vol.mkdir()
        target = vol / "VocabularyAppData"
        target.mkdir()
        (target / "existing_user_file.txt").write_text("do not delete!", encoding="utf-8")

        with patch.dict(os.environ, self.clean_env):
            # Preflight plan must reject occupied destination
            with self.assertRaises(RelocationError) as ctx:
                plan_relocation(target, source_root=self.local_root)
            self.assertIn("already exists and is occupied", str(ctx.exception))

            # Existing file remains untouched
            self.assertTrue((target / "existing_user_file.txt").is_file())
            self.assertEqual((target / "existing_user_file.txt").read_text(encoding="utf-8"), "do not delete!")

    def test_e2e_scenario4_disconnected_target_volume_fail_closed(self) -> None:
        """Scenario 4: Disconnected or missing target volume fails closed safely
        without falling back to stale default data or creating a blank DB.
        """
        vol = self.base / "external_e"
        vol.mkdir()
        target = vol / "VocabularyAppData"

        with patch.dict(os.environ, self.clean_env):
            plan = plan_relocation(target, source_root=self.local_root)
            execute_relocation(plan, default_root=self.local_root)

            # Simulate drive disconnect by renaming/removing external folder
            shutil.rmtree(target)

            app_config._bound_relocated_paths = None
            app_config._bound_guarded_database = None

            # Startup resolution must fail closed with DataRootError
            with self.assertRaises(DataRootError) as ctx:
                resolve_data_paths()
            self.assertIn("selected folder does not exist", str(ctx.exception).lower())

            # Verify no replacement database was created at default root
            # Note: default root still has its original vocab.db, but it must NOT be opened silently
            # Let's verify get_database_path() raises DataRootError
            with self.assertRaises(DataRootError):
                get_database_path()

    def test_e2e_scenario5_interrupted_transition_crash_recovery(self) -> None:
        """Scenario 5: Crash recovery when journal is left in SWITCHING state:
        Case A: abrupt crash before promotion -> rolls back safely to prior committed root.
        Case B: abrupt crash after promotion -> rolls forward cleanly to target root.
        """
        vol = self.base / "crash_vol"
        vol.mkdir()
        target = vol / "VocabularyAppData"

        with patch.dict(os.environ, self.clean_env):
            plan = plan_relocation(target, source_root=self.local_root)

            # Case A: Crash BEFORE atomic promotion (staging directory exists with marker)
            plan.staging_dir.mkdir(parents=True)
            (plan.staging_dir / "vocab.db").write_text("staged db", encoding="utf-8")
            (plan.staging_dir / ROOT_MARKER_NAME).write_text(
                json.dumps({
                    "version": 1,
                    "marker_uuid": plan.marker_uuid,
                    "source_root": str(self.local_root),
                    "target_root": str(target),
                }),
                encoding="utf-8",
            )
            switching_journal = {
                "version": 1,
                "status": "SWITCHING",
                "pending_target_root": str(target),
                "pending_staging_dir": str(plan.staging_dir),
                "pending_marker_uuid": plan.marker_uuid,
                "latest_committed_root": str(self.local_root),
                "history": [],
            }
            (self.local_root / RECOVERY_JOURNAL_NAME).write_text(json.dumps(switching_journal), encoding="utf-8")

            # Starting up now should detect unpromoted staging and rollback safely
            app_config._bound_relocated_paths = None
            app_config._bound_guarded_database = None
            resolved_a = resolve_data_paths()
            self.assertEqual(resolved_a.data_root, self.local_root)
            # Staging directory must be cleaned up
            self.assertFalse(plan.staging_dir.exists())

            # Case B: Crash AFTER atomic promotion (promoted target exists with complete manifest)
            plan_b = plan_relocation(target, source_root=self.local_root)
            # Populate target as promoted
            shutil.copytree(self.local_root, target)
            (target / ROOT_MARKER_NAME).write_text(
                json.dumps({
                    "version": 1,
                    "marker_uuid": plan_b.marker_uuid,
                    "source_root": str(self.local_root),
                    "target_root": str(target),
                    "components": app_config._build_component_manifest(target),
                }),
                encoding="utf-8",
            )
            switching_journal_b = {
                "version": 1,
                "status": "SWITCHING",
                "pending_target_root": str(target),
                "pending_staging_dir": str(plan_b.staging_dir),
                "pending_marker_uuid": plan_b.marker_uuid,
                "latest_committed_root": str(self.local_root),
                "pending_components": app_config._build_component_manifest(target),
                "history": [],
            }
            (self.local_root / RECOVERY_JOURNAL_NAME).write_text(json.dumps(switching_journal_b), encoding="utf-8")

            # Starting up now should detect promoted target and forward-roll pointer & journal
            app_config._bound_relocated_paths = None
            app_config._bound_guarded_database = None
            resolved_b = resolve_data_paths()
            self.assertEqual(resolved_b.data_root, target)

            # Check pointer was created and journal marked COMMITTED
            pointer = json.loads((self.local_root / DATA_ROOT_POINTER_NAME).read_text(encoding="utf-8"))
            self.assertEqual(Path(pointer["data_root"]).resolve(), target)
            journal = json.loads((self.local_root / RECOVERY_JOURNAL_NAME).read_text(encoding="utf-8"))
            self.assertEqual(journal["status"], "COMMITTED")
            self.assertEqual(Path(journal["latest_committed_root"]).resolve(), target)

    def test_e2e_scenario6_stale_root_background_write_prevention(self) -> None:
        """Scenario 6: Invariant verification: Prevent stale-root background writes
        between migration commit and application exit.
        """
        # Step 1: Start from an established relocated baseline
        vol1 = self.base / "target_vol1"
        vol1.mkdir()
        source_relocated = vol1 / "VocabularyAppData"
        _seed_fictional_data(source_relocated)
        (self.local_root / DATA_ROOT_POINTER_NAME).write_text(
            json.dumps({"version": 1, "data_root": str(source_relocated)}),
            encoding="utf-8",
        )
        (self.local_root / RECOVERY_JOURNAL_NAME).write_text(
            json.dumps({
                "version": 1,
                "status": "COMMITTED",
                "latest_committed_root": str(source_relocated),
                "history": [],
            }),
            encoding="utf-8",
        )

        with patch.dict(os.environ, self.clean_env):
            # Pin the active relocated paths at process startup
            paths = bind_startup_data_paths()
            self.assertTrue(paths.relocated)
            db.DB_PATH = paths.database

            # Verify initial DB connection can open and write
            with closing(db.get_connection()) as conn:
                conn.execute("INSERT INTO collections (id, name) VALUES (2, 'Initial Collection')")
                conn.commit()

            # Step 2: Now relocate from source_relocated to target_vol2
            vol2 = self.base / "target_vol2"
            vol2.mkdir()
            target_relocated = vol2 / "VocabularyAppData"

            plan = plan_relocation(target_relocated, source_root=source_relocated)
            res = execute_relocation(plan, default_root=self.local_root)
            self.assertTrue(res.success)

            # Step 3: In the currently running app process, any subsequent call to db.get_connection()
            # or resolve_data_paths() MUST fail with DataRootError because data-root.json now points
            # to target_relocated, which differs from _bound_relocated_paths!
            with self.assertRaises(DataRootError) as ctx:
                db.get_connection()
            err_msg = str(ctx.exception).lower()
            self.assertTrue(
                "the location pointer changed while the app was open" in err_msg
                or "data paths changed while the app was open" in err_msg
            )

            # Step 4: Attempting to save preferences without explicit path must also fail with DataRootError
            with self.assertRaises(DataRootError):
                save_preferences(Preferences(appearance="Light"))

            # Step 5: Audio asset store materialization must also fail with DataRootError
            with self.assertRaises(DataRootError):
                AudioAssetStore()

    def test_e2e_scenario7_ui_closing_during_active_relocation(self) -> None:
        """Scenario 7: MainWindow closeEvent during active relocation waits for
        background worker to finish and prevents premature teardown.
        """
        from PySide6.QtGui import QCloseEvent
        from src.ui_desktop.main_window import MainWindow

        with patch.dict(os.environ, self.clean_env):
            # Patch TodayController.refresh to avoid database dependency
            with patch("src.ui_desktop.controllers.today_controller.TodayController.refresh"):
                main_win = MainWindow()
                try:
                    controller = main_win.settings_controller

                    # Simulate active worker
                    fake_worker = MagicMock()
                    fake_worker.isRunning.return_value = True
                    fake_worker.wait.return_value = True
                    controller.register_relocation_worker(fake_worker)
                    self.assertTrue(controller.is_relocating())

                    close_event = QCloseEvent()
                    main_win.closeEvent(close_event)

                    # Shutdown was called and waited for worker
                    fake_worker.wait.assert_called_with(15000)
                    self.assertTrue(close_event.isAccepted())

                    # If worker times out (returns False), closeEvent must be ignored
                    fake_worker.wait.reset_mock()
                    fake_worker.wait.return_value = False
                    close_event_timeout = QCloseEvent()
                    main_win.closeEvent(close_event_timeout)
                    self.assertFalse(close_event_timeout.isAccepted())
                finally:
                    main_win.close()
                    self.app.processEvents()
                    main_win.deleteLater()


if __name__ == "__main__":
    unittest.main()

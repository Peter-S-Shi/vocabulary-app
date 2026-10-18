from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from src import app_config


def _create_fictional_app_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE app_metadata (key TEXT PRIMARY KEY, "
            "value TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
            (("schema_version", "test", "fictional"),
             ("app_data_version", "test", "fictional")),
        )
        connection.commit()


class M23ADataRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_startup = app_config._bound_startup_paths
        self._saved_relocated = app_config._bound_relocated_paths
        self._saved_guarded = app_config._bound_guarded_database
        app_config._bound_relocated_paths = None
        app_config._bound_startup_paths = None
        app_config._bound_guarded_database = None

    def tearDown(self) -> None:
        app_config._bound_startup_paths = self._saved_startup
        app_config._bound_relocated_paths = self._saved_relocated
        app_config._bound_guarded_database = self._saved_guarded

    def test_legacy_installation_without_pointer_keeps_original_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            local = home / "local"
            with patch.dict(os.environ, {
                "LOCALAPPDATA": str(local),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            }):
                paths = app_config.resolve_data_paths()
            self.assertEqual(paths.database, local / "vocabulary_app" / "vocab.db")
            self.assertEqual(paths.backups, local / "vocabulary_app" / "backups")
            self.assertEqual(paths.audio_cache, local / "vocabulary_app" / "audio-cache")
            self.assertEqual(paths.preferences, local / "vocabulary_app" / "preferences.json")
            self.assertFalse(paths.relocated)
            self.assertFalse((local / "vocabulary_app").exists())

    def test_relocated_root_resolves_all_four_components_before_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            relocated = home / "fictional-relocated"
            default_root.mkdir(parents=True)
            relocated.mkdir()
            _create_fictional_app_database(relocated / "vocab.db")
            (default_root / "data-root.json").write_text(
                json.dumps({"version": 1, "data_root": str(relocated)}), encoding="utf-8"
            )
            with patch.dict(os.environ, {
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            }):
                self.assertEqual(app_config.get_database_path(), relocated / "vocab.db")
                self.assertEqual(app_config.get_backup_dir(), relocated / "backups")
                self.assertEqual(app_config.get_audio_cache_dir(), relocated / "audio-cache")
                self.assertEqual(app_config.get_app_preferences_path(), relocated / "preferences.json")

    def test_missing_selected_drive_stops_native_startup_before_database_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            default_root.mkdir(parents=True)
            missing_root = home / "disconnected-fictional-drive"
            (default_root / "data-root.json").write_text(
                json.dumps({"version": 1, "data_root": str(missing_root)}), encoding="utf-8"
            )
            environment = dict(os.environ)
            environment.update({
                "LOCALAPPDATA": str(home / "local"),
                "QT_QPA_PLATFORM": "offscreen",
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            })
            for command in (
                [sys.executable, "-m", "src.ui_desktop"],
                [sys.executable, "winbuild/desktop_entry.py"],
            ):
                with self.subTest(command=command):
                    process = subprocess.run(
                        command,
                        cwd=Path(__file__).resolve().parent.parent,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    self.assertEqual(process.returncode, 2, process.stderr)
                    self.assertIn("Reconnect the original drive", process.stderr)
            self.assertFalse((default_root / "vocab.db").exists())
            self.assertFalse(missing_root.exists())

    def test_corrupt_selected_database_is_rejected_without_replacing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            relocated = home / "fictional-relocated"
            default_root.mkdir(parents=True)
            relocated.mkdir()
            database = relocated / "vocab.db"
            original = b"fictional damaged database"
            database.write_bytes(original)
            (default_root / "data-root.json").write_text(
                json.dumps({"version": 1, "data_root": str(relocated)}), encoding="utf-8"
            )
            with patch.dict(os.environ, {
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            }):
                with self.assertRaises(app_config.DataRootError):
                    app_config.get_database_path()
            self.assertEqual(database.read_bytes(), original)
            self.assertFalse((default_root / "vocab.db").exists())

    def test_unrelated_sqlite_with_entries_table_is_not_accepted_as_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            relocated = home / "unrelated-fictional-sqlite"
            default_root.mkdir(parents=True)
            relocated.mkdir()
            with closing(sqlite3.connect(relocated / "vocab.db")) as connection:
                connection.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY)")
                connection.commit()
            (default_root / "data-root.json").write_text(
                json.dumps({"version": 1, "data_root": str(relocated)}), encoding="utf-8"
            )
            with patch.dict(os.environ, {
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            }):
                with self.assertRaises(app_config.DataRootError):
                    app_config.get_database_path()

    def test_selected_database_disappearing_after_import_is_not_recreated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            relocated = home / "fictional-relocated"
            default_root.mkdir(parents=True)
            relocated.mkdir()
            database = relocated / "vocab.db"
            _create_fictional_app_database(database)
            (default_root / "data-root.json").write_text(
                json.dumps({"version": 1, "data_root": str(relocated)}), encoding="utf-8"
            )
            environment = dict(os.environ)
            environment.update({
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            })
            process = subprocess.run(
                [sys.executable, "-c", "from src import db; "
                 "db.DB_PATH.rename(db.DB_PATH.with_suffix('.saved')); db.init_db()"],
                cwd=Path(__file__).resolve().parent.parent,
                env=environment,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("DataRootError", process.stderr)
            self.assertFalse(database.exists())
            self.assertTrue(database.with_suffix(".saved").is_file())

    def test_explicit_overrides_win_per_component_and_full_override_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            relocated = home / "fictional-relocated"
            default_root.mkdir(parents=True)
            relocated.mkdir()
            _create_fictional_app_database(relocated / "vocab.db")
            pointer = default_root / "data-root.json"
            pointer.write_text(
                json.dumps({"version": 1, "data_root": str(relocated)}), encoding="utf-8"
            )
            override_db = home / "advanced" / "chosen.db"
            override_db.parent.mkdir()
            _create_fictional_app_database(override_db)
            override_backup = home / "advanced" / "backups"
            override_audio = home / "advanced" / "audio"
            override_preferences = home / "advanced" / "prefs.json"
            environment = {
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": str(override_db),
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            }
            with patch.dict(os.environ, environment):
                partial = app_config.resolve_data_paths()
            self.assertEqual(partial.database, override_db)
            self.assertEqual(partial.backups, relocated / "backups")
            self.assertEqual(partial.audio_cache, relocated / "audio-cache")
            self.assertEqual(partial.preferences, relocated / "preferences.json")

            pointer.write_text("damaged pointer", encoding="utf-8")
            with patch.dict(os.environ, environment):
                with self.assertRaises(app_config.DataRootError):
                    app_config.resolve_data_paths()
            environment.update({
                "VOCAB_APP_BACKUP_DIR": str(override_backup),
                "VOCAB_APP_AUDIO_CACHE_DIR": str(override_audio),
                "VOCAB_APP_PREFERENCES_PATH": str(override_preferences),
            })
            with patch.dict(os.environ, environment):
                recovered = app_config.resolve_data_paths()
            self.assertEqual(
                (recovered.database, recovered.backups, recovered.audio_cache, recovered.preferences),
                (override_db, override_backup, override_audio, override_preferences),
            )
            self.assertFalse(recovered.relocated)

    def test_full_override_cannot_bypass_damaged_pointer_into_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            default_root.mkdir(parents=True)
            (default_root / "data-root.json").write_text("damaged pointer", encoding="utf-8")
            advanced = home / "advanced"
            with patch.dict(os.environ, {
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": str(advanced / "missing.db"),
                "VOCAB_APP_BACKUP_DIR": str(advanced / "backups"),
                "VOCAB_APP_AUDIO_CACHE_DIR": str(advanced / "audio"),
                "VOCAB_APP_PREFERENCES_PATH": str(advanced / "prefs.json"),
            }):
                with self.assertRaises(app_config.DataRootError):
                    app_config.resolve_data_paths()
            self.assertFalse(advanced.exists())

    def test_invalid_pointer_state_fails_closed_without_writing_default_data(self) -> None:
        invalid_contents = (
            "not-json",
            json.dumps({"version": 99, "data_root": "unused"}),
            json.dumps({"version": 1, "data_root": "relative/folder"}),
            json.dumps({"version": 1, "data_root": ""}),
        )
        for content in invalid_contents:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary).resolve()
                default_root = home / "local" / "vocabulary_app"
                default_root.mkdir(parents=True)
                pointer = default_root / "data-root.json"
                pointer.write_text(content, encoding="utf-8")
                legacy_database = default_root / "vocab.db"
                legacy_database.write_bytes(b"fictional prior data sentinel")
                with patch.dict(os.environ, {
                    "LOCALAPPDATA": str(home / "local"),
                    "VOCAB_APP_DB_PATH": "",
                    "VOCAB_APP_BACKUP_DIR": "",
                    "VOCAB_APP_AUDIO_CACHE_DIR": "",
                    "VOCAB_APP_PREFERENCES_PATH": "",
                }):
                    with self.assertRaises(app_config.DataRootError):
                        app_config.resolve_data_paths()
                self.assertEqual(legacy_database.read_bytes(), b"fictional prior data sentinel")
                self.assertEqual(
                    sorted(item.name for item in default_root.iterdir()),
                    ["data-root.json", "vocab.db"],
                )

    def test_desktop_bootstrap_opens_existing_relocated_data_before_building_ui(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            relocated = home / "fictional-relocated"
            default_root.mkdir(parents=True)
            relocated.mkdir()
            seed_environment = dict(os.environ)
            seed_environment.update({
                "LOCALAPPDATA": str(home / "local"),
                "VOCAB_APP_DB_PATH": str(relocated / "vocab.db"),
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            })
            seeded = subprocess.run(
                [sys.executable, "-c", "from src.db import init_db; init_db()"],
                cwd=Path(__file__).resolve().parent.parent,
                env=seed_environment,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            (default_root / "data-root.json").write_text(
                json.dumps({"version": 1, "data_root": str(relocated)}), encoding="utf-8"
            )
            environment = dict(os.environ)
            environment.update({
                "LOCALAPPDATA": str(home / "local"),
                "QT_QPA_PLATFORM": "offscreen",
                "EXPECTED_FICTIONAL_ROOT": str(relocated),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            })
            script = (
                "import os; from pathlib import Path; from src import db; "
                "from src.ui_desktop.app import build_application; "
                "from src.app_config import get_app_storage_summary; "
                "a,w,t=build_application([]); "
                "root=Path(os.environ['EXPECTED_FICTIONAL_ROOT']); "
                "assert db.DB_PATH.resolve() == (root / 'vocab.db').resolve(); "
                "assert get_app_storage_summary()['path_source']=='relocated data root'; "
                "w.close()"
            )
            process = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parent.parent,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue((relocated / "vocab.db").is_file())
            self.assertFalse((default_root / "vocab.db").exists())

    def test_pointer_switch_during_running_process_does_not_redirect_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            old_root = home / "fictional-old"
            new_root = home / "fictional-new"
            default_root.mkdir(parents=True)
            for root in (old_root, new_root):
                root.mkdir()
                _create_fictional_app_database(root / "vocab.db")
            pointer = default_root / "data-root.json"
            pointer.write_text(
                json.dumps({"version": 1, "data_root": str(old_root)}), encoding="utf-8"
            )
            environment = dict(os.environ)
            environment.update({
                "LOCALAPPDATA": str(home / "local"),
                "FICTIONAL_POINTER": str(pointer),
                "FICTIONAL_NEW_ROOT": str(new_root),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            })
            script = (
                "import json, os; from pathlib import Path; from src import db; "
                "from src.app_config import get_app_preferences_path; "
                "p=Path(os.environ['FICTIONAL_POINTER']); "
                "p.write_text(json.dumps({'version':1,'data_root':os.environ['FICTIONAL_NEW_ROOT']}),encoding='utf-8'); "
                "get_app_preferences_path()"
            )
            process = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parent.parent,
                env=environment,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("DataRootError", process.stderr)
            self.assertTrue((old_root / "vocab.db").is_file())
            self.assertTrue((new_root / "vocab.db").is_file())

    def test_override_change_during_relocated_session_does_not_split_backups(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            default_root = home / "local" / "vocabulary_app"
            relocated = home / "fictional-relocated"
            default_root.mkdir(parents=True)
            relocated.mkdir()
            _create_fictional_app_database(relocated / "vocab.db")
            (default_root / "data-root.json").write_text(
                json.dumps({"version": 1, "data_root": str(relocated)}), encoding="utf-8"
            )
            environment = dict(os.environ)
            environment.update({
                "LOCALAPPDATA": str(home / "local"),
                "FICTIONAL_OTHER_BACKUPS": str(home / "other-backups"),
                "VOCAB_APP_DB_PATH": "",
                "VOCAB_APP_BACKUP_DIR": "",
                "VOCAB_APP_AUDIO_CACHE_DIR": "",
                "VOCAB_APP_PREFERENCES_PATH": "",
            })
            process = subprocess.run(
                [sys.executable, "-c", "import os; from src import db; "
                 "from src.app_config import get_backup_dir; "
                 "os.environ['VOCAB_APP_BACKUP_DIR']=os.environ['FICTIONAL_OTHER_BACKUPS']; "
                 "get_backup_dir()"],
                cwd=Path(__file__).resolve().parent.parent,
                env=environment,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("DataRootError", process.stderr)
            self.assertFalse((home / "other-backups").exists())

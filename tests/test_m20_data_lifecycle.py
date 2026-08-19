from __future__ import annotations

import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from src.app_config import (
    APP_SLUG,
    BACKUP_DIR_ENV,
    DATABASE_PATH_ENV,
    get_backup_dir,
    get_database_path,
    get_default_data_dir,
    get_default_db_path,
    get_project_root,
)
from src.db_import import DatabaseImportError, import_existing_database
from src.migrations import (
    CURRENT_SCHEMA_VERSION,
    backup_before_pending_migration,
    build_pre_migration_backup_filename,
    ensure_app_metadata_table,
    set_metadata,
)

"""
Focused tests for the M20 production data-lifecycle foundation
(docs/packaging/M20_RELEASE_CONTRACT.md §§ 2.2, 2.6):

- the database/backup path defaults resolve under the frozen
  ``%LOCALAPPDATA%\\vocabulary_app\\`` root, not inside the repository
  working directory (the § 2.2 "critical finding" this checkpoint
  closes);
- environment-variable overrides for both still work, preserving the
  existing dev/test escape hatch;
- ``backup_before_pending_migration`` copies the database before a real
  pending migration, and is a safe no-op for a brand-new database or one
  already at the current schema;
- ``import_existing_database`` copies (never moves) a user-selected
  SQLite file into the active database location, backing up a non-empty
  destination first, and rejects unsafe inputs before touching anything.
"""

_ENV_KEYS = (
    "LOCALAPPDATA",
    "XDG_DATA_HOME",
    DATABASE_PATH_ENV,
    BACKUP_DIR_ENV,
)


class _EnvIsolationMixin(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._saved_env = {key: os.environ.get(key) for key in _ENV_KEYS}

    def tearDown(self) -> None:
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        super().tearDown()


class ProductionDataRootTests(_EnvIsolationMixin):
    def test_default_data_dir_resolves_under_local_app_data(self) -> None:
        os.environ.pop(DATABASE_PATH_ENV, None)
        os.environ.pop(BACKUP_DIR_ENV, None)
        os.environ["LOCALAPPDATA"] = r"C:\Users\example\AppData\Local"

        data_dir = get_default_data_dir()

        self.assertEqual(data_dir, Path(r"C:\Users\example\AppData\Local") / APP_SLUG)
        self.assertEqual(get_default_db_path(), data_dir / "vocab.db")
        self.assertEqual(get_backup_dir(), (data_dir / "backups").resolve())

    def test_default_data_dir_never_resolves_inside_project_root(self) -> None:
        os.environ.pop(DATABASE_PATH_ENV, None)
        os.environ.pop(BACKUP_DIR_ENV, None)
        os.environ["LOCALAPPDATA"] = r"C:\Users\example\AppData\Local"

        project_root = get_project_root()
        data_dir = get_default_data_dir()

        self.assertNotEqual(data_dir, project_root / "data")
        self.assertFalse(str(data_dir).startswith(str(project_root)))

    def test_non_windows_fallback_uses_xdg_data_home_not_project_root(self) -> None:
        os.environ.pop("LOCALAPPDATA", None)
        os.environ.pop(DATABASE_PATH_ENV, None)
        os.environ.pop(BACKUP_DIR_ENV, None)
        os.environ["XDG_DATA_HOME"] = "/tmp/example-xdg-data"

        data_dir = get_default_data_dir()

        self.assertEqual(data_dir, Path("/tmp/example-xdg-data") / APP_SLUG)

    def test_database_path_env_override_still_wins(self) -> None:
        os.environ["LOCALAPPDATA"] = r"C:\Users\example\AppData\Local"
        os.environ[DATABASE_PATH_ENV] = r"D:\override\vocab.db"

        self.assertEqual(get_database_path(), Path(r"D:\override\vocab.db").resolve())

    def test_backup_dir_env_override_still_wins(self) -> None:
        os.environ["LOCALAPPDATA"] = r"C:\Users\example\AppData\Local"
        os.environ[BACKUP_DIR_ENV] = r"D:\override\backups"

        self.assertEqual(get_backup_dir(), Path(r"D:\override\backups").resolve())


class FrozenProjectRootTests(unittest.TestCase):
    """PyInstaller places bundled ``datas`` under ``sys._MEIPASS``, one
    level deeper than ``sys.executable``'s own directory under the
    default --onedir ``_internal\\`` layout -- confirmed against a real
    PyInstaller 6.22 onedir build during M20 packaging work. Getting
    this wrong silently breaks the packaged app's icon and Local
    Windows Speech Provider scripts without any error until launch."""

    def test_frozen_resolves_via_meipass_not_executable_dir(self) -> None:
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "_MEIPASS", r"C:\Program Files\Vocabulary App\_internal", create=True), \
                patch.object(sys, "executable", r"C:\Program Files\Vocabulary App\Vocabulary App.exe"):
            root = get_project_root()
        self.assertEqual(root, Path(r"C:\Program Files\Vocabulary App\_internal"))

    def test_frozen_without_meipass_falls_back_to_executable_dir(self) -> None:
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", r"C:\Program Files\Vocabulary App\Vocabulary App.exe"):
            if hasattr(sys, "_MEIPASS"):
                delattr(sys, "_MEIPASS")
            root = get_project_root()
        self.assertEqual(root, Path(r"C:\Program Files\Vocabulary App"))

    def test_not_frozen_still_resolves_to_repo_root_from_source(self) -> None:
        self.assertFalse(getattr(sys, "frozen", False))
        root = get_project_root()
        self.assertTrue((root / "src" / "app_config.py").is_file())


def _connection_with_schema_version(version: str | None) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    if version is not None:
        ensure_app_metadata_table(connection)
        set_metadata(connection, "schema_version", version)
    return connection


class BackupBeforePendingMigrationTests(_EnvIsolationMixin):
    def setUp(self) -> None:
        super().setUp()
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        os.environ.pop("LOCALAPPDATA", None)
        os.environ[BACKUP_DIR_ENV] = str(self._tmp_path / "backups")

    def tearDown(self) -> None:
        self._tmp.cleanup()
        super().tearDown()

    def test_fresh_database_is_not_backed_up(self) -> None:
        db_path = self._tmp_path / "vocab.db"
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY)")
            connection.commit()
            result = backup_before_pending_migration(connection, db_path)
        finally:
            connection.close()

        self.assertIsNone(result)
        self.assertFalse((self._tmp_path / "backups").exists())

    def test_database_already_current_is_not_backed_up(self) -> None:
        db_path = self._tmp_path / "vocab.db"
        connection = sqlite3.connect(db_path)
        try:
            ensure_app_metadata_table(connection)
            set_metadata(connection, "schema_version", CURRENT_SCHEMA_VERSION)
            connection.commit()
            result = backup_before_pending_migration(connection, db_path)
        finally:
            connection.close()

        self.assertIsNone(result)

    def test_stale_schema_creates_identifiable_backup_with_prior_data(self) -> None:
        db_path = self._tmp_path / "vocab.db"
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, term TEXT)")
            connection.execute("INSERT INTO entries (id, term) VALUES (1, 'bonjour')")
            ensure_app_metadata_table(connection)
            set_metadata(connection, "schema_version", "13.0.0-linked-append-source")
            connection.commit()

            result = backup_before_pending_migration(connection, db_path)
        finally:
            connection.close()

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.exists())
        self.assertIn("vocab-pre-13.0.0-linked-append-source-", result.name)

        backup_connection = sqlite3.connect(result)
        try:
            row = backup_connection.execute("SELECT term FROM entries WHERE id = 1").fetchone()
        finally:
            backup_connection.close()
        self.assertEqual(row[0], "bonjour")

    def test_missing_db_file_is_not_backed_up_even_with_stale_version(self) -> None:
        db_path = self._tmp_path / "does-not-exist.db"
        connection = _connection_with_schema_version("13.0.0-linked-append-source")
        try:
            result = backup_before_pending_migration(connection, db_path)
        finally:
            connection.close()

        self.assertIsNone(result)

    def test_backup_filename_is_timestamped_and_sanitized(self) -> None:
        from datetime import datetime

        name = build_pre_migration_backup_filename(
            "13.0.0-linked-append-source", now=datetime(2026, 8, 18, 12, 0, 0)
        )
        self.assertEqual(name, "vocab-pre-13.0.0-linked-append-source-2026-08-18_120000.db")


class ImportExistingDatabaseTests(_EnvIsolationMixin):
    def setUp(self) -> None:
        super().setUp()
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        os.environ.pop("LOCALAPPDATA", None)
        os.environ[BACKUP_DIR_ENV] = str(self._tmp_path / "backups")

    def tearDown(self) -> None:
        self._tmp.cleanup()
        super().tearDown()

    def _make_sqlite_file(self, path: Path, term: str) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, term TEXT)")
            connection.execute("INSERT INTO entries (id, term) VALUES (1, ?)", (term,))
            connection.commit()
        finally:
            connection.close()

    def test_missing_source_raises_without_side_effects(self) -> None:
        destination = self._tmp_path / "vocab.db"
        with self.assertRaises(DatabaseImportError):
            import_existing_database(self._tmp_path / "missing.db", destination_path=destination)
        self.assertFalse(destination.exists())

    def test_non_sqlite_source_is_rejected(self) -> None:
        source = self._tmp_path / "not-a-database.db"
        source.write_bytes(b"not a real sqlite file")
        destination = self._tmp_path / "vocab.db"

        with self.assertRaises(DatabaseImportError):
            import_existing_database(source, destination_path=destination)
        self.assertFalse(destination.exists())

    def test_source_equal_to_destination_is_rejected(self) -> None:
        same_path = self._tmp_path / "vocab.db"
        self._make_sqlite_file(same_path, "existing")

        with self.assertRaises(DatabaseImportError):
            import_existing_database(same_path, destination_path=same_path)

    def test_import_into_empty_destination_copies_without_backup(self) -> None:
        source = self._tmp_path / "incoming.db"
        self._make_sqlite_file(source, "bonjour")
        destination = self._tmp_path / "dest" / "vocab.db"

        result = import_existing_database(source, destination_path=destination)

        self.assertIsNone(result["backup_path"])
        self.assertFalse(result["destination_backed_up"])
        self.assertTrue(destination.exists())
        connection = sqlite3.connect(destination)
        try:
            row = connection.execute("SELECT term FROM entries WHERE id = 1").fetchone()
        finally:
            connection.close()
        self.assertEqual(row[0], "bonjour")
        # Source must remain untouched.
        source_connection = sqlite3.connect(source)
        try:
            source_row = source_connection.execute("SELECT term FROM entries WHERE id = 1").fetchone()
        finally:
            source_connection.close()
        self.assertEqual(source_row[0], "bonjour")

    def test_import_over_existing_destination_backs_it_up_first(self) -> None:
        source = self._tmp_path / "incoming.db"
        self._make_sqlite_file(source, "new-data")
        destination = self._tmp_path / "vocab.db"
        self._make_sqlite_file(destination, "old-data")

        result = import_existing_database(source, destination_path=destination)

        self.assertTrue(result["destination_backed_up"])
        backup_path = result["backup_path"]
        assert backup_path is not None
        self.assertTrue(backup_path.exists())

        backup_connection = sqlite3.connect(backup_path)
        try:
            backup_row = backup_connection.execute("SELECT term FROM entries WHERE id = 1").fetchone()
        finally:
            backup_connection.close()
        self.assertEqual(backup_row[0], "old-data")

        destination_connection = sqlite3.connect(destination)
        try:
            destination_row = destination_connection.execute("SELECT term FROM entries WHERE id = 1").fetchone()
        finally:
            destination_connection.close()
        self.assertEqual(destination_row[0], "new-data")


if __name__ == "__main__":
    unittest.main()

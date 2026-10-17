from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


APP_NAME = "Vocabulary App"
APP_SLUG = "vocabulary_app"
APP_VERSION = "1.1.0"
DATABASE_PATH_ENV = "VOCAB_APP_DB_PATH"
BACKUP_DIR_ENV = "VOCAB_APP_BACKUP_DIR"
AUDIO_CACHE_PATH_ENV = "VOCAB_APP_AUDIO_CACHE_DIR"
APP_PREFERENCES_PATH_ENV = "VOCAB_APP_PREFERENCES_PATH"
DATA_ROOT_POINTER_NAME = "data-root.json"
_bound_guarded_database: Path | None = None


class DataRootError(RuntimeError):
    """A selected data root cannot be used without risking a blank database."""


@dataclass(frozen=True)
class DataPaths:
    data_root: Path
    database: Path
    backups: Path
    audio_cache: Path
    preferences: Path
    relocated: bool
    guarded_database: bool


_bound_relocated_paths: DataPaths | None = None


def _data_root_error(detail: str) -> DataRootError:
    return DataRootError(
        f"The selected Vocabulary App data folder is unavailable: {detail}. "
        "Reconnect the original drive or restore the data folder and its "
        "data-root.json pointer, then restart. No new database was created."
    )


@lru_cache(maxsize=16)
def _validate_relocated_database(database: Path) -> None:
    """Check a selected database once per process, before any writable open."""
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        result = connection.execute("PRAGMA quick_check").fetchone()
        if result is None or result[0] != "ok":
            raise ValueError("selected database failed SQLite quick_check")
        entries = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'entries'"
        ).fetchone()
        if entries is None:
            raise ValueError("selected database has no Entries table")
        metadata = dict(connection.execute(
            "SELECT key, value FROM app_metadata "
            "WHERE key IN ('schema_version', 'app_data_version')"
        ))
        if not metadata.get("schema_version") or not metadata.get("app_data_version"):
            raise ValueError("selected database has no Vocabulary App identity metadata")
    with database.open("rb+"):
        pass


def _is_link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


@lru_cache(maxsize=32)
def _probe_writable_directory(path: Path) -> None:
    # An actual create/close probe catches Windows ACL failures that
    # os.access() can miss. TemporaryFile removes its own file on close.
    with tempfile.TemporaryFile(dir=path):
        pass


def _require_writable_directory(path: Path) -> None:
    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        raise ValueError(f"{path.name} is inaccessible")
    _probe_writable_directory(path)


def _configured_data_root(default_root: Path) -> Path | None:
    pointer = default_root / DATA_ROOT_POINTER_NAME
    try:
        if not pointer.exists() and not _is_link(pointer):
            return None
        if _is_link(pointer) or not pointer.is_file():
            raise ValueError("the location pointer is not a regular file")
        if pointer.stat().st_size > 4096:
            raise ValueError("location pointer is too large")
        raw = json.loads(pointer.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"version", "data_root"}:
            raise ValueError("location pointer has an invalid format")
        if type(raw["version"]) is not int or raw["version"] != 1:
            raise ValueError("location pointer has an unsupported version")
        value = raw["data_root"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("location pointer has no folder")
        root = Path(value)
        if not root.is_absolute():
            raise ValueError("location pointer must name an absolute folder")
        if _is_link(root):
            raise ValueError("selected folder is a link")
        if not root.is_dir():
            raise ValueError("selected folder does not exist")
        root = root.resolve(strict=True)
        database = root / "vocab.db"
        if _is_link(database) or not database.is_file():
            raise ValueError("selected folder has no existing regular vocab.db")
        if not os.access(database, os.R_OK | os.W_OK):
            raise ValueError("selected database is inaccessible")
        _validate_relocated_database(database)
        _require_writable_directory(root)
        for name in ("backups", "audio-cache"):
            child = root / name
            if _is_link(child) or (child.exists() and not child.is_dir()):
                raise ValueError(f"{name} is not a regular folder")
            if child.exists():
                _require_writable_directory(child)
        preferences = root / "preferences.json"
        if _is_link(preferences) or (preferences.exists() and not preferences.is_file()):
            raise ValueError("preferences.json is not a regular file")
        if preferences.exists():
            with preferences.open("rb+"):
                pass
        return root
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, sqlite3.Error) as error:
        raise _data_root_error(str(error)) from error


def resolve_data_paths() -> DataPaths:
    """Resolve all data components before opening SQLite or preferences.

    Four explicit environment overrides retain their existing per-component
    precedence. A complete four-path override can bypass an unavailable
    pointer for advanced recovery; a partial override cannot silently mix
    the remaining components with a missing selected root.
    """
    overrides = {
        DATABASE_PATH_ENV: os.environ.get(DATABASE_PATH_ENV, "").strip(),
        BACKUP_DIR_ENV: os.environ.get(BACKUP_DIR_ENV, "").strip(),
        AUDIO_CACHE_PATH_ENV: os.environ.get(AUDIO_CACHE_PATH_ENV, "").strip(),
        APP_PREFERENCES_PATH_ENV: os.environ.get(APP_PREFERENCES_PATH_ENV, "").strip(),
    }
    default_root = get_default_data_dir()
    complete_override = all(overrides.values())
    pointer = default_root / DATA_ROOT_POINTER_NAME
    try:
        pointer_present = pointer.exists() or _is_link(pointer)
    except OSError as error:
        raise _data_root_error(str(error)) from error
    selected_root = None if complete_override else _configured_data_root(default_root)
    if _bound_relocated_paths is not None and selected_root != _bound_relocated_paths.data_root:
        raise _data_root_error("the location pointer changed while the app was open")
    root = selected_root or default_root
    database = (
        Path(overrides[DATABASE_PATH_ENV]).expanduser()
        if overrides[DATABASE_PATH_ENV] else root / "vocab.db"
    ).resolve()
    guarded_database = (selected_root is not None and not overrides[DATABASE_PATH_ENV]) or (
        complete_override and pointer_present
    )
    if complete_override and pointer_present:
        try:
            if _is_link(database) or not database.is_file():
                raise ValueError("recovery override has no existing regular database")
            _validate_relocated_database(database)
        except (OSError, ValueError, sqlite3.Error) as error:
            raise _data_root_error(str(error)) from error
    if _bound_guarded_database is not None and (
        not guarded_database or database != _bound_guarded_database
    ):
        raise _data_root_error("the protected database path changed while the app was open")
    local_app_data = bool(os.environ.get("LOCALAPPDATA", "").strip())
    legacy_audio = (
        default_root / "audio-cache"
        if local_app_data else Path.home() / ".cache" / APP_SLUG / "audio-cache"
    )
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if local_app_data:
        legacy_preferences = default_root / "preferences.json"
    elif xdg_config:
        legacy_preferences = Path(xdg_config) / APP_SLUG / "preferences.json"
    else:
        legacy_preferences = Path.home() / ".config" / APP_SLUG / "preferences.json"
    backup_path = (
        Path(overrides[BACKUP_DIR_ENV]).expanduser()
        if overrides[BACKUP_DIR_ENV] else root / "backups"
    )
    audio_path = (
        Path(overrides[AUDIO_CACHE_PATH_ENV]).expanduser()
        if overrides[AUDIO_CACHE_PATH_ENV]
        else root / "audio-cache" if selected_root else legacy_audio
    )
    preferences_path = (
        Path(overrides[APP_PREFERENCES_PATH_ENV]).expanduser()
        if overrides[APP_PREFERENCES_PATH_ENV]
        else root / "preferences.json" if selected_root else legacy_preferences
    )
    paths = DataPaths(
        data_root=root.resolve(),
        database=database,
        backups=backup_path.resolve(),
        audio_cache=audio_path.resolve(),
        preferences=preferences_path.resolve(),
        relocated=selected_root is not None,
        guarded_database=guarded_database,
    )
    if _bound_relocated_paths is not None and paths != _bound_relocated_paths:
        raise _data_root_error("data paths changed while the app was open")
    return paths


def bind_startup_data_paths() -> DataPaths:
    """Pin a relocated root when the database module starts this process."""
    global _bound_relocated_paths, _bound_guarded_database
    paths = resolve_data_paths()
    if paths.relocated:
        _bound_relocated_paths = paths
    if paths.guarded_database:
        _bound_guarded_database = paths.database
    return paths


def get_project_root() -> Path:
    """The application's own installed/checked-out root -- for
    read-only, application-owned assets bundled with the app (icon,
    PowerShell scripts) only, never for per-user data (see
    get_default_data_dir()). Resolves to ``sys._MEIPASS`` (where
    PyInstaller actually places bundled ``datas``) when frozen -- NOT
    ``sys.executable``'s directory, which is one level too shallow
    under PyInstaller's default onedir layout: bundled data lands in an
    ``_internal\\`` subfolder beside the ``.exe``, not beside it
    directly (confirmed against a real PyInstaller 6.22 onedir build).
    A frozen module's ``__file__`` does not sit inside a real ``src/``
    folder on disk the way it does running from source, hence the
    separate branch at all."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return Path(__file__).resolve().parent.parent


def get_default_data_dir() -> Path:
    """Per-user application-data root for durable user data (database,
    backups) -- the frozen ``%LOCALAPPDATA%\\vocabulary_app\\`` root on
    Windows (falls back to XDG data-home semantics off Windows), matching
    the pattern ``get_audio_cache_dir()``/``get_app_preferences_path()``
    already establish. Never inside the repository/install tree -- see
    docs/packaging/M20_RELEASE_CONTRACT.md §§ 2.2, 2.6."""
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_data:
        return Path(local_data) / APP_SLUG
    xdg_data = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data:
        return Path(xdg_data) / APP_SLUG
    return Path.home() / ".local" / "share" / APP_SLUG


def get_default_db_path() -> Path:
    return get_default_data_dir() / "vocab.db"


def get_database_path() -> Path:
    return resolve_data_paths().database


def get_backup_dir() -> Path:
    return resolve_data_paths().backups


def get_audio_cache_dir() -> Path:
    return resolve_data_paths().audio_cache


def get_app_preferences_path() -> Path:
    """Persistent per-user desktop preference location (Appearance, Accent).

    Unlike ``get_audio_cache_dir()``, this must survive routine cache
    cleanup: preferences are durable presentation state, not rebuildable
    data. The non-Windows fallback therefore uses XDG *config* semantics
    (``$XDG_CONFIG_HOME`` or ``~/.config``), never a cache directory. See
    docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md §§ 11-12.
    """
    return resolve_data_paths().preferences


def get_app_icon_path() -> Path:
    """Repository-owned application icon (used by the desktop launcher
    shortcut and the PySide6 application/window icon). Not a per-user
    path -- this is a tracked repository asset, resolved relative to the
    project root like any other bundled resource."""
    return get_project_root() / "assets" / "icons" / "vocabulary_app.ico"


def get_app_storage_summary() -> dict:
    paths = resolve_data_paths()
    database_path = paths.database
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "database_path": database_path,
        "data_directory": database_path.parent,
        "backup_directory": paths.backups,
        "audio_cache_directory": paths.audio_cache,
        "audio_cache_path_source": (
            "environment override"
            if os.environ.get(AUDIO_CACHE_PATH_ENV, "").strip()
            else "relocated data root" if paths.relocated else "platform local app data"
        ),
        "path_source": (
            "environment override"
            if os.environ.get(DATABASE_PATH_ENV, "").strip()
            else "relocated data root" if paths.relocated else "project default"
        ),
        "database_exists": database_path.is_file(),
        "local_first": True,
    }

from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "Vocabulary App"
APP_SLUG = "vocabulary_app"
APP_VERSION = "0.11.3"
DATABASE_PATH_ENV = "VOCAB_APP_DB_PATH"
BACKUP_DIR_ENV = "VOCAB_APP_BACKUP_DIR"
AUDIO_CACHE_PATH_ENV = "VOCAB_APP_AUDIO_CACHE_DIR"
APP_PREFERENCES_PATH_ENV = "VOCAB_APP_PREFERENCES_PATH"


def get_project_root() -> Path:
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
    override = os.environ.get(DATABASE_PATH_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return get_default_db_path().resolve()


def get_backup_dir() -> Path:
    override = os.environ.get(BACKUP_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (get_default_data_dir() / "backups").resolve()


def get_audio_cache_dir() -> Path:
    override = os.environ.get(AUDIO_CACHE_PATH_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_data:
        return (Path(local_data) / APP_SLUG / "audio-cache").resolve()
    return (Path.home() / ".cache" / APP_SLUG / "audio-cache").resolve()


def get_app_preferences_path() -> Path:
    """Persistent per-user desktop preference location (Appearance, Accent).

    Unlike ``get_audio_cache_dir()``, this must survive routine cache
    cleanup: preferences are durable presentation state, not rebuildable
    data. The non-Windows fallback therefore uses XDG *config* semantics
    (``$XDG_CONFIG_HOME`` or ``~/.config``), never a cache directory. See
    docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md §§ 11-12.
    """
    override = os.environ.get(APP_PREFERENCES_PATH_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_data:
        return (Path(local_data) / APP_SLUG / "preferences.json").resolve()
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg_config:
        return (Path(xdg_config) / APP_SLUG / "preferences.json").resolve()
    return (Path.home() / ".config" / APP_SLUG / "preferences.json").resolve()


def get_app_icon_path() -> Path:
    """Repository-owned application icon (used by the desktop launcher
    shortcut and the PySide6 application/window icon). Not a per-user
    path -- this is a tracked repository asset, resolved relative to the
    project root like any other bundled resource."""
    return get_project_root() / "assets" / "icons" / "vocabulary_app.ico"


def get_app_storage_summary() -> dict:
    database_path = get_database_path()
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "database_path": database_path,
        "data_directory": database_path.parent,
        "backup_directory": get_backup_dir().resolve(),
        "audio_cache_directory": get_audio_cache_dir(),
        "audio_cache_path_source": (
            "environment override"
            if os.environ.get(AUDIO_CACHE_PATH_ENV, "").strip()
            else "platform local app data"
        ),
        "path_source": (
            "environment override"
            if os.environ.get(DATABASE_PATH_ENV, "").strip()
            else "project default"
        ),
        "database_exists": database_path.is_file(),
        "local_first": True,
    }

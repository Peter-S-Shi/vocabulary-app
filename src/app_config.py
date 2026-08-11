from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "Vocabulary App"
APP_SLUG = "vocabulary_app"
APP_VERSION = "0.11.3"
DATABASE_PATH_ENV = "VOCAB_APP_DB_PATH"


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_default_data_dir() -> Path:
    return get_project_root() / "data"


def get_default_db_path() -> Path:
    return get_default_data_dir() / "vocab.db"


def get_database_path() -> Path:
    override = os.environ.get(DATABASE_PATH_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return get_default_db_path().resolve()


def get_backup_dir() -> Path:
    return get_project_root() / "backups"


def get_app_storage_summary() -> dict:
    database_path = get_database_path()
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "database_path": database_path,
        "data_directory": database_path.parent,
        "backup_directory": get_backup_dir().resolve(),
        "path_source": (
            "environment override"
            if os.environ.get(DATABASE_PATH_ENV, "").strip()
            else "project default"
        ),
        "database_exists": database_path.is_file(),
        "local_first": True,
    }

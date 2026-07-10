from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
import sqlite3


BASELINE_SCHEMA_VERSION = "10.6.0-baseline"
APP_DATA_VERSION = "10.6"

METADATA_KEYS = {
    "schema_version",
    "app_data_version",
    "last_migration_at",
}

DEFAULT_FEATURE_FLAGS = {
    "feature.dictionary_assistance": False,
    "feature.pronunciation_assistance": False,
    "feature.ai_assistance": False,
    "feature.advanced_import_assistance": False,
}

MigrationFunction = Callable[[sqlite3.Connection], None]


MIGRATIONS: list[dict[str, str | MigrationFunction]] = [
    # Future additive migrations should follow this shape:
    # {
    #     "from": "10.6.0-baseline",
    #     "to": "10.7.0",
    #     "name": "example_future_migration",
    #     "function": migration_function,
    # }
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_app_metadata_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def get_metadata(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    ensure_app_metadata_table(conn)
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return default
    return row["value"] if isinstance(row, sqlite3.Row) else row[0]


def set_metadata(conn: sqlite3.Connection, key: str, value: str) -> None:
    ensure_app_metadata_table(conn)
    conn.execute(
        """
        INSERT INTO app_metadata (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value, _utc_now()),
    )


def _set_metadata_if_missing(conn: sqlite3.Connection, key: str, value: str) -> bool:
    if get_metadata(conn, key) is not None:
        return False
    set_metadata(conn, key, value)
    return True


def initialize_app_metadata(conn: sqlite3.Connection) -> list[str]:
    ensure_app_metadata_table(conn)
    initialized_keys = []

    if _set_metadata_if_missing(conn, "schema_version", BASELINE_SCHEMA_VERSION):
        initialized_keys.append("schema_version")
    if _set_metadata_if_missing(conn, "app_data_version", APP_DATA_VERSION):
        initialized_keys.append("app_data_version")
    if _set_metadata_if_missing(conn, "last_migration_at", _utc_now()):
        initialized_keys.append("last_migration_at")

    for feature_key, enabled in DEFAULT_FEATURE_FLAGS.items():
        if _set_metadata_if_missing(conn, feature_key, "enabled" if enabled else "disabled"):
            initialized_keys.append(feature_key)

    return initialized_keys


def get_schema_version(conn: sqlite3.Connection) -> str:
    return get_metadata(conn, "schema_version", BASELINE_SCHEMA_VERSION) or BASELINE_SCHEMA_VERSION


def set_schema_version(conn: sqlite3.Connection, version: str) -> None:
    set_metadata(conn, "schema_version", version)


def get_feature_flag(conn: sqlite3.Connection, feature_key: str, default: bool = False) -> bool:
    value = get_metadata(conn, feature_key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "enabled", "on"}


def set_feature_flag(conn: sqlite3.Connection, feature_key: str, enabled: bool) -> None:
    set_metadata(conn, feature_key, "enabled" if enabled else "disabled")


def run_migrations(conn: sqlite3.Connection) -> list[str]:
    """Run pending additive migrations and return their human-readable names."""
    initialize_app_metadata(conn)

    applied_migrations = []
    current_version = get_schema_version(conn)

    for migration in MIGRATIONS:
        if migration["from"] != current_version:
            continue

        migration_function = migration["function"]
        if not callable(migration_function):
            raise TypeError(f"Migration {migration['name']} does not have a callable function.")

        migration_function(conn)
        set_schema_version(conn, str(migration["to"]))
        set_metadata(conn, "last_migration_at", _utc_now())
        applied_migrations.append(str(migration["name"]))
        current_version = str(migration["to"])

    return applied_migrations


def get_compatibility_status(conn: sqlite3.Connection) -> dict:
    initialize_app_metadata(conn)
    feature_flags = {
        feature_key: get_feature_flag(conn, feature_key)
        for feature_key in DEFAULT_FEATURE_FLAGS
    }
    return {
        "schema_version": get_schema_version(conn),
        "app_data_version": get_metadata(conn, "app_data_version", APP_DATA_VERSION),
        "last_migration_at": get_metadata(conn, "last_migration_at", ""),
        "feature_flags": feature_flags,
    }

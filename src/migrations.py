from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
import sqlite3


BASELINE_SCHEMA_VERSION = "10.6.0-baseline"
CARD_HISTORY_SCHEMA_VERSION = "11.3.0-card-history"
CURRENT_SCHEMA_VERSION = "11.3.1-quiz-log-history"
APP_DATA_VERSION = "11.3"

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


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"] if isinstance(row, sqlite3.Row) else row[1]) for row in rows}


def migrate_to_m11_3_card_history(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            card_number INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            retired_at TEXT,
            FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_active_collection_number
        ON cards(collection_id, card_number)
        WHERE is_active = 1
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cards_collection_active ON cards(collection_id, is_active)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS card_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            revision_number INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            change_reason TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE,
            UNIQUE(card_id, revision_number)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_card_revisions_card ON card_revisions(card_id, revision_number)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS card_revision_entries (
            revision_id INTEGER NOT NULL,
            entry_id INTEGER NOT NULL,
            position_within_card INTEGER NOT NULL,
            PRIMARY KEY(revision_id, position_within_card),
            UNIQUE(revision_id, entry_id),
            FOREIGN KEY(revision_id) REFERENCES card_revisions(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_card_revision_entries_entry ON card_revision_entries(entry_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entry_change_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            changed_at TEXT NOT NULL,
            changes_json TEXT NOT NULL,
            change_source TEXT NOT NULL DEFAULT 'app_edit'
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_entry_change_events_entry ON entry_change_events(entry_id, changed_at)"
    )

    quiz_columns = _table_columns(conn, "quiz_sessions")
    if "card_id" not in quiz_columns:
        conn.execute("ALTER TABLE quiz_sessions ADD COLUMN card_id INTEGER")
    if "card_revision_id" not in quiz_columns:
        conn.execute("ALTER TABLE quiz_sessions ADD COLUMN card_revision_id INTEGER")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quiz_sessions_card_identity ON quiz_sessions(card_id, card_revision_id)"
    )

    from src.card_history import reconcile_collection_card_history

    collection_rows = conn.execute("SELECT id FROM collections ORDER BY id").fetchall()
    for row in collection_rows:
        collection_id = int(row["id"] if isinstance(row, sqlite3.Row) else row[0])
        reconcile_collection_card_history(
            conn,
            collection_id,
            change_reason="m11.3_migration_baseline",
            migrate_legacy_names=True,
        )
    set_metadata(conn, "app_data_version", APP_DATA_VERSION)


def _quiz_item_logs_has_entry_foreign_key(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("PRAGMA foreign_key_list(quiz_item_logs)").fetchall()
    for row in rows:
        source_column = row["from"] if isinstance(row, sqlite3.Row) else row[3]
        target_table = row["table"] if isinstance(row, sqlite3.Row) else row[2]
        if source_column == "entry_id" and target_table == "entries":
            return True
    return False


def migrate_quiz_logs_to_preserved_entry_identity(conn: sqlite3.Connection) -> None:
    if _quiz_item_logs_has_entry_foreign_key(conn):
        conn.execute(
            """
            CREATE TABLE quiz_item_logs_m11_3_preserved (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                entry_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                expected_answer TEXT NOT NULL,
                user_answer TEXT,
                is_correct INTEGER,
                answered_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            INSERT INTO quiz_item_logs_m11_3_preserved (
                id, session_id, entry_id, prompt, expected_answer,
                user_answer, is_correct, answered_at
            )
            SELECT
                id, session_id, entry_id, prompt, expected_answer,
                user_answer, is_correct, answered_at
            FROM quiz_item_logs
            ORDER BY id
            """
        )
        conn.execute("DROP TABLE quiz_item_logs")
        conn.execute(
            "ALTER TABLE quiz_item_logs_m11_3_preserved RENAME TO quiz_item_logs"
        )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quiz_item_logs_session_id ON quiz_item_logs(session_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quiz_item_logs_entry_id ON quiz_item_logs(entry_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quiz_item_logs_answered_at ON quiz_item_logs(answered_at)"
    )


MIGRATIONS: list[dict[str, str | MigrationFunction]] = [
    {
        "from": BASELINE_SCHEMA_VERSION,
        "to": CARD_HISTORY_SCHEMA_VERSION,
        "name": "m11.3_stable_card_identity_and_entry_history",
        "function": migrate_to_m11_3_card_history,
    },
    {
        "from": CARD_HISTORY_SCHEMA_VERSION,
        "to": CURRENT_SCHEMA_VERSION,
        "name": "m11.3_preserve_quiz_logs_after_entry_delete",
        "function": migrate_quiz_logs_to_preserved_entry_identity,
    },
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

        conn.execute("SAVEPOINT app_schema_migration")
        try:
            migration_function(conn)
            set_schema_version(conn, str(migration["to"]))
            set_metadata(conn, "last_migration_at", _utc_now())
            conn.execute("RELEASE SAVEPOINT app_schema_migration")
        except Exception:
            conn.execute("ROLLBACK TO SAVEPOINT app_schema_migration")
            conn.execute("RELEASE SAVEPOINT app_schema_migration")
            raise
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

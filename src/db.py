from pathlib import Path
import sqlite3

from src.app_config import get_database_path
from src.migrations import run_migrations


DB_PATH = get_database_path()


CREATE_ENTRIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL,
    explanation_language TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    term TEXT NOT NULL,
    meaning TEXT NOT NULL,
    example TEXT,
    notes TEXT,
    tags TEXT,
    source TEXT,
    status TEXT DEFAULT 'new',
    review_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    current_interval_days INTEGER DEFAULT 0,
    next_due_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_COLLECTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    card_size INTEGER NOT NULL DEFAULT 8,
    is_system INTEGER NOT NULL DEFAULT 0,
    system_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_ENTRY_COLLECTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entry_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    collection_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    FOREIGN KEY(entry_id) REFERENCES entries(id) ON DELETE CASCADE,
    FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    UNIQUE(entry_id, collection_id)
);
"""

CREATE_CARD_REVIEW_STATES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS card_review_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    card_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    review_count INTEGER NOT NULL DEFAULT 0,
    current_interval_days INTEGER NOT NULL DEFAULT 0,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    next_due_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    UNIQUE(collection_id, card_number)
);
"""

CREATE_CARD_REVIEW_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS card_review_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    card_number INTEGER NOT NULL,
    reviewed_at TEXT NOT NULL,
    rating TEXT NOT NULL,
    previous_interval_days INTEGER NOT NULL,
    new_interval_days INTEGER NOT NULL,
    previous_due_at TEXT,
    next_due_at TEXT,
    entry_count INTEGER NOT NULL,
    FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
);
"""

CREATE_COLLECTION_CARD_METADATA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS collection_card_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    card_number INTEGER NOT NULL,
    name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    UNIQUE(collection_id, card_number)
);
"""

CREATE_QUIZ_SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    card_number INTEGER NOT NULL,
    quiz_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    total_items INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    card_id INTEGER,
    card_revision_id INTEGER,
    FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
);
"""

CREATE_QUIZ_ITEM_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS quiz_item_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    entry_id INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    user_answer TEXT,
    is_correct INTEGER,
    answered_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE
);
"""


CREATE_ENTRY_TEMPLATES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entry_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    language TEXT,
    template_type TEXT NOT NULL DEFAULT 'custom',
    is_system INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_ENTRY_TEMPLATE_FIELDS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entry_template_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    field_key TEXT NOT NULL,
    field_label TEXT NOT NULL,
    field_type TEXT NOT NULL DEFAULT 'text',
    required INTEGER NOT NULL DEFAULT 0,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(template_id) REFERENCES entry_templates(id) ON DELETE CASCADE,
    UNIQUE(template_id, field_key)
);
"""

CREATE_ENTRY_FIELD_VALUES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entry_field_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    field_id INTEGER NOT NULL,
    field_value TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(entry_id) REFERENCES entries(id) ON DELETE CASCADE,
    FOREIGN KEY(field_id) REFERENCES entry_template_fields(id) ON DELETE CASCADE,
    UNIQUE(entry_id, field_id)
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(name);",
    "CREATE INDEX IF NOT EXISTS idx_collections_system_type ON collections(system_type);",
    "CREATE INDEX IF NOT EXISTS idx_entry_collections_entry_id ON entry_collections(entry_id);",
    "CREATE INDEX IF NOT EXISTS idx_entry_collections_collection_id ON entry_collections(collection_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_entry_collections_unique ON entry_collections(entry_id, collection_id);",
    "CREATE INDEX IF NOT EXISTS idx_entry_collections_collection_position ON entry_collections(collection_id, position);",
    "CREATE INDEX IF NOT EXISTS idx_card_review_states_collection_card ON card_review_states(collection_id, card_number);",
    "CREATE INDEX IF NOT EXISTS idx_card_review_states_next_due_at ON card_review_states(next_due_at);",
    "CREATE INDEX IF NOT EXISTS idx_card_review_logs_collection_card ON card_review_logs(collection_id, card_number);",
    "CREATE INDEX IF NOT EXISTS idx_card_review_logs_reviewed_at ON card_review_logs(reviewed_at);",
    "CREATE INDEX IF NOT EXISTS idx_collection_card_metadata_collection_card ON collection_card_metadata(collection_id, card_number);",
    "CREATE INDEX IF NOT EXISTS idx_collection_card_metadata_name ON collection_card_metadata(name);",
    "CREATE INDEX IF NOT EXISTS idx_quiz_sessions_collection_card ON quiz_sessions(collection_id, card_number);",
    "CREATE INDEX IF NOT EXISTS idx_quiz_sessions_started_at ON quiz_sessions(started_at);",
    "CREATE INDEX IF NOT EXISTS idx_quiz_sessions_status ON quiz_sessions(status);",
    "CREATE INDEX IF NOT EXISTS idx_quiz_item_logs_session_id ON quiz_item_logs(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_quiz_item_logs_entry_id ON quiz_item_logs(entry_id);",
    "CREATE INDEX IF NOT EXISTS idx_quiz_item_logs_answered_at ON quiz_item_logs(answered_at);",
    "CREATE INDEX IF NOT EXISTS idx_entries_template_id ON entries(template_id);",
    "CREATE INDEX IF NOT EXISTS idx_entry_templates_type ON entry_templates(template_type);",
    "CREATE INDEX IF NOT EXISTS idx_entry_template_fields_template_order ON entry_template_fields(template_id, display_order);",
    "CREATE INDEX IF NOT EXISTS idx_entry_field_values_entry_id ON entry_field_values(entry_id);",
    "CREATE INDEX IF NOT EXISTS idx_entry_field_values_field_id ON entry_field_values(field_id);",
]


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _get_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}



def _ensure_collections_system_columns(connection: sqlite3.Connection) -> None:
    columns = _get_table_columns(connection, "collections")

    if "is_system" not in columns:
        connection.execute(
            "ALTER TABLE collections ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0"
        )

    if "system_type" not in columns:
        connection.execute("ALTER TABLE collections ADD COLUMN system_type TEXT")

    connection.execute(
        """
        UPDATE collections
        SET is_system = 1,
            system_type = 'mistake_book'
        WHERE name = 'Mistake Book'
          AND (system_type IS NULL OR system_type = '')
        """
    )
    connection.execute(
        """
        UPDATE collections
        SET is_system = 1,
            system_type = 'starred'
        WHERE name = 'Starred'
          AND (system_type IS NULL OR system_type = '')
        """
    )
    connection.execute(
        """
        UPDATE collections
        SET is_system = 1,
            system_type = 'proficient_pool'
        WHERE name = 'Proficient Pool'
          AND (system_type IS NULL OR system_type = '')
        """
    )

def _ensure_quiz_session_status_column(connection: sqlite3.Connection) -> None:
    columns = _get_table_columns(connection, "quiz_sessions")

    if "status" not in columns:
        connection.execute(
            "ALTER TABLE quiz_sessions ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
        )

    connection.execute(
        """
        UPDATE quiz_sessions
        SET status = 'completed'
        WHERE completed_at IS NOT NULL
          AND status = 'active'
        """
    )


def _ensure_entries_quiz_count_columns(connection: sqlite3.Connection) -> None:
    columns = _get_table_columns(connection, "entries")

    if "correct_count" not in columns:
        connection.execute(
            "ALTER TABLE entries ADD COLUMN correct_count INTEGER DEFAULT 0"
        )

    if "wrong_count" not in columns:
        connection.execute(
            "ALTER TABLE entries ADD COLUMN wrong_count INTEGER DEFAULT 0"
        )



def _ensure_entries_template_id_column(connection: sqlite3.Connection) -> None:
    columns = _get_table_columns(connection, "entries")

    if "template_id" not in columns:
        connection.execute("ALTER TABLE entries ADD COLUMN template_id INTEGER")


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(CREATE_ENTRIES_TABLE_SQL)
        _ensure_entries_quiz_count_columns(connection)
        _ensure_entries_template_id_column(connection)
        connection.execute(CREATE_COLLECTIONS_TABLE_SQL)
        _ensure_collections_system_columns(connection)
        connection.execute(CREATE_ENTRY_COLLECTIONS_TABLE_SQL)
        connection.execute(CREATE_CARD_REVIEW_STATES_TABLE_SQL)
        connection.execute(CREATE_CARD_REVIEW_LOGS_TABLE_SQL)
        connection.execute(CREATE_COLLECTION_CARD_METADATA_TABLE_SQL)
        connection.execute(CREATE_QUIZ_SESSIONS_TABLE_SQL)
        _ensure_quiz_session_status_column(connection)
        connection.execute(CREATE_QUIZ_ITEM_LOGS_TABLE_SQL)
        connection.execute(CREATE_ENTRY_TEMPLATES_TABLE_SQL)
        connection.execute(CREATE_ENTRY_TEMPLATE_FIELDS_TABLE_SQL)
        connection.execute(CREATE_ENTRY_FIELD_VALUES_TABLE_SQL)
        for create_index_sql in CREATE_INDEXES_SQL:
            connection.execute(create_index_sql)
        run_migrations(connection)

    from src.entry_templates import init_entry_template_system

    init_entry_template_system()

from __future__ import annotations

from pathlib import Path

from src.app_config import get_default_db_path


def require_isolated_test_database(database_path: Path) -> Path:
    """Resolve and reject the production database path for fixture writes."""
    resolved_database_path = database_path.expanduser().resolve()
    if resolved_database_path == get_default_db_path().resolve():
        raise AssertionError(
            "Synthetic scheduling fixtures require an isolated test database."
        )
    return resolved_database_path

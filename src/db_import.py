from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from src.app_config import get_backup_dir, get_database_path

"""
Existing-database import (M20 Release Contract § 2.6
"Existing-database import: frozen, explicit, user-selected,
copy-with-backup"). Lets a user who already has a ``vocab.db`` (e.g. from
a previous install, a different machine, or a pre-release checkout) point
the installed app at it via an explicit, user-selected file, rather than
starting over with an empty database.

This intentionally does not reconstruct or merge database content the
way the existing backup-workbook Restore Preview would have to -- it
copies the raw SQLite file, then lets the existing, already-battle-tested
migration pipeline (``src.migrations.run_migrations`` via
``src.db.init_db``) bring its schema up to date the next time the app
opens it. No parallel DB engine, no row-level merge logic.
"""

SQLITE_HEADER = b"SQLite format 3\x00"


class DatabaseImportError(ValueError):
    """A controlled existing-database import validation/copy error."""


def _looks_like_sqlite_database(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            header = handle.read(len(SQLITE_HEADER))
    except OSError:
        return False
    return header == SQLITE_HEADER


def import_existing_database(source_path: str | Path, destination_path: str | Path | None = None) -> dict:
    """Copy ``source_path`` into the app's active database location.

    Frozen behavior:
    - the source file is never modified or deleted (copy, not move);
    - any non-empty file already at the destination is backed up first,
      under the same frozen backup location a pending-migration backup
      uses (``src.app_config.get_backup_dir()``);
    - the destination is only ever replaced after that backup succeeds.

    Raises ``DatabaseImportError`` for a missing, identical, or
    not-a-SQLite-database source -- never partially copies in that case.
    """
    source = Path(source_path).expanduser().resolve()
    destination = (
        Path(destination_path).expanduser().resolve() if destination_path is not None else get_database_path()
    )

    if not source.is_file():
        raise DatabaseImportError(f"Selected file does not exist: {source}")
    if source == destination:
        raise DatabaseImportError("Selected file is already the active database.")
    if not _looks_like_sqlite_database(source):
        raise DatabaseImportError("Selected file does not look like a SQLite database.")

    destination.parent.mkdir(parents=True, exist_ok=True)

    backup_path: Path | None = None
    if destination.exists() and destination.stat().st_size > 0:
        backup_dir = get_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_path = backup_dir / f"vocab-pre-import-{timestamp}.db"
        existing_connection = sqlite3.connect(destination)
        backup_connection = sqlite3.connect(backup_path)
        try:
            existing_connection.backup(backup_connection)
        finally:
            backup_connection.close()
            existing_connection.close()

    shutil.copy2(source, destination)

    return {
        "source_path": source,
        "destination_path": destination,
        "backup_path": backup_path,
        "destination_backed_up": backup_path is not None,
    }

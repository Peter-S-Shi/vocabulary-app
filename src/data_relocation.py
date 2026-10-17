from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from src.app_config import (
    DATA_ROOT_POINTER_NAME,
    RECOVERY_JOURNAL_NAME,
    ROOT_MARKER_NAME,
    _is_link,
    _require_writable_directory,
    _validate_relocated_database,
    get_default_data_dir,
    resolve_data_paths,
)


class RelocationError(RuntimeError):
    """Raised when data folder relocation cannot proceed safely."""


@dataclass(frozen=True)
class RelocationPlan:
    source_root: Path
    target_dir: Path
    staging_dir: Path
    marker_uuid: str


@dataclass(frozen=True)
class RelocationResult:
    success: bool
    source_root: Path
    target_root: Path
    needs_restart: bool
    detail: str


@contextmanager
def acquire_quiescence_lock(root: Path) -> Iterator[None]:
    """Acquires a cross-process lock on the data root during relocation."""
    root.mkdir(parents=True, exist_ok=True)
    lock_file = root / ".app_data.lock"
    handle = None
    try:
        handle = open(lock_file, "a+b")
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RelocationError(
                    "Another Vocabulary App process or migration is actively using this data folder."
                ) from error
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RelocationError(
                    "Another Vocabulary App process or migration is actively using this data folder."
                ) from error
        yield
    finally:
        if handle is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                handle.close()
            except OSError:
                pass


def plan_relocation(
    target_dir: Path,
    source_root: Path | None = None,
) -> RelocationPlan:
    """Preflight checks and staging plan for relocating the user data root."""
    target = Path(target_dir).resolve()
    if not target.is_absolute():
        raise RelocationError("Target folder must be an absolute path.")
    if _is_link(target):
        raise RelocationError("Target folder cannot be a symbolic link or junction.")

    source = (
        Path(source_root).resolve()
        if source_root is not None
        else resolve_data_paths().data_root
    )

    if target == source:
        raise RelocationError("Target folder is identical to the current data folder.")

    try:
        if target.is_relative_to(source):
            raise RelocationError("Target folder cannot be inside the current data folder.")
    except AttributeError:
        # Fallback for older python
        if str(target).startswith(str(source)):
            raise RelocationError("Target folder cannot be inside the current data folder.")

    try:
        if source.is_relative_to(target):
            raise RelocationError("Current data folder cannot be inside the target folder.")
    except AttributeError:
        if str(source).startswith(str(target)):
            raise RelocationError("Current data folder cannot be inside the target folder.")

    if target.exists():
        raise RelocationError("Target folder already exists and is occupied.")

    target_parent = target.parent
    if not target_parent.exists() or not target_parent.is_dir():
        raise RelocationError(f"Parent directory '{target_parent}' does not exist.")
    if _is_link(target_parent):
        raise RelocationError("Target parent directory cannot be a symbolic link or junction.")

    _require_writable_directory(target_parent)

    marker_uuid = uuid.uuid4().hex[:12]
    staging_dir = target_parent / f".vocab-stage-{marker_uuid}"
    if staging_dir.exists():
        raise RelocationError("A previous staging directory with the same name already exists.")

    return RelocationPlan(
        source_root=source,
        target_dir=target,
        staging_dir=staging_dir,
        marker_uuid=marker_uuid,
    )


def execute_relocation(
    plan: RelocationPlan,
    default_root: Path | None = None,
    progress_callback: Callable[[str, float], None] | None = None,
) -> RelocationResult:
    """Executes verified unified relocation of SQLite, backups, audio-cache and preferences."""
    def_root = (
        Path(default_root).resolve()
        if default_root is not None
        else get_default_data_dir()
    )

    if progress_callback:
        progress_callback("Locking source data folder...", 0.05)

    with acquire_quiescence_lock(plan.source_root):
        plan.staging_dir.mkdir(parents=True, exist_ok=False)
        stage_marker = plan.staging_dir / ".vocab_stage_marker.json"
        stage_marker.write_text(
            json.dumps({
                "version": 1,
                "marker_uuid": plan.marker_uuid,
                "target_dir": str(plan.target_dir),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }),
            encoding="utf-8",
        )

        try:
            source_db = plan.source_root / "vocab.db"
            if not source_db.is_file():
                raise RelocationError("Source folder has no regular vocab.db database.")

            if progress_callback:
                progress_callback("Snapshotting SQLite database...", 0.20)

            # SQLite online backup for snapshot consistency without copying live WAL/SHM
            staged_db = plan.staging_dir / "vocab.db"
            with closing(sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True)) as src_conn:
                with closing(sqlite3.connect(staged_db)) as dst_conn:
                    src_conn.backup(dst_conn)

            if progress_callback:
                progress_callback("Copying backups and cache...", 0.50)

            # Backups
            src_backups = plan.source_root / "backups"
            if src_backups.is_dir() and not _is_link(src_backups):
                shutil.copytree(src_backups, plan.staging_dir / "backups")

            # Audio cache
            src_audio = plan.source_root / "audio-cache"
            if src_audio.is_dir() and not _is_link(src_audio):
                shutil.copytree(src_audio, plan.staging_dir / "audio-cache")

            # Preferences
            src_prefs = plan.source_root / "preferences.json"
            if src_prefs.is_file() and not _is_link(src_prefs):
                shutil.copy2(src_prefs, plan.staging_dir / "preferences.json")

            if progress_callback:
                progress_callback("Verifying staged files...", 0.70)

            # Verify staged database
            _validate_relocated_database(staged_db)

            # Read actual schema_version and app_data_version from staged DB
            with closing(sqlite3.connect(staged_db.as_uri() + "?mode=ro", uri=True)) as check_conn:
                metadata = dict(check_conn.execute(
                    "SELECT key, value FROM app_metadata WHERE key IN ('schema_version', 'app_data_version')"
                ))
                schema_ver = metadata.get("schema_version", "unknown")
                app_data_ver = metadata.get("app_data_version", "unknown")

            # Verify staged preferences if present
            staged_prefs = plan.staging_dir / "preferences.json"
            if staged_prefs.exists():
                json.loads(staged_prefs.read_text(encoding="utf-8"))

            # Finalize staged DB so it has no orphaned temporary wal/shm files before promotion
            with closing(sqlite3.connect(staged_db)) as staged_conn:
                staged_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            for ext in ("-wal", "-shm"):
                aux = staged_db.with_name(staged_db.name + ext)
                if aux.exists() and aux.stat().st_size == 0:
                    try:
                        aux.unlink()
                    except OSError:
                        pass

            if progress_callback:
                progress_callback("Promoting target folder...", 0.85)

            # Remove stage marker before promoting to final target
            if stage_marker.exists():
                stage_marker.unlink()

            # Atomic promotion: sibling rename on same filesystem
            os.replace(plan.staging_dir, plan.target_dir)

            # Write root marker in target directory
            root_marker = plan.target_dir / ROOT_MARKER_NAME
            root_marker.write_text(
                json.dumps({
                    "version": 1,
                    "marker_uuid": plan.marker_uuid,
                    "source_root": str(plan.source_root),
                    "target_root": str(plan.target_dir),
                    "relocated_at": datetime.now(timezone.utc).isoformat(),
                }),
                encoding="utf-8",
            )

            if progress_callback:
                progress_callback("Updating durable journal and locator...", 0.95)

            # Update durable recovery journal
            journal_path = def_root / RECOVERY_JOURNAL_NAME
            existing_history: list[dict] = []
            next_seq = 1
            if journal_path.is_file():
                try:
                    journal_raw = json.loads(journal_path.read_text(encoding="utf-8"))
                    if isinstance(journal_raw, dict) and isinstance(journal_raw.get("history"), list):
                        existing_history = journal_raw["history"]
                        if existing_history:
                            next_seq = max(item.get("sequence", 0) for item in existing_history) + 1
                except Exception:
                    pass

            new_history_entry = {
                "sequence": next_seq,
                "committed_at": datetime.now(timezone.utc).isoformat(),
                "source_root": str(plan.source_root),
                "target_root": str(plan.target_dir),
                "schema_version": schema_ver,
                "app_data_version": app_data_ver,
                "marker_uuid": plan.marker_uuid,
            }
            existing_history.append(new_history_entry)

            journal_data = {
                "version": 1,
                "latest_committed_root": str(plan.target_dir),
                "history": existing_history,
            }

            # Atomic write journal via tempfile + replace
            with tempfile.NamedTemporaryFile("w", dir=def_root, delete=False, encoding="utf-8") as temp_j:
                temp_j.write(json.dumps(journal_data, indent=2))
                temp_j_name = temp_j.name
            os.replace(temp_j_name, journal_path)

            # Atomic write pointer via tempfile + replace
            pointer_path = def_root / DATA_ROOT_POINTER_NAME
            pointer_data = {
                "version": 1,
                "data_root": str(plan.target_dir),
            }
            with tempfile.NamedTemporaryFile("w", dir=def_root, delete=False, encoding="utf-8") as temp_p:
                temp_p.write(json.dumps(pointer_data, indent=2))
                temp_p_name = temp_p.name
            os.replace(temp_p_name, pointer_path)

            if progress_callback:
                progress_callback("Relocation complete.", 1.0)

            return RelocationResult(
                success=True,
                source_root=plan.source_root,
                target_root=plan.target_dir,
                needs_restart=True,
                detail="Relocation completed successfully. Restart required.",
            )

        except Exception as error:
            # Cleanup staging directory on error
            if plan.staging_dir.exists():
                shutil.rmtree(plan.staging_dir, ignore_errors=True)
            if isinstance(error, RelocationError):
                raise
            raise RelocationError(f"Relocation failed: {error}") from error

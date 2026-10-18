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
    _build_component_manifest,
    _is_link,
    _require_writable_directory,
    _validate_relocated_database,
    get_default_data_dir,
    resolve_data_paths,
)
from src.data_lock import acquire_data_lock, DataLockError


class RelocationError(RuntimeError):
    """Raised when data folder relocation cannot proceed safely."""


@contextmanager
def acquire_quiescence_lock(root: Path) -> Iterator[None]:
    """Acquires a cross-process exclusive lock on the data root during relocation."""
    try:
        with acquire_data_lock(root, exclusive=True):
            yield
    except DataLockError as error:
        raise RelocationError(
            "Another Vocabulary App process or migration is actively using this data folder."
        ) from error


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


def _get_tree_size_and_validate(path: Path) -> int:
    """Calculate the total size of regular files in a directory while rejecting symlinks."""
    total_size = 0
    if not path.exists():
        return 0
    if _is_link(path):
        raise RelocationError(f"Directory '{path}' is a link or junction, which is not permitted.")
    if not path.is_dir():
        raise RelocationError(f"Expected directory at '{path}', found file or special object.")
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        for d in dirs:
            dir_path = root_path / d
            if _is_link(dir_path):
                raise RelocationError(f"Subdirectory '{dir_path}' is a link or junction, which is not permitted.")
        for f in files:
            file_path = root_path / f
            if _is_link(file_path):
                raise RelocationError(f"File '{file_path}' is a link, which is not permitted.")
            total_size += file_path.stat().st_size
    return total_size


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

    # Validate source components strictly
    for child_name in ("backups", "audio-cache"):
        child = source / child_name
        if child.exists() and not child.is_dir():
            raise RelocationError(f"Source component '{child_name}' exists but is not a regular directory.")
    source_prefs = source / "preferences.json"
    if source_prefs.exists() and not source_prefs.is_file():
        raise RelocationError("Source component 'preferences.json' exists but is not a regular file.")

    # Estimate required space (db + backups + cache + preferences + 10MB safety buffer)
    required_bytes = 10 * 1024 * 1024
    source_db = source / "vocab.db"
    if source_db.is_file():
        required_bytes += source_db.stat().st_size
    for child_name in ("backups", "audio-cache"):
        child = source / child_name
        if child.is_dir():
            required_bytes += _get_tree_size_and_validate(child)
    if source_prefs.is_file():
        required_bytes += source_prefs.stat().st_size

    try:
        disk_stat = shutil.disk_usage(target_parent)
        if disk_stat.free < required_bytes:
            raise RelocationError(
                f"Insufficient disk space on destination: {disk_stat.free // (1024*1024)} MB available, "
                f"at least {required_bytes // (1024*1024)} MB required."
            )
    except OSError as error:
        raise RelocationError(f"Could not verify destination disk space: {error}") from error

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


def _atomic_promote_no_clobber(staging_dir: Path, target_dir: Path) -> None:
    """Promotes staging_dir to target_dir atomically without overwriting any existing target."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        MOVEFILE_WRITE_THROUGH = 0x00000008
        success = kernel32.MoveFileExW(
            str(staging_dir),
            str(target_dir),
            wintypes.DWORD(MOVEFILE_WRITE_THROUGH),
        )
        if not success:
            err = kernel32.GetLastError()
            ERROR_ALREADY_EXISTS = 183
            ERROR_FILE_EXISTS = 80
            if err in (ERROR_ALREADY_EXISTS, ERROR_FILE_EXISTS):
                raise RelocationError(
                    f"Destination folder '{target_dir}' already exists or was occupied during relocation."
                )
            raise RelocationError(f"Atomic promotion failed with Windows error code {err}.")
    else:
        if target_dir.exists() or _is_link(target_dir):
            raise RelocationError(
                f"Destination folder '{target_dir}' already exists or was occupied during relocation."
            )
        os.rename(staging_dir, target_dir)


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

    journal_in_switching = False
    try:
        with acquire_data_lock(plan.source_root, exclusive=True):
            # Check target again right under lock
            if plan.target_dir.exists() or _is_link(plan.target_dir):
                raise RelocationError("Target folder already exists and is occupied.")

            source_db = plan.source_root / "vocab.db"
            if not source_db.is_file() or _is_link(source_db):
                raise RelocationError("Source folder has no regular vocab.db database.")

            source_manifest = _build_component_manifest(plan.source_root)

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
            elif src_backups.exists() or _is_link(src_backups):
                raise RelocationError("Source backups component is not a regular directory.")

            # Audio cache
            src_audio = plan.source_root / "audio-cache"
            if src_audio.is_dir() and not _is_link(src_audio):
                shutil.copytree(src_audio, plan.staging_dir / "audio-cache")
            elif src_audio.exists() or _is_link(src_audio):
                raise RelocationError("Source audio-cache component is not a regular directory.")

            # Preferences
            src_prefs = plan.source_root / "preferences.json"
            if src_prefs.is_file() and not _is_link(src_prefs):
                shutil.copy2(src_prefs, plan.staging_dir / "preferences.json")
            elif src_prefs.exists() or _is_link(src_prefs):
                raise RelocationError("Source preferences.json component is not a regular file.")

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

            # Build and verify 4-component manifest of staged files against source
            staged_manifest = _build_component_manifest(plan.staging_dir)
            for comp_key in ("preferences", "backups", "audio_cache"):
                if staged_manifest[comp_key] != source_manifest[comp_key]:
                    raise RelocationError(
                        f"Staged component '{comp_key}' failed completeness verification against source."
                    )

            # Pre-write root marker inside staging directory BEFORE promotion.
            # This guarantees that both unpromoted staging and promoted target carry full provenance + manifest.
            root_marker = plan.staging_dir / ROOT_MARKER_NAME
            root_marker.write_text(
                json.dumps({
                    "version": 1,
                    "marker_uuid": plan.marker_uuid,
                    "source_root": str(plan.source_root),
                    "target_root": str(plan.target_dir),
                    "schema_version": schema_ver,
                    "app_data_version": app_data_ver,
                    "relocated_at": datetime.now(timezone.utc).isoformat(),
                    "components": staged_manifest,
                }),
                encoding="utf-8",
            )

            # Remove stage marker before promoting to final target
            if stage_marker.exists():
                stage_marker.unlink()

            if progress_callback:
                progress_callback("Recording pending migration transition...", 0.80)

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

            journal_existed_before = journal_path.is_file()
            prev_journal_content = journal_path.read_text(encoding="utf-8") if journal_existed_before else None

            # Journal state transition: SWITCHING
            switching_journal_data = {
                "version": 1,
                "status": "SWITCHING",
                "pending_target_root": str(plan.target_dir),
                "pending_staging_dir": str(plan.staging_dir),
                "pending_marker_uuid": plan.marker_uuid,
                "pending_schema_version": schema_ver,
                "pending_app_data_version": app_data_ver,
                "pending_components": staged_manifest,
                "had_prior_journal": journal_existed_before,
                "latest_committed_root": str(plan.source_root),
                "history": existing_history,
            }
            with tempfile.NamedTemporaryFile("w", dir=def_root, delete=False, encoding="utf-8") as temp_j:
                temp_j.write(json.dumps(switching_journal_data, indent=2))
                temp_j.flush()
                os.fsync(temp_j.fileno())
                temp_j_name = temp_j.name
            os.replace(temp_j_name, journal_path)
            journal_in_switching = True

            if progress_callback:
                progress_callback("Promoting target folder...", 0.88)

            try:
                _atomic_promote_no_clobber(plan.staging_dir, plan.target_dir)
            except Exception as promote_err:
                # Promotion failed! Restore previous journal state or remove journal if it didn't exist before
                if journal_existed_before and prev_journal_content is not None:
                    with tempfile.NamedTemporaryFile("w", dir=def_root, delete=False, encoding="utf-8") as temp_rb:
                        temp_rb.write(prev_journal_content)
                        temp_rb.flush()
                        os.fsync(temp_rb.fileno())
                        temp_rb_name = temp_rb.name
                    os.replace(temp_rb_name, journal_path)
                    journal_in_switching = False
                else:
                    try:
                        journal_path.unlink(missing_ok=True)
                        journal_in_switching = False
                    except OSError:
                        pass
                raise promote_err

            if progress_callback:
                progress_callback("Updating durable journal and locator...", 0.95)

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

            committed_journal_data = {
                "version": 1,
                "status": "COMMITTED",
                "latest_committed_root": str(plan.target_dir),
                "history": existing_history,
            }

            # Atomic write pointer via tempfile + flush + fsync + replace
            pointer_path = def_root / DATA_ROOT_POINTER_NAME
            pointer_data = {
                "version": 1,
                "data_root": str(plan.target_dir),
            }
            with tempfile.NamedTemporaryFile("w", dir=def_root, delete=False, encoding="utf-8") as temp_p:
                temp_p.write(json.dumps(pointer_data, indent=2))
                temp_p.flush()
                os.fsync(temp_p.fileno())
                temp_p_name = temp_p.name
            os.replace(temp_p_name, pointer_path)

            # Atomic write journal via tempfile + flush + fsync + replace
            with tempfile.NamedTemporaryFile("w", dir=def_root, delete=False, encoding="utf-8") as temp_j:
                temp_j.write(json.dumps(committed_journal_data, indent=2))
                temp_j.flush()
                os.fsync(temp_j.fileno())
                temp_j_name = temp_j.name
            os.replace(temp_j_name, journal_path)
            journal_in_switching = False

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
        # Cleanup staging directory on error only if journal is not left in SWITCHING state
        if not journal_in_switching and plan.staging_dir.exists():
            shutil.rmtree(plan.staging_dir, ignore_errors=True)
        if isinstance(error, RelocationError):
            raise
        if isinstance(error, DataLockError):
            raise RelocationError(
                f"Cannot start relocation: another Vocabulary App process or writer is actively using this data folder: {error}"
            ) from error
        raise RelocationError(f"Relocation failed: {error}") from error


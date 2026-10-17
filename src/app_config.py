from __future__ import annotations

import hashlib
import json
import os
import shutil
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
RECOVERY_JOURNAL_NAME = "migration-recovery.json"
ROOT_MARKER_NAME = ".vocab_app_root_marker.json"
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


def _compute_file_sha256(path: Path) -> str:
    """Compute the SHA-256 digest of a regular file using streaming reads."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _summarize_component_tree(path: Path) -> dict[str, object]:
    """Summarize a directory component with relative file paths and streaming digests while rejecting links."""
    if _is_link(path):
        raise ValueError(f"component '{path.name}' is a link or junction")
    if not path.exists():
        return {"present": False, "file_count": 0, "total_bytes": 0, "files": {}}
    if not path.is_dir():
        raise ValueError(f"component '{path.name}' is not a regular directory")
    file_count = 0
    total_bytes = 0
    files_map: dict[str, dict[str, object]] = {}
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        for d in dirs:
            dir_path = root_path / d
            if _is_link(dir_path):
                raise ValueError(f"subdirectory '{dir_path}' is a link or junction")
        for f in sorted(files):
            file_path = root_path / f
            if _is_link(file_path) or not file_path.is_file():
                raise ValueError(f"file '{file_path}' is not a regular file")
            rel_name = str(file_path.relative_to(path)).replace("\\", "/")
            file_size = file_path.stat().st_size
            file_sha = _compute_file_sha256(file_path)
            file_count += 1
            total_bytes += file_size
            files_map[rel_name] = {
                "size": file_size,
                "sha256": file_sha,
            }
    return {
        "present": True,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "files": files_map,
    }


def _build_component_manifest(root: Path) -> dict[str, object]:
    """Build a verifiable four-component manifest with relative file paths and streaming SHA-256 digests."""
    db_path = root / "vocab.db"
    if _is_link(db_path) or not db_path.is_file():
        raise ValueError("vocab.db is missing or not a regular file")
    prefs_path = root / "preferences.json"
    if _is_link(prefs_path):
        raise ValueError("preferences.json is a link")
    prefs_present = prefs_path.exists()
    if prefs_present:
        if not prefs_path.is_file():
            raise ValueError("preferences.json is not a regular file")
        parsed_prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
        if not isinstance(parsed_prefs, dict):
            raise ValueError("preferences.json is not a valid JSON object")
        prefs_size = prefs_path.stat().st_size
        prefs_sha = _compute_file_sha256(prefs_path)
    else:
        prefs_size = 0
        prefs_sha = ""

    return {
        "database": {
            "present": True,
            "size": db_path.stat().st_size,
            "sha256": _compute_file_sha256(db_path),
        },
        "preferences": {
            "present": prefs_present,
            "size": prefs_size,
            "sha256": prefs_sha,
        },
        "backups": _summarize_component_tree(root / "backups"),
        "audio_cache": _summarize_component_tree(root / "audio-cache"),
    }


def _verify_promoted_target(
    pending_root: Path,
    expected_source_root: Path,
    expected_uuid: str,
    expected_components: dict[str, object] | None,
) -> dict[str, object]:
    """Verify full four-component integrity (streaming digests and relative files) and marker provenance."""
    if _is_link(pending_root) or not pending_root.is_dir():
        raise ValueError("promoted target folder is missing or not a regular directory")
    _require_writable_directory(pending_root)

    marker = pending_root / ROOT_MARKER_NAME
    if _is_link(marker) or not marker.is_file():
        raise ValueError("root marker is missing or not a regular file")
    marker_data = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(marker_data, dict):
        raise ValueError("root marker is not a valid JSON object")

    marker_target_raw = marker_data.get("target_root", "")
    if (
        not isinstance(marker_target_raw, str)
        or not marker_target_raw.strip()
        or Path(marker_target_raw).resolve() != pending_root
    ):
        raise ValueError("root marker target_root does not match pending target")

    marker_source_raw = marker_data.get("source_root", "")
    if (
        not isinstance(marker_source_raw, str)
        or not marker_source_raw.strip()
        or Path(marker_source_raw).resolve() != expected_source_root
    ):
        raise ValueError("root marker source_root does not match journal latest_committed_root")

    if not expected_uuid or marker_data.get("marker_uuid") != expected_uuid:
        raise ValueError("root marker uuid does not match journal expectation")

    pending_db = pending_root / "vocab.db"
    if _is_link(pending_db) or not pending_db.is_file():
        raise ValueError("promoted target has no regular vocab.db")
    _validate_relocated_database(pending_db)

    marker_components = marker_data.get("components")
    manifest = expected_components if isinstance(expected_components, dict) else marker_components
    if not isinstance(manifest, dict):
        raise ValueError("missing four-component verification manifest for SWITCHING recovery")
    if isinstance(expected_components, dict) and isinstance(marker_components, dict):
        if expected_components != marker_components:
            raise ValueError("journal component manifest does not match target root marker manifest")

    actual_manifest = _build_component_manifest(pending_root)
    for comp_key in ("database", "preferences", "backups", "audio_cache"):
        if comp_key not in manifest or actual_manifest.get(comp_key) != manifest.get(comp_key):
            raise ValueError(
                f"component '{comp_key}' verification failed during SWITCHING recovery"
            )

    for dir_name in ("backups", "audio-cache"):
        child_dir = pending_root / dir_name
        if child_dir.exists():
            _require_writable_directory(child_dir)
    prefs_file = pending_root / "preferences.json"
    if prefs_file.exists():
        with prefs_file.open("rb+"):
            pass

    return marker_data



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
    journal_path = default_root / RECOVERY_JOURNAL_NAME
    try:
        pointer_present = pointer.exists() or _is_link(pointer)
        journal_present = journal_path.exists() or _is_link(journal_path)
    except OSError as error:
        raise _data_root_error(str(error)) from error

    journal_record: dict | None = None
    if journal_present and not complete_override:
        try:
            if _is_link(journal_path) or not journal_path.is_file():
                raise ValueError("the recovery journal is not a regular file")
            if journal_path.stat().st_size > 65536:
                raise ValueError("recovery journal is too large")
            raw_journal = json.loads(journal_path.read_text(encoding="utf-8"))
            if not isinstance(raw_journal, dict):
                raise ValueError("recovery journal has an invalid format")
            
            # Crash recovery check: if journal was left in SWITCHING state
            status = raw_journal.get("status")
            if status == "SWITCHING":
                pending_root_str = raw_journal.get("pending_target_root")
                if not isinstance(pending_root_str, str) or not pending_root_str.strip():
                    raise ValueError("recovery journal left in SWITCHING state without valid pending_target_root")
                latest_committed_str = raw_journal.get("latest_committed_root")
                if not isinstance(latest_committed_str, str) or not latest_committed_str.strip():
                    raise ValueError("recovery journal left in SWITCHING state without valid latest_committed_root")
                expected_uuid = raw_journal.get("pending_marker_uuid")
                if not isinstance(expected_uuid, str) or not expected_uuid.strip():
                    raise ValueError("recovery journal left in SWITCHING state without valid pending_marker_uuid")

                pending_root = Path(pending_root_str).resolve()
                expected_source_root = Path(latest_committed_str).resolve()
                expected_components = raw_journal.get("pending_components")

                if pending_root.exists() or _is_link(pending_root):
                    # Case 1: Promoted target exists on disk -> verify full 4-component integrity + marker provenance
                    try:
                        marker_data = _verify_promoted_target(
                            pending_root=pending_root,
                            expected_source_root=expected_source_root,
                            expected_uuid=expected_uuid,
                            expected_components=expected_components if isinstance(expected_components, dict) else None,
                        )
                    except Exception as verify_err:
                        raise ValueError(
                            f"Relocation transition was interrupted during SWITCHING to '{pending_root}', "
                            f"and target verification failed: {verify_err}"
                        ) from verify_err

                    # Forward-roll pointer
                    pointer_data = {"version": 1, "data_root": str(pending_root)}
                    with tempfile.NamedTemporaryFile("w", dir=default_root, delete=False, encoding="utf-8") as temp_p:
                        temp_p.write(json.dumps(pointer_data, indent=2))
                        temp_p.flush()
                        os.fsync(temp_p.fileno())
                        temp_p_name = temp_p.name
                    os.replace(temp_p_name, pointer)
                    pointer_present = True

                    # Forward-roll journal to COMMITTED and append to history
                    history = raw_journal.get("history")
                    if not isinstance(history, list):
                        history = []
                    next_seq = (max((item.get("sequence", 0) for item in history), default=0) + 1)
                    recovered_entry = {
                        "sequence": next_seq,
                        "committed_at": marker_data.get("relocated_at", "recovered"),
                        "source_root": str(expected_source_root),
                        "target_root": str(pending_root),
                        "schema_version": marker_data.get(
                            "schema_version", raw_journal.get("pending_schema_version", "unknown")
                        ),
                        "app_data_version": marker_data.get(
                            "app_data_version", raw_journal.get("pending_app_data_version", "unknown")
                        ),
                        "marker_uuid": str(marker_data.get("marker_uuid", expected_uuid)),
                        "recovered": True,
                    }
                    history.append(recovered_entry)

                    raw_journal["status"] = "COMMITTED"
                    raw_journal["latest_committed_root"] = str(pending_root)
                    raw_journal["history"] = history
                    for k in (
                        "pending_target_root",
                        "pending_staging_dir",
                        "pending_marker_uuid",
                        "pending_schema_version",
                        "pending_app_data_version",
                        "pending_components",
                        "had_prior_journal",
                    ):
                        raw_journal.pop(k, None)
                    with tempfile.NamedTemporaryFile("w", dir=default_root, delete=False, encoding="utf-8") as temp_j:
                        temp_j.write(json.dumps(raw_journal, indent=2))
                        temp_j.flush()
                        os.fsync(temp_j.fileno())
                        temp_j_name = temp_j.name
                    os.replace(temp_j_name, journal_path)
                else:
                    # Case 2: Promoted target does not exist.
                    # Distinguish an abrupt crash BEFORE atomic promotion (staging directory still present
                    # on the target parent volume with matching provenance marker) from an unavailable/unplugged
                    # promoted destination.
                    pending_staging_str = raw_journal.get("pending_staging_dir")
                    unpromoted_staging_verified = False
                    pending_staging: Path | None = None
                    if isinstance(pending_staging_str, str) and pending_staging_str.strip():
                        pending_staging = Path(pending_staging_str).resolve()
                        stage_marker_file = pending_staging / ROOT_MARKER_NAME
                        if (
                            pending_staging.is_dir()
                            and not _is_link(pending_staging)
                            and stage_marker_file.is_file()
                            and not _is_link(stage_marker_file)
                        ):
                            try:
                                stage_marker_data = json.loads(stage_marker_file.read_text(encoding="utf-8"))
                                if (
                                    isinstance(stage_marker_data, dict)
                                    and stage_marker_data.get("marker_uuid") == expected_uuid
                                    and Path(stage_marker_data.get("target_root", "")).resolve() == pending_root
                                    and Path(stage_marker_data.get("source_root", "")).resolve() == expected_source_root
                                ):
                                    unpromoted_staging_verified = True
                            except Exception:
                                unpromoted_staging_verified = False

                    if unpromoted_staging_verified and pending_staging is not None:
                        # Verify the prior committed source root is still intact before rolling back journal
                        if _is_link(expected_source_root) or not expected_source_root.is_dir():
                            raise ValueError("prior source root is unavailable for pre-promotion rollback")
                        _validate_relocated_database(expected_source_root / "vocab.db")

                        history = raw_journal.get("history")
                        if not isinstance(history, list):
                            history = []
                        had_prior_journal = bool(raw_journal.get("had_prior_journal", bool(history)))

                        if (
                            not had_prior_journal
                            and not history
                            and expected_source_root == default_root.resolve()
                            and not pointer_present
                        ):
                            # First relocation from default root was aborted before promotion: remove journal first
                            journal_path.unlink(missing_ok=True)
                            journal_present = False
                            raw_journal = None
                        else:
                            # Restore journal to prior COMMITTED root first
                            if expected_source_root != default_root.resolve():
                                pointer_data = {"version": 1, "data_root": str(expected_source_root)}
                                with tempfile.NamedTemporaryFile("w", dir=default_root, delete=False, encoding="utf-8") as temp_p:
                                    temp_p.write(json.dumps(pointer_data, indent=2))
                                    temp_p.flush()
                                    os.fsync(temp_p.fileno())
                                    temp_p_name = temp_p.name
                                os.replace(temp_p_name, pointer)
                                pointer_present = True

                            raw_journal["status"] = "COMMITTED"
                            raw_journal["latest_committed_root"] = str(expected_source_root)
                            raw_journal["history"] = history
                            for k in (
                                "pending_target_root",
                                "pending_staging_dir",
                                "pending_marker_uuid",
                                "pending_schema_version",
                                "pending_app_data_version",
                                "pending_components",
                                "had_prior_journal",
                            ):
                                raw_journal.pop(k, None)
                            with tempfile.NamedTemporaryFile("w", dir=default_root, delete=False, encoding="utf-8") as temp_j:
                                temp_j.write(json.dumps(raw_journal, indent=2))
                                temp_j.flush()
                                os.fsync(temp_j.fileno())
                                temp_j_name = temp_j.name
                            os.replace(temp_j_name, journal_path)

                        # Remove unpromoted staging directory after journal is durably restored
                        shutil.rmtree(pending_staging, ignore_errors=True)
                    else:
                        raise ValueError(
                            f"Relocation transition was interrupted during SWITCHING to '{pending_root}', "
                            "and target verification failed (target missing and no unpromoted staging directory found)"
                        )

            if raw_journal is not None:
                if "latest_committed_root" not in raw_journal:
                    raise ValueError("recovery journal has an invalid format")
                latest_val = raw_journal["latest_committed_root"]
                if not isinstance(latest_val, str) or not latest_val.strip():
                    raise ValueError("recovery journal has an invalid committed root")
                journal_record = raw_journal
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, sqlite3.Error) as error:
            raise _data_root_error(f"recovery journal error: {error}") from error


    if not complete_override and journal_record is not None and not pointer_present:
        latest = journal_record.get("latest_committed_root", "")
        raise _data_root_error(
            f"A prior data relocation was committed to '{latest}', but the location pointer "
            f"'{DATA_ROOT_POINTER_NAME}' is missing or damaged"
        )

    selected_root = None if complete_override else _configured_data_root(default_root)
    if not complete_override and journal_record is not None and selected_root is not None:
        journal_target = Path(journal_record["latest_committed_root"]).resolve()
        if selected_root != journal_target:
            raise _data_root_error(
                f"Conflict between {DATA_ROOT_POINTER_NAME} ('{selected_root}') "
                f"and recovery journal ('{journal_target}')"
            )
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

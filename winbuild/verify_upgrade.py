"""Phase F2 Upgrade & Data-Preservation Verification Script.

Automates and proves:
  1. Official v1.0.0 installer identity (SHA-256 match against release evidence:
     108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297).
  2. Silent installation of v1.0.0 to per-user Programs directory.
  3. Verification of installed v1.0.0 executable metadata (ProductVersion="1.0.0",
     FileVersion="1.0.0.0") and Inno Uninstall Registry entry.
  4. Construction of authentic v1.0.0 user state from the repository's v1.0.0 tag/source:
     - Real default database path: %LOCALAPPDATA%\\vocabulary_app\\vocab.db
     - Genuine v1.0 schema (schema_version="15.1.0-speech-semantics", app_data_version="15.1")
     - Sentinel Collection and Sentinel Entry created via v1.0.0 domain APIs
     - Sentinel Preferences (preferences.json)
  5. Silent overlay upgrade of current v1.1.0 installer to the identical AppId/location.
  6. Verification of Inno Uninstall Registry evidence (single registration updated in-place,
     stable AppId, no duplicate/parallel product entries).
  7. Verification of upgraded v1.1.0 executable metadata (ProductVersion="1.1.0",
     FileVersion="1.1.0.0").
  8. Verification of data preservation across installer execution (no wipe/truncate of vocab.db).
  9. Execution of v1.1.0 migration and validation of pre-migration backup contract
     (vocab-pre-15.1.0-speech-semantics-*.db).
 10. Verification of upgraded schema (schema_version="21.1.0-review-schedule",
     app_data_version="21.1", card_review_schedules table).
 11. Verification of sentinel data accessibility and preferences durability.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Official published v1.0.0 release evidence
V1_0_RELEASE_TAG = "v1.0.0"
V1_0_RELEASE_SHA = "3ad6a2027cdbb66413661b3e3bb99a9c2cc2bd14"
V1_0_INSTALLER_NAME = "VocabularyApp-Setup-1.0.0.exe"
V1_0_KNOWN_SHA256 = (
    "108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297"
)
V1_0_RELEASE_DOWNLOAD_URL = (
    f"https://github.com/Peter-S-Shi/vocabulary-app/releases/download/"
    f"{V1_0_RELEASE_TAG}/{V1_0_INSTALLER_NAME}"
)

# Product identity constants
INNO_APP_ID = "{6C6F9E2A-6E3A-4C9F-9E8E-6B9C6E9A6F3D}"
INNO_UNINSTALL_KEY_NAME = f"{INNO_APP_ID}_is1"
EXPECTED_DEFAULT_DB_FILENAME = "vocab.db"

# Schema version constants
V1_0_SCHEMA_VERSION = "15.1.0-speech-semantics"
V1_0_APP_DATA_VERSION = "15.1"
V1_1_SCHEMA_VERSION = "21.1.0-review-schedule"
V1_1_APP_DATA_VERSION = "21.1"
V1_1_EXPECTED_APP_VERSION = "1.1.0"
V1_1_EXPECTED_FILE_VERSION = "1.1.0.0"

# Sentinel test data constants
SENTINEL_TERM = "v1_0_provenance_sentinel_term"
SENTINEL_MEANING = "v1_0_provenance_sentinel_meaning"
SENTINEL_COLLECTION_NAME = "v1_0_Upgrade_Sentinel_Collection"
SENTINEL_PREF_KEY = "v1_0_sentinel_pref_flag"
SENTINEL_PREF_VAL = "v1.0-verified-safe-upgrade-sentinel"


class UpgradeVerificationError(RuntimeError):
    """Raised when any upgrade or data safety invariant fails."""


def calculate_sha256(path: Path) -> str:
    """Calculate the lowercase hexadecimal SHA-256 digest of a file."""
    if not path.is_file():
        raise UpgradeVerificationError(f"File not found for checksum: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def verify_v1_installer_sha256(installer_path: Path) -> str:
    """Verify that the v1.0.0 installer matches official release evidence."""
    actual_sha = calculate_sha256(installer_path)
    expected_sha = V1_0_KNOWN_SHA256.lower()
    if actual_sha != expected_sha:
        raise UpgradeVerificationError(
            f"v1.0.0 installer SHA-256 mismatch!\n"
            f"  File: {installer_path}\n"
            f"  Actual:   {actual_sha}\n"
            f"  Expected: {expected_sha}"
        )
    return actual_sha


def ensure_v1_installer(download_dir: Path, custom_path: Path | None = None) -> Path:
    """Ensure authentic v1.0.0 installer exists, downloading if necessary."""
    if custom_path:
        if not custom_path.is_file():
            raise UpgradeVerificationError(f"Specified v1.0 installer not found: {custom_path}")
        verify_v1_installer_sha256(custom_path)
        return custom_path

    target_path = download_dir / V1_0_INSTALLER_NAME
    if target_path.is_file():
        try:
            verify_v1_installer_sha256(target_path)
            return target_path
        except UpgradeVerificationError:
            target_path.unlink()

    download_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading v1.0.0 installer from {V1_0_RELEASE_DOWNLOAD_URL} ...")
    urllib.request.urlretrieve(V1_0_RELEASE_DOWNLOAD_URL, str(target_path))
    verify_v1_installer_sha256(target_path)
    return target_path


def get_default_programs_install_dir() -> Path:
    r"""Return default Inno Setup per-user install directory ({autopf}\Vocabulary App)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Programs" / "Vocabulary App"
    return Path.home() / "AppData" / "Local" / "Programs" / "Vocabulary App"


def get_default_user_data_dir() -> Path:
    r"""Return default user data directory (%LOCALAPPDATA%\vocabulary_app)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "vocabulary_app"
    return Path.home() / "AppData" / "Local" / "vocabulary_app"


def get_windows_exe_version(exe_path: Path) -> dict[str, str]:
    """Query Windows executable version resource metadata via PowerShell."""
    if not exe_path.is_file():
        raise UpgradeVerificationError(f"Executable not found at {exe_path}")

    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"(Get-Item -LiteralPath '{exe_path}').VersionInfo | "
        "Select-Object ProductVersion, FileVersion, FileDescription, ProductName | "
        "ConvertTo-Json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise UpgradeVerificationError(
            f"Failed to query PE version for {exe_path}: {proc.stderr}"
        )

    try:
        data = json.loads(proc.stdout)
        return {
            "ProductVersion": str(data.get("ProductVersion", "")).strip(),
            "FileVersion": str(data.get("FileVersion", "")).strip(),
            "FileDescription": str(data.get("FileDescription", "")).strip(),
            "ProductName": str(data.get("ProductName", "")).strip(),
        }
    except Exception as exc:
        raise UpgradeVerificationError(
            f"Failed to parse PE version JSON for {exe_path}: {exc}\nOutput: {proc.stdout}"
        ) from exc


def get_inno_uninstall_registrations(
    app_id: str = INNO_APP_ID,
    app_name: str = "Vocabulary App",
) -> list[dict[str, Any]]:
    """Query Windows registry for Inno Setup uninstall registrations."""
    results: list[dict[str, Any]] = []
    try:
        import winreg
    except ImportError:
        return results

    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hkey, subkey_path in roots:
        try:
            with winreg.OpenKey(hkey, subkey_path) as key:
                num_subkeys, _, _ = winreg.QueryInfoKey(key)
                for i in range(num_subkeys):
                    subkey_name = winreg.EnumKey(key, i)
                    try:
                        with winreg.OpenKey(key, subkey_name) as app_key:
                            values: dict[str, Any] = {}
                            num_vals, _, _ = winreg.QueryInfoKey(app_key)
                            for j in range(num_vals):
                                val_name, val_data, _ = winreg.EnumValue(app_key, j)
                                values[val_name] = val_data
                            display_name = str(values.get("DisplayName", ""))
                            # Match against exact AppId subkey or app name
                            if app_id.lower() in subkey_name.lower() or (
                                app_name.lower() in display_name.lower()
                            ):
                                results.append({
                                    "hive": "HKCU" if hkey == winreg.HKEY_CURRENT_USER else "HKLM",
                                    "key_name": subkey_name,
                                    "display_name": display_name,
                                    "display_version": str(
                                        values.get("DisplayVersion")
                                        or values.get("Inno Setup: Setup Version")
                                        or ""
                                    ),
                                    "setup_version": str(values.get("Inno Setup: Setup Version", "")),
                                    "install_location": str(
                                        values.get("InstallLocation")
                                        or values.get("Inno Setup: App Path")
                                        or ""
                                    ),
                                    "uninstall_string": str(values.get("UninstallString", "")),
                                    "quiet_uninstall_string": str(values.get("QuietUninstallString", "")),
                                })
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            continue
    return results


def verify_v1_0_uninstall_registration(
    registrations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify that v1.0.0 created exactly one correct uninstall registration."""
    if not registrations:
        raise UpgradeVerificationError(
            "No Inno Setup uninstall registration found after v1.0.0 installation!"
        )
    if len(registrations) > 1:
        raise UpgradeVerificationError(
            f"Expected exactly 1 uninstall registration for v1.0.0, found {len(registrations)}: {registrations}"
        )
    reg = registrations[0]
    if INNO_APP_ID.lower() not in reg["key_name"].lower() or not reg["key_name"].endswith("_is1"):
        raise UpgradeVerificationError(
            f"Uninstall key name '{reg['key_name']}' does not match expected Inno AppId '{INNO_APP_ID}'"
        )
    if not reg["display_version"].startswith("1.0.0"):
        raise UpgradeVerificationError(
            f"v1.0.0 DisplayVersion is '{reg['display_version']}', expected '1.0.0'"
        )
    return reg


def verify_v1_1_overlay_uninstall_registration(
    v1_0_reg: dict[str, Any],
    registrations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify that v1.1.0 updated the existing registration in-place without side-by-side duplicates."""
    if not registrations:
        raise UpgradeVerificationError(
            "No Inno Setup uninstall registration found after v1.1.0 upgrade!"
        )
    if len(registrations) > 1:
        raise UpgradeVerificationError(
            f"Multiple uninstall registrations found after v1.1.0 upgrade! "
            f"Overlay failed and installed parallel products: {registrations}"
        )
    reg = registrations[0]
    if reg["key_name"].lower() != v1_0_reg["key_name"].lower():
        raise UpgradeVerificationError(
            f"AppId key name changed during upgrade! Before: '{v1_0_reg['key_name']}', After: '{reg['key_name']}'"
        )
    if not reg["display_version"].startswith(V1_1_EXPECTED_APP_VERSION):
        raise UpgradeVerificationError(
            f"v1.1.0 DisplayVersion is '{reg['display_version']}', expected '{V1_1_EXPECTED_APP_VERSION}'"
        )
    return reg


def run_silent_installer(installer_path: Path) -> None:
    """Execute an Inno Setup installer silently with standard per-user flags."""
    if not installer_path.is_file():
        raise UpgradeVerificationError(f"Installer binary not found: {installer_path}")

    cmd = [
        str(installer_path),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
        "/CURRENTUSER",
    ]
    print(f"Running silent installer: {installer_path.name} ...")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise UpgradeVerificationError(
            f"Installer {installer_path.name} failed with code {proc.returncode}.\n"
            f"Stdout: {proc.stdout}\nStderr: {proc.stderr}"
        )
    print(f"Installer {installer_path.name} finished successfully (code 0).")


@contextmanager
def scoped_app_env(data_dir: Path):
    """Scope database and preference environment variables to data_dir, restoring on exit."""
    from src import db

    db_path = data_dir / EXPECTED_DEFAULT_DB_FILENAME
    pref_path = data_dir / "preferences.json"
    backup_dir = data_dir / "backups"

    old_db_path = db.DB_PATH
    old_env = {
        "VOCAB_APP_DB_PATH": os.environ.get("VOCAB_APP_DB_PATH"),
        "VOCAB_APP_BACKUP_DIR": os.environ.get("VOCAB_APP_BACKUP_DIR"),
        "VOCAB_APP_PREFERENCES_PATH": os.environ.get("VOCAB_APP_PREFERENCES_PATH"),
    }
    os.environ["VOCAB_APP_DB_PATH"] = str(db_path)
    os.environ["VOCAB_APP_BACKUP_DIR"] = str(backup_dir)
    os.environ["VOCAB_APP_PREFERENCES_PATH"] = str(pref_path)
    db.DB_PATH = db_path
    try:
        yield
    finally:
        db.DB_PATH = old_db_path
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def create_authentic_v1_0_user_state(
    data_dir: Path,
    repo_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Construct an authentic v1.0.0 user state using real v1.0.0 tag source code.

    Creates an isolated git worktree at tag `v1.0.0`, executes v1.0.0's native
    init_db() and domain APIs to create a sentinel collection and entry in the
    real default database (`vocab.db`), writes authentic v1.0 preferences, and
    cleans up the worktree.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / EXPECTED_DEFAULT_DB_FILENAME
    pref_path = data_dir / "preferences.json"
    backup_dir = data_dir / "backups"

    if db_path.is_file():
        db_path.unlink()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_parent:
        worktree_dir = Path(tmp_parent) / "v1_0_worktree"

        # 1. Add detached git worktree at v1.0.0 tag
        print(f"Creating isolated git worktree at tag {V1_0_RELEASE_TAG} ...")
        proc_wt = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_dir), V1_0_RELEASE_TAG],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc_wt.returncode != 0:
            raise UpgradeVerificationError(
                f"Failed to create git worktree for {V1_0_RELEASE_TAG}:\n{proc_wt.stderr}"
            )

        try:
            # 2. Write seeding script inside v1.0.0 worktree
            seeder_script = worktree_dir / "seed_v1_0_baseline.py"
            seeder_content = f"""
import json
import os
import sqlite3
import sys
from pathlib import Path

# Force v1.0.0 worktree to the front of sys.path
sys.path.insert(0, os.getcwd())

from src.db import init_db, get_connection
from src.entries import add_entry
from src.collections import create_collection, add_entries_to_collection
from src.migrations import get_schema_version, get_metadata

# 1. Native v1.0.0 schema initialization
init_db()

# 2. Seed sentinel entry and collection via v1.0 domain APIs
sentinel_entry_id = int(add_entry(
    language="English",
    term="{SENTINEL_TERM}",
    meaning="{SENTINEL_MEANING}",
    explanation_language="English",
    entry_type="word",
    example="Authentic v1.0.0 sentence created via v1.0.0 git tag source.",
    notes="Sentinel notes.",
    tags="v1_sentinel,upgrade_proof",
))

sentinel_collection_id = int(create_collection(
    name="{SENTINEL_COLLECTION_NAME}",
    description="Sentinel Collection created under authentic v1.0.0 tag.",
))

add_entries_to_collection(
    collection_id=sentinel_collection_id,
    entry_ids=[sentinel_entry_id],
)

# 3. Read metadata and verify v1.0 invariants
with get_connection() as conn:
    schema_ver = get_schema_version(conn)
    app_data_ver = get_metadata(conn, "app_data_version")

# 4. Write authentic v1.0 preferences.json
preferences_data = {{
    "theme": "dark",
    "include_proficient_in_study": True,
    "speech_engine": "windows_builtin",
    "{SENTINEL_PREF_KEY}": "{SENTINEL_PREF_VAL}",
}}
pref_path = Path(os.environ["VOCAB_APP_PREFERENCES_PATH"])
pref_path.write_text(json.dumps(preferences_data, indent=2), encoding="utf-8")

result = {{
    "sentinel_entry_id": sentinel_entry_id,
    "sentinel_collection_id": sentinel_collection_id,
    "v1_0_schema_version": schema_ver,
    "v1_0_app_data_version": app_data_ver,
}}
print("V1_0_SEED_RESULT_START" + json.dumps(result) + "V1_0_SEED_RESULT_END")
"""
            seeder_script.write_text(seeder_content, encoding="utf-8")

            # 3. Execute seeder script in v1.0.0 worktree subprocess
            child_env = dict(os.environ)
            child_env["VOCAB_APP_DB_PATH"] = str(db_path)
            child_env["VOCAB_APP_BACKUP_DIR"] = str(backup_dir)
            child_env["VOCAB_APP_PREFERENCES_PATH"] = str(pref_path)
            child_env["PYTHONPATH"] = str(worktree_dir)

            proc_seed = subprocess.run(
                [sys.executable, str(seeder_script)],
                cwd=str(worktree_dir),
                env=child_env,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc_seed.returncode != 0:
                raise UpgradeVerificationError(
                    f"v1.0.0 state creation failed with code {proc_seed.returncode}.\n"
                    f"Stdout: {proc_seed.stdout}\nStderr: {proc_seed.stderr}"
                )

            # Parse result token
            output = proc_seed.stdout
            start_marker = "V1_0_SEED_RESULT_START"
            end_marker = "V1_0_SEED_RESULT_END"
            if start_marker not in output or end_marker not in output:
                raise UpgradeVerificationError(
                    f"Failed to parse v1.0 seeder output:\n{output}"
                )
            json_str = output.split(start_marker)[1].split(end_marker)[0]
            seed_data = json.loads(json_str)

        finally:
            # 4. Clean up git worktree
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_dir)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )

    # 5. Direct verification of generated v1.0 database file
    if not db_path.is_file():
        raise UpgradeVerificationError(f"Expected database missing: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        schema_row = conn.execute(
            "SELECT value FROM app_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if not schema_row or schema_row["value"] != V1_0_SCHEMA_VERSION:
            raise UpgradeVerificationError(
                f"Generated v1.0 DB schema is '{schema_row['value'] if schema_row else None}', "
                f"expected '{V1_0_SCHEMA_VERSION}'"
            )
        has_schedules = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_review_schedules'"
        ).fetchone()
        if has_schedules is not None:
            raise UpgradeVerificationError(
                "Generated v1.0 DB contains 'card_review_schedules' table; provenance is invalid!"
            )
    finally:
        conn.close()

    db_sha = calculate_sha256(db_path)
    pref_sha = calculate_sha256(pref_path)
    print(f"Created authentic v1.0 user state from tag {V1_0_RELEASE_TAG} at {data_dir}:")
    print(f"  Database file: {db_path.name} (SHA-256: {db_sha})")
    print(f"  Preferences:   {pref_path.name} (SHA-256: {pref_sha})")

    return {
        "v1_0_source_tag": V1_0_RELEASE_TAG,
        "v1_0_source_sha": V1_0_RELEASE_SHA,
        "database_filename": db_path.name,
        "sentinel_entry_id": seed_data["sentinel_entry_id"],
        "sentinel_collection_id": seed_data["sentinel_collection_id"],
        "pre_upgrade_db_sha": db_sha,
        "pre_upgrade_pref_sha": pref_sha,
        "v1_0_schema_version": seed_data["v1_0_schema_version"],
        "v1_0_app_data_version": seed_data["v1_0_app_data_version"],
    }


def verify_pre_migration_backup(backup_dir: Path) -> Path:
    """Verify that the pre-migration backup contract executed and produced a valid DB."""
    if not backup_dir.is_dir():
        raise UpgradeVerificationError(f"Backup directory missing: {backup_dir}")

    candidates = sorted(backup_dir.glob(f"vocab-pre-{V1_0_SCHEMA_VERSION}-*.db"))
    if not candidates:
        raise UpgradeVerificationError(
            f"Pre-migration backup missing! No backup file matching 'vocab-pre-{V1_0_SCHEMA_VERSION}-*.db' "
            f"found in {backup_dir}."
        )

    backup_file = candidates[-1]
    if backup_file.stat().st_size < 1024:
        raise UpgradeVerificationError(
            f"Pre-migration backup file {backup_file.name} is suspiciously small ({backup_file.stat().st_size} bytes)."
        )

    # Verify backup contains valid pre-migration SQLite database
    conn = sqlite3.connect(backup_file)
    try:
        conn.row_factory = sqlite3.Row
        from src.migrations import get_schema_version

        backup_schema = get_schema_version(conn)
        if backup_schema != V1_0_SCHEMA_VERSION:
            raise UpgradeVerificationError(
                f"Backup database schema version is '{backup_schema}', expected '{V1_0_SCHEMA_VERSION}'."
            )
        # Check that card_review_schedules does NOT exist in the backup
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_review_schedules'"
        ).fetchone()
        if table_exists is not None:
            raise UpgradeVerificationError(
                "Backup database contains 'card_review_schedules' table; backup was not taken pre-migration!"
            )
        # Check sentinel entry exists in backup
        entry = conn.execute(
            "SELECT * FROM entries WHERE term = ?", (SENTINEL_TERM,)
        ).fetchone()
        if entry is None:
            raise UpgradeVerificationError("Sentinel entry missing from pre-migration backup!")
    finally:
        conn.close()

    print(f"Pre-migration backup verified: {backup_file.name} (Schema: {backup_schema})")
    return backup_file


def verify_v1_1_migrated_state(
    data_dir: Path,
    sentinel_info: dict[str, Any],
) -> dict[str, Any]:
    """Execute v1.1.0 migration and verify all schema and data preservation invariants."""
    db_path = data_dir / EXPECTED_DEFAULT_DB_FILENAME
    pref_path = data_dir / "preferences.json"
    backup_dir = data_dir / "backups"

    if not db_path.is_file():
        raise UpgradeVerificationError(
            f"Target database file missing at production path: {db_path}"
        )

    with scoped_app_env(data_dir):
        # 1. Run migration via standard production init_db()
        from src.db import init_db
        from src.migrations import get_schema_version, get_metadata
        from src.entries import get_entry_by_id
        from src.collections import get_collection_by_id, get_entries_in_collection

        init_db()

        # 2. Verify pre-migration backup
        backup_path = verify_pre_migration_backup(backup_dir)

        # 3. Verify upgraded database schema
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            schema_ver = get_schema_version(conn)
            app_data_ver = get_metadata(conn, "app_data_version")
            if schema_ver != V1_1_SCHEMA_VERSION:
                raise UpgradeVerificationError(
                    f"Migrated database schema is '{schema_ver}', expected '{V1_1_SCHEMA_VERSION}'"
                )
            if app_data_ver != V1_1_APP_DATA_VERSION:
                raise UpgradeVerificationError(
                    f"Migrated database app_data_version is '{app_data_ver}', expected '{V1_1_APP_DATA_VERSION}'"
                )
            # Ensure card_review_schedules table exists
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_review_schedules'"
            ).fetchone()
            if has_table is None:
                raise UpgradeVerificationError(
                    "Upgraded database is missing the 'card_review_schedules' table!"
                )
        finally:
            conn.close()

        # 4. Verify sentinel database entries through domain API
        entry = get_entry_by_id(sentinel_info["sentinel_entry_id"])
        if not entry or entry["term"] != SENTINEL_TERM or entry["meaning"] != SENTINEL_MEANING:
            raise UpgradeVerificationError(
                f"Sentinel entry corrupted or missing after migration! Found: {entry}"
            )

        collection = get_collection_by_id(sentinel_info["sentinel_collection_id"])
        if not collection or collection["name"] != SENTINEL_COLLECTION_NAME:
            raise UpgradeVerificationError(
                f"Sentinel collection corrupted or missing after migration! Found: {collection}"
            )

        entries = get_entries_in_collection(sentinel_info["sentinel_collection_id"])
        if not any(int(e["id"]) == sentinel_info["sentinel_entry_id"] for e in entries):
            raise UpgradeVerificationError(
                "Sentinel entry is no longer associated with Sentinel collection after migration!"
            )

        # 5. Verify preferences durability
        if not pref_path.is_file():
            raise UpgradeVerificationError(f"Preferences file missing at {pref_path}")
        prefs = json.loads(pref_path.read_text(encoding="utf-8"))
        if prefs.get(SENTINEL_PREF_KEY) != SENTINEL_PREF_VAL:
            raise UpgradeVerificationError(
                f"Preferences sentinel corrupted or missing! Found: {prefs}"
            )
        if prefs.get("theme") != "dark":
            raise UpgradeVerificationError(
                f"Preferences 'theme' key corrupted! Found: {prefs}"
            )

    print("v1.1.0 migration and data preservation invariants fully verified:")
    print(f"  Schema: {schema_ver} (app_data_version: {app_data_ver})")
    print(f"  Sentinel Entry: ID {entry['id']} '{entry['term']}' -> '{entry['meaning']}' (PRESERVED)")
    print(f"  Sentinel Collection: ID {collection['id']} '{collection['name']}' (PRESERVED)")
    print(f"  Sentinel Prefs: {SENTINEL_PREF_KEY}='{SENTINEL_PREF_VAL}' (PRESERVED)")

    return {
        "migrated_schema_version": schema_ver,
        "migrated_app_data_version": app_data_ver,
        "backup_path": str(backup_path),
        "backup_sha256": calculate_sha256(backup_path),
        "post_migration_db_sha256": calculate_sha256(db_path),
    }


def run_full_upgrade_verification(
    v1_installer_path: Path,
    v1_1_installer_path: Path,
    data_dir: Path,
    install_dir: Path,
    report_path: Path,
    skip_installer_execution: bool = False,
    repo_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Execute full automated v1.0.0 -> v1.1.0 upgrade & data-safety verification pipeline."""
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "v1_0_release_tag": V1_0_RELEASE_TAG,
        "v1_0_release_sha": V1_0_RELEASE_SHA,
        "v1_0_expected_installer_sha256": V1_0_KNOWN_SHA256,
        "target_database_filename": EXPECTED_DEFAULT_DB_FILENAME,
        "inno_app_id": INNO_APP_ID,
        "inno_uninstall_key": INNO_UNINSTALL_KEY_NAME,
        "data_dir": str(data_dir),
        "install_dir": str(install_dir),
        "stages": {},
    }

    # Step 0: Check v1.0.0 installer SHA-256
    v1_sha = verify_v1_installer_sha256(v1_installer_path)
    report["v1_0_installer_path"] = str(v1_installer_path)
    report["v1_0_installer_sha256"] = v1_sha
    print(f"v1.0.0 installer verified: {v1_installer_path} (SHA-256 match)")

    installed_exe = install_dir / "Vocabulary App.exe"

    if not skip_installer_execution:
        # Step 1: Clean install v1.0.0
        print("\n=== Step 1: Installing v1.0.0 ===")
        run_silent_installer(v1_installer_path)
        v1_meta = get_windows_exe_version(installed_exe)
        print(f"Installed v1.0.0 EXE metadata: {v1_meta}")
        if not v1_meta["ProductVersion"].startswith("1.0.0"):
            raise UpgradeVerificationError(
                f"Installed v1.0.0 EXE ProductVersion is '{v1_meta['ProductVersion']}', expected '1.0.0'"
            )
        if not v1_meta["FileVersion"].startswith("1.0.0"):
            raise UpgradeVerificationError(
                f"Installed v1.0.0 EXE FileVersion is '{v1_meta['FileVersion']}', expected '1.0.0.0'"
            )
        report["v1_0_installed_metadata"] = v1_meta

        # Verify v1.0 Inno uninstall registration
        v1_regs = get_inno_uninstall_registrations(INNO_APP_ID)
        v1_reg = verify_v1_0_uninstall_registration(v1_regs)
        print(f"Verified v1.0.0 Inno uninstall registration: {v1_reg['key_name']} ({v1_reg['display_version']})")
        report["v1_0_uninstall_registration"] = v1_reg

    # Step 2: Seed authentic v1.0.0 user state using v1.0.0 git tag
    print(f"\n=== Step 2: Seeding Authentic v1.0.0 User State from tag {V1_0_RELEASE_TAG} ===")
    sentinel_info = create_authentic_v1_0_user_state(data_dir, repo_root=repo_root)
    report["v1_0_user_state"] = sentinel_info

    if not skip_installer_execution:
        # Step 3: Overlay upgrade to v1.1.0
        print("\n=== Step 3: Overlay Upgrading to v1.1.0 ===")
        run_silent_installer(v1_1_installer_path)
        v1_1_meta = get_windows_exe_version(installed_exe)
        print(f"Upgraded v1.1.0 EXE metadata: {v1_1_meta}")
        if not v1_1_meta["ProductVersion"].startswith(V1_1_EXPECTED_APP_VERSION):
            raise UpgradeVerificationError(
                f"Upgraded v1.1.0 EXE ProductVersion is '{v1_1_meta['ProductVersion']}', expected '{V1_1_EXPECTED_APP_VERSION}'"
            )
        if not v1_1_meta["FileVersion"].startswith(V1_1_EXPECTED_FILE_VERSION):
            raise UpgradeVerificationError(
                f"Upgraded v1.1.0 EXE FileVersion is '{v1_1_meta['FileVersion']}', expected '{V1_1_EXPECTED_FILE_VERSION}'"
            )
        report["v1_1_installed_metadata"] = v1_1_meta

        # Verify v1.1 Inno uninstall registration is updated in-place (overlay, not parallel)
        v1_1_regs = get_inno_uninstall_registrations(INNO_APP_ID)
        v1_1_reg = verify_v1_1_overlay_uninstall_registration(v1_reg, v1_1_regs)
        print(f"Verified v1.1.0 overlay uninstall registration: {v1_1_reg['key_name']} ({v1_1_reg['display_version']})")
        report["v1_1_uninstall_registration"] = v1_1_reg

        # Verify user state files were not wiped by Inno Setup
        db_path = data_dir / EXPECTED_DEFAULT_DB_FILENAME
        pref_path = data_dir / "preferences.json"
        if not db_path.is_file() or not pref_path.is_file():
            raise UpgradeVerificationError(
                f"v1.1.0 installer erased user data files in {data_dir}!"
            )

    # Step 4: Run v1.1.0 migration and verify data preservation
    print("\n=== Step 4: Verifying v1.1.0 Schema Migration & Data Preservation ===")
    migration_result = verify_v1_1_migrated_state(data_dir, sentinel_info)
    report["migration_and_data_preservation"] = migration_result

    report["overall_status"] = "PASSED"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nUpgrade verification report written to: {report_path}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify v1.0.0 -> v1.1.0 Upgrade and Data-Preservation Proof."
    )
    parser.add_argument(
        "--v1-installer",
        type=Path,
        default=None,
        help="Path to official VocabularyApp-Setup-1.0.0.exe (downloaded automatically if omitted).",
    )
    parser.add_argument(
        "--v1-1-installer",
        type=Path,
        default=Path("dist/installer/VocabularyApp-Setup-1.1.0.exe"),
        help="Path to built VocabularyApp-Setup-1.1.0.exe.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="User data directory (defaults to %%LOCALAPPDATA%%\\vocabulary_app).",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        help="Install directory (defaults to %%LOCALAPPDATA%%\\Programs\\Vocabulary App).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("dist/upgrade_verification_report.json"),
        help="Path to write verification report JSON.",
    )
    parser.add_argument(
        "--skip-installer-execution",
        action="store_true",
        help="Skip installer execution (for unit tests / mock environment).",
    )
    args = parser.parse_args()

    # Resolve v1.0 installer
    download_dir = PROJECT_ROOT / "dist" / "v1_0_installer"
    try:
        v1_installer = ensure_v1_installer(download_dir, args.v1_installer)
    except Exception as exc:
        print(f"[FAILED] Failed to prepare v1.0.0 installer: {exc}", file=sys.stderr)
        return 1

    v1_1_installer = args.v1_1_installer
    if not args.skip_installer_execution and not v1_1_installer.is_file():
        print(f"[FAILED] v1.1.0 installer not found: {v1_1_installer}", file=sys.stderr)
        return 1

    data_dir = args.data_dir or get_default_user_data_dir()
    install_dir = args.install_dir or get_default_programs_install_dir()

    try:
        run_full_upgrade_verification(
            v1_installer_path=v1_installer,
            v1_1_installer_path=v1_1_installer,
            data_dir=data_dir,
            install_dir=install_dir,
            report_path=args.report_path,
            skip_installer_execution=args.skip_installer_execution,
            repo_root=PROJECT_ROOT,
        )
        print("\n=======================================================")
        print("[OK] PHASE F2 UPGRADE & DATA-PRESERVATION PROOF: PASSED")
        print("=======================================================")
        return 0
    except UpgradeVerificationError as err:
        print(f"\n[FAILED] UPGRADE PROOF FAILED: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
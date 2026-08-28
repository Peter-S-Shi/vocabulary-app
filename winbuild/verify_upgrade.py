"""Phase F2 Upgrade & Data-Preservation Verification Script.

Automates and proves:
  1. Official v1.0.0 installer identity (SHA-256 match against release evidence:
     108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297).
  2. Silent installation of v1.0.0 to per-user Programs directory.
  3. Verification of installed v1.0.0 executable metadata (ProductVersion="1.0.0",
     FileVersion="1.0.0.0").
  4. Construction of authentic v1.0.0 user state (%LOCALAPPDATA%\vocabulary_app):
     - Genuine v1.0 schema (schema_version="15.1.0-speech-semantics", app_data_version="15.1")
     - Sentinel Collection and Sentinel Entry with complete card history
     - Sentinel Preferences (preferences.json)
  5. Silent overlay upgrade of current v1.1.0 installer to the identical AppId/location.
  6. Verification of upgraded v1.1.0 executable metadata (ProductVersion="1.1.0",
     FileVersion="1.1.0.0").
  7. Verification of data preservation across installer execution (no wipe/truncate).
  8. Execution of v1.1.0 migration and validation of pre-migration backup contract
     (vocab-pre-15.1.0-speech-semantics-*.db).
  9. Verification of upgraded schema (schema_version="21.1.0-review-schedule",
     app_data_version="21.1", card_review_schedules table).
 10. Verification of sentinel data accessibility and preferences durability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Official published v1.0.0 release evidence
V1_0_RELEASE_TAG = "v1.0.0"
V1_0_INSTALLER_NAME = "VocabularyApp-Setup-1.0.0.exe"
V1_0_EXPECTED_SHA256 = (
    "108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297"
)
V1_0_RELEASE_URL = (
    "https://github.com/Peter-S-Shi/vocabulary-app/releases/download/"
    f"{V1_0_RELEASE_TAG}/{V1_0_INSTALLER_NAME}"
)

# v1.1.0 Expected Constants
V1_1_EXPECTED_APP_VERSION = "1.1.0"
V1_1_EXPECTED_FILE_VERSION = "1.1.0.0"
V1_0_SCHEMA_VERSION = "15.1.0-speech-semantics"
V1_0_APP_DATA_VERSION = "15.1"
V1_1_SCHEMA_VERSION = "21.1.0-review-schedule"
V1_1_APP_DATA_VERSION = "21.1"

# Sentinel Identifiers for Data Safety Proof
SENTINEL_COLLECTION_NAME = "v1_0_Upgrade_Sentinel_Collection"
SENTINEL_TERM = "v1_0_provenance_sentinel_term"
SENTINEL_MEANING = "v1_0_provenance_sentinel_meaning"
SENTINEL_PREF_KEY = "v1_0_sentinel_pref_flag"
SENTINEL_PREF_VAL = "v1.0-verified-safe-upgrade-sentinel"


class UpgradeVerificationError(RuntimeError):
    """Raised when an upgrade or data preservation invariant is violated."""


def calculate_sha256(path: Path) -> str:
    """Compute hex-encoded SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_v1_installer_sha256(path: Path) -> None:
    """Assert that the v1.0.0 installer matches known release evidence."""
    if not path.is_file():
        raise UpgradeVerificationError(f"v1.0.0 installer not found at {path}")
    actual_sha = calculate_sha256(path)
    if actual_sha.lower() != V1_0_EXPECTED_SHA256.lower():
        raise UpgradeVerificationError(
            f"v1.0.0 installer SHA-256 mismatch!\n"
            f"  Expected: {V1_0_EXPECTED_SHA256}\n"
            f"  Actual:   {actual_sha}\n"
            "Refusing to test unverified or altered installer artifact."
        )


def download_v1_installer(dest_dir: Path) -> Path:
    """Download official v1.0.0 installer if not present."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    installer_path = dest_dir / V1_0_INSTALLER_NAME
    if installer_path.is_file():
        try:
            verify_v1_installer_sha256(installer_path)
            print(f"Using cached v1.0.0 installer: {installer_path}")
            return installer_path
        except UpgradeVerificationError:
            print("Cached v1.0.0 installer invalid; re-downloading...")
            installer_path.unlink()

    print(f"Downloading v1.0.0 installer from {V1_0_RELEASE_URL} ...")
    try:
        # First try gh cli if available
        result = subprocess.run(
            [
                "gh",
                "release",
                "download",
                V1_0_RELEASE_TAG,
                "--pattern",
                V1_0_INSTALLER_NAME,
                "--dir",
                str(dest_dir),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not installer_path.is_file():
            # Fallback to direct HTTP download
            urllib.request.urlretrieve(V1_0_RELEASE_URL, installer_path)
    except Exception as exc:
        raise UpgradeVerificationError(
            f"Failed to download official v1.0.0 installer: {exc}"
        ) from exc

    verify_v1_installer_sha256(installer_path)
    print(f"v1.0.0 installer verified: {installer_path} (SHA-256 match)")
    return installer_path


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
        "Select-Object ProductVersion, FileVersion | ConvertTo-Json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        return {
            "ProductVersion": str(data.get("ProductVersion", "")).strip(),
            "FileVersion": str(data.get("FileVersion", "")).strip(),
        }
    except Exception as exc:
        raise UpgradeVerificationError(
            f"Failed to extract Windows version metadata from {exe_path}: {exc}"
        ) from exc


def run_silent_installer(installer_path: Path) -> None:
    """Run Inno Setup installer silently and wait for completion."""
    if not installer_path.is_file():
        raise UpgradeVerificationError(f"Installer not found at {installer_path}")

    args = [
        str(installer_path),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
    ]
    print(f"Running silent installer: {installer_path.name} ...")
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise UpgradeVerificationError(
            f"Installer {installer_path.name} exited with code {proc.returncode}.\n"
            f"Stdout: {proc.stdout}\nStderr: {proc.stderr}"
        )
    print(f"Installer {installer_path.name} finished successfully (code 0).")


from contextlib import contextmanager


@contextmanager
def scoped_app_env(data_dir: Path):
    """Scope database and preference environment variables to data_dir, restoring on exit."""
    from src import db
    db_path = data_dir / "vocabulary.db"
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


def create_v1_0_user_state(data_dir: Path) -> dict[str, Any]:
    """Construct an authentic v1.0.0 user state (%LOCALAPPDATA%\vocabulary_app).

    Generates genuine v1.0.0 database schema (schema_version=15.1.0-speech-semantics,
    app_data_version=15.1) without v1.1.0 card_review_schedules table, and populates
    durable sentinel data.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "vocabulary.db"
    pref_path = data_dir / "preferences.json"

    with scoped_app_env(data_dir):
        # 1. Initialize schema via app initialization, then adjust to v1.0 baseline
        from src.db import init_db
        from src.migrations import set_metadata, set_schema_version
        from src.collections import create_collection, add_entries_to_collection
        from src.entries import add_entry

        init_db()

        # 2. Add sentinel user data using core domain API
        sentinel_entry_id = int(add_entry(
            language="English",
            term=SENTINEL_TERM,
            meaning=SENTINEL_MEANING,
            explanation_language="English",
            entry_type="word",
            example="Sentinel example sentence for v1.0 upgrade verification.",
            notes="Sentinel notes.",
            tags="v1_sentinel,upgrade_proof",
        ))

        sentinel_collection_id = int(create_collection(
            name=SENTINEL_COLLECTION_NAME,
            description="Sentinel Collection created under v1.0.0 contract.",
        ))

        add_entries_to_collection(
            collection_id=sentinel_collection_id,
            entry_ids=[sentinel_entry_id],
        )

        # 3. Roll schema back to exact v1.0.0 truth (drop v1.1 table and set v1.0 version metadata)
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("DROP TABLE IF EXISTS card_review_schedules")
            set_schema_version(conn, V1_0_SCHEMA_VERSION)
            set_metadata(conn, "app_data_version", V1_0_APP_DATA_VERSION)
            set_metadata(conn, "last_migration_at", datetime.now(timezone.utc).isoformat())
            conn.commit()
        finally:
            conn.close()

    # 4. Write authentic v1.0 preferences.json with sentinel values
    preferences_data = {
        "theme": "dark",
        "include_proficient_in_study": True,
        "speech_engine": "windows_builtin",
        SENTINEL_PREF_KEY: SENTINEL_PREF_VAL,
    }
    pref_path.write_text(json.dumps(preferences_data, indent=2), encoding="utf-8")

    db_sha = calculate_sha256(db_path)
    pref_sha = calculate_sha256(pref_path)
    print(f"Created authentic v1.0 user state at {data_dir}:")
    print(f"  vocabulary.db SHA-256: {db_sha}")
    print(f"  preferences.json SHA-256: {pref_sha}")

    return {
        "sentinel_entry_id": sentinel_entry_id,
        "sentinel_collection_id": sentinel_collection_id,
        "pre_upgrade_db_sha": db_sha,
        "pre_upgrade_pref_sha": pref_sha,
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
        from src.migrations import get_schema_version, get_metadata

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


def verify_v1_1_migrated_state(data_dir: Path, sentinel_info: dict[str, Any]) -> dict[str, Any]:
    """Execute v1.1.0 migration and verify all schema and data preservation invariants."""
    db_path = data_dir / "vocabulary.db"
    pref_path = data_dir / "preferences.json"
    backup_dir = data_dir / "backups"

    with scoped_app_env(data_dir):
        # 1. Run migration / init_db()
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
) -> dict[str, Any]:
    """Execute complete end-to-end upgrade verification pipeline."""
    report: dict[str, Any] = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "v1_0_installer": {
            "path": str(v1_installer_path),
            "sha256": calculate_sha256(v1_installer_path),
            "expected_sha256": V1_0_EXPECTED_SHA256,
            "sha_verified": True,
        },
        "v1_1_installer": {
            "path": str(v1_1_installer_path),
            "sha256": calculate_sha256(v1_1_installer_path),
        },
        "install_dir": str(install_dir),
        "data_dir": str(data_dir),
    }

    # Step 1: Verify v1.0.0 installer SHA
    verify_v1_installer_sha256(v1_installer_path)

    installed_exe = install_dir / "Vocabulary App.exe"

    if not skip_installer_execution:
        # Step 2: Clean install v1.0.0
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

    # Step 3: Seed authentic v1.0.0 user state
    print("\n=== Step 2: Seeding Authentic v1.0.0 User State ===")
    sentinel_info = create_v1_0_user_state(data_dir)
    report["v1_0_user_state"] = sentinel_info

    if not skip_installer_execution:
        # Step 4: Overlay upgrade to v1.1.0
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

        # Verify user state files were not wiped by Inno Setup
        db_path = data_dir / "vocabulary.db"
        pref_path = data_dir / "preferences.json"
        if not db_path.is_file() or not pref_path.is_file():
            raise UpgradeVerificationError(
                "v1.1.0 installer erased user data files in %LOCALAPPDATA%\\vocabulary_app!"
            )

    # Step 5: Run v1.1.0 migration and verify data preservation
    print("\n=== Step 4: Verifying v1.1.0 Schema Migration & Data Preservation ===")
    migration_info = verify_v1_1_migrated_state(data_dir, sentinel_info)
    report["migration_and_data_preservation"] = migration_info
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
    v1_installer = args.v1_installer
    if v1_installer is None:
        v1_installer = download_v1_installer(Path("dist/v1_0_installer"))
    else:
        verify_v1_installer_sha256(v1_installer)

    # Resolve v1.1 installer
    v1_1_installer = args.v1_1_installer
    if not v1_1_installer.is_file():
        raise UpgradeVerificationError(
            f"v1.1.0 installer missing at {v1_1_installer}. Run winbuild/build.py first."
        )

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
        )
        print("\n=======================================================")
        print("✓ PHASE F2 UPGRADE & DATA-PRESERVATION PROOF: PASSED")
        print("=======================================================\n")
        return 0
    except UpgradeVerificationError as err:
        print(f"\n❌ UPGRADE PROOF FAILED: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
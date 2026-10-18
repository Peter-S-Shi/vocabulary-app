"""Upgrade & Data-Preservation Verification Script.

Automates and proves:
  1. Official v1.1.0 (or v1.0.0) installer identity (SHA-256 match against release evidence:
     v1.1.0: 8ae6bcf615ed180788119384e0c38b8d64590b6dbcce2b542e113b4fca3ecf89;
     v1.0.0: 108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297).
  2. Silent installation of baseline installer to per-user Programs directory.
  3. Verification of installed baseline executable metadata and Inno Uninstall Registry entry.
  4. Construction of authentic baseline user state from the repository's git tag/source:
     - Verified git tag provenance: annotated tag object SHA vs peeled source commit SHA.
     - Isolated harness database path supplied explicitly with --data-dir
     - Genuine schema and domain data (sentinel Collection, Entry, and Preferences)
  5. Silent overlay upgrade of target v1.2.0 installer to the identical AppId/location.
  6. Verification of Inno Uninstall Registry evidence (single registration updated in-place,
     stable AppId, populated raw_values, no duplicate/parallel product entries).
  7. Verification of upgraded executable metadata.
  8. Verification of data preservation across installer execution (no wipe/truncate of vocab.db).
  9. Execution of target migration and validation of pre-migration backup contract if applicable.
 10. Verification of upgraded schema and intact data tables.
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

# Official published v1.0.0 release evidence & provenance
V1_0_RELEASE_TAG = "v1.0.0"
V1_0_TAG_OBJECT_SHA = "3ad6a2027cdbb66413661b3e3bb99a9c2cc2bd14"
V1_0_PEELED_COMMIT_SHA = "2363e73bbd85ca24f7e227f8007e0046eeabd471"
V1_0_INSTALLER_NAME = "VocabularyApp-Setup-1.0.0.exe"
V1_0_KNOWN_SHA256 = (
    "108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297"
)
V1_0_RELEASE_DOWNLOAD_URL = (
    f"https://github.com/Peter-S-Shi/vocabulary-app/releases/download/"
    f"{V1_0_RELEASE_TAG}/{V1_0_INSTALLER_NAME}"
)

# Official published v1.1.0 release evidence & provenance
V1_1_RELEASE_TAG = "v1.1.0"
V1_1_TAG_OBJECT_SHA = "2af5dc48c25b690ef806c8c61a26037e9959d464"
V1_1_PEELED_COMMIT_SHA = "6bc492082cb2db8e19fdbf6c8530468edb4edf02"
V1_1_INSTALLER_NAME = "VocabularyApp-Setup-1.1.0.exe"
V1_1_KNOWN_SHA256 = (
    "8ae6bcf615ed180788119384e0c38b8d64590b6dbcce2b542e113b4fca3ecf89"
)
V1_1_RELEASE_DOWNLOAD_URL = (
    f"https://github.com/Peter-S-Shi/vocabulary-app/releases/download/"
    f"{V1_1_RELEASE_TAG}/{V1_1_INSTALLER_NAME}"
)

# Active baseline for current upgrade verification (v1.1.0 -> v1.2.0)
BASELINE_RELEASE_TAG = V1_1_RELEASE_TAG
BASELINE_TAG_OBJECT_SHA = V1_1_TAG_OBJECT_SHA
BASELINE_PEELED_COMMIT_SHA = V1_1_PEELED_COMMIT_SHA
BASELINE_INSTALLER_NAME = V1_1_INSTALLER_NAME
BASELINE_KNOWN_SHA256 = V1_1_KNOWN_SHA256
BASELINE_RELEASE_DOWNLOAD_URL = V1_1_RELEASE_DOWNLOAD_URL

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

TARGET_SCHEMA_VERSION = "21.1.0-review-schedule"
TARGET_APP_DATA_VERSION = "21.1"
TARGET_EXPECTED_APP_VERSION = "1.2.0"
TARGET_EXPECTED_FILE_VERSION = "1.2.0.0"

# Sentinel test data constants
SENTINEL_TERM = "v1_1_provenance_sentinel_term"
SENTINEL_MEANING = "v1_1_provenance_sentinel_meaning"
SENTINEL_COLLECTION_NAME = "v1_1_Upgrade_Sentinel_Collection"
SENTINEL_PREF_KEY = "v1_1_sentinel_pref_flag"
SENTINEL_PREF_VAL = "v1.1-verified-safe-upgrade-sentinel"


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


def verify_installer_sha256(installer_path: Path, expected_sha: str = BASELINE_KNOWN_SHA256) -> str:
    """Verify that the baseline installer matches official release evidence."""
    actual_sha = calculate_sha256(installer_path)
    if actual_sha != expected_sha.lower():
        raise UpgradeVerificationError(
            f"Installer SHA-256 mismatch!\n"
            f"  File: {installer_path}\n"
            f"  Actual:   {actual_sha}\n"
            f"  Expected: {expected_sha.lower()}"
        )
    return actual_sha


def verify_v1_installer_sha256(installer_path: Path) -> str:
    """Backward-compatible helper for verifying v1.0.0 installer."""
    return verify_installer_sha256(installer_path, expected_sha=V1_0_KNOWN_SHA256)


def verify_tag_provenance(
    tag_name: str = BASELINE_RELEASE_TAG,
    expected_tag_sha: str = BASELINE_TAG_OBJECT_SHA,
    expected_commit_sha: str = BASELINE_PEELED_COMMIT_SHA,
    repo_root: Path = PROJECT_ROOT,
) -> dict[str, str]:
    """Verify git tag provenance: tag object SHA vs peeled source commit SHA."""
    proc_tag = subprocess.run(
        ["git", "rev-parse", tag_name],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc_tag.returncode != 0:
        raise UpgradeVerificationError(
            f"Failed to resolve git tag {tag_name}:\n{proc_tag.stderr}"
        )
    tag_sha = proc_tag.stdout.strip()
    if tag_sha != expected_tag_sha:
        raise UpgradeVerificationError(
            f"Git tag {tag_name} tag object SHA mismatch!\n"
            f"  Actual:   {tag_sha}\n"
            f"  Expected: {expected_tag_sha}"
        )

    proc_commit = subprocess.run(
        ["git", "rev-parse", f"{tag_name}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc_commit.returncode != 0:
        raise UpgradeVerificationError(
            f"Failed to resolve git commit for tag {tag_name}:\n{proc_commit.stderr}"
        )
    commit_sha = proc_commit.stdout.strip()
    if commit_sha != expected_commit_sha:
        raise UpgradeVerificationError(
            f"Git tag {tag_name} peeled commit SHA mismatch!\n"
            f"  Actual:   {commit_sha}\n"
            f"  Expected: {expected_commit_sha}"
        )

    print(f"Verified {tag_name} git provenance:")
    print(f"  Tag Object SHA:    {tag_sha}")
    print(f"  Source Commit SHA: {commit_sha}")
    return {
        "tag_name": tag_name,
        "tag_object_sha": tag_sha,
        "source_commit_sha": commit_sha,
    }


def verify_v1_0_tag_provenance(repo_root: Path = PROJECT_ROOT) -> dict[str, str]:
    """Backward-compatible helper for verifying v1.0.0 tag provenance."""
    return verify_tag_provenance(
        tag_name=V1_0_RELEASE_TAG,
        expected_tag_sha=V1_0_TAG_OBJECT_SHA,
        expected_commit_sha=V1_0_PEELED_COMMIT_SHA,
        repo_root=repo_root,
    )


def ensure_baseline_installer(
    download_dir: Path,
    custom_path: Path | None = None,
    tag_name: str = BASELINE_RELEASE_TAG,
    installer_name: str = BASELINE_INSTALLER_NAME,
    known_sha256: str = BASELINE_KNOWN_SHA256,
    download_url: str = BASELINE_RELEASE_DOWNLOAD_URL,
) -> Path:
    """Ensure authentic baseline installer exists, downloading if necessary."""
    if custom_path:
        if not custom_path.is_file():
            raise UpgradeVerificationError(f"Specified baseline installer not found: {custom_path}")
        verify_installer_sha256(custom_path, expected_sha=known_sha256)
        return custom_path

    target_path = download_dir / installer_name
    if target_path.is_file():
        try:
            verify_installer_sha256(target_path, expected_sha=known_sha256)
            return target_path
        except UpgradeVerificationError:
            target_path.unlink()

    download_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading baseline installer from {download_url} ...")
    urllib.request.urlretrieve(download_url, str(target_path))
    verify_installer_sha256(target_path, expected_sha=known_sha256)
    return target_path


def ensure_v1_installer(download_dir: Path, custom_path: Path | None = None) -> Path:
    """Backward-compatible helper for ensuring v1.0.0 installer."""
    return ensure_baseline_installer(
        download_dir=download_dir,
        custom_path=custom_path,
        tag_name=V1_0_RELEASE_TAG,
        installer_name=V1_0_INSTALLER_NAME,
        known_sha256=V1_0_KNOWN_SHA256,
        download_url=V1_0_RELEASE_DOWNLOAD_URL,
    )


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


def require_isolated_verification_data_dir(data_dir: Path) -> Path:
    """Resolve and reject production user-data targets for destructive verification."""
    resolved_data_dir = data_dir.expanduser().resolve()
    production_data_dir = get_default_user_data_dir().expanduser().resolve()
    if (
        resolved_data_dir == production_data_dir
        or production_data_dir in resolved_data_dir.parents
    ):
        raise UpgradeVerificationError(
            "Upgrade verification requires an isolated --data-dir outside the "
            "production Vocabulary App user-data directory."
        )
    return resolved_data_dir


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
                # winreg.QueryInfoKey returns (num_subkeys, num_values, last_modified)
                num_subkeys, _, _ = winreg.QueryInfoKey(key)
                for i in range(num_subkeys):
                    subkey_name = winreg.EnumKey(key, i)
                    try:
                        with winreg.OpenKey(key, subkey_name) as app_key:
                            values: dict[str, Any] = {}
                            # Correct indexing: index 1 is num_values
                            _, num_values, _ = winreg.QueryInfoKey(app_key)
                            for j in range(num_values):
                                val_name, val_data, _ = winreg.EnumValue(app_key, j)
                                values[val_name] = val_data

                            val_map = {str(k).strip().lower(): str(v).strip() for k, v in values.items()}
                            display_name = str(values.get("DisplayName") or val_map.get("displayname", ""))
                            # Match against exact AppId subkey or app name
                            if app_id.lower() in subkey_name.lower() or (
                                app_name.lower() in display_name.lower()
                            ):
                                display_version = (
                                    val_map.get("displayversion")
                                    or val_map.get("inno setup: setup version")
                                    or val_map.get("setup version")
                                    or val_map.get("version")
                                    or ""
                                )
                                install_location = (
                                    val_map.get("installlocation")
                                    or val_map.get("inno setup: app path")
                                    or val_map.get("app path")
                                    or ""
                                )
                                results.append({
                                    "hive": "HKCU" if hkey == winreg.HKEY_CURRENT_USER else "HKLM",
                                    "key_name": subkey_name,
                                    "display_name": display_name,
                                    "display_version": display_version,
                                    "install_location": install_location,
                                    "uninstall_string": str(values.get("UninstallString", "")),
                                    "quiet_uninstall_string": str(values.get("QuietUninstallString", "")),
                                    "raw_values": {str(k): str(v) for k, v in values.items()},
                                })
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            continue
    return results


def verify_baseline_uninstall_registration(
    registrations: list[dict[str, Any]],
    expected_version_prefix: str = "1.1.0",
    expected_install_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify that baseline created exactly one correct, populated uninstall registration."""
    if not registrations:
        raise UpgradeVerificationError(
            "No Inno Setup uninstall registration found after baseline installation!"
        )
    if len(registrations) > 1:
        raise UpgradeVerificationError(
            f"Expected exactly 1 uninstall registration for baseline, found {len(registrations)}: {registrations}"
        )
    reg = registrations[0]
    if INNO_APP_ID.lower() not in reg["key_name"].lower() or not reg["key_name"].endswith("_is1"):
        raise UpgradeVerificationError(
            f"Uninstall key name '{reg['key_name']}' does not match expected Inno AppId '{INNO_APP_ID}'"
        )
    if not reg.get("raw_values"):
        raise UpgradeVerificationError(
            f"Uninstall registration raw_values is empty! Failed to enumerate values from registry key '{reg['key_name']}'"
        )
    if "vocabulary app" not in reg.get("display_name", "").lower():
        raise UpgradeVerificationError(
            f"Uninstall DisplayName is '{reg.get('display_name')}', expected to contain 'Vocabulary App'"
        )
    if not reg.get("display_version", "").startswith(expected_version_prefix):
        raise UpgradeVerificationError(
            f"Baseline DisplayVersion is '{reg.get('display_version')}', expected '{expected_version_prefix}'"
        )
    if not reg.get("install_location"):
        raise UpgradeVerificationError(
            f"Uninstall InstallLocation / App Path is empty in key '{reg['key_name']}'"
        )
    if expected_install_dir:
        actual_install = Path(reg["install_location"]).resolve()
        expected_install = expected_install_dir.resolve()
        if actual_install != expected_install and expected_install.name.lower() not in str(actual_install).lower():
            raise UpgradeVerificationError(
                f"Baseline InstallLocation '{actual_install}' does not match expected '{expected_install}'"
            )
    return reg


def verify_v1_0_uninstall_registration(
    registrations: list[dict[str, Any]],
    expected_install_dir: Path | None = None,
) -> dict[str, Any]:
    """Backward-compatible helper for verifying v1.0.0 uninstall registration."""
    return verify_baseline_uninstall_registration(
        registrations, expected_version_prefix="1.0.0", expected_install_dir=expected_install_dir
    )


def verify_target_overlay_uninstall_registration(
    baseline_reg: dict[str, Any],
    registrations: list[dict[str, Any]],
    expected_version: str = TARGET_EXPECTED_APP_VERSION,
    expected_install_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify that target upgrade updated the existing registration in-place without side-by-side duplicates."""
    if not registrations:
        raise UpgradeVerificationError(
            "No Inno Setup uninstall registration found after overlay upgrade!"
        )
    if len(registrations) > 1:
        raise UpgradeVerificationError(
            f"Multiple uninstall registrations found after overlay upgrade! "
            f"Overlay failed and installed parallel products: {registrations}"
        )
    reg = registrations[0]
    if reg["key_name"].lower() != baseline_reg["key_name"].lower():
        raise UpgradeVerificationError(
            f"AppId key name changed during upgrade! Before: '{baseline_reg['key_name']}', After: '{reg['key_name']}'"
        )
    if not reg.get("raw_values"):
        raise UpgradeVerificationError(
            f"Upgraded uninstall registration raw_values is empty for key '{reg['key_name']}'"
        )
    if "vocabulary app" not in reg.get("display_name", "").lower():
        raise UpgradeVerificationError(
            f"Upgraded uninstall DisplayName is '{reg.get('display_name')}', expected to contain 'Vocabulary App'"
        )
    if not reg.get("display_version", "").startswith(expected_version):
        raise UpgradeVerificationError(
            f"Upgraded DisplayVersion is '{reg.get('display_version')}', expected '{expected_version}'"
        )
    if not reg.get("install_location"):
        raise UpgradeVerificationError(
            f"Upgraded InstallLocation / App Path is empty in key '{reg['key_name']}'"
        )
    if expected_install_dir:
        actual_install = Path(reg["install_location"]).resolve()
        expected_install = expected_install_dir.resolve()
        if actual_install != expected_install and expected_install.name.lower() not in str(actual_install).lower():
            raise UpgradeVerificationError(
                f"Upgraded InstallLocation '{actual_install}' does not match expected '{expected_install}'"
            )
    return reg


def verify_v1_1_overlay_uninstall_registration(
    v1_0_reg: dict[str, Any],
    registrations: list[dict[str, Any]],
    expected_install_dir: Path | None = None,
) -> dict[str, Any]:
    """Backward-compatible helper for verifying v1.1.0 overlay uninstall registration."""
    # If the target being verified is 1.2.0, accept target expected version, else 1.1.0
    expected_ver = (
        registrations[0].get("display_version", "")
        if registrations and registrations[0].get("display_version", "").startswith(TARGET_EXPECTED_APP_VERSION)
        else V1_1_EXPECTED_APP_VERSION
    )
    return verify_target_overlay_uninstall_registration(
        v1_0_reg,
        registrations,
        expected_version=expected_ver,
        expected_install_dir=expected_install_dir,
    )


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
    from src import app_config, db

    db_path = data_dir / EXPECTED_DEFAULT_DB_FILENAME
    pref_path = data_dir / "preferences.json"
    backup_dir = data_dir / "backups"
    audio_dir = data_dir / "audio-cache"

    old_db_path = db.DB_PATH
    old_startup = app_config._bound_startup_paths
    old_relocated = app_config._bound_relocated_paths
    old_guarded = app_config._bound_guarded_database

    old_env = {
        "VOCAB_APP_DB_PATH": os.environ.get("VOCAB_APP_DB_PATH"),
        "VOCAB_APP_BACKUP_DIR": os.environ.get("VOCAB_APP_BACKUP_DIR"),
        "VOCAB_APP_AUDIO_CACHE_DIR": os.environ.get("VOCAB_APP_AUDIO_CACHE_DIR"),
        "VOCAB_APP_PREFERENCES_PATH": os.environ.get("VOCAB_APP_PREFERENCES_PATH"),
    }
    os.environ["VOCAB_APP_DB_PATH"] = str(db_path)
    os.environ["VOCAB_APP_BACKUP_DIR"] = str(backup_dir)
    os.environ["VOCAB_APP_AUDIO_CACHE_DIR"] = str(audio_dir)
    os.environ["VOCAB_APP_PREFERENCES_PATH"] = str(pref_path)
    app_config._bound_startup_paths = None
    app_config._bound_relocated_paths = None
    app_config._bound_guarded_database = None
    db.DB_PATH = db_path
    try:
        yield
    finally:
        db.DB_PATH = old_db_path
        app_config._bound_startup_paths = old_startup
        app_config._bound_relocated_paths = old_relocated
        app_config._bound_guarded_database = old_guarded
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def create_authentic_baseline_user_state(
    data_dir: Path,
    tag_name: str = BASELINE_RELEASE_TAG,
    expected_tag_sha: str = BASELINE_TAG_OBJECT_SHA,
    expected_commit_sha: str = BASELINE_PEELED_COMMIT_SHA,
    expected_schema_version: str = V1_1_SCHEMA_VERSION,
    expected_app_data_version: str = V1_1_APP_DATA_VERSION,
    repo_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Construct authentic baseline user state using git archive source code at baseline tag."""
    data_dir = require_isolated_verification_data_dir(data_dir)

    tag_provenance = verify_tag_provenance(
        tag_name=tag_name,
        expected_tag_sha=expected_tag_sha,
        expected_commit_sha=expected_commit_sha,
        repo_root=repo_root,
    )

    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / EXPECTED_DEFAULT_DB_FILENAME
    pref_path = data_dir / "preferences.json"
    backup_dir = data_dir / "backups"
    audio_dir = data_dir / "audio-cache"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if db_path.is_file():
        db_path.unlink()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_parent:
        archive_dir = Path(tmp_parent) / f"{tag_name.replace('.', '_')}_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        print(f"Extracting git archive at tag {tag_name} ...")
        proc_archive = subprocess.run(
            ["git", "archive", "--format=tar", tag_name],
            cwd=str(repo_root),
            capture_output=True,
            check=False,
        )
        if proc_archive.returncode != 0:
            raise UpgradeVerificationError(
                f"Failed to create git archive for {tag_name}:\n{proc_archive.stderr.decode('utf-8', errors='replace')}"
            )

        import io
        import tarfile

        with tarfile.open(fileobj=io.BytesIO(proc_archive.stdout)) as tar:
            tar.extractall(archive_dir)

        seeder_script = archive_dir / f"seed_{tag_name.replace('.', '_')}_baseline.py"
        # Determine add_entries_to_collection argument signature
        # In v1.0.0: add_entries_to_collection(collection_id=..., entry_ids=[...])
        # In v1.1.0: add_entries_to_collection(entry_ids, collection_id)
        if tag_name == V1_0_RELEASE_TAG:
            add_entries_call = "add_entries_to_collection(collection_id=sentinel_collection_id, entry_ids=[sentinel_entry_id])"
        else:
            add_entries_call = "add_entries_to_collection([sentinel_entry_id], sentinel_collection_id)"

        seeder_content = f"""
import json
import os
import sqlite3
import sys
from pathlib import Path

# Force baseline archive to the front of sys.path
sys.path.insert(0, os.getcwd())

from src.db import init_db, get_connection
from src.entries import add_entry
from src.collections import create_collection, add_entries_to_collection
from src.migrations import get_schema_version, get_metadata

# 1. Native schema initialization
init_db()

# 2. Seed sentinel entry and collection via domain APIs
sentinel_entry_id = int(add_entry(
    language="English",
    term="{SENTINEL_TERM}",
    meaning="{SENTINEL_MEANING}",
    explanation_language="English",
    entry_type="word",
    example="Authentic sentence created via {tag_name} git tag source.",
    notes="Sentinel notes.",
    tags="sentinel,upgrade_proof",
))

sentinel_collection_id = int(create_collection(
    name="{SENTINEL_COLLECTION_NAME}",
    description="Sentinel Collection created under authentic {tag_name} tag.",
))

{add_entries_call}

# 3. Read metadata and verify baseline invariants
with get_connection() as conn:
    schema_ver = get_schema_version(conn)
    app_data_ver = get_metadata(conn, "app_data_version")

# 4. Write authentic preferences.json
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
    "schema_version": schema_ver,
    "app_data_version": app_data_ver,
}}
print("BASELINE_SEED_RESULT_START" + json.dumps(result) + "BASELINE_SEED_RESULT_END")
"""
        seeder_script.write_text(seeder_content, encoding="utf-8")

        child_env = dict(os.environ)
        child_env["VOCAB_APP_DB_PATH"] = str(db_path)
        child_env["VOCAB_APP_BACKUP_DIR"] = str(backup_dir)
        child_env["VOCAB_APP_AUDIO_CACHE_DIR"] = str(audio_dir)
        child_env["VOCAB_APP_PREFERENCES_PATH"] = str(pref_path)
        child_env["PYTHONPATH"] = str(archive_dir)

        proc_seed = subprocess.run(
            [sys.executable, str(seeder_script)],
            cwd=str(archive_dir),
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc_seed.returncode != 0:
            raise UpgradeVerificationError(
                f"{tag_name} state creation failed with code {proc_seed.returncode}.\n"
                f"Stdout: {proc_seed.stdout}\nStderr: {proc_seed.stderr}"
            )

        output = proc_seed.stdout
        start_marker = "BASELINE_SEED_RESULT_START"
        end_marker = "BASELINE_SEED_RESULT_END"
        if start_marker not in output or end_marker not in output:
            raise UpgradeVerificationError(
                f"Failed to parse {tag_name} seeder output:\n{output}"
            )
        json_str = output.split(start_marker)[1].split(end_marker)[0]
        seed_data = json.loads(json_str)

    if not db_path.is_file():
        raise UpgradeVerificationError(f"Expected database missing: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        schema_row = conn.execute(
            "SELECT value FROM app_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if not schema_row or schema_row["value"] != expected_schema_version:
            raise UpgradeVerificationError(
                f"Generated DB schema is '{schema_row['value'] if schema_row else None}', "
                f"expected '{expected_schema_version}'"
            )
    finally:
        conn.close()

    db_sha = calculate_sha256(db_path)
    pref_sha = calculate_sha256(pref_path)
    print(f"Created authentic baseline user state from tag {tag_name} at {data_dir}:")
    print(f"  Database file: {db_path.name} (SHA-256: {db_sha})")
    print(f"  Preferences:   {pref_path.name} (SHA-256: {pref_sha})")

    return {
        "tag_name": tag_provenance["tag_name"],
        "tag_object_sha": tag_provenance["tag_object_sha"],
        "source_commit_sha": tag_provenance["source_commit_sha"],
        "database_filename": db_path.name,
        "sentinel_entry_id": seed_data["sentinel_entry_id"],
        "sentinel_collection_id": seed_data["sentinel_collection_id"],
        "pre_upgrade_db_sha": db_sha,
        "pre_upgrade_pref_sha": pref_sha,
        "schema_version": seed_data["schema_version"],
        "app_data_version": seed_data["app_data_version"],
        # Backwards compatibility keys
        "v1_0_tag_name": tag_provenance["tag_name"],
        "v1_0_tag_object_sha": tag_provenance["tag_object_sha"],
        "v1_0_source_commit_sha": tag_provenance["source_commit_sha"],
        "v1_0_schema_version": seed_data["schema_version"],
        "v1_0_app_data_version": seed_data["app_data_version"],
    }


def create_authentic_v1_0_user_state(
    data_dir: Path,
    repo_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Backward-compatible helper for creating v1.0.0 user state."""
    return create_authentic_baseline_user_state(
        data_dir=data_dir,
        tag_name=V1_0_RELEASE_TAG,
        expected_tag_sha=V1_0_TAG_OBJECT_SHA,
        expected_commit_sha=V1_0_PEELED_COMMIT_SHA,
        expected_schema_version=V1_0_SCHEMA_VERSION,
        expected_app_data_version=V1_0_APP_DATA_VERSION,
        repo_root=repo_root,
    )


def verify_pre_migration_backup(
    backup_dir: Path,
    prior_schema_version: str = V1_0_SCHEMA_VERSION,
) -> Path:
    """Verify that the pre-migration backup contract executed and produced a valid DB."""
    if not backup_dir.is_dir():
        raise UpgradeVerificationError(f"Backup directory missing: {backup_dir}")

    candidates = sorted(backup_dir.glob(f"vocab-pre-{prior_schema_version}-*.db"))
    if not candidates:
        raise UpgradeVerificationError(
            f"Pre-migration backup missing! No backup file matching 'vocab-pre-{prior_schema_version}-*.db' "
            f"found in {backup_dir}."
        )

    backup_file = candidates[-1]
    if backup_file.stat().st_size < 1024:
        raise UpgradeVerificationError(
            f"Pre-migration backup file {backup_file.name} is suspiciously small ({backup_file.stat().st_size} bytes)."
        )

    conn = sqlite3.connect(backup_file)
    try:
        conn.row_factory = sqlite3.Row
        from src.migrations import get_schema_version

        backup_schema = get_schema_version(conn)
        if backup_schema != prior_schema_version:
            raise UpgradeVerificationError(
                f"Backup database schema version is '{backup_schema}', expected '{prior_schema_version}'."
            )
        entry = conn.execute(
            "SELECT * FROM entries WHERE term = ?", (SENTINEL_TERM,)
        ).fetchone()
        if entry is None:
            # Also check if legacy v1_0 sentinel term was used
            entry = conn.execute(
                "SELECT * FROM entries WHERE term = ?", ("v1_0_provenance_sentinel_term",)
            ).fetchone()
        if entry is None:
            raise UpgradeVerificationError("Sentinel entry missing from pre-migration backup!")
    finally:
        conn.close()

    print(f"Pre-migration backup verified: {backup_file.name} (Schema: {backup_schema})")
    return backup_file


def verify_target_migrated_state(
    data_dir: Path,
    sentinel_info: dict[str, Any],
    expected_schema: str = TARGET_SCHEMA_VERSION,
    expected_app_data: str = TARGET_APP_DATA_VERSION,
) -> dict[str, Any]:
    """Execute target initialization/migration and verify all schema and data preservation invariants."""
    data_dir = require_isolated_verification_data_dir(data_dir)
    db_path = data_dir / EXPECTED_DEFAULT_DB_FILENAME
    pref_path = data_dir / "preferences.json"
    backup_dir = data_dir / "backups"

    if not db_path.is_file():
        raise UpgradeVerificationError(
            f"Target database file missing at production path: {db_path}"
        )

    with scoped_app_env(data_dir):
        from src.db import init_db
        from src.migrations import get_schema_version, get_metadata
        from src.entries import get_entry_by_id
        from src.collections import get_collection_by_id, get_entries_in_collection

        # 1. Run migration via standard production init_db()
        init_db()

        # 2. Check if a backup was required (only if schema differed)
        prior_schema = sentinel_info.get("schema_version") or sentinel_info.get("v1_0_schema_version")
        backup_path = None
        if prior_schema and prior_schema != expected_schema:
            backup_path = verify_pre_migration_backup(backup_dir, prior_schema_version=prior_schema)

        # 3. Verify upgraded database schema
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            schema_ver = get_schema_version(conn)
            app_data_ver = get_metadata(conn, "app_data_version")
            if schema_ver != expected_schema:
                raise UpgradeVerificationError(
                    f"Migrated database schema is '{schema_ver}', expected '{expected_schema}'"
                )
            if app_data_ver != expected_app_data:
                raise UpgradeVerificationError(
                    f"Migrated database app_data_version is '{app_data_ver}', expected '{expected_app_data}'"
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
        if not entry or entry["term"] not in (SENTINEL_TERM, "v1_0_provenance_sentinel_term"):
            raise UpgradeVerificationError(
                f"Sentinel entry corrupted or missing after migration! Found: {entry}"
            )

        collection = get_collection_by_id(sentinel_info["sentinel_collection_id"])
        if not collection or collection["name"] not in (SENTINEL_COLLECTION_NAME, "v1_0_Upgrade_Sentinel_Collection"):
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
        if prefs.get(SENTINEL_PREF_KEY) != SENTINEL_PREF_VAL and prefs.get("v1_0_sentinel_pref_flag") != "v1.0-verified-safe-upgrade-sentinel":
            raise UpgradeVerificationError(
                f"Preferences sentinel corrupted or missing! Found: {prefs}"
            )
        if prefs.get("theme") != "dark":
            raise UpgradeVerificationError(
                f"Preferences 'theme' key corrupted! Found: {prefs}"
            )

    print("Migration and data preservation invariants fully verified:")
    print(f"  Schema: {schema_ver} (app_data_version: {app_data_ver})")
    print(f"  Sentinel Entry: ID {entry['id']} '{entry['term']}' (PRESERVED)")
    print(f"  Sentinel Collection: ID {collection['id']} '{collection['name']}' (PRESERVED)")
    print(f"  Sentinel Prefs: PRESERVED")

    res = {
        "migrated_schema_version": schema_ver,
        "migrated_app_data_version": app_data_ver,
        "post_migration_db_sha256": calculate_sha256(db_path),
    }
    if backup_path:
        res["backup_path"] = str(backup_path)
        res["backup_sha256"] = calculate_sha256(backup_path)
    return res


def verify_v1_1_migrated_state(
    data_dir: Path,
    sentinel_info: dict[str, Any],
) -> dict[str, Any]:
    """Backward-compatible helper for verifying v1.1 migrated state."""
    return verify_target_migrated_state(
        data_dir=data_dir,
        sentinel_info=sentinel_info,
        expected_schema=TARGET_SCHEMA_VERSION,
        expected_app_data=TARGET_APP_DATA_VERSION,
    )


def verify_installed_smoke(installed_exe: Path) -> None:
    """Run startup/import smoke test against installed executable."""
    print(f"Running startup smoke test on installed executable: {installed_exe} ...")
    proc_smoke = subprocess.run(
        [str(installed_exe), "--smoke-test"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if proc_smoke.returncode != 0 or "PACKAGED_SMOKE_TEST_PASSED" not in proc_smoke.stdout:
        raise UpgradeVerificationError(
            f"Installed executable failed startup smoke test (exit {proc_smoke.returncode})!\n"
            f"Stdout: {proc_smoke.stdout}\nStderr: {proc_smoke.stderr}"
        )
    print("Installed executable startup smoke test: PASSED (all runtime modules loaded cleanly)")


def run_full_upgrade_verification(
    baseline_installer_path: Path | None = None,
    target_installer_path: Path | None = None,
    data_dir: Path | None = None,
    install_dir: Path | None = None,
    report_path: Path | None = None,
    skip_installer_execution: bool = False,
    repo_root: Path = PROJECT_ROOT,
    baseline_tag: str = BASELINE_RELEASE_TAG,
    baseline_tag_sha: str = BASELINE_TAG_OBJECT_SHA,
    baseline_commit_sha: str = BASELINE_PEELED_COMMIT_SHA,
    baseline_known_sha: str = BASELINE_KNOWN_SHA256,
    target_expected_version: str = TARGET_EXPECTED_APP_VERSION,
    target_expected_file_ver: str = TARGET_EXPECTED_FILE_VERSION,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute full automated baseline -> target upgrade & data-safety verification pipeline."""
    # Backwards-compatibility argument handling
    if baseline_installer_path is None and "v1_installer_path" in kwargs:
        baseline_installer_path = kwargs["v1_installer_path"]
        baseline_tag = V1_0_RELEASE_TAG
        baseline_tag_sha = V1_0_TAG_OBJECT_SHA
        baseline_commit_sha = V1_0_PEELED_COMMIT_SHA
        baseline_known_sha = V1_0_KNOWN_SHA256
    if target_installer_path is None and "v1_1_installer_path" in kwargs:
        target_installer_path = kwargs["v1_1_installer_path"]

    if baseline_installer_path is None or target_installer_path is None or data_dir is None:
        raise ValueError("baseline_installer_path, target_installer_path, and data_dir are required")

    data_dir = require_isolated_verification_data_dir(data_dir)
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline_release_tag": baseline_tag,
        "baseline_tag_object_sha": baseline_tag_sha,
        "baseline_source_commit_sha": baseline_commit_sha,
        "baseline_expected_installer_sha256": baseline_known_sha,
        "target_expected_app_version": target_expected_version,
        "target_expected_file_version": target_expected_file_ver,
        "target_database_filename": EXPECTED_DEFAULT_DB_FILENAME,
        "inno_app_id": INNO_APP_ID,
        "inno_uninstall_key": INNO_UNINSTALL_KEY_NAME,
        "data_dir": str(data_dir),
        "install_dir": str(install_dir),
        "stages": {},
        # Backwards compatibility keys
        "v1_0_release_tag": baseline_tag,
        "v1_0_tag_object_sha": baseline_tag_sha,
        "v1_0_source_commit_sha": baseline_commit_sha,
        "v1_0_expected_installer_sha256": baseline_known_sha,
    }

    # Step 0: Check baseline installer SHA-256
    if baseline_tag == V1_0_RELEASE_TAG:
        b_sha = verify_v1_installer_sha256(baseline_installer_path)
    else:
        b_sha = verify_installer_sha256(baseline_installer_path, expected_sha=baseline_known_sha)
    report["baseline_installer_path"] = str(baseline_installer_path)
    report["baseline_installer_sha256"] = b_sha
    print(f"Baseline installer verified: {baseline_installer_path} (SHA-256 match)")

    installed_exe = install_dir / "Vocabulary App.exe"

    if not skip_installer_execution:
        # Step 1: Clean install baseline
        print(f"\n=== Step 1: Installing baseline ({baseline_tag}) ===")
        run_silent_installer(baseline_installer_path)
        base_meta = get_windows_exe_version(installed_exe)
        print(f"Installed baseline EXE metadata: {base_meta}")
        report["baseline_installed_metadata"] = base_meta

        # Verify baseline Inno uninstall registration
        base_regs = get_inno_uninstall_registrations(INNO_APP_ID)
        version_prefix = "1.0.0" if baseline_tag == V1_0_RELEASE_TAG else "1.1.0"
        base_reg = verify_baseline_uninstall_registration(
            base_regs, expected_version_prefix=version_prefix, expected_install_dir=install_dir
        )
        print(f"Verified baseline Inno uninstall registration: {base_reg['key_name']} ({base_reg['display_version']})")
        report["baseline_uninstall_registration"] = base_reg

    # Step 2: Seed authentic user state using git tag
    print(f"\n=== Step 2: Seeding Authentic User State from tag {baseline_tag} ===")
    baseline_schema = V1_0_SCHEMA_VERSION if baseline_tag == V1_0_RELEASE_TAG else V1_1_SCHEMA_VERSION
    baseline_app_data = V1_0_APP_DATA_VERSION if baseline_tag == V1_0_RELEASE_TAG else V1_1_APP_DATA_VERSION
    sentinel_info = create_authentic_baseline_user_state(
        data_dir,
        tag_name=baseline_tag,
        expected_tag_sha=baseline_tag_sha,
        expected_commit_sha=baseline_commit_sha,
        expected_schema_version=baseline_schema,
        expected_app_data_version=baseline_app_data,
        repo_root=repo_root,
    )
    report["baseline_user_state"] = sentinel_info
    report["v1_0_user_state"] = sentinel_info

    if not skip_installer_execution:
        # Step 3: Overlay upgrade to target
        print(f"\n=== Step 3: Overlay Upgrading to target ({target_expected_version}) ===")
        run_silent_installer(target_installer_path)
        target_meta = get_windows_exe_version(installed_exe)
        print(f"Upgraded EXE metadata: {target_meta}")
        if not target_meta["ProductVersion"].startswith(target_expected_version):
            raise UpgradeVerificationError(
                f"Upgraded EXE ProductVersion is '{target_meta['ProductVersion']}', expected '{target_expected_version}'"
            )
        if not target_meta["FileVersion"].startswith(target_expected_file_ver):
            raise UpgradeVerificationError(
                f"Upgraded EXE FileVersion is '{target_meta['FileVersion']}', expected '{target_expected_file_ver}'"
            )
        report["target_installed_metadata"] = target_meta

        # Verify installed executable runs startup import smoke test
        verify_installed_smoke(installed_exe)

        # Verify Inno uninstall registration is updated in-place (overlay, not parallel)
        target_regs = get_inno_uninstall_registrations(INNO_APP_ID)
        target_reg = verify_target_overlay_uninstall_registration(
            base_reg,
            target_regs,
            expected_version=target_expected_version,
            expected_install_dir=install_dir,
        )
        print(f"Verified overlay uninstall registration: {target_reg['key_name']} ({target_reg['display_version']})")
        report["target_uninstall_registration"] = target_reg

        # Verify user state files were not wiped by Inno Setup
        db_path = data_dir / EXPECTED_DEFAULT_DB_FILENAME
        pref_path = data_dir / "preferences.json"
        if not db_path.is_file() or not pref_path.is_file():
            raise UpgradeVerificationError(
                f"Target installer erased user data files in {data_dir}!"
            )

    # Step 4: Run migration and verify data preservation
    print("\n=== Step 4: Verifying Schema Migration & Data Preservation ===")
    migration_result = verify_target_migrated_state(data_dir, sentinel_info)
    report["migration_and_data_preservation"] = migration_result

    report["overall_status"] = "PASSED"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nUpgrade verification report written to: {report_path}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Baseline -> Target Upgrade and Data-Preservation Proof."
    )
    parser.add_argument(
        "--baseline-installer",
        "--v1-installer",
        dest="baseline_installer",
        type=Path,
        default=None,
        help="Path to official baseline installer (downloaded automatically if omitted).",
    )
    parser.add_argument(
        "--target-installer",
        "--v1-2-installer",
        "--v1-1-installer",
        dest="target_installer",
        type=Path,
        default=Path("dist/installer/VocabularyApp-Setup-1.2.0.exe"),
        help="Path to built target installer (defaults to 1.2.0 installer).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Explicit isolated user-data directory outside %%LOCALAPPDATA%%\\vocabulary_app.",
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

    try:
        data_dir = require_isolated_verification_data_dir(args.data_dir)
    except UpgradeVerificationError as exc:
        print(f"[FAILED] Unsafe upgrade verification target: {exc}", file=sys.stderr)
        return 1

    # Resolve baseline installer
    download_dir = PROJECT_ROOT / "dist" / "baseline_installer"
    try:
        baseline_installer = ensure_baseline_installer(download_dir, args.baseline_installer)
    except Exception as exc:
        print(f"[FAILED] Failed to prepare baseline installer: {exc}", file=sys.stderr)
        return 1

    target_installer = args.target_installer
    if not args.skip_installer_execution and not target_installer.is_file():
        print(f"[FAILED] Target installer not found: {target_installer}", file=sys.stderr)
        return 1

    install_dir = args.install_dir or get_default_programs_install_dir()

    try:
        run_full_upgrade_verification(
            baseline_installer_path=baseline_installer,
            target_installer_path=target_installer,
            data_dir=data_dir,
            install_dir=install_dir,
            report_path=args.report_path,
            skip_installer_execution=args.skip_installer_execution,
            repo_root=PROJECT_ROOT,
        )
        print("\n=======================================================")
        print("[OK] UPGRADE & DATA-PRESERVATION PROOF: PASSED")
        print("=======================================================")
        return 0
    except UpgradeVerificationError as err:
        print(f"\n[FAILED] UPGRADE PROOF FAILED: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

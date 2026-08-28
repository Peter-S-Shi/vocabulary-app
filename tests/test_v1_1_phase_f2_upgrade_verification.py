"""Unit tests for Phase F2 upgrade & data-preservation verification harness."""

from __future__ import annotations

import gc
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.app_config import get_default_data_dir, get_default_db_path
from winbuild.verify_upgrade import (
    EXPECTED_DEFAULT_DB_FILENAME,
    INNO_APP_ID,
    INNO_UNINSTALL_KEY_NAME,
    SENTINEL_COLLECTION_NAME,
    SENTINEL_MEANING,
    SENTINEL_PREF_KEY,
    SENTINEL_PREF_VAL,
    SENTINEL_TERM,
    V1_0_APP_DATA_VERSION,
    V1_0_KNOWN_SHA256,
    V1_0_RELEASE_TAG,
    V1_0_SCHEMA_VERSION,
    V1_1_APP_DATA_VERSION,
    V1_1_SCHEMA_VERSION,
    UpgradeVerificationError,
    calculate_sha256,
    create_authentic_v1_0_user_state,
    run_full_upgrade_verification,
    verify_pre_migration_backup,
    verify_v1_0_uninstall_registration,
    verify_v1_1_migrated_state,
    verify_v1_1_overlay_uninstall_registration,
    verify_v1_installer_sha256,
)


class UpgradeVerificationHarnessTests(unittest.TestCase):
    def tearDown(self) -> None:
        gc.collect()

    def test_default_database_filename_and_data_dir_regressions(self) -> None:
        """Lock down production database filename as vocab.db (never vocabulary.db)."""
        default_db = get_default_db_path()
        self.assertEqual(default_db.name, EXPECTED_DEFAULT_DB_FILENAME)
        self.assertEqual(default_db.name, "vocab.db")
        self.assertNotEqual(default_db.name, "vocabulary.db")

        default_dir = get_default_data_dir()
        self.assertEqual(default_dir.name, "vocabulary_app")
        self.assertEqual(default_db.parent, default_dir)

    def test_sha256_calculation_and_v1_installer_sha_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sample_file = tmp_path / "sample.txt"
            sample_file.write_bytes(b"hello world\n")
            self.assertEqual(
                calculate_sha256(sample_file),
                "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447",
            )

            # Test invalid v1 installer sha rejection
            fake_installer = tmp_path / "fake_installer.exe"
            fake_installer.write_bytes(b"corrupted binary")
            with self.assertRaises(UpgradeVerificationError):
                verify_v1_installer_sha256(fake_installer)

    def test_inno_uninstall_registration_verification_rules(self) -> None:
        """Verify uninstall registration single-instance and overlay validation logic."""
        # 1. Empty registrations list raises error
        with self.assertRaises(UpgradeVerificationError):
            verify_v1_0_uninstall_registration([])

        # 2. Valid v1.0.0 registration
        v1_valid = [{
            "hive": "HKCU",
            "key_name": INNO_UNINSTALL_KEY_NAME,
            "display_name": "Vocabulary App",
            "display_version": "1.0.0",
            "install_location": r"C:\Users\test\AppData\Local\Programs\Vocabulary App",
        }]
        reg = verify_v1_0_uninstall_registration(v1_valid)
        self.assertEqual(reg["display_version"], "1.0.0")

        # 3. Multiple registrations for v1.0 raises error
        with self.assertRaises(UpgradeVerificationError):
            verify_v1_0_uninstall_registration([v1_valid[0], v1_valid[0]])

        # 4. Valid v1.1.0 overlay registration
        v1_1_valid = [{
            "hive": "HKCU",
            "key_name": INNO_UNINSTALL_KEY_NAME,
            "display_name": "Vocabulary App",
            "display_version": "1.1.0",
            "install_location": r"C:\Users\test\AppData\Local\Programs\Vocabulary App",
        }]
        overlay_reg = verify_v1_1_overlay_uninstall_registration(v1_valid[0], v1_1_valid)
        self.assertEqual(overlay_reg["display_version"], "1.1.0")

        # 5. Parallel/duplicate product registration raises error
        parallel_reg = [
            v1_valid[0],
            {
                "hive": "HKCU",
                "key_name": "{ANOTHER_APP_ID}_is1",
                "display_name": "Vocabulary App 1.1",
                "display_version": "1.1.0",
                "install_location": r"C:\Users\test\AppData\Local\Programs\Vocabulary App 1.1",
            },
        ]
        with self.assertRaises(UpgradeVerificationError):
            verify_v1_1_overlay_uninstall_registration(v1_valid[0], parallel_reg)

    def test_authentic_v1_0_state_creation_from_git_tag_and_migration_preservation(self) -> None:
        """Verify authentic state creation from git tag v1.0.0 into vocab.db and migration to v1.1.0."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_dir = Path(tmp)
            sentinel_info = create_authentic_v1_0_user_state(data_dir)

            db_path = data_dir / "vocab.db"
            pref_path = data_dir / "preferences.json"
            self.assertTrue(db_path.is_file())
            self.assertTrue(pref_path.is_file())
            self.assertEqual(sentinel_info["database_filename"], "vocab.db")
            self.assertEqual(sentinel_info["v1_0_source_tag"], V1_0_RELEASE_TAG)

            # Verify authentic v1.0.0 schema state in vocab.db
            conn = sqlite3.connect(db_path)
            try:
                conn.row_factory = sqlite3.Row
                schema_row = conn.execute(
                    "SELECT value FROM app_metadata WHERE key = 'schema_version'"
                ).fetchone()
                self.assertEqual(schema_row["value"], V1_0_SCHEMA_VERSION)
                has_schedules = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_review_schedules'"
                ).fetchone()
                self.assertIsNone(has_schedules)
            finally:
                conn.close()

            # Verify migration and backup contract against authentic vocab.db
            result = verify_v1_1_migrated_state(data_dir, sentinel_info)
            self.assertEqual(result["migrated_schema_version"], V1_1_SCHEMA_VERSION)
            self.assertEqual(result["migrated_app_data_version"], V1_1_APP_DATA_VERSION)

            # Verify pre-migration backup file
            backup_path = Path(result["backup_path"])
            self.assertTrue(backup_path.is_file())
            self.assertIn(f"vocab-pre-{V1_0_SCHEMA_VERSION}-", backup_path.name)

            # Verify backup content
            conn = sqlite3.connect(backup_path)
            try:
                conn.row_factory = sqlite3.Row
                schema_row = conn.execute(
                    "SELECT value FROM app_metadata WHERE key = 'schema_version'"
                ).fetchone()
                self.assertEqual(schema_row["value"], V1_0_SCHEMA_VERSION)
                entry_row = conn.execute(
                    "SELECT * FROM entries WHERE term = ?", (SENTINEL_TERM,)
                ).fetchone()
                self.assertIsNotNone(entry_row)
                self.assertEqual(entry_row["meaning"], SENTINEL_MEANING)
            finally:
                conn.close()

            # Verify post-migration database has schedules table and intact sentinel data
            conn = sqlite3.connect(db_path)
            try:
                conn.row_factory = sqlite3.Row
                has_schedules = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_review_schedules'"
                ).fetchone()
                self.assertIsNotNone(has_schedules)
            finally:
                conn.close()

            # Verify preferences
            prefs = json.loads(pref_path.read_text(encoding="utf-8"))
            self.assertEqual(prefs[SENTINEL_PREF_KEY], SENTINEL_PREF_VAL)
            self.assertEqual(prefs["theme"], "dark")
            gc.collect()

    def test_run_full_upgrade_verification_pipeline_mocked(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            v1_installer = tmp_path / "VocabularyApp-Setup-1.0.0.exe"
            v1_1_installer = tmp_path / "VocabularyApp-Setup-1.1.0.exe"
            data_dir = tmp_path / "user_data"
            install_dir = tmp_path / "programs"
            report_path = tmp_path / "report.json"

            v1_installer.write_bytes(b"v1_installer_mock_binary")
            v1_1_installer.write_bytes(b"v1_1_installer_mock_binary")

            v1_meta = {"ProductVersion": "1.0.0", "FileVersion": "1.0.0.0"}
            v1_1_meta = {"ProductVersion": "1.1.0", "FileVersion": "1.1.0.0"}

            call_count = 0

            def mock_get_exe_version(exe_path: Path) -> dict[str, str]:
                nonlocal call_count
                call_count += 1
                return v1_meta if call_count == 1 else v1_1_meta

            v1_reg_mock = [{
                "hive": "HKCU",
                "key_name": INNO_UNINSTALL_KEY_NAME,
                "display_name": "Vocabulary App",
                "display_version": "1.0.0",
                "install_location": str(install_dir),
            }]
            v1_1_reg_mock = [{
                "hive": "HKCU",
                "key_name": INNO_UNINSTALL_KEY_NAME,
                "display_name": "Vocabulary App",
                "display_version": "1.1.0",
                "install_location": str(install_dir),
            }]
            reg_call_count = 0

            def mock_get_registrations(app_id: str = INNO_APP_ID, app_name: str = "Vocabulary App"):
                nonlocal reg_call_count
                reg_call_count += 1
                return v1_reg_mock if reg_call_count == 1 else v1_1_reg_mock

            with patch("winbuild.verify_upgrade.verify_v1_installer_sha256", return_value=V1_0_KNOWN_SHA256), \
                    patch("winbuild.verify_upgrade.run_silent_installer"), \
                    patch("winbuild.verify_upgrade.get_windows_exe_version", side_effect=mock_get_exe_version), \
                    patch("winbuild.verify_upgrade.get_inno_uninstall_registrations", side_effect=mock_get_registrations):
                report = run_full_upgrade_verification(
                    v1_installer_path=v1_installer,
                    v1_1_installer_path=v1_1_installer,
                    data_dir=data_dir,
                    install_dir=install_dir,
                    report_path=report_path,
                    skip_installer_execution=False,
                )

            self.assertEqual(report["overall_status"], "PASSED")
            self.assertEqual(report["target_database_filename"], "vocab.db")
            self.assertTrue(report_path.is_file())
            report_json = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(
                report_json["migration_and_data_preservation"]["migrated_schema_version"],
                V1_1_SCHEMA_VERSION,
            )
            gc.collect()


if __name__ == "__main__":
    unittest.main()
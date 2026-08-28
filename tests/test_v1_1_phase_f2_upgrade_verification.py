"""Unit tests for Phase F2 upgrade & data-preservation verification harness."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from winbuild.verify_upgrade import (
    SENTINEL_COLLECTION_NAME,
    SENTINEL_MEANING,
    SENTINEL_PREF_KEY,
    SENTINEL_PREF_VAL,
    SENTINEL_TERM,
    V1_0_APP_DATA_VERSION,
    V1_0_EXPECTED_SHA256,
    V1_0_SCHEMA_VERSION,
    V1_1_APP_DATA_VERSION,
    V1_1_SCHEMA_VERSION,
    UpgradeVerificationError,
    calculate_sha256,
    create_v1_0_user_state,
    run_full_upgrade_verification,
    verify_pre_migration_backup,
    verify_v1_1_migrated_state,
    verify_v1_installer_sha256,
)


class UpgradeVerificationHarnessTests(unittest.TestCase):
    def tearDown(self) -> None:
        import gc
        gc.collect()

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

    def test_v1_0_user_state_creation_and_migration_preservation(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_dir = Path(tmp)
            sentinel_info = create_v1_0_user_state(data_dir)

            db_path = data_dir / "vocabulary.db"
            pref_path = data_dir / "preferences.json"
            self.assertTrue(db_path.is_file())
            self.assertTrue(pref_path.is_file())

            # Verify pre-migration schema state
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

            # Verify migration and backup contract
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
            import gc
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

            with patch("winbuild.verify_upgrade.verify_v1_installer_sha256"), \
                    patch("winbuild.verify_upgrade.run_silent_installer"), \
                    patch("winbuild.verify_upgrade.get_windows_exe_version", side_effect=mock_get_exe_version):
                report = run_full_upgrade_verification(
                    v1_installer_path=v1_installer,
                    v1_1_installer_path=v1_1_installer,
                    data_dir=data_dir,
                    install_dir=install_dir,
                    report_path=report_path,
                    skip_installer_execution=False,
                )

            self.assertEqual(report["overall_status"], "PASSED")
            self.assertTrue(report_path.is_file())
            report_json = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report_json["migration_and_data_preservation"]["migrated_schema_version"], V1_1_SCHEMA_VERSION)
            import gc
            gc.collect()


if __name__ == "__main__":
    unittest.main()
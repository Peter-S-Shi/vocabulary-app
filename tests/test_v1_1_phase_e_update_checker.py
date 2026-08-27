from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from src.app_config import APP_VERSION
from src.update_checker import (
    PYSIDE6_AVAILABLE,
    SemVer,
    UpdateCheckResult,
    UpdateCheckState,
    check_for_updates,
    extract_highest_stable_release,
)

if PYSIDE6_AVAILABLE:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QSignalSpy
    from src.update_checker import UpdateAwarenessService, UpdateCheckWorker


class SemVerTests(unittest.TestCase):
    def test_semver_parse_valid_variants(self) -> None:
        v1 = SemVer.parse("1.1.0")
        self.assertIsNotNone(v1)
        self.assertEqual((v1.major, v1.minor, v1.patch), (1, 1, 0))
        self.assertEqual(v1.prerelease, "")
        self.assertFalse(v1.is_prerelease)
        self.assertEqual(v1.to_version_string(), "1.1.0")

        # 'v' and 'V' prefix
        v2 = SemVer.parse("v1.2.3")
        self.assertIsNotNone(v2)
        self.assertEqual((v2.major, v2.minor, v2.patch), (1, 2, 3))

        v3 = SemVer.parse("V2.0.0")
        self.assertIsNotNone(v3)
        self.assertEqual((v3.major, v3.minor, v3.patch), (2, 0, 0))

        # Two-part short version (1.2 -> 1.2.0)
        v4 = SemVer.parse("v1.2")
        self.assertIsNotNone(v4)
        self.assertEqual((v4.major, v4.minor, v4.patch), (1, 2, 0))

        # Single part (2 -> 2.0.0)
        v5 = SemVer.parse("2")
        self.assertIsNotNone(v5)
        self.assertEqual((v5.major, v5.minor, v5.patch), (2, 0, 0))

        # Prerelease tag
        v6 = SemVer.parse("v1.1.0-beta.1")
        self.assertIsNotNone(v6)
        self.assertTrue(v6.is_prerelease)
        self.assertEqual(v6.prerelease, "beta.1")
        self.assertEqual(v6.to_version_string(), "1.1.0-beta.1")

        # Build metadata
        v7 = SemVer.parse("1.0.0+build.42")
        self.assertIsNotNone(v7)
        self.assertEqual(v7.build, "build.42")
        self.assertEqual(v7.to_version_string(), "1.0.0")

    def test_semver_parse_invalid_inputs_return_none(self) -> None:
        invalid_cases = [
            None,
            "",
            "   ",
            "abc",
            "v",
            "1.2.3.4",
            "-1.0.0",
            "1.-2.0",
            "v1.x.3",
            {},
            [],
        ]
        for item in invalid_cases:
            self.assertIsNone(SemVer.parse(item), f"Expected None for {item!r}")

    def test_semver_comparison_ordering(self) -> None:
        v1_0_0 = SemVer.parse("1.0.0")
        v1_0_1 = SemVer.parse("v1.0.1")
        v1_0_9 = SemVer.parse("1.0.9")
        v1_1_0 = SemVer.parse("v1.1.0")
        v1_1_0_dup = SemVer.parse("1.1.0")
        v1_2_0 = SemVer.parse("1.2.0")
        v2_0_0 = SemVer.parse("v2.0.0")

        self.assertTrue(v1_0_0 < v1_0_1)
        self.assertTrue(v1_0_1 < v1_0_9)
        self.assertTrue(v1_0_9 < v1_1_0)
        self.assertTrue(v1_1_0 < v1_2_0)
        self.assertTrue(v1_2_0 < v2_0_0)

        # Equality
        self.assertEqual(v1_1_0, v1_1_0_dup)
        self.assertTrue(v1_1_0 <= v1_1_0_dup)
        self.assertTrue(v1_1_0 >= v1_1_0_dup)
        self.assertFalse(v1_1_0 < v1_1_0_dup)
        self.assertFalse(v1_1_0 > v1_1_0_dup)

        # Prerelease precedence: normal version > prerelease
        v_beta = SemVer.parse("1.1.0-beta")
        v_rc = SemVer.parse("1.1.0-rc.1")
        self.assertTrue(v_beta < v1_1_0)
        self.assertTrue(v_rc < v1_1_0)
        self.assertTrue(v_beta < v_rc)
        self.assertFalse(v1_1_0 < v_beta)


class ReleaseFilteringTests(unittest.TestCase):
    def test_extract_highest_stable_release_filters_drafts_and_prereleases(self) -> None:
        payload = [
            {
                "tag_name": "v1.3.0",
                "name": "v1.3.0 Draft",
                "draft": True,
                "prerelease": False,
            },
            {
                "tag_name": "v1.2.0-beta.1",
                "name": "v1.2.0 Beta 1",
                "draft": False,
                "prerelease": True,
            },
            {
                "tag_name": "v1.2.0-rc1",
                "name": "v1.2.0 Release Candidate",
                "draft": False,
                "prerelease": False,  # Even if prerelease flag is False, tag has prerelease suffix
            },
            {
                "tag_name": "v1.1.0",
                "name": "Vocabulary App v1.1.0",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.1.0",
            },
            {
                "tag_name": "v1.0.0",
                "name": "Vocabulary App v1.0.0",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.0.0",
            },
            {
                "tag_name": "invalid-tag-format",
                "draft": False,
                "prerelease": False,
            },
        ]

        highest = extract_highest_stable_release(payload)
        self.assertIsNotNone(highest)
        self.assertEqual(highest["tag_name"], "v1.1.0")

    def test_extract_highest_stable_release_handles_empty_or_all_prerelease(self) -> None:
        self.assertIsNone(extract_highest_stable_release([]))
        self.assertIsNone(extract_highest_stable_release(None))
        self.assertIsNone(extract_highest_stable_release({"invalid": "dict"}))

        prerelease_only = [
            {"tag_name": "v1.1.0-alpha", "draft": False, "prerelease": True},
            {"tag_name": "v1.2.0-beta", "draft": True, "prerelease": False},
        ]
        self.assertIsNone(extract_highest_stable_release(prerelease_only))


class UpdateCheckerEngineTests(unittest.TestCase):
    def test_check_for_updates_detects_update_available(self) -> None:
        payload = [
            {
                "tag_name": "v1.1.0",
                "name": "Vocabulary App v1.1.0 - Theme Customization",
                "body": "## What's New in v1.1.0\n- Theme customization\n- Bug fixes",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.1.0",
                "published_at": "2026-08-27T12:00:00Z",
            }
        ]

        def fake_fetcher(url: str, timeout: float):
            return 200, json.dumps(payload).encode("utf-8"), {}

        result = check_for_updates(
            current_version="1.0.0",
            fetcher=fake_fetcher,
        )

        self.assertEqual(result.state, UpdateCheckState.UPDATE_AVAILABLE)
        self.assertTrue(result.has_update)
        self.assertTrue(result.is_success)
        self.assertEqual(result.current_version, "1.0.0")
        self.assertEqual(result.latest_version, "1.1.0")
        self.assertEqual(result.release_url, "https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.1.0")
        self.assertEqual(result.release_title, "Vocabulary App v1.1.0 - Theme Customization")
        self.assertIn("Theme customization", result.release_notes)
        self.assertIsNotNone(result.checked_at)
        self.assertIsNone(result.error_message)

    def test_check_for_updates_reports_up_to_date_when_equal_or_ahead(self) -> None:
        payload = [
            {
                "tag_name": "v1.1.0",
                "name": "Release 1.1.0",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.1.0",
            }
        ]

        def fake_fetcher(url: str, timeout: float):
            return 200, json.dumps(payload).encode("utf-8"), {}

        # Case 1: Same version
        result_same = check_for_updates(current_version="1.1.0", fetcher=fake_fetcher)
        self.assertEqual(result_same.state, UpdateCheckState.UP_TO_DATE)
        self.assertFalse(result_same.has_update)
        self.assertTrue(result_same.is_success)
        self.assertEqual(result_same.latest_version, "1.1.0")

        # Case 2: Local version is newer (e.g. dev build 1.2.0)
        result_ahead = check_for_updates(current_version="1.2.0", fetcher=fake_fetcher)
        self.assertEqual(result_ahead.state, UpdateCheckState.UP_TO_DATE)
        self.assertFalse(result_ahead.has_update)

    def test_check_for_updates_ignores_drafts_and_prereleases(self) -> None:
        payload = [
            {
                "tag_name": "v2.0.0-beta.1",
                "name": "v2.0.0 Beta",
                "draft": False,
                "prerelease": True,
            },
            {
                "tag_name": "v1.1.0",
                "name": "v1.1.0 Stable",
                "draft": False,
                "prerelease": False,
            },
        ]

        def fake_fetcher(url: str, timeout: float):
            return 200, json.dumps(payload).encode("utf-8"), {}

        result = check_for_updates(current_version="1.1.0", fetcher=fake_fetcher)
        self.assertEqual(result.state, UpdateCheckState.UP_TO_DATE)
        self.assertEqual(result.latest_version, "1.1.0")

    def test_failure_isolation_network_timeout(self) -> None:
        def timeout_fetcher(url: str, timeout: float):
            raise TimeoutError("Socket connection timed out")

        result = check_for_updates(current_version="1.0.0", fetcher=timeout_fetcher)
        self.assertEqual(result.state, UpdateCheckState.CHECK_FAILED)
        self.assertFalse(result.has_update)
        self.assertFalse(result.is_success)
        self.assertIn("timed out", result.error_message.lower())
        self.assertIsNotNone(result.checked_at)

    def test_failure_isolation_http_403_rate_limit(self) -> None:
        def rate_limit_fetcher(url: str, timeout: float):
            raise urllib.error.HTTPError(
                url=url,
                code=403,
                msg="rate limit exceeded",
                hdrs=MagicMock(),
                fp=None,
            )

        result = check_for_updates(current_version="1.0.0", fetcher=rate_limit_fetcher)
        self.assertEqual(result.state, UpdateCheckState.CHECK_FAILED)
        self.assertIn("rate limit", result.error_message.lower())

    def test_failure_isolation_http_404_not_found(self) -> None:
        def not_found_fetcher(url: str, timeout: float):
            raise urllib.error.HTTPError(
                url=url,
                code=404,
                msg="Not Found",
                hdrs=MagicMock(),
                fp=None,
            )

        result = check_for_updates(current_version="1.0.0", fetcher=not_found_fetcher)
        self.assertEqual(result.state, UpdateCheckState.CHECK_FAILED)
        self.assertIn("not found", result.error_message.lower())

    def test_failure_isolation_corrupted_json_response(self) -> None:
        def corrupt_fetcher(url: str, timeout: float):
            return 200, b"<html>502 Bad Gateway</html>", {}

        result = check_for_updates(current_version="1.0.0", fetcher=corrupt_fetcher)
        self.assertEqual(result.state, UpdateCheckState.CHECK_FAILED)
        self.assertIn("Failed to parse release payload", result.error_message)

    def test_failure_isolation_invalid_local_app_version(self) -> None:
        result = check_for_updates(current_version="invalid-version-string")
        self.assertEqual(result.state, UpdateCheckState.CHECK_FAILED)
        self.assertIn("Invalid local version", result.error_message)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class UpdateAwarenessAsyncServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_service_initial_state(self) -> None:
        service = UpdateAwarenessService(current_version="1.0.0")
        self.assertEqual(service.current_result().state, UpdateCheckState.NOT_CHECKED)
        self.assertFalse(service.is_checking())

    def test_service_async_execution_and_signal_emission(self) -> None:
        payload = [
            {
                "tag_name": "v1.2.0",
                "name": "Vocabulary App v1.2.0",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0",
            }
        ]

        def fake_fetcher(url: str, timeout: float):
            return 200, json.dumps(payload).encode("utf-8"), {}

        service = UpdateAwarenessService(
            current_version="1.0.0",
            fetcher=fake_fetcher,
        )

        spy = QSignalSpy(service.state_changed)
        service.check_for_updates()

        # Should emit CHECKING first
        self.assertTrue(service.is_checking() or spy.count() >= 1)

        # Wait for worker thread to finish
        if service._active_worker is not None:
            service._active_worker.wait(5000)

        # Process Qt events
        QApplication.processEvents()

        self.assertFalse(service.is_checking())
        result = service.current_result()
        self.assertEqual(result.state, UpdateCheckState.UPDATE_AVAILABLE)
        self.assertEqual(result.latest_version, "1.2.0")
        self.assertGreaterEqual(spy.count(), 2)  # CHECKING + UPDATE_AVAILABLE


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import time
import unittest
import urllib.error
from unittest.mock import MagicMock

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
    def test_semver_parse_valid_canonical_variants(self) -> None:
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

        # Prerelease tag
        v4 = SemVer.parse("v1.1.0-beta.1")
        self.assertIsNotNone(v4)
        self.assertTrue(v4.is_prerelease)
        self.assertEqual(v4.prerelease, "beta.1")
        self.assertEqual(v4.to_version_string(), "1.1.0-beta.1")

        # Build metadata
        v5 = SemVer.parse("1.0.0+build.42")
        self.assertIsNotNone(v5)
        self.assertEqual(v5.build, "build.42")
        self.assertEqual(v5.to_version_string(), "1.0.0")

        # Prerelease + Build metadata
        v6 = SemVer.parse("v1.1.0-rc.2+sha.abcdef")
        self.assertIsNotNone(v6)
        self.assertEqual(v6.prerelease, "rc.2")
        self.assertEqual(v6.build, "sha.abcdef")

    def test_semver_parse_rejects_non_standard_short_versions(self) -> None:
        short_cases = [
            "1",
            "v1",
            "1.2",
            "v1.2",
            "V1.0",
            "1.0.0.0",
            "1.2.3.4",
        ]
        for item in short_cases:
            self.assertIsNone(SemVer.parse(item), f"Expected None for non-standard version '{item}'")

    def test_semver_parse_rejects_malformed_tags_and_dangling_delimiters(self) -> None:
        malformed_cases = [
            None,
            "",
            "   ",
            "abc",
            "v",
            "-1.0.0",
            "1.-2.0",
            "v1.x.3",
            "1.0.0-",
            "1.0.0+",
            "1.0.0-alpha..1",
            "1.0.0+build..1",
            "v1..0",
            "1.0.",
            ".1.0.0",
            {},
            [],
        ]
        for item in malformed_cases:
            self.assertIsNone(SemVer.parse(item), f"Expected None for malformed '{item}'")

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

    def test_semver_prerelease_precedence_semantics(self) -> None:
        # Standard SemVer 2.0 ordering chain:
        # 1.1.0-alpha < 1.1.0-alpha.1 < 1.1.0-alpha.beta < 1.1.0-beta < 1.1.0-beta.2 < 1.1.0-beta.11 < 1.1.0-rc.1 < 1.1.0
        v_alpha = SemVer.parse("1.1.0-alpha")
        v_alpha1 = SemVer.parse("1.1.0-alpha.1")
        v_alpha_beta = SemVer.parse("1.1.0-alpha.beta")
        v_beta = SemVer.parse("1.1.0-beta")
        v_beta2 = SemVer.parse("1.1.0-beta.2")
        v_beta11 = SemVer.parse("1.1.0-beta.11")
        v_rc1 = SemVer.parse("1.1.0-rc.1")
        v_final = SemVer.parse("1.1.0")

        self.assertTrue(v_alpha < v_alpha1)
        self.assertTrue(v_alpha1 < v_alpha_beta)
        self.assertTrue(v_alpha_beta < v_beta)
        self.assertTrue(v_beta < v_beta2)
        self.assertTrue(v_beta2 < v_beta11)  # Numeric comparison: 2 < 11
        self.assertTrue(v_beta11 < v_rc1)
        self.assertTrue(v_rc1 < v_final)     # Normal release > prerelease
        self.assertFalse(v_final < v_rc1)

    def test_semver_build_metadata_ignored_in_comparison(self) -> None:
        v_build1 = SemVer.parse("1.1.0+build.1")
        v_build2 = SemVer.parse("1.1.0+build.2")
        self.assertEqual(v_build1, v_build2)
        self.assertFalse(v_build1 < v_build2)
        self.assertFalse(v_build2 < v_build1)


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
            {
                "tag_name": "v1.2",  # Non-standard short version rejected
                "draft": False,
                "prerelease": False,
            },
            {
                "tag_name": "v1.0.0-",  # Dangling delimiter rejected
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

    def test_check_for_updates_fails_when_no_stable_release_found(self) -> None:
        # Remote only has prerelease/draft releases
        payload = [
            {
                "tag_name": "v2.0.0-beta.1",
                "name": "v2.0.0 Beta",
                "draft": False,
                "prerelease": True,
            },
            {
                "tag_name": "v1.2.0-draft",
                "draft": True,
                "prerelease": False,
            },
        ]

        def fake_fetcher(url: str, timeout: float):
            return 200, json.dumps(payload).encode("utf-8"), {}

        result = check_for_updates(current_version="1.0.0", fetcher=fake_fetcher)
        self.assertEqual(result.state, UpdateCheckState.CHECK_FAILED)
        self.assertFalse(result.has_update)
        self.assertFalse(result.is_success)
        self.assertIsNone(result.latest_version)
        self.assertIn("No published stable release found", result.error_message)

    def test_check_for_updates_fails_on_empty_releases_list(self) -> None:
        def empty_fetcher(url: str, timeout: float):
            return 200, json.dumps([]).encode("utf-8"), {}

        result = check_for_updates(current_version="1.0.0", fetcher=empty_fetcher)
        self.assertEqual(result.state, UpdateCheckState.CHECK_FAILED)
        self.assertFalse(result.is_success)
        self.assertIsNone(result.latest_version)
        self.assertIn("No published stable release found", result.error_message)

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

    def test_service_shutdown_cleanly_when_worker_finishes_in_window(self) -> None:
        def fast_fetcher(url: str, timeout: float):
            return 200, json.dumps([]).encode("utf-8"), {}

        service = UpdateAwarenessService(
            current_version="1.0.0",
            fetcher=fast_fetcher,
        )
        service.check_for_updates()
        # Shutdown with ample wait window should return True and clear worker
        completed = service.shutdown(wait_ms=2000)
        self.assertTrue(completed)
        self.assertFalse(service.is_checking())
        self.assertIsNone(service._active_worker)

    def test_service_teardown_while_worker_running_does_not_destroy_running_qthread(self) -> None:
        import gc
        from src.update_checker import _ACTIVE_WORKER_REGISTRY

        # Worker sleeps longer than the short shutdown wait window
        def slow_fetcher(url: str, timeout: float):
            time.sleep(0.15)
            return 200, json.dumps([]).encode("utf-8"), {}

        service = UpdateAwarenessService(
            current_version="1.0.0",
            fetcher=slow_fetcher,
        )
        service.check_for_updates()
        worker = service._active_worker
        self.assertIsNotNone(worker)

        # Worker MUST be unparented from Service to avoid Qt parent-child cascading destruction
        self.assertIsNone(worker.parent())
        self.assertIn(worker, _ACTIVE_WORKER_REGISTRY)

        # Shutdown times out
        completed = service.shutdown(wait_ms=10)
        self.assertFalse(completed)
        self.assertIsNone(service._active_worker)

        # Simulate immediate destruction / garbage collection of Service during app teardown
        del service
        gc.collect()
        QApplication.processEvents()

        # The unparented worker continues executing safely without C++ premature destruction
        self.assertTrue(worker.isRunning() or worker.isFinished())

        # Wait for worker to finish naturally
        worker.wait(2000)
        QApplication.processEvents()

        # After finishing, worker cleans itself up from the global registry
        self.assertNotIn(worker, _ACTIVE_WORKER_REGISTRY)


if __name__ == "__main__":
    unittest.main()

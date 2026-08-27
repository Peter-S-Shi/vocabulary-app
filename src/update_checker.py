from __future__ import annotations

import datetime
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from src.app_config import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_REPO = "Peter-S-Shi/vocabulary-app"
DEFAULT_RELEASES_URL = f"https://api.github.com/repos/{DEFAULT_GITHUB_REPO}/releases"
DEFAULT_LATEST_RELEASE_URL = f"https://api.github.com/repos/{DEFAULT_GITHUB_REPO}/releases/latest"
DEFAULT_TIMEOUT_SECONDS = 6.0


class UpdateCheckState(str, Enum):
    NOT_CHECKED = "not_checked"
    CHECKING = "checking"
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    CHECK_FAILED = "check_failed"

    @property
    def display_label(self) -> str:
        labels = {
            self.NOT_CHECKED: "Not Checked",
            self.CHECKING: "Checking...",
            self.UP_TO_DATE: "Up to Date",
            self.UPDATE_AVAILABLE: "Update Available",
            self.CHECK_FAILED: "Check Failed",
        }
        return labels.get(self, self.value)


@dataclass(frozen=True)
class SemVer:
    """Lightweight Semantic Version representation (SemVer 2.0.0 subset)

    Supports format: [v|V]MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
    Examples: '1.0.0', 'v1.1.0', 'v1.2.0-beta.1', '1.0.9+build.42'
    """

    major: int
    minor: int
    patch: int
    prerelease: str = ""
    build: str = ""
    raw: str = ""

    @classmethod
    def parse(cls, version_str: str | None) -> SemVer | None:
        if not version_str or not isinstance(version_str, str):
            return None
        v = version_str.strip()
        if v.startswith(("v", "V")):
            v = v[1:].strip()
        if not v:
            return None

        # Extract build metadata (+...)
        build = ""
        if "+" in v:
            v, build = v.split("+", 1)

        # Extract prerelease identifier (-...)
        prerelease = ""
        if "-" in v:
            v, prerelease = v.split("-", 1)

        parts = v.split(".")
        if len(parts) == 1:
            parts = [parts[0], "0", "0"]
        elif len(parts) == 2:
            parts = [parts[0], parts[1], "0"]
        elif len(parts) > 3:
            return None

        try:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
            if major < 0 or minor < 0 or patch < 0:
                return None
        except (ValueError, TypeError):
            return None

        return cls(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease.strip(),
            build=build.strip(),
            raw=version_str.strip(),
        )

    @property
    def is_prerelease(self) -> bool:
        return bool(self.prerelease)

    def to_version_string(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base = f"{base}-{self.prerelease}"
        return base

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        # Normal version has higher precedence than a prerelease version
        if not self.prerelease and other.prerelease:
            return False  # 1.0.0 > 1.0.0-beta
        if self.prerelease and not other.prerelease:
            return True  # 1.0.0-beta < 1.0.0
        if self.prerelease and other.prerelease:
            return self.prerelease < other.prerelease
        return False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.prerelease) == (
            other.major,
            other.minor,
            other.patch,
            other.prerelease,
        )

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self < other or self == other

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return not (self <= other)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return not (self < other)


@dataclass(frozen=True)
class UpdateCheckResult:
    """Durable result model for an update check cycle."""

    state: UpdateCheckState = UpdateCheckState.NOT_CHECKED
    current_version: str = APP_VERSION
    latest_version: str | None = None
    release_url: str | None = None
    release_title: str | None = None
    release_notes: str | None = None
    published_at: str | None = None
    error_message: str | None = None
    checked_at: str | None = None

    @property
    def has_update(self) -> bool:
        return self.state == UpdateCheckState.UPDATE_AVAILABLE

    @property
    def is_success(self) -> bool:
        return self.state in (UpdateCheckState.UP_TO_DATE, UpdateCheckState.UPDATE_AVAILABLE)


def _default_http_fetcher(url: str, timeout: float) -> tuple[int, bytes, dict[str, str]]:
    """Default HTTP fetcher using standard library urllib."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"VocabularyApp/{APP_VERSION} (Windows; UpdateAwareness/1.0)",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        status_code = response.status if hasattr(response, "status") else response.getcode()
        body = response.read()
        headers = dict(response.headers)
        return status_code, body, headers


def extract_highest_stable_release(payload: Any) -> dict[str, Any] | None:
    """Extracts the highest valid stable release from a GitHub releases payload.

    Filters out:
    - draft releases (draft == True)
    - prereleases (prerelease == True)
    - malformed tags or versions containing prerelease identifiers
    """
    candidates: list[tuple[SemVer, dict[str, Any]]] = []

    items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []

    for item in items:
        if not isinstance(item, dict):
            continue
        # Rule: Drafts are strictly rejected
        if item.get("draft") is True:
            continue
        # Rule: Prereleases are strictly rejected
        if item.get("prerelease") is True:
            continue

        tag_name = item.get("tag_name")
        if not tag_name or not isinstance(tag_name, str):
            continue

        semver = SemVer.parse(tag_name)
        # Rule: Malformed versions or prerelease tags (e.g. v1.2.0-beta) rejected
        if semver is None or semver.is_prerelease:
            continue

        candidates.append((semver, item))

    if not candidates:
        return None

    # Sort descending by semver to find the highest official release
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def check_for_updates(
    current_version: str = APP_VERSION,
    repo: str = DEFAULT_GITHUB_REPO,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    fetcher: Callable[[str, float], tuple[int, bytes, dict[str, str]]] | None = None,
    api_url: str | None = None,
) -> UpdateCheckResult:
    """Checks GitHub for official stable releases and evaluates update availability.

    Guarantees:
    - Never raises network, decoding, or parsing exceptions to caller.
    - All network or payload failures fail gracefully to `CHECK_FAILED`.
    - local APP_VERSION is authoritative for current version.
    - GitHub stable Releases are authoritative for latest public version.
    """
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    current_semver = SemVer.parse(current_version)

    if current_semver is None:
        return UpdateCheckResult(
            state=UpdateCheckState.CHECK_FAILED,
            current_version=current_version,
            error_message=f"Invalid local version configuration: '{current_version}'",
            checked_at=now_iso,
        )

    target_url = api_url or f"https://api.github.com/repos/{repo}/releases"
    http_get = fetcher or _default_http_fetcher

    try:
        status_code, body, _headers = http_get(target_url, timeout)
    except urllib.error.HTTPError as exc:
        msg = f"GitHub API error: HTTP {exc.code} ({exc.reason})"
        if exc.code == 403:
            msg = "GitHub API rate limit exceeded. Please try again later."
        elif exc.code == 404:
            msg = f"Repository or releases not found: '{repo}'."
        logger.warning("Update check HTTP error: %s", msg)
        return UpdateCheckResult(
            state=UpdateCheckState.CHECK_FAILED,
            current_version=current_version,
            error_message=msg,
            checked_at=now_iso,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        msg = f"Network connection error: {exc}"
        logger.info("Update check network error: %s", msg)
        return UpdateCheckResult(
            state=UpdateCheckState.CHECK_FAILED,
            current_version=current_version,
            error_message=msg,
            checked_at=now_iso,
        )
    except Exception as exc:
        msg = f"Unexpected update check error: {exc}"
        logger.exception("Unexpected error during update check")
        return UpdateCheckResult(
            state=UpdateCheckState.CHECK_FAILED,
            current_version=current_version,
            error_message=msg,
            checked_at=now_iso,
        )

    if status_code != 200:
        return UpdateCheckResult(
            state=UpdateCheckState.CHECK_FAILED,
            current_version=current_version,
            error_message=f"GitHub API returned HTTP status {status_code}",
            checked_at=now_iso,
        )

    try:
        payload = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return UpdateCheckResult(
            state=UpdateCheckState.CHECK_FAILED,
            current_version=current_version,
            error_message=f"Failed to parse release payload: {exc}",
            checked_at=now_iso,
        )

    highest_release = extract_highest_stable_release(payload)
    if highest_release is None:
        # No stable releases found (e.g. empty releases or only drafts/prereleases)
        return UpdateCheckResult(
            state=UpdateCheckState.UP_TO_DATE,
            current_version=current_version,
            latest_version=current_version,
            error_message=None,
            checked_at=now_iso,
        )

    tag_name = highest_release.get("tag_name", "")
    release_semver = SemVer.parse(tag_name)
    if release_semver is None:
        return UpdateCheckResult(
            state=UpdateCheckState.CHECK_FAILED,
            current_version=current_version,
            error_message=f"Malformed release tag: '{tag_name}'",
            checked_at=now_iso,
        )

    latest_version_str = release_semver.to_version_string()
    release_url = highest_release.get("html_url")
    release_title = highest_release.get("name") or tag_name
    release_notes = highest_release.get("body") or ""
    published_at = highest_release.get("published_at")

    if release_semver > current_semver:
        state = UpdateCheckState.UPDATE_AVAILABLE
    else:
        state = UpdateCheckState.UP_TO_DATE

    return UpdateCheckResult(
        state=state,
        current_version=current_version,
        latest_version=latest_version_str,
        release_url=release_url,
        release_title=release_title,
        release_notes=release_notes,
        published_at=published_at,
        checked_at=now_iso,
    )


# -- PySide6 Non-Blocking Thread Worker & Service ---------------------------

try:
    from PySide6.QtCore import QObject, QThread, Signal

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False


if PYSIDE6_AVAILABLE:

    class UpdateCheckWorker(QThread):
        """Background QThread worker ensuring network checks never block the Qt main thread."""

        finished_result = Signal(object)

        def __init__(
            self,
            current_version: str = APP_VERSION,
            repo: str = DEFAULT_GITHUB_REPO,
            timeout: float = DEFAULT_TIMEOUT_SECONDS,
            fetcher: Callable[[str, float], tuple[int, bytes, dict[str, str]]] | None = None,
            api_url: str | None = None,
            parent: QObject | None = None,
        ) -> None:
            super().__init__(parent)
            self._current_version = current_version
            self._repo = repo
            self._timeout = timeout
            self._fetcher = fetcher
            self._api_url = api_url

        def run(self) -> None:
            result = check_for_updates(
                current_version=self._current_version,
                repo=self._repo,
                timeout=self._timeout,
                fetcher=self._fetcher,
                api_url=self._api_url,
            )
            self.finished_result.emit(result)

    class UpdateAwarenessService(QObject):
        """Coordinates update checks, holds latest result, and isolates background work."""

        state_changed = Signal(object)  # Emits UpdateCheckResult

        def __init__(
            self,
            current_version: str = APP_VERSION,
            repo: str = DEFAULT_GITHUB_REPO,
            timeout: float = DEFAULT_TIMEOUT_SECONDS,
            fetcher: Callable[[str, float], tuple[int, bytes, dict[str, str]]] | None = None,
            api_url: str | None = None,
            parent: QObject | None = None,
        ) -> None:
            super().__init__(parent)
            self._current_version = current_version
            self._repo = repo
            self._timeout = timeout
            self._fetcher = fetcher
            self._api_url = api_url
            self._current_result = UpdateCheckResult(
                state=UpdateCheckState.NOT_CHECKED,
                current_version=current_version,
            )
            self._active_worker: UpdateCheckWorker | None = None

        def current_result(self) -> UpdateCheckResult:
            return self._current_result

        def is_checking(self) -> bool:
            return (
                self._active_worker is not None
                and self._active_worker.isRunning()
            )

        def check_for_updates(self) -> None:
            """Triggers a non-blocking background update check."""
            if self.is_checking():
                return

            self._current_result = UpdateCheckResult(
                state=UpdateCheckState.CHECKING,
                current_version=self._current_version,
                checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            self.state_changed.emit(self._current_result)

            self._active_worker = UpdateCheckWorker(
                current_version=self._current_version,
                repo=self._repo,
                timeout=self._timeout,
                fetcher=self._fetcher,
                api_url=self._api_url,
                parent=self,
            )
            self._active_worker.finished_result.connect(self._on_worker_finished)
            self._active_worker.start()

        def _on_worker_finished(self, result: UpdateCheckResult) -> None:
            self._current_result = result
            self._active_worker = None
            self.state_changed.emit(self._current_result)

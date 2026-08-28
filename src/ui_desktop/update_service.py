from __future__ import annotations

import datetime
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

from src.app_config import APP_VERSION
from src.update_checker import (
    DEFAULT_GITHUB_REPO,
    DEFAULT_TIMEOUT_SECONDS,
    UpdateCheckResult,
    UpdateCheckState,
    check_for_updates,
)

PYSIDE6_AVAILABLE = True

_ACTIVE_WORKER_REGISTRY: set[UpdateCheckWorker] = set()


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

        # Note: parent=None ensures Service destruction never cascades into deleting
        # an active running QThread in Qt C++ object tree.
        worker = UpdateCheckWorker(
            current_version=self._current_version,
            repo=self._repo,
            timeout=self._timeout,
            fetcher=self._fetcher,
            api_url=self._api_url,
            parent=None,
        )
        self._active_worker = worker
        _ACTIVE_WORKER_REGISTRY.add(worker)

        worker.finished_result.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda w=worker: _ACTIVE_WORKER_REGISTRY.discard(w))
        worker.start()

    def shutdown(self, wait_ms: int = 2000) -> bool:
        """Gracefully waits for active worker to complete before teardown.

        If wait times out while worker is still running, disconnects callbacks
        and leaves the unparented worker safely in _ACTIVE_WORKER_REGISTRY to finish
        naturally without running-QThread destruction risks.

        Returns:
            True if all workers terminated cleanly within wait_ms.
            False if an in-flight worker exceeded wait_ms.
        """
        if self._active_worker is None:
            return True

        worker = self._active_worker
        self._active_worker = None

        if not worker.isRunning():
            return True

        # Disconnect callback so post-teardown execution doesn't invoke service
        try:
            worker.finished_result.disconnect(self._on_worker_finished)
        except (RuntimeError, TypeError):
            pass

        return worker.wait(wait_ms)

    def _on_worker_finished(self, result: UpdateCheckResult) -> None:
        self._current_result = result
        self._active_worker = None
        self.state_changed.emit(self._current_result)

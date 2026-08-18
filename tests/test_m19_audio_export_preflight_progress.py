from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db

"""
Final Human Acceptance Gate corrective (Attempt 2) -- Data Tools >
Audio Export must not freeze while its provider preflight runs.

Reported at native acceptance: every Data Tools button opened
instantly except Audio Export, which took 6-7 seconds to respond with
no feedback at all.

Root cause (confirmed by reading and measuring, not guessed):
``AudioExportDialog.__init__`` called ``_populate_voice_table()`` ->
``AudioExportController.voice_assignment_rows()`` ->
``ProviderRegistry.preflight()`` for each frozen language, and the
Mandarin route's preflight shells out to ``powershell.exe`` through
``subprocess.run`` (``src/tts_providers.py``'s
``CommandSpeechProvider.preflight``, 30s timeout). All of that ran
synchronously on the Qt UI thread before the dialog could paint. The
same call was measured hanging far past a 200s probe timeout in one
environment, so the cost is real and unbounded in practice -- not a
fixed 6 seconds to be optimized away.

Fix: the preflight runs on a background ``QThread``
(``_VoicePreflightWorker``) reporting truthful per-language progress,
the hub shows a determinate ``ProgressRing`` beside the button (hollow
-> filled) while it runs, and the dialog opens afterwards seeded with
the results so it never repeats the cost.

These tests patch ``build_provider_registry`` with a fake so they
exercise the threading/progress/seeding wiring deterministically,
without depending on real PowerShell timing.
"""

if PYSIDE6_AVAILABLE:
    from PySide6.QtCore import QEventLoop, QTimer

    from src.tts_providers import FROZEN_PROVIDER_SPECS, ProviderAvailability
    from src.ui_desktop.controllers import audio_export_controller as controller_module
    from src.ui_desktop.controllers.audio_export_controller import AudioExportController
    from src.ui_desktop.controllers.data_tools_controller import DataToolsController
    from src.ui_desktop.state.preferences import Preferences
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.data_tools_view import DataToolsView
    from src.ui_desktop.widgets.progress_ring import ProgressRing

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app

    class _FakeRegistry:
        """Stands in for a real ProviderRegistry, with an optional
        per-language delay so a slow preflight can be simulated without
        actually spawning PowerShell."""

        def __init__(self, delay: float = 0.0, available: bool = True) -> None:
            self._delay = delay
            self._available = available

        def preflight(self, language: str) -> "ProviderAvailability":
            if self._delay:
                time.sleep(self._delay)
            if self._available:
                return ProviderAvailability(True, "available", "")
            return ProviderAvailability(False, "provider_unavailable", "fake unavailable")

    def _wait_for_preflight(controller: "AudioExportController", timeout_ms: int = 15000) -> None:
        loop = QEventLoop()

        def on_changed() -> None:
            if not controller.voice_preflight_running:
                loop.quit()

        controller.voice_preflight_changed.connect(on_changed)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        if controller.voice_preflight_running:
            loop.exec()
        timer.stop()
        controller.voice_preflight_changed.disconnect(on_changed)
        controller.shutdown_voice_preflight()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class _PreflightTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m19_preflight.sqlite3"
        db.init_db()
        self._original_build_registry = controller_module.build_provider_registry

    def tearDown(self) -> None:
        controller_module.build_provider_registry = self._original_build_registry
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _patch_registry(self, delay: float = 0.0, available: bool = True) -> None:
        registry = _FakeRegistry(delay=delay, available=available)
        controller_module.build_provider_registry = lambda preferences=None: registry


class BackgroundVoicePreflightTests(_PreflightTestCase):
    def test_preflight_reports_progress_for_every_frozen_language(self) -> None:
        self._patch_registry()
        controller = AudioExportController(Preferences())
        events: list[tuple[int, int]] = []
        controller.voice_preflight_progress.connect(lambda done, total: events.append((done, total)))

        controller.start_voice_preflight()
        _wait_for_preflight(controller)

        total = len(FROZEN_PROVIDER_SPECS)
        # An initial 0/total (hollow ring) then one event per language.
        self.assertEqual(events[0], (0, total))
        self.assertEqual(events[-1], (total, total))
        self.assertEqual(len(events), total + 1)

    def test_results_are_cached_so_the_dialog_does_not_repeat_the_cost(self) -> None:
        self._patch_registry()
        controller = AudioExportController(Preferences())
        controller.start_voice_preflight()
        _wait_for_preflight(controller)

        self.assertIsNotNone(controller.voice_rows)
        self.assertEqual(len(controller.voice_rows), len(FROZEN_PROVIDER_SPECS))

        # With rows cached, voice_assignment_rows() must not rebuild a
        # registry at all -- swap in a registry that would fail loudly.
        def _explode(preferences=None):
            raise AssertionError("voice_assignment_rows() re-ran the preflight despite a cached result")

        controller_module.build_provider_registry = _explode
        rows = controller.voice_assignment_rows()
        self.assertEqual(len(rows), len(FROZEN_PROVIDER_SPECS))

    def test_running_flag_and_thread_lifecycle_are_clean(self) -> None:
        self._patch_registry(delay=0.02)
        controller = AudioExportController(Preferences())

        controller.start_voice_preflight()
        self.assertTrue(controller.voice_preflight_running)

        _wait_for_preflight(controller)

        self.assertFalse(controller.voice_preflight_running)
        self.assertEqual(controller._preflight_inflight, [])

    def test_a_superseded_preflight_result_is_discarded(self) -> None:
        """The same generation-guard discipline the Analytics and export
        workers use: a stale in-flight run must never overwrite a newer
        one's result."""
        self._patch_registry(delay=0.05)
        controller = AudioExportController(Preferences())

        controller.start_voice_preflight()
        first_generation = controller._preflight_generation
        controller.start_voice_preflight()
        second_generation = controller._preflight_generation

        self.assertGreater(second_generation, first_generation)
        _wait_for_preflight(controller)
        self.assertFalse(controller.voice_preflight_running)
        self.assertEqual(controller._preflight_inflight, [])

    def test_shutdown_is_safe_with_nothing_in_flight(self) -> None:
        controller = AudioExportController(Preferences())
        controller.shutdown_voice_preflight()  # must not raise or block
        self.assertEqual(controller._preflight_inflight, [])

    def test_an_unavailable_provider_still_produces_honest_rows(self) -> None:
        self._patch_registry(available=False)
        controller = AudioExportController(Preferences())
        controller.start_voice_preflight()
        _wait_for_preflight(controller)

        self.assertIsNotNone(controller.voice_rows)
        for _language, _provider, _voice, available, detail in controller.voice_rows:
            self.assertFalse(available)
            self.assertTrue(detail)


class DataToolsAudioExportRingTests(_PreflightTestCase):
    def test_ring_starts_hollow_and_hidden_at_rest(self) -> None:
        view = DataToolsView(DataToolsController())
        self.addCleanup(view.deleteLater)
        self.addCleanup(view._audio_preflight_controller.shutdown_voice_preflight)

        self.assertTrue(view._audio_export_ring.isHidden())
        self.assertEqual(view._audio_export_ring.progress_ratio(), 0.0)
        self.assertTrue(view._audio_export_button.isEnabled())

    def _view_without_modal_dialog(self) -> tuple["DataToolsView", list]:
        """A real DataToolsView with only the modal dialog stubbed out --
        `exec()` would otherwise block forever in a headless run with no
        user to close it (diagnosed from a faulthandler thread dump
        during this corrective). Returns the captured dialog-open calls
        so a test can assert the dialog really would have opened."""
        view = DataToolsView(DataToolsController())
        self.addCleanup(view.deleteLater)
        self.addCleanup(view._audio_preflight_controller.shutdown_voice_preflight)
        opened: list = []
        view._open_audio_export_dialog = lambda voice_rows: opened.append(voice_rows)
        return view, opened

    def test_ring_fills_as_each_language_resolves_then_opens_the_dialog(self) -> None:
        self._patch_registry()
        view, opened = self._view_without_modal_dialog()
        controller = view._audio_preflight_controller

        ratios: list[float] = []
        controller.voice_preflight_progress.connect(
            lambda _done, _total: ratios.append(view._audio_export_ring.progress_ratio())
        )
        view._on_audio_export()  # the real button handler
        _wait_for_preflight(controller)

        self.assertEqual(ratios[0], 0.0)  # hollow at the start
        self.assertEqual(ratios[-1], 1.0)  # solid when complete
        self.assertEqual(ratios, sorted(ratios))  # only ever fills forward
        # The dialog opened exactly once, seeded with the real rows.
        self.assertEqual(len(opened), 1)
        self.assertEqual(len(opened[0]), len(FROZEN_PROVIDER_SPECS))
        # And the hub returned to rest.
        self.assertTrue(view._audio_export_ring.isHidden())
        self.assertTrue(view._audio_export_button.isEnabled())

    def test_a_repeated_click_cannot_start_two_preflights(self) -> None:
        """Duplicate-action discipline, matching the rest of M19: the
        button is disabled for the duration and the handler refuses a
        re-entrant start."""
        self._patch_registry(delay=0.05)
        view, opened = self._view_without_modal_dialog()
        controller = view._audio_preflight_controller

        view._on_audio_export()
        generation_before = controller._preflight_generation
        view._on_audio_export()  # a second click while one is running

        self.assertEqual(controller._preflight_generation, generation_before)
        self.assertTrue(controller.voice_preflight_running)
        _wait_for_preflight(controller)
        self.assertEqual(len(opened), 1)  # never two dialogs

    def test_a_preflight_not_started_by_the_button_never_opens_a_dialog(self) -> None:
        """The one-shot launch guard: only a preflight the user actually
        initiated may pop a modal dialog."""
        self._patch_registry()
        view, opened = self._view_without_modal_dialog()
        controller = view._audio_preflight_controller

        controller.start_voice_preflight()  # not via the button
        _wait_for_preflight(controller)

        self.assertEqual(opened, [])
        self.assertFalse(view._audio_launch_pending)

    def test_progress_ring_never_divides_by_zero_or_overshoots(self) -> None:
        ring = ProgressRing()
        self.addCleanup(ring.deleteLater)

        ring.set_progress(5, 0)  # nonsensical maximum
        self.assertEqual(ring.progress_ratio(), 1.0)

        ring.set_progress(-3, 3)
        self.assertEqual(ring.progress_ratio(), 0.0)

        ring.set_progress(99, 3)
        self.assertEqual(ring.progress_ratio(), 1.0)

        ring.reset()
        self.assertEqual(ring.progress_ratio(), 0.0)

    def test_audio_export_status_label_has_themed_qss_coverage(self) -> None:
        """M18 Human Gate 1 lesson: an uncovered control renders at
        effectively-invisible Light Mode contrast."""
        for tokens in (THEME_CALM_BLUE_LIGHT, THEME_CALM_BLUE_DARK):
            self.assertIn("#data-tools-audio-export-status", build_stylesheet(tokens))

    def test_theme_tokens_reach_the_painted_ring(self) -> None:
        """The ring paints an arc, which QSS cannot express, so it must
        receive its colors through the same apply_theme_tokens seam
        MainWindow already uses for the Entries Star column."""
        view = DataToolsView(DataToolsController())
        self.addCleanup(view.deleteLater)
        self.addCleanup(view._audio_preflight_controller.shutdown_voice_preflight)

        view.apply_theme_tokens(THEME_CALM_BLUE_DARK)
        dark_arc = view._audio_export_ring._arc_color.name()
        view.apply_theme_tokens(THEME_CALM_BLUE_LIGHT)
        light_arc = view._audio_export_ring._arc_color.name()

        self.assertEqual(dark_arc.lower(), THEME_CALM_BLUE_DARK.accent.primary.background.lower())
        self.assertEqual(light_arc.lower(), THEME_CALM_BLUE_LIGHT.accent.primary.background.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

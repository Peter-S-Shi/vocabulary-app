from __future__ import annotations

import os
import tempfile
import unittest
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry

"""
Focused tests for M18 Phase E -- Card Audio Export
(audio_export_view.py's Design Derivation Record above
`AudioExportDialog`; `AudioExportController`'s module docstring).

Per DESIGN.md § 2 Rule C these are structural/behavioral proof that
``AudioExportController`` delegates every plan/execute/retry call to the
exact same ``src.audio_export`` M15.3 functions the core already
provides (no SQL, no second export engine), that the background
``QThread`` + cancellation wiring behaves correctly (the same class of
cross-thread bug Analytics' Human Gate 2 corrective fixed), and that
voice configuration stays read-only per M15's frozen provider/language
routing. Native human visual acceptance is a separate, required gate
(AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.audio_export import SCOPE_COLLECTION, SCOPE_SELECTED_CARDS, SCOPE_SINGLE_CARD
    from src.tts_providers import (
        FROZEN_PROVIDER_SPECS,
        ProviderAvailability,
        ProviderRegistry,
        SynthesisResult,
    )
    from src.ui_desktop.controllers import audio_export_controller as controller_module
    from src.ui_desktop.state.preferences import Preferences
    from src.ui_desktop.controllers.audio_export_controller import AudioExportController
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.audio_export_view import AudioExportDialog

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app

    def _write_wav(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(24_000)
            writer.writeframes(b"\x00\x10" * 240)

    class _FakeProvider:
        def __init__(
            self, language: str, *, fail: bool = False, delay: float = 0.0, unavailable: bool = False
        ) -> None:
            self.spec = FROZEN_PROVIDER_SPECS[language]
            self.fail = fail
            self.delay = delay
            self.unavailable = unavailable

        def preflight(self) -> ProviderAvailability:
            if self.unavailable:
                return ProviderAvailability(False, "provider_unavailable", "Synthetic unavailable provider.")
            return ProviderAvailability(True, "available")

        def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult:
            if self.delay:
                import time

                time.sleep(self.delay)
            if self.fail:
                return SynthesisResult(
                    self.spec.provider_id, self.spec.voice_id, self.spec.language,
                    None, None, None, "synthetic_provider_failure", "Synthetic provider failure.",
                )
            _write_wav(output_path)
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                output_path, "audio/wav", 24_000,
            )

    def _fake_registry(
        *, fail_language: str | None = None, delay: float = 0.0, unavailable_language: str | None = None
    ) -> ProviderRegistry:
        return ProviderRegistry([
            _FakeProvider(
                language, fail=language == fail_language, delay=delay,
                unavailable=language == unavailable_language,
            )
            for language in FROZEN_PROVIDER_SPECS
        ])

    def _wait_for_run(controller: "AudioExportController", timeout_ms: int = 5000) -> None:
        """Same shape as Analytics' ``_wait_for_load`` (test_m18_analytics.py):
        pump the Qt event loop until the run finishes, then block for the
        background QThread to actually stop before the test's ``tearDown``
        deletes the temporary database -- required to avoid the exact
        "QThread: Destroyed while thread is still running" segfault class
        Analytics' Human Gate 2 corrective found and fixed."""
        from PySide6.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        controller.state_changed.connect(loop.quit)
        controller.run_failed.connect(loop.quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        loop.exec()
        timer.stop()
        controller.state_changed.disconnect(loop.quit)
        controller.run_failed.disconnect(loop.quit)
        if controller.is_running:
            raise AssertionError("Audio export background run did not complete within the timeout.")
        controller.shutdown()
        if controller._inflight:
            raise AssertionError("Audio export background QThread did not fully stop within the timeout.")


class _SyntheticDatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m18_audio_export.sqlite3"
        db.init_db()
        self.destination = self.root / "export"

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _collection(self, count: int = 2, *, card_size: int = 1) -> int:
        entry_ids = [
            add_entry("English", "English", "word", f"term-{i}", f"meaning-{i}") for i in range(count)
        ]
        collection_id = create_collection(f"Audio Export {count}", card_size=card_size)
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class AudioExportControllerScopeTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_set_collection_loads_cards_and_resets_selection(self) -> None:
        collection_id = self._collection(3)
        controller = AudioExportController(Preferences())
        controller.set_collection(collection_id)
        self.assertEqual(sorted(controller.cards), [1, 2, 3])
        self.assertEqual(controller.single_card_number, 1)
        self.assertEqual(controller.selected_card_numbers, set())

    def test_can_build_plan_requires_scope_specific_selection(self) -> None:
        collection_id = self._collection(2)
        controller = AudioExportController(Preferences())
        controller.set_collection(collection_id)
        controller.set_destination_root(str(self.destination))

        controller.set_scope(SCOPE_SELECTED_CARDS)
        self.assertFalse(controller.can_build_plan())
        controller.set_selected_card_numbers({1})
        self.assertTrue(controller.can_build_plan())

        controller.set_scope(SCOPE_COLLECTION)
        self.assertTrue(controller.can_build_plan())

        controller.set_scope(SCOPE_SINGLE_CARD)
        self.assertTrue(controller.can_build_plan())
        controller.set_single_card_number(None)
        self.assertFalse(controller.can_build_plan())

    def test_voice_assignment_rows_reflect_frozen_specs_read_only(self) -> None:
        controller = AudioExportController(Preferences())
        rows = controller.voice_assignment_rows()
        self.assertEqual(len(rows), len(FROZEN_PROVIDER_SPECS))
        for language, provider_id, voice_id, _available, _detail in rows:
            spec = FROZEN_PROVIDER_SPECS[language]
            self.assertEqual((provider_id, voice_id), (spec.provider_id, spec.voice_id))

    def test_voice_assignment_rows_report_live_preflight_status(self) -> None:
        """HG3 corrective: "0 of X Cards ready" gave no visible reason.
        This panel must reflect a REAL, live preflight -- not a cached
        plan-time snapshot -- so unavailable providers are diagnosable
        before the user ever builds a Plan."""
        controller = AudioExportController(Preferences())

        # build_provider_registry() unpatched here (with hermetic empty
        # Preferences) -- exercises the real "no shared TTS runtime
        # configured anywhere" path this corrective adds a distinct,
        # actionable code/detail for.
        unavailable_rows = controller.voice_assignment_rows()
        for _language, _provider_id, _voice_id, available, detail in unavailable_rows:
            self.assertFalse(available)
            self.assertIn("VOCAB_APP_VOICE_BINDINGS", detail)

        controller_module.build_provider_registry = lambda preferences=None: _fake_registry()
        try:
            available_rows = controller.voice_assignment_rows()
        finally:
            controller_module.build_provider_registry = self._original_build_registry
        if self._saved_shared_tts_env is not None:
            os.environ["VOCAB_APP_VOICE_BINDINGS"] = self._saved_shared_tts_env
        for _language, _provider_id, _voice_id, available, _detail in available_rows:
            self.assertTrue(available)

    def setUp(self) -> None:
        super().setUp()
        self._original_build_registry = controller_module.build_provider_registry
        # M19 hermeticity: a developer machine may legitimately have
        # VOCAB_APP_VOICE_BINDINGS set system-wide (the operator did so
        # after M18 closed, which made every "real unconfigured path"
        # test in this file fail against a real runtime). Tests that
        # exercise the unconfigured path must isolate the environment.
        self._saved_shared_tts_env = os.environ.pop("VOCAB_APP_VOICE_BINDINGS", None)

    def tearDown(self) -> None:
        controller_module.build_provider_registry = self._original_build_registry
        if self._saved_shared_tts_env is not None:
            os.environ["VOCAB_APP_VOICE_BINDINGS"] = self._saved_shared_tts_env
        super().tearDown()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class AudioExportControllerRunTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self._original_build_registry = controller_module.build_provider_registry
        # M19 hermeticity: a developer machine may legitimately have
        # VOCAB_APP_VOICE_BINDINGS set system-wide (the operator did so
        # after M18 closed, which made every "real unconfigured path"
        # test in this file fail against a real runtime). Tests that
        # exercise the unconfigured path must isolate the environment.
        self._saved_shared_tts_env = os.environ.pop("VOCAB_APP_VOICE_BINDINGS", None)

    def tearDown(self) -> None:
        controller_module.build_provider_registry = self._original_build_registry
        if self._saved_shared_tts_env is not None:
            os.environ["VOCAB_APP_VOICE_BINDINGS"] = self._saved_shared_tts_env
        super().tearDown()

    def _patch_registry(self, registry: ProviderRegistry) -> None:
        controller_module.build_provider_registry = lambda preferences=None: registry

    def test_successful_run_produces_one_file_per_card_and_progress_events(self) -> None:
        self._patch_registry(_fake_registry())
        collection_id = self._collection(2)
        controller = AudioExportController(Preferences())
        controller.set_collection(collection_id)
        controller.set_scope(SCOPE_COLLECTION)
        controller.set_destination_root(str(self.destination))
        controller.build_plan()
        self.assertEqual(controller.plan.ready_count, 2)

        events: list[tuple[int, int, str]] = []
        controller.run_progress.connect(lambda c, t, k: events.append((c, t, k)))
        controller.run()
        _wait_for_run(controller)

        self.assertEqual(controller.result.succeeded_count, 2)
        self.assertEqual(len(list(self.destination.glob("*.wav"))), 2)
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0], (0, 2, "batch_planned"))

    def test_unavailable_provider_produces_controlled_unresolved_result(self) -> None:
        # build_provider_registry() is left unpatched here (hermetic empty
        # Preferences) -- exercises the real honest "no shared TTS runtime
        # configured" path.
        collection_id = self._collection(1)
        controller = AudioExportController(Preferences())
        controller.set_collection(collection_id)
        controller.set_scope(SCOPE_COLLECTION)
        controller.set_destination_root(str(self.destination))
        controller.build_plan()
        controller.run()
        _wait_for_run(controller)

        self.assertEqual(controller.result.unresolved_count, 1)
        self.assertEqual(controller.result.succeeded_count, 0)

    def test_cancellation_is_card_atomic_and_retry_recovers_remainder(self) -> None:
        self._patch_registry(_fake_registry(delay=0.05))
        collection_id = self._collection(3)
        controller = AudioExportController(Preferences())
        controller.set_collection(collection_id)
        controller.set_scope(SCOPE_COLLECTION)
        controller.set_destination_root(str(self.destination))
        controller.build_plan()

        cancelled_after_first = {"done": False}

        def cancel_after_first_card(completed: int, total: int, kind: str) -> None:
            if kind == "export_published" and not cancelled_after_first["done"]:
                cancelled_after_first["done"] = True
                controller.cancel()

        controller.run_progress.connect(cancel_after_first_card)
        controller.run()
        _wait_for_run(controller)

        cancelled_count = controller.result.cancelled_count
        self.assertGreaterEqual(cancelled_count, 1)
        self.assertTrue(controller.can_retry())

        controller.retry()
        _wait_for_run(controller)

        # retry()'s result covers only the retried (previously cancelled)
        # Cards -- not the whole batch -- matching build_retry_plan's
        # core contract (test_m15_3_audio_export.py's
        # test_retry_targets_only_failure_and_reuses_successful_output).
        # The 1st Card's own output, published before cancellation, is
        # untouched and still on disk.
        self.assertEqual(controller.result.succeeded_count, cancelled_count)
        self.assertEqual(controller.result.cancelled_count, 0)
        self.assertEqual(len(list(self.destination.glob("*.wav"))), 3)

    def test_a_superseded_run_generation_is_discarded(self) -> None:
        """Same discipline as AnalyticsController's ``_generation`` guard
        (module docstring): starting a second run before the first's
        worker signal is processed must never let the stale first result
        overwrite the real, current one. Two distinct destinations (not
        two runs of the identical plan) keep this a pure generation-guard
        test rather than a filesystem race between two workers racing to
        publish the same output path under CONFLICT_SKIP."""
        self._patch_registry(_fake_registry(delay=0.05))
        collection_id = self._collection(1)
        controller = AudioExportController(Preferences())
        controller.set_collection(collection_id)
        controller.set_scope(SCOPE_COLLECTION)

        controller.set_destination_root(str(self.destination / "first"))
        controller.build_plan()
        first_plan = controller.plan

        controller.set_destination_root(str(self.destination / "second"))
        controller.build_plan()
        second_plan = controller.plan

        controller._start_run(first_plan)
        controller._start_run(second_plan)  # supersedes the first in-flight run
        _wait_for_run(controller)

        # The 1st (stale) worker still runs to completion and publishes
        # its own file -- only its *result* is discarded, per
        # ``_on_succeeded``'s generation check; superseding a run is not
        # cancellation. What matters here is that the controller's
        # user-visible result reflects the 2nd (current) run, not the 1st.
        self.assertEqual(controller.result.succeeded_count, 1)
        self.assertEqual(controller.result.plan.destination_root, second_plan.destination_root)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class AudioExportDialogTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_dialog_constructs_and_lists_collections(self) -> None:
        self._collection(1)
        dialog = AudioExportDialog(preferences=Preferences())
        self.addCleanup(dialog._controller.shutdown)
        self.addCleanup(dialog.deleteLater)
        self.assertGreaterEqual(dialog._collection_combo.count(), 2)  # placeholder + 1 Collection
        self.assertEqual(dialog._voice_table.rowCount(), len(FROZEN_PROVIDER_SPECS))
        self.assertEqual(dialog._voice_table.columnCount(), 4)  # + live preflight Status column

    def test_voice_table_shows_unavailable_status_with_actionable_detail(self) -> None:
        """HG3 corrective regression: the Voice Assignment panel must
        show *why* every language is unavailable, not just a bare
        provider/voice identity -- build_provider_registry() is
        deliberately left unpatched (hermetic empty Preferences) so this
        exercises the real "no shared TTS runtime configured"
        desktop-session path."""
        dialog = AudioExportDialog(preferences=Preferences())
        self.addCleanup(dialog._controller.shutdown)
        self.addCleanup(dialog.deleteLater)
        for row in range(dialog._voice_table.rowCount()):
            status_text = dialog._voice_table.item(row, 3).text()
            self.assertIn("Unavailable", status_text)
            self.assertIn("VOCAB_APP_VOICE_BINDINGS", status_text)

    def test_plan_table_preserves_partial_batch_honesty_for_mixed_availability(self) -> None:
        """Review-required semantics: ready Cards proceed, unresolved
        Cards stay honestly identified -- never silently treated as
        ready, and readiness is never enabled unconditionally regardless
        of real provider availability."""
        english_id = add_entry("English", "English", "word", "hello", "greeting")
        french_id = add_entry("French", "English", "word", "bonjour", "greeting-fr")
        collection_id = create_collection("Mixed availability", card_size=1)
        add_entries_to_collection([english_id, french_id], collection_id)

        controller_module.build_provider_registry = (
            lambda preferences=None: _fake_registry(unavailable_language="fr")
        )

        dialog = AudioExportDialog(preferences=Preferences())
        self.addCleanup(dialog._controller.shutdown)
        self.addCleanup(dialog.deleteLater)
        dialog._collection_combo.setCurrentIndex(dialog._collection_combo.findData(collection_id))
        dialog._controller.set_destination_root(str(self.destination))
        dialog._on_build_plan()

        self.assertEqual(dialog._controller.plan.ready_count, 1)
        statuses = {
            dialog._plan_table.item(row, 0).text(): dialog._plan_table.item(row, 2).text()
            for row in range(dialog._plan_table.rowCount())
        }
        self.assertEqual(statuses, {"1": "Ready", "2": "Not ready"})
        reasons = {
            dialog._plan_table.item(row, 0).text(): dialog._plan_table.item(row, 3).text()
            for row in range(dialog._plan_table.rowCount())
        }
        self.assertEqual(reasons["1"], "")
        self.assertIn("provider_unavailable", reasons["2"])

    def setUp(self) -> None:
        super().setUp()
        self._original_build_registry = controller_module.build_provider_registry
        # M19 hermeticity: a developer machine may legitimately have
        # VOCAB_APP_VOICE_BINDINGS set system-wide (the operator did so
        # after M18 closed, which made every "real unconfigured path"
        # test in this file fail against a real runtime). Tests that
        # exercise the unconfigured path must isolate the environment.
        self._saved_shared_tts_env = os.environ.pop("VOCAB_APP_VOICE_BINDINGS", None)

    def tearDown(self) -> None:
        controller_module.build_provider_registry = self._original_build_registry
        if self._saved_shared_tts_env is not None:
            os.environ["VOCAB_APP_VOICE_BINDINGS"] = self._saved_shared_tts_env
        super().tearDown()

    def test_plan_table_shows_concrete_per_card_reason_when_not_ready(self) -> None:
        """HG3 corrective regression: "0 of X Cards ready" alone, with no
        visible reason, was the reported blocker. Every not-ready row
        must show its own real CardAudioPlan.issues, not a generic
        placeholder."""
        collection_id = self._collection(2)
        dialog = AudioExportDialog(preferences=Preferences())
        self.addCleanup(dialog._controller.shutdown)
        self.addCleanup(dialog.deleteLater)
        dialog._collection_combo.setCurrentIndex(dialog._collection_combo.findData(collection_id))
        dialog._controller.set_destination_root(str(self.destination))
        dialog._on_build_plan()

        self.assertEqual(dialog._controller.plan.ready_count, 0)
        self.assertEqual(dialog._plan_table.rowCount(), 2)
        for row in range(dialog._plan_table.rowCount()):
            self.assertEqual(dialog._plan_table.item(row, 2).text(), "Not ready")
            reason = dialog._plan_table.item(row, 3).text()
            self.assertIn("voice_not_configured", reason)
            self.assertIn("VOCAB_APP_VOICE_BINDINGS", reason)

    def test_choosing_a_collection_populates_card_selectors(self) -> None:
        collection_id = self._collection(2)
        dialog = AudioExportDialog(preferences=Preferences())
        self.addCleanup(dialog._controller.shutdown)
        self.addCleanup(dialog.deleteLater)
        dialog._collection_combo.setCurrentIndex(dialog._collection_combo.findData(collection_id))
        self.assertEqual(dialog._single_card_combo.count(), 2)
        self.assertEqual(dialog._card_list.count(), 2)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18AudioExportQssStructuralCoverageTests(unittest.TestCase):
    REPRESENTATIVE_SELECTORS = (
        "#data-tools-audio-export-button",
        "#audio-export-choose-folder-button",
        "#audio-export-build-plan-button",
        "#audio-export-start-button",
        "#audio-export-cancel-button",
        "#audio-export-retry-button",
        "#audio-export-progress-bar",
        "#audio-export-status-label",
    )

    def _assert_all_selectors_present(self, tokens) -> None:
        stylesheet = build_stylesheet(tokens)
        for selector in self.REPRESENTATIVE_SELECTORS:
            self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")

    def test_light_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_LIGHT)

    def test_dark_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_DARK)


if __name__ == "__main__":
    unittest.main()

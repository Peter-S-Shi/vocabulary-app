from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from src.audio_composition import REPEAT_EACH_FIELD, REPETITION_MODES, CompositionConfig
from src.audio_export import (
    CONFLICT_OVERWRITE,
    CONFLICT_POLICIES,
    CONFLICT_SKIP,
    SCOPE_COLLECTION,
    SCOPE_SELECTED_CARDS,
    SCOPE_SINGLE_CARD,
    AudioExportBatchResult,
    AudioExportPlan,
    ExportProgressEvent,
    build_audio_export_plan,
    build_retry_plan,
    execute_audio_export_plan,
)
from src.collections import get_card_metadata_for_collection, get_collections
from src.tts_providers import FROZEN_PROVIDER_SPECS, ProviderRegistry
from src.ui_desktop.state.preferences import Preferences
from src.ui_desktop.state.tts_runtime import build_provider_registry

"""
AudioExportController owns the Card Audio Export workspace's transient
scope/configuration state and its background export run (DESIGN.md
§ 7.4 "Audio Export configuration: B, VR-UTILITY-001"; § 12.5 "For Card
Audio Export preserve M15.3"). Every plan/execute/retry call delegates
to ``src.audio_export`` -- no SQL, no second export engine, no
desktop-only synthesis path.

Voice configuration (DESIGN.md § 7.4 "voice/repetition configuration:
B, P6 focused form") is READ-ONLY here, not a picker: M15 froze
provider/language routing (``src.tts_providers.FROZEN_PROVIDER_SPECS``)
and the M18 contract § 5 forbids reopening it "without evidence of an
actual blocker" -- none exists. The workspace instead surfaces which
frozen voice each Card's languages will use, so "configuration" means
confirming the deterministic assignment before running a batch, not
choosing among voices. Repetition mode/count are the genuinely
configurable half of ``CompositionConfig`` the roadmap actually names
("repetition count; repetition-mode selection") and are exposed as such.

Export is genuinely long-running (`DESIGN.md § 12.4`), so it runs on a
background ``QThread`` via ``_AudioExportWorker`` -- the same shape
Analytics' Human Gate 2 corrective established
(``AnalyticsController``/``_AnalyticsLoadWorker``): a monotonic
``_generation`` token discards a stale superseded run, worker signals
connect to real bound methods (never a lambda) so PySide6 correctly
queues them onto the Qt UI thread, and ``shutdown()`` blocks until any
in-flight run has actually stopped before the owning dialog closes.
Cancellation (§ 12.4 "whether cancellation is safe") is a
``threading.Event`` polled by ``execute_audio_export_plan``'s
``should_cancel`` between Cards -- Card-atomic, per that function's own
docstring: a Card already published stays published, and every
remaining Card comes back ``cancelled`` rather than silently unattempted.
"""


class _AudioExportWorker(QObject):
    stage_changed = Signal(int, object)  # (generation, ExportProgressEvent)
    succeeded = Signal(int, object)  # (generation, AudioExportBatchResult)
    failed = Signal(int, str)

    def __init__(
        self,
        generation: int,
        plan: AudioExportPlan,
        providers: ProviderRegistry,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self._generation = generation
        self._plan = plan
        self._providers = providers
        self._cancel_event = cancel_event

    def run(self) -> None:
        try:
            result = execute_audio_export_plan(
                self._plan,
                providers=self._providers,
                progress=self._on_progress,
                should_cancel=self._cancel_event.is_set,
            )
        except Exception as exc:  # noqa: BLE001 -- surfaced as a controlled error state, not a crash
            self.failed.emit(self._generation, str(exc))
            return
        self.succeeded.emit(self._generation, result)

    def _on_progress(self, event: ExportProgressEvent) -> None:
        self.stage_changed.emit(self._generation, event)


SCOPE_LABELS: tuple[tuple[str, str], ...] = (
    (SCOPE_SINGLE_CARD, "Single Card"),
    (SCOPE_SELECTED_CARDS, "Selected Cards"),
    (SCOPE_COLLECTION, "Whole Collection"),
)

REPETITION_MODE_LABELS: tuple[tuple[str, str], ...] = (
    (REPEAT_EACH_FIELD, "Repeat Each Field"),
    ("repeat_whole_card", "Repeat Whole Card"),
)

CONFLICT_LABELS: tuple[tuple[str, str], ...] = (
    (CONFLICT_SKIP, "Skip existing files"),
    (CONFLICT_OVERWRITE, "Overwrite existing files"),
)


class AudioExportController(QObject):
    state_changed = Signal()
    run_started = Signal()
    run_progress = Signal(int, int, str)
    run_failed = Signal(str)

    def __init__(self, preferences: Preferences | None = None) -> None:
        super().__init__()
        # M19: the live Preferences instance (or None to re-read the
        # persisted preferences file at each resolution, so a runtime
        # folder just saved in Settings > Audio takes effect without
        # restart). See state/tts_runtime.py for the resolution order.
        self._preferences = preferences
        self.collections: list[dict] = []
        self.collection_id: int | None = None
        self.cards: dict[int, dict] = {}
        self.scope: str = SCOPE_COLLECTION
        self.selected_card_numbers: set[int] = set()
        self.single_card_number: int | None = None
        self.repetition_mode: str = REPEAT_EACH_FIELD
        self.repetition_count: int = 1
        self.conflict_policy: str = CONFLICT_SKIP
        self.destination_root: str = ""
        self.plan: AudioExportPlan | None = None
        self.plan_error: str | None = None
        self.result: AudioExportBatchResult | None = None
        self.is_running: bool = False
        self.run_error: str | None = None
        self._generation = 0
        self._cancel_event: threading.Event | None = None
        # Kept alive together, matching AnalyticsController's precedent
        # (module docstring): an unparented worker with no other Python
        # reference could otherwise be garbage-collected before the
        # QThread ever invokes it.
        self._inflight: list[tuple[QThread, _AudioExportWorker]] = []

    # -- Scope / configuration -----------------------------------------

    def refresh(self) -> None:
        self.collections = [c for c in get_collections() if not c.get("is_system")]
        if self.collection_id is not None and not any(int(c["id"]) == self.collection_id for c in self.collections):
            self.collection_id = None
            self.cards = {}
        self.state_changed.emit()

    def set_collection(self, collection_id: int | None) -> None:
        if collection_id == self.collection_id:
            return
        self.collection_id = collection_id
        self.cards = get_card_metadata_for_collection(collection_id) if collection_id is not None else {}
        self.selected_card_numbers = set()
        self.single_card_number = next(iter(sorted(self.cards)), None)
        self.plan = None
        self.plan_error = None
        self.result = None
        self.state_changed.emit()

    def set_scope(self, scope: str) -> None:
        if scope == self.scope:
            return
        self.scope = scope
        self.plan = None
        self.plan_error = None
        self.result = None
        self.state_changed.emit()

    def set_single_card_number(self, card_number: int | None) -> None:
        self.single_card_number = card_number
        self.plan = None
        self.result = None
        self.state_changed.emit()

    def set_selected_card_numbers(self, card_numbers: set[int]) -> None:
        self.selected_card_numbers = set(card_numbers)
        self.plan = None
        self.result = None
        self.state_changed.emit()

    def set_repetition_mode(self, mode: str) -> None:
        if mode not in REPETITION_MODES:
            return
        self.repetition_mode = mode
        self.plan = None
        self.result = None
        self.state_changed.emit()

    def set_repetition_count(self, count: int) -> None:
        self.repetition_count = int(count)
        self.plan = None
        self.result = None
        self.state_changed.emit()

    def set_conflict_policy(self, policy: str) -> None:
        if policy not in CONFLICT_POLICIES:
            return
        self.conflict_policy = policy
        self.plan = None
        self.result = None
        self.state_changed.emit()

    def set_destination_root(self, path: str) -> None:
        self.destination_root = path
        self.plan = None
        self.result = None
        self.state_changed.emit()

    def languages_in_scope(self) -> list[str]:
        """Best-effort, plan-independent language preview for the
        read-only voice-configuration panel -- Cards have no first-class
        stored language, so this can only report the languages
        M15's frozen routing actually supports; the built Plan itself
        remains the source of truth for what will really synthesize."""
        return sorted(FROZEN_PROVIDER_SPECS)

    def voice_assignment_rows(self) -> list[tuple[str, str, str, bool, str]]:
        """(language, provider_id, voice_id, available, detail) per frozen
        M15 language. ``available``/``detail`` come from a real, live
        ``build_provider_registry().preflight()`` call -- not a
        cached/plan-time snapshot -- so this panel honestly reflects
        whether the current process can actually reach the configured
        shared TTS runtime (Settings > Audio app setting, or the
        VOCAB_APP_SHARED_TTS_DIR per-process override; see
        state/tts_runtime.py) *before* the user spends effort
        building a Plan (HG3 corrective: "0 of X Cards ready" with no
        visible reason was the reported blocker)."""
        registry = build_provider_registry(self._preferences)
        rows = []
        for spec in FROZEN_PROVIDER_SPECS.values():
            availability = registry.preflight(spec.language)
            rows.append((spec.language, spec.provider_id, spec.voice_id, availability.available, availability.detail))
        return rows

    # -- Plan ------------------------------------------------------------

    def can_build_plan(self) -> bool:
        if self.collection_id is None or not self.destination_root:
            return False
        if self.scope == SCOPE_SINGLE_CARD:
            return self.single_card_number is not None
        if self.scope == SCOPE_SELECTED_CARDS:
            return bool(self.selected_card_numbers)
        return True

    def build_plan(self) -> None:
        if not self.can_build_plan():
            return
        config = CompositionConfig(
            repetition_mode=self.repetition_mode, repetition_count=self.repetition_count
        )
        # M19: pass the desktop-resolved registry explicitly. Core's
        # build_audio_export_plan defaults to environment-only
        # resolution when providers is omitted, which would ignore a
        # runtime folder configured through Settings > Audio -- the Plan
        # and the Run must judge readiness against the same registry.
        registry = build_provider_registry(self._preferences)
        try:
            config.validated()
            if self.scope == SCOPE_SINGLE_CARD:
                self.plan = build_audio_export_plan(
                    self.collection_id, [self.single_card_number], Path(self.destination_root),
                    scope=SCOPE_SINGLE_CARD, providers=registry,
                    composition_config=config, conflict_policy=self.conflict_policy,
                )
            elif self.scope == SCOPE_SELECTED_CARDS:
                self.plan = build_audio_export_plan(
                    self.collection_id, sorted(self.selected_card_numbers), Path(self.destination_root),
                    scope=SCOPE_SELECTED_CARDS, providers=registry,
                    composition_config=config, conflict_policy=self.conflict_policy,
                )
            else:
                self.plan = build_audio_export_plan(
                    self.collection_id, sorted(self.cards), Path(self.destination_root),
                    scope=SCOPE_COLLECTION, providers=registry,
                    composition_config=config, conflict_policy=self.conflict_policy,
                )
            self.plan_error = None
        except ValueError as error:
            self.plan = None
            self.plan_error = str(error)
        self.result = None
        self.state_changed.emit()

    # -- Run / cancel ------------------------------------------------------

    def can_run(self) -> bool:
        return bool(self.plan and self.plan.items and not self.is_running)

    def run(self) -> None:
        if not self.can_run():
            return
        self._start_run(self.plan)

    def can_retry(self) -> bool:
        return bool(self.result) and not self.is_running and (
            self.result.failed_count or self.result.unresolved_count or self.result.cancelled_count
        )

    def retry(self) -> None:
        if not self.can_retry():
            return
        # M19: like build_plan(), pass the desktop-resolved registry --
        # build_retry_plan re-validates unresolved/cancelled Cards and
        # would otherwise fall back to core's environment-only default,
        # ignoring a runtime configured through Settings > Audio.
        retry_plan = build_retry_plan(self.result, providers=build_provider_registry(self._preferences))
        if not retry_plan.items:
            return
        self._start_run(retry_plan)

    def _start_run(self, plan: AudioExportPlan) -> None:
        self._generation += 1
        generation = self._generation
        self.is_running = True
        self.run_error = None
        self.run_started.emit()

        cancel_event = threading.Event()
        self._cancel_event = cancel_event
        thread = QThread()
        worker = _AudioExportWorker(generation, plan, build_provider_registry(self._preferences), cancel_event)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.stage_changed.connect(self._on_stage)
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._inflight.append((thread, worker))
        thread.start()

    def cancel(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()

    def _on_thread_finished(self) -> None:
        thread = self.sender()
        self._inflight = [pair for pair in self._inflight if pair[0] is not thread]

    def _on_stage(self, generation: int, event: ExportProgressEvent) -> None:
        if generation != self._generation:
            return
        self.run_progress.emit(event.completed, event.total, event.kind)

    def _on_succeeded(self, generation: int, result: AudioExportBatchResult) -> None:
        if generation != self._generation:
            return  # a newer run superseded this in-flight one; discard
        self.result = result
        self.is_running = False
        self.state_changed.emit()

    def _on_failed(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self.is_running = False
        self.run_error = message
        self.run_failed.emit(message)

    def shutdown(self) -> None:
        """Block until every in-flight background run has actually
        stopped -- see module docstring / AnalyticsController.shutdown()
        precedent for why this must happen before the owning dialog (or
        the app) is torn down."""
        self.cancel()
        for pair in list(self._inflight):
            thread, _worker = pair
            thread.quit()
            thread.wait(5000)
            if pair in self._inflight:
                self._inflight.remove(pair)

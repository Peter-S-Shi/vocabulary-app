from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from src.analytics import EvidenceProfileCache, build_evidence_profile_cache, get_collection_coverage_profile
from src.collections import get_collections
from src.db import get_connection
from src.entry_templates import get_entry_templates
from src.insights import build_learning_brief, get_all_findings

"""
AnalyticsController owns the Analytics workspace's transient scope
selection, calling existing ``src.insights``/``src.analytics`` reads for
every Finding, Brief item, and Coverage figure it projects -- no SQL, no
invented thresholds/scores, no mutation (DESIGN.md § 6.5 frozen
semantics: "actions are recommendations and do not silently mutate
learning state").

Scope model: "all" (every current Entry, ``collection_id=None``) or one
Collection (matching the scope kwarg every M14 function already
accepts). There is no global Coverage function in ``src.analytics`` --
Coverage/Scope Activity are inherently Collection/Template-scoped
concepts in the M14 contract, so the Coverage panel is intentionally
absent for "all" scope rather than inventing a global coverage metric
the core does not define.

Human Gate 2 corrective (M18 Phase D): on a real production database,
navigating to Analytics froze the whole app -- ``get_scope_coverage_findings``
reloaded and recomputed the *entire* database's evidence profiles once per
Collection and again once per Card, all synchronously on the Qt UI thread
(see ``src.analytics.EvidenceProfileCache``'s docstring for the root-cause
fix). Two independent corrections apply here, on top of that root-cause
fix in the core:

1. the (now O(1)-per-refresh, but still not instantaneous on a large
   database) M14 read still runs on a background ``QThread`` via
   ``_AnalyticsLoadWorker`` rather than the Qt UI thread, so the window
   never stops responding to input even if a computation legitimately
   takes a while;
2. every load carries a monotonically increasing ``_generation`` token;
   a load whose token no longer matches ``self._generation`` when it
   finishes (because the user changed scope again before it returned) is
   discarded rather than applied, so a stale in-flight result can never
   overwrite a newer one.

The worker's signals carry ``generation`` as part of the payload and are
connected *directly* to ``AnalyticsController``'s real bound methods
(``self._on_stage`` etc.) rather than to a lambda closing over
``generation`` -- independent-review finding: PySide6 can only detect a
cross-thread receiver (and therefore correctly queue the call onto the
receiver's own thread) when the connected callable is an actual bound
method of a ``QObject``. A lambda has no such identity, so PySide6 was
falling back to a direct call executed on the *worker's* thread --
exactly the unsynchronized, off-Qt-UI-thread execution this correction
exists to prevent, and a real race against ``_start_load``'s
``self._generation += 1`` on the main thread.
"""


class _AnalyticsLoadWorker(QObject):
    """Runs one Analytics load off the Qt UI thread.

    Opens its own SQLite connection -- ``sqlite3.Connection`` objects are
    not safe to share across threads, but ``src.db.get_connection()``
    already opens a fresh one per call, so this is naturally safe as long
    as the connection is both opened and used inside ``run()`` (i.e. on
    the worker thread), never on the controller's thread.

    Progress is staged by *completed step*, not a fabricated
    within-step percentage: there is no way to truthfully measure
    fractional progress inside a single M14 read, so each stage boundary
    (evidence loaded, findings/brief built, coverage loaded) is the most
    granular truthful signal available.
    """

    stage_changed = Signal(int, int, int, str)
    succeeded = Signal(int, dict, list, object)
    failed = Signal(int, str)

    def __init__(self, generation: int, scope_type: str, scope_id: int | None) -> None:
        super().__init__()
        self._generation = generation
        self._scope_type = scope_type
        self._scope_id = scope_id

    def run(self) -> None:
        collection_id = self._scope_id if self._scope_type == "collection" else None
        total_steps = 3 if collection_id is not None else 2
        try:
            with get_connection() as connection:
                self.stage_changed.emit(self._generation, 1, total_steps, "Loading evidence…")
                cache: EvidenceProfileCache = build_evidence_profile_cache(connection)

                self.stage_changed.emit(self._generation, 2, total_steps, "Finding patterns…")
                full_findings = get_all_findings(connection, collection_id=collection_id, cache=cache)
                brief = build_learning_brief(
                    connection, full_findings["full_findings"], collection_id=collection_id
                )

                coverage = None
                if collection_id is not None:
                    self.stage_changed.emit(self._generation, 3, total_steps, "Loading Collection coverage…")
                    coverage = get_collection_coverage_profile(connection, collection_id, cache=cache)
        except Exception as exc:  # noqa: BLE001 -- surfaced as a controlled Analytics error state, not a crash
            self.failed.emit(self._generation, str(exc))
            return
        self.succeeded.emit(self._generation, full_findings, brief, coverage)


class AnalyticsController(QObject):
    state_changed = Signal()
    loading_started = Signal()
    loading_stage = Signal(int, int, str)
    loading_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.scope_type: str = "all"
        self.scope_id: int | None = None
        self.collections: list[dict] = []
        self.templates: list[dict] = []
        self.brief: list[dict] = []
        self.full_findings: dict = {"entry_findings": [], "coverage_findings": [], "full_findings": []}
        self.coverage: dict | None = None
        self.is_loading: bool = False
        self.load_error: str | None = None
        self._generation = 0
        # Both the QThread and its worker must be kept alive together: an
        # unparented worker with no other Python reference is eligible for
        # garbage collection the moment ``_start_load`` returns, which
        # silently drops the ``thread.started -> worker.run`` connection
        # before the thread ever gets a chance to invoke it (found via a
        # real hang -- ``run()`` was simply never called, no exception,
        # no signal, nothing).
        self._inflight: list[tuple[QThread, _AnalyticsLoadWorker]] = []

    def refresh(self) -> None:
        self.collections = [c for c in get_collections() if not c.get("is_system")]
        self.templates = get_entry_templates()
        if self.scope_type == "collection" and self.scope_id is not None:
            if not any(int(c["id"]) == self.scope_id for c in self.collections):
                self.scope_type = "all"
                self.scope_id = None
        self._start_load()

    def set_scope(self, scope_type: str, scope_id: int | None = None) -> None:
        self.scope_type = scope_type
        self.scope_id = scope_id if scope_type == "collection" else None
        self._start_load()

    def _start_load(self) -> None:
        self._generation += 1
        generation = self._generation
        self.is_loading = True
        self.load_error = None
        self.loading_started.emit()

        thread = QThread()
        worker = _AnalyticsLoadWorker(generation, self.scope_type, self.scope_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        # Connected directly to real bound methods (not a lambda) so
        # PySide6 can detect that ``self`` lives on a different thread
        # than the emitting worker and correctly queue the call onto the
        # Qt UI thread -- see the module docstring's Human Gate 2
        # corrective note for the bug this fixes.
        worker.stage_changed.connect(self._on_stage)
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        # A bound method (self._on_thread_finished), not a lambda/local
        # function, for the same cross-thread-detection reason as above;
        # it identifies which pair to drop via self.sender() rather than
        # a captured closure variable.
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # Kept alive as a (thread, worker) pair in a list -- not one
        # overwritten attribute -- so a superseded-but-still-running load
        # from a previous scope change is never garbage-collected out
        # from under its running QThread; it finishes naturally and
        # self-removes via thread.finished above.
        self._inflight.append((thread, worker))
        thread.start()

    def _on_thread_finished(self) -> None:
        thread = self.sender()
        self._inflight = [pair for pair in self._inflight if pair[0] is not thread]

    def _on_stage(self, generation: int, step: int, total: int, label: str) -> None:
        if generation != self._generation:
            return
        self.loading_stage.emit(step, total, label)

    def _on_succeeded(self, generation: int, full_findings: dict, brief: list[dict], coverage: dict | None) -> None:
        if generation != self._generation:
            return  # a newer scope change superseded this in-flight load; discard
        self.full_findings = full_findings
        self.brief = brief
        self.coverage = coverage
        self.is_loading = False
        self.state_changed.emit()

    def _on_failed(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self.is_loading = False
        self.load_error = message
        self.loading_failed.emit(message)

    def shutdown(self) -> None:
        """Block until every in-flight background load has actually
        stopped.

        Independent-review finding: with no shutdown hook, closing the
        app while a load was still running let ``AnalyticsController``
        (and its ``_inflight`` list -- the only strong reference keeping
        the QThread alive) be torn down while the QThread's
        ``isRunning()`` was still true, which Qt treats as fatal ("QThread:
        Destroyed while thread is still running"). ``MainWindow.closeEvent``
        calls this before accepting the close.

        Removes each pair from ``_inflight`` directly once
        ``thread.wait()`` confirms it has actually stopped, rather than
        relying on the queued ``thread.finished -> _on_thread_finished``
        callback -- that callback only runs once something pumps the Qt
        event loop again, which nothing here guarantees.
        """
        for pair in list(self._inflight):
            thread, _worker = pair
            thread.quit()
            thread.wait(5000)
            if pair in self._inflight:
                self._inflight.remove(pair)

    def actionable_findings(self) -> list[dict]:
        """Full Findings excluding entries with no current Finding
        (``primary_finding == "none"``) -- Coverage Gap findings never
        carry that value, so this only ever filters entry-level rows.
        The unfiltered set remains available via ``full_findings``
        itself for the "show every current Entry" toggle."""
        return [
            item for item in self.full_findings["full_findings"] if item.get("primary_finding") != "none"
        ]

    def collection_names_by_id(self) -> dict[int, str]:
        return {int(c["id"]): str(c["name"]) for c in self.collections}

    def template_names_by_id(self) -> dict[int, str]:
        return {int(t["id"]): str(t["name"]) for t in self.templates}

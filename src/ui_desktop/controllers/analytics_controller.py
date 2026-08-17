from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.analytics import get_collection_coverage_profile
from src.collections import get_collections
from src.db import get_connection
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
"""


class AnalyticsController(QObject):
    state_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.scope_type: str = "all"
        self.scope_id: int | None = None
        self.collections: list[dict] = []
        self.brief: list[dict] = []
        self.full_findings: dict = {"entry_findings": [], "coverage_findings": [], "full_findings": []}
        self.coverage: dict | None = None

    def refresh(self) -> None:
        self.collections = [c for c in get_collections() if not c.get("is_system")]
        if self.scope_type == "collection" and self.scope_id is not None:
            if not any(int(c["id"]) == self.scope_id for c in self.collections):
                self.scope_type = "all"
                self.scope_id = None
        self._reload_analytics()
        self.state_changed.emit()

    def set_scope(self, scope_type: str, scope_id: int | None = None) -> None:
        self.scope_type = scope_type
        self.scope_id = scope_id if scope_type == "collection" else None
        self._reload_analytics()
        self.state_changed.emit()

    def _reload_analytics(self) -> None:
        collection_id = self.scope_id if self.scope_type == "collection" else None
        with get_connection() as connection:
            self.full_findings = get_all_findings(connection, collection_id=collection_id)
            self.brief = build_learning_brief(
                connection, self.full_findings["full_findings"], collection_id=collection_id
            )
            if collection_id is not None:
                self.coverage = get_collection_coverage_profile(connection, collection_id)
            else:
                self.coverage = None

    def actionable_findings(self) -> list[dict]:
        """Full Findings excluding entries with no current Finding
        (``primary_finding == "none"``) -- Coverage Gap findings never
        carry that value, so this only ever filters entry-level rows.
        The unfiltered set remains available via ``full_findings``
        itself for the "show every current Entry" toggle."""
        return [
            item for item in self.full_findings["full_findings"] if item.get("primary_finding") != "none"
        ]

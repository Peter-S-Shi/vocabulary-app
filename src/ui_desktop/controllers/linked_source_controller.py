from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from src.import_export import ImportPreviewError, get_xlsx_sheet_names
from src.linked_sources import (
    LinkedSourceError,
    confirm_collection_source_link,
    confirm_linked_source_refresh,
    get_collection_source_link,
    preview_collection_source_link,
    preview_linked_source_refresh,
    unlink_collection_source,
)

"""
LinkedSourceController owns one Collection's Linked Source workflow
state (DESIGN.md § 7.4 "Linked Source setup/status: B, P6 within
Collection context"; "Linked Source Refresh Preview: B, VR-UTILITY-001").
Delegates entirely to ``src.linked_sources`` -- no SQL, no second
append-source engine, no desktop-only relink capability the core does
not support.

There is no Streamlit precedent for this workflow (M13 closed the core
only); the desktop implementation is the first UI this feature gets.

Initial link vs. refresh dispatch matches the core's own contract
exactly: ``confirm_collection_source_link`` only ever creates the link
row and refuses if one already exists; ``confirm_linked_source_refresh``
only ever updates ``last_refreshed_at`` on an existing link. There is no
dedicated "change the linked path" function -- relinking a missing/
unreadable/replaced source is genuinely ``unlink_collection_source``
(metadata only; Collection/Entries untouched) followed by a fresh
``confirm_collection_source_link``, exactly as the core's own tests
exercise it. This controller does not invent a shortcut around that.
"""

IMPORT_MODE_LABELS: tuple[tuple[str, str], ...] = (
    ("general_entry", "General Entry"),
    ("template_aware", "Template-Based"),
)


class LinkedSourceController(QObject):
    state_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.collection_id: int | None = None
        self.collection_name: str = ""
        self.link: dict | None = None
        self.staged_source_path: str | None = None
        self.staged_import_mode: str = "general_entry"
        self.staged_sheet_name: str | None = None
        self.sheet_names: list[str] = []
        self.preview: dict | None = None
        self.result: dict | None = None

    def open_for_collection(self, collection_id: int, collection_name: str = "") -> None:
        self.collection_id = collection_id
        self.collection_name = collection_name
        self.link = get_collection_source_link(collection_id)
        self._clear_staged()
        self.preview = None
        self.result = None
        self.state_changed.emit()

    def _clear_staged(self) -> None:
        self.staged_source_path = None
        self.staged_import_mode = "general_entry"
        self.staged_sheet_name = None
        self.sheet_names = []

    def stage_source_path(self, path: str) -> None:
        """Only reads the file locally to list XLSX sheet names for the
        picker -- the linked-source core always re-reads the file from
        ``source_path`` itself at preview/confirm/refresh time, since the
        whole point of a *linked* source is that it stays on disk."""
        self.staged_source_path = path
        self.sheet_names = []
        self.staged_sheet_name = None
        if path.lower().endswith(".xlsx"):
            try:
                file_bytes = Path(path).read_bytes()
                self.sheet_names = get_xlsx_sheet_names(file_bytes)
                self.staged_sheet_name = self.sheet_names[0] if self.sheet_names else None
            except (OSError, ImportPreviewError):
                pass  # best-effort only; run_preview() surfaces the real controlled error
        self.preview = None
        self.result = None
        self.state_changed.emit()

    def set_staged_import_mode(self, mode: str) -> None:
        self.staged_import_mode = mode

    def set_staged_sheet(self, sheet_name: str) -> None:
        self.staged_sheet_name = sheet_name

    def run_preview(self) -> None:
        if self.link is not None:
            self.preview = preview_linked_source_refresh(self.collection_id)
        else:
            if not self.staged_source_path:
                return
            self.preview = preview_collection_source_link(
                self.collection_id, self.staged_source_path, self.staged_import_mode, self.staged_sheet_name
            )
        self.result = None
        self.state_changed.emit()

    def can_confirm(self) -> bool:
        return bool(self.preview and self.preview.get("can_confirm")) and self.result is None

    def confirm(self) -> dict:
        """May raise ``LinkedSourceError``."""
        if not self.can_confirm():
            raise LinkedSourceError("Preview a linkable/refreshable source before confirming.")
        if self.link is not None:
            result = confirm_linked_source_refresh(self.collection_id)
        else:
            result = confirm_collection_source_link(
                self.collection_id, self.staged_source_path, self.staged_import_mode, self.staged_sheet_name
            )
        self.result = result
        if result.get("success"):
            self.link = result.get("link") or get_collection_source_link(self.collection_id)
        self.state_changed.emit()
        return result

    def unlink(self) -> dict:
        result = unlink_collection_source(self.collection_id)
        if result.get("success"):
            self.link = None
            self._clear_staged()
            self.preview = None
            self.result = None
        self.state_changed.emit()
        return result

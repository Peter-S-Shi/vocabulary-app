from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.backup import (
    BackupError,
    build_backup_filename,
    build_full_backup_workbook_bytes,
    get_backup_summary,
    get_database_file_bytes,
    preview_backup_workbook,
)
from src.entry_templates import get_entry_templates
from src.import_export import (
    ImportPreviewError,
    build_export_filename,
    build_import_preview,
    detect_file_type,
    export_all_entries_to_rows,
    export_collection_entries_to_rows,
    export_collections_summary_to_rows,
    get_export_columns,
    get_exportable_collections,
    get_xlsx_sheet_names,
    import_collection_rows,
    import_general_entry_rows,
    import_template_entry_rows,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
    sanitize_filename_component,
)
from src.template_definitions import (
    TemplateDefinitionError,
    export_template_definition_csv,
    import_template_definition_csv,
    preview_template_definition_csv,
)

"""
DataToolsController owns the Data Tools workspace's transient
Import/Export workflow state, delegating every parse/validate/import/
export call to the exact same ``src.import_export`` functions the
Streamlit Import/Export page already uses (``build_import_preview``,
``import_general_entry_rows``, ``import_template_entry_rows``,
``import_collection_rows``, ``export_*_to_rows``) -- no SQL, no second
import/export engine.

Preview vs. commit (DESIGN.md § 12.3 "Upload -> Validate -> Preview ->
Confirm -> Import"): ``run_preview()`` never mutates SQLite; only
``confirm_import()`` does, and only after a caller has already produced a
preview. Import mode dispatch mirrors the Streamlit page's confirm-time
writer selection exactly: General Entry -> ``import_general_entry_rows``,
Template-Based -> ``import_template_entry_rows``, Collection/Card ->
``import_collection_rows``.
"""

IMPORT_MODE_LABELS: tuple[tuple[str, str], ...] = (
    ("general_entry", "General Entry Import"),
    ("template_aware", "Template-Based Import"),
    ("collection", "Collection/Card Import"),
)

EXPORT_SCOPE_LABELS: tuple[tuple[str, str], ...] = (
    ("all", "All entries"),
    ("collection", "Selected collection"),
    ("summary", "Collection summary"),
)


class DataToolsController(QObject):
    import_state_changed = Signal()
    export_collections_changed = Signal()
    template_definition_state_changed = Signal()
    restore_preview_state_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.reset_import()
        self.export_collections: list[dict] = []
        self.reset_template_definition_import()
        self.reset_restore_preview()

    # -- Import --------------------------------------------------------

    def reset_import(self) -> None:
        self.file_bytes: bytes | None = None
        self.filename: str = ""
        self.mode: str = "general_entry"
        self.sheet_names: list[str] = []
        self.selected_sheet: str | None = None
        self.preview: dict | None = None
        self.preview_error: str | None = None
        self.duplicate_handling: str = "skip"
        self.target_collection_id: int | None = None
        self.collection_import_mode: str = "append_to_existing"
        self.new_collection_name: str = ""
        self.new_collection_description: str = ""
        self.new_collection_card_size: int = 8
        self.preserve_file_order: bool = True
        self.import_result: dict | None = None
        self.import_error: str | None = None
        self.import_state_changed.emit()

    def load_file(self, file_bytes: bytes, filename: str) -> None:
        """Clears only file-derived state (sheet selection, preview,
        result) -- never ``reset_import()``, which would silently discard
        ``mode``/duplicate-handling/destination choices the user already
        made before picking (or re-picking) a file. Caught by this
        checkpoint's own tests before shipping: choosing "Collection/Card
        Import" and then a file used to silently revert to "General Entry
        Import"."""
        self.file_bytes = file_bytes
        self.filename = filename
        self.sheet_names = []
        self.selected_sheet = None
        self.preview = None
        self.import_result = None
        self.import_error = None
        # Independent-review finding: get_xlsx_sheet_names() can raise
        # ImportPreviewError for a malformed/corrupted/misnamed .xlsx file
        # -- unlike run_preview() below, this used to propagate the
        # exception straight out of the "Choose File" click handler
        # instead of surfacing a controlled inline error the same way an
        # equally-malformed file does during Preview.
        if detect_file_type(filename) == "xlsx":
            try:
                self.sheet_names = get_xlsx_sheet_names(file_bytes)
                self.selected_sheet = self.sheet_names[0] if self.sheet_names else None
                self.preview_error = None
            except ImportPreviewError as error:
                self.preview_error = str(error)
        else:
            self.preview_error = None
        self.import_state_changed.emit()

    def set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self.preview = None
        self.preview_error = None
        self.import_result = None
        self.import_state_changed.emit()

    def set_sheet(self, sheet_name: str) -> None:
        self.selected_sheet = sheet_name

    def set_duplicate_handling(self, value: str) -> None:
        self.duplicate_handling = value

    def set_target_collection(self, collection_id: int | None) -> None:
        self.target_collection_id = collection_id

    def set_collection_import_mode(self, mode: str) -> None:
        self.collection_import_mode = mode

    def set_new_collection_fields(self, name: str, description: str, card_size: int) -> None:
        self.new_collection_name = name
        self.new_collection_description = description
        self.new_collection_card_size = card_size

    def set_preserve_file_order(self, value: bool) -> None:
        self.preserve_file_order = value

    def import_target_collections(self) -> list[dict]:
        return get_exportable_collections()

    def run_preview(self) -> None:
        if self.file_bytes is None:
            return
        options: dict = {}
        if self.selected_sheet:
            options["sheet_name"] = self.selected_sheet
        try:
            self.preview = build_import_preview(self.file_bytes, self.filename, mode=self.mode, options=options)
            self.preview_error = None
        except ImportPreviewError as error:
            self.preview = None
            self.preview_error = str(error)
        self.import_result = None
        self.import_state_changed.emit()

    def can_confirm_import(self) -> bool:
        return bool(self.preview and self.preview["valid_rows"]) and self.import_result is None

    def confirm_import(self) -> dict:
        """May raise ``ValueError`` (e.g. no target Collection selected,
        blank new-Collection name)."""
        if not self.can_confirm_import():
            raise ValueError("Preview a file with at least one valid row before confirming.")
        valid_rows = self.preview["valid_rows"]

        if self.mode == "collection":
            create_options = None
            if self.collection_import_mode == "create_new_collection":
                create_options = {
                    "name": self.new_collection_name,
                    "description": self.new_collection_description,
                    "card_size": self.new_collection_card_size,
                }
            result = import_collection_rows(
                valid_rows,
                import_mode=self.collection_import_mode,
                duplicate_handling=self.duplicate_handling,
                target_collection_id=self.target_collection_id,
                create_collection_options=create_options,
                preserve_file_order=self.preserve_file_order,
            )
        elif self.mode == "template_aware":
            result = import_template_entry_rows(
                valid_rows, duplicate_handling=self.duplicate_handling, target_collection_id=self.target_collection_id
            )
        else:
            result = import_general_entry_rows(
                valid_rows, duplicate_handling=self.duplicate_handling, target_collection_id=self.target_collection_id
            )

        self.import_result = result
        self.import_state_changed.emit()
        return result

    # -- Export ----------------------------------------------------------

    def refresh_export_collections(self) -> None:
        self.export_collections = get_exportable_collections()
        self.export_collections_changed.emit()

    def export_rows(self, scope: str, collection_id: int | None = None) -> tuple[list[dict], list[str]]:
        if scope == "collection":
            if collection_id is None:
                raise ValueError("Select a Collection to export.")
            rows = export_collection_entries_to_rows(collection_id)
        elif scope == "summary":
            rows = export_collections_summary_to_rows()
        else:
            rows = export_all_entries_to_rows()
        return rows, get_export_columns(rows)

    def export_bytes(self, rows: list[dict], columns: list[str], file_format: str, sheet_name: str = "entries") -> bytes:
        if file_format == "xlsx":
            return rows_to_xlsx_bytes(rows, columns, sheet_name=sheet_name)
        return rows_to_csv_bytes(rows, columns)

    def export_filename(self, scope: str, label: str, file_format: str) -> str:
        return build_export_filename(scope, label, file_format)

    # -- Template Definition import/export (M18 Phase C4) ------------------
    # A distinct portability concept from Entry import above: this moves a
    # Template's *field structure*, not Entries. Delegates entirely to
    # src.template_definitions -- no SQL, no second Template-creation path.

    def exportable_templates(self) -> list[dict]:
        return get_entry_templates()

    def export_template_definition(self, template_id: int) -> bytes:
        """May raise ``TemplateDefinitionError`` (template not found, or
        has no fields)."""
        return export_template_definition_csv(template_id)

    def template_definition_export_filename(self, template_name: str) -> str:
        safe_name = sanitize_filename_component(template_name)
        return f"{safe_name}_template_definition.csv"

    def reset_template_definition_import(self) -> None:
        self.template_definition_file_bytes: bytes | None = None
        self.template_definition_filename: str = ""
        self.template_definition_preview: dict | None = None
        self.template_definition_result: dict | None = None
        self.template_definition_state_changed.emit()

    def load_template_definition_file(self, file_bytes: bytes, filename: str) -> None:
        """Only clears file-derived state, matching ``load_file()``'s
        fix above -- there is no other persistent choice to preserve
        here, but the same principle applies."""
        self.template_definition_file_bytes = file_bytes
        self.template_definition_filename = filename
        self.template_definition_preview = None
        self.template_definition_result = None
        self.template_definition_state_changed.emit()

    def run_template_definition_preview(self) -> None:
        if self.template_definition_file_bytes is None:
            return
        self.template_definition_preview = preview_template_definition_csv(self.template_definition_file_bytes)
        self.template_definition_result = None
        self.template_definition_state_changed.emit()

    def can_confirm_template_definition_import(self) -> bool:
        return (
            bool(self.template_definition_preview and self.template_definition_preview["can_import"])
            and self.template_definition_result is None
        )

    def confirm_template_definition_import(self) -> dict:
        """May raise ``TemplateDefinitionError``."""
        if not self.can_confirm_template_definition_import():
            raise TemplateDefinitionError("Preview a valid Template Definition file before confirming.")
        result = import_template_definition_csv(self.template_definition_file_bytes)
        self.template_definition_result = result
        self.template_definition_state_changed.emit()
        return result

    # -- Backup / Restore Preview (M18 Phase C5) ----------------------------
    # Delegates entirely to src.backup. Restore is intentionally
    # PREVIEW-ONLY: no core function performs an actual database restore
    # ("Full database restore is not implemented ... to avoid accidental
    # data loss", the exact product truth the Streamlit Import/Export
    # page's Restore Preview section already states) -- this desktop
    # workflow must not invent a destructive restore capability the core
    # does not support.

    def backup_summary(self) -> dict:
        return get_backup_summary()

    def build_database_backup(self) -> bytes:
        """May raise ``BackupError``."""
        return get_database_file_bytes()

    def build_full_backup_workbook(self) -> bytes:
        """May raise ``BackupError``."""
        return build_full_backup_workbook_bytes()

    def backup_filename(self, kind: str, extension: str) -> str:
        return build_backup_filename(kind, extension)

    def reset_restore_preview(self) -> None:
        self.restore_preview_file_bytes: bytes | None = None
        self.restore_preview_filename: str = ""
        self.restore_preview_result: dict | None = None
        self.restore_preview_state_changed.emit()

    def load_restore_preview_file(self, file_bytes: bytes, filename: str) -> None:
        self.restore_preview_file_bytes = file_bytes
        self.restore_preview_filename = filename
        self.restore_preview_result = None
        self.restore_preview_state_changed.emit()

    def run_restore_preview(self) -> None:
        if self.restore_preview_file_bytes is None:
            return
        self.restore_preview_result = preview_backup_workbook(self.restore_preview_file_bytes)
        self.restore_preview_state_changed.emit()

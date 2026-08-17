from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.entry_templates import (
    ALLOWED_FIELD_TYPES,
    create_entry_template,
    create_template_field,
    delete_entry_template,
    delete_template_field,
    get_entry_template,
    get_entry_templates,
    get_template_fields,
    template_field_has_values,
    template_has_entries,
    update_entry_template,
    update_template_field,
)

"""
TemplatesController owns the Template Manager's transient selection state
only, calling existing ``src.entry_templates`` reads/writes for every fact
it projects or mutates -- no SQL, no second Template/Field model. Every
method delegates to the exact same core functions the Streamlit Templates
page already uses (``create_entry_template``, ``update_entry_template``,
``delete_entry_template``, ``create_template_field``,
``update_template_field``, ``delete_template_field``), including the
existing in-use safety gates (``template_has_entries``,
``template_field_has_values``) that block a destructive delete rather
than merely warning about it.
"""

FIELD_TYPES: tuple[str, ...] = tuple(sorted(ALLOWED_FIELD_TYPES))


class TemplatesController(QObject):
    templates_changed = Signal()
    selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.templates: list[dict] = []
        self.selected_id: int | None = None

    def refresh(self) -> None:
        self.templates = get_entry_templates()
        if self.selected_id is not None and not any(t["id"] == self.selected_id for t in self.templates):
            self.selected_id = None
        self.templates_changed.emit()
        self.selection_changed.emit()

    def select_template(self, template_id: int) -> None:
        self.selected_id = template_id
        self.selection_changed.emit()

    def clear_selection(self) -> None:
        self.selected_id = None
        self.selection_changed.emit()

    def selected_template(self) -> dict | None:
        if self.selected_id is None:
            return None
        return get_entry_template(self.selected_id)

    def selected_fields(self) -> list[dict]:
        if self.selected_id is None:
            return []
        return get_template_fields(self.selected_id)

    # -- Template CRUD -----------------------------------------------------

    def create_new_template(self, name: str, description: str, language: str | None, template_type: str) -> int:
        """May raise ``ValueError`` (blank/duplicate name)."""
        template_id = create_entry_template(
            name=name, description=description, language=language, template_type=template_type, is_system=False
        )
        self.refresh()
        self.select_template(template_id)
        return template_id

    def update_selected_template(self, name: str, description: str, language: str | None, template_type: str) -> None:
        """May raise ``ValueError`` (not found, system template, blank/duplicate name)."""
        if self.selected_id is None:
            raise ValueError("No Template is selected.")
        update_entry_template(
            template_id=self.selected_id, name=name, description=description, language=language, template_type=template_type
        )
        self.refresh()

    def can_delete_selected_template(self) -> bool:
        if self.selected_id is None:
            return False
        template = self.selected_template()
        if template is None or template["is_system"]:
            return False
        return not template_has_entries(self.selected_id)

    def delete_selected_template(self) -> bool:
        if self.selected_id is None:
            raise ValueError("No Template is selected.")
        deleted = delete_entry_template(self.selected_id)
        if deleted:
            self.clear_selection()
            self.refresh()
        return deleted

    # -- Field CRUD ----------------------------------------------------------

    def create_field(self, field_key: str, field_label: str, field_type: str, required: bool, display_order: int) -> int:
        """May raise ``ValueError`` (system template, duplicate key, blank label)."""
        if self.selected_id is None:
            raise ValueError("No Template is selected.")
        field_id = create_template_field(
            template_id=self.selected_id,
            field_key=field_key,
            field_label=field_label,
            field_type=field_type,
            required=required,
            display_order=display_order,
        )
        self.selection_changed.emit()
        self.templates_changed.emit()
        return field_id

    def update_field(self, field_id: int, field_label: str, field_type: str, required: bool, display_order: int) -> None:
        """May raise ``ValueError`` (system template, blank label)."""
        update_template_field(
            field_id=field_id, field_label=field_label, field_type=field_type, required=required, display_order=display_order
        )
        self.selection_changed.emit()

    def field_has_values(self, field_id: int) -> bool:
        return template_field_has_values(field_id)

    def delete_field(self, field_id: int) -> bool:
        deleted = delete_template_field(field_id)
        if deleted:
            self.selection_changed.emit()
            self.templates_changed.emit()
        return deleted

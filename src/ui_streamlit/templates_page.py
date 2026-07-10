import streamlit as st

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
from src.import_export import (
    build_template_import_template_filename,
    get_export_columns,
    get_template_import_template_rows,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
)
from src.ui_streamlit.common import LANGUAGES, option_index


FIELD_TYPES = sorted(ALLOWED_FIELD_TYPES)
LANGUAGE_OPTIONS = ["", *LANGUAGES, "any"]


def _template_label(template: dict) -> str:
    system_marker = "system" if template["is_system"] else "custom"
    return f"{template['id']} - {template['name']} ({system_marker})"


def _show_action_error(error: Exception) -> None:
    st.error("Validation failed. Please fix the highlighted issue(s) below; your input has been kept.")
    st.error(str(error))


def _render_template_list(templates: list[dict]) -> None:
    st.header("Templates")
    if not templates:
        st.info("No templates found.")
        return

    rows = [
        {
            "id": template["id"],
            "name": template["name"],
            "description": template["description"] or "",
            "language": template["language"] or "",
            "template_type": template["template_type"],
            "is_system": "Yes" if template["is_system"] else "No",
            "field_count": template["field_count"],
            "created_at": template["created_at"],
            "updated_at": template["updated_at"],
        }
        for template in templates
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_create_template_form() -> None:
    st.header("Create Custom Template")

    st.caption(
        "Create a template here, then select it under Inspect Template to add custom "
        "field keys, labels, field types, and required flags."
    )

    with st.form("create_template_form"):
        name = st.text_input("Name")
        description = st.text_area("Description")
        language = st.selectbox("Language", LANGUAGE_OPTIONS)
        template_type = st.text_input("Template Type", value="custom")
        submitted = st.form_submit_button("Create Template")

    if submitted:
        try:
            create_entry_template(
                name=name,
                description=description,
                language=language or None,
                template_type=template_type or "custom",
                is_system=False,
            )
        except ValueError as error:
            _show_action_error(error)
        else:
            st.success("Template created.")
            st.rerun()


def _render_template_metadata(template: dict) -> None:
    st.subheader("Template Details")
    detail_rows = [
        {"field": "id", "value": template["id"]},
        {"field": "name", "value": template["name"]},
        {"field": "description", "value": template["description"] or ""},
        {"field": "language", "value": template["language"] or ""},
        {"field": "template_type", "value": template["template_type"]},
        {"field": "is_system", "value": "Yes" if template["is_system"] else "No"},
        {"field": "created_at", "value": template["created_at"]},
        {"field": "updated_at", "value": template["updated_at"]},
    ]
    st.dataframe(detail_rows, use_container_width=True, hide_index=True)

    if template["is_system"]:
        st.info("System template: read-only.")


def _render_fields_table(fields: list[dict]) -> None:
    st.subheader("Fields")
    if not fields:
        st.info("No fields yet.")
        return

    rows = [
        {
            "display_order": field["display_order"],
            "field_key": field["field_key"],
            "field_label": field["field_label"],
            "field_type": field["field_type"],
            "required": "Yes" if field["required"] else "No",
        }
        for field in fields
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_template_export_control(template: dict) -> None:
    st.subheader("Export Template")
    try:
        rows = get_template_import_template_rows(template["id"])
    except ValueError as error:
        _show_action_error(error)
        return

    columns = get_export_columns(rows)
    st.caption("Download a fillable Template-Based Import file for this template.")
    st.dataframe(rows[:3], use_container_width=True, hide_index=True, column_order=columns)

    file_format = st.radio(
        "Template File Format",
        ["CSV", "XLSX"],
        horizontal=True,
        key=f"template_export_format_{template['id']}",
    )
    if file_format == "CSV":
        data = rows_to_csv_bytes(rows, columns)
        extension = "csv"
        mime = "text/csv"
    else:
        data = rows_to_xlsx_bytes(rows, columns, sheet_name="template_import")
        extension = "xlsx"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    st.download_button(
        "Export Template",
        data=data,
        file_name=build_template_import_template_filename(template["name"], extension),
        mime=mime,
        key=f"template_export_download_{template['id']}",
    )


def _render_edit_template_form(template: dict) -> None:
    st.subheader("Edit Template")

    with st.form(f"edit_template_{template['id']}"):
        name = st.text_input("Name", value=template["name"])
        description = st.text_area(
            "Description",
            value=template["description"] or "",
        )
        language = st.selectbox(
            "Language",
            LANGUAGE_OPTIONS,
            index=option_index(LANGUAGE_OPTIONS, template["language"] or ""),
        )
        template_type = st.text_input(
            "Template Type",
            value=template["template_type"] or "custom",
        )
        submitted = st.form_submit_button("Save Template")

    if submitted:
        try:
            update_entry_template(
                template_id=template["id"],
                name=name,
                description=description,
                language=language or None,
                template_type=template_type,
            )
        except ValueError as error:
            _show_action_error(error)
        else:
            st.success("Template updated.")
            st.rerun()


def _render_add_field_form(template: dict) -> None:
    st.subheader("Add Field")
    st.caption(
        "Use Field Key for the stored snake_case key, Field Label for the user-facing "
        "name, and Required to make the field mandatory."
    )

    with st.form(f"add_field_{template['id']}"):
        field_key = st.text_input("Field Key")
        field_label = st.text_input("Field Label")
        field_type = st.selectbox("Field Type", FIELD_TYPES)
        required = st.checkbox("Required")
        display_order = st.number_input(
            "Display Order",
            min_value=0,
            step=1,
            value=0,
        )
        submitted = st.form_submit_button("Add Field")

    if submitted:
        try:
            create_template_field(
                template_id=template["id"],
                field_key=field_key,
                field_label=field_label,
                field_type=field_type,
                required=required,
                display_order=int(display_order),
            )
        except ValueError as error:
            _show_action_error(error)
        else:
            st.success("Field added.")
            st.rerun()


def _render_edit_field_form(fields: list[dict]) -> None:
    if not fields:
        return

    st.subheader("Edit Field")
    selected_field = st.selectbox(
        "Select field",
        fields,
        format_func=lambda field: f"{field['display_order']} - {field['field_key']}",
        key="template_field_edit_select",
    )

    with st.form(f"edit_field_{selected_field['id']}"):
        st.text_input("Field Key", value=selected_field["field_key"], disabled=True)
        field_label = st.text_input("Field Label", value=selected_field["field_label"])
        field_type = st.selectbox(
            "Field Type",
            FIELD_TYPES,
            index=option_index(FIELD_TYPES, selected_field["field_type"]),
        )
        required = st.checkbox("Required", value=bool(selected_field["required"]))
        display_order = st.number_input(
            "Display Order",
            min_value=0,
            step=1,
            value=int(selected_field["display_order"]),
        )
        submitted = st.form_submit_button("Save Field")

    if submitted:
        try:
            update_template_field(
                field_id=selected_field["id"],
                field_label=field_label,
                field_type=field_type,
                required=required,
                display_order=int(display_order),
            )
        except ValueError as error:
            _show_action_error(error)
        else:
            st.success("Field updated.")
            st.rerun()


def _render_delete_field_control(fields: list[dict]) -> None:
    if not fields:
        return

    st.subheader("Delete Field")
    selected_field = st.selectbox(
        "Field to delete",
        fields,
        format_func=lambda field: f"{field['display_order']} - {field['field_key']}",
        key="template_field_delete_select",
    )
    has_values = template_field_has_values(selected_field["id"])
    if has_values:
        st.warning("This field already has entry values and cannot be deleted safely in this milestone.")

    confirmed = st.checkbox(
        "I confirm I want to delete this field.",
        key=f"confirm_delete_field_{selected_field['id']}",
        disabled=has_values,
    )
    if st.button("Delete Field", disabled=has_values or not confirmed):
        if delete_template_field(selected_field["id"]):
            st.success("Field deleted.")
            st.rerun()
        else:
            st.warning("Field was not deleted.")


def _render_delete_template_control(template: dict) -> None:
    st.subheader("Delete Template")
    has_entries = template_has_entries(template["id"])
    if has_entries:
        st.warning("This template is used by existing entries and cannot be deleted safely.")

    confirmed = st.checkbox(
        "I confirm I want to delete this template.",
        key=f"confirm_delete_template_{template['id']}",
        disabled=has_entries,
    )
    if st.button("Delete Template", disabled=has_entries or not confirmed):
        if delete_entry_template(template["id"]):
            st.success("Template deleted.")
            st.rerun()
        else:
            st.warning("Template was not deleted.")


def _render_custom_template_controls(template: dict, fields: list[dict]) -> None:
    edit_col, add_col = st.columns(2)
    with edit_col:
        _render_edit_template_form(template)
    with add_col:
        _render_add_field_form(template)

    field_edit_col, field_delete_col = st.columns(2)
    with field_edit_col:
        _render_edit_field_form(fields)
    with field_delete_col:
        _render_delete_field_control(fields)

    _render_delete_template_control(template)


def render_templates_page() -> None:
    templates = get_entry_templates()
    _render_template_list(templates)
    _render_create_template_form()

    st.header("Inspect Template")
    if not templates:
        return

    selected_template = st.selectbox(
        "Template",
        templates,
        format_func=_template_label,
        key="template_management_select",
    )
    template = get_entry_template(selected_template["id"])
    if template is None:
        st.warning("The selected template no longer exists.")
        return

    fields = get_template_fields(template["id"])
    _render_template_metadata(template)
    _render_fields_table(fields)
    _render_template_export_control(template)

    if template["is_system"]:
        return

    _render_custom_template_controls(template, fields)

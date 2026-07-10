import streamlit as st

from src.app_config import DATABASE_PATH_ENV, get_app_storage_summary
from src.db import get_connection
from src.entry_templates import get_entry_templates, get_template_fields
from src.migrations import get_compatibility_status
from src.ui_streamlit.templates_page import render_templates_page


def _render_entry_templates_view() -> None:
    st.header("Entry Templates")

    templates = get_entry_templates()
    if not templates:
        st.info("No entry templates found yet. Restart the app to initialize templates.")
        return

    template_rows = [
        {
            "id": template["id"],
            "name": template["name"],
            "type": template["template_type"],
            "language": template["language"] or "",
            "system": "Yes" if template["is_system"] else "No",
            "fields": template["field_count"],
        }
        for template in templates
    ]
    st.dataframe(template_rows, use_container_width=True, hide_index=True)

    selected_template = st.selectbox(
        "Inspect template fields",
        templates,
        format_func=lambda template: template["name"],
    )
    fields = get_template_fields(selected_template["id"])

    if fields:
        field_rows = [
            {
                "order": field["display_order"],
                "key": field["field_key"],
                "label": field["field_label"],
                "type": field["field_type"],
                "required": "Yes" if field["required"] else "No",
            }
            for field in fields
        ]
        st.dataframe(field_rows, use_container_width=True, hide_index=True)
    else:
        st.info("This template has no fields yet.")


def render_settings_page() -> None:
    st.title("Settings / Data")

    st.header("User-Owned Content & Safety Notes")
    st.info(
        "Vocabulary App stores and organizes entries that you create, edit, or import. "
        "It does not include built-in dictionary data, pronunciation audio, voice "
        "models, copyrighted word lists, or AI-generated learning content."
    )
    st.write(
        "Review your entries carefully. The app supports organization, review, quiz, "
        "statistics, import/export, backup, and daily workflow, but it does not "
        "guarantee that user-created content is linguistically correct."
    )
    st.caption(
        "When importing CSV/XLSX files, use content you created or have permission to use."
    )

    st.header("Local Data")
    storage = get_app_storage_summary()
    storage_rows = [
        {"Setting": "Database path", "Value": str(storage["database_path"])},
        {"Setting": "Data directory", "Value": str(storage["data_directory"])},
        {"Setting": "Backup directory", "Value": str(storage["backup_directory"])},
        {"Setting": "Path source", "Value": storage["path_source"]},
        {
            "Setting": "Database file exists",
            "Value": "Yes" if storage["database_exists"] else "No",
        },
        {"Setting": "Local-first", "Value": "Enabled"},
    ]
    st.dataframe(storage_rows, use_container_width=True, hide_index=True)
    st.write(
        "This app is local-first. The database file is generated on this computer and "
        "should not be committed to GitHub because it can contain personal vocabulary "
        "and learning records."
    )
    st.caption(
        f"Advanced users can set {DATABASE_PATH_ENV} before launch. This page does "
        "not switch or migrate database paths."
    )

    st.header("Software Update Compatibility")
    with get_connection() as connection:
        compatibility = get_compatibility_status(connection)

    compatibility_rows = [
        {"Setting": "Schema version", "Value": compatibility["schema_version"]},
        {"Setting": "App data version", "Value": compatibility["app_data_version"]},
        {"Setting": "Last migration time", "Value": compatibility["last_migration_at"]},
    ]
    for feature_key, enabled in compatibility["feature_flags"].items():
        compatibility_rows.append(
            {
                "Setting": feature_key,
                "Value": "Enabled" if enabled else "Disabled",
            }
        )
    st.dataframe(compatibility_rows, use_container_width=True, hide_index=True)
    st.caption(
        "This panel is read-only. Future database changes should use additive, "
        "idempotent migrations and preserve user-created entries, logs, templates, "
        "imports, exports, and backups."
    )

    st.header("Current Version")
    st.write(f"App version: {storage['app_version']} (Milestone 10.7)")

    st.header("Template Management")
    st.caption(
        "Create custom templates and manage field keys, labels, field types, and "
        "required flags here. The same tool is also available in Entries / Templates."
    )
    with st.expander("Open Template Management", expanded=False):
        render_templates_page()

    with st.expander("Read-only Template Overview", expanded=False):
        _render_entry_templates_view()

    st.header("Data Tools")
    st.write(
        "Use Import / Export for validated CSV/XLSX transfer, local backups, and "
        "restore preview. Database reset remains an explicit manual action."
    )

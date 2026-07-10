from __future__ import annotations

import hashlib

import streamlit as st

from src.backup import (
    BackupError,
    build_backup_filename,
    build_full_backup_workbook_bytes,
    get_backup_summary,
    get_database_file_bytes,
    preview_backup_workbook,
)

from src.import_export import (
    ImportPreviewError,
    build_export_filename,
    build_import_preview,
    export_all_entries_to_rows,
    export_collection_entries_to_rows,
    export_collection_card_entries_to_rows,
    export_collections_summary_to_rows,
    export_template_entries_to_rows,
    get_export_columns,
    get_exportable_collections,
    get_exportable_templates,
    get_import_sample_rows,
    get_xlsx_sheet_names,
    get_template_field_map_rows,
    IMPORT_SAMPLE_LABELS,
    import_general_entry_rows,
    import_template_entry_rows,
    import_collection_rows,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
)


def _render_export_section() -> None:
    st.subheader("Export")
    collections = get_exportable_collections()
    templates = get_exportable_templates()
    control_col1, control_col2 = st.columns(2)
    with control_col1:
        scope = st.radio(
            "Export Scope",
            ["All entries", "Selected collection", "Selected collection card", "Selected template", "Collection summary"],
            horizontal=True,
        )
    with control_col2:
        file_format = st.radio("File Format", ["CSV", "XLSX"], horizontal=True)

    filename_scope, filename_label = "all_entries", "all"
    if scope in {"Selected collection", "Selected collection card"}:
        if not collections:
            st.info("No collections found yet.")
            return
        selected = st.selectbox("Collection", collections, format_func=lambda item: f"{item['name']} ({item['entry_count']} entries)")
        if scope == "Selected collection card":
            card_size = max(int(selected.get("card_size") or 8), 1)
            card_count = (int(selected.get("entry_count") or 0) + card_size - 1) // card_size
            if card_count == 0:
                st.info("No cards found for this collection.")
                return
            else:
                card_number = st.selectbox("Card #", list(range(1, card_count + 1)))
                rows = export_collection_card_entries_to_rows(selected["id"], card_number)
            filename_scope, filename_label = "collection", f"{selected['name']}_card_{card_number}"
        else:
            rows = export_collection_entries_to_rows(selected["id"])
            filename_scope, filename_label = "collection", selected["name"]
    elif scope == "Selected template":
        if not templates:
            st.info("No templates found yet.")
            return
        selected = st.selectbox("Template", templates, format_func=lambda item: f"{item['name']} ({item['entry_count']} entries)")
        rows = export_template_entries_to_rows(selected["id"])
        filename_scope, filename_label = "template", selected["name"]
    elif scope == "Collection summary":
        rows = export_collections_summary_to_rows()
        filename_scope, filename_label = "collections", "summary"
    else:
        rows = export_all_entries_to_rows()

    try:
        columns = get_export_columns(rows)
    except Exception as error:
        st.error("Could not prepare this export.")
        st.caption(str(error))
        return
    metric_col1, metric_col2 = st.columns(2)
    metric_col1.metric("Rows", len(rows)); metric_col2.metric("Columns", len(columns))
    if not rows:
        st.info("No rows found for this export option.")
        return
    st.write("Preview")
    st.dataframe(rows[:20], width="stretch", hide_index=True, column_order=columns)
    if file_format == "CSV":
        file_bytes, mime_type, extension = rows_to_csv_bytes(rows, columns), "text/csv", "csv"
    else:
        file_bytes, mime_type, extension = rows_to_xlsx_bytes(rows, columns), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    filename = build_export_filename(filename_scope, filename_label, extension)
    st.caption(f"Selected scope: {scope} | Filename: {filename}")
    st.download_button("Download Export", data=file_bytes, file_name=filename, mime=mime_type, type="primary")


def _preview_table_rows(rows: list[dict], include_errors: bool = False) -> list[dict]:
    display_rows = []
    for row in rows[:50]:
        data = row.get("data", {})
        display = {
            "row": row.get("row_number"),
            "template": data.get("resolved_template_name") or data.get("template_name", ""),
            "template_type": data.get("resolved_template_type") or data.get("template_type", ""),
            "language": data.get("language", ""),
            "entry_type": data.get("entry_type") or "word",
            "term": data.get("resolved_term") or data.get("term", ""),
            "meaning": data.get("resolved_meaning") or data.get("meaning", ""),
            "collection": data.get("collection_name", ""),
            "position": data.get("position", ""),
            "card": data.get("card_number", ""),
            "duplicate": "Yes" if row.get("duplicate_candidate") else "No",
            "warnings": "; ".join(row.get("warnings", [])),
        }
        if include_errors:
            display["errors"] = "; ".join(row.get("errors", []))
        display_rows.append(display)
    return display_rows


def _reset_import_preview(preview_key: str) -> None:
    st.session_state.import_preview_hash = preview_key
    st.session_state.import_preview_result = None
    st.session_state.import_result = None
    st.session_state.import_preview_completed = False


def _render_import_section() -> None:
    st.subheader("Import")
    import_mode_label = st.radio(
        "Import Mode",
        ["General Entry Import", "Template-Based Import", "Collection/Card Import"],
        horizontal=True,
    )
    is_template_mode = import_mode_label == "Template-Based Import"
    is_collection_mode = import_mode_label == "Collection/Card Import"
    validation_mode = "collection" if is_collection_mode else "template_aware" if is_template_mode else "general_entry"
    captions = {
        "general_entry": "Import canonical General Entry rows.",
        "template_aware": "Import rows into existing templates using template_name/template_type and field:<field_key> columns.",
        "collection": "Import ordered General or template-based rows into one existing or explicitly created collection.",
    }
    st.caption(captions[validation_mode])
    uploaded_file = st.file_uploader("CSV or XLSX File", type=["csv", "xlsx"], key="entry_import_file")
    if uploaded_file is None:
        st.info("Please upload a CSV or XLSX file first.")
        return
    file_bytes = uploaded_file.getvalue()
    selected_sheet_name = None
    if uploaded_file.name.lower().endswith(".xlsx"):
        try:
            sheet_names = get_xlsx_sheet_names(file_bytes)
        except ImportPreviewError as error:
            st.error(str(error))
            return
        if not sheet_names:
            st.error("This XLSX file does not contain any worksheets.")
            return
        selected_sheet_name = st.selectbox("Worksheet", sheet_names, key="entry_import_worksheet")
        st.caption(f"Selected worksheet: {selected_sheet_name}")
    preview_key = f"{validation_mode}:{selected_sheet_name or ''}:{hashlib.sha256(file_bytes).hexdigest()}"
    if st.session_state.get("import_preview_hash") != preview_key:
        _reset_import_preview(preview_key)
    preview_label = "Preview Collection Import" if is_collection_mode else "Preview Template Import" if is_template_mode else "Preview Import"
    if st.button(preview_label, type="primary"):
        try:
            preview_options = {"sheet_name": selected_sheet_name} if selected_sheet_name else None
            st.session_state.import_preview_result = build_import_preview(
                file_bytes,
                uploaded_file.name,
                mode=validation_mode,
                options=preview_options,
            )
            st.session_state.import_result = None; st.session_state.import_preview_completed = False
        except ImportPreviewError as error:
            st.session_state.import_preview_result = None; st.error(str(error))
        except Exception as error:
            st.session_state.import_preview_result = None; st.error("Could not build the import preview."); st.caption(str(error))
    preview = st.session_state.get("import_preview_result")
    if not preview:
        return
    summary = preview["summary"]
    for column, label, key in zip(st.columns(5), ["Rows", "Valid", "Invalid", "Warnings", "Duplicates"], ["total_rows", "valid_count", "invalid_count", "warning_count", "duplicate_candidate_count"]):
        column.metric(label, summary[key])
    if is_template_mode or is_collection_mode:
        detected = sorted({row.get("data", {}).get("resolved_template_name") for row in preview["valid_rows"] + preview["invalid_rows"] if row.get("data", {}).get("resolved_template_name")})
        st.caption("Detected templates: " + (", ".join(detected) if detected else "General Entry rows"))
    st.write("Valid Rows")
    if preview["valid_rows"]:
        st.dataframe(_preview_table_rows(preview["valid_rows"]), width="stretch", hide_index=True)
    else:
        st.info("No valid rows to import.")
    with st.expander("Invalid Rows", expanded=bool(preview["invalid_rows"])):
        if preview["invalid_rows"]:
            st.dataframe(_preview_table_rows(preview["invalid_rows"], True), width="stretch", hide_index=True)
        else:
            st.info("No invalid rows.")
    if preview["warnings"]:
        with st.expander("Warnings", expanded=False): st.dataframe(preview["warnings"], width="stretch", hide_index=True)
    if not preview["valid_rows"]:
        return
    if summary["invalid_count"]: st.warning("Invalid rows will be skipped.")
    if summary["duplicate_candidate_count"]: st.warning("Some rows look like duplicates. Choose how to handle them before importing.")

    duplicate_label = st.radio("Duplicate Handling", ["Skip duplicates", "Import anyway"], index=0)
    collections = get_exportable_collections()
    target_collection = None; destination = None; create_options = None; preserve_order = True
    if is_collection_mode:
        destination = st.radio("Destination", ["Append to existing collection", "Create new collection"], horizontal=True)
        if destination == "Append to existing collection":
            if not collections:
                st.info("No collections found yet. Choose Create new collection.")
                return
            target_collection = st.selectbox("Target Collection", collections, format_func=lambda item: item["name"])
            if target_collection.get("is_system"):
                st.warning("You are importing into a system collection. This may affect special study pools.")
        else:
            first_data = preview["valid_rows"][0].get("data", {})
            name = st.text_input("New Collection Name", value=str(first_data.get("collection_name") or ""))
            description = st.text_input("Description", value=str(first_data.get("collection_description") or ""))
            try: default_card_size = max(int(first_data.get("card_size") or 8), 1)
            except (TypeError, ValueError): default_card_size = 8
            card_size = st.number_input("Card Size", min_value=1, max_value=100, value=default_card_size, step=1)
            create_options = {"name": name, "description": description, "card_size": int(card_size)}
        preserve_order = st.checkbox("Use file order / position when available", value=True)
    else:
        target_collection = st.selectbox("Add to Collection", [None] + collections, format_func=lambda item: "None" if item is None else item["name"])

    confirmation_text = "I understand this will create entries and add them to the selected collection."
    if is_collection_mode and destination == "Create new collection": confirmation_text = "I understand this will create a new collection and import entries into it."
    elif is_template_mode: confirmation_text = "I understand this will add template-based entries and field values to my database."
    elif not is_collection_mode: confirmation_text = "I understand this will add new General Entry rows to my database."
    confirmed = st.checkbox(confirmation_text)
    already_imported = bool(st.session_state.get("import_preview_completed"))
    if already_imported: st.info("This preview has already been imported. Upload a new file or preview again to start a new import action.")
    button_label = "Confirm Import Into Collection" if is_collection_mode else "Confirm Import Template Rows" if is_template_mode else "Confirm Import Valid Rows"
    if st.button(button_label, disabled=not confirmed or already_imported):
        try:
            duplicate_handling = "skip" if duplicate_label == "Skip duplicates" else "import_anyway"
            if is_collection_mode:
                result = import_collection_rows(
                    preview["valid_rows"],
                    import_mode="create_new_collection" if destination == "Create new collection" else "append_to_existing",
                    duplicate_handling=duplicate_handling,
                    target_collection_id=None if target_collection is None else int(target_collection["id"]),
                    create_collection_options=create_options,
                    preserve_file_order=preserve_order,
                )
            else:
                writer = import_template_entry_rows if is_template_mode else import_general_entry_rows
                result = writer(preview["valid_rows"], duplicate_handling=duplicate_handling, target_collection_id=None if target_collection is None else int(target_collection["id"]))
            st.session_state.import_result = result; st.session_state.import_preview_completed = True
        except Exception as error:
            st.error("Import failed before the batch could be completed."); st.caption(str(error))
    result = st.session_state.get("import_result")
    if result:
        st.success("Import finished.")
        if is_collection_mode:
            metrics = [("Imported", result["imported_entry_count"]), ("Duplicates Skipped", result["skipped_duplicate_count"]), ("Failed", result["failed_count"]), ("Added", result["added_to_collection_count"]), ("Position Range", f"{result['start_position'] or 'N/A'}-{result['end_position'] or 'N/A'}")]
            st.caption(f"Collection: {result.get('collection_name') or 'Not created'}")
        elif is_template_mode:
            metrics = [("Imported", result["imported_count"]), ("Field Values", result["field_value_count"]), ("Duplicates Skipped", result["skipped_duplicate_count"]), ("Failed", result["failed_count"]), ("Added", result["added_to_collection_count"])]
        else:
            metrics = [("Imported", result["imported_count"]), ("Duplicates Skipped", result["skipped_duplicate_count"]), ("Failed", result["failed_count"]), ("Added", result["collection_added_count"])]
        for column, (label, value) in zip(st.columns(len(metrics)), metrics): column.metric(label, value)
        if result["errors"]: st.dataframe(result["errors"], width="stretch", hide_index=True)
        if result["warnings"]:
            with st.expander("Import Warnings", expanded=False): st.dataframe(result["warnings"], width="stretch", hide_index=True)


def _render_sample_files_section() -> None:
    st.subheader("Templates / Sample Files")
    options = list(IMPORT_SAMPLE_LABELS) + ["template_field_map"]
    selected = st.selectbox(
        "Sample",
        options,
        format_func=lambda key: "Current Template Field Map" if key == "template_field_map" else f"{IMPORT_SAMPLE_LABELS[key]} Sample",
    )
    file_format = st.radio("Sample Format", ["CSV", "XLSX"], horizontal=True)
    if selected == "template_field_map":
        rows = get_template_field_map_rows()
        filename_base = "current_template_field_map"
    else:
        rows = get_import_sample_rows(selected)
        filename_base = f"{selected}_sample"
    if not rows:
        st.info("No templates found yet.")
        return
    columns = get_export_columns(rows)
    st.dataframe(rows, width="stretch", hide_index=True, column_order=columns)
    if file_format == "CSV":
        data, extension, mime = rows_to_csv_bytes(rows, columns), "csv", "text/csv"
    else:
        data = rows_to_xlsx_bytes(rows, columns, sheet_name="template_fields" if selected == "template_field_map" else "sample")
        extension, mime = "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    st.download_button(
        "Download Sample File" if selected != "template_field_map" else "Download Template Field Map",
        data=data,
        file_name=f"vocabulary_{filename_base}.{extension}",
        mime=mime,
    )


def _render_help_section() -> None:
    st.subheader("Help / Safety Notes")
    st.info(
        "Import files should contain content you created, collected for permitted "
        "personal study, or otherwise have the right to use."
    )
    st.caption(
        "The app validates file structure, not dictionary accuracy, pronunciation, "
        "copyright status, or linguistic correctness."
    )
    st.write("Import safety model")
    st.markdown("1. Upload\n2. Preview and fix errors\n3. Choose duplicate handling\n4. Confirm\n5. Import")
    st.info("Invalid rows are skipped. Unknown templates and template fields are rejected. Collections are created only through the explicit new-collection option.")
    st.warning("Backup restore is preview-only. The active database is never overwritten from this page.")


def _render_backup_section() -> None:
    st.subheader("Backup")
    st.caption("Download a read-only backup of your local vocabulary data.")
    try:
        summary = get_backup_summary()
        database_bytes = get_database_file_bytes()
        workbook_bytes = build_full_backup_workbook_bytes()
    except BackupError as error:
        st.error(str(error))
        return

    metric_data = [
        ("Entries", summary["entries"]), ("Collections", summary["collections"]),
        ("Templates", summary["templates"]), ("Field Values", summary["entry_field_values"]),
        ("Quiz Sessions", summary["quiz_sessions"]), ("Quiz Logs", summary["quiz_item_logs"]),
        ("Review Logs", summary["review_logs"]),
    ]
    for column, (label, value) in zip(st.columns(len(metric_data)), metric_data):
        column.metric(label, value)

    download_col1, download_col2 = st.columns(2)
    with download_col1:
        st.download_button(
            "Download SQLite Database Backup",
            data=database_bytes,
            file_name=build_backup_filename("database", "sqlite3"),
            mime="application/octet-stream",
            type="primary",
        )
        st.warning("Keep this file safe. It is a direct copy of your local database.")
    with download_col2:
        st.download_button(
            "Download Full Data Backup Workbook",
            data=workbook_bytes,
            file_name=build_backup_filename("full", "xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption("Entries, templates, collections, review logs, and quiz logs are stored as separate sheets.")

    st.write("Restore Preview")
    st.info("This does not restore or import anything. It only inspects the uploaded backup workbook.")
    st.warning("Full database restore is not implemented in this milestone to avoid accidental data loss.")
    uploaded = st.file_uploader("Backup Workbook", type=["xlsx"], key="backup_preview_file")
    if uploaded is None:
        return
    backup_bytes = uploaded.getvalue()
    backup_hash = hashlib.sha256(backup_bytes).hexdigest()
    if st.session_state.get("backup_preview_hash") != backup_hash:
        st.session_state.backup_preview_hash = backup_hash
        st.session_state.backup_preview_result = None
    if st.button("Preview Backup"):
        st.session_state.backup_preview_result = preview_backup_workbook(backup_bytes)
    result = st.session_state.get("backup_preview_result")
    if not result:
        return
    if result["valid_backup"]:
        st.success("This workbook contains supported backup metadata.")
    for error in result["errors"]:
        st.error(error)
    for warning in result["warnings"]:
        st.warning(warning)
    if result["backup_metadata"]:
        st.dataframe(
            [{"key": key, "value": value} for key, value in result["backup_metadata"].items()],
            width="stretch", hide_index=True,
        )
    st.dataframe(result["sheets"], width="stretch", hide_index=True)


def render_import_export_page() -> None:
    st.title("Import / Export")
    st.caption("Move vocabulary data through the app-defined CSV/XLSX format.")
    export_tab, import_tab, samples_tab, backup_tab, help_tab = st.tabs(
        ["Export", "Import", "Templates / Sample Files", "Backup", "Help / Safety Notes"]
    )
    with export_tab:
        _render_export_section()
    with import_tab:
        _render_import_section()
    with samples_tab:
        _render_sample_files_section()
    with backup_tab:
        _render_backup_section()
    with help_tab:
        _render_help_section()


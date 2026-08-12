from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from sqlite3 import Connection
from typing import Iterator

from src.db import get_connection
from src.entry_templates import (
    normalize_template_field_key,
    validate_template_field_type,
)
from src.import_export import ImportPreviewError, parse_csv_bytes, rows_to_csv_bytes


TEMPLATE_DEFINITION_VERSION = "1"
TEMPLATE_DEFINITION_COLUMNS = [
    "definition_version",
    "template_name",
    "template_description",
    "language",
    "template_type",
    "field_key",
    "field_label",
    "field_type",
    "required",
    "display_order",
]


class TemplateDefinitionError(ValueError):
    """A controlled Template Definition error suitable for a future UI."""


@contextmanager
def _connection(connection: Connection | None = None) -> Iterator[Connection]:
    if connection is not None:
        yield connection
        return

    owned_connection = get_connection()
    try:
        yield owned_connection
    finally:
        owned_connection.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _template_row(connection: Connection, template_id: int) -> dict | None:
    row = connection.execute(
        """
        SELECT id, name, description, language, template_type, is_system
        FROM entry_templates
        WHERE id = ?
        """,
        (int(template_id),),
    ).fetchone()
    return dict(row) if row is not None else None


def _template_fields(connection: Connection, template_id: int) -> list[dict]:
    rows = connection.execute(
        """
        SELECT field_key, field_label, field_type, required, display_order
        FROM entry_template_fields
        WHERE template_id = ?
        ORDER BY display_order ASC, field_key ASC
        """,
        (int(template_id),),
    ).fetchall()
    return [dict(row) for row in rows]


def export_template_definition_rows(
    template_id: int,
    connection: Connection | None = None,
) -> list[dict]:
    with _connection(connection) as conn:
        template = _template_row(conn, template_id)
        if template is None:
            raise TemplateDefinitionError("Template not found.")
        fields = _template_fields(conn, template_id)

    if not fields:
        raise TemplateDefinitionError(
            "A Template Definition must contain at least one field."
        )

    metadata = {
        "definition_version": TEMPLATE_DEFINITION_VERSION,
        "template_name": str(template.get("name") or ""),
        "template_description": str(template.get("description") or ""),
        "language": str(template.get("language") or ""),
        "template_type": str(template.get("template_type") or ""),
    }
    return [
        {
            **metadata,
            "field_key": str(field["field_key"]),
            "field_label": str(field["field_label"]),
            "field_type": str(field["field_type"]),
            "required": "1" if bool(field["required"]) else "0",
            "display_order": int(field["display_order"]),
        }
        for field in fields
    ]


def export_template_definition_csv(
    template_id: int,
    connection: Connection | None = None,
) -> bytes:
    return rows_to_csv_bytes(
        export_template_definition_rows(template_id, connection),
        TEMPLATE_DEFINITION_COLUMNS,
    )


def _empty_preview() -> dict:
    return {
        "definition_version": None,
        "template": None,
        "fields": [],
        "errors": [],
        "name_conflict": False,
        "can_import": False,
    }


def _normalized_headers(row: dict) -> dict[str, str]:
    return {str(key or "").strip().casefold(): str(key) for key in row}


def _strict_integer(value, label: str, errors: list[str]) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text or not text.isdigit():
        errors.append(f"{label} must be a non-negative integer.")
        return None
    return int(text)


def preview_template_definition_csv(
    file_bytes: bytes,
    connection: Connection | None = None,
) -> dict:
    preview = _empty_preview()
    try:
        raw_rows = parse_csv_bytes(file_bytes)
    except ImportPreviewError as error:
        preview["errors"].append(str(error))
        return preview

    header_map = _normalized_headers(raw_rows[0])
    actual_headers = set(header_map)
    expected_headers = set(TEMPLATE_DEFINITION_COLUMNS)
    missing = sorted(expected_headers - actual_headers)
    unknown = sorted(actual_headers - expected_headers)
    if missing:
        preview["errors"].append(
            "Missing required columns: " + ", ".join(missing)
        )
    if unknown:
        preview["errors"].append(
            "Unsupported columns for definition version 1: " + ", ".join(unknown)
        )
    if missing or unknown:
        return preview

    rows = [
        {
            column: row.get(header_map[column], "")
            for column in TEMPLATE_DEFINITION_COLUMNS
        }
        for row in raw_rows
    ]

    metadata_columns = [
        "definition_version",
        "template_name",
        "template_description",
        "language",
        "template_type",
    ]
    normalized_metadata = []
    for row in rows:
        normalized_metadata.append(
            {
                column: str(row.get(column) or "").strip()
                for column in metadata_columns
            }
        )

    versions = {row["definition_version"] for row in normalized_metadata}
    if versions != {TEMPLATE_DEFINITION_VERSION}:
        preview["errors"].append(
            "Template Definition version must be exactly 1."
        )
    else:
        preview["definition_version"] = TEMPLATE_DEFINITION_VERSION

    first_metadata = normalized_metadata[0]
    for column in metadata_columns[1:]:
        values = {row[column] for row in normalized_metadata}
        if len(values) != 1:
            preview["errors"].append(
                f"Inconsistent Template metadata: {column}."
            )

    template_name = first_metadata["template_name"]
    template_type = first_metadata["template_type"]
    if not template_name:
        preview["errors"].append("Template name is required.")
    if not template_type:
        preview["errors"].append("Template type is required.")

    preview["template"] = {
        "name": template_name,
        "description": first_metadata["template_description"],
        "language": first_metadata["language"],
        "template_type": template_type,
    }

    field_keys: set[str] = set()
    display_orders: set[int] = set()
    fields = []
    for index, row in enumerate(rows, start=2):
        prefix = f"Row {index}"
        raw_key = str(row.get("field_key") or "")
        try:
            field_key = normalize_template_field_key(raw_key)
        except ValueError as error:
            preview["errors"].append(f"{prefix}: {error}")
            field_key = ""
        if field_key:
            if field_key in field_keys:
                preview["errors"].append(
                    f"{prefix}: duplicate normalized field key: {field_key}."
                )
            field_keys.add(field_key)

        field_label = str(row.get("field_label") or "").strip()
        if not field_label:
            preview["errors"].append(
                f"{prefix}: Template field label is required."
            )

        try:
            field_type = validate_template_field_type(
                str(row.get("field_type") or "")
            )
        except ValueError as error:
            preview["errors"].append(f"{prefix}: {error}")
            field_type = ""

        required_text = str(row.get("required") or "").strip()
        if required_text not in {"0", "1"}:
            preview["errors"].append(
                f"{prefix}: required must be 0 or 1."
            )
            required = None
        else:
            required = int(required_text)

        display_order = _strict_integer(
            row.get("display_order"),
            f"{prefix}: display_order",
            preview["errors"],
        )
        if display_order is not None:
            if display_order in display_orders:
                preview["errors"].append(
                    f"{prefix}: duplicate display_order: {display_order}."
                )
            display_orders.add(display_order)

        fields.append(
            {
                "field_key": field_key,
                "field_label": field_label,
                "field_type": field_type,
                "required": required,
                "display_order": display_order,
            }
        )

    preview["fields"] = sorted(
        fields,
        key=lambda field: (
            field["display_order"] if field["display_order"] is not None else 2**31,
            field["field_key"],
        ),
    )

    if template_name:
        with _connection(connection) as conn:
            conflict = conn.execute(
                "SELECT 1 FROM entry_templates WHERE name = ?",
                (template_name,),
            ).fetchone()
        preview["name_conflict"] = conflict is not None
        if preview["name_conflict"]:
            preview["errors"].append(
                "A Template with this name already exists."
            )

    preview["can_import"] = not preview["errors"]
    return preview


def import_template_definition_csv(
    file_bytes: bytes,
    connection: Connection | None = None,
) -> dict:
    with _connection(connection) as conn:
        preview = preview_template_definition_csv(file_bytes, conn)
        if not preview["can_import"]:
            raise TemplateDefinitionError(
                "Template Definition cannot be imported: "
                + "; ".join(preview["errors"])
            )

        template = preview["template"]
        fields = preview["fields"]
        now = _now_iso()
        savepoint = "template_definition_import"
        conn.execute(f"SAVEPOINT {savepoint}")
        try:
            cursor = conn.execute(
                """
                INSERT INTO entry_templates (
                    name, description, language, template_type, is_system,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    template["name"],
                    template["description"],
                    template["language"] or None,
                    template["template_type"],
                    now,
                    now,
                ),
            )
            template_id = int(cursor.lastrowid)
            for field in fields:
                conn.execute(
                    """
                    INSERT INTO entry_template_fields (
                        template_id, field_key, field_label, field_type,
                        required, display_order, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template_id,
                        field["field_key"],
                        field["field_label"],
                        field["field_type"],
                        field["required"],
                        field["display_order"],
                        now,
                        now,
                    ),
                )
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception as error:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise TemplateDefinitionError(
                "Could not import the Template Definition. No changes were saved."
            ) from error

        created_template = _template_row(conn, template_id)
        created_fields = _template_fields(conn, template_id)
        return {
            "template_id": template_id,
            "template": created_template,
            "fields": created_fields,
            "field_count": len(created_fields),
        }

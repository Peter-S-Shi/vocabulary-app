from datetime import datetime, timezone

from src.db import get_connection
from src.entry_templates import (
    ensure_general_entry_template,
    get_canonical_mapping,
    get_entry_field_values,
    resolve_canonical_fields,
    set_entry_template_values,
    validate_template_values,
)


ENTRY_COLUMNS = """
    entries.id,
    entries.template_id,
    COALESCE(entry_templates.name, '') AS template_name,
    entries.language,
    entries.explanation_language,
    entries.entry_type,
    entries.term,
    entries.meaning,
    entries.example,
    entries.notes,
    entries.tags,
    entries.source,
    entries.status,
    entries.review_count,
    entries.correct_count,
    entries.wrong_count,
    entries.current_interval_days,
    entries.next_due_at,
    entries.created_at,
    entries.updated_at
"""

CANONICAL_ENTRY_FIELDS = [
    "language",
    "explanation_language",
    "entry_type",
    "status",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_entry_data(entry_data: dict) -> dict:
    return {
        "language": str(entry_data.get("language", "") or "").strip(),
        "explanation_language": str(
            entry_data.get("explanation_language", "") or ""
        ).strip(),
        "entry_type": str(entry_data.get("entry_type", "") or "").strip(),
        "status": str(entry_data.get("status", "new") or "new").strip(),
    }


def _validate_base_entry_data(entry_data: dict) -> list[str]:
    errors = []
    for field_name in CANONICAL_ENTRY_FIELDS:
        if not str(entry_data.get(field_name, "") or "").strip():
            errors.append(f"{field_name} is required.")
    return errors


def create_entry_with_template(
    entry_data: dict,
    template_values: dict,
    manual_term: str = "",
    manual_meaning: str = "",
) -> int:
    template_id = int(entry_data.get("template_id") or ensure_general_entry_template())
    clean_entry_data = _clean_entry_data(entry_data)

    errors = _validate_base_entry_data(clean_entry_data)
    errors.extend(validate_template_values(template_id, template_values))

    canonical_values = resolve_canonical_fields(
        template_id=template_id,
        template_values=template_values,
        manual_term=manual_term,
        manual_meaning=manual_meaning,
    )
    if not canonical_values["term"]:
        errors.append("Canonical term is required.")
    if not canonical_values["meaning"]:
        errors.append("Canonical meaning is required.")
    if errors:
        raise ValueError("\n".join(errors))

    now = _now_iso()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO entries (
                template_id,
                language,
                explanation_language,
                entry_type,
                term,
                meaning,
                example,
                notes,
                tags,
                source,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                clean_entry_data["language"],
                clean_entry_data["explanation_language"],
                clean_entry_data["entry_type"],
                canonical_values["term"],
                canonical_values["meaning"],
                canonical_values["example"],
                canonical_values["notes"],
                canonical_values["tags"],
                canonical_values["source"],
                clean_entry_data["status"],
                now,
                now,
            ),
        )
        entry_id = int(cursor.lastrowid)

    set_entry_template_values(entry_id, template_values)
    return entry_id


def add_entry(
    language: str,
    explanation_language: str,
    entry_type: str,
    term: str,
    meaning: str,
    example: str = "",
    notes: str = "",
    tags: str = "",
    source: str = "",
    status: str = "new",
) -> int:
    template_id = ensure_general_entry_template()
    return create_entry_with_template(
        entry_data={
            "template_id": template_id,
            "language": language,
            "explanation_language": explanation_language,
            "entry_type": entry_type,
            "status": status,
        },
        template_values={
            "term": term,
            "meaning": meaning,
            "example": example,
            "notes": notes,
            "tags": tags,
            "source": source,
        },
    )


def list_entries() -> list[dict]:
    return search_entries()


def search_entries(
    search_text: str = "",
    language: str = "All",
    entry_type: str = "All",
    status: str = "All",
    template_id: int | str | None = None,
) -> list[dict]:
    where_clauses = []
    params = []

    if search_text.strip():
        search_pattern = f"%{search_text.strip().lower()}%"
        where_clauses.append(
            """
            (
                LOWER(entries.term) LIKE ?
                OR LOWER(entries.meaning) LIKE ?
                OR LOWER(COALESCE(entries.example, '')) LIKE ?
                OR LOWER(COALESCE(entries.notes, '')) LIKE ?
                OR LOWER(COALESCE(entries.tags, '')) LIKE ?
                OR LOWER(COALESCE(entries.source, '')) LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM entry_field_values
                    WHERE entry_field_values.entry_id = entries.id
                      AND LOWER(COALESCE(entry_field_values.field_value, '')) LIKE ?
                )
            )
            """
        )
        params.extend([
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
        ])

    if language != "All":
        where_clauses.append("entries.language = ?")
        params.append(language)

    if entry_type != "All":
        where_clauses.append("entries.entry_type = ?")
        params.append(entry_type)

    if status != "All":
        where_clauses.append("entries.status = ?")
        params.append(status)

    if template_id not in (None, "", "All"):
        where_clauses.append("entries.template_id = ?")
        params.append(int(template_id))

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT {ENTRY_COLUMNS}
            FROM entries
            LEFT JOIN entry_templates
                ON entry_templates.id = entries.template_id
            {where_sql}
            ORDER BY entries.created_at DESC, entries.id DESC
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def get_entry_by_id(entry_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT {ENTRY_COLUMNS}
            FROM entries
            LEFT JOIN entry_templates
                ON entry_templates.id = entries.template_id
            WHERE entries.id = ?
            """,
            (entry_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_entry_with_template_values(entry_id: int) -> dict | None:
    entry = get_entry_by_id(entry_id)
    if entry is None:
        return None

    entry["template_values"] = get_entry_field_values(entry_id)
    return entry


def get_entry_detail_with_template_values(entry_id: int) -> dict | None:
    return get_entry_with_template_values(entry_id)


def update_entry_with_template(
    entry_id: int,
    entry_data: dict,
    template_values: dict,
    manual_term: str = "",
    manual_meaning: str = "",
) -> None:
    existing_entry = get_entry_by_id(entry_id)
    if existing_entry is None:
        raise ValueError("Entry not found.")

    template_id = int(existing_entry["template_id"] or ensure_general_entry_template())
    clean_entry_data = _clean_entry_data(entry_data)

    errors = _validate_base_entry_data(clean_entry_data)
    errors.extend(validate_template_values(template_id, template_values))

    canonical_values = resolve_canonical_fields(
        template_id=template_id,
        template_values=template_values,
        manual_term=manual_term,
        manual_meaning=manual_meaning,
    )
    if not canonical_values["term"]:
        errors.append("Canonical term is required.")
    if not canonical_values["meaning"]:
        errors.append("Canonical meaning is required.")
    if errors:
        raise ValueError("\n".join(errors))

    now = _now_iso()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE entries
            SET
                template_id = ?,
                language = ?,
                explanation_language = ?,
                entry_type = ?,
                term = ?,
                meaning = ?,
                example = ?,
                notes = ?,
                tags = ?,
                source = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                template_id,
                clean_entry_data["language"],
                clean_entry_data["explanation_language"],
                clean_entry_data["entry_type"],
                canonical_values["term"],
                canonical_values["meaning"],
                canonical_values["example"],
                canonical_values["notes"],
                canonical_values["tags"],
                canonical_values["source"],
                clean_entry_data["status"],
                now,
                entry_id,
            ),
        )

    set_entry_template_values(entry_id, template_values)


def update_entry(
    entry_id: int,
    language: str,
    explanation_language: str,
    entry_type: str,
    term: str,
    meaning: str,
    example: str = "",
    notes: str = "",
    tags: str = "",
    source: str = "",
    status: str = "new",
) -> None:
    existing_entry = get_entry_with_template_values(entry_id)
    if existing_entry is None:
        raise ValueError("Entry not found.")

    if existing_entry.get("template_name") == "General Entry":
        template_values = {
            "term": term,
            "meaning": meaning,
            "example": example,
            "notes": notes,
            "tags": tags,
            "source": source,
        }
        manual_term = ""
        manual_meaning = ""
    else:
        template_values = {
            key: value_data["field_value"]
            for key, value_data in existing_entry["template_values"].items()
        }
        mapping = get_canonical_mapping(int(existing_entry["template_id"]))
        if mapping["term_source"] is not None:
            template_values[mapping["term_source"]] = term
        if mapping["meaning_source"] is not None:
            template_values[mapping["meaning_source"]] = meaning
        for field_key, field_value in {
            "example": example,
            "notes": notes,
            "tags": tags,
            "source": source,
        }.items():
            if field_key in template_values:
                template_values[field_key] = field_value
        manual_term = term if mapping["needs_manual_term"] else ""
        manual_meaning = meaning if mapping["needs_manual_meaning"] else ""

    update_entry_with_template(
        entry_id=entry_id,
        entry_data={
            "language": language,
            "explanation_language": explanation_language,
            "entry_type": entry_type,
            "status": status,
        },
        template_values=template_values,
        manual_term=manual_term,
        manual_meaning=manual_meaning,
    )


def delete_entry(entry_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM entries
            WHERE id = ?
            """,
            (entry_id,),
        )


def delete_entries(entry_ids: list[int]) -> int:
    if not entry_ids:
        return 0

    with get_connection() as connection:
        cursor = connection.executemany(
            """
            DELETE FROM entries
            WHERE id = ?
            """,
            [(entry_id,) for entry_id in entry_ids],
        )

    return cursor.rowcount

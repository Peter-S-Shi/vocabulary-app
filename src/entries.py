from datetime import datetime, timezone
import json

from src.card_history import preview_collection_transition, reconcile_collection_card_history
from src.collections import CrossCardMoveConfirmationRequired
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

    canonical_after = {
        "template_id": template_id,
        "language": clean_entry_data["language"],
        "explanation_language": clean_entry_data["explanation_language"],
        "entry_type": clean_entry_data["entry_type"],
        "term": canonical_values["term"],
        "meaning": canonical_values["meaning"],
        "example": canonical_values["example"],
        "notes": canonical_values["notes"],
        "tags": canonical_values["tags"],
        "source": canonical_values["source"],
        "status": clean_entry_data["status"],
    }
    with get_connection() as connection:
        canonical_before_row = connection.execute(
            """
            SELECT template_id, language, explanation_language, entry_type,
                   term, meaning, example, notes, tags, source, status
            FROM entries
            WHERE id = ?
            """,
            (int(entry_id),),
        ).fetchone()
        if canonical_before_row is None:
            raise ValueError("Entry not found.")
        canonical_before = {
            key: canonical_before_row[key]
            for key in canonical_after
        }
        for optional_key in ("example", "notes", "tags", "source"):
            canonical_before[optional_key] = str(canonical_before[optional_key] or "")
        field_rows = connection.execute(
            """
            SELECT fields.id, fields.field_key, COALESCE(values_table.field_value, '') AS field_value
            FROM entry_template_fields AS fields
            LEFT JOIN entry_field_values AS values_table
              ON values_table.field_id = fields.id
             AND values_table.entry_id = ?
            WHERE fields.template_id = ?
            ORDER BY fields.display_order, fields.id
            """,
            (int(entry_id), template_id),
        ).fetchall()
        template_after = {
            str(row["field_key"]): str(template_values.get(row["field_key"], "") or "")
            for row in field_rows
        }
        changes = {
            key: {"old": canonical_before[key], "new": new_value}
            for key, new_value in canonical_after.items()
            if canonical_before[key] != new_value
        }
        changes.update(
            {
                f"template.{row['field_key']}": {
                    "old": str(row["field_value"] or ""),
                    "new": template_after[str(row["field_key"])],
                }
                for row in field_rows
                if str(row["field_value"] or "")
                != template_after[str(row["field_key"])]
            }
        )
        if not changes:
            return

        now = _now_iso()
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
        connection.executemany(
            """
            INSERT INTO entry_field_values (
                entry_id, field_id, field_value, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entry_id, field_id) DO UPDATE SET
                field_value = excluded.field_value,
                updated_at = excluded.updated_at
            """,
            [
                (
                    int(entry_id),
                    int(row["id"]),
                    template_after[str(row["field_key"])],
                    now,
                    now,
                )
                for row in field_rows
            ],
        )
        connection.execute(
            """
            INSERT INTO entry_change_events (
                entry_id, changed_at, changes_json, change_source
            ) VALUES (?, ?, ?, 'app_edit')
            """,
            (int(entry_id), now, json.dumps(changes, ensure_ascii=False, sort_keys=True)),
        )


def get_entry_change_events(entry_id: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, entry_id, changed_at, changes_json, change_source
            FROM entry_change_events
            WHERE entry_id = ?
            ORDER BY changed_at, id
            """,
            (int(entry_id),),
        ).fetchall()
    events = []
    for row in rows:
        event = dict(row)
        event["changes"] = json.loads(event.pop("changes_json"))
        events.append(event)
    return events


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


def delete_entry(entry_id: int, *, confirm_cross_card: bool = False) -> None:
    delete_entries([entry_id], confirm_cross_card=confirm_cross_card)


def delete_entries(
    entry_ids: list[int],
    *,
    confirm_cross_card: bool = False,
) -> int:
    if not entry_ids:
        return 0

    unique_entry_ids = list(dict.fromkeys(int(entry_id) for entry_id in entry_ids))
    with get_connection() as connection:
        placeholders = ",".join("?" for _ in unique_entry_ids)
        affected_rows = connection.execute(
            f"""
            SELECT DISTINCT collection_id
            FROM entry_collections
            WHERE entry_id IN ({placeholders})
            ORDER BY collection_id
            """,
            unique_entry_ids,
        ).fetchall()
        affected_collection_ids = [int(row["collection_id"]) for row in affected_rows]
        previews = []
        remove_ids = set(unique_entry_ids)
        for collection_id in affected_collection_ids:
            before_ids = [
                int(row["entry_id"])
                for row in connection.execute(
                    "SELECT entry_id FROM entry_collections WHERE collection_id = ? ORDER BY position, id",
                    (collection_id,),
                ).fetchall()
            ]
            preview = preview_collection_transition(
                connection,
                collection_id,
                proposed_entry_ids=[value for value in before_ids if value not in remove_ids],
            )
            if preview["requires_confirmation"]:
                previews.append(preview)
        if previews and not confirm_cross_card:
            raise CrossCardMoveConfirmationRequired({"collections": previews})

        cursor = connection.executemany(
            """
            DELETE FROM entries
            WHERE id = ?
            """,
            [(entry_id,) for entry_id in unique_entry_ids],
        )
        for collection_id in affected_collection_ids:
            remaining_rows = connection.execute(
                "SELECT entry_id FROM entry_collections WHERE collection_id = ? ORDER BY position, id",
                (collection_id,),
            ).fetchall()
            connection.executemany(
                """
                UPDATE entry_collections
                SET position = ?
                WHERE collection_id = ? AND entry_id = ?
                """,
                [
                    (position, collection_id, int(row["entry_id"]))
                    for position, row in enumerate(remaining_rows, start=1)
                ],
            )
            reconcile_collection_card_history(
                connection,
                collection_id,
                change_reason="entries_hard_deleted",
            )

    return cursor.rowcount

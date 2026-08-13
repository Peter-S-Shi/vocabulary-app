from datetime import datetime, timezone
import re

from src.db import get_connection


GENERAL_ENTRY_TEMPLATE_NAME = "General Entry"
GENERAL_ENTRY_TEMPLATE_DESCRIPTION = "Default general vocabulary entry template."
GENERAL_ENTRY_TEMPLATE_TYPE = "general"
GENERAL_ENTRY_TEMPLATE_LANGUAGE = "any"

GENERAL_ENTRY_FIELDS = [
    {
        "field_key": "term",
        "field_label": "Term",
        "field_type": "text",
        "required": 1,
        "speech_language_role": "entry",
        "display_order": 1,
    },
    {
        "field_key": "meaning",
        "field_label": "Meaning",
        "field_type": "long_text",
        "required": 1,
        "speech_language_role": "explanation",
        "display_order": 2,
    },
    {
        "field_key": "example",
        "field_label": "Example",
        "field_type": "long_text",
        "required": 0,
        "speech_language_role": "none",
        "display_order": 3,
    },
    {
        "field_key": "notes",
        "field_label": "Notes",
        "field_type": "long_text",
        "required": 0,
        "speech_language_role": "none",
        "display_order": 4,
    },
    {
        "field_key": "tags",
        "field_label": "Tags",
        "field_type": "text",
        "required": 0,
        "speech_language_role": "none",
        "display_order": 5,
    },
    {
        "field_key": "source",
        "field_label": "Source",
        "field_type": "text",
        "required": 0,
        "speech_language_role": "none",
        "display_order": 6,
    },
]

GENERAL_ENTRY_VALUE_COLUMNS = {
    "term": "term",
    "meaning": "meaning",
    "example": "example",
    "notes": "notes",
    "tags": "tags",
    "source": "source",
}


FRENCH_VERB_PRESENT_TEMPLATE_NAME = "French Verb Present"
FRENCH_ADJECTIVE_AGREEMENT_TEMPLATE_NAME = "French Adjective Agreement"
FRENCH_NOUN_GENDER_PLURAL_TEMPLATE_NAME = "French Noun Gender Plural"

def _speech_field(
    field_key: str,
    field_label: str,
    field_type: str,
    required: int,
    display_order: int,
    role: str,
) -> dict:
    return {
        "field_key": field_key,
        "field_label": field_label,
        "field_type": field_type,
        "required": required,
        "display_order": display_order,
        "speech_language_role": role,
    }


FRENCH_VERB_PRESENT_FIELDS = [
    _speech_field("infinitive", "Infinitive", "text", 1, 1, "entry"),
    _speech_field("meaning", "Meaning", "long_text", 1, 2, "explanation"),
    _speech_field("je", "je", "text", 1, 3, "entry"),
    _speech_field("tu", "tu", "text", 1, 4, "entry"),
    _speech_field("il_elle_on", "il/elle/on", "text", 1, 5, "entry"),
    _speech_field("nous", "nous", "text", 1, 6, "entry"),
    _speech_field("vous", "vous", "text", 1, 7, "entry"),
    _speech_field("ils_elles", "ils/elles", "text", 1, 8, "entry"),
    _speech_field("example", "Example", "long_text", 0, 9, "none"),
    _speech_field("notes", "Notes", "long_text", 0, 10, "none"),
    _speech_field("tags", "Tags", "text", 0, 11, "none"),
    _speech_field("source", "Source", "text", 0, 12, "none"),
]

FRENCH_ADJECTIVE_AGREEMENT_FIELDS = [
    _speech_field("masculine_singular", "Masculine Singular", "text", 1, 1, "entry"),
    _speech_field("meaning", "Meaning", "long_text", 1, 2, "explanation"),
    _speech_field("feminine_singular", "Feminine Singular", "text", 1, 3, "entry"),
    _speech_field("masculine_plural", "Masculine Plural", "text", 1, 4, "entry"),
    _speech_field("feminine_plural", "Feminine Plural", "text", 1, 5, "entry"),
    _speech_field("example", "Example", "long_text", 0, 6, "none"),
    _speech_field("notes", "Notes", "long_text", 0, 7, "none"),
    _speech_field("tags", "Tags", "text", 0, 8, "none"),
    _speech_field("source", "Source", "text", 0, 9, "none"),
]

FRENCH_NOUN_GENDER_PLURAL_FIELDS = [
    _speech_field("singular", "Singular", "text", 1, 1, "entry"),
    _speech_field("meaning", "Meaning", "long_text", 1, 2, "explanation"),
    _speech_field("gender", "Gender", "text", 1, 3, "entry"),
    _speech_field("plural", "Plural", "text", 1, 4, "entry"),
    _speech_field("article", "Article", "text", 1, 5, "entry"),
    _speech_field("example", "Example", "long_text", 0, 6, "none"),
    _speech_field("notes", "Notes", "long_text", 0, 7, "none"),
    _speech_field("tags", "Tags", "text", 0, 8, "none"),
    _speech_field("source", "Source", "text", 0, 9, "none"),
]

ALLOWED_FIELD_TYPES = {"text", "long_text"}
ALLOWED_SPEECH_LANGUAGE_ROLES = {"entry", "explanation", "none", "unresolved"}
FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_required(required: bool | int) -> int:
    return 1 if bool(required) else 0


def normalize_speech_language_role(role: str | None, required: bool | int) -> str:
    if role is None or not str(role).strip():
        return "unresolved" if bool(required) else "none"
    clean_role = str(role).strip().lower()
    if clean_role not in ALLOWED_SPEECH_LANGUAGE_ROLES:
        raise ValueError(f"Unsupported speech language role: {clean_role}")
    if not bool(required):
        return "none"
    if clean_role == "none":
        return "unresolved"
    return clean_role



def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    clean_value = value.strip()
    if not clean_value:
        return None

    return clean_value


def normalize_template_field_key(field_key: str) -> str:
    clean_key = field_key.strip().lower().replace("-", " ")
    clean_key = "_".join(clean_key.split())
    clean_key = re.sub(r"_+", "_", clean_key)

    if not clean_key:
        raise ValueError("Template field key is required.")
    if not FIELD_KEY_PATTERN.fullmatch(clean_key):
        raise ValueError(
            "Template field key must use snake_case and start with a letter."
        )

    return clean_key


def validate_template_field_type(field_type: str) -> str:
    clean_type = field_type.strip() or "text"
    if clean_type not in ALLOWED_FIELD_TYPES:
        raise ValueError(f"Unsupported field type: {clean_type}")

    return clean_type


def _normalize_field_key(field_key: str) -> str:
    return normalize_template_field_key(field_key)


def _validate_field_type(field_type: str) -> str:
    return validate_template_field_type(field_type)


def _is_system_template(template: dict | None) -> bool:
    return bool(template and template.get("is_system"))


def create_entry_template(
    name: str,
    description: str = "",
    language: str | None = None,
    template_type: str = "custom",
    is_system: bool = False,
) -> int:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Template name is required.")
    if get_entry_template_by_name(clean_name) is not None:
        raise ValueError("Template name must be unique.")

    now = _now_iso()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO entry_templates (
                name,
                description,
                language,
                template_type,
                is_system,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_name,
                description.strip(),
                _clean_optional_text(language),
                template_type.strip() or "custom",
                1 if is_system else 0,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def get_entry_templates() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                template.id,
                template.name,
                template.description,
                template.language,
                template.template_type,
                template.is_system,
                template.created_at,
                template.updated_at,
                COUNT(field.id) AS field_count
            FROM entry_templates AS template
            LEFT JOIN entry_template_fields AS field
                ON field.template_id = template.id
            GROUP BY template.id
            ORDER BY template.is_system DESC, template.name ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_entry_template(template_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                name,
                description,
                language,
                template_type,
                is_system,
                created_at,
                updated_at
            FROM entry_templates
            WHERE id = ?
            """,
            (template_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_entry_template_by_name(name: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                name,
                description,
                language,
                template_type,
                is_system,
                created_at,
                updated_at
            FROM entry_templates
            WHERE name = ?
            """,
            (name.strip(),),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def create_template_field(
    template_id: int,
    field_key: str,
    field_label: str,
    field_type: str = "text",
    required: bool | int = False,
    display_order: int = 0,
    speech_language_role: str | None = None,
    allow_system: bool = False,
) -> int:
    clean_key = _normalize_field_key(field_key)
    clean_label = field_label.strip()
    clean_type = _validate_field_type(field_type)
    clean_role = normalize_speech_language_role(speech_language_role, required)

    if not clean_label:
        raise ValueError("Template field label is required.")

    template = get_entry_template(template_id)
    if template is None:
        raise ValueError("Template not found.")
    if _is_system_template(template) and not allow_system:
        raise ValueError("System template fields are read-only.")

    existing_fields = {field["field_key"] for field in get_template_fields(template_id)}
    if clean_key in existing_fields:
        raise ValueError("Template field key must be unique within this template.")

    now = _now_iso()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO entry_template_fields (
                template_id,
                field_key,
                field_label,
                field_type,
                required,
                speech_language_role,
                display_order,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                clean_key,
                clean_label,
                clean_type,
                _normalize_required(required),
                clean_role,
                int(display_order),
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def get_template_fields(template_id: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                template_id,
                field_key,
                field_label,
                field_type,
                required,
                speech_language_role,
                display_order,
                created_at,
                updated_at
            FROM entry_template_fields
            WHERE template_id = ?
            ORDER BY display_order ASC, id ASC
            """,
            (template_id,),
        ).fetchall()

    return [dict(row) for row in rows]



def _ensure_system_template(
    name: str,
    description: str,
    language: str,
    template_type: str,
) -> int:
    existing_template = get_entry_template_by_name(name)
    now = _now_iso()

    if existing_template is None:
        return create_entry_template(
            name=name,
            description=description,
            language=language,
            template_type=template_type,
            is_system=True,
        )

    template_id = int(existing_template["id"])
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE entry_templates
            SET
                description = ?,
                language = ?,
                template_type = ?,
                is_system = 1,
                updated_at = ?
            WHERE id = ?
            """,
            (description, language, template_type, now, template_id),
        )

    return template_id


def ensure_template_fields(template_id: int, fields: list[dict]) -> None:
    existing_fields = {
        field["field_key"]: field for field in get_template_fields(template_id)
    }
    for field in fields:
        if field["field_key"] not in existing_fields:
            create_template_field(template_id=template_id, allow_system=True, **field)
            continue
        existing = existing_fields[field["field_key"]]
        required = _normalize_required(field.get("required", existing["required"]))
        role = normalize_speech_language_role(
            field.get("speech_language_role", existing.get("speech_language_role")),
            required,
        )
        if int(existing["required"]) != required or existing.get("speech_language_role") != role:
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE entry_template_fields
                    SET required = ?, speech_language_role = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (required, role, _now_iso(), int(existing["id"])),
                )


def ensure_french_verb_present_template() -> int:
    template_id = _ensure_system_template(
        name=FRENCH_VERB_PRESENT_TEMPLATE_NAME,
        description="French present tense verb conjugation template.",
        language="French",
        template_type="french_verb_present",
    )
    ensure_template_fields(template_id, FRENCH_VERB_PRESENT_FIELDS)
    return template_id


def ensure_french_adjective_agreement_template() -> int:
    template_id = _ensure_system_template(
        name=FRENCH_ADJECTIVE_AGREEMENT_TEMPLATE_NAME,
        description="French adjective gender and number agreement template.",
        language="French",
        template_type="french_adjective_agreement",
    )
    ensure_template_fields(template_id, FRENCH_ADJECTIVE_AGREEMENT_FIELDS)
    return template_id


def ensure_french_noun_gender_plural_template() -> int:
    template_id = _ensure_system_template(
        name=FRENCH_NOUN_GENDER_PLURAL_TEMPLATE_NAME,
        description="French noun gender and plural template.",
        language="French",
        template_type="french_noun_gender_plural",
    )
    ensure_template_fields(template_id, FRENCH_NOUN_GENDER_PLURAL_FIELDS)
    return template_id


def ensure_french_template_presets() -> dict:
    return {
        "french_verb_present_template_id": ensure_french_verb_present_template(),
        "french_adjective_agreement_template_id": ensure_french_adjective_agreement_template(),
        "french_noun_gender_plural_template_id": ensure_french_noun_gender_plural_template(),
    }


def ensure_general_entry_template() -> int:
    existing_template = get_entry_template_by_name(GENERAL_ENTRY_TEMPLATE_NAME)
    now = _now_iso()

    if existing_template is None:
        template_id = create_entry_template(
            name=GENERAL_ENTRY_TEMPLATE_NAME,
            description=GENERAL_ENTRY_TEMPLATE_DESCRIPTION,
            language=GENERAL_ENTRY_TEMPLATE_LANGUAGE,
            template_type=GENERAL_ENTRY_TEMPLATE_TYPE,
            is_system=True,
        )
    else:
        template_id = int(existing_template["id"])
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE entry_templates
                SET
                    description = ?,
                    language = ?,
                    template_type = ?,
                    is_system = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    GENERAL_ENTRY_TEMPLATE_DESCRIPTION,
                    GENERAL_ENTRY_TEMPLATE_LANGUAGE,
                    GENERAL_ENTRY_TEMPLATE_TYPE,
                    now,
                    template_id,
                ),
            )

    ensure_template_fields(template_id, GENERAL_ENTRY_FIELDS)

    return template_id


def assign_general_template_to_existing_entries() -> int:
    template_id = ensure_general_entry_template()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE entries
            SET template_id = ?
            WHERE template_id IS NULL
            """,
            (template_id,),
        )
        return cursor.rowcount


def set_entry_field_value(entry_id: int, field_id: int, field_value: str | None) -> None:
    now = _now_iso()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO entry_field_values (
                entry_id,
                field_id,
                field_value,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entry_id, field_id) DO UPDATE SET
                field_value = excluded.field_value,
                updated_at = excluded.updated_at
            """,
            (entry_id, field_id, field_value or "", now, now),
        )


def get_entry_field_values(entry_id: int) -> dict:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                field.id AS field_id,
                field.field_key,
                field.field_label,
                field.field_type,
                field.required,
                field.speech_language_role,
                field.display_order,
                COALESCE(value.field_value, '') AS field_value
            FROM entries AS entry
            JOIN entry_template_fields AS field
                ON field.template_id = entry.template_id
            LEFT JOIN entry_field_values AS value
                ON value.entry_id = entry.id
               AND value.field_id = field.id
            WHERE entry.id = ?
            ORDER BY field.display_order ASC, field.id ASC
            """,
            (entry_id,),
        ).fetchall()

    return {row["field_key"]: dict(row) for row in rows}


def sync_general_entry_field_values(entry_id: int) -> bool:
    template_id = ensure_general_entry_template()
    now = _now_iso()

    with get_connection() as connection:
        entry = connection.execute(
            """
            SELECT id, template_id, term, meaning, example, notes, tags, source
            FROM entries
            WHERE id = ?
            """,
            (entry_id,),
        ).fetchone()

        if entry is None:
            return False

        if entry["template_id"] is None:
            connection.execute(
                """
                UPDATE entries
                SET template_id = ?
                WHERE id = ?
                """,
                (template_id, entry_id),
            )
            entry_template_id = template_id
        else:
            entry_template_id = int(entry["template_id"])

        if entry_template_id != template_id:
            return False

        fields = connection.execute(
            """
            SELECT id, field_key
            FROM entry_template_fields
            WHERE template_id = ?
            """,
            (template_id,),
        ).fetchall()

        for field in fields:
            field_key = field["field_key"]
            source_column = GENERAL_ENTRY_VALUE_COLUMNS.get(field_key)
            if source_column is None:
                continue

            connection.execute(
                """
                INSERT INTO entry_field_values (
                    entry_id,
                    field_id,
                    field_value,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entry_id, field_id) DO UPDATE SET
                    field_value = excluded.field_value,
                    updated_at = excluded.updated_at
                """,
                (
                    entry_id,
                    int(field["id"]),
                    entry[source_column] or "",
                    now,
                    now,
                ),
            )

    return True


def sync_general_entry_field_values_for_existing_entries() -> int:
    template_id = ensure_general_entry_template()
    now = _now_iso()
    with get_connection() as connection:
        fields = connection.execute(
            """
            SELECT id, field_key
            FROM entry_template_fields
            WHERE template_id = ?
            """,
            (template_id,),
        ).fetchall()

        synced_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM entries WHERE template_id = ?",
                (template_id,),
            ).fetchone()[0]
        )

        for field in fields:
            field_key = field["field_key"]
            source_column = GENERAL_ENTRY_VALUE_COLUMNS.get(field_key)
            if source_column is None:
                continue

            connection.execute(
                f"""
                INSERT INTO entry_field_values (
                    entry_id,
                    field_id,
                    field_value,
                    created_at,
                    updated_at
                )
                SELECT
                    entries.id,
                    ?,
                    COALESCE(entries.{source_column}, ''),
                    ?,
                    ?
                FROM entries
                WHERE entries.template_id = ?
                ON CONFLICT(entry_id, field_id) DO UPDATE SET
                    field_value = excluded.field_value,
                    updated_at = excluded.updated_at
                WHERE COALESCE(entry_field_values.field_value, '') != excluded.field_value
                """,
                (int(field["id"]), now, now, template_id),
            )

    return synced_count


def init_entry_template_system() -> dict:
    template_id = ensure_general_entry_template()
    french_preset_result = ensure_french_template_presets()
    assigned_count = assign_general_template_to_existing_entries()
    synced_entry_count = sync_general_entry_field_values_for_existing_entries()

    return {
        "general_template_id": template_id,
        **french_preset_result,
        "assigned_count": assigned_count,
        "synced_entry_count": synced_entry_count,
    }


def update_entry_template(
    template_id: int,
    name: str,
    description: str = "",
    language: str | None = None,
    template_type: str | None = None,
) -> None:
    template = get_entry_template(template_id)
    if template is None:
        raise ValueError("Template not found.")
    if _is_system_template(template):
        raise ValueError("System templates are read-only.")

    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Template name is required.")

    existing_template = get_entry_template_by_name(clean_name)
    if existing_template is not None and int(existing_template["id"]) != template_id:
        raise ValueError("Template name must be unique.")

    clean_type = (template_type or "custom").strip() or "custom"
    now = _now_iso()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE entry_templates
            SET
                name = ?,
                description = ?,
                language = ?,
                template_type = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                clean_name,
                description.strip(),
                _clean_optional_text(language),
                clean_type,
                now,
                template_id,
            ),
        )


def template_has_entries(template_id: int) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS entry_count
            FROM entries
            WHERE template_id = ?
            """,
            (template_id,),
        ).fetchone()

    return bool(row and row["entry_count"] > 0)


def delete_entry_template(template_id: int) -> bool:
    template = get_entry_template(template_id)
    if template is None or _is_system_template(template) or template_has_entries(template_id):
        return False

    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM entry_templates
            WHERE id = ?
            """,
            (template_id,),
        )

    return cursor.rowcount > 0


def get_template_field(field_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                template_id,
                field_key,
                field_label,
                field_type,
                required,
                speech_language_role,
                display_order,
                created_at,
                updated_at
            FROM entry_template_fields
            WHERE id = ?
            """,
            (field_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_template_field_count(template_id: int) -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS field_count
            FROM entry_template_fields
            WHERE template_id = ?
            """,
            (template_id,),
        ).fetchone()

    return int(row["field_count"] if row else 0)


def template_field_has_values(field_id: int) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS value_count
            FROM entry_field_values
            WHERE field_id = ?
            """,
            (field_id,),
        ).fetchone()

    return bool(row and row["value_count"] > 0)


def update_template_field(
    field_id: int,
    field_label: str,
    field_type: str,
    required: bool | int,
    display_order: int,
    speech_language_role: str | None = None,
) -> None:
    field = get_template_field(field_id)
    if field is None:
        raise ValueError("Template field not found.")

    template = get_entry_template(int(field["template_id"]))
    if _is_system_template(template):
        raise ValueError("System template fields are read-only.")

    clean_label = field_label.strip()
    if not clean_label:
        raise ValueError("Template field label is required.")

    clean_type = _validate_field_type(field_type)
    if speech_language_role is not None:
        role_value = speech_language_role
    elif not bool(required):
        role_value = "none"
    elif not bool(field["required"]):
        # The existing Template UI only submits the Required checkbox. Turning
        # an optional field on must therefore create a safe unresolved role.
        role_value = None
    else:
        role_value = field.get("speech_language_role")
    clean_role = normalize_speech_language_role(role_value, required)
    now = _now_iso()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE entry_template_fields
            SET
                field_label = ?,
                field_type = ?,
                required = ?,
                speech_language_role = ?,
                display_order = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                clean_label,
                clean_type,
                _normalize_required(required),
                clean_role,
                int(display_order),
                now,
                field_id,
            ),
        )


def set_template_field_speech_language_role(
    field_id: int,
    speech_language_role: str,
) -> None:
    field = get_template_field(field_id)
    if field is None:
        raise ValueError("Template field not found.")
    template = get_entry_template(int(field["template_id"]))
    if _is_system_template(template):
        raise ValueError("System template fields are read-only.")
    role = normalize_speech_language_role(
        speech_language_role,
        bool(field["required"]),
    )
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE entry_template_fields
            SET speech_language_role = ?, updated_at = ?
            WHERE id = ?
            """,
            (role, _now_iso(), int(field_id)),
        )


def inspect_template_speech_readiness(template_id: int) -> dict:
    template = get_entry_template(template_id)
    if template is None:
        raise ValueError("Template not found.")
    fields = get_template_fields(template_id)
    issues = []
    for field in fields:
        role = str(field.get("speech_language_role") or "unresolved")
        if field["required"] and role not in {"entry", "explanation"}:
            issues.append(
                {
                    "code": "required_field_role_unresolved",
                    "field_id": int(field["id"]),
                    "field_key": str(field["field_key"]),
                    "speech_language_role": role,
                }
            )
    return {
        "template_id": int(template_id),
        "template_name": str(template["name"]),
        "audio_ready": not issues,
        "issues": issues,
    }


def delete_template_field(field_id: int) -> bool:
    field = get_template_field(field_id)
    if field is None:
        return False

    template = get_entry_template(int(field["template_id"]))
    if _is_system_template(template) or template_field_has_values(field_id):
        return False

    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM entry_template_fields
            WHERE id = ?
            """,
            (field_id,),
        )

    return cursor.rowcount > 0


def get_canonical_mapping(template_id: int) -> dict:
    fields = get_template_fields(template_id)
    field_keys = {field["field_key"] for field in fields}

    term_source = None
    if "term" in field_keys:
        term_source = "term"
    elif "infinitive" in field_keys:
        term_source = "infinitive"
    elif "masculine_singular" in field_keys:
        term_source = "masculine_singular"
    elif "singular" in field_keys:
        term_source = "singular"
    else:
        for field in fields:
            if field["required"] and field["field_type"] == "text":
                term_source = field["field_key"]
                break

    meaning_source = None
    if "meaning" in field_keys:
        meaning_source = "meaning"
    elif "definition" in field_keys:
        meaning_source = "definition"

    return {
        "term_source": term_source,
        "meaning_source": meaning_source,
        "needs_manual_term": term_source is None,
        "needs_manual_meaning": meaning_source is None,
    }


def validate_template_values(template_id: int, template_values: dict) -> list[str]:
    errors = []
    for field in get_template_fields(template_id):
        if not field["required"]:
            continue

        value = str(template_values.get(field["field_key"], "") or "").strip()
        if not value:
            errors.append(f"{field['field_label']} is required.")

    return errors


def resolve_canonical_fields(
    template_id: int,
    template_values: dict,
    manual_term: str = "",
    manual_meaning: str = "",
) -> dict:
    mapping = get_canonical_mapping(template_id)

    if mapping["term_source"] is None:
        term = manual_term.strip()
        term_source = "manual"
    else:
        term_source = mapping["term_source"]
        term = str(template_values.get(term_source, "") or "").strip()

    if mapping["meaning_source"] is None:
        meaning = manual_meaning.strip()
        meaning_source = "manual"
    else:
        meaning_source = mapping["meaning_source"]
        meaning = str(template_values.get(meaning_source, "") or "").strip()

    def mapped_value(field_key: str) -> str:
        return str(template_values.get(field_key, "") or "").strip()

    return {
        "term": term,
        "meaning": meaning,
        "example": mapped_value("example"),
        "notes": mapped_value("notes"),
        "tags": mapped_value("tags"),
        "source": mapped_value("source"),
        "term_source": term_source,
        "meaning_source": meaning_source,
        "needs_manual_term": mapping["needs_manual_term"],
        "needs_manual_meaning": mapping["needs_manual_meaning"],
    }


def set_entry_template_values(entry_id: int, template_values: dict) -> None:
    with get_connection() as connection:
        entry = connection.execute(
            """
            SELECT template_id
            FROM entries
            WHERE id = ?
            """,
            (entry_id,),
        ).fetchone()

    if entry is None:
        raise ValueError("Entry not found.")

    fields = get_template_fields(int(entry["template_id"]))
    fields_by_key = {field["field_key"]: field for field in fields}

    for field_key, value in template_values.items():
        if field_key not in fields_by_key:
            continue
        set_entry_field_value(
            entry_id=entry_id,
            field_id=int(fields_by_key[field_key]["id"]),
            field_value=str(value or ""),
        )

    for field in fields:
        if field["field_key"] not in template_values:
            set_entry_field_value(entry_id=entry_id, field_id=int(field["id"]), field_value="")

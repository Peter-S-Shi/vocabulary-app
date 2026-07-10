ALLOWED_FIELDS = {
    "language",
    "explanation_language",
    "entry_type",
    "term",
    "meaning",
    "example",
    "notes",
    "tags",
    "source",
    "status",
    "collections",
}

REQUIRED_FIELDS = {
    "language",
    "explanation_language",
    "term",
    "meaning",
}

VALID_LANGUAGES = {"English", "French"}
VALID_EXPLANATION_LANGUAGES = {"Chinese", "English"}
VALID_ENTRY_TYPES = {"word", "phrase", "chunk", "sentence_frame", "conjugation"}
VALID_STATUSES = {"new", "learning", "familiar", "mastered"}


def parse_entry_card(text: str) -> dict:
    data = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        if not line:
            continue

        if ":" not in line:
            raise ValueError(f"Line {line_number} must use field_name: value format.")

        field_name, value = line.split(":", 1)
        field_name = field_name.strip()
        value = value.strip()

        if field_name not in ALLOWED_FIELDS:
            raise ValueError(f"Unknown field: {field_name}")

        data[field_name] = value

    return data


def normalize_entry_data(data: dict) -> dict:
    normalized = {
        "entry_type": "word",
        "example": "",
        "notes": "",
        "tags": "",
        "source": "",
        "status": "new",
        "collections": [],
    }
    normalized.update({key: value.strip() for key, value in data.items()})

    if isinstance(normalized["collections"], str):
        normalized["collections"] = [
            collection_name.strip()
            for collection_name in normalized["collections"].split(";")
            if collection_name.strip()
        ]

    return normalized


def validate_entry_data(data: dict) -> tuple[bool, list[str]]:
    errors = []

    for field_name in sorted(data):
        if field_name not in ALLOWED_FIELDS:
            errors.append(f"Unknown field: {field_name}")

    for field_name in sorted(REQUIRED_FIELDS):
        if not data.get(field_name, "").strip():
            errors.append(f"Missing required field: {field_name}")

    language = data.get("language", "")
    if language and language not in VALID_LANGUAGES:
        errors.append("language must be English or French")

    explanation_language = data.get("explanation_language", "")
    if (
        explanation_language
        and explanation_language not in VALID_EXPLANATION_LANGUAGES
    ):
        errors.append("explanation_language must be Chinese or English")

    entry_type = data.get("entry_type", "")
    if entry_type and entry_type not in VALID_ENTRY_TYPES:
        errors.append(
            "entry_type must be one of: word, phrase, chunk, sentence_frame, conjugation"
        )

    status = data.get("status", "")
    if status and status not in VALID_STATUSES:
        errors.append("status must be one of: new, learning, familiar, mastered")

    return len(errors) == 0, errors


def parse_and_validate_entry_card(text: str) -> tuple[dict | None, list[str]]:
    try:
        parsed = parse_entry_card(text)
    except ValueError as error:
        return None, [str(error)]

    normalized = normalize_entry_data(parsed)
    is_valid, errors = validate_entry_data(normalized)

    if not is_valid:
        return None, errors

    return normalized, []
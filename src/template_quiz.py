from src.collections import get_card_entries_for_study, get_card_groups_for_collection, get_entries_in_collection
from src.db import get_connection
from src.entry_templates import get_entry_field_values
from src.quiz import shuffle_mcq_options, shuffle_quiz_items, shuffle_sequence


TEMPLATE_FIELD_SELF_GRADED = "template_field_self_graded"
TEMPLATE_FIELD_MCQ = "template_field_mcq"
TEMPLATE_FIELD_MATCHING = "template_field_matching"

TEMPLATE_QUIZ_TYPES = {
    "Multiple Choice": TEMPLATE_FIELD_MCQ,
    "Matching": TEMPLATE_FIELD_MATCHING,
    "Self-Graded Filling Blanks": TEMPLATE_FIELD_SELF_GRADED,
}

TEMPLATE_QUIZ_DIFFICULTIES = ["Simple", "Normal", "Hard"]

TEMPLATE_QUIZ_RULES = {
    "french_verb_present": [
        {"id": "infinitive_to_je", "source_field_key": "infinitive", "target_field_key": "je", "label": "Infinitive -> je"},
        {"id": "infinitive_to_tu", "source_field_key": "infinitive", "target_field_key": "tu", "label": "Infinitive -> tu"},
        {"id": "infinitive_to_il_elle_on", "source_field_key": "infinitive", "target_field_key": "il_elle_on", "label": "Infinitive -> il/elle/on"},
        {"id": "infinitive_to_nous", "source_field_key": "infinitive", "target_field_key": "nous", "label": "Infinitive -> nous"},
        {"id": "infinitive_to_vous", "source_field_key": "infinitive", "target_field_key": "vous", "label": "Infinitive -> vous"},
        {"id": "infinitive_to_ils_elles", "source_field_key": "infinitive", "target_field_key": "ils_elles", "label": "Infinitive -> ils/elles"},
        {"id": "meaning_to_infinitive", "source_field_key": "meaning", "target_field_key": "infinitive", "label": "Meaning -> Infinitive"},
        {"id": "infinitive_to_meaning", "source_field_key": "infinitive", "target_field_key": "meaning", "label": "Infinitive -> Meaning"},
    ],
    "french_adjective_agreement": [
        {"id": "masculine_singular_to_feminine_singular", "source_field_key": "masculine_singular", "target_field_key": "feminine_singular", "label": "Masculine Singular -> Feminine Singular"},
        {"id": "masculine_singular_to_masculine_plural", "source_field_key": "masculine_singular", "target_field_key": "masculine_plural", "label": "Masculine Singular -> Masculine Plural"},
        {"id": "masculine_singular_to_feminine_plural", "source_field_key": "masculine_singular", "target_field_key": "feminine_plural", "label": "Masculine Singular -> Feminine Plural"},
        {"id": "meaning_to_masculine_singular", "source_field_key": "meaning", "target_field_key": "masculine_singular", "label": "Meaning -> Masculine Singular"},
        {"id": "masculine_singular_to_meaning", "source_field_key": "meaning", "target_field_key": "meaning", "label": "Masculine Singular -> Meaning"},
    ],
    "french_noun_gender_plural": [
        {"id": "singular_to_plural", "source_field_key": "singular", "target_field_key": "plural", "label": "Singular -> Plural"},
        {"id": "singular_to_gender", "source_field_key": "singular", "target_field_key": "gender", "label": "Singular -> Gender"},
        {"id": "singular_to_article", "source_field_key": "singular", "target_field_key": "article", "label": "Singular -> Article"},
        {"id": "meaning_to_singular", "source_field_key": "meaning", "target_field_key": "singular", "label": "Meaning -> Singular"},
        {"id": "singular_to_meaning", "source_field_key": "singular", "target_field_key": "meaning", "label": "Singular -> Meaning"},
    ],
}

def get_template_quiz_rules(template_type: str | None) -> list[dict]:
    return [dict(rule, template_type=template_type) for rule in TEMPLATE_QUIZ_RULES.get(template_type or "", [])]


def get_template_quiz_rule(template_type: str | None, rule_id: str) -> dict | None:
    for rule in get_template_quiz_rules(template_type):
        if rule["id"] == rule_id:
            return rule
    return None


def get_available_template_quiz_sources(collection_id: int) -> list[dict]:
    entries = get_entries_in_collection(collection_id)
    sources_by_template_id: dict[int, dict] = {}

    for entry in entries:
        template_id = entry.get("template_id")
        template_type = entry.get("template_type") or ""
        if template_id is None or template_type not in TEMPLATE_QUIZ_RULES:
            continue

        source = sources_by_template_id.setdefault(
            int(template_id),
            {
                "template_id": int(template_id),
                "template_name": entry.get("template_name") or f"Template {template_id}",
                "template_type": template_type,
                "entry_count": 0,
            },
        )
        source["entry_count"] += 1

    return sorted(sources_by_template_id.values(), key=lambda source: source["template_name"].lower())


def get_entries_for_template_quiz_card(
    collection_id: int,
    card_number: int,
    template_id: int,
    *,
    include_proficient: bool = True,
) -> list[dict]:
    entries = get_card_entries_for_study(
        collection_id,
        card_number,
        include_proficient=include_proficient,
    )
    return [
        entry
        for entry in entries
        if int(entry.get("template_id") or 0) == int(template_id)
    ]


def get_available_template_quiz_sources_for_card(
    collection_id: int,
    card_number: int,
    *,
    include_proficient: bool = True,
) -> list[dict]:
    sources_by_template_id: dict[int, dict] = {}
    entries = get_card_entries_for_study(
        collection_id,
        card_number,
        include_proficient=include_proficient,
    )
    for entry in entries:
        template_id = entry.get("template_id")
        template_type = entry.get("template_type") or ""
        if template_id is None or template_type not in TEMPLATE_QUIZ_RULES:
            continue

        source = sources_by_template_id.setdefault(
            int(template_id),
            {
                "template_id": int(template_id),
                "template_name": entry.get("template_name") or f"Template {template_id}",
                "template_type": template_type,
                "entry_count": 0,
            },
        )
        source["entry_count"] += 1

    return sorted(sources_by_template_id.values(), key=lambda source: source["template_name"].lower())


def get_dataset_entries_for_template(template_id: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                e.id,
                e.template_id,
                COALESCE(t.name, '') AS template_name,
                COALESCE(t.template_type, '') AS template_type,
                e.language,
                e.explanation_language,
                e.entry_type,
                e.term,
                e.meaning,
                e.example,
                e.notes,
                e.tags,
                e.source,
                e.status,
                e.created_at,
                e.updated_at
            FROM entries e
            LEFT JOIN entry_templates t ON t.id = e.template_id
            WHERE e.template_id = ?
            ORDER BY e.created_at DESC, e.id DESC
            """,
            (int(template_id),),
        ).fetchall()

    return [dict(row) for row in rows]


def _clean_field_value(field_values: dict, field_key: str) -> str:
    field_value = field_values.get(field_key, {}).get("field_value", "")
    return str(field_value or "").strip()


def _field_label(field_values: dict, field_key: str) -> str:
    return field_values.get(field_key, {}).get("field_label") or field_key


def _field_values_for_entries(entries: list[dict]) -> dict[int, dict]:
    return {int(entry["id"]): get_entry_field_values(int(entry["id"])) for entry in entries}


def _template_item_prompt(entry: dict, field_values: dict, rule: dict) -> str:
    source_value = _clean_field_value(field_values, rule["source_field_key"])
    source_label = _field_label(field_values, rule["source_field_key"])
    target_label = _field_label(field_values, rule["target_field_key"])
    return f"{entry.get('term', '')} | {source_label}: {source_value} | Fill {target_label}"


def _build_template_base_item(entry: dict, field_values: dict, template_id: int, rule: dict) -> dict | None:
    source_field_key = rule["source_field_key"]
    target_field_key = rule["target_field_key"]
    prompt = _clean_field_value(field_values, source_field_key)
    expected_answer = _clean_field_value(field_values, target_field_key)
    if not prompt or not expected_answer:
        return None

    return {
        "entry_id": entry["id"],
        "term": entry.get("term", ""),
        "meaning": entry.get("meaning", ""),
        "example": entry.get("example", ""),
        "prompt": _template_item_prompt(entry, field_values, rule),
        "expected_answer": expected_answer,
        "template_id": template_id,
        "template_name": entry.get("template_name", ""),
        "template_type": entry.get("template_type", ""),
        "rule_id": rule["id"],
        "rule_label": rule["label"],
        "source_field_key": source_field_key,
        "source_field_label": _field_label(field_values, source_field_key),
        "source_value": prompt,
        "target_field_key": target_field_key,
        "target_field_label": _field_label(field_values, target_field_key),
        "target_value": expected_answer,
    }


def _unique_nonempty_values(values: list[str], correct_answer: str) -> list[str]:
    normalized_correct = correct_answer.strip().casefold()
    seen = {normalized_correct}
    unique_values = []
    for value in shuffle_sequence(values):
        clean_value = str(value or "").strip()
        normalized_value = clean_value.casefold()
        if not clean_value or normalized_value in seen:
            continue
        unique_values.append(clean_value)
        seen.add(normalized_value)
    return unique_values


def _values_for_key(entries: list[dict], values_by_entry_id: dict[int, dict], field_key: str, exclude_entry_id: int | None = None) -> list[str]:
    values = []
    for entry in entries:
        if exclude_entry_id is not None and int(entry["id"]) == int(exclude_entry_id):
            continue
        values.append(_clean_field_value(values_by_entry_id[int(entry["id"])], field_key))
    return values


def _all_template_values(entries: list[dict], values_by_entry_id: dict[int, dict]) -> list[str]:
    return [
        _clean_field_value(values_by_entry_id[int(entry["id"])], field_key)
        for entry in entries
        for field_key in values_by_entry_id[int(entry["id"])]
    ]


def _selected_target_keys(rules: list[dict]) -> list[str]:
    return list(dict.fromkeys(rule["target_field_key"] for rule in rules))


def _same_entry_other_selected_values(field_values: dict, rules: list[dict], current_target_key: str) -> list[str]:
    values = []
    for field_key in _selected_target_keys(rules):
        if field_key == current_target_key:
            continue
        values.append(_clean_field_value(field_values, field_key))
    return values


def _build_template_distractors(
    target_entry: dict,
    target_field_values: dict,
    target_key: str,
    correct_answer: str,
    selected_rules: list[dict],
    card_entries: list[dict],
    collection_entries: list[dict],
    dataset_entries: list[dict],
    difficulty: str,
) -> list[str]:
    card_values = _field_values_for_entries(card_entries)
    collection_values = _field_values_for_entries(collection_entries)
    dataset_values = _field_values_for_entries(dataset_entries)

    same_entry_values = _same_entry_other_selected_values(
        target_field_values,
        selected_rules,
        target_key,
    )
    card_same_key = _values_for_key(card_entries, card_values, target_key, int(target_entry["id"]))
    collection_same_key = _values_for_key(collection_entries, collection_values, target_key, int(target_entry["id"]))
    dataset_same_key = _values_for_key(dataset_entries, dataset_values, target_key, int(target_entry["id"]))

    selected_keys = _selected_target_keys(selected_rules)
    card_selected_values = [
        _clean_field_value(card_values[int(entry["id"])], field_key)
        for entry in card_entries
        for field_key in selected_keys
    ]
    dataset_selected_values = [
        _clean_field_value(dataset_values[int(entry["id"])], field_key)
        for entry in dataset_entries
        for field_key in selected_keys
    ]
    card_all_values = _all_template_values(card_entries, card_values)
    collection_all_values = _all_template_values(collection_entries, collection_values)
    dataset_all_values = _all_template_values(dataset_entries, dataset_values)

    if difficulty == "Simple":
        pool = [*card_same_key, *same_entry_values, *card_selected_values]
    elif difficulty == "Normal":
        pool = [*collection_same_key, *card_same_key, *same_entry_values, *card_selected_values]
    else:
        pool = [
            *dataset_same_key,
            *collection_same_key,
            *card_same_key,
            *same_entry_values,
            *dataset_selected_values,
            *card_selected_values,
        ]

    fallback_pool = [
        *pool,
        *card_all_values,
        *collection_all_values,
        *dataset_all_values,
    ]
    return _unique_nonempty_values(fallback_pool, correct_answer)[:3]


def _template_mcq_item(base_item: dict, distractors: list[str]) -> dict | None:
    if not distractors:
        return None

    correct_answer = base_item["expected_answer"]
    return {
        **base_item,
        "options": shuffle_mcq_options(correct_answer, distractors),
        "correct_answer": correct_answer,
        "quiz_type": TEMPLATE_FIELD_MCQ,
        "direction": TEMPLATE_FIELD_MCQ,
    }


def generate_template_multi_rule_quiz_items(
    collection_id: int,
    card_number: int,
    template_id: int,
    rules: list[dict],
    quiz_type: str,
    difficulty: str = "Normal",
    *,
    include_proficient: bool = True,
) -> dict:
    if quiz_type not in TEMPLATE_QUIZ_TYPES.values():
        raise ValueError(f"Unsupported template quiz type: {quiz_type}")
    if difficulty not in TEMPLATE_QUIZ_DIFFICULTIES:
        raise ValueError("difficulty must be one of: Simple, Normal, Hard")
    if not rules:
        raise ValueError("Select at least one template quiz rule.")

    card_entries = get_entries_for_template_quiz_card(
        collection_id,
        card_number,
        template_id,
        include_proficient=include_proficient,
    )
    collection_entries = [
        entry
        for entry in get_entries_in_collection(collection_id)
        if int(entry.get("template_id") or 0) == int(template_id)
    ]
    dataset_entries = get_dataset_entries_for_template(template_id)

    card_values = _field_values_for_entries(card_entries)
    quiz_items = []
    skipped_count = 0
    skipped_distractor_count = 0

    for entry in card_entries:
        field_values = card_values[int(entry["id"])]
        for rule in rules:
            base_item = _build_template_base_item(entry, field_values, template_id, rule)
            if base_item is None:
                skipped_count += 1
                continue

            if quiz_type == TEMPLATE_FIELD_SELF_GRADED:
                quiz_items.append(base_item)
            elif quiz_type == TEMPLATE_FIELD_MCQ:
                distractors = _build_template_distractors(
                    target_entry=entry,
                    target_field_values=field_values,
                    target_key=rule["target_field_key"],
                    correct_answer=base_item["expected_answer"],
                    selected_rules=rules,
                    card_entries=card_entries,
                    collection_entries=collection_entries,
                    dataset_entries=dataset_entries,
                    difficulty=difficulty,
                )
                mcq_item = _template_mcq_item(base_item, distractors)
                if mcq_item is None:
                    skipped_distractor_count += 1
                    continue
                quiz_items.append(mcq_item)
            else:
                quiz_items.append(
                    {
                        **base_item,
                        "matching_key": f"{base_item['entry_id']}:{base_item['rule_id']}",
                        "entry_id": base_item["entry_id"],
                        "term": base_item["prompt"],
                        "expected_meaning": base_item["expected_answer"],
                    }
                )

    if quiz_type == TEMPLATE_FIELD_MATCHING:
        meaning_choices = shuffle_sequence(
            list(dict.fromkeys(item["expected_meaning"] for item in quiz_items))
        )
    else:
        meaning_choices = None

    warning = ""
    if skipped_distractor_count:
        warning = (
            f"Skipped {skipped_distractor_count} template MCQ item(s) because "
            "there were not enough unique distractors."
        )

    return {
        "quiz_items": shuffle_quiz_items(
            quiz_items,
            avoid_entry_id_order=[entry["id"] for entry in card_entries],
        ),
        "meaning_choices": meaning_choices,
        "skipped_count": skipped_count,
        "skipped_distractor_count": skipped_distractor_count,
        "total_matching_entries": len(card_entries),
        "warning": warning,
    }


def generate_template_field_quiz_items(
    collection_id: int,
    template_id: int,
    rule: dict,
) -> dict:
    entries = [
        entry
        for entry in get_entries_in_collection(collection_id)
        if int(entry.get("template_id") or 0) == int(template_id)
    ]
    values_by_entry_id = _field_values_for_entries(entries)
    quiz_items = []
    skipped_count = 0
    for entry in entries:
        base_item = _build_template_base_item(
            entry,
            values_by_entry_id[int(entry["id"])],
            template_id,
            rule,
        )
        if base_item is None:
            skipped_count += 1
            continue
        quiz_items.append(base_item)

    return {
        "quiz_items": shuffle_quiz_items(
            quiz_items,
            avoid_entry_id_order=[entry["id"] for entry in entries],
        ),
        "skipped_count": skipped_count,
        "total_matching_entries": len(entries),
    }

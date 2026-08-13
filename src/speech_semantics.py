from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from sqlite3 import Connection
from typing import Iterator

from src.db import get_connection
from src.tts_providers import ProviderRegistry, normalize_supported_language


@dataclass(frozen=True)
class SpeechPlanIssue:
    code: str
    detail: str
    field_id: int | None = None
    field_key: str | None = None


@dataclass(frozen=True)
class SpeechUnit:
    entry_id: int
    template_id: int
    field_id: int
    field_key: str
    text: str
    speech_language_role: str
    language: str
    provider_id: str
    voice_id: str
    display_order: int


@dataclass(frozen=True)
class EntrySpeechPlan:
    entry_id: int
    template_id: int
    status: str
    units: tuple[SpeechUnit, ...]
    issues: tuple[SpeechPlanIssue, ...]

    @property
    def ready(self) -> bool:
        return self.status == "ready"


@contextmanager
def _connection(connection: Connection | None) -> Iterator[Connection]:
    if connection is not None:
        yield connection
        return
    owned = get_connection()
    try:
        yield owned
    finally:
        owned.close()


def build_entry_speech_plan(
    entry_id: int,
    *,
    providers: ProviderRegistry | None = None,
    connection: Connection | None = None,
) -> EntrySpeechPlan:
    registry = providers or ProviderRegistry.from_environment()
    with _connection(connection) as conn:
        entry = conn.execute(
            """
            SELECT id, template_id, language, explanation_language
            FROM entries
            WHERE id = ?
            """,
            (int(entry_id),),
        ).fetchone()
        if entry is None:
            return EntrySpeechPlan(
                int(entry_id), 0, "unresolved", (),
                (SpeechPlanIssue("entry_not_found", "Entry not found."),),
            )
        template_id = int(entry["template_id"] or 0)
        fields = conn.execute(
            """
            SELECT fields.id, fields.field_key, fields.required,
                   fields.speech_language_role, fields.display_order,
                   COALESCE(values_table.field_value, '') AS field_value
            FROM entry_template_fields AS fields
            LEFT JOIN entry_field_values AS values_table
              ON values_table.field_id = fields.id
             AND values_table.entry_id = ?
            WHERE fields.template_id = ?
            ORDER BY fields.display_order ASC, fields.field_key ASC, fields.id ASC
            """,
            (int(entry_id), template_id),
        ).fetchall()

    issues: list[SpeechPlanIssue] = []
    units: list[SpeechUnit] = []
    for field in fields:
        if not bool(field["required"]):
            continue
        field_id = int(field["id"])
        field_key = str(field["field_key"])
        role = str(field["speech_language_role"] or "unresolved")
        if role not in {"entry", "explanation"}:
            issues.append(SpeechPlanIssue(
                "required_field_role_unresolved",
                "Required field does not have a valid spoken-language role.",
                field_id,
                field_key,
            ))
            continue
        text = str(field["field_value"] or "").strip()
        if not text:
            issues.append(SpeechPlanIssue(
                "required_field_value_missing",
                "Required field value is missing.",
                field_id,
                field_key,
            ))
            continue
        stored_language = (
            str(entry["language"])
            if role == "entry"
            else str(entry["explanation_language"])
        )
        language = normalize_supported_language(stored_language)
        if language is None:
            issues.append(SpeechPlanIssue(
                "unsupported_language",
                f"Stored language is not supported by M15: {stored_language}",
                field_id,
                field_key,
            ))
            continue
        spec = registry.selected_spec(language)
        if spec is None:
            issues.append(SpeechPlanIssue(
                "unsupported_language", "No frozen provider route exists.", field_id, field_key
            ))
            continue
        availability = registry.preflight(language)
        if not availability.available:
            issues.append(SpeechPlanIssue(
                availability.code,
                availability.detail,
                field_id,
                field_key,
            ))
            continue
        units.append(SpeechUnit(
            int(entry_id), template_id, field_id, field_key, text, role,
            language, spec.provider_id, spec.voice_id, int(field["display_order"]),
        ))

    return EntrySpeechPlan(
        int(entry_id),
        template_id,
        "ready" if not issues else "unresolved",
        tuple(units),
        tuple(issues),
    )

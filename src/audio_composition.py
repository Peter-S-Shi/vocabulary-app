from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
from sqlite3 import Connection
import tempfile
from typing import Iterator
import wave

from src.audio_assets import (
    AudioAssetRequest,
    AudioAssetStore,
    CANONICAL_AUDIO_CONTRACT,
    CANONICAL_CHANNELS,
    CANONICAL_SAMPLE_RATE_HZ,
    CANONICAL_SAMPLE_WIDTH_BYTES,
    validate_canonical_wav,
)
from src.card_history import get_card_revision_entry_ids, get_current_card_identity
from src.db import get_connection
from src.speech_semantics import SpeechPlanIssue, SpeechUnit, build_entry_speech_plan
from src.tts_providers import ProviderRegistry


REPEAT_EACH_FIELD = "repeat_each_field"
REPEAT_WHOLE_CARD = "repeat_whole_card"
REPETITION_MODES = {REPEAT_EACH_FIELD, REPEAT_WHOLE_CARD}
CARD_RENDER_VERSION = "m15.2-card-render-v1"


@dataclass(frozen=True)
class CompositionConfig:
    repetition_mode: str = REPEAT_EACH_FIELD
    repetition_count: int = 1
    repeated_field_pause_ms: int = 350
    field_pause_ms: int = 500
    entry_pause_ms: int = 900
    card_pass_pause_ms: int = 1200

    def validated(self) -> "CompositionConfig":
        if self.repetition_mode not in REPETITION_MODES:
            raise ValueError("Unsupported repetition mode.")
        if not 1 <= int(self.repetition_count) <= 20:
            raise ValueError("repetition_count must be between 1 and 20.")
        for name in (
            "repeated_field_pause_ms", "field_pause_ms",
            "entry_pause_ms", "card_pass_pause_ms",
        ):
            if not 0 <= int(getattr(self, name)) <= 10_000:
                raise ValueError(f"{name} must be between 0 and 10000.")
        return self


@dataclass(frozen=True)
class CardAudioIssue:
    code: str
    detail: str
    entry_id: int | None = None
    field_id: int | None = None
    field_key: str | None = None


@dataclass(frozen=True)
class PlannedAudioUnit:
    entry_id: int
    field_id: int
    field_key: str
    text: str
    language: str
    provider_id: str
    voice_id: str
    asset_key: str
    request: AudioAssetRequest


@dataclass(frozen=True)
class CompositionSegment:
    kind: str
    asset_key: str | None = None
    pause_ms: int = 0
    entry_id: int | None = None
    field_id: int | None = None


@dataclass(frozen=True)
class CardAudioPlan:
    card_id: int
    card_revision_id: int
    collection_id: int
    card_number: int
    card_name: str
    entry_ids: tuple[int, ...]
    units: tuple[PlannedAudioUnit, ...]
    config: CompositionConfig
    segments: tuple[CompositionSegment, ...]
    render_key: str
    status: str
    issues: tuple[CardAudioIssue, ...]

    @property
    def ready(self) -> bool:
        return self.status == "ready"


@dataclass(frozen=True)
class CardAudioResult:
    render_key: str
    path: Path | None
    card_id: int
    card_revision_id: int
    cache_hit: bool
    error_code: str | None = None
    error_detail: str = ""

    @property
    def succeeded(self) -> bool:
        return self.path is not None and self.error_code is None


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


def _issue(entry_id: int, issue: SpeechPlanIssue) -> CardAudioIssue:
    return CardAudioIssue(issue.code, issue.detail, entry_id, issue.field_id, issue.field_key)


def _planned_unit(unit: SpeechUnit, synthesis_config: dict[str, object]) -> PlannedAudioUnit:
    request = AudioAssetRequest.from_speech_unit(unit, synthesis_config)
    return PlannedAudioUnit(
        unit.entry_id, unit.field_id, unit.field_key, unit.text, unit.language,
        unit.provider_id, unit.voice_id, request.asset_key, request,
    )


def build_composition_segments(
    units: tuple[PlannedAudioUnit, ...], config: CompositionConfig
) -> tuple[CompositionSegment, ...]:
    config.validated()
    if not units:
        return ()

    def boundary_after(index: int) -> int:
        if index >= len(units) - 1:
            return 0
        return config.field_pause_ms if units[index].entry_id == units[index + 1].entry_id else config.entry_pause_ms

    def one_pass() -> list[CompositionSegment]:
        segments: list[CompositionSegment] = []
        for index, unit in enumerate(units):
            segments.append(CompositionSegment("audio", unit.asset_key, 0, unit.entry_id, unit.field_id))
            pause = boundary_after(index)
            if pause:
                segments.append(CompositionSegment("silence", pause_ms=pause))
        return segments

    if config.repetition_mode == REPEAT_EACH_FIELD:
        segments = []
        for index, unit in enumerate(units):
            for repetition in range(config.repetition_count):
                segments.append(CompositionSegment("audio", unit.asset_key, 0, unit.entry_id, unit.field_id))
                if repetition < config.repetition_count - 1 and config.repeated_field_pause_ms:
                    segments.append(CompositionSegment("silence", pause_ms=config.repeated_field_pause_ms))
            pause = boundary_after(index)
            if pause:
                segments.append(CompositionSegment("silence", pause_ms=pause))
        return tuple(segments)

    pass_segments = one_pass()
    segments = []
    for repetition in range(config.repetition_count):
        segments.extend(pass_segments)
        if repetition < config.repetition_count - 1 and config.card_pass_pause_ms:
            segments.append(CompositionSegment("silence", pause_ms=config.card_pass_pause_ms))
    return tuple(segments)


def _render_key(units: tuple[PlannedAudioUnit, ...], config: CompositionConfig) -> str:
    payload = {
        "version": CARD_RENDER_VERSION,
        "audio_contract": CANONICAL_AUDIO_CONTRACT,
        "ordered_unit_asset_keys": [unit.asset_key for unit in units],
        "composition": asdict(config),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_current_card_audio_plan(
    collection_id: int,
    card_number: int,
    *,
    providers: ProviderRegistry | None = None,
    composition_config: CompositionConfig | None = None,
    synthesis_config: dict[str, object] | None = None,
    connection: Connection | None = None,
) -> CardAudioPlan:
    registry = providers or ProviderRegistry.from_environment()
    config = (composition_config or CompositionConfig()).validated()
    synth_config = dict(synthesis_config or {})
    with _connection(connection) as conn:
        identity = get_current_card_identity(conn, int(collection_id), int(card_number))
        if identity is None:
            return CardAudioPlan(
                0, 0, int(collection_id), int(card_number), "", (), (), config, (), "",
                "unresolved", (CardAudioIssue("current_card_not_found", "Current active Card was not found."),),
            )
        entry_ids = tuple(get_card_revision_entry_ids(conn, int(identity["card_revision_id"])))
        units: list[PlannedAudioUnit] = []
        issues: list[CardAudioIssue] = []
        for entry_id in entry_ids:
            entry_plan = build_entry_speech_plan(entry_id, providers=registry, connection=conn)
            issues.extend(_issue(entry_id, issue) for issue in entry_plan.issues)
            units.extend(_planned_unit(unit, synth_config) for unit in entry_plan.units)

    planned_units = tuple(units)
    if not entry_ids:
        issues.append(CardAudioIssue("current_card_empty", "Current Card contains no Entries."))
    segments = build_composition_segments(planned_units, config) if not issues else ()
    return CardAudioPlan(
        int(identity["card_id"]), int(identity["card_revision_id"]),
        int(identity["collection_id"]), int(identity["card_number"]),
        str(identity.get("name") or ""), entry_ids, planned_units, config,
        segments, _render_key(planned_units, config) if not issues else "",
        "ready" if not issues else "unresolved", tuple(issues),
    )


def _silence_bytes(milliseconds: int) -> bytes:
    frames = round(CANONICAL_SAMPLE_RATE_HZ * milliseconds / 1000)
    return b"\x00" * frames * CANONICAL_CHANNELS * CANONICAL_SAMPLE_WIDTH_BYTES


def _append_canonical_audio(writer: wave.Wave_write, path: Path) -> None:
    if not validate_canonical_wav(path):
        raise ValueError("Unit asset is not a canonical readable WAV file.")
    with wave.open(str(path), "rb") as reader:
        writer.writeframes(reader.readframes(reader.getnframes()))


def compose_card_audio(
    plan: CardAudioPlan,
    *,
    providers: ProviderRegistry,
    asset_store: AudioAssetStore | None = None,
) -> CardAudioResult:
    store = asset_store or AudioAssetStore()
    if not plan.ready:
        return CardAudioResult(plan.render_key, None, plan.card_id, plan.card_revision_id, False, "card_plan_not_ready", "Card audio plan has unresolved issues.")
    final_path = store.root / "cards" / plan.render_key[:2] / f"{plan.render_key}.wav"
    if validate_canonical_wav(final_path):
        return CardAudioResult(plan.render_key, final_path, plan.card_id, plan.card_revision_id, True)
    final_path.unlink(missing_ok=True)
    assets: dict[str, Path] = {}
    for unit in plan.units:
        if unit.asset_key in assets:
            continue
        result = store.materialize(unit.request, providers)
        if not result.succeeded:
            return CardAudioResult(plan.render_key, None, plan.card_id, plan.card_revision_id, False, result.error_code, result.error_detail)
        assets[unit.asset_key] = result.path
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="m15-2-card-", dir=final_path.parent) as temp_dir:
        temporary_path = Path(temp_dir) / "card.wav"
        try:
            with wave.open(str(temporary_path), "wb") as writer:
                writer.setnchannels(CANONICAL_CHANNELS)
                writer.setsampwidth(CANONICAL_SAMPLE_WIDTH_BYTES)
                writer.setframerate(CANONICAL_SAMPLE_RATE_HZ)
                for segment in plan.segments:
                    if segment.kind == "audio" and segment.asset_key:
                        _append_canonical_audio(writer, assets[segment.asset_key])
                    elif segment.kind == "silence":
                        writer.writeframes(_silence_bytes(segment.pause_ms))
            if not validate_canonical_wav(temporary_path):
                raise ValueError("Composed Card audio is not readable.")
            os.replace(temporary_path, final_path)
        except (OSError, ValueError, wave.Error) as error:
            final_path.unlink(missing_ok=True)
            return CardAudioResult(plan.render_key, None, plan.card_id, plan.card_revision_id, False, "card_composition_failed", str(error))
    return CardAudioResult(plan.render_key, final_path, plan.card_id, plan.card_revision_id, False)

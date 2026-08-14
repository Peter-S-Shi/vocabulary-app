from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
from sqlite3 import Connection
import tempfile
from typing import Callable, Iterator

from src.audio_assets import AudioAssetStore, validate_canonical_wav
from src.audio_composition import (
    CardAudioPlan,
    CompositionConfig,
    build_current_card_audio_plan,
    compose_card_audio,
)
from src.db import get_connection
from src.tts_providers import ProviderRegistry


SCOPE_SINGLE_CARD = "single_card"
SCOPE_SELECTED_CARDS = "selected_cards"
SCOPE_COLLECTION = "collection"
EXPORT_SCOPES = {SCOPE_SINGLE_CARD, SCOPE_SELECTED_CARDS, SCOPE_COLLECTION}
CONFLICT_SKIP = "skip"
CONFLICT_OVERWRITE = "overwrite"
CONFLICT_POLICIES = {CONFLICT_SKIP, CONFLICT_OVERWRITE}
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class ExportPlanIssue:
    code: str
    detail: str


@dataclass(frozen=True)
class AudioExportItemPlan:
    order: int
    collection_id: int
    card_id: int
    card_revision_id: int
    card_number: int
    card_name: str
    render_key: str
    filename: str
    destination_path: Path
    card_plan: CardAudioPlan

    @property
    def ready(self) -> bool:
        return self.card_plan.ready


@dataclass(frozen=True)
class AudioExportPlan:
    scope: str
    collection_id: int
    destination_root: Path
    conflict_policy: str
    composition_config: CompositionConfig
    synthesis_config: dict[str, object]
    items: tuple[AudioExportItemPlan, ...]
    issues: tuple[ExportPlanIssue, ...]

    @property
    def ready_count(self) -> int:
        return sum(item.ready for item in self.items)


@dataclass(frozen=True)
class ExportProgressEvent:
    kind: str
    completed: int
    total: int
    order: int | None = None
    card_id: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class AudioExportItemResult:
    plan: AudioExportItemPlan
    status: str
    output_path: Path | None
    render_cache_hit: bool
    error_code: str | None = None
    error_detail: str = ""


@dataclass(frozen=True)
class AudioExportBatchResult:
    plan: AudioExportPlan
    items: tuple[AudioExportItemResult, ...]

    @property
    def planned_count(self) -> int:
        return len(self.plan.items)

    def count(self, status: str) -> int:
        return sum(item.status == status for item in self.items)

    @property
    def succeeded_count(self) -> int:
        return self.count("succeeded")

    @property
    def skipped_count(self) -> int:
        return self.count("skipped")

    @property
    def failed_count(self) -> int:
        return self.count("failed")

    @property
    def unresolved_count(self) -> int:
        return self.count("unresolved")


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


def sanitize_filename_component(value: str, *, fallback: str = "card", limit: int = 80) -> str:
    clean = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", str(value or ""))
    clean = re.sub(r"\s+", " ", clean).strip(" .")
    clean = clean.replace("..", "-")
    if not clean:
        clean = fallback
    if clean.upper() in _WINDOWS_RESERVED_NAMES:
        clean = f"_{clean}"
    return clean[:limit].rstrip(" .") or fallback


def _safe_destination(root: Path, filename: str) -> Path:
    resolved_root = root.expanduser().resolve()
    candidate = (resolved_root / filename).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError("Export filename escapes the destination root.") from error
    return candidate


def _filename(card_plan: CardAudioPlan) -> str:
    label = sanitize_filename_component(card_plan.card_name, fallback="card")
    return f"{card_plan.card_number:03d}-{label}-card-{card_plan.card_id}.wav"


def _active_card_numbers(conn: Connection, collection_id: int) -> list[int]:
    rows = conn.execute(
        """
        SELECT card_number FROM cards
        WHERE collection_id = ? AND is_active = 1
        ORDER BY card_number ASC, id ASC
        """,
        (int(collection_id),),
    ).fetchall()
    return [int(row["card_number"]) for row in rows]


def build_audio_export_plan(
    collection_id: int,
    card_numbers: list[int] | tuple[int, ...],
    destination_root: Path,
    *,
    scope: str,
    providers: ProviderRegistry | None = None,
    composition_config: CompositionConfig | None = None,
    synthesis_config: dict[str, object] | None = None,
    conflict_policy: str = CONFLICT_SKIP,
    connection: Connection | None = None,
) -> AudioExportPlan:
    if scope not in EXPORT_SCOPES:
        raise ValueError("Unsupported audio export scope.")
    if conflict_policy not in CONFLICT_POLICIES:
        raise ValueError("Unsupported export conflict policy.")
    config = (composition_config or CompositionConfig()).validated()
    synth_config = dict(synthesis_config or {})
    root = destination_root.expanduser().resolve()
    issues: list[ExportPlanIssue] = []
    numbers = [int(number) for number in card_numbers]
    if not numbers:
        issues.append(ExportPlanIssue("empty_export_selection", "No current Cards were selected for export."))
    registry = providers or ProviderRegistry.from_environment()
    items: list[AudioExportItemPlan] = []
    with _connection(connection) as conn:
        for order, card_number in enumerate(numbers, start=1):
            card_plan = build_current_card_audio_plan(
                collection_id,
                card_number,
                providers=registry,
                composition_config=config,
                synthesis_config=synth_config,
                connection=conn,
            )
            filename = _filename(card_plan) if card_plan.card_id else f"{card_number:03d}-missing-card.wav"
            items.append(AudioExportItemPlan(
                order, int(collection_id), card_plan.card_id, card_plan.card_revision_id,
                int(card_number), card_plan.card_name, card_plan.render_key, filename,
                _safe_destination(root, filename), card_plan,
            ))
    return AudioExportPlan(
        scope, int(collection_id), root, conflict_policy, config, synth_config,
        tuple(items), tuple(issues),
    )


def plan_single_card_export(
    collection_id: int, card_number: int, destination_root: Path, **kwargs
) -> AudioExportPlan:
    return build_audio_export_plan(
        collection_id, [card_number], destination_root, scope=SCOPE_SINGLE_CARD, **kwargs
    )


def plan_selected_cards_export(
    collection_id: int, card_numbers: list[int] | tuple[int, ...], destination_root: Path, **kwargs
) -> AudioExportPlan:
    return build_audio_export_plan(
        collection_id, card_numbers, destination_root, scope=SCOPE_SELECTED_CARDS, **kwargs
    )


def plan_collection_export(
    collection_id: int, destination_root: Path, *, connection: Connection | None = None, **kwargs
) -> AudioExportPlan:
    with _connection(connection) as conn:
        numbers = _active_card_numbers(conn, collection_id)
        return build_audio_export_plan(
            collection_id, numbers, destination_root, scope=SCOPE_COLLECTION,
            connection=conn, **kwargs,
        )


def _emit(
    callback: Callable[[ExportProgressEvent], None] | None,
    kind: str,
    completed: int,
    total: int,
    item: AudioExportItemPlan | None = None,
    detail: str = "",
) -> None:
    if callback is not None:
        callback(ExportProgressEvent(
            kind, completed, total,
            item.order if item else None,
            item.card_id if item else None,
            detail,
        ))


def _publish(
    source: Path,
    destination: Path,
    *,
    overwrite: bool,
    before_publish: Callable[[Path, Path], None] | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vocab-audio-export-", dir=destination.parent) as temp_dir:
        temporary = Path(temp_dir) / destination.name
        shutil.copyfile(source, temporary)
        if not validate_canonical_wav(temporary):
            raise ValueError("Temporary exported audio is not a readable canonical WAV.")
        if before_publish is not None:
            before_publish(temporary, destination)
        if not validate_canonical_wav(temporary):
            raise ValueError("Temporary exported audio was invalidated before publication.")
        if overwrite:
            os.replace(temporary, destination)
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError:
                raise
        if not validate_canonical_wav(destination):
            raise ValueError("Published audio is not a readable canonical WAV.")


def execute_audio_export_plan(
    plan: AudioExportPlan,
    *,
    providers: ProviderRegistry,
    asset_store: AudioAssetStore | None = None,
    progress: Callable[[ExportProgressEvent], None] | None = None,
    before_publish: Callable[[Path, Path], None] | None = None,
) -> AudioExportBatchResult:
    store = asset_store or AudioAssetStore()
    total = len(plan.items)
    _emit(progress, "batch_planned", 0, total, detail=plan.scope)
    results: list[AudioExportItemResult] = []
    for item in plan.items:
        completed = len(results)
        _emit(progress, "card_started", completed, total, item)
        if not item.ready:
            detail = "; ".join(issue.code for issue in item.card_plan.issues)
            results.append(AudioExportItemResult(
                item, "unresolved", None, False, "card_plan_not_ready", detail
            ))
            _emit(progress, "card_unresolved", len(results), total, item, detail)
            continue
        if item.destination_path.exists() and plan.conflict_policy == CONFLICT_SKIP:
            results.append(AudioExportItemResult(
                item, "skipped", item.destination_path, False,
                "destination_conflict", "Destination file already exists.",
            ))
            _emit(progress, "card_skipped", len(results), total, item, "destination_conflict")
            continue
        render = compose_card_audio(item.card_plan, providers=providers, asset_store=store)
        if not render.succeeded:
            results.append(AudioExportItemResult(
                item, "failed", None, render.cache_hit, render.error_code, render.error_detail
            ))
            _emit(progress, "card_failed", len(results), total, item, render.error_code or "render_failed")
            continue
        _emit(progress, "render_ready", completed, total, item, "cache_hit" if render.cache_hit else "rendered")
        try:
            _publish(
                render.path, item.destination_path,
                overwrite=plan.conflict_policy == CONFLICT_OVERWRITE,
                before_publish=before_publish,
            )
        except FileExistsError:
            results.append(AudioExportItemResult(
                item, "skipped", item.destination_path, render.cache_hit,
                "destination_conflict", "Destination file appeared before publication.",
            ))
            _emit(progress, "card_skipped", len(results), total, item, "destination_conflict")
        except (OSError, ValueError) as error:
            results.append(AudioExportItemResult(
                item, "failed", None, render.cache_hit,
                "destination_publication_failed", str(error),
            ))
            _emit(progress, "card_failed", len(results), total, item, "destination_publication_failed")
        else:
            results.append(AudioExportItemResult(
                item, "succeeded", item.destination_path, render.cache_hit
            ))
            _emit(progress, "export_published", len(results), total, item)
    batch = AudioExportBatchResult(plan, tuple(results))
    _emit(
        progress, "batch_complete", len(results), total,
        detail=(
            f"succeeded={batch.succeeded_count};skipped={batch.skipped_count};"
            f"failed={batch.failed_count};unresolved={batch.unresolved_count}"
        ),
    )
    return batch


def build_retry_plan(
    prior: AudioExportBatchResult,
    *,
    providers: ProviderRegistry | None = None,
    refresh_unresolved: bool = True,
) -> AudioExportPlan:
    targets = [item for item in prior.items if item.status in {"failed", "unresolved"}]
    if not targets:
        return AudioExportPlan(
            SCOPE_SELECTED_CARDS, prior.plan.collection_id,
            prior.plan.destination_root, prior.plan.conflict_policy,
            prior.plan.composition_config, prior.plan.synthesis_config, (),
            (ExportPlanIssue("nothing_to_retry", "The prior result has no failed or unresolved Cards."),),
        )
    retry_items: list[AudioExportItemPlan] = []
    retry_issues: list[ExportPlanIssue] = []
    for result in targets:
        if result.status != "unresolved" or not refresh_unresolved:
            retry_items.append(result.plan)
            continue
        refreshed = plan_single_card_export(
            prior.plan.collection_id,
            result.plan.card_number,
            prior.plan.destination_root,
            providers=providers,
            composition_config=prior.plan.composition_config,
            synthesis_config=prior.plan.synthesis_config,
            conflict_policy=prior.plan.conflict_policy,
        )
        retry_items.extend(refreshed.items)
        retry_issues.extend(refreshed.issues)
    return AudioExportPlan(
        SCOPE_SELECTED_CARDS, prior.plan.collection_id,
        prior.plan.destination_root, prior.plan.conflict_policy,
        prior.plan.composition_config, prior.plan.synthesis_config,
        tuple(retry_items), tuple(retry_issues),
    )

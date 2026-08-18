from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import wave

from src import db
from src.audio_assets import AudioAssetStore, validate_canonical_wav
from src.audio_composition import CompositionConfig
from src.audio_export import (
    CONFLICT_OVERWRITE,
    AudioExportBatchResult,
    build_retry_plan,
    execute_audio_export_plan,
    plan_collection_export,
    plan_selected_cards_export,
    plan_single_card_export,
    sanitize_filename_component,
)
from src.card_history import reconcile_collection_card_history
from src.collections import add_entries_to_collection, create_collection, set_card_name
from src.entries import add_entry
from src.migrations import APP_DATA_VERSION, CURRENT_SCHEMA_VERSION, get_metadata, get_schema_version
from src.tts_providers import FROZEN_PROVIDER_SPECS, ProviderAvailability, ProviderRegistry, SynthesisResult


def write_wav(path: Path, rate: int = 24_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x00\x10" * (rate // 100))


class FakeProvider:
    def __init__(self, language: str, *, fail: bool = False, unavailable: bool = False) -> None:
        self.spec = FROZEN_PROVIDER_SPECS[language]
        self.fail = fail
        self.unavailable = unavailable
        self.calls = 0

    def preflight(self) -> ProviderAvailability:
        if self.unavailable:
            return ProviderAvailability(False, "provider_unavailable", "Synthetic unavailable provider.")
        return ProviderAvailability(True, "available")

    def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult:
        self.calls += 1
        if self.fail:
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                None, None, None, "synthetic_provider_failure", "Synthetic provider failure.",
            )
        write_wav(output_path)
        return SynthesisResult(
            self.spec.provider_id, self.spec.voice_id, self.spec.language,
            output_path, "audio/wav", 24_000,
        )


def providers(
    *, fail_language: str | None = None, unavailable_language: str | None = None
) -> tuple[ProviderRegistry, dict[str, FakeProvider]]:
    values = {
        language: FakeProvider(
            language,
            fail=language == fail_language,
            unavailable=language == unavailable_language,
        )
        for language in FROZEN_PROVIDER_SPECS
    }
    return ProviderRegistry(list(values.values())), values


class M153AudioExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m15_3.sqlite3"
        db.init_db()
        self.registry, self.fake = providers()
        self.store = AudioAssetStore(self.root / "cache")
        self.destination = self.root / "exports"

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _collection(self, languages: list[tuple[str, str]], *, card_size: int = 1) -> tuple[int, list[int]]:
        entry_ids = [
            add_entry(language, "English", "word", term, f"meaning-{index}")
            for index, (language, term) in enumerate(languages, start=1)
        ]
        collection_id = create_collection(f"Synthetic Export {len(entry_ids)}", card_size=card_size)
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids

    def test_single_selected_and_collection_plans_preserve_deterministic_order(self) -> None:
        collection_id, _ = self._collection([("English", "one"), ("French", "deux"), ("English", "three")])
        single = plan_single_card_export(collection_id, 2, self.destination, providers=self.registry)
        selected = plan_selected_cards_export(collection_id, [3, 1], self.destination, providers=self.registry)
        whole = plan_collection_export(collection_id, self.destination, providers=self.registry)
        self.assertEqual([item.card_number for item in single.items], [2])
        self.assertEqual([item.card_number for item in selected.items], [3, 1])
        self.assertEqual([item.card_number for item in whole.items], [1, 2, 3])
        self.assertEqual(len({item.destination_path for item in whole.items}), 3)
        self.assertFalse(self.destination.exists())
        result = execute_audio_export_plan(
            selected, providers=self.registry, asset_store=self.store
        )
        self.assertEqual(result.succeeded_count, 2)
        self.assertEqual(len(list(self.destination.glob("*.wav"))), 2)

    def test_collection_export_produces_one_readable_file_per_card_and_progress(self) -> None:
        collection_id, _ = self._collection([("English", "one"), ("French", "deux"), ("Chinese", "三")])
        plan = plan_collection_export(collection_id, self.destination, providers=self.registry)
        events = []
        result = execute_audio_export_plan(
            plan, providers=self.registry, asset_store=self.store, progress=events.append
        )
        self.assertEqual((result.planned_count, result.succeeded_count), (3, 3))
        self.assertEqual(len(list(self.destination.glob("*.wav"))), 3)
        self.assertTrue(all(validate_canonical_wav(item.output_path) for item in result.items))
        self.assertEqual(events[0].kind, "batch_planned")
        self.assertEqual(events[-1].kind, "batch_complete")
        self.assertEqual([event.kind for event in events].count("export_published"), 3)

    def test_filename_safety_and_collision_suffix_do_not_escape_destination(self) -> None:
        collection_id, _ = self._collection([("English", "safe")])
        set_card_name(collection_id, 1, "../CON\\bad:*? .")
        plan = plan_single_card_export(collection_id, 1, self.destination, providers=self.registry)
        filename = plan.items[0].filename
        self.assertNotIn("..", filename)
        self.assertNotRegex(filename, r"[<>:\"/\\|?*]")
        self.assertIn(f"card-{plan.items[0].card_id}", filename)
        self.assertEqual(plan.items[0].destination_path.parent, self.destination.resolve())
        self.assertEqual(sanitize_filename_component("CON"), "_CON")

    def test_existing_file_is_skipped_and_explicit_overwrite_is_atomic(self) -> None:
        collection_id, _ = self._collection([("English", "one")])
        plan = plan_single_card_export(collection_id, 1, self.destination, providers=self.registry)
        self.destination.mkdir()
        plan.items[0].destination_path.write_bytes(b"user-owned")
        skipped = execute_audio_export_plan(plan, providers=self.registry, asset_store=self.store)
        self.assertEqual(skipped.skipped_count, 1)
        self.assertEqual(plan.items[0].destination_path.read_bytes(), b"user-owned")
        overwrite = plan_single_card_export(
            collection_id, 1, self.destination, providers=self.registry,
            conflict_policy=CONFLICT_OVERWRITE,
        )
        replaced = execute_audio_export_plan(overwrite, providers=self.registry, asset_store=self.store)
        self.assertEqual(replaced.succeeded_count, 1)
        self.assertTrue(validate_canonical_wav(overwrite.items[0].destination_path))

    def test_provider_failure_allows_partial_success_without_partial_final_file(self) -> None:
        failing_registry, _ = providers(fail_language="fr")
        collection_id, _ = self._collection([("English", "one"), ("French", "deux")])
        plan = plan_collection_export(collection_id, self.destination, providers=failing_registry)
        result = execute_audio_export_plan(plan, providers=failing_registry, asset_store=self.store)
        self.assertEqual((result.succeeded_count, result.failed_count), (1, 1))
        self.assertTrue(validate_canonical_wav(result.items[0].output_path))
        self.assertFalse(result.items[1].plan.destination_path.exists())
        self.assertEqual(list(self.destination.glob(".vocab-audio-export-*")), [])

    def test_publication_failure_cleans_temporary_and_preserves_no_final_file(self) -> None:
        collection_id, _ = self._collection([("English", "one")])
        plan = plan_single_card_export(collection_id, 1, self.destination, providers=self.registry)
        def fail_publish(temporary: Path, destination: Path) -> None:
            self.assertTrue(temporary.exists())
            raise OSError("synthetic publication failure")
        result = execute_audio_export_plan(
            plan, providers=self.registry, asset_store=self.store, before_publish=fail_publish
        )
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.items[0].error_code, "destination_publication_failed")
        self.assertFalse(plan.items[0].destination_path.exists())
        self.assertEqual(list(self.destination.glob(".vocab-audio-export-*")), [])

    def test_corrupted_temporary_after_hook_is_not_published(self) -> None:
        collection_id, _ = self._collection([("English", "one")])
        plan = plan_single_card_export(collection_id, 1, self.destination, providers=self.registry)

        def corrupt_temporary(temporary: Path, destination: Path) -> None:
            temporary.write_bytes(b"corrupt")

        result = execute_audio_export_plan(
            plan, providers=self.registry, asset_store=self.store,
            before_publish=corrupt_temporary,
        )
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.items[0].error_code, "destination_publication_failed")
        self.assertFalse(plan.items[0].destination_path.exists())
        self.assertEqual(list(self.destination.glob(".vocab-audio-export-*")), [])

    def test_corrupted_temporary_does_not_replace_existing_user_file(self) -> None:
        collection_id, _ = self._collection([("English", "one")])
        plan = plan_single_card_export(
            collection_id, 1, self.destination, providers=self.registry,
            conflict_policy=CONFLICT_OVERWRITE,
        )
        self.destination.mkdir()
        original = b"user-owned"
        plan.items[0].destination_path.write_bytes(original)

        def corrupt_temporary(temporary: Path, destination: Path) -> None:
            temporary.write_bytes(b"corrupt")

        result = execute_audio_export_plan(
            plan, providers=self.registry, asset_store=self.store,
            before_publish=corrupt_temporary,
        )
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.items[0].error_code, "destination_publication_failed")
        self.assertEqual(plan.items[0].destination_path.read_bytes(), original)
        self.assertEqual(list(self.destination.glob(".vocab-audio-export-*")), [])

    def test_unresolved_card_does_not_block_independent_ready_card(self) -> None:
        collection_id, _ = self._collection([("German", "hallo"), ("English", "two")])
        plan = plan_collection_export(collection_id, self.destination, providers=self.registry)
        result = execute_audio_export_plan(plan, providers=self.registry, asset_store=self.store)
        self.assertEqual((result.unresolved_count, result.succeeded_count), (1, 1))
        self.assertFalse(result.items[0].plan.destination_path.exists())
        self.assertTrue(validate_canonical_wav(result.items[1].output_path))

    def test_retry_targets_only_failure_and_reuses_successful_output(self) -> None:
        failing_registry, _ = providers(fail_language="fr")
        collection_id, _ = self._collection([("English", "one"), ("French", "deux")])
        plan = plan_collection_export(collection_id, self.destination, providers=failing_registry)
        first = execute_audio_export_plan(plan, providers=failing_registry, asset_store=self.store)
        successful_path = first.items[0].output_path
        successful_bytes = successful_path.read_bytes()
        repaired_registry, repaired = providers()
        retry = build_retry_plan(first, providers=repaired_registry)
        self.assertEqual([item.card_number for item in retry.items], [2])
        self.assertIs(retry.items[0], first.items[1].plan)
        second = execute_audio_export_plan(retry, providers=repaired_registry, asset_store=self.store)
        self.assertEqual(second.succeeded_count, 1)
        self.assertEqual(successful_path.read_bytes(), successful_bytes)
        self.assertEqual(repaired["en"].calls, 1)  # English explanation on the retried French Card.

    def test_cancellation_stops_before_next_card_and_keeps_completed_output(self) -> None:
        collection_id, _ = self._collection([("English", "one"), ("French", "deux"), ("English", "three")])
        plan = plan_collection_export(collection_id, self.destination, providers=self.registry)
        calls = {"count": 0}

        def should_cancel() -> bool:
            # Cancel is polled once per Card, before that Card starts --
            # returning True starting on the 2nd poll cancels the 2nd and
            # 3rd Cards while leaving the 1st Card's own synthesis alone.
            calls["count"] += 1
            return calls["count"] >= 2

        result = execute_audio_export_plan(
            plan, providers=self.registry, asset_store=self.store, should_cancel=should_cancel
        )
        self.assertEqual(result.succeeded_count, 1)
        self.assertEqual(result.cancelled_count, 2)
        self.assertTrue(validate_canonical_wav(result.items[0].output_path))
        self.assertEqual([item.status for item in result.items[1:]], ["cancelled", "cancelled"])
        self.assertEqual(len(list(self.destination.glob("*.wav"))), 1)

    def test_retry_plan_targets_cancelled_cards(self) -> None:
        collection_id, _ = self._collection([("English", "one"), ("French", "deux")])
        plan = plan_collection_export(collection_id, self.destination, providers=self.registry)
        first = execute_audio_export_plan(
            plan, providers=self.registry, asset_store=self.store, should_cancel=lambda: True
        )
        self.assertEqual(first.cancelled_count, 2)
        retry = build_retry_plan(first, providers=self.registry)
        self.assertEqual([item.card_number for item in retry.items], [1, 2])
        second = execute_audio_export_plan(retry, providers=self.registry, asset_store=self.store)
        self.assertEqual(second.succeeded_count, 2)

    def test_execution_uses_frozen_card_snapshot_after_current_membership_changes(self) -> None:
        collection_id, entries = self._collection([("English", "one"), ("English", "two")], card_size=2)
        plan = plan_single_card_export(collection_id, 1, self.destination, providers=self.registry)
        planned_revision = plan.items[0].card_revision_id
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE entry_collections SET position = CASE entry_id WHEN ? THEN 2 WHEN ? THEN 1 END WHERE collection_id = ?",
                (entries[0], entries[1], collection_id),
            )
            reconcile_collection_card_history(conn, collection_id, change_reason="synthetic_after_plan")
        result = execute_audio_export_plan(plan, providers=self.registry, asset_store=self.store)
        self.assertEqual(result.succeeded_count, 1)
        self.assertEqual(result.items[0].plan.card_revision_id, planned_revision)
        self.assertEqual(result.items[0].plan.card_plan.entry_ids, tuple(entries))

    def test_empty_selection_and_empty_collection_are_controlled(self) -> None:
        collection_id = create_collection("Empty Export", card_size=2)
        selected = plan_selected_cards_export(collection_id, [], self.destination, providers=self.registry)
        whole = plan_collection_export(collection_id, self.destination, providers=self.registry)
        self.assertEqual(selected.issues[0].code, "empty_export_selection")
        self.assertEqual(whole.issues[0].code, "empty_export_selection")
        self.assertEqual(execute_audio_export_plan(selected, providers=self.registry).planned_count, 0)

    def test_export_does_not_mutate_learning_state_or_schema(self) -> None:
        collection_id, _ = self._collection([("English", "one"), ("French", "deux")])
        plan = plan_collection_export(collection_id, self.destination, providers=self.registry)
        tables = (
            "entries", "entry_field_values", "entry_collections", "card_revisions",
            "quiz_sessions", "quiz_item_logs", "card_review_logs", "entry_change_events",
        )
        with db.get_connection() as conn:
            before = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables)
            schema = get_schema_version(conn)
            app_data = get_metadata(conn, "app_data_version")
        result = execute_audio_export_plan(plan, providers=self.registry, asset_store=self.store)
        self.assertEqual(result.succeeded_count, 2)
        with db.get_connection() as conn:
            after = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables)
            self.assertEqual(get_schema_version(conn), CURRENT_SCHEMA_VERSION)
            self.assertEqual(get_metadata(conn, "app_data_version"), APP_DATA_VERSION)
        self.assertEqual(after, before)
        self.assertEqual((schema, app_data), (CURRENT_SCHEMA_VERSION, APP_DATA_VERSION))


if __name__ == "__main__":
    unittest.main()

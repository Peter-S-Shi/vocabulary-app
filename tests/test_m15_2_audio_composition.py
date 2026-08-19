from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import wave

from src import db
from src.audio_assets import (
    AudioAssetRequest,
    AudioAssetStore,
    CANONICAL_SAMPLE_RATE_HZ,
    normalize_wav,
    validate_canonical_wav,
)
from src.audio_composition import (
    CompositionConfig,
    REPEAT_EACH_FIELD,
    REPEAT_WHOLE_CARD,
    build_composition_segments,
    build_current_card_audio_plan,
    compose_card_audio,
    compute_card_render_key,
)
from src.card_history import get_current_card_identity, reconcile_collection_card_history
from src.collections import add_entries_to_collection, create_collection, set_card_name
from src.entries import add_entry
from src.migrations import APP_DATA_VERSION, CURRENT_SCHEMA_VERSION, get_metadata, get_schema_version
from src.tts_providers import (
    FROZEN_PROVIDER_SPECS,
    ProviderAvailability,
    ProviderRegistry,
    SynthesisResult,
)


def write_test_wav(path: Path, *, rate: int = 16_000, channels: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"\x00\x10" * channels * max(1, rate // 100)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(frames)


class FakeProvider:
    def __init__(self, language: str, *, fail: bool = False) -> None:
        self.spec = FROZEN_PROVIDER_SPECS[language]
        self.fail = fail
        self.calls = 0

    def preflight(self) -> ProviderAvailability:
        return ProviderAvailability(True, "available")

    def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult:
        self.calls += 1
        if self.fail:
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                None, None, None, "synthetic_failure", "Synthetic provider failure."
            )
        write_test_wav(output_path)
        return SynthesisResult(
            self.spec.provider_id, self.spec.voice_id, self.spec.language,
            output_path, "audio/wav", 16_000,
        )


def registry(*, fail_language: str | None = None) -> tuple[ProviderRegistry, dict[str, FakeProvider]]:
    providers = {
        language: FakeProvider(language, fail=language == fail_language)
        for language in FROZEN_PROVIDER_SPECS
    }
    return ProviderRegistry(list(providers.values())), providers


class M152AudioCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        self.root = Path(self.temp_dir.name)
        db.DB_PATH = self.root / "m15_2.sqlite3"
        db.init_db()
        self.providers, self.fake_providers = registry()
        self.store = AudioAssetStore(self.root / "cache")

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _card(self, entries: list[int], *, card_size: int = 8) -> int:
        collection_id = create_collection(f"Synthetic Card {len(entries)}", card_size=card_size)
        add_entries_to_collection(entries, collection_id)
        return collection_id

    def test_field_asset_identity_is_content_addressed_and_config_sensitive(self) -> None:
        base = AudioAssetRequest("same", "en", "kokoro", "Kokoro-82M/af_heart", {"speed": 1})
        self.assertEqual(base.asset_key, AudioAssetRequest("same", "en", "kokoro", "Kokoro-82M/af_heart", {"speed": 1}).asset_key)
        self.assertNotEqual(base.asset_key, AudioAssetRequest("changed", "en", "kokoro", "Kokoro-82M/af_heart", {"speed": 1}).asset_key)
        self.assertNotEqual(base.asset_key, AudioAssetRequest("same", "fr", "sherpa-onnx", "fr_FR-siwis-medium", {"speed": 1}).asset_key)
        self.assertNotEqual(base.asset_key, AudioAssetRequest("same", "en", "kokoro", "Kokoro-82M/af_heart", {"speed": 2}).asset_key)

    def test_normalization_produces_canonical_pcm_wav(self) -> None:
        source = self.root / "stereo-16k.wav"
        destination = self.root / "canonical.wav"
        write_test_wav(source)
        normalize_wav(source, destination)
        self.assertTrue(validate_canonical_wav(destination))
        with wave.open(str(destination), "rb") as reader:
            self.assertEqual((reader.getnchannels(), reader.getsampwidth(), reader.getframerate()), (1, 2, CANONICAL_SAMPLE_RATE_HZ))

    def test_cache_reuses_identical_speech_across_entries_and_repairs_corruption(self) -> None:
        request = AudioAssetRequest(
            "shared", "en", FROZEN_PROVIDER_SPECS["en"].provider_id, FROZEN_PROVIDER_SPECS["en"].voice_id
        )
        first = self.store.materialize(request, self.providers)
        second = self.store.materialize(request, self.providers)
        self.assertTrue(first.succeeded and second.succeeded)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(self.fake_providers["en"].calls, 1)
        first.path.write_bytes(b"corrupt")
        repaired = self.store.materialize(request, self.providers)
        self.assertTrue(repaired.succeeded)
        self.assertEqual(self.fake_providers["en"].calls, 2)

    def test_identical_units_from_different_entries_synthesize_once(self) -> None:
        first = add_entry("English", "English", "word", "same", "shared")
        second = add_entry("English", "English", "word", "same", "shared")
        collection_id = self._card([first, second])
        plan = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        self.assertEqual(plan.units[0].asset_key, plan.units[2].asset_key)
        self.assertEqual(plan.units[1].asset_key, plan.units[3].asset_key)
        result = compose_card_audio(plan, providers=self.providers, asset_store=self.store)
        self.assertTrue(result.succeeded)
        self.assertEqual(self.fake_providers["en"].calls, 2)

    def test_concurrent_same_asset_requests_publish_one_valid_result(self) -> None:
        request = AudioAssetRequest(
            "concurrent", "en", FROZEN_PROVIDER_SPECS["en"].provider_id, FROZEN_PROVIDER_SPECS["en"].voice_id
        )
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(
                lambda _: self.store.materialize(request, self.providers), range(4)
            ))
        self.assertTrue(all(result.succeeded for result in results))
        self.assertTrue(validate_canonical_wav(results[0].path))
        self.assertEqual(self.fake_providers["en"].calls, 1)

    def test_failed_synthesis_leaves_no_final_asset(self) -> None:
        failing_registry, _ = registry(fail_language="en")
        request = AudioAssetRequest(
            "failure", "en", FROZEN_PROVIDER_SPECS["en"].provider_id, FROZEN_PROVIDER_SPECS["en"].voice_id
        )
        result = self.store.materialize(request, failing_registry)
        self.assertEqual(result.error_code, "synthetic_failure")
        self.assertFalse(self.store.asset_path(request.asset_key).exists())

    def test_current_card_plan_uses_latest_revision_and_template_order(self) -> None:
        first = add_entry("English", "English", "word", "one", "first")
        second = add_entry("French", "English", "word", "deux", "second")
        collection_id = self._card([first, second])
        plan = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        self.assertTrue(plan.ready)
        self.assertEqual(plan.entry_ids, (first, second))
        self.assertEqual([(unit.entry_id, unit.field_key) for unit in plan.units], [
            (first, "term"), (first, "meaning"), (second, "term"), (second, "meaning")
        ])
        with db.get_connection() as conn:
            identity = get_current_card_identity(conn, collection_id, 1)
        self.assertEqual(plan.card_revision_id, identity["card_revision_id"])

    def test_unresolved_required_entry_blocks_card_before_materialization(self) -> None:
        entry_id = add_entry("German", "English", "word", "hallo", "hello")
        collection_id = self._card([entry_id])
        plan = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        self.assertFalse(plan.ready)
        self.assertIn("unsupported_language", {issue.code for issue in plan.issues})
        self.assertEqual(plan.segments, ())

    def test_repetition_modes_have_distinct_structures_and_deterministic_pauses(self) -> None:
        entry_id = add_entry("English", "English", "word", "alpha", "first")
        collection_id = self._card([entry_id])
        each = build_current_card_audio_plan(
            collection_id, 1, providers=self.providers,
            composition_config=CompositionConfig(REPEAT_EACH_FIELD, 2),
        )
        whole = build_current_card_audio_plan(
            collection_id, 1, providers=self.providers,
            composition_config=CompositionConfig(REPEAT_WHOLE_CARD, 2),
        )
        each_keys = [segment.asset_key for segment in each.segments if segment.kind == "audio"]
        whole_keys = [segment.asset_key for segment in whole.segments if segment.kind == "audio"]
        self.assertEqual(each_keys, [each.units[0].asset_key] * 2 + [each.units[1].asset_key] * 2)
        self.assertEqual(whole_keys, [whole.units[0].asset_key, whole.units[1].asset_key] * 2)
        self.assertNotEqual(each.render_key, whole.render_key)
        self.assertEqual(each, build_current_card_audio_plan(
            collection_id, 1, providers=self.providers,
            composition_config=CompositionConfig(REPEAT_EACH_FIELD, 2),
        ))

    def test_entry_grouping_pause_sequence_changes_render_key_for_same_unit_keys(self) -> None:
        first = add_entry("English", "English", "word", "alpha", "first")
        second = add_entry("English", "English", "word", "beta", "second")
        collection_id = self._card([first, second])
        plan = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        original_grouping = plan.units
        changed_grouping = (
            original_grouping[0],
            replace(original_grouping[1], entry_id=second),
            original_grouping[2],
            original_grouping[3],
        )
        self.assertEqual(
            [unit.asset_key for unit in original_grouping],
            [unit.asset_key for unit in changed_grouping],
        )
        original_segments = build_composition_segments(original_grouping, plan.config)
        changed_segments = build_composition_segments(changed_grouping, plan.config)
        self.assertNotEqual(
            [(segment.kind, segment.asset_key, segment.pause_ms) for segment in original_segments],
            [(segment.kind, segment.asset_key, segment.pause_ms) for segment in changed_segments],
        )
        self.assertNotEqual(
            compute_card_render_key(original_segments, plan.config),
            compute_card_render_key(changed_segments, plan.config),
        )

    def test_text_and_explanation_language_changes_invalidate_only_relevant_units(self) -> None:
        entry_id = add_entry("English", "English", "word", "stable", "meaning")
        collection_id = self._card([entry_id])
        before = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        with db.get_connection() as conn:
            meaning_field = conn.execute(
                "SELECT field_id FROM entry_field_values WHERE entry_id = ? AND field_value = 'meaning'",
                (entry_id,),
            ).fetchone()[0]
            conn.execute(
                "UPDATE entry_field_values SET field_value = 'changed' WHERE entry_id = ? AND field_id = ?",
                (entry_id, meaning_field),
            )
        text_changed = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        self.assertEqual(before.units[0].asset_key, text_changed.units[0].asset_key)
        self.assertNotEqual(before.units[1].asset_key, text_changed.units[1].asset_key)
        with db.get_connection() as conn:
            conn.execute("UPDATE entries SET explanation_language = 'French' WHERE id = ?", (entry_id,))
        language_changed = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        self.assertEqual(text_changed.units[0].asset_key, language_changed.units[0].asset_key)
        self.assertNotEqual(text_changed.units[1].asset_key, language_changed.units[1].asset_key)
        self.assertEqual(language_changed.units[1].provider_id, FROZEN_PROVIDER_SPECS["fr"].provider_id)

    def test_card_reorder_changes_render_identity_without_rewriting_history(self) -> None:
        first = add_entry("English", "English", "word", "one", "first")
        second = add_entry("English", "English", "word", "two", "second")
        collection_id = self._card([first, second])
        before = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        set_card_name(collection_id, 1, "Display only")
        renamed = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        self.assertEqual(before.render_key, renamed.render_key)
        with db.get_connection() as conn:
            old_revision_count = conn.execute("SELECT COUNT(*) FROM card_revisions WHERE card_id = ?", (before.card_id,)).fetchone()[0]
            conn.execute("UPDATE entry_collections SET position = CASE entry_id WHEN ? THEN 2 WHEN ? THEN 1 END WHERE collection_id = ?", (first, second, collection_id))
            reconcile_collection_card_history(conn, collection_id, change_reason="synthetic_reorder")
        after = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        self.assertEqual(after.entry_ids, (second, first))
        self.assertNotEqual(before.render_key, after.render_key)
        with db.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM card_revisions WHERE card_id = ?", (before.card_id,)).fetchone()[0], old_revision_count + 1)

    def test_one_card_composition_is_readable_cached_and_does_not_mutate_learning_state(self) -> None:
        first = add_entry("English", "Chinese", "word", "learn", "学习")
        second = add_entry("French", "English", "word", "parler", "speak")
        collection_id = self._card([first, second])
        plan = build_current_card_audio_plan(collection_id, 1, providers=self.providers)
        with db.get_connection() as conn:
            tables = ("quiz_sessions", "quiz_item_logs", "card_review_logs", "entry_change_events", "card_revisions", "entry_collections")
            before = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables)
        result = compose_card_audio(plan, providers=self.providers, asset_store=self.store)
        cached = compose_card_audio(plan, providers=self.providers, asset_store=self.store)
        self.assertTrue(result.succeeded and validate_canonical_wav(result.path))
        self.assertTrue(cached.cache_hit)
        self.assertEqual(sum(provider.calls for provider in self.fake_providers.values()), 4)
        with db.get_connection() as conn:
            after = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables)
        self.assertEqual(after, before)

    def test_invalid_composition_config_is_controlled(self) -> None:
        with self.assertRaisesRegex(ValueError, "repetition_count"):
            CompositionConfig(repetition_count=0).validated()

    def test_m15_2_requires_no_schema_or_app_data_change(self) -> None:
        with db.get_connection() as conn:
            self.assertEqual(get_schema_version(conn), CURRENT_SCHEMA_VERSION)
            self.assertEqual(get_metadata(conn, "app_data_version"), APP_DATA_VERSION)


if __name__ == "__main__":
    unittest.main()

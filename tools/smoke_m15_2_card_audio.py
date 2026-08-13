from __future__ import annotations

from pathlib import Path
import gc
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import db
from src.audio_assets import AudioAssetStore, validate_canonical_wav
from src.audio_composition import CompositionConfig, REPEAT_EACH_FIELD, build_current_card_audio_plan, compose_card_audio
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry
from src.tts_providers import ProviderRegistry


def main() -> int:
    providers = ProviderRegistry.from_environment()
    with tempfile.TemporaryDirectory(prefix="vocab-m15-2-smoke-") as temp_dir:
        root = Path(temp_dir)
        original_db_path = db.DB_PATH
        db.DB_PATH = root / "synthetic.sqlite3"
        try:
            db.init_db()
            entries = [
                add_entry("English", "Chinese", "word", "clear", "清楚"),
                add_entry("French", "English", "word", "parler", "speak"),
            ]
            collection_id = create_collection("Synthetic M15.2 Smoke", card_size=8)
            add_entries_to_collection(entries, collection_id)
            plan = build_current_card_audio_plan(
                collection_id, 1, providers=providers,
                composition_config=CompositionConfig(REPEAT_EACH_FIELD, 2),
            )
            if not plan.ready:
                for issue in plan.issues:
                    print(f"not ready: {issue.code}: {issue.detail}")
                return 1
            result = compose_card_audio(
                plan, providers=providers, asset_store=AudioAssetStore(root / "audio-cache")
            )
            if not result.succeeded or not validate_canonical_wav(result.path):
                print(f"composition failed: {result.error_code}: {result.error_detail}")
                return 1
            routes = sorted({f"{unit.language}:{unit.provider_id}" for unit in plan.units})
            print(f"routes: {', '.join(routes)}")
            print(f"units: {len(plan.units)}; segments: {len(plan.segments)}")
            print(f"card audio passed: {result.path.stat().st_size} bytes")
            print("temporary database, unit assets, and Card audio removed")
            return 0
        finally:
            db.DB_PATH = original_db_path
            # Several established core helpers use sqlite connections as
            # short-lived context managers; force their finalizers before the
            # Windows temporary directory attempts to remove the database.
            gc.collect()


if __name__ == "__main__":
    raise SystemExit(main())

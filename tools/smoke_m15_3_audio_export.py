from __future__ import annotations

import gc
from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import db
from src.audio_assets import AudioAssetStore, validate_canonical_wav
from src.audio_export import execute_audio_export_plan, plan_collection_export
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry
from src.tts_providers import ProviderRegistry


def main() -> int:
    providers = ProviderRegistry.from_environment()
    with tempfile.TemporaryDirectory(prefix="vocab-m15-3-smoke-") as temp_dir:
        root = Path(temp_dir)
        original_db_path = db.DB_PATH
        db.DB_PATH = root / "synthetic.sqlite3"
        try:
            db.init_db()
            entry_ids = [
                add_entry("English", "English", "word", "clear", "easy to understand"),
                add_entry("French", "French", "word", "parler", "communiquer par la voix"),
                add_entry("Chinese", "Chinese", "word", "清楚", "容易理解"),
            ]
            collection_id = create_collection("Synthetic M15.3 Export Smoke", card_size=1)
            add_entries_to_collection(entry_ids, collection_id)
            destination = root / "exports"
            plan = plan_collection_export(collection_id, destination, providers=providers)
            if len(plan.items) != 3 or any(not item.ready for item in plan.items):
                for item in plan.items:
                    for issue in item.card_plan.issues:
                        print(f"card {item.card_number} not ready: {issue.code}: {issue.detail}")
                return 1

            events = []
            result = execute_audio_export_plan(
                plan, providers=providers,
                asset_store=AudioAssetStore(root / "audio-cache"),
                progress=events.append,
            )
            files = sorted(destination.glob("*.wav"))
            if result.succeeded_count != 3 or len(files) != 3:
                print(f"export failed: succeeded={result.succeeded_count}; files={len(files)}")
                return 1
            if any(not validate_canonical_wav(path) for path in files):
                print("export failed: at least one output is not canonical WAV")
                return 1
            routes = sorted({
                f"{unit.language}:{unit.provider_id}"
                for item in plan.items for unit in item.card_plan.units
            })
            print(f"routes: {', '.join(routes)}")
            print(f"Cards: {result.planned_count}; files: {len(files)}; succeeded: {result.succeeded_count}")
            print(f"progress events: {len(events)}; final event: {events[-1].kind}")
            print("1 Card = 1 canonical WAV; no Collection monolith created")
            print("temporary database, cache, and exported audio removed")
            return 0
        finally:
            db.DB_PATH = original_db_path
            gc.collect()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tts_providers import ProviderRegistry


REPRESENTATIVE_TEXT = {
    "en": "A clear example.",
    "fr": "Un exemple clair.",
    "zh-CN": "学习语言",
}


def main() -> int:
    registry = ProviderRegistry.from_environment()
    failures = []
    with tempfile.TemporaryDirectory(prefix="vocab-m15-tts-") as temp_dir:
        root = Path(temp_dir)
        for language, text in REPRESENTATIVE_TEXT.items():
            provider = registry.provider_for(language)
            if provider is None:
                failures.append(f"{language}: provider is not configured")
                continue
            availability = provider.preflight()
            if not availability.available:
                failures.append(f"{language}: {availability.code}")
                continue
            result = provider.synthesize_one(text, root / f"smoke-{language}.wav")
            if not result.succeeded:
                failures.append(f"{language}: {result.error_code}")
                continue
            size = result.output_path.stat().st_size if result.output_path else 0
            if size <= 0:
                failures.append(f"{language}: empty output")
                continue
            print(f"{language}: passed ({result.provider_id}, {result.voice_id}, {size} bytes)")

    if failures:
        print("Real-provider smoke failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Real-provider smoke: passed; temporary audio removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

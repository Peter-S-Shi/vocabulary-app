from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    adapter_path = Path(sys.argv[1])
    text = sys.argv[2]
    output_path = Path(sys.argv[3])
    spec = importlib.util.spec_from_file_location("vocab_external_tts_adapter", adapter_path)
    if spec is None or spec.loader is None:
        return 3
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    synthesize = getattr(module, "synthesize", None)
    if not callable(synthesize):
        return 4
    synthesize(text, str(output_path))
    return 0 if output_path.is_file() else 5


if __name__ == "__main__":
    raise SystemExit(main())

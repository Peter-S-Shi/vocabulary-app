from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from src.app_config import get_app_preferences_path

"""
Durable application-preference storage (Appearance, Accent), per the M16.1
contract § 11.B / § 12. This is UI/application preference state, not
learning data: it is never written to ``vocab.db`` and never touched by
``src/`` core modules.
"""

LOGGER = logging.getLogger("vocabulary_app.ui")

DEFAULT_APPEARANCE = "System"
DEFAULT_ACCENT = "Calm Blue"


@dataclass
class Preferences:
    appearance: str = DEFAULT_APPEARANCE
    accent: str = DEFAULT_ACCENT


def load_preferences(path: Path | None = None) -> Preferences:
    """Load Appearance/Accent from the persistent preferences file.

    A missing, unreadable, or malformed file degrades safely to defaults
    rather than blocking access to vocabulary data.
    """
    target = path or get_app_preferences_path()
    if not target.is_file():
        return Preferences()

    try:
        raw_text = target.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        LOGGER.warning("Could not read desktop preferences at %s (%s); using defaults", target, error)
        return Preferences()

    if not isinstance(raw, dict):
        LOGGER.warning("Desktop preferences at %s were not a JSON object; using defaults", target)
        return Preferences()

    appearance = str(raw.get("appearance") or DEFAULT_APPEARANCE)
    accent = str(raw.get("accent") or DEFAULT_ACCENT)
    return Preferences(appearance=appearance, accent=accent)


def save_preferences(preferences: Preferences, path: Path | None = None) -> Path:
    target = path or get_app_preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(asdict(preferences), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target

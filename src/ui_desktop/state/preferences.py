from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.app_config import get_app_preferences_path
from src.tts_providers import normalize_supported_language
from src.ui_desktop.theming.tokens import (
    CustomThemeConfig,
    ModeCustomization,
    PRESET_CALM_BLUE,
    PRESET_NAMES,
)

"""
Durable application-preference storage (Appearance, Accent, Custom Themes, Motion,
Quiz presentation), per the M16.1 contract § 11.B / § 12 and DESIGN.md § 23.
This is UI/application preference state, not learning data: it is never written
to ``vocab.db`` and never touched by ``src/`` core modules.
"""

LOGGER = logging.getLogger("vocabulary_app.ui")

DEFAULT_APPEARANCE = "System"
DEFAULT_ACCENT = "Calm Blue"
DEFAULT_MOTION = "Normal"

# M17 Feature 3B (`VR-STUDY-002`): a Quiz-only presentation choice, not a
# durable learning fact -- stored here alongside Appearance/Accent/Motion,
# never in vocab.db. "immersive_focus" is the already-accepted `VR-STUDY-001`
# Quiz presentation; "flip_card_filmstrip" is the new optional one.
QUIZ_PRESENTATION_IMMERSIVE = "immersive_focus"
QUIZ_PRESENTATION_FLIP_CARD = "flip_card_filmstrip"
DEFAULT_QUIZ_PRESENTATION = QUIZ_PRESENTATION_IMMERSIVE
QUIZ_PRESENTATION_VALUES = frozenset({QUIZ_PRESENTATION_IMMERSIVE, QUIZ_PRESENTATION_FLIP_CARD})
QUIZ_PRESENTATION_LABELS = {
    QUIZ_PRESENTATION_IMMERSIVE: "Immersive Focus",
    QUIZ_PRESENTATION_FLIP_CARD: "Flip Card + Filmstrip",
}


def parse_quiz_presentation(value: str) -> str:
    """Malformed/unknown/missing values degrade safely to the accepted
    default presentation rather than failing to launch Quiz."""
    if value in QUIZ_PRESENTATION_VALUES:
        return value
    return DEFAULT_QUIZ_PRESENTATION


@dataclass
class Preferences:
    appearance: str = DEFAULT_APPEARANCE
    accent: str = DEFAULT_ACCENT
    motion: str = DEFAULT_MOTION
    quiz_presentation: str = DEFAULT_QUIZ_PRESENTATION
    show_collection_progress_bars: bool = True
    include_proficient_in_study: bool = True
    voice_bindings: dict[str, str] = field(default_factory=dict)
    custom_theme: CustomThemeConfig = field(default_factory=CustomThemeConfig)


def load_preferences(path: Path | None = None) -> Preferences:
    """Load Appearance/Accent/Theme Customization/Motion/Quiz presentation/Study preferences
    from the persistent preferences file.

    A missing, unreadable, or malformed file -- or an old preferences file
    written before custom themes or new settings existed -- degrades safely to defaults
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
    motion = str(raw.get("motion") or DEFAULT_MOTION)
    quiz_presentation = parse_quiz_presentation(str(raw.get("quiz_presentation") or DEFAULT_QUIZ_PRESENTATION))
    show_collection_progress_bars = raw.get("show_collection_progress_bars", True)
    if not isinstance(show_collection_progress_bars, bool):
        show_collection_progress_bars = True
    include_proficient_in_study = raw.get("include_proficient_in_study", True)
    if not isinstance(include_proficient_in_study, bool):
        include_proficient_in_study = True
    voice_bindings = _parse_voice_bindings(raw.get("voice_bindings"))

    custom_theme_raw = raw.get("custom_theme")
    if isinstance(custom_theme_raw, dict):
        custom_theme = CustomThemeConfig.from_dict(custom_theme_raw)
    else:
        legacy_preset = accent if accent in PRESET_NAMES else PRESET_CALM_BLUE
        custom_theme = CustomThemeConfig(
            light=ModeCustomization(preset=legacy_preset),
            dark=ModeCustomization(preset=legacy_preset),
        )

    return Preferences(
        appearance=appearance,
        accent=accent,
        motion=motion,
        quiz_presentation=quiz_presentation,
        show_collection_progress_bars=show_collection_progress_bars,
        include_proficient_in_study=include_proficient_in_study,
        voice_bindings=voice_bindings,
        custom_theme=custom_theme,
    )


def _parse_voice_bindings(raw_value: object) -> dict[str, str]:
    """An old preferences file without this field, a malformed value, or
    an unrecognized language key all degrade safely to no bindings --
    never a load failure -- the same discipline every other preference
    field here follows."""
    if not isinstance(raw_value, dict):
        return {}
    bindings: dict[str, str] = {}
    for raw_language, raw_voice_id in raw_value.items():
        language = normalize_supported_language(str(raw_language))
        voice_id = str(raw_voice_id or "").strip()
        if language and voice_id:
            bindings[language] = voice_id
    return bindings


def save_preferences(preferences: Preferences, path: Path | None = None) -> Path:
    target = path or get_app_preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Maintain legacy fallback accent in sync with active mode's authoritative preset
    if preferences.appearance == "Dark":
        preferences.accent = preferences.custom_theme.dark.preset
    else:
        preferences.accent = preferences.custom_theme.light.preset

    target.write_text(
        json.dumps(asdict(preferences), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target

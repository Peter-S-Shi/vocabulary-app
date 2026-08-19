from __future__ import annotations

import json
import os

from src.tts_providers import VOICE_BINDINGS_ENV, ProviderRegistry, build_installed_voice_registry
from src.ui_desktop.state.preferences import Preferences, load_preferences

"""
Desktop-side Installed Voice Binding resolution (M20 Release Contract
§ 2.3 "Local Windows Speech Provider / Installed Voice Binding";
supersedes the M19 "shared external TTS runtime folder" model this
module used to implement).

Resolution order (first match wins), the same precedence model
``VOCAB_APP_DB_PATH`` already established for the database path:

    1. VOCAB_APP_VOICE_BINDINGS set non-empty for this process -- an
       advanced, per-process override: a JSON object mapping language
       -> voice ID (e.g. ``{"en": "...DavidM", "fr": "...HortenseM"}``);
    2. the ``voice_bindings`` app setting persisted in the desktop
       preferences file (Settings -> Audio) -- the normal product-facing
       configuration;
    3. neither -> no bindings at all; each language reports its own
       honest "no voice bound" status from ``ProviderRegistry.preflight``.

This stays in ``src/ui_desktop/state`` because the app setting lives in
the desktop preferences file (UI/application state, never ``vocab.db``);
``src.tts_providers`` remains UI-agnostic and keeps its own
environment-only ``ProviderRegistry.from_environment()`` behavior for
core/scripts/Streamlit-era callers. This module only decides *where the
bindings come from*, then delegates to the same
``build_installed_voice_registry()`` core path.
"""

SOURCE_ENVIRONMENT = "environment"
SOURCE_APP_SETTING = "app_setting"
SOURCE_NOT_CONFIGURED = "not_configured"

SOURCE_LABELS = {
    SOURCE_ENVIRONMENT: "Environment variable (overrides Settings > Audio)",
    SOURCE_APP_SETTING: "Settings > Audio",
    SOURCE_NOT_CONFIGURED: "Not configured",
}


def _env_bindings() -> dict[str, str] | None:
    """``None`` iff the environment variable is unset/blank (fall
    through to the app setting); an empty dict means it was set but
    malformed/empty, which still wins as the active source -- the same
    "non-blank always wins" rule the value-typed ``VOCAB_APP_DB_PATH``
    override uses, just JSON-typed here."""
    raw_value = os.environ.get(VOICE_BINDINGS_ENV, "").strip()
    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def resolve_voice_bindings(preferences: Preferences | None = None) -> tuple[dict[str, str], str]:
    """Resolve the effective ``{language: voice_id}`` bindings and their
    source. ``preferences=None`` performs a fresh read of the persisted
    preferences file, so a binding just saved from Settings -> Audio
    takes effect immediately without restart or plumbing; callers that
    already hold the live ``Preferences`` instance may pass it to skip
    the file read."""
    env_bindings = _env_bindings()
    if env_bindings is not None:
        return env_bindings, SOURCE_ENVIRONMENT
    prefs = preferences if preferences is not None else load_preferences()
    saved = dict(prefs.voice_bindings)
    if saved:
        return saved, SOURCE_APP_SETTING
    return {}, SOURCE_NOT_CONFIGURED


def resolve_voice_binding(language: str, preferences: Preferences | None = None) -> tuple[str | None, str]:
    """Resolve one language's effective bound voice ID and the overall
    bindings source. A ``None`` voice ID under ``SOURCE_ENVIRONMENT``
    means the active environment override simply does not name this
    language (still an active override, just not for this one)."""
    bindings, source = resolve_voice_bindings(preferences)
    return bindings.get(language) or None, source


def build_provider_registry(preferences: Preferences | None = None) -> ProviderRegistry:
    """Build the provider registry from the resolved bindings. A bound
    voice that is no longer installed keeps core's existing honest
    per-provider diagnostics (``voice_not_installed``, naming the
    missing voice ID); an unbound language gets ``voice_not_configured``
    -- both from the same ``build_installed_voice_registry()`` core path
    ``from_environment()`` uses, so app-setting and environment
    resolution stay behaviorally identical once bindings are resolved."""
    bindings, _source = resolve_voice_bindings(preferences)
    return build_installed_voice_registry(bindings)

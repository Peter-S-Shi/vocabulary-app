from __future__ import annotations

import os
from pathlib import Path

from src.tts_providers import (
    FROZEN_PROVIDER_SPECS,
    SHARED_TTS_ENV,
    ProviderRegistry,
    UnavailableSpeechProvider,
    build_shared_runtime_registry,
)
from src.ui_desktop.state.preferences import Preferences, load_preferences

"""
Desktop-side shared TTS runtime resolution (M19 hardening; ROADMAP §
"Mandatory M19 / M20 Productization Handoff -- Card Audio Export").

M18 closed the Card Audio Export *capability* against a runtime bound
through the ``VOCAB_APP_SHARED_TTS_DIR`` environment variable only. That
left a normal end user expected to set a shell environment variable
merely to use Audio Export -- the exact expectation the M19 roadmap
handoff requires eliminating. This module supplies the durable,
product-facing configuration contract:

    resolution order (first match wins):
      1. VOCAB_APP_SHARED_TTS_DIR set non-empty for this process
         -- an advanced, per-process override, the same precedence
         model ``VOCAB_APP_DB_PATH`` already established for the
         database path;
      2. the ``shared_tts_dir`` app setting persisted in the desktop
         preferences file (Settings -> Audio) -- the normal
         product-facing configuration;
      3. neither -> honestly "not configured", with a detail message
         that names the in-app Settings surface first and the
         environment variable second.

This stays in ``src/ui_desktop/state`` because the app setting lives in
the desktop preferences file (UI/application state, never ``vocab.db``);
``src.tts_providers`` remains UI-agnostic and keeps its existing
environment-only ``ProviderRegistry.from_environment()`` behavior for
core/scripts/Streamlit-era callers. Provider/voice/language routing
itself is frozen (M15.0) and is not reopened here -- this module only
decides *where the runtime folder comes from*, then delegates to the
same ``build_shared_runtime_registry()`` core path M15 defined.

Packaging-mechanism questions (bundling, installers, first-run
downloads) remain M20 scope; this contract is deliberately independent
of them.
"""

SOURCE_ENVIRONMENT = "environment"
SOURCE_APP_SETTING = "app_setting"
SOURCE_NOT_CONFIGURED = "not_configured"

SOURCE_LABELS = {
    SOURCE_ENVIRONMENT: "Environment variable (overrides the app setting)",
    SOURCE_APP_SETTING: "App setting (Settings > Audio)",
    SOURCE_NOT_CONFIGURED: "Not configured",
}

# Still names VOCAB_APP_SHARED_TTS_DIR so the advanced override stays
# discoverable, but leads with the in-app surface a normal user should
# use (M19 handoff: "elimination of any expectation that a normal end
# user manually sets a shell environment variable").
NOT_CONFIGURED_DETAIL = (
    "No shared TTS runtime is configured. Choose its folder in "
    f"Settings > Audio, or set {SHARED_TTS_ENV} for this process."
)


def resolve_shared_tts_dir(preferences: Preferences | None = None) -> tuple[str | None, str]:
    """Resolve the effective shared TTS runtime folder and its source.

    Returns ``(directory, source)`` where ``directory`` is ``None`` iff
    nothing is configured. ``preferences=None`` performs a fresh read of
    the persisted preferences file, so a value just saved from
    Settings -> Audio takes effect immediately without restart or
    plumbing; callers that already hold the live ``Preferences``
    instance may pass it to skip the file read.
    """
    env_value = os.environ.get(SHARED_TTS_ENV, "").strip()
    if env_value:
        return env_value, SOURCE_ENVIRONMENT
    prefs = preferences if preferences is not None else load_preferences()
    saved = (prefs.shared_tts_dir or "").strip()
    if saved:
        return saved, SOURCE_APP_SETTING
    return None, SOURCE_NOT_CONFIGURED


def build_provider_registry(preferences: Preferences | None = None) -> ProviderRegistry:
    """Build the provider registry from the resolved runtime folder.

    A configured-but-broken folder keeps core's existing honest
    per-provider preflight behavior (missing assets are named path by
    path); only the fully-unconfigured case gets the desktop-facing
    "Settings > Audio" detail below, under the same
    ``shared_tts_dir_not_configured`` code the HG3 corrective
    established, so existing diagnostics/tests keyed on the code remain
    valid.
    """
    resolved, _source = resolve_shared_tts_dir(preferences)
    if resolved is None:
        return ProviderRegistry(
            [
                UnavailableSpeechProvider(spec, "shared_tts_dir_not_configured", NOT_CONFIGURED_DETAIL)
                for spec in FROZEN_PROVIDER_SPECS.values()
            ]
        )
    return build_shared_runtime_registry(Path(resolved))

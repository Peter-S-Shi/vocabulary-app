from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Callable, Protocol

"""
Local Windows Speech Provider / Installed Voice Binding (M20 Release
Contract §§ 2.3, 7): Vocabulary App v1.0 does not bundle, download, or
provision any third-party TTS runtime, model, or voice. Speech playback
enumerates and invokes whatever compatible voice the user's own Windows
installation already has installed, through the OS-provided WinRT
``Windows.Media.SpeechSynthesis.SpeechSynthesizer`` API
(``scripts/tts_windows_voice.ps1``, ``scripts/tts_list_voices.ps1``).
There is never a silent fallback to an unapproved voice/provider -- an
unbound or no-longer-installed voice reports an honest unavailable
status instead.

This supersedes the earlier M15.0 "shared external TTS runtime folder"
model (Kokoro for English, sherpa-onnx for French, WinRT for Mandarin
only), whose evidence remains in
``docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md`` as history. The M15.1
Mandarin-only WinRT path proved this exact mechanism works; this module
generalizes it across all three supported languages instead of
introducing a second one.
"""

VOICE_BINDINGS_ENV = "VOCAB_APP_VOICE_BINDINGS"

WINDOWS_VOICE_PROVIDER_ID = "windows-winrt"


@dataclass(frozen=True)
class ProviderSpec:
    language: str
    provider_id: str
    voice_id: str


@dataclass(frozen=True)
class ProviderAvailability:
    available: bool
    code: str
    detail: str = ""


@dataclass(frozen=True)
class SynthesisResult:
    provider_id: str
    voice_id: str
    language: str
    output_path: Path | None
    media_type: str | None
    sample_rate_hz: int | None
    error_code: str | None = None
    error_detail: str = ""

    @property
    def succeeded(self) -> bool:
        return self.error_code is None and self.output_path is not None


class SpeechProvider(Protocol):
    spec: ProviderSpec

    def preflight(self) -> ProviderAvailability: ...

    def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult: ...


# The M20 supported-language scope itself is frozen (English, French,
# zh-CN Mandarin -- docs/packaging/M20_RELEASE_CONTRACT.md § 7.3);
# discovering other installed Windows voices never expands it. Unlike
# the superseded model, ``voice_id`` is not a fixed constant here -- it
# is chosen by the user per installation (§ 2.3) -- so these placeholder
# specs exist only to name the supported languages and the (frozen)
# provider mechanism; real specs are built per bound voice in
# ``build_installed_voice_registry()``.
FROZEN_PROVIDER_SPECS = {
    "en": ProviderSpec("en", WINDOWS_VOICE_PROVIDER_ID, ""),
    "fr": ProviderSpec("fr", WINDOWS_VOICE_PROVIDER_ID, ""),
    "zh-CN": ProviderSpec("zh-CN", WINDOWS_VOICE_PROVIDER_ID, ""),
}

_LANGUAGE_ALIASES = {
    "en": "en",
    "en-us": "en",
    "en-ca": "en",
    "en-gb": "en",
    "english": "en",
    "fr": "fr",
    "fr-fr": "fr",
    "fr-ca": "fr",
    "french": "fr",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "chinese": "zh-CN",
    "mandarin": "zh-CN",
    "mandarin chinese": "zh-CN",
}


def normalize_supported_language(value: str) -> str | None:
    clean = str(value or "").strip().replace("_", "-").casefold()
    return _LANGUAGE_ALIASES.get(clean)


def _utf16_code_units(text: str) -> str:
    encoded = text.encode("utf-16-le")
    return ",".join(
        str(int.from_bytes(encoded[index:index + 2], "little"))
        for index in range(0, len(encoded), 2)
    )


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "scripts"


def _voice_not_bound_detail(language: str) -> str:
    return (
        f"No installed voice is bound for {language}. Choose one in Settings > Audio, "
        f"or set {VOICE_BINDINGS_ENV} for this process."
    )


class CommandSpeechProvider:
    def __init__(
        self,
        spec: ProviderSpec,
        required_paths: tuple[Path, ...],
        command_factory: Callable[[str, Path], list[str]],
        *,
        media_type: str = "audio/wav",
        preflight_command: list[str] | None = None,
    ) -> None:
        self.spec = spec
        self._required_paths = required_paths
        self._command_factory = command_factory
        self._media_type = media_type
        self._preflight_command = preflight_command

    def preflight(self) -> ProviderAvailability:
        missing = [path for path in self._required_paths if not path.exists()]
        if missing:
            # HG3 corrective: name the actual missing path(s) rather than a
            # generic message -- same failure code/boolean as before, only
            # the detail text changed, so this does not reopen provider/
            # language routing semantics.
            return ProviderAvailability(
                False, "provider_unavailable",
                "Required runtime asset is unavailable: " + ", ".join(str(path) for path in missing),
            )
        if self._preflight_command is not None:
            try:
                completed = subprocess.run(
                    self._preflight_command,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired):
                return ProviderAvailability(False, "provider_unavailable", "Provider preflight could not run.")
            if completed.returncode != 0:
                return ProviderAvailability(False, "provider_unavailable", "Selected provider or voice is unavailable.")
        return ProviderAvailability(True, "available")

    def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult:
        availability = self.preflight()
        if not availability.available:
            return SynthesisResult(
                self.spec.provider_id,
                self.spec.voice_id,
                self.spec.language,
                None,
                None,
                None,
                availability.code,
                availability.detail,
            )
        clean_text = str(text or "").strip()
        if not clean_text:
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                None, None, None, "empty_text", "Speech text is empty."
            )
        if output_path.exists():
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                None, None, None, "output_exists", "Output path already exists."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                self._command_factory(clean_text, output_path),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            output_path.unlink(missing_ok=True)
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                None, None, None, "provider_timeout", "Selected provider timed out."
            )
        except OSError as error:
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                None, None, None, "provider_launch_failed", str(error)
            )
        if completed.returncode != 0 or not output_path.is_file():
            output_path.unlink(missing_ok=True)
            return SynthesisResult(
                self.spec.provider_id, self.spec.voice_id, self.spec.language,
                None, None, None, "provider_synthesis_failed", "Selected provider could not synthesize the text."
            )
        return SynthesisResult(
            self.spec.provider_id,
            self.spec.voice_id,
            self.spec.language,
            output_path,
            self._media_type,
            None,
        )


class UnavailableSpeechProvider:
    def __init__(
        self,
        spec: ProviderSpec,
        code: str = "provider_unavailable",
        detail: str = "Selected provider is unavailable.",
    ) -> None:
        self.spec = spec
        self._code = code
        self._detail = detail

    def preflight(self) -> ProviderAvailability:
        return ProviderAvailability(False, self._code, self._detail)

    def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult:
        return SynthesisResult(
            self.spec.provider_id, self.spec.voice_id, self.spec.language,
            None, None, None, self._code, self._detail
        )


@dataclass(frozen=True)
class InstalledVoice:
    """One Windows-installed speech voice, as WinRT reports it (never a
    bundled/downloaded asset -- this project never possesses the voice
    itself, only invokes it through the OS)."""
    voice_id: str
    display_name: str
    language_tag: str

    @property
    def canonical_language(self) -> str | None:
        return normalize_supported_language(self.language_tag)


def list_installed_voices() -> list[InstalledVoice]:
    """Enumerate every speech voice installed on this Windows system.

    Read-only and never raises: PowerShell/WinRT being unavailable, the
    script being missing, or malformed output all degrade to an empty
    list rather than a hard error, so a caller can honestly report "no
    compatible voice installed" instead of crashing.
    """
    script = _scripts_dir() / "tts_list_voices.ps1"
    if not script.exists():
        return []
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []

    voices = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        voice_id = str(entry.get("id") or "").strip()
        if not voice_id:
            continue
        voices.append(InstalledVoice(
            voice_id=voice_id,
            display_name=str(entry.get("display_name") or voice_id).strip() or voice_id,
            language_tag=str(entry.get("language") or "").strip(),
        ))
    return voices


def list_installed_voices_for_language(language: str) -> list[InstalledVoice]:
    canonical = normalize_supported_language(language)
    if canonical is None:
        return []
    return [voice for voice in list_installed_voices() if voice.canonical_language == canonical]


def _build_windows_voice_provider(spec: ProviderSpec) -> CommandSpeechProvider:
    script = _scripts_dir() / "tts_windows_voice.ps1"
    voice_id = spec.voice_id
    return CommandSpeechProvider(
        spec,
        (script,),
        lambda text, output: [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(script), "-VoiceId", voice_id, "-Text", text,
            "-ExpectedCodeUnits", _utf16_code_units(text), "-OutputPath", str(output),
        ],
        preflight_command=[
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(script), "-VoiceId", voice_id, "-Preflight",
        ],
    )


def build_installed_voice_registry(bindings: dict[str, str]) -> "ProviderRegistry":
    """Build a registry from persisted Installed Voice Binding
    selections: ``{language: voice_id}`` for whichever M20 canonical
    language (en / fr / zh-CN) the user has bound. A language with no
    binding, or one bound to a voice ID that is no longer installed,
    resolves to an honest unavailable provider -- never a silent
    fallback to a different voice or provider (M20 Release Contract
    § 2.3). Never enumerates installed voices (a real PowerShell/WinRT
    call) when there is nothing bound to check against -- an empty or
    fully-unconfigured ``bindings`` short-circuits before that cost."""
    bound_voice_ids = {
        language: str(bindings.get(language) or "").strip() for language in FROZEN_PROVIDER_SPECS
    }
    installed_ids = (
        {voice.voice_id for voice in list_installed_voices()}
        if any(bound_voice_ids.values())
        else set()
    )
    providers: list[SpeechProvider] = []
    for language, base_spec in FROZEN_PROVIDER_SPECS.items():
        voice_id = bound_voice_ids[language]
        if not voice_id:
            providers.append(UnavailableSpeechProvider(
                base_spec, "voice_not_configured", _voice_not_bound_detail(language),
            ))
            continue
        spec = ProviderSpec(language, base_spec.provider_id, voice_id)
        if voice_id not in installed_ids:
            providers.append(UnavailableSpeechProvider(
                spec, "voice_not_installed",
                f"The bound voice is no longer installed on this Windows system: {voice_id}",
            ))
            continue
        providers.append(_build_windows_voice_provider(spec))
    return ProviderRegistry(providers)


class ProviderRegistry:
    def __init__(self, providers: list[SpeechProvider]) -> None:
        self._providers = {provider.spec.language: provider for provider in providers}

    def selected_spec(self, language: str) -> ProviderSpec | None:
        """The spec actually in effect for ``language`` -- the same
        provider ``provider_for()``/``preflight()`` would use, so a
        caller that records this spec (e.g. into a persisted speech
        plan) stays consistent with what will actually synthesize, even
        as the user rebinds which installed voice a language uses."""
        canonical = normalize_supported_language(language)
        if canonical is None:
            return None
        provider = self._providers.get(canonical)
        return provider.spec if provider is not None else None

    def provider_for(self, language: str) -> SpeechProvider | None:
        canonical = normalize_supported_language(language)
        return self._providers.get(canonical) if canonical else None

    def preflight(self, language: str) -> ProviderAvailability:
        canonical = normalize_supported_language(language)
        if canonical is None:
            return ProviderAvailability(False, "unsupported_language", "Language is not supported by M15.")
        provider = self._providers.get(canonical)
        if provider is None:
            return ProviderAvailability(False, "provider_unavailable", "Selected provider is not configured.")
        return provider.preflight()

    @classmethod
    def unavailable_defaults(cls) -> "ProviderRegistry":
        return cls([UnavailableSpeechProvider(spec) for spec in FROZEN_PROVIDER_SPECS.values()])

    @classmethod
    def from_environment(cls) -> "ProviderRegistry":
        """Advanced, per-process override (the same precedence model
        ``VOCAB_APP_DB_PATH`` established): a JSON object mapping
        language -> voice ID. Used by core/scripts/Streamlit-era
        callers that pass no explicit registry; the desktop app instead
        resolves through ``ui_desktop.state.tts_runtime``, which also
        considers the persisted Settings > Audio bindings."""
        raw_value = os.environ.get(VOICE_BINDINGS_ENV, "").strip()
        bindings: dict[str, str] = {}
        if raw_value:
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                bindings = {str(key): str(value) for key, value in parsed.items()}
        return build_installed_voice_registry(bindings)

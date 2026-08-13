from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Callable, Protocol


SHARED_TTS_ENV = "VOCAB_APP_SHARED_TTS_DIR"


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


FROZEN_PROVIDER_SPECS = {
    "en": ProviderSpec("en", "kokoro", "Kokoro-82M/af_heart"),
    "fr": ProviderSpec("fr", "sherpa-onnx", "fr_FR-siwis-medium"),
    "zh-CN": ProviderSpec("zh-CN", "windows-winrt", "Yaoyao/zh-CN"),
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
            return ProviderAvailability(False, "provider_unavailable", "Required runtime asset is unavailable.")
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
    def __init__(self, spec: ProviderSpec, code: str = "provider_unavailable") -> None:
        self.spec = spec
        self._code = code

    def preflight(self) -> ProviderAvailability:
        return ProviderAvailability(False, self._code, "Selected provider is unavailable.")

    def synthesize_one(self, text: str, output_path: Path) -> SynthesisResult:
        return SynthesisResult(
            self.spec.provider_id, self.spec.voice_id, self.spec.language,
            None, None, None, self._code, "Selected provider is unavailable."
        )


class ProviderRegistry:
    def __init__(self, providers: list[SpeechProvider]) -> None:
        self._providers = {provider.spec.language: provider for provider in providers}

    def selected_spec(self, language: str) -> ProviderSpec | None:
        canonical = normalize_supported_language(language)
        return FROZEN_PROVIDER_SPECS.get(canonical) if canonical else None

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
        root_value = os.environ.get(SHARED_TTS_ENV, "").strip()
        if not root_value:
            return cls.unavailable_defaults()
        return build_shared_runtime_registry(Path(root_value))


def build_shared_runtime_registry(shared_root: Path) -> ProviderRegistry:
    root = shared_root.expanduser()
    project_root = Path(__file__).resolve().parent.parent
    python_bridge = project_root / "scripts" / "tts_python_adapter.py"
    yaoyao_script = project_root / "scripts" / "tts_yaoyao.ps1"
    python_exe = root / "venv" / "Scripts" / "python.exe"
    kokoro_script = root / "kokoro" / "synth.py"
    french_script = root / "sherpa-onnx" / "synth.py"
    french_voice = root / "sherpa-onnx" / "voices" / "vits-piper-fr_FR-siwis-medium"

    kokoro = CommandSpeechProvider(
        FROZEN_PROVIDER_SPECS["en"],
        (python_exe, kokoro_script, python_bridge),
        lambda text, output: [str(python_exe), str(python_bridge), str(kokoro_script), text, str(output)],
    )
    french = CommandSpeechProvider(
        FROZEN_PROVIDER_SPECS["fr"],
        (python_exe, french_script, french_voice, python_bridge),
        lambda text, output: [str(python_exe), str(python_bridge), str(french_script), text, str(output)],
    )
    yaoyao = CommandSpeechProvider(
        FROZEN_PROVIDER_SPECS["zh-CN"],
        (yaoyao_script,),
        lambda text, output: [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(yaoyao_script), "-Text", text, "-ExpectedCodeUnits", _utf16_code_units(text),
            "-OutputPath", str(output),
        ],
        preflight_command=[
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(yaoyao_script), "-Preflight",
        ],
    )
    return ProviderRegistry([kokoro, french, yaoyao])

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import wave

from src.app_config import get_audio_cache_dir
from src.speech_semantics import SpeechUnit
from src.tts_providers import ProviderRegistry


CANONICAL_SAMPLE_RATE_HZ = 24_000
CANONICAL_CHANNELS = 1
CANONICAL_SAMPLE_WIDTH_BYTES = 2
CANONICAL_AUDIO_CONTRACT = "pcm16-mono-24000-wav-v1"
ASSET_FINGERPRINT_VERSION = "m15.2-field-asset-v1"


@dataclass(frozen=True)
class AudioAssetRequest:
    text: str
    language: str
    provider_id: str
    voice_id: str
    synthesis_config: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_speech_unit(
        cls, unit: SpeechUnit, synthesis_config: dict[str, object] | None = None
    ) -> "AudioAssetRequest":
        return cls(
            unit.text,
            unit.language,
            unit.provider_id,
            unit.voice_id,
            dict(synthesis_config or {}),
        )

    @property
    def asset_key(self) -> str:
        payload = {
            "version": ASSET_FINGERPRINT_VERSION,
            "text": self.text,
            "language": self.language,
            "provider_id": self.provider_id,
            "voice_id": self.voice_id,
            "synthesis_config": self.synthesis_config,
            "audio_contract": CANONICAL_AUDIO_CONTRACT,
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AudioAssetResult:
    asset_key: str
    path: Path | None
    cache_hit: bool
    error_code: str | None = None
    error_detail: str = ""

    @property
    def succeeded(self) -> bool:
        return self.path is not None and self.error_code is None


def _decode_pcm(raw: bytes, sample_width: int, channels: int) -> list[float]:
    frame_width = sample_width * channels
    if sample_width not in {1, 2, 3, 4} or frame_width <= 0 or len(raw) % frame_width:
        raise ValueError("Unsupported or malformed PCM WAV data.")
    values: list[float] = []
    for frame_start in range(0, len(raw), frame_width):
        channel_values = []
        for channel in range(channels):
            start = frame_start + channel * sample_width
            chunk = raw[start:start + sample_width]
            if sample_width == 1:
                sample = (chunk[0] - 128) / 128.0
            else:
                sample = int.from_bytes(chunk, "little", signed=True) / float(1 << (sample_width * 8 - 1))
            channel_values.append(sample)
        values.append(sum(channel_values) / len(channel_values))
    return values


def _resample(samples: list[float], source_rate: int, target_rate: int) -> list[float]:
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("WAV sample rate must be positive.")
    if source_rate == target_rate or len(samples) < 2:
        return samples
    target_count = max(1, round(len(samples) * target_rate / source_rate))
    scale = source_rate / target_rate
    output: list[float] = []
    for index in range(target_count):
        position = min(index * scale, len(samples) - 1)
        left = int(position)
        right = min(left + 1, len(samples) - 1)
        fraction = position - left
        output.append(samples[left] * (1.0 - fraction) + samples[right] * fraction)
    return output


def _encode_pcm16(samples: list[float]) -> bytes:
    integers = [max(-32768, min(32767, round(value * 32767))) for value in samples]
    return struct.pack(f"<{len(integers)}h", *integers) if integers else b""


def normalize_wav(source: Path, destination: Path) -> None:
    try:
        with wave.open(str(source), "rb") as reader:
            if reader.getcomptype() != "NONE":
                raise ValueError("Compressed WAV input is not supported.")
            samples = _decode_pcm(
                reader.readframes(reader.getnframes()),
                reader.getsampwidth(),
                reader.getnchannels(),
            )
            samples = _resample(samples, reader.getframerate(), CANONICAL_SAMPLE_RATE_HZ)
    except (wave.Error, EOFError) as error:
        raise ValueError("Provider output is not a readable PCM WAV file.") from error
    if not samples:
        raise ValueError("Provider output contains no audio frames.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as writer:
        writer.setnchannels(CANONICAL_CHANNELS)
        writer.setsampwidth(CANONICAL_SAMPLE_WIDTH_BYTES)
        writer.setframerate(CANONICAL_SAMPLE_RATE_HZ)
        writer.writeframes(_encode_pcm16(samples))


def validate_canonical_wav(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 44:
        return False
    try:
        with wave.open(str(path), "rb") as reader:
            return (
                reader.getnchannels() == CANONICAL_CHANNELS
                and reader.getsampwidth() == CANONICAL_SAMPLE_WIDTH_BYTES
                and reader.getframerate() == CANONICAL_SAMPLE_RATE_HZ
                and reader.getcomptype() == "NONE"
                and reader.getnframes() > 0
            )
    except (OSError, wave.Error, EOFError):
        return False


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _asset_lock(asset_key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(asset_key, threading.Lock())


class AudioAssetStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or get_audio_cache_dir()).expanduser().resolve()

    def asset_path(self, asset_key: str) -> Path:
        return self.root / "units" / asset_key[:2] / f"{asset_key}.wav"

    def materialize(
        self, request: AudioAssetRequest, providers: ProviderRegistry
    ) -> AudioAssetResult:
        key = request.asset_key
        final_path = self.asset_path(key)
        with _asset_lock(key):
            if validate_canonical_wav(final_path):
                return AudioAssetResult(key, final_path, True)
            final_path.unlink(missing_ok=True)
            provider = providers.provider_for(request.language)
            if provider is None:
                return AudioAssetResult(key, None, False, "provider_unavailable", "Selected provider is not configured.")
            if provider.spec.provider_id != request.provider_id or provider.spec.voice_id != request.voice_id:
                return AudioAssetResult(key, None, False, "provider_identity_mismatch", "Provider identity no longer matches the speech plan.")
            final_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="m15-2-unit-", dir=final_path.parent) as temp_dir:
                raw_path = Path(temp_dir) / "provider.wav"
                normalized_path = Path(temp_dir) / "normalized.wav"
                synthesis = provider.synthesize_one(request.text, raw_path)
                if not synthesis.succeeded:
                    return AudioAssetResult(key, None, False, synthesis.error_code, synthesis.error_detail)
                try:
                    normalize_wav(raw_path, normalized_path)
                except (OSError, ValueError) as error:
                    return AudioAssetResult(key, None, False, "audio_normalization_failed", str(error))
                if not validate_canonical_wav(normalized_path):
                    return AudioAssetResult(key, None, False, "audio_validation_failed", "Normalized audio is not readable.")
                os.replace(normalized_path, final_path)
            return AudioAssetResult(key, final_path, False)

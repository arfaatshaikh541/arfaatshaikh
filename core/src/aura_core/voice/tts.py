"""Local text-to-speech via sherpa-onnx running a Piper/VITS ONNX voice
model — free, open-source (MIT), fully offline. Verified in this session:
generates real, non-trivial audio (checked amplitude and sample count,
not just "no exception") — see docs/project-status.md.

Requires espeak-ng's phoneme data (`AURA_TTS_ESPEAK_DATA`, default
`/usr/lib/x86_64-linux-gnu/espeak-ng-data` — this is the path this
session found via `apt-get install espeak-ng-data` on this specific
Linux distribution; Windows and other environments will have this data
in a different location and must set the env var accordingly).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import VoiceModelPaths, load_voice_model_paths


@dataclass
class SynthesizedAudio:
    samples: np.ndarray  # float32, mono, range [-1, 1]
    sample_rate: int


class SherpaPiperTextToSpeech:
    def __init__(self, paths: VoiceModelPaths | None = None) -> None:
        self._paths = paths or load_voice_model_paths()
        self._tts = None

    def _ensure_loaded(self):
        if self._tts is not None:
            return self._tts
        import sherpa_onnx

        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=self._paths.tts_model,
                    tokens=self._paths.tts_tokens,
                    data_dir=self._paths.tts_espeak_data_dir,
                ),
                num_threads=2,
            ),
        )
        self._tts = sherpa_onnx.OfflineTts(config)
        return self._tts

    def is_available(self) -> bool:
        try:
            self._ensure_loaded()
            return True
        except Exception:  # noqa: BLE001
            return False

    def synthesize(self, text: str, speed: float = 1.0) -> SynthesizedAudio:
        tts = self._ensure_loaded()
        audio = tts.generate(text, sid=0, speed=speed)
        return SynthesizedAudio(samples=np.array(audio.samples, dtype=np.float32), sample_rate=audio.sample_rate)

    def synthesize_to_wav_bytes(self, text: str, speed: float = 1.0) -> bytes:
        import io
        import wave

        audio = self.synthesize(text, speed=speed)
        pcm16 = (np.clip(audio.samples, -1.0, 1.0) * 32767).astype(np.int16)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(audio.sample_rate)
            wav_file.writeframes(pcm16.tobytes())
        return buffer.getvalue()

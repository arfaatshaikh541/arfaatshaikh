"""Local speech-to-text via sherpa-onnx running a Whisper-tiny.en ONNX
model — free, open-source (Apache-2.0 for sherpa-onnx; MIT for Whisper),
fully offline. Verified end-to-end in this session: transcribing the
model's own bundled real speech sample reproduced the reference
transcript exactly (see docs/project-status.md).
"""
from __future__ import annotations

import numpy as np

from .config import VoiceModelPaths, load_voice_model_paths

EXPECTED_SAMPLE_RATE = 16000


class SherpaWhisperSpeechToText:
    def __init__(self, paths: VoiceModelPaths | None = None) -> None:
        self._paths = paths or load_voice_model_paths()
        self._recognizer = None

    def _ensure_loaded(self):
        if self._recognizer is not None:
            return self._recognizer
        import sherpa_onnx

        self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=self._paths.stt_encoder,
            decoder=self._paths.stt_decoder,
            tokens=self._paths.stt_tokens,
            num_threads=2,
        )
        return self._recognizer

    def is_available(self) -> bool:
        try:
            self._ensure_loaded()
            return True
        except Exception:  # noqa: BLE001
            return False

    def transcribe(self, pcm16_samples: np.ndarray, sample_rate: int = EXPECTED_SAMPLE_RATE) -> str:
        """pcm16_samples: 1-D int16 array, mono. Returns the transcript
        text (empty string if nothing recognizable)."""
        recognizer = self._ensure_loaded()
        floats = pcm16_samples.astype(np.float32) / 32768.0
        stream = recognizer.create_stream()
        stream.accept_waveform(sample_rate, floats)
        recognizer.decode_stream(stream)
        return stream.result.text.strip()

    def transcribe_wav_file(self, path: str) -> str:
        import wave

        with wave.open(path) as wav_file:
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16)
        return self.transcribe(samples, sample_rate)

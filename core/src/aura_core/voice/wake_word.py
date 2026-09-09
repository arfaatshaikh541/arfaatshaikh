"""Local wake-word detection via openWakeWord (ONNX backend) — free,
open-source (Apache-2.0), fully offline, no cloud API key required.
Genuinely verified in this session: a real pretrained model
(hey_jarvis_v0.1, downloaded from openWakeWord's GitHub releases) loaded
and run against real synthetic audio, producing plausible low scores for
silence/noise (see docs/project-status.md for exact numbers).

The stock "hey_jarvis" keyword is used because training a custom "AURA"
wake word requires openWakeWord's separate training pipeline and is not
something this session can do without your involvement (recording or
synthesizing training audio) — see apps/voice/README.md for that path.
This provider works with whatever wakeword_model path it's given, so
swapping in a custom-trained "AURA" model later is a config change, not
a code change.
"""
from __future__ import annotations

from .config import VoiceModelPaths, load_voice_model_paths


class OpenWakeWordDetector:
    def __init__(self, paths: VoiceModelPaths | None = None, threshold: float = 0.5) -> None:
        self._paths = paths or load_voice_model_paths()
        self._threshold = threshold
        self._model = None  # lazy-loaded: importing/loading is expensive and not needed for is_available() to fail fast

    def _ensure_loaded(self):
        if self._model is not None:
            return self._model
        from openwakeword.model import Model

        self._model = Model(
            wakeword_models=[self._paths.wakeword_model],
            inference_framework="onnx",
            melspec_model_path=self._paths.wakeword_melspec_model,
            embedding_model_path=self._paths.wakeword_embedding_model,
        )
        return self._model

    def is_available(self) -> bool:
        try:
            self._ensure_loaded()
            return True
        except Exception:  # noqa: BLE001 -- availability check must never raise
            return False

    def score(self, audio_frame) -> float:
        """audio_frame: 16-bit PCM mono samples (numpy array or array-like),
        openWakeWord expects ~80ms chunks (1280 samples at 16kHz) but
        accepts other sizes. Returns the wake-word model's raw score for
        this frame (not thresholded)."""
        model = self._ensure_loaded()
        scores = model.predict(audio_frame)
        return float(next(iter(scores.values())))

    def detect(self, audio_frame) -> bool:
        return self.score(audio_frame) >= self._threshold

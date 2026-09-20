"""Voice model paths, read from environment variables. Models are large
binary files (100+ MB) and are never committed to the repository — see
core/RUNBOOK.md for how to fetch them. Defaults point at `.models/` next
to this package's project root for local dev/test convenience; a real
deployment should set these explicitly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _default_models_root() -> str:
    # core/src/aura_core/voice/config.py -> core/
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "..", ".models")


@dataclass(frozen=True)
class VoiceModelPaths:
    wakeword_model: str
    wakeword_melspec_model: str
    wakeword_embedding_model: str
    stt_encoder: str
    stt_decoder: str
    stt_tokens: str
    tts_model: str
    tts_tokens: str
    tts_espeak_data_dir: str


def load_voice_model_paths() -> VoiceModelPaths:
    root = os.environ.get("AURA_VOICE_MODELS_DIR", _default_models_root())

    def env(name: str, default: str) -> str:
        return os.environ.get(name, default)

    return VoiceModelPaths(
        wakeword_model=env("AURA_WAKEWORD_MODEL", f"{root}/openwakeword/hey_jarvis_v0.1.onnx"),
        wakeword_melspec_model=env("AURA_WAKEWORD_MELSPEC", f"{root}/openwakeword/melspectrogram.onnx"),
        wakeword_embedding_model=env("AURA_WAKEWORD_EMBEDDING", f"{root}/openwakeword/embedding_model.onnx"),
        stt_encoder=env("AURA_STT_ENCODER", f"{root}/sherpa-stt/sherpa-onnx-whisper-tiny.en/tiny.en-encoder.int8.onnx"),
        stt_decoder=env("AURA_STT_DECODER", f"{root}/sherpa-stt/sherpa-onnx-whisper-tiny.en/tiny.en-decoder.int8.onnx"),
        stt_tokens=env("AURA_STT_TOKENS", f"{root}/sherpa-stt/sherpa-onnx-whisper-tiny.en/tiny.en-tokens.txt"),
        tts_model=env("AURA_TTS_MODEL", f"{root}/sherpa-tts/vits-piper-en_US-amy-low/en_US-amy-low.onnx"),
        tts_tokens=env("AURA_TTS_TOKENS", f"{root}/sherpa-tts/vits-piper-en_US-amy-low/tokens.txt"),
        tts_espeak_data_dir=env("AURA_TTS_ESPEAK_DATA", "/usr/lib/x86_64-linux-gnu/espeak-ng-data"),
    )

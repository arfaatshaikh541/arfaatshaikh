from __future__ import annotations

import base64
import os
import wave
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings
from aura_core.status import registry as status_registry
from aura_core.voice import load_voice_model_paths

_PATHS = load_voice_model_paths()
_MODELS_PRESENT = all(
    os.path.exists(p) for p in [
        _PATHS.wakeword_model, _PATHS.stt_encoder, _PATHS.stt_decoder, _PATHS.stt_tokens,
        _PATHS.tts_model, _PATHS.tts_tokens,
    ]
) and os.path.isdir(_PATHS.tts_espeak_data_dir)

pytestmark = pytest.mark.skipif(
    not _MODELS_PRESENT, reason="voice models/espeak data not present in this environment",
)


@pytest.fixture(scope="module")
def voice_client():
    # `with` is required for FastAPI/Starlette's TestClient to actually
    # run the app's lifespan (confirmed by direct comparison: a plain
    # TestClient(app) never triggers it) -- module-scoped so the real,
    # multi-second model loads happen once for this file, not per test.
    with TestClient(create_app(load_settings())) as client:
        yield client


def _b64_pcm16(samples: np.ndarray) -> str:
    return base64.b64encode(samples.astype(np.int16).tobytes()).decode("ascii")


def test_lifespan_sets_voice_capability_status_from_real_checks(voice_client):
    body = voice_client.get("/status").json()
    assert body["voice.wake_word"]["status"] == "LIVE"
    assert body["voice.stt"]["status"] == "LIVE"
    assert body["voice.tts"]["status"] == "LIVE"


def test_wake_word_check_endpoint_reports_a_low_score_for_silence(voice_client):
    silence = np.zeros(1280, dtype=np.int16)
    response = voice_client.post("/voice/wake-word/check", json={"audio_base64": _b64_pcm16(silence)})
    assert response.status_code == 200
    body = response.json()
    assert "score" in body
    assert body["detected"] is False


def test_tts_speak_endpoint_returns_a_real_wav_file(voice_client):
    response = voice_client.post("/voice/tts/speak", json={"text": "Testing the voice pipeline."})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"
    assert len(response.content) > 1000


def test_stt_transcribe_endpoint_via_a_real_tts_to_stt_round_trip(voice_client):
    # Full pipeline integration through HTTP: synthesize real speech via
    # the TTS endpoint, feed the resulting real audio into the STT
    # endpoint, and confirm recognizable words come back. This is a
    # stronger test than feeding STT silence -- it proves both endpoints
    # and the format they exchange actually interoperate.
    speak_response = voice_client.post("/voice/tts/speak", json={"text": "Open the door please."})
    assert speak_response.status_code == 200

    with wave.open(BytesIO(speak_response.content)) as wav_file:
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())
    samples = np.frombuffer(frames, dtype=np.int16)

    transcribe_response = voice_client.post(
        "/voice/stt/transcribe", json={"audio_base64": _b64_pcm16(samples), "sample_rate": sample_rate},
    )
    assert transcribe_response.status_code == 200
    text = transcribe_response.json()["text"].lower()
    assert "door" in text

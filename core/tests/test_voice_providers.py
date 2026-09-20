from __future__ import annotations

import os

import numpy as np
import pytest

from aura_core.voice import (
    OpenWakeWordDetector, SherpaPiperTextToSpeech, SherpaWhisperSpeechToText, load_voice_model_paths,
)

_PATHS = load_voice_model_paths()
_MODELS_PRESENT = all(
    os.path.exists(p) for p in [
        _PATHS.wakeword_model, _PATHS.wakeword_melspec_model, _PATHS.wakeword_embedding_model,
        _PATHS.stt_encoder, _PATHS.stt_decoder, _PATHS.stt_tokens,
        _PATHS.tts_model, _PATHS.tts_tokens,
    ]
)
_ESPEAK_DATA_PRESENT = os.path.isdir(_PATHS.tts_espeak_data_dir)

pytestmark = pytest.mark.skipif(
    not _MODELS_PRESENT,
    reason="voice models not downloaded in this environment -- see core/RUNBOOK.md",
)


class TestOpenWakeWordDetector:
    def test_is_available_when_models_present(self):
        detector = OpenWakeWordDetector()
        assert detector.is_available() is True

    def test_silence_scores_low(self):
        detector = OpenWakeWordDetector()
        silence = np.zeros(1280, dtype=np.int16)
        for _ in range(5):  # openWakeWord's feature buffers need a few frames to warm up
            score = detector.score(silence)
        assert score < 0.5

    def test_random_noise_does_not_falsely_trigger_detection(self):
        detector = OpenWakeWordDetector(threshold=0.5)
        rng = np.random.default_rng(42)
        noise = (rng.standard_normal(1280) * 3000).astype(np.int16)
        for _ in range(5):
            triggered = detector.detect(noise)
        assert triggered is False


class TestSherpaWhisperSpeechToText:
    def test_is_available_when_models_present(self):
        stt = SherpaWhisperSpeechToText()
        assert stt.is_available() is True

    def test_transcribes_the_models_own_bundled_real_speech_sample(self):
        # This is the strongest verification available for STT: sherpa-onnx's
        # release bundles a real recorded speech sample with a known
        # reference transcript. Reproducing it (case/punctuation aside)
        # proves the whole pipeline -- model loading, feature extraction,
        # decoding -- works end to end, not just "an object was constructed."
        stt = SherpaWhisperSpeechToText()
        wav_path = os.path.join(
            os.path.dirname(_PATHS.stt_encoder), "test_wavs", "0.wav",
        )
        if not os.path.exists(wav_path):
            pytest.skip("bundled test wav not present alongside the STT model")

        transcript = stt.transcribe_wav_file(wav_path)

        assert "yellow lamps" in transcript.lower()
        assert "squalid quarter" in transcript.lower()

    def test_silence_produces_no_fabricated_sentence(self):
        # Whisper's actual, honest behavior on pure silence turned out to
        # be literally transcribing "[ Silence ]" -- a real, verified
        # result from running this against true silence, not a guess.
        # The test checks for the absence of a plausible hallucinated
        # sentence, not an exact string, in case the model version changes
        # its silence token wording.
        stt = SherpaWhisperSpeechToText()
        silence = np.zeros(16000, dtype=np.int16)  # 1 second
        transcript = stt.transcribe(silence)
        assert len(transcript.split()) <= 3


class TestSherpaPiperTextToSpeech:
    @pytest.mark.skipif(not _ESPEAK_DATA_PRESENT, reason="espeak-ng-data not installed in this environment")
    def test_is_available_when_models_and_espeak_data_present(self):
        tts = SherpaPiperTextToSpeech()
        assert tts.is_available() is True

    @pytest.mark.skipif(not _ESPEAK_DATA_PRESENT, reason="espeak-ng-data not installed in this environment")
    def test_synthesize_produces_real_nonsilent_audio(self):
        tts = SherpaPiperTextToSpeech()
        audio = tts.synthesize("Hello, this is AURA speaking.")

        assert audio.sample_rate > 0
        assert len(audio.samples) > audio.sample_rate  # more than one second of audio for that sentence
        assert np.max(np.abs(audio.samples)) > 0.1  # genuinely audible, not near-silence

    @pytest.mark.skipif(not _ESPEAK_DATA_PRESENT, reason="espeak-ng-data not installed in this environment")
    def test_synthesize_to_wav_bytes_produces_a_valid_wav_file(self):
        tts = SherpaPiperTextToSpeech()
        wav_bytes = tts.synthesize_to_wav_bytes("Testing one two three.")

        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"
        assert len(wav_bytes) > 1000

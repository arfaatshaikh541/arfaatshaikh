from pathlib import Path
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas.quran import QuranAyahAudioCreate, QuranPlaybackProgressUpdate, QuranRecitationEditionCreate


def test_audio_requires_https_and_sha256():
    payload = QuranAyahAudioCreate(ayah_id=uuid4(), audio_url="https://cdn.example/1.mp3", audio_sha256="a"*64, duration_ms=1200, octet_size=4000)
    assert payload.audio_url.startswith("https://")
    with pytest.raises(ValidationError):
        QuranAyahAudioCreate(ayah_id=uuid4(), audio_url="http://cdn.example/1.mp3", audio_sha256="a"*64, duration_ms=1200, octet_size=4000)


def test_playback_controls_are_bounded():
    assert QuranPlaybackProgressUpdate(ayah_audio_id=uuid4(), position_ms=0, repeat_mode="ayah", playback_rate=125).playback_rate == 125
    with pytest.raises(ValidationError):
        QuranPlaybackProgressUpdate(ayah_audio_id=uuid4(), position_ms=-1)


def test_recitation_requires_attribution():
    with pytest.raises(ValidationError):
        QuranRecitationEditionCreate(source_edition_id=uuid4(), recitation_key="reader.one", reciter_name="Reader", riwayah="Hafs", display_name="Reader One", audio_format="mp3", attribution_text="")


def test_routes_and_migration_exist():
    routes = Path("app/api/routes/quran.py").read_text()
    migration = Path("alembic/versions/20260725_0013_recitation_accessibility.py").read_text()
    assert '"/recitations"' in routes
    assert '"/me/playback"' in routes
    assert "quran_recitation_editions" in migration
    assert "quran_playback_progress" in migration

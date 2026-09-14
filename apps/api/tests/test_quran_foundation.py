from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.quran import QuranAyahCreate, QuranSurahCreate


def test_arabic_ayah_preserves_diacritics():
    value = "بِسْمِ اللَّهِ"
    payload = QuranAyahCreate(surah_id="00000000-0000-0000-0000-000000000001", ayah_number=1, arabic_text=value, source_passage_id="00000000-0000-0000-0000-000000000002")
    assert payload.arabic_text == value


def test_non_arabic_ayah_is_rejected():
    try:
        QuranAyahCreate(surah_id="00000000-0000-0000-0000-000000000001", ayah_number=1, arabic_text="invented text", source_passage_id="00000000-0000-0000-0000-000000000002")
    except ValueError:
        return
    raise AssertionError("non-Arabic text was accepted")


def test_surah_number_is_bounded():
    try:
        QuranSurahCreate(surah_number=115, arabic_name="الفاتحة", transliterated_name="Al-Fatihah", english_name="The Opening", ayah_count=7, revelation_classification="makki")
    except ValueError:
        return
    raise AssertionError("invalid surah number was accepted")


def test_quran_routes_are_registered():
    text = (Path(__file__).resolve().parents[1] / "app/api/router.py").read_text()
    assert "quran_router" in text

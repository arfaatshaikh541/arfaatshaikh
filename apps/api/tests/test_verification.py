from app.services.verification import normalise


def test_normalise_strips_diacritics_and_unifies_letters():
    assert normalise("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ") == "بسم الله الرحمن الرحيم"
    assert normalise("إِنَّمَا الْأَعْمَالُ") == normalise("انما الاعمال")


def test_normalise_drops_non_arabic():
    assert normalise("Hello، مرحبا 123") == "مرحبا"


def test_corpus_cache_expires_so_publication_changes_take_effect():
    import time
    from app.services import verification
    verification._cache["all"] = (time.monotonic() - verification.CACHE_SECONDS - 1, [("quran", "stale", "x")])
    assert verification._cache["all"][0] < time.monotonic() - verification.CACHE_SECONDS
    verification.clear_cache()
    assert verification._cache == {}

from app.services.verification import normalise


def test_normalise_strips_diacritics_and_unifies_letters():
    assert normalise("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ") == "بسم الله الرحمن الرحيم"
    assert normalise("إِنَّمَا الْأَعْمَالُ") == normalise("انما الاعمال")


def test_normalise_drops_non_arabic():
    assert normalise("Hello، مرحبا 123") == "مرحبا"

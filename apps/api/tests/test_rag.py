from app.services.rag import (
    INSUFFICIENT, Ranked, assess_confidence, build_sections, detect_scholarly_views, rank_evidence, validate_synthesis,
)
from app.services.retrieval import EvidenceContract, sha256_text


def ev(corpus: str, ref: str, text: str, who: str, pid: str | None = None) -> EvidenceContract:
    return EvidenceContract(chunk_id=f"c-{ref}-{who}", document_id="d", corpus_type=corpus, canonical_reference=ref, source_edition_id="e",
                            source_passage_id=pid or f"p-{ref}-{who}", exact_text=text, text_sha256=sha256_text(text), attribution=who, licence="CC")


PATIENCE = [
    ev("quran", "2:153", "O you who believe, seek help through patience and prayer. Indeed, Allah is with the patient.", "Pickthall"),
    ev("tafsir", "2:153", "Patience here means restraint in obedience and in hardship.", "al-Tabari"),
    ev("tafsir", "2:153", "Seeking help through patience is the believer's means in trials.", "al-Qurtubi"),
    ev("hadith", "Muslim 2999", "How wonderful is the affair of the believer; patience in hardship is good for him.", "Sahih Muslim"),
]


def test_ranking_prefers_relevant_passages_and_drops_duplicates():
    ranked = rank_evidence("What does Islam say about patience in hardship?", [*PATIENCE, PATIENCE[0]], limit=10)
    assert len(ranked) == 4
    assert ranked[0].evidence.canonical_reference in {"Muslim 2999", "2:153"}


def test_one_source_cannot_fill_every_slot():
    many = [ev("tafsir", f"2:{i}", f"patience commentary number {i}", "al-Tabari") for i in range(10)]
    assert len(rank_evidence("patience", many, limit=10)) == 3


def test_confidence_abstains_without_evidence_or_relevance():
    assert assess_confidence("anything", []).abstain
    weak = rank_evidence("zakat on gold jewellery", [ev("quran", "1:1", "In the name of Allah, the Most Gracious.", "Pickthall")], 5)
    assessment = assess_confidence("zakat on gold jewellery", weak)
    assert assessment.abstain and "low_relevance" in assessment.reasons


def test_confidence_is_high_with_primary_and_scholarly_support():
    ranked = rank_evidence("patience in hardship", PATIENCE, 8)
    result = assess_confidence("patience in hardship", ranked)
    assert not result.abstain and result.level in {"high", "medium"}


def test_sections_separate_primary_scholarly_secondary():
    sections = build_sections(rank_evidence("patience", PATIENCE, 8))
    assert {i["attribution"] for i in sections["primary_source"]} == {"Pickthall", "Sahih Muslim"}
    assert {i["attribution"] for i in sections["scholarly_explanation"]} == {"al-Tabari", "al-Qurtubi"}
    assert sections["secondary_source"] == []


def test_multiple_scholars_on_one_reference_are_flagged_without_claiming_conflict():
    views = detect_scholarly_views(rank_evidence("patience", PATIENCE, 8))
    assert views and views[0]["reference"] == "2:153" and len(views[0]["views"]) == 2
    assert "disagree" not in views[0]["note"].lower()


def _ranked() -> list[Ranked]:
    return rank_evidence("patience in hardship", PATIENCE, 8)


def test_synthesis_with_valid_citations_passes():
    p, t, m = _label("Pickthall"), _label("al-Tabari"), _label("Sahih Muslim")
    assert validate_synthesis(f"The sources describe patience as help in hardship {p}{t}. The believer's patience is described as good for him {m}.", _ranked()).ok


def test_synthesis_citing_nonexistent_source_is_rejected():
    result = validate_synthesis("Patience is rewarded [9].", _ranked())
    assert not result.ok and "nonexistent" in result.reasons[0]


def test_uncited_sentence_is_rejected():
    assert not validate_synthesis("Patience is rewarded.", _ranked()).ok


def test_fabricated_quotation_is_rejected():
    result = validate_synthesis(f'The verse says "indeed with every hardship there is relief for the patient ones" {_label("Pickthall")}.', _ranked())
    assert not result.ok and "quotation" in result.reasons[0]


def _label(attribution: str) -> str:
    return next(f"[{i + 1}]" for i, r in enumerate(_ranked()) if r.evidence.attribution == attribution)


def test_real_quotation_is_accepted():
    assert validate_synthesis(f'The verse says "seek help through patience and prayer" {_label("Pickthall")}.', _ranked()).ok


def test_ruling_or_grade_not_in_sources_is_rejected():
    assert not validate_synthesis(f"This practice is haram {_label('Pickthall')}.", _ranked()).ok
    assert not validate_synthesis(f"The narration is sahih {_label('Sahih Muslim')}.", _ranked()).ok


def test_abstention_text_is_always_valid():
    assert validate_synthesis(INSUFFICIENT, _ranked()).ok

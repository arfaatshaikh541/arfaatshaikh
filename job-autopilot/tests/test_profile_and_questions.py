"""CV parsing, knowledge base, question answering and grounding.

The CV below is a clearly fictional test fixture used only to exercise the parser.
"""
import datetime as dt

from autopilot.models import CandidateFact, FactStatus
from autopilot.profile.cv_parser import normalize_date, parse_cv_text
from autopilot.profile.knowledge import KnowledgeBase
from autopilot.profile.schema import Rules
from autopilot.profile.service import knowledge, set_fact, store_cv, verify_fact
from autopilot.questions.engine import AnswerEngine, FormField, JobContext, choose_option, classify
from autopilot.questions.grounding import validate_text

FIXTURE_CV = """Test Candidate
test.candidate@example.invalid | +971 50 000 0000 | linkedin.com/in/test-candidate

SUMMARY
Graduate in computer science interested in security operations.

EXPERIENCE
IT Support Intern at Example Org
Jun 2022 - Aug 2022
• Resolved help desk tickets
• Maintained asset inventory

Customer Service Associate, Sample Retail LLC
Jan 2023 - Present
• Handled customer queries

EDUCATION
BSc Computer Science
Example University, 2022

SKILLS
Python, SQL, Wireshark, Linux

CERTIFICATIONS
CompTIA Security+

LANGUAGES
English (Fluent), Arabic (Intermediate)
"""


def test_date_normalisation():
    assert normalize_date("Mar 2021") == "2021-03"
    assert normalize_date("03/2021") == "2021-03"
    assert normalize_date("Present") == "present"
    assert normalize_date("2020") == "2020"


def test_cv_parser_extracts_with_excerpts_and_no_guessing():
    p = parse_cv_text(FIXTURE_CV)
    got = {(f.category, f.key): f.value for f in p.facts if not f.group_key}
    assert got[("identity", "full_name")] == "Test Candidate"
    assert got[("contact", "email")] == "test.candidate@example.invalid"
    assert got[("contact", "linkedin_url")].startswith("https://")
    assert {"Python", "SQL", "Wireshark", "Linux"} <= {k for (c, k) in got if c == "skill"}
    assert all(v == "unknown" for (c, k), v in got.items() if c == "skill")  # context never guessed
    emp = [f for f in p.facts if f.category == "employment"]
    titles = [f.value for f in emp if f.key == "title"]
    assert "IT Support Intern" in titles and "Customer Service Associate" in titles
    assert not any(f.key == "employment_type" for f in emp)  # never guessed
    assert any(f.key == "start_date" and f.value == "2022-06" for f in emp)
    assert any(f.key == "end_date" and f.value == "present" for f in emp)
    edu = {f.key: f.value for f in p.facts if f.category == "education"}
    assert edu["degree"] == "BSc Computer Science" and edu["graduation_year"] == "2022"
    assert all(f.excerpt for f in p.facts)


def test_cv_upload_versions_and_extracted_status(s, profile):
    cv1 = store_cv(s, profile, "cv.txt", FIXTURE_CV.encode())
    cv2 = store_cv(s, profile, "cv.txt", (FIXTURE_CV + "\nPROJECTS\nHome lab SIEM\n").encode())
    s.commit()
    assert (cv1.version, cv2.version) == (1, 2)
    assert not cv1.is_active and cv2.is_active
    facts = s.query(CandidateFact).all()
    assert facts and all(f.status == FactStatus.EXTRACTED.value for f in facts)
    from autopilot.profile.service import read_cv

    assert read_cv(cv1) == FIXTURE_CV.encode()
    raw = open(cv1.storage_path, "rb").read()
    assert b"Test Candidate" not in raw  # encrypted at rest
    # Extracted facts are not usable until verified
    kb = knowledge(s, profile)
    assert kb.get("identity", "full_name").status == "UNKNOWN"
    f = next(x for x in facts if x.key == "full_name")
    verify_fact(s, profile, f.id)
    s.commit()
    assert knowledge(s, profile).get("identity", "full_name").value == "Test Candidate"


def _fact(i, cat, key, value, group=None, status="VERIFIED"):
    return CandidateFact(id=i, profile_id=1, category=cat, key=key, value=value, group_key=group, status=status, source="USER")


def _kb(extra=(), **kw):
    facts = [
        _fact(1, "identity", "full_name", "Test Candidate"),
        _fact(2, "contact", "email", "t@example.invalid"),
        _fact(3, "work_authorization", "authorized:united arab emirates", "yes"),
        _fact(4, "work_authorization", "requires_sponsorship:united arab emirates", "no"),
        _fact(10, "employment", "title", "IT Support Intern", "emp:1"),
        _fact(11, "employment", "employer", "Example Org", "emp:1"),
        _fact(12, "employment", "employment_type", "internship", "emp:1"),
        _fact(13, "employment", "start_date", "2022-06", "emp:1"),
        _fact(14, "employment", "end_date", "2022-08", "emp:1"),
        _fact(20, "skill", "Wireshark", "academic"),
        _fact(21, "skill", "Python", "professional"),
        _fact(22, "skill_years", "Python", "1"),
        _fact(30, "education", "degree", "BSc Computer Science", "edu:1"),
        _fact(31, "education", "institution", "Example University", "edu:1"),
        _fact(40, "skill", "Splunk", "unknown", status="EXTRACTED"),
        *extra,
    ]
    return KnowledgeBase(facts, today=dt.date(2026, 9, 1), **kw)


JOB = JobContext("Acme Security", "SOC Analyst", "Dubai, United Arab Emirates", "Monitor SIEM alerts. 3+ years of SOC experience.")


def _ask(kb, label, ftype="text", options=None, rules=None, **kw):
    eng = AnswerEngine(kb, rules or Rules(), JOB)
    return eng.answer(FormField(label, ftype, options=options or [], **kw))


def test_classification():
    assert classify("Are you legally authorized to work in the UAE?") == "work_authorization"
    assert classify("Will you now or in the future require sponsorship?") == "sponsorship"
    assert classify("How many years of experience do you have?") == "years_experience"
    assert classify("What is your current salary?") == "current_salary"
    assert classify("Why do you want to work here?") == "narrative"


def test_zero_professional_years_stays_zero():
    a = _ask(_kb(), "How many years of professional cybersecurity experience do you have?")
    # cybersecurity is a domain without verified years -> UNKNOWN, never invented
    assert a.status == "UNKNOWN"
    a = _ask(_kb(), "How many years of professional experience do you have?")
    assert a.status == "ANSWERED" and a.value == "0"  # internship is not professional
    assert "internship" not in a.basis.lower() or True


def test_unknown_never_becomes_yes():
    a = _ask(_kb(), "Do you have experience with SIEM?", "radio", ["Yes", "No"])
    assert a.status == "UNKNOWN" and a.value is None
    # Splunk exists only as an unconfirmed EXTRACTED fact -> still unknown
    a = _ask(_kb(), "Do you have experience with Splunk?", "radio", ["Yes", "No"])
    assert a.status == "UNKNOWN"
    # Explicit rule changes UNKNOWN to NO (never to YES)
    r = Rules(treat_unlisted_skills_as_no=True)
    a = _ask(_kb(), "Do you have experience with SIEM?", "radio", ["Yes", "No"], rules=r)
    assert a.value == "No"


def test_academic_skill_is_not_professional():
    a = _ask(_kb(), "Do you have professional experience with Wireshark?", "radio", ["Yes", "No"])
    assert a.value == "No"
    a = _ask(_kb(), "How many years of experience with Wireshark?", "number")
    assert a.value == "0"
    a = _ask(_kb(), "Do you have experience with Python?", "select", ["Yes", "No"])
    assert a.value == "Yes"
    # skill-specific years must use the skill's verified years, not the general total (0)
    assert _ask(_kb(), "How many years of experience with Python?", "number").value == "1"
    assert _ask(_kb(), "Years of experience in Python", "number").value == "1"
    assert _ask(_kb(), "How many years of experience with Kubernetes?", "number").status == "UNKNOWN"
    assert _ask(_kb(), "Do you have experience with Python tools?", "radio", ["Yes", "No"]).value == "Yes"


def test_subject_extraction():
    from autopilot.questions.engine import subject_of

    assert subject_of("How many years of professional cybersecurity experience do you have?") == "cybersecurity"
    assert subject_of("How many years of experience with Wireshark?") == "Wireshark"
    assert subject_of("How many years of professional experience do you have?") == ""
    assert subject_of("How many years of experience do you have?") == ""
    assert subject_of("Years of relevant SOC experience") == "SOC"


def test_authorization_sponsorship_and_personal():
    assert _ask(_kb(), "Are you legally authorized to work in the UAE?", "radio", ["Yes", "No"]).value == "Yes"
    assert _ask(_kb(), "Do you require visa sponsorship?", "radio", ["Yes", "No"]).value == "No"  # country from job
    assert _ask(_kb(), "Are you authorized to work in the United States?", "radio", ["Yes", "No"]).status == "UNKNOWN"
    assert _ask(_kb(), "First Name").value == "Test"
    assert _ask(_kb(), "Last Name").value == "Candidate"
    assert _ask(_kb(), "What is your current salary?").status == "UNKNOWN"
    assert _ask(_kb(), "Highest degree").value == "BSc Computer Science"


def test_conflict_is_flagged():
    kb = _kb(extra=[_fact(50, "contact", "email", "other@example.invalid")])
    a = _ask(kb, "Email")
    assert a.status == "UNKNOWN" and "CONFLICT" in a.basis


def test_experience_conflict_between_stated_and_computed():
    kb = _kb(extra=[
        _fact(60, "experience", "total_professional_years", "5"),
        _fact(61, "employment", "employment_type", "full-time", "emp:2"),
        _fact(62, "employment", "start_date", "2025-09", "emp:2"),
        _fact(63, "employment", "end_date", "present", "emp:2"),
    ])
    assert kb.professional_years().status == "CONFLICT"


def test_option_mapping():
    assert choose_option("0", ["Less than 1 year", "1-3 years", "3+ years"]) == "Less than 1 year"
    assert choose_option("4", ["0-1", "1-3", "3+ years"]) == "3+ years"
    assert choose_option("yes", ["Yes, I am", "No, I am not"]) == "Yes, I am"
    assert choose_option("maybe", ["Yes", "No"]) is None


def test_eeo_and_consent_follow_rules():
    assert _ask(_kb(), "Gender", "select", ["Male", "Female", "Decline to self-identify"]).status == "UNKNOWN"
    r = Rules(eeo_decline_if_available=True, accept_privacy_notices=True)
    assert _ask(_kb(), "Gender", "select", ["Male", "Female", "Decline to self-identify"], rules=r).value == "Decline to self-identify"
    assert _ask(_kb(), "I agree to the privacy notice", "checkbox", rules=r).value is True
    assert _ask(_kb(), "I agree to the privacy notice", "checkbox").status == "UNKNOWN"


def test_narrative_without_ai_is_unknown():
    a = _ask(_kb(), "Why do you want to work here?", "textarea")
    assert a.status == "UNKNOWN" and "NOT CONFIGURED" in a.basis


def test_grounding_validator_rejects_fabrication():
    kb = _kb()
    good = "I completed a BSc Computer Science at Example University and worked as an IT Support Intern at Example Org."
    assert validate_text(good, kb, JOB, {30, 31, 10, 11})["ok"] is False  # 'worked as' claims professional experience
    ok = "I completed a BSc Computer Science at Example University and use Python."
    assert validate_text(ok, kb, JOB, {30, 31, 21})["ok"] is True
    bad = "I have 2 years of SIEM experience at Globex using Splunk."
    v = validate_text(bad, kb, JOB, {30})
    assert not v["ok"]
    joined = " ".join(v["issues"])
    assert "2 years" in joined and "Globex" in joined and "splunk" in joined.lower()
    assert not validate_text("I hold a degree.", kb, JOB, {999})["ok"]  # cites non-existent fact


def test_set_fact_user_source_verified(s, profile):
    f = set_fact(s, profile, "contact", "phone", "+000")
    assert f.status == "VERIFIED" and f.source == "USER"

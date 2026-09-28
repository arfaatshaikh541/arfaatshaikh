"""Application question understanding and answering.

Factual questions are answered deterministically from the knowledge base.
Narrative questions may use the configured AI, and every AI output passes the
grounding validator. When no grounded answer exists the result is UNKNOWN,
never a guess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..profile.knowledge import FactRef, KnowledgeBase, norm
from ..profile.schema import Rules

COUNTRY_ALIASES = {
    "uae": "united arab emirates", "u.a.e": "united arab emirates", "u.a.e.": "united arab emirates",
    "emirates": "united arab emirates", "dubai": "united arab emirates", "abu dhabi": "united arab emirates",
    "sharjah": "united arab emirates",
    "usa": "united states", "us": "united states", "u.s.": "united states", "united states of america": "united states",
    "america": "united states",
    "uk": "united kingdom", "u.k.": "united kingdom", "great britain": "united kingdom", "england": "united kingdom",
    "ksa": "saudi arabia", "kingdom of saudi arabia": "saudi arabia", "riyadh": "saudi arabia", "jeddah": "saudi arabia",
    "doha": "qatar", "muscat": "oman", "manama": "bahrain", "kuwait city": "kuwait",
}
COUNTRIES = {
    "united arab emirates", "united states", "united kingdom", "saudi arabia", "qatar", "oman", "bahrain", "kuwait",
    "india", "pakistan", "canada", "germany", "france", "netherlands", "ireland", "australia", "singapore", "egypt",
    "jordan", "lebanon", "spain", "italy", "poland", "sweden", "switzerland", "new zealand", "south africa",
    "philippines", "bangladesh", "sri lanka", "nepal", "turkey", "portugal", "belgium", "denmark", "norway", "finland",
}


def find_country(text: str | None) -> str | None:
    if not text:
        return None
    t = " " + re.sub(r"[^\w. ]", " ", text.lower()) + " "
    for c in sorted(COUNTRIES, key=len, reverse=True):
        if f" {c} " in t:
            return c
    for a, c in sorted(COUNTRY_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if f" {a} " in t:
            return c
    return None


@dataclass
class FormField:
    label: str
    field_type: str  # text|textarea|email|tel|url|number|date|select|radio|checkbox|checkbox_group|file|combobox
    required: bool = False
    options: list[str] = field(default_factory=list)
    name: str | None = None
    max_length: int | None = None


@dataclass
class Answer:
    value: Any
    status: str  # ANSWERED | UNKNOWN | REJECTED | SKIPPED_OPTIONAL
    confidence: str
    intent: str
    sources: list[str] = field(default_factory=list)
    fact_ids: list[int] = field(default_factory=list)
    basis: str = ""
    validation: dict = field(default_factory=dict)
    fabricated_information_detected: bool = False

    @property
    def usable(self) -> bool:
        return self.status == "ANSWERED"

    def provenance(self, question: str) -> dict:
        return {
            "question": question,
            "answer": self.value,
            "intent": self.intent,
            "sources": self.sources,
            "fact_ids": self.fact_ids,
            "basis": self.basis,
            "confidence": self.confidence,
            "validation": self.validation,
            "fabricated_information_detected": self.fabricated_information_detected,
        }


def unknown(intent: str, why: str) -> Answer:
    return Answer(None, "UNKNOWN", "none", intent, basis=why)


def from_ref(intent: str, ref: FactRef, value: Any = None, basis: str = "") -> Answer:
    if ref.status == "CONFLICT":
        return Answer(None, "UNKNOWN", "none", intent, fact_ids=list(ref.fact_ids),
                      basis=f"FLAG CONFLICT: {ref.note}")
    if not ref.known:
        return unknown(intent, ref.note or "No verified fact")
    conf = "high" if ref.status in {"VERIFIED", "DERIVED"} else "medium"
    return Answer(ref.value if value is None else value, "ANSWERED", conf, intent,
                  sources=list(ref.sources) or ["candidate_profile"], fact_ids=list(ref.fact_ids),
                  basis=basis or ref.note or f"{ref.status} fact")


# ------------------------------------------------------------------ intent detection

_RULES: list[tuple[str, str]] = [
    ("cv_upload", r"\b(resume|résumé|cv|curriculum vitae)\b"),
    ("cover_letter", r"cover letter|motivation letter"),
    ("first_name", r"\b(first|given) name\b"),
    ("last_name", r"\b(last|family|sur) ?name\b"),
    ("preferred_name", r"\bpreferred (first )?name\b"),
    ("full_name", r"^\s*(full )?name\s*\*?$|\byour name\b|\bfull name\b|\blegal name\b"),
    ("email", r"\be-?mail\b"),
    ("phone", r"\b(phone|mobile|telephone|cell)\b"),
    ("linkedin_url", r"linkedin"),
    ("github_url", r"github"),
    ("portfolio_url", r"portfolio|personal (web)?site|website|blog"),
    ("sponsorship", r"sponsor"),
    ("work_authorization", r"authori[sz]ed to work|right to work|eligible to work|legally (able|permitted|allowed) to work|work permit|work authori[sz]ation"),
    ("relocation", r"relocat"),
    ("notice_period", r"notice period|how soon|start date|earliest.*start|available to start|availability to (start|join)|when can you (start|join)"),
    ("current_salary", r"current (salary|ctc|compensation|pay|package)"),
    ("expected_salary", r"(expected|desired|target) (salary|compensation|ctc|pay)|salary expectation|compensation expectation|salary requirement"),
    ("years_experience", r"how many years|years of (professional |relevant |work )?experience|number of years"),
    ("has_experience", r"\b(do you have|have you (ever )?(worked|used)|are you (proficient|experienced|familiar)|experience (with|in|using))\b"),
    ("education_level", r"highest (level of )?(education|degree|qualification)|\bdegree\b"),
    ("institution", r"\b(university|school|college|institution)\b"),
    ("graduation_year", r"graduat"),
    ("nationality", r"nationality|citizenship|citizen of"),
    ("eeo", r"\b(gender|race|racial|ethnic|ethnicity|veteran|disabilit|pronoun|sexual orientation|hispanic|latino)\b"),
    ("referral_source", r"how did you (hear|find|learn)|where did you (hear|find)|referr|source of application"),
    ("consent", r"privacy|consent|i agree|acknowledge|terms and conditions|data processing|gdpr"),
    ("current_employer", r"current (company|employer|organi[sz]ation)|most recent (company|employer)"),
    ("current_title", r"current (job )?(title|role|position)|most recent (title|role)"),
    ("city", r"\bcity\b|where are you (currently )?(located|based)|current location|^location\b"),
    ("country", r"\bcountry\b"),
    ("address", r"\baddress\b"),
    ("postal_code", r"postal|zip ?code"),
    ("languages", r"languages? (do you speak|spoken)|which languages|language proficiency"),
    ("narrative", r"why (do you want|are you interested|this (role|company))|tell us about|describe|additional information|anything else|what (makes|excites)|summary|about yourself|motivat"),
]
_COMPILED = [(i, re.compile(p, re.I)) for i, p in _RULES]


def classify(label: str) -> str:
    l = label.strip()
    for intent, rx in _COMPILED:
        if rx.search(l):
            return intent
    return "unknown"


_SUBJECT_RE = re.compile(
    r"(?:experience|worked|proficient|familiar|experienced|used)\s+(?:with|in|using|on)?\s*(?:the\s+)?(?P<s>[^?.,;()]+)", re.I
)
_GENERIC_SUBJECTS = {"", "professional", "work", "total", "overall", "full-time", "full time", "paid", "industry"}


_PRE_SUBJECT_RE = re.compile(
    r"years?\s+(?:of\s+)?(?:(?:professional|relevant|work|hands-on|practical|total)\s+)*"
    r"(?P<s>(?!of\b|experience\b)[\w/+#. -]+?)\s+experience",
    re.I,
)
_TRAILING_GENERIC = re.compile(r"\s+(tools?|platforms?|technologies|technology|software|systems?|solutions?)$", re.I)


def _clean_subject(subj: str) -> str:
    subj = re.sub(r"\b(do you have|years?|of|professional|experience|total|relevant|any|the)\b", " ", subj, flags=re.I)
    subj = re.sub(r"\s+", " ", subj).strip(" -")
    return _TRAILING_GENERIC.sub("", subj)


def subject_of(label: str) -> str:
    """'years of professional cybersecurity experience' -> 'cybersecurity';
    'years of experience with Wireshark' -> 'Wireshark'; generic questions -> ''."""
    for rx in (_PRE_SUBJECT_RE, _SUBJECT_RE):
        m = rx.search(label)
        if m:
            subj = _clean_subject(m.group("s"))
            if subj:
                return subj
    return ""


# ------------------------------------------------------------------ option mapping

YES = {"yes", "y", "true", "i am", "i do", "i will", "i have"}
NO = {"no", "n", "false", "i am not", "i do not", "i don't", "i will not", "i have not"}


def _canon(s: str) -> str:
    return re.sub(r"[^a-z0-9+ ]", "", s.lower()).strip()


def choose_option(value: Any, options: list[str]) -> str | None:
    """Map a grounded value onto one of the form's options, or None if ambiguous."""
    if not options:
        return None
    v = _canon(str(value))
    opts = [(o, _canon(o)) for o in options]
    for o, c in opts:
        if c == v:
            return o
    if v in {"yes", "no"}:
        target = YES if v == "yes" else NO
        hits = [o for o, c in opts if c in target or c.split(" ")[0] == v]
        if len(hits) == 1:
            return hits[0]
        hits = [o for o, c in opts if c.startswith(v + " ")]
        return hits[0] if len(hits) == 1 else None
    # numeric value against ranges ("0-1 years", "3+ years", "Less than 1 year")
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = None
    if num is not None:
        for o, c in opts:
            m = re.match(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", c)
            if m and float(m.group(1)) <= num <= float(m.group(2)):
                return o
            m = re.match(r"(\d+(?:\.\d+)?)\s*\+|(?:more than|over|at least)\s*(\d+(?:\.\d+)?)", c)
            if m and num >= float(m.group(1) or m.group(2)):
                return o
            m = re.match(r"(?:less than|under|fewer than)\s*(\d+(?:\.\d+)?)", c)
            if m and num < float(m.group(1)):
                return o
            if c in {"none", "0", "no experience"} and num == 0:
                return o
        return None
    hits = [o for o, c in opts if v and (v in c or c in v) and len(c) > 1]
    return hits[0] if len(hits) == 1 else None


# ------------------------------------------------------------------ answering


@dataclass
class JobContext:
    company: str | None
    title: str
    location: str | None
    description: str | None


class AnswerEngine:
    def __init__(self, kb: KnowledgeBase, rules: Rules, job: JobContext, narrative_fn=None):
        self.kb = kb
        self.rules = rules
        self.job = job
        self.narrative_fn = narrative_fn  # callable(question, kb, job) -> Answer

    def answer(self, f: FormField) -> Answer:
        intent = "cv_upload" if f.field_type == "file" and not re.search(r"cover", f.label, re.I) else classify(f.label)
        if f.field_type == "file" and intent != "cv_upload":
            return unknown(intent, "Only the CV file upload is supported; other documents are NOT SUPPORTED")
        a = self._answer_intent(intent, f)
        return self._fit_to_field(a, f)

    # -- per intent
    def _answer_intent(self, intent: str, f: FormField) -> Answer:
        kb = self.kb
        if intent == "cv_upload":
            return Answer("__ACTIVE_CV__", "ANSWERED", "high", intent, sources=["cv_versions"], basis="Active CV version")
        if intent in {"first_name", "last_name", "full_name", "preferred_name"}:
            ref = kb.get("identity", intent)
            if not ref.known and intent in {"first_name", "last_name"}:
                full = kb.get("identity", "full_name")
                if full.known and len(full.value.split()) >= 2:
                    parts = full.value.split()
                    val = parts[0] if intent == "first_name" else " ".join(parts[1:])
                    return from_ref(intent, full, val, "Split from verified full name")
            if not ref.known and intent == "preferred_name":
                return from_ref(intent, kb.get("identity", "first_name"))
            return from_ref(intent, ref)
        if intent in {"email", "phone", "linkedin_url", "github_url", "portfolio_url", "city", "address", "postal_code"}:
            key = {"address": "address_line"}.get(intent, intent)
            return from_ref(intent, kb.get("contact", key))
        if intent == "country":
            return from_ref(intent, kb.get("contact", "country"))
        if intent == "nationality":
            return from_ref(intent, kb.get("identity", "nationality"))
        if intent in {"work_authorization", "sponsorship"}:
            country = find_country(f.label) or find_country(self.job.location)
            if not country:
                return unknown(intent, "Country of the question could not be determined")
            key = ("authorized:" if intent == "work_authorization" else "requires_sponsorship:") + country
            return from_ref(intent, kb.get("work_authorization", key), basis=f"Verified {key}")
        if intent == "relocation":
            return from_ref(intent, kb.get("availability", "willing_to_relocate"))
        if intent == "notice_period":
            ref = kb.get("availability", "notice_period")
            return from_ref(intent, ref if ref.known else kb.get("availability", "earliest_start_date"))
        if intent in {"current_salary", "expected_salary"}:
            return from_ref(intent, kb.get("compensation", intent))
        if intent == "years_experience":
            subj = subject_of(f.label)
            if norm(subj) in _GENERIC_SUBJECTS:
                return from_ref(intent, kb.professional_years())
            return from_ref(intent, kb.skill_professional_years(subj), basis=f"Professional years with {subj}")
        if intent == "has_experience":
            subj = subject_of(f.label)
            if not subj:
                return unknown(intent, "Could not identify the skill being asked about")
            ref = kb.skill(subj)
            if ref.known:
                ctx = ref.value
                professional_q = bool(re.search(r"professional|commercial|production|work experience", f.label, re.I))
                if professional_q and ctx != "professional":
                    return from_ref(intent, ref, "no", f"{subj}: verified as {ctx} only, not professional")
                return from_ref(intent, ref, "yes", f"{subj}: verified ({ctx})")
            if self.rules.treat_unlisted_skills_as_no:
                return Answer("no", "ANSWERED", "medium", intent, sources=["rules.treat_unlisted_skills_as_no"],
                              basis=f"{subj} not in verified skills; rule treats unlisted skills as NO")
            return unknown(intent, f"{subj}: NOT VERIFIED")
        if intent == "education_level":
            eds = kb.education()
            degrees = [(e.get("degree"), e) for e in eds if e.get("degree")]
            if not degrees:
                return unknown(intent, "No verified education")
            deg, e = degrees[-1] if len(degrees) == 1 else max(degrees, key=lambda d: e_rank(d[0]))
            return Answer(deg, "ANSWERED", "high", intent, sources=["education"],
                          fact_ids=[x.id for x in e.fields.values()], basis="Highest verified degree")
        if intent == "institution":
            vals = [(e.get("institution"), e) for e in kb.education() if e.get("institution")]
            if len(vals) != 1:
                return unknown(intent, "Zero or several institutions verified; ambiguous")
            return Answer(vals[0][0], "ANSWERED", "high", intent, sources=["education"],
                          fact_ids=[x.id for x in vals[0][1].fields.values()])
        if intent == "graduation_year":
            vals = [(e.get("graduation_year"), e) for e in kb.education() if e.get("graduation_year")]
            if len(vals) != 1:
                return unknown(intent, "Zero or several graduation years verified; ambiguous")
            return Answer(vals[0][0], "ANSWERED", "high", intent, sources=["education"],
                          fact_ids=[x.id for x in vals[0][1].fields.values()])
        if intent in {"current_employer", "current_title"}:
            cur = [e for e in kb.employment() if (e.get("end_date") or "") == "present"]
            if len(cur) != 1:
                return unknown(intent, "No single verified current position")
            v = cur[0].get("employer" if intent == "current_employer" else "title")
            if not v:
                return unknown(intent, "Field not verified")
            return Answer(v, "ANSWERED", "high", intent, sources=["employment_history"],
                          fact_ids=[x.id for x in cur[0].fields.values()])
        if intent == "eeo":
            key = next((k for k in ("gender", "race", "ethnicity", "veteran", "disability", "pronoun", "sexual orientation")
                        if k in f.label.lower()), "eeo")
            ref = kb.get("eeo", key.replace(" ", "_"))
            if ref.known:
                return from_ref(intent, ref)
            if self.rules.eeo_decline_if_available:
                decline = [o for o in f.options if re.search(r"decline|prefer not|don.t wish|do not wish|not to (say|answer|disclose)", o, re.I)]
                if decline:
                    return Answer(decline[0], "ANSWERED", "high", intent, sources=["rules.eeo_decline_if_available"],
                                  basis="Candidate rule: decline voluntary self-identification")
            return unknown(intent, "Voluntary EEO answer not provided by candidate")
        if intent == "referral_source":
            if self.rules.referral_source_answer:
                return Answer(self.rules.referral_source_answer, "ANSWERED", "high", intent,
                              sources=["rules.referral_source_answer"])
            return unknown(intent, "No configured referral-source answer")
        if intent == "consent":
            if f.field_type in {"checkbox", "checkbox_group", "radio", "select"} and self.rules.accept_privacy_notices:
                return Answer(True, "ANSWERED", "high", intent, sources=["rules.accept_privacy_notices"],
                              basis="Candidate explicitly accepts employer privacy/data-processing notices")
            return unknown(intent, "Consent not granted in rules")
        if intent == "languages":
            langs = [f"{x.key}{' (' + x.value + ')' if x.value else ''}" for x in kb.category("language")]
            if not langs:
                return unknown(intent, "No verified languages")
            return Answer(", ".join(langs), "ANSWERED", "high", intent, sources=["languages"],
                          fact_ids=[x.id for x in kb.category("language")])
        if intent == "cover_letter":
            if not self.rules.generate_cover_letters or f.field_type == "file":
                return unknown(intent, "Cover letter generation disabled or file upload required")
            return self._narrative(f, intent)
        if intent == "narrative":
            return self._narrative(f, intent)
        return unknown(intent, "Question not understood; no grounded answer")

    def _narrative(self, f: FormField, intent: str) -> Answer:
        if self.narrative_fn is None:
            return unknown(intent, "Narrative answers need a configured AI provider (NOT CONFIGURED)")
        return self.narrative_fn(f, self.kb, self.job)

    # -- adapt a grounded value to the concrete field
    def _fit_to_field(self, a: Answer, f: FormField) -> Answer:
        if not a.usable:
            return a
        if f.field_type in {"select", "radio", "combobox"} and f.options:
            chosen = choose_option(a.value, f.options)
            if chosen is None:
                return Answer(None, "UNKNOWN", "none", a.intent, a.sources, a.fact_ids,
                              basis=f"Grounded value '{a.value}' does not map unambiguously to options {f.options[:10]}")
            a.value = chosen
        elif f.field_type == "checkbox":
            v = a.value
            if isinstance(v, str):
                c = _canon(v)
                if c in YES:
                    v = True
                elif c in NO:
                    v = False
                else:
                    return Answer(None, "UNKNOWN", "none", a.intent, a.sources, a.fact_ids,
                                  basis=f"Value '{a.value}' is not a yes/no answer for a checkbox")
            a.value = bool(v)
        elif f.field_type == "number":
            m = re.search(r"-?\d+(?:\.\d+)?", str(a.value))
            if not m:
                return Answer(None, "UNKNOWN", "none", a.intent, a.sources, a.fact_ids,
                              basis=f"Value '{a.value}' is not numeric")
            a.value = m.group(0)
        if isinstance(a.value, str) and f.max_length and len(a.value) > f.max_length:
            return Answer(None, "UNKNOWN", "none", a.intent, a.sources, a.fact_ids,
                          basis=f"Grounded answer longer than field limit {f.max_length}; not truncating silently")
        return a


_DEG_RANK = [
    (r"ph\.?d|doctor", 6), (r"master|m\.?sc|msc|mba|m\.?s\b|m\.?a\b|m\.?tech", 5),
    (r"bachelor|b\.?sc|bsc|b\.?s\b|b\.?a\b|b\.?e\b|b\.?tech", 4), (r"associate", 3), (r"diploma", 2),
    (r"high school|a[- ]level", 1),
]


def e_rank(degree: str | None) -> int:
    for rx, r in _DEG_RANK:
        if degree and re.search(rx, degree, re.I):
            return r
    return 0

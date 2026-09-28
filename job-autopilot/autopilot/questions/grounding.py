"""Grounding validation and AI narrative generation.

The validator is deliberately conservative: anything in an answer that cannot
be traced to a verified fact or to the job posting itself is treated as
potential fabrication and the answer is rejected.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..ai.providers import AIError, ProviderHandle, extract_json
from ..profile.knowledge import KnowledgeBase, norm
from .engine import Answer, FormField, JobContext

# Terms whose mention implies a skill/experience claim.
SKILL_VOCAB = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "sql", "postgresql", "mysql", "mongodb",
    "react", "angular", "vue", "node.js", "django", "flask", "fastapi", "spring", "kubernetes", "docker", "terraform",
    "ansible", "aws", "amazon web services", "azure", "google cloud", "linux", "windows server", "siem", "splunk",
    "qradar", "sentinel", "elastic", "wireshark", "nmap", "metasploit", "burp suite", "soc", "incident response",
    "threat hunting", "penetration testing", "vulnerability management", "firewall", "ids", "ips", "edr", "crowdstrike",
    "iso 27001", "nist", "pci dss", "gdpr", "machine learning", "deep learning", "tensorflow", "pytorch", "pandas",
    "excel", "power bi", "tableau", "salesforce", "sap", "jira", "agile", "scrum", "ccna", "cissp", "ceh", "oscp",
    "security+", "comptia", "itil", "pmp", "devops", "ci/cd", "git",
}
_STOP_CAPS = {
    "I", "I'm", "I've", "My", "The", "A", "An", "In", "At", "As", "With", "This", "That", "These", "Those", "During",
    "Through", "While", "Since", "My", "Our", "We", "It", "For", "And", "But", "Also", "Additionally", "Furthermore",
    "Moreover", "However", "Thank", "Dear", "Hiring", "Manager", "Team", "Sincerely", "Regards", "Best", "Yes", "No",
    "Currently", "Previously", "Recently", "Having", "Given", "Being", "When", "Where", "What", "Why", "How", "Which",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December", "English", "Arabic",
}
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", re.I)
_PRO_CLAIM_RE = re.compile(r"\b(professional experience|worked as|employed as|years of experience|in my (current|previous) role)\b", re.I)


def validate_text(text: str, kb: KnowledgeBase, job: JobContext, cited_ids: set[int] | None = None) -> dict[str, Any]:
    issues: list[str] = []
    facts_text = kb.all_text_values().lower()
    job_text = " ".join(filter(None, [job.company, job.title, job.location, job.description])).lower()
    usable_ids = {f.id for f in kb.usable}

    if cited_ids is not None:
        bad = cited_ids - usable_ids
        if bad:
            issues.append(f"Cites facts that are not verified or do not exist: {sorted(bad)}")

    # Numbers of years must equal a verified/derived figure.
    allowed_years: set[float] = set()
    py = kb.professional_years()
    if py.known:
        allowed_years.add(float(py.value))
    for f in kb.category("skill_years"):
        try:
            allowed_years.add(float(f.value))
        except (TypeError, ValueError):
            pass
    for m in _YEARS_RE.finditer(text):
        n = float(m.group(1))
        if n not in allowed_years:
            issues.append(f"Years figure '{m.group(0)}' is not a verified value")

    # Proper nouns (organisations, products, certificates) must appear in facts or the job posting.
    for sent in re.split(r"(?<=[.!?])\s+|\n", text):
        tokens = re.findall(r"\b[A-Z][A-Za-z0-9&+.#-]{1,}(?:\s+[A-Z][A-Za-z0-9&+.#-]+)*", sent)
        for i, tok in enumerate(tokens):
            words = [w for w in tok.split() if w not in _STOP_CAPS]
            if not words:
                continue
            phrase = " ".join(words).strip(".").lower()
            if phrase and phrase not in facts_text and phrase not in job_text:
                if not all(w.lower() in facts_text or w.lower() in job_text for w in words):
                    issues.append(f"Unverified name/term: '{' '.join(words)}'")

    # Skill mentions must be verified skills (mentioning the job's own requirements is not allowed either,
    # because in first person it reads as a claim).
    verified = kb.verified_skill_names()
    low = text.lower()
    for term in SKILL_VOCAB:
        if re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", low) and norm(term) not in verified and term not in facts_text:
            issues.append(f"Mentions skill '{term}' that is not verified")

    if _PRO_CLAIM_RE.search(text):
        pro = [e for e in kb.employment() if (e.get("employment_type") or "").lower() in
               {"full-time", "part-time", "contract", "freelance", "temporary", "self-employed"}]
        if not pro:
            issues.append("Claims professional experience but no professional employment is verified")

    return {"ok": not issues, "issues": sorted(set(issues))}


SYSTEM_PROMPT = """You draft answers to job application questions for a candidate.
Hard rules:
- Use ONLY the facts provided in CANDIDATE_FACTS. Never invent employers, titles, dates, certifications, skills,
  numbers, achievements or experience.
- Do not describe academic, internship or personal experience as professional experience.
- If the facts are insufficient to answer honestly, return {"answer": null, "insufficient": true}.
- Do not mention skills from the job posting unless they are in CANDIDATE_FACTS.
- Return JSON only: {"answer": "...", "claims": [{"text": "<claim>", "fact_ids": [<ids>]}], "insufficient": false}
  Every factual claim must list the fact ids that support it."""


def make_narrative_fn(provider: ProviderHandle):
    def narrative(f: FormField, kb: KnowledgeBase, job: JobContext) -> Answer:
        intent = "narrative"
        payload = {
            "QUESTION": f.label,
            "MAX_CHARACTERS": f.max_length or 1500,
            "JOB": {"company": job.company, "title": job.title, "location": job.location,
                    "description": (job.description or "")[:6000]},
            "CANDIDATE_FACTS": kb.facts_for_prompt(),
        }
        try:
            raw = provider.complete(SYSTEM_PROMPT, json.dumps(payload, default=str), contains_candidate_data=True)
            data = extract_json(raw)
        except AIError as e:
            return Answer(None, "UNKNOWN", "none", intent, basis=f"AI unavailable: {e}")
        if data.get("insufficient") or not data.get("answer"):
            return Answer(None, "UNKNOWN", "none", intent, basis="AI reported insufficient verified facts")
        text = str(data["answer"]).strip()
        cited: set[int] = set()
        for c in data.get("claims") or []:
            for i in c.get("fact_ids") or []:
                try:
                    cited.add(int(i))
                except (TypeError, ValueError):
                    pass
        v = validate_text(text, kb, job, cited)
        if not cited:
            v["ok"] = False
            v["issues"] = v.get("issues", []) + ["No supporting fact ids cited"]
        if not v["ok"]:
            return Answer(text, "REJECTED", "none", intent, sources=["ai:" + provider.settings.provider],
                          fact_ids=sorted(cited), basis="Grounding validation failed", validation=v,
                          fabricated_information_detected=True)
        return Answer(text, "ANSWERED", "medium", intent,
                      sources=["ai:" + provider.settings.provider, "candidate_facts"], fact_ids=sorted(cited),
                      basis="AI draft grounded in cited verified facts", validation=v)

    return narrative

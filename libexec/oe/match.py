# Copyright 2026 Mohsen Seyedkazemi Ardebili
# SPDX-License-Identifier: Apache-2.0
# Part of opportunity-engine — https://github.com/MSKazemi/opportunity-engine
"""Match a profile against a posting the way the posting will actually be read.

Hiring is screened by two machines in sequence, and they want different things:

  Stage 1 — the parser gate. A classic applicant tracking system parses the
  document and scores literal coverage of the stated requirements. It does not
  understand you; it counts. Losing here means nothing downstream ever runs.

  Stage 2 — the ranking layer. A language model reads what survived, summarises
  it and ranks it. It is not counting terms — it is looking for whether a claim
  is *supported*. "Kubernetes" in a skills list and "operated production
  Kubernetes for a 400-node cluster" score identically at stage 1 and nothing
  alike at stage 2.

So this module reports both, separately, and never blends them into a single
number that hides which one you are failing.

Three things it will not do:

  - It will not invent evidence. Every point of the evidence score is traced to
    a line in the user's own profile, printed with it.
  - It will not round a knockout away. A hard requirement the user cannot meet
    (a clearance, a language, a residency rule) sets the verdict to knocked-out
    regardless of how well everything else scores. A 0.9 fit on a role you are
    barred from is not a 0.9.
  - It will not pretend the number is precise. The bands are coarse on purpose.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from . import paths, profile as profile_mod

WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#.\-/]*")
YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|jahre|yrs?)\b", re.I)
BULLET_RE = re.compile(r"^\s*(?:[-*•·–—▪]|\d+[.)])\s+")

#: Verdict bands. Deliberately coarse — a two-decimal fit score would imply a
#: precision that no amount of keyword counting earns.
BANDS = ((0.70, "strong"), (0.45, "plausible"), (0.0, "weak"))

EVIDENCE_WEIGHT = {"proven": 1.0, "claimed": 0.5, "absent": 0.0}

#: Below this many recognised requirement terms, a posting is not scored at all.
#: Without this floor a posting mentioning "python" once scores 1/1 = 100% and
#: outranks a role matching fifteen terms out of twenty. A ratio with a
#: denominator of one is not a measurement, and reporting it as one is worse
#: than admitting the posting did not say enough to judge.
MIN_TERMS_TO_SCORE = 4

#: Overlap at which breadth stops adding confidence. Matching 8 distinct
#: requirements says as much as matching 20.
DEPTH_SATURATION = 8

#: What fit is made of. Coverage is what the parser gate scores, evidence is what
#: the ranking layer scores, depth stops a thin match from looking like a broad
#: one, and alignment stops a term coincidence in an unrelated role from
#: outranking the job you actually do.
WEIGHTS = {"coverage": 0.30, "evidence": 0.30, "depth": 0.20, "alignment": 0.20}


def lexicon() -> dict[str, Any]:
    return json.loads((paths.DATA / "lexicon.json").read_text())


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def _contains_term(haystack: str, term: str) -> bool:
    """Whole-term containment, so 'go' does not match 'algorithm'."""
    if not term:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


# --------------------------------------------------------------------------- #
# reading the posting
# --------------------------------------------------------------------------- #

def split_requirements(text: str, lex: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(required, nice-to-have) bullet lines.

    A posting's tail is where the disqualifiers hide — the language demand and
    the clearance are rarely in the headline. Both halves are read; the split
    matters because scoring a 'nice to have' as a hard requirement makes every
    role look like a bad fit.
    """
    required: list[str] = []
    optional: list[str] = []
    bucket: list[str] | None = None

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower().rstrip(":")
        if any(h in low for h in lex["nice_to_have_headings"]) and len(low) < 90:
            bucket = optional
            continue
        if any(h in low for h in lex["requirement_headings"]) and len(low) < 90:
            bucket = required
            continue
        if bucket is not None and BULLET_RE.match(raw_line):
            bucket.append(BULLET_RE.sub("", line).strip())

    if not required and not optional:
        # No recognisable requirements section: fall back to every bullet, marked
        # required. Reported as low confidence by the caller.
        required = [BULLET_RE.sub("", l.strip()).strip()
                    for l in (text or "").splitlines() if BULLET_RE.match(l)]
    return required, optional


def extract_requirements(posting: dict[str, Any], lex: dict[str, Any] | None = None
                         ) -> dict[str, Any]:
    """Everything the posting demands, in a form that can be checked."""
    lex = lex or lexicon()
    body = " \n".join(str(posting.get(k) or "") for k in ("title", "description", "tags"))
    flat = _norm(body)
    required_lines, optional_lines = split_requirements(posting.get("description") or "", lex)

    all_terms = {term for group in lex["groups"].values() for term in group}
    demanded = sorted({t for t in all_terms if _contains_term(flat, t)})

    required_terms = sorted({t for t in all_terms
                             if any(_contains_term(_norm(line), t) for line in required_lines)})
    optional_terms = sorted({t for t in all_terms
                             if any(_contains_term(_norm(line), t) for line in optional_lines)})
    if not required_terms:
        required_terms = demanded          # nothing parsed as a section; treat all as required

    years = [int(m.group(1)) for m in YEARS_RE.finditer(body)]
    degrees = [name for name, forms in lex["degree"].items()
               if any(_contains_term(flat, f) for f in forms)]
    seniority = [name for name, forms in lex["seniority"].items()
                 if any(_contains_term(_norm(posting.get("title") or ""), f) for f in forms)]

    languages = {}
    for name, forms in lex["languages"].items():
        for form in forms:
            hit = re.search(r"(.{0,60})(?<![a-z])" + re.escape(form) + r"(?![a-z])(.{0,60})",
                            flat)
            if hit:
                window = hit.group(0)
                level = next((lv for lv in lex["language_levels"] if lv in window), "")
                languages[name] = level or "unspecified"
                break

    knockouts = {}
    for kind, signals in lex["knockout_signals"].items():
        found = [s for s in signals if s in flat]
        if found:
            knockouts[kind] = found

    return {
        "required_terms": required_terms,
        "optional_terms": [t for t in optional_terms if t not in required_terms],
        "all_mentioned_terms": demanded,
        "required_lines": required_lines,
        "optional_lines": optional_lines,
        "years_demanded": max(years) if years else None,
        "degrees": degrees,
        "seniority": seniority,
        "languages": languages,
        "knockout_signals": knockouts,
        "confidence": "high" if (required_lines or optional_lines) else "low",
    }


# --------------------------------------------------------------------------- #
# the two stages
# --------------------------------------------------------------------------- #

def stage1_parser(profile: dict[str, Any], reqs: dict[str, Any]) -> dict[str, Any]:
    """Literal coverage — what a parsing ATS actually scores."""
    have = profile_mod.skill_terms(profile)
    haystack = " ".join(have)
    covered, missing = [], []
    for term in reqs["required_terms"]:
        if term in have or _contains_term(haystack, term):
            covered.append(term)
        else:
            missing.append(term)
    total = len(covered) + len(missing)
    return {
        "covered": covered,
        "missing": missing,
        "score": (len(covered) / total) if total else None,
        "note": "no requirement terms were recognised in this posting" if not total else "",
    }


def _clip(text: str, limit: int) -> str:
    """Trim to a word boundary. A line cut mid-word reads as broken, and this
    text is quoted verbatim into a letter a person sends."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit * 0.6 else cut).rstrip(" ,;:-") + "…"


def stage2_evidence(profile: dict[str, Any], reqs: dict[str, Any]) -> dict[str, Any]:
    """Is each requirement *supported*, and by what line of the profile.

    proven  — a concrete instance exists in a role, project or publication
    claimed — the term is in the skills list but nothing describes doing it
    absent  — the profile does not support it at all
    """
    corpus = profile_mod.evidence_corpus(profile)
    listed = profile_mod.skill_terms(profile)
    # Skills arrive grouped ("AI, Machine Learning, and Agentic Systems"), so a
    # set-membership test misses every term inside a group name and reports a
    # specialist's core skill as absent. Match against the joined text as well.
    listed_text = " ; ".join(listed)
    graded: list[dict[str, Any]] = []

    for term in reqs["required_terms"]:
        hit = next(((where, text) for where, text in corpus
                    if _contains_term(_norm(text), term)), None)
        if hit:
            graded.append({"term": term, "grade": "proven",
                           "where": hit[0], "evidence": _clip(hit[1], 240)})
        elif term in listed or _contains_term(listed_text, term):
            graded.append({"term": term, "grade": "claimed", "where": "skills list",
                           "evidence": ""})
        else:
            graded.append({"term": term, "grade": "absent", "where": "", "evidence": ""})

    if graded:
        score = sum(EVIDENCE_WEIGHT[g["grade"]] for g in graded) / len(graded)
    else:
        score = None
    return {"graded": graded, "score": score,
            "proven": sum(1 for g in graded if g["grade"] == "proven"),
            "claimed": sum(1 for g in graded if g["grade"] == "claimed"),
            "absent": sum(1 for g in graded if g["grade"] == "absent")}


def knockouts(profile: dict[str, Any], reqs: dict[str, Any],
              constraints: dict[str, Any]) -> list[dict[str, str]]:
    """Hard barriers. These are not penalties — they end the evaluation.

    Constraints are the user's own, from workspace config. Nothing here is
    hardcoded about any person: the tool has no opinion about which sectors or
    countries someone will work in, only about honouring what they declared.
    """
    blocking: list[dict[str, str]] = []

    for kind, signals in reqs["knockout_signals"].items():
        if kind in set(constraints.get("exclude_signals", [])):
            blocking.append({"kind": kind, "why": f"posting mentions {', '.join(signals[:3])}",
                             "source": "your exclude_signals"})

    spoken = {k.lower() for k in (constraints.get("languages") or [])}
    for language, level in reqs["languages"].items():
        if language == "english":
            continue
        if language not in spoken and level not in ("", "unspecified"):
            blocking.append({"kind": "language",
                             "why": f"needs {language} ({level}); you did not list it",
                             "source": "your languages"})

    excluded_countries = {c.lower() for c in (constraints.get("exclude_countries") or [])}
    country = _norm(f"{reqs.get('location', '')}")
    for excluded in excluded_countries:
        if excluded and excluded in country:
            blocking.append({"kind": "location", "why": f"location matches {excluded}",
                             "source": "your exclude_countries"})

    if constraints.get("no_clearance", True) and "clearance" in reqs["knockout_signals"]:
        blocking.append({"kind": "clearance",
                         "why": "a security clearance is required",
                         "source": "your no_clearance setting"})
    return blocking


#: The formats these feeds actually use. RFC-822 from RSS, ISO-8601 from the JSON
#: APIs with and without a timezone, plain dates, and epoch seconds from RemoteOK.
DATE_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
)


def parse_date(text: str) -> datetime | None:
    """Naive UTC datetime from whatever a feed used, or None.

    Returning None is a real answer here: pretending an unparsed date is "today"
    would make every stale posting look urgent, which is precisely the mistake
    that wastes an application window.
    """
    text = (text or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            when = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return when.astimezone(timezone.utc).replace(tzinfo=None) if when.tzinfo else when
    try:                                    # ISO with a trailing Z, and similar
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return when.astimezone(timezone.utc).replace(tzinfo=None) if when.tzinfo else when
    except ValueError:
        pass
    try:                                    # epoch seconds
        value = float(text)
        if 10**8 < value < 10**11:
            return datetime.utcfromtimestamp(value)
    except (ValueError, OverflowError, OSError):
        pass
    return None


def freshness(posted_at: str | None) -> tuple[float, str]:
    """How much the clock has already cost this application.

    Early applicants get materially more interviews than late ones, and a
    freelance posting decays in hours rather than days. This is a *ranking*
    multiplier, never folded into fit — a role you fit perfectly is still a good
    fit when it is old, it is just a worse use of the next hour.
    """
    if not posted_at:
        return 1.0, "age unknown"
    when = parse_date(str(posted_at))
    if when is None:
        return 1.0, "age unparseable"
    days = max((datetime.utcnow() - when).days, 0)
    if days <= 2:
        return 1.0, f"{days}d old — apply now, this is the window"
    if days <= 7:
        return 0.85, f"{days}d old — still worth it"
    if days <= 21:
        return 0.6, f"{days}d old — the early readers have been through it"
    return 0.35, f"{days}d old — likely shortlisted already"


STOPWORDS = {"senior", "junior", "staff", "lead", "principal", "the", "and", "for", "with",
             "remote", "engineer", "manager", "specialist", "developer", "part", "time",
             "full", "chief", "head", "director", "officer", "consultant", "expert"}


def role_vocabulary(profile: dict[str, Any]) -> set[str]:
    """The words that describe what this person does for a living."""
    words: set[str] = set()
    for text in [profile_mod.dig(profile, "basics.label") or ""] + \
                [j.get("position", "") for j in profile.get("work", [])] + \
                [s.get("name", "") for s in profile.get("skills", [])]:
        words |= {w for w in WORD_RE.findall(_norm(text)) if len(w) > 3}
    return words - STOPWORDS


def title_alignment(profile: dict[str, Any], posting: dict[str, Any]) -> tuple[float, str]:
    """Is this even the kind of work you do?

    A posting can share a term with a profile by coincidence — "python" appears
    in an account-management ad that wants someone to talk to developers. Without
    this factor, that coincidence scores the same as a genuine domain match, and
    the top of the ranked list fills with roles the user would never take.
    """
    title_words = {w for w in WORD_RE.findall(_norm(posting.get("title") or ""))
                   if len(w) > 3} - STOPWORDS
    if not title_words:
        return 0.5, "the posting has no usable title to compare"
    mine = role_vocabulary(profile)
    shared = title_words & mine
    if shared:
        return min(1.0, 0.5 + 0.25 * len(shared)), f"title shares {', '.join(sorted(shared))}"
    return 0.0, "nothing in the title matches the work you describe doing"


def defensible_sentence(profile: dict[str, Any], posting: dict[str, Any]) -> dict[str, Any]:
    """Can a screener say in one clause what you are, for this role?

    An accountable reader picks what is easiest to justify to someone else. A
    candidate who cannot be categorised gives them no such sentence, and that
    absence is the rejection — being unusual is punished here and nowhere else.
    """
    label = _norm(profile_mod.dig(profile, "basics.label") or "")
    title = _norm(posting.get("title") or "")
    if not label:
        return {"ok": False,
                "note": "your profile has no `basics.label` — the screener has no category to "
                        "put you in, and a credential is not a category"}
    overlap = {w for w in WORD_RE.findall(label)} & {w for w in WORD_RE.findall(title)}
    overlap = {w for w in overlap if len(w) > 3}
    if overlap:
        return {"ok": True, "note": f"your label and the title share: {', '.join(sorted(overlap))}"}
    return {"ok": False,
            "note": f"your label ({label!r}) shares no term with the title ({title!r}) — "
                    f"consider whether the CV for this one should lead with their category"}


def match(profile: dict[str, Any], posting: dict[str, Any],
          constraints: dict[str, Any] | None = None, lex: dict[str, Any] | None = None
          ) -> dict[str, Any]:
    constraints = constraints or {}
    reqs = extract_requirements(posting, lex)
    reqs["location"] = posting.get("location", "")

    blocked = knockouts(profile, reqs, constraints)
    stage1 = stage1_parser(profile, reqs)
    stage2 = stage2_evidence(profile, reqs)
    fresh, fresh_note = freshness(posting.get("posted_at"))
    align, align_note = title_alignment(profile, posting)

    recognised = len(reqs["required_terms"])
    components: dict[str, float] = {}
    if recognised < MIN_TERMS_TO_SCORE or stage1["score"] is None or stage2["score"] is None:
        fit = None
        unscorable_note = (
            f"only {recognised} requirement term(s) were recognised — too few to judge. "
            f"This usually means the posting is prose without a requirements list, not that "
            f"it is a bad fit. Read it yourself: {posting.get('url', '')}")
    else:
        unscorable_note = ""
        components = {
            "coverage": stage1["score"],
            "evidence": stage2["score"],
            "depth": min(1.0, len(stage1["covered"]) / DEPTH_SATURATION),
            "alignment": align,
        }
        fit = sum(WEIGHTS[k] * v for k, v in components.items())

    if blocked:
        verdict = "knocked-out"
    elif fit is None:
        verdict = "unscorable"
    else:
        verdict = next(name for floor, name in BANDS if fit >= floor)

    gaps = [g["term"] for g in stage2["graded"] if g["grade"] == "absent"]
    weak = [g["term"] for g in stage2["graded"] if g["grade"] == "claimed"]

    return {
        "opportunity": posting.get("id", ""),
        "title": posting.get("title", ""),
        "org": posting.get("org", ""),
        "url": posting.get("url", ""),
        "verdict": verdict,
        "fit": fit,
        "components": components,
        "unscorable_note": unscorable_note,
        "alignment": {"factor": align, "note": align_note},
        "priority": None if fit is None else round(fit * fresh, 4),
        "freshness": {"factor": fresh, "note": fresh_note},
        "knockouts": blocked,
        "stage1_parser": stage1,
        "stage2_evidence": stage2,
        "requirements": reqs,
        "gaps": gaps,
        "unsupported_claims": weak,
        "defensible_sentence": defensible_sentence(profile, posting),
        "advice": ([unscorable_note] if unscorable_note else
                   _advice(verdict, stage1, stage2, gaps, weak, fresh_note, align_note)),
    }


def _advice(verdict: str, stage1: dict, stage2: dict, gaps: list[str],
            weak: list[str], fresh_note: str, align_note: str = "") -> list[str]:
    out: list[str] = []
    if verdict == "knocked-out":
        return ["Do not spend time here — a hard requirement blocks it. "
                "The block is listed above; if it is wrong, fix your constraints."]
    if stage1["score"] is not None and stage1["score"] < 0.5:
        out.append(f"The parser gate is the problem, not your experience: "
                   f"{len(stage1['missing'])} required term(s) never appear in your profile. "
                   f"If you genuinely have them, they belong in the CV in the words the "
                   f"posting uses.")
    if weak:
        out.append(f"Listed but never demonstrated: {', '.join(weak[:6])}. "
                   f"A ranking layer treats a skills-list entry and a described instance very "
                   f"differently — add one concrete instance for the ones that matter here.")
    if gaps:
        out.append(f"Genuinely absent: {', '.join(gaps[:6])}. "
                   f"Do not add these to your profile to raise the score. Either they are a "
                   f"real gap, or the posting is asking for something you do under another name.")
    if align_note.startswith("nothing in the title"):
        out.append("This is not the kind of work your profile describes. Terms can "
                   "overlap by coincidence; that is what the alignment factor is for.")
    out.append(f"Timing: {fresh_note}.")
    return out

# Copyright 2026 Mohsen Seyedkazemi Ardebili
# SPDX-License-Identifier: Apache-2.0
# Part of opportunity-engine — https://github.com/MSKazemi/opportunity-engine
"""The profile — one file that every other command reads.

It is [JSON Resume](https://jsonresume.org) plus one extension object,
`application`, which holds the answers forms demand but a résumé has no place
for: work authorization, notice period, salary expectation, language levels,
screening answers. That object exists for a single reason — **nothing the user
has already told us should ever be asked twice.** A form field that cannot be
filled from here is a gap in the profile, and gaps are reported, never guessed.

The profile is the only place a factual claim may come from. Every downstream
command treats it as the boundary of what may be said about a person.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from . import paths

SCHEMA_URL = "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json"

#: Sections a JSON Resume may carry. Anything else is kept but not interpreted.
RESUME_SECTIONS = ("basics", "work", "volunteer", "education", "awards", "certificates",
                   "publications", "skills", "languages", "interests", "references",
                   "projects", "meta")

#: What `application` is for. Each key answers a class of form field that would
#: otherwise interrupt a run to ask a human something they already know.
APPLICATION_KEYS = ("personal", "workAuthorization", "preferences", "compensation",
                    "demographics", "languages", "skillYearsOfExperience",
                    "educationSummary", "screeningAnswers", "documents", "rules")

#: Fields without which an application cannot honestly be completed.
REQUIRED_FOR_APPLYING = {
    "basics.name": "your name",
    "basics.email": "a contact email",
    "work": "at least one role, so claims have somewhere to come from",
    "skills": "your skills, so a posting can be matched against something",
    "application.workAuthorization.summary": "where you may legally work — asked on nearly every form",
    "application.preferences.noticePeriod": "your notice period",
    "application.compensation.currency": "the currency you quote in",
}


def empty() -> dict[str, Any]:
    return {
        "$schema": SCHEMA_URL,
        "basics": {"name": "", "email": "", "profiles": []},
        "work": [], "education": [], "skills": [], "projects": [], "publications": [],
        "languages": [], "certificates": [],
        "application": {key: {} for key in APPLICATION_KEYS},
        "meta": {"generator": "opportunity-engine", "sources": []},
    }


def load(path: Path | None = None) -> dict[str, Any] | None:
    target = path or paths.profile_path()
    if not target.exists():
        return None
    return json.loads(target.read_text())


def save(profile: dict[str, Any], path: Path | None = None) -> Path:
    target = path or paths.profile_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    return target


def dig(profile: dict[str, Any], dotted: str) -> Any:
    node: Any = profile
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def merge(base: dict[str, Any], incoming: dict[str, Any], source: str = "") -> dict[str, Any]:
    """Fold a newly-read document into the profile.

    Conservative on purpose: **an existing value is never overwritten.** A CV
    read second cannot silently replace an answer the user typed, and two CVs
    disagreeing about a date produces a reported conflict rather than a coin
    flip. New keys are added, lists are extended without duplicating, and every
    contributing document is recorded in `meta.sources`.
    """
    result = json.loads(json.dumps(base))
    conflicts: list[str] = []

    def fold(dst: dict[str, Any], src: dict[str, Any], trail: str) -> None:
        for key, value in src.items():
            where = f"{trail}.{key}" if trail else key
            if key not in dst or dst[key] in ("", None, [], {}):
                dst[key] = value
            elif isinstance(dst[key], dict) and isinstance(value, dict):
                fold(dst[key], value, where)
            elif isinstance(dst[key], list) and isinstance(value, list):
                known = {json.dumps(item, sort_keys=True) for item in dst[key]}
                for item in value:
                    if json.dumps(item, sort_keys=True) not in known:
                        dst[key].append(item)
            elif dst[key] != value:
                conflicts.append(f"{where}: kept {dst[key]!r}, ignored {value!r}")

    fold(result, incoming, "")
    meta = result.setdefault("meta", {})
    if source:
        meta.setdefault("sources", []).append(source)
    if conflicts:
        meta.setdefault("conflicts", []).extend(conflicts)
    return result


def gaps(profile: dict[str, Any]) -> list[tuple[str, str]]:
    """What is missing before an application could be completed honestly."""
    missing = []
    for field, why in REQUIRED_FOR_APPLYING.items():
        value = dig(profile, field)
        if value in (None, "", [], {}):
            missing.append((field, why))
    return missing


def skill_terms(profile: dict[str, Any]) -> set[str]:
    """Every term the profile lets us claim, lowercased.

    Drawn from skills keywords, job titles, project names and publication
    keywords — the places a real capability leaves a trace. Nothing here is
    invented: if a term is not in the profile, the tool cannot say it.
    """
    terms: set[str] = set()
    for skill in profile.get("skills", []):
        if skill.get("name"):
            terms.add(skill["name"].lower())
        terms.update(k.lower() for k in skill.get("keywords", []) if k)
    for job in profile.get("work", []):
        if job.get("position"):
            terms.add(job["position"].lower())
    for project in profile.get("projects", []):
        if project.get("name"):
            terms.add(project["name"].lower())
        terms.update(k.lower() for k in project.get("keywords", []) if k)
    for key in (profile.get("application", {}).get("skillYearsOfExperience") or {}):
        if key != "note":
            terms.add(key.replace("_", " ").lower())
    return {t for t in terms if len(t) > 1}


def evidence_corpus(profile: dict[str, Any]) -> list[tuple[str, str]]:
    """(where, text) pairs a claim can be traced back to.

    This is what separates "I know Kubernetes" from "I ran Kubernetes in
    production at X" — the second is checkable, and checkability is what earns
    belief from a human reader and a ranking layer alike.
    """
    corpus: list[tuple[str, str]] = []
    for job in profile.get("work", []):
        where = f"{job.get('position', '?')} at {job.get('name', '?')}"
        if job.get("summary"):
            corpus.append((where, job["summary"]))
        for highlight in job.get("highlights", []) or []:
            corpus.append((where, highlight))
    for project in profile.get("projects", []):
        where = f"project {project.get('name', '?')}"
        if project.get("description"):
            corpus.append((where, project["description"]))
        for highlight in project.get("highlights", []) or []:
            corpus.append((where, highlight))
    for pub in _publications(profile):
        title = pub.get("name") or pub.get("title") or ""
        if title:
            corpus.append((f"publication ({pub.get('publisher') or pub.get('venue') or 'n/a'})", title))
    for edu in profile.get("education", []):
        bits = " ".join(str(edu.get(k, "")) for k in ("studyType", "area", "researchTopic"))
        if bits.strip():
            corpus.append((f"education at {edu.get('institution', '?')}", bits))
    return corpus


#: Buckets that are NOT publications yet. A submitted manuscript is not a
#: publication, and letting one into the evidence corpus turns "under review"
#: into a claim on a real application.
UNPUBLISHED_BUCKETS = ("underreview", "under_review", "inpreparation", "in_preparation",
                       "submitted", "draft", "planned", "rejected")


def _publications(profile: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Every published item, however deeply the export nested them.

    Real profiles split these by venue type and then by status
    (`journals.publishedOrAccepted`, `conferences.underReview`, …). Walk it, and
    drop any bucket whose name says the work is not out yet.
    """
    out: list[dict[str, Any]] = []

    def walk(node: Any, bucket: str = "") -> None:
        if isinstance(node, list):
            out.extend(v for v in node
                       if isinstance(v, dict) and bucket not in UNPUBLISHED_BUCKETS)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key.startswith("_"):
                    continue
                walk(value, key.lower().replace(" ", ""))

    walk(profile.get("publications"))
    return out


def summarise(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": dig(profile, "basics.name") or "(unnamed)",
        "label": dig(profile, "basics.label") or "",
        "roles": len(profile.get("work", [])),
        "skills": len(profile.get("skills", [])),
        "projects": len(profile.get("projects", [])),
        "publications": len(list(_publications(profile))),
        "skill_terms": len(skill_terms(profile)),
        "evidence_items": len(evidence_corpus(profile)),
        "sources": profile.get("meta", {}).get("sources", []),
        "conflicts": profile.get("meta", {}).get("conflicts", []),
        "gaps": gaps(profile),
    }

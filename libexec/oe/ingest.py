# Copyright 2026 Mohsen Seyedkazemi Ardebili
# SPDX-License-Identifier: Apache-2.0
# Part of opportunity-engine — https://github.com/MSKazemi/opportunity-engine
"""Turn whatever the user already has into one profile.

The honest position, stated up front because it shapes everything here: a PDF
CV is a *rendering*, and rendering is lossy. Nothing in this module guesses at a
structure it cannot see. It extracts what can be extracted deterministically —
JSON Resume as-is, contact details, section text, links — records the raw text
as evidence, and then **reports what it could not determine** so a human or an
agent can fill it in.

The alternative, a regex that infers employment dates from prose and is wrong
one time in ten, would put fabricated history into the one file this tool treats
as the boundary of truth. That trade is never worth it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import profile as profile_mod

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
URL_RE = re.compile(r"https?://[^\s<>)\]},;\"']+")
PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(\d{1,4}\)[\s.-]?)?\d[\d\s.-]{7,}\d")
ORCID_RE = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")

KNOWN_PROFILES = {
    "github.com": "GitHub", "gitlab.com": "GitLab", "linkedin.com": "LinkedIn",
    "orcid.org": "ORCID", "scholar.google": "Google Scholar", "twitter.com": "X",
    "x.com": "X", "stackoverflow.com": "Stack Overflow", "huggingface.co": "Hugging Face",
}


class IngestError(Exception):
    pass


# --------------------------------------------------------------------------- #
# readers
# --------------------------------------------------------------------------- #

def read_text(path: Path) -> str:
    """Plain text out of any supported document."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(path)
    if suffix in (".tex", ".latex"):
        return _latex_text(path.read_text(errors="replace"))
    return path.read_text(errors="replace")


def _pdf_text(path: Path) -> str:
    """pdftotext if present; otherwise say so rather than return nothing."""
    if not shutil.which("pdftotext"):
        raise IngestError(
            "reading a PDF needs `pdftotext` (poppler-utils). Install it, or pass the "
            "same CV as .tex, .md or .txt — the text is what matters, not the layout")
    out = subprocess.run(["pdftotext", "-layout", "-nopgbrk", str(path), "-"],
                         capture_output=True, timeout=120)
    if out.returncode != 0:
        raise IngestError(f"pdftotext failed: {out.stderr.decode('utf-8', 'replace')[:200]}")
    return out.stdout.decode("utf-8", "replace")


LATEX_COMMENT = re.compile(r"(?<!\\)%.*$", re.M)
LATEX_COMMAND = re.compile(r"\\[a-zA-Z@]+\s*(\[[^\]]*\])?")


def _latex_text(raw: str) -> str:
    """Readable text out of a .tex source.

    Deliberately crude: strip comments, unwrap braces, drop commands. The goal is
    a searchable body of evidence, not a faithful render.
    """
    body = LATEX_COMMENT.sub("", raw)
    body = re.sub(r"\\(href|url)\s*\{([^}]*)\}\s*(\{([^}]*)\})?",
                  lambda m: f"{m.group(4) or ''} {m.group(2)}", body)
    body = LATEX_COMMAND.sub(" ", body)
    body = body.replace("{", " ").replace("}", " ").replace("&", " ")
    body = re.sub(r"[ \t]+", " ", body)
    return "\n".join(line.strip() for line in body.splitlines() if line.strip())


def _looks_like_json_resume(data: Any) -> bool:
    return isinstance(data, dict) and "basics" in data and isinstance(data.get("basics"), dict)


def _looks_like_linkedin(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    keys = {k.lower() for k in data}
    return "firstname" in keys and ("positions" in keys or "profile" in keys)


def _from_linkedin(data: dict[str, Any]) -> dict[str, Any]:
    """Best-effort mapping of a LinkedIn data export into JSON Resume shape."""
    def pick(*names: str) -> Any:
        for name in names:
            for key, value in data.items():
                if key.lower() == name.lower():
                    return value
        return None

    first, last = pick("firstName") or "", pick("lastName") or ""
    out = profile_mod.empty()
    out["basics"]["name"] = " ".join(p for p in (first, last) if p)
    out["basics"]["label"] = pick("headline") or ""
    out["basics"]["summary"] = pick("summary") or ""
    if pick("emailAddress"):
        out["basics"]["email"] = pick("emailAddress")

    for role in pick("positions") or []:
        if not isinstance(role, dict):
            continue
        out["work"].append({
            "name": role.get("companyName") or role.get("company") or "",
            "position": role.get("title") or "",
            "location": role.get("location") or "",
            "startDate": role.get("startedOn") or role.get("startDate") or "",
            "endDate": role.get("finishedOn") or role.get("endDate") or "",
            "summary": role.get("description") or "",
        })
    for school in pick("education") or []:
        if isinstance(school, dict):
            out["education"].append({
                "institution": school.get("schoolName") or "",
                "area": school.get("fieldOfStudy") or "",
                "studyType": school.get("degreeName") or "",
                "startDate": school.get("startedOn") or "",
                "endDate": school.get("finishedOn") or "",
            })
    skills = [s.get("name") if isinstance(s, dict) else s for s in (pick("skills") or [])]
    skills = [s for s in skills if s]
    if skills:
        out["skills"].append({"name": "LinkedIn skills", "keywords": skills})
    return out


# --------------------------------------------------------------------------- #
# extraction from unstructured text
# --------------------------------------------------------------------------- #

def contacts_from_text(text: str) -> dict[str, Any]:
    """Only what a regex can be trusted with: contact points and links."""
    basics: dict[str, Any] = {}
    emails = EMAIL_RE.findall(text)
    if emails:
        basics["email"] = emails[0]

    profiles = []
    seen = set()
    for url in URL_RE.findall(text):
        url = url.rstrip(".,);")
        for host, network in KNOWN_PROFILES.items():
            if host in url and network not in seen:
                profiles.append({"network": network, "url": url})
                seen.add(network)
                break
    orcid = ORCID_RE.search(text)
    if orcid and "ORCID" not in seen:
        profiles.append({"network": "ORCID", "url": f"https://orcid.org/{orcid.group(0)}"})
    if profiles:
        basics["profiles"] = profiles
    return {"basics": basics} if basics else {}


def strip_annotations(node: Any, trail: str = "") -> tuple[Any, list[str]]:
    """A profile with every `_`-prefixed key removed, and the list of what went.

    Underscore keys are the source system's marginalia — editorial notes, "do not
    claim this" warnings, provenance, paths back into whatever repository the CV
    was assembled in. JSON Resume has no such fields and nothing here reads one,
    so their only possible destination is a rendered document going to a stranger.
    A real one seen in the wild pointed at a private repository path and named an
    internal memory file; `cv.lint` caught it at the last moment. Dropping them at
    the door is the earlier and better place — but never silently, because a note
    a person wrote is a note they may want back.
    """
    dropped: list[str] = []
    if isinstance(node, dict):
        clean = {}
        for key, value in node.items():
            where = f"{trail}.{key}" if trail else key
            if key.startswith("_"):
                dropped.append(where)
                continue
            clean[key], gone = strip_annotations(value, where)
            dropped.extend(gone)
        return clean, dropped
    if isinstance(node, list):
        out = []
        for index, value in enumerate(node):
            item, gone = strip_annotations(value, f"{trail}[{index}]")
            out.append(item)
            dropped.extend(gone)
        return out, dropped
    return node, dropped


def ingest_file(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read one document. Returns (profile fragment, report).

    The report is the honest half: what was recognised, what was extracted, and
    what a human still has to supply.
    """
    report: dict[str, Any] = {"file": str(path), "kind": "", "extracted": [], "todo": []}
    if not path.exists():
        raise IngestError(f"no such file: {path}")

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(errors="replace"))
        if _looks_like_json_resume(data):
            report["kind"] = "json-resume"
            data, annotations = strip_annotations(data)
            report["extracted"] = [k for k in data if data.get(k)]
            if annotations:
                report["dropped"] = annotations
                report["todo"].append(
                    f"{len(annotations)} private annotation(s) were left behind, not merged: "
                    f"{', '.join(annotations[:4])}"
                    f"{f' (+{len(annotations) - 4} more)' if len(annotations) > 4 else ''}. "
                    "Underscore keys are notes to yourself; they have no place in a document "
                    "an employer reads. They are still in the source file if you want them")
            return data, report
        if _looks_like_linkedin(data):
            report["kind"] = "linkedin-export"
            fragment = _from_linkedin(data)
            report["extracted"] = [k for k in ("basics", "work", "education", "skills")
                                   if fragment.get(k)]
            report["todo"].append(
                "a LinkedIn export carries no notice period, salary expectation or work "
                "authorization — fill `application` before applying")
            return fragment, report
        report["kind"] = "json (unrecognised)"
        report["todo"].append(
            "this JSON is neither JSON Resume nor a LinkedIn export; it was kept as "
            "evidence text but no fields were mapped")
        text = json.dumps(data, ensure_ascii=False, indent=1)
    else:
        text = read_text(path)
        report["kind"] = {".pdf": "pdf", ".tex": "latex", ".latex": "latex",
                          ".md": "markdown"}.get(path.suffix.lower(), "text")

    fragment = contacts_from_text(text)
    if fragment.get("basics", {}).get("email"):
        report["extracted"].append("email")
    if fragment.get("basics", {}).get("profiles"):
        report["extracted"].append(
            f"{len(fragment['basics']['profiles'])} profile link(s)")

    fragment.setdefault("meta", {})["evidenceText"] = text[:200000]
    report["extracted"].append(f"{len(text.split())} words of evidence text")
    report["todo"].append(
        "roles, dates and skills were NOT inferred from this document — inferring them "
        "is how fabricated history gets into a profile. Add them to the JSON, or run "
        "`opp profile --agent` to get a filling prompt for a Claude session")
    return fragment, report


def ingest(paths_in: list[Path], base: dict[str, Any] | None = None
           ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = base if base is not None else profile_mod.empty()
    reports = []
    for path in paths_in:
        fragment, report = ingest_file(path)
        result = profile_mod.merge(result, fragment, source=str(path))
        reports.append(report)
    return result, reports


def agent_prompt(profile: dict[str, Any]) -> str:
    """A prompt package for a Claude Code session to complete the profile.

    Deliberately not an API call: this tool never spends money on inference the
    user did not ask for. It hands you the exact task and the exact rules, to run
    in a session you already pay for.
    """
    evidence = (profile.get("meta", {}) or {}).get("evidenceText", "")
    missing = profile_mod.gaps(profile)
    return f"""You are completing a JSON Resume profile from a person's own CV text.

RULES — these are absolute:
- Use ONLY facts present in the evidence text below. Invent nothing.
- If a date, title, employer or metric is ambiguous, leave the field empty and add a
  note to `meta.unresolved` naming what was ambiguous. An empty field is correct;
  a plausible guess is a fabrication that will end up on a real application.
- Do not add skills the text does not support.
- Do not copy a home address, a national ID, a permit number or a date of birth into
  the profile. Those belong in the user's own records, not in a file that tools read.

STILL MISSING (these block an application):
{chr(10).join(f'  - {field}: {why}' for field, why in missing) or '  (nothing)'}

OUTPUT: a single JSON object in JSON Resume shape with the sections you can fill
(`basics`, `work`, `education`, `skills`, `projects`, `publications`). Then merge it:
  opp ingest filled.json

EVIDENCE TEXT
-------------
{evidence[:60000]}
"""

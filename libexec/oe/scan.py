# Copyright 2026 Mohsen Seyedkazemi Ardebili
# SPDX-License-Identifier: Apache-2.0
# Part of opportunity-engine — https://github.com/MSKazemi/opportunity-engine
"""Fetch opportunities from the key-free sources and normalise them.

Each normaliser was written against a real response captured on 2026-08-15, not
against the vendor's documentation — the two disagree often enough that guessing
costs more than checking. If a payload changes shape, the normaliser returns what
it can and records the miss rather than inventing a field: a row with an empty
description is honest, a row with a fabricated one poisons every later match.

Everything lands in one schema.org/JobPosting-shaped record, because that is the
vocabulary both the boards and the automated screeners already speak.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from itertools import islice
from typing import Any, Callable, Iterator

from . import sources
from .store import now

TAG_RE = re.compile(r"<[^>]+>")
#: Every horizontal space character, not just ASCII ones. `&nbsp;` unescapes to
#: U+00A0, and a description carrying "We need" will never match a search
#: for "we need" — the mismatch is invisible on screen and fatal to scoring.
WS_RE = re.compile(r"[ \t\r\f\v\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+")


def text_of(raw: str | None) -> str:
    """HTML or plain text in, readable plain text out."""
    if not raw:
        return ""
    body = TAG_RE.sub(" ", raw)
    body = html.unescape(body)
    body = WS_RE.sub(" ", body)
    return "\n".join(line.strip() for line in body.splitlines() if line.strip()).strip()


def joined(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v)
    return str(value or "")


# --------------------------------------------------------------------------- #
# normalisers — one per source, keyed on the shapes actually observed
# --------------------------------------------------------------------------- #

def _greenhouse(payload: dict, board: str) -> Iterator[dict]:
    for job in payload.get("jobs", []):
        yield {
            "source": "greenhouse", "source_ref": board,
            "url": job.get("absolute_url", ""),
            "title": job.get("title", ""),
            "org": job.get("company_name") or board,
            "description": text_of(job.get("content")),
            "location": (job.get("location") or {}).get("name", ""),
            "posted_at": job.get("first_published") or job.get("updated_at", ""),
            "valid_through": job.get("application_deadline") or "",
            "language": job.get("language", ""),
            "opportunity_type": "employment",
            "raw": json.dumps(job, ensure_ascii=False)[:20000],
        }


def _lever(payload: list, company: str) -> Iterator[dict]:
    for job in payload:
        categories = job.get("categories") or {}
        yield {
            "source": "lever", "source_ref": company,
            "url": job.get("hostedUrl", ""),
            "title": job.get("text", ""),
            "org": company,
            "description": text_of(job.get("descriptionPlain") or job.get("description")),
            "location": categories.get("location", ""),
            "employment_type": categories.get("commitment", ""),
            "posted_at": str(job.get("createdAt", "")),
            "opportunity_type": "employment",
            "raw": json.dumps(job, ensure_ascii=False)[:20000],
        }


def _ashby(payload: dict, org: str) -> Iterator[dict]:
    for job in payload.get("jobs", []):
        yield {
            "source": "ashby", "source_ref": org,
            "url": job.get("jobUrl") or job.get("applyUrl", ""),
            "title": job.get("title", "").strip(),
            "org": org,
            "description": text_of(job.get("descriptionPlain") or job.get("descriptionHtml")),
            "location": job.get("location", ""),
            "remote": 1 if job.get("isRemote") else 0,
            "employment_type": job.get("employmentType", ""),
            "posted_at": job.get("publishedAt", ""),
            "opportunity_type": "employment",
            "raw": json.dumps(job, ensure_ascii=False)[:20000],
        }


def _arbeitnow(payload: dict, _: str = "") -> Iterator[dict]:
    for job in payload.get("data", []):
        yield {
            "source": "arbeitnow", "source_ref": job.get("slug", ""),
            "url": job.get("url", ""),
            "title": job.get("title", ""),
            "org": job.get("company_name", ""),
            "description": text_of(job.get("description")),
            "location": job.get("location", ""),
            "remote": 1 if job.get("remote") else 0,
            "employment_type": joined(job.get("job_types")),
            "tags": joined(job.get("tags")),
            "posted_at": str(job.get("created_at", "")),
            "opportunity_type": "employment",
            "raw": json.dumps(job, ensure_ascii=False)[:20000],
        }


def _remotive(payload: dict, _: str = "") -> Iterator[dict]:
    for job in payload.get("jobs", []):
        yield {
            "source": "remotive", "source_ref": str(job.get("id", "")),
            "url": job.get("url", ""),
            "title": job.get("title", ""),
            "org": job.get("company_name", ""),
            "description": text_of(job.get("description")),
            "location": job.get("candidate_required_location", ""),
            "remote": 1,
            "employment_type": job.get("job_type", ""),
            "tags": joined(job.get("tags")),
            "posted_at": job.get("publication_date", ""),
            "opportunity_type": "employment",
            "raw": json.dumps(job, ensure_ascii=False)[:20000],
        }


def _remoteok(payload: list, _: str = "") -> Iterator[dict]:
    for job in payload:
        if not isinstance(job, dict) or "position" not in job:
            continue                      # the first row is the API's legal notice
        yield {
            "source": "remoteok", "source_ref": str(job.get("id", "")),
            "url": job.get("url") or job.get("apply_url", ""),
            "title": job.get("position", ""),
            "org": job.get("company", ""),
            "description": text_of(job.get("description")),
            "location": job.get("location", ""),
            "remote": 1,
            "tags": joined(job.get("tags")),
            "salary_min": job.get("salary_min") or None,
            "salary_max": job.get("salary_max") or None,
            "salary_currency": "USD" if job.get("salary_min") else "",
            "salary_period": "year" if job.get("salary_min") else "",
            "posted_at": job.get("date", ""),
            "opportunity_type": "employment",
            "raw": json.dumps(job, ensure_ascii=False)[:20000],
        }


def _jobicy(payload: dict, _: str = "") -> Iterator[dict]:
    for job in payload.get("jobs", []):
        yield {
            "source": "jobicy", "source_ref": str(job.get("id", "")),
            "url": job.get("url", ""),
            "title": job.get("jobTitle", ""),
            "org": job.get("companyName", ""),
            "description": text_of(job.get("jobDescription") or job.get("jobExcerpt")),
            "location": job.get("jobGeo", ""),
            "remote": 1,
            "employment_type": joined(job.get("jobType")),
            "tags": joined(job.get("jobIndustry")),
            "salary_min": job.get("salaryMin") or None,
            "salary_max": job.get("salaryMax") or None,
            "salary_currency": job.get("salaryCurrency", ""),
            "posted_at": job.get("pubDate", ""),
            "opportunity_type": "employment",
            "raw": json.dumps(job, ensure_ascii=False)[:20000],
        }


def _himalayas(payload: dict, _: str = "") -> Iterator[dict]:
    for job in payload.get("jobs", []):
        yield {
            "source": "himalayas", "source_ref": str(job.get("guid", "")),
            "url": job.get("applicationLink", ""),
            "title": job.get("title", ""),
            "org": job.get("companyName", ""),
            "description": text_of(job.get("description") or job.get("excerpt")),
            "location": joined(job.get("locationRestrictions")),
            "remote": 1,
            "employment_type": job.get("employmentType", ""),
            "tags": joined(job.get("categories")),
            "salary_min": job.get("minSalary") or None,
            "salary_max": job.get("maxSalary") or None,
            "salary_currency": job.get("currency", ""),
            "salary_period": job.get("salaryPeriod", ""),
            "valid_through": str(job.get("expiryDate", "")),
            "posted_at": str(job.get("pubDate", "")),
            "opportunity_type": "employment",
            "raw": json.dumps(job, ensure_ascii=False)[:20000],
        }


def _weworkremotely(payload: bytes, _: str = "") -> Iterator[dict]:
    root = ET.fromstring(payload)
    for item in root.iterfind(".//item"):
        def field(tag: str) -> str:
            node = item.find(tag)
            return (node.text or "") if node is not None else ""
        title = field("title")
        org, _, role = title.partition(":")
        yield {
            "source": "weworkremotely", "source_ref": field("guid"),
            "url": field("link"),
            "title": (role or title).strip(),
            "org": org.strip() if role else "",
            "description": text_of(field("description")),
            "location": field("region"),
            "remote": 1,
            "posted_at": field("pubDate"),
            "opportunity_type": "employment",
        }


NORMALISERS: dict[str, Callable[..., Iterator[dict]]] = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "ashby": _ashby,
    "arbeitnow": _arbeitnow,
    "remotive": _remotive,
    "remoteok": _remoteok,
    "jobicy": _jobicy,
    "himalayas": _himalayas,
    "weworkremotely": _weworkremotely,
}

#: Sources that can be scanned without a key or a login, in the order that costs
#: the least to try. Everything else needs `opp apply` and a human-driven browser.
SCANNABLE = tuple(NORMALISERS)


def scan_source(source_id: str, target: str | None = None, limit: int = 200,
                registry: dict | None = None) -> tuple[list[dict], dict]:
    """Fetch one source. Returns (rows, report).

    `target` is the company slug for the per-company ATS boards. The report says
    what happened even when nothing came back, because a source that silently
    returns zero rows looks identical to one that is simply quiet today.
    """
    source = sources.get(source_id, registry)
    report: dict[str, Any] = {"source": source_id, "target": target or "", "at": now()}

    if source is None:
        return [], {**report, "status": "unknown-source"}
    if source_id not in NORMALISERS:
        return [], {**report, "status": "not-scannable",
                    "detail": "no key-free feed; use `opp apply` for this one"}

    access = source.get("access") or {}
    endpoint = access.get("endpoint", "")
    # Only a per-company board needs a target. `{n}` and friends are request
    # parameters and must never be mistaken for one.
    if access.get("per_company"):
        if not target:
            return [], {**report, "status": "needs-target",
                        "detail": "per-company board; pass --target <company-slug>"}
        for placeholder in ("{board}", "{company}", "{org}", "{account}"):
            endpoint = endpoint.replace(placeholder, target)
    endpoint = (endpoint.replace("{n}", str(limit))
                        .replace("{geo}", "").replace("{industry}", ""))

    status, body = sources.fetch(endpoint)
    if not 200 <= status < 300:
        return [], {**report, "status": "http-error", "http": status,
                    "detail": body[:200].decode("utf-8", "replace")}

    normalise = NORMALISERS[source_id]
    try:
        payload: Any = body if source_id == "weworkremotely" else json.loads(body)
        # islice, not list(...)[:limit] — these feeds carry thousands of rows and
        # cleaning the HTML of every one before throwing most away costs minutes.
        rows = list(islice((r for r in normalise(payload, target or "") if r.get("title")),
                           limit))
    except (json.JSONDecodeError, ET.ParseError, KeyError, TypeError) as err:
        return [], {**report, "status": "unparsable", "http": status,
                    "detail": f"{type(err).__name__}: {err}"}
    return rows, {**report, "status": "ok", "http": status, "fetched": len(rows)}

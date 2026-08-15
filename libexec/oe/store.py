# Copyright 2026 Mohsen Seyedkazemi Ardebili
# SPDX-License-Identifier: Apache-2.0
# Part of opportunity-engine — https://github.com/MSKazemi/opportunity-engine
"""The opportunity store — one SQLite file, no server, no ORM.

Every row is one opportunity in a shape borrowed from schema.org/JobPosting, so
what is stored here is already the vocabulary that job boards publish and that
automated screeners consume. The engine's own fields (score, state, evidence)
live alongside it rather than replacing it.

Deduplication is by `fingerprint`, not by URL: the same role is routinely posted
to four boards under four URLs, and applying twice through two channels is worse
than not applying at all.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    id              TEXT PRIMARY KEY,
    fingerprint     TEXT NOT NULL,
    source          TEXT NOT NULL,
    source_ref      TEXT DEFAULT '',
    url             TEXT DEFAULT '',
    title           TEXT DEFAULT '',
    org             TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    location        TEXT DEFAULT '',
    country         TEXT DEFAULT '',
    remote          INTEGER DEFAULT 0,
    employment_type TEXT DEFAULT '',
    opportunity_type TEXT DEFAULT '',
    salary_min      REAL,
    salary_max      REAL,
    salary_currency TEXT DEFAULT '',
    salary_period   TEXT DEFAULT '',
    posted_at       TEXT DEFAULT '',
    valid_through   TEXT DEFAULT '',
    tags            TEXT DEFAULT '',
    language        TEXT DEFAULT '',
    raw             TEXT DEFAULT '',
    fetched_at      TEXT DEFAULT '',
    -- engine fields
    score           REAL,
    score_detail    TEXT DEFAULT '',
    state           TEXT DEFAULT 'new',
    state_reason    TEXT DEFAULT '',
    updated_at      TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_fingerprint ON opportunities(fingerprint);
CREATE INDEX IF NOT EXISTS idx_state       ON opportunities(state);
CREATE INDEX IF NOT EXISTS idx_score       ON opportunities(score);
CREATE INDEX IF NOT EXISTS idx_source      ON opportunities(source);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity  TEXT NOT NULL,
    at           TEXT NOT NULL,
    event        TEXT NOT NULL,
    detail       TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_opp ON events(opportunity);

CREATE TABLE IF NOT EXISTS scans (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL,
    source     TEXT NOT NULL,
    target     TEXT DEFAULT '',
    status     TEXT DEFAULT '',
    fetched    INTEGER DEFAULT 0,
    new_rows   INTEGER DEFAULT 0,
    duplicates INTEGER DEFAULT 0,
    detail     TEXT DEFAULT ''
);
"""

STATES = ("new", "screened", "rejected", "shortlisted", "drafted",
          "applied", "blocked", "replied", "interview", "offer", "closed")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


_WORD = re.compile(r"[a-z0-9]+")


def fingerprint(org: str, title: str, location: str = "") -> str:
    """What makes two postings the same job.

    Normalised so that "Senior SRE (m/f/d)" at "ACME GmbH" and "Senior SRE" at
    "ACME" collapse together. Location is included but coarsely: the same role in
    two cities is two jobs, the same role posted twice for one city is one.
    """
    def norm(s: str) -> str:
        s = s.lower()
        s = re.sub(r"\((?:m|w|f|d|x)[/|]?(?:m|w|f|d|x)?[/|]?(?:m|w|f|d|x)?\)", " ", s)
        s = re.sub(r"\b(gmbh|ag|inc|ltd|llc|s\.p\.a|srl|bv|nv|oy|ab|as)\b", " ", s)
        return " ".join(_WORD.findall(s))

    key = f"{norm(org)}|{norm(title)}|{norm(location)[:40]}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def make_id(source: str, url: str, title: str) -> str:
    return hashlib.sha1(f"{source}|{url}|{title}".encode()).hexdigest()[:12]


def upsert(con: sqlite3.Connection, row: dict[str, Any]) -> str:
    """Insert an opportunity, or recognise it as one already seen.

    Returns "new", "duplicate" (same job, different posting) or "known" (this
    exact posting again). Nothing is overwritten on a repeat: a scan must never
    silently reset a state you moved a row into by hand.
    """
    row = dict(row)
    row.setdefault("fetched_at", now())
    row["fingerprint"] = fingerprint(row.get("org", ""), row.get("title", ""),
                                     row.get("location", ""))
    row["id"] = make_id(row.get("source", ""), row.get("url", ""), row.get("title", ""))

    existing = con.execute("SELECT id FROM opportunities WHERE id = ?", (row["id"],)).fetchone()
    if existing:
        return "known"

    twin = con.execute("SELECT id FROM opportunities WHERE fingerprint = ?",
                       (row["fingerprint"],)).fetchone()

    columns = [c[1] for c in con.execute("PRAGMA table_info(opportunities)")]
    payload = {k: v for k, v in row.items() if k in columns}
    payload.setdefault("state", "duplicate" if twin else "new")
    payload.setdefault("updated_at", now())
    if twin:
        payload["state"] = "closed"
        payload["state_reason"] = f"duplicate of {twin['id']}"

    keys = ", ".join(payload)
    marks = ", ".join("?" for _ in payload)
    con.execute(f"INSERT INTO opportunities ({keys}) VALUES ({marks})", list(payload.values()))
    log(con, row["id"], "found", row.get("source", ""))
    return "duplicate" if twin else "new"


def log(con: sqlite3.Connection, opportunity: str, event: str, detail: str = "") -> None:
    con.execute("INSERT INTO events (opportunity, at, event, detail) VALUES (?,?,?,?)",
                (opportunity, now(), event, detail))


def record_scan(con: sqlite3.Connection, **fields: Any) -> None:
    fields.setdefault("at", now())
    keys = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    con.execute(f"INSERT INTO scans ({keys}) VALUES ({marks})", list(fields.values()))


def counts(con: sqlite3.Connection) -> dict[str, int]:
    rows = con.execute("SELECT state, COUNT(*) n FROM opportunities GROUP BY state")
    return {r["state"]: r["n"] for r in rows}


def search(con: sqlite3.Connection, state: str | None = None, source: str | None = None,
           limit: int = 50, order: str = "score") -> list[sqlite3.Row]:
    where, params = [], []
    if state:
        where.append("state = ?")
        params.append(state)
    if source:
        where.append("source = ?")
        params.append(source)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    order_sql = {"score": "score DESC NULLS LAST, posted_at DESC",
                 "date": "posted_at DESC",
                 "org": "org ASC"}.get(order, "score DESC NULLS LAST")
    params.append(limit)
    return list(con.execute(
        f"SELECT * FROM opportunities {clause} ORDER BY {order_sql} LIMIT ?", params))


def dump(rows: Iterable[sqlite3.Row]) -> str:
    return json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False)

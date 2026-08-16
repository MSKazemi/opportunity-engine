# Copyright 2026 Mohsen Seyedkazemi Ardebili
# SPDX-License-Identifier: Apache-2.0
# Part of opportunity-engine — https://github.com/MSKazemi/opportunity-engine
"""Where things live.

The workspace holds *your* data — profile, opportunities, applications — and is
resolved from where you are, so one installed copy serves several workspaces
(a personal hunt, a client's, a throwaway experiment) without them seeing each
other:

    $OPP_HOME            if set, wins outright
    nearest ancestor holding .opp/     the usual case, created by `opp init`
    ~/.opportunity       the default when nothing else matches

The repository's own read-only data (the source registry, schemas, CV templates)
is found relative to this file and never written to.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
SCHEMAS = REPO / "schemas"
TEMPLATES = REPO / "cv" / "templates"

WORKSPACE_MARKER = ".opp"


def find_workspace(start: Path | None = None) -> Path:
    """The workspace in scope. Does not create anything."""
    env = os.environ.get("OPP_HOME")
    if env:
        return Path(env).expanduser().resolve()

    cwd = (start or Path.cwd()).resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / WORKSPACE_MARKER).is_dir():
            return candidate / WORKSPACE_MARKER

    return Path.home() / ".opportunity"


def ensure_workspace(root: Path | None = None) -> Path:
    ws = root or find_workspace()
    for sub in ("", "profile", "opportunities", "applications", "cv", "logs", "cache"):
        (ws / sub).mkdir(parents=True, exist_ok=True)
    return ws


def db_path(ws: Path | None = None) -> Path:
    return (ws or find_workspace()) / "opportunities.db"


def profile_path(ws: Path | None = None) -> Path:
    return (ws or find_workspace()) / "profile" / "profile.json"


def config_path(ws: Path | None = None) -> Path:
    return (ws or find_workspace()) / "config.json"


def local_sources_path(ws: Path | None = None) -> Path:
    """Your own additions to the source registry.

    Deliberately in the workspace and not in the repository: a source you added
    is *your* data, and the shipped registry is something you pull updates to.
    Keeping them in one file would mean every `git pull` was a merge conflict and
    every private endpoint was one `git add -A` away from a public remote.
    """
    return (ws or find_workspace()) / "sources.local.json"


#: Written on `opp init` so the file exists, is valid, and explains itself. The
#: example is commented out by being a `_example` key rather than a source row —
#: a registry that ships with a fake source in it would be a registry that lies.
DEFAULT_LOCAL_SOURCES = {
    "_note": "Your own sources. Merged over the shipped registry by `id`: a new id is "
             "added, a known id is patched field-by-field, and \"disabled\": true mutes "
             "one without deleting it. Never committed — this file is yours.",
    "_example": {
        "id": "example-board",
        "name": "Some board with a public JSON feed",
        "kind": "aggregator",
        "access": {"method": "api", "endpoint": "https://example.com/api/jobs?limit={n}",
                   "auth": "none", "key_required": False},
        "free": {"cost": "free", "card_required": False, "capacity": None},
        "apply": {"channel": "redirect", "automatable": True, "walls": []},
        "_why": "Adding a row makes the source known and checkable. Scanning it also needs a "
                "normaliser in scan.py — `opp sources-check --id <id>` tells you where it stands.",
    },
    "sources": [],
}


#: The user's own hard rules. The tool has no opinion about which countries,
#: sectors or contract forms anyone will work in — it only honours what the user
#: declared here, and says which line of this file blocked something.
DEFAULT_CONFIG = {
    "_note": "Your rules. A match is knocked out — not merely penalised — when it hits one.",
    "languages": ["english"],
    "_languages": "Languages you can honestly claim. A posting demanding one you did not list is knocked out.",
    "exclude_countries": [],
    "_exclude_countries": "Substrings matched against a posting's location, e.g. ['united states'].",
    "exclude_signals": [],
    "_exclude_signals": "Any of: clearance, citizenship, residency, employment-form, sector.",
    "no_clearance": True,
    "_no_clearance": "Knock out roles requiring a security clearance you cannot obtain.",
    "min_fit": 0.45,
    "_min_fit": "Below this, `opp match --top` will not suggest applying.",

    # --- how an application leaves your machine -----------------------------
    # Volume is a real constraint: at ten or fifty packages, reviewing each one
    # by hand is the bottleneck, and some people would rather trade that review
    # for throughput. That is a judgement about *your* time and *your* name, so
    # it is yours to make. What it cannot buy is a false statement — see
    # auto_submit_requires below, which no setting turns off.
    "auto_submit": False,
    "_auto_submit": "false = a worker fills the form, screenshots it and stops for you. "
                    "true = it presses submit itself, but only when every condition in "
                    "auto_submit_requires holds. Anything else still stops and waits.",
    "auto_submit_max": 10,
    "_auto_submit_max": "Most applications a single run may send. A ceiling on the blast "
                        "radius of a mistake — the rest are prepared and left waiting.",
    "auto_submit_requires": [
        "every form field answered truthfully from your profile — no MISSING, no guess",
        "no private notes detected in the generated CV",
        "the posting was not knocked out by your own rules",
        "no login, captcha, 2FA or identity check in the way",
        "the confirmation the site returned is actually visible",
    ],
    "_auto_submit_requires": "Read-only. These are not preferences and setting auto_submit "
                             "does not waive them: each one is the difference between sending "
                             "fast and sending something untrue over your signature.",
}


#: What `exclude_signals` accepts. A free-form string here would be silently
#: ignored by the matcher — a knockout rule that never fires looks exactly like
#: one that never had anything to knock out, which is the worst way to be wrong.
SIGNALS = ("clearance", "citizenship", "residency", "employment-form", "sector")

LIST_RULES = ("languages", "exclude_countries", "exclude_signals")

#: key -> the type it is stored as. `auto_submit_requires` is deliberately absent:
#: it is not a preference, and leaving it unsettable here is what keeps it so.
SETTABLE_RULES = {
    "languages": list, "exclude_countries": list, "exclude_signals": list,
    "no_clearance": bool, "min_fit": float, "auto_submit": bool, "auto_submit_max": int,
}

TRUTHY = {"true", "yes", "on", "1"}
FALSEY = {"false", "no", "off", "0"}


def coerce_rule_item(key: str, value: str) -> str:
    """One member of a list rule, normalised and checked."""
    item = value.strip().strip("'\"").lower()
    if not item:
        raise ValueError(f"{key}: an empty value is not a rule")
    if key == "exclude_signals" and item not in SIGNALS:
        raise ValueError(f"exclude_signals accepts one of: {', '.join(SIGNALS)} — not '{item}'")
    return item


def coerce_rule(key: str, value: str) -> object:
    """A rule value parsed into the type the matcher expects.

    Raises rather than guessing. `min_fit=high` has no defensible reading, and a
    rule that silently became 0.0 would quietly stop protecting anything.
    """
    if key.startswith("_") or key == "auto_submit_requires":
        raise KeyError(f"{key} is read-only — it is not a preference")
    if key not in SETTABLE_RULES:
        raise KeyError(f"unknown rule '{key}' — try one of: {', '.join(SETTABLE_RULES)}")

    want = SETTABLE_RULES[key]
    text = value.strip().strip("'\"")
    if want is bool:
        if text.lower() in TRUTHY:
            return True
        if text.lower() in FALSEY:
            return False
        raise ValueError(f"{key} is true or false, not '{text}'")
    if want is float:
        try:
            number = float(text)
        except ValueError:
            raise ValueError(f"{key} is a number between 0 and 1, not '{text}'") from None
        if not 0.0 <= number <= 1.0:
            raise ValueError(f"{key} is a fit score between 0 and 1 — {number} is outside it")
        return number
    if want is int:
        try:
            number = int(text)
        except ValueError:
            raise ValueError(f"{key} is a whole number, not '{text}'") from None
        if number < 0:
            raise ValueError(f"{key} cannot be negative")
        return number
    # A list rule set wholesale: comma-separated, each member checked.
    return [coerce_rule_item(key, part) for part in text.split(",") if part.strip()]


def load_config(ws: Path | None = None) -> dict:
    import json
    target = config_path(ws)
    if not target.exists():
        return dict(DEFAULT_CONFIG)
    try:
        return {**DEFAULT_CONFIG, **json.loads(target.read_text())}
    except ValueError:
        return dict(DEFAULT_CONFIG)

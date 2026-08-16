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


def load_config(ws: Path | None = None) -> dict:
    import json
    target = config_path(ws)
    if not target.exists():
        return dict(DEFAULT_CONFIG)
    try:
        return {**DEFAULT_CONFIG, **json.loads(target.read_text())}
    except ValueError:
        return dict(DEFAULT_CONFIG)

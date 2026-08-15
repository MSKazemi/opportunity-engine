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

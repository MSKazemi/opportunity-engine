# Copyright 2026 Mohsen Seyedkazemi Ardebili
# SPDX-License-Identifier: Apache-2.0
# Part of opportunity-engine — https://github.com/MSKazemi/opportunity-engine
"""The source registry — where opportunities can be found, and what each one
gives away for free.

Two rules make this file worth having instead of a bookmark folder:

1. **Every row carries how it was checked and when.** `verified.method` is
   `http` (a real request was made), `operator` (a human who uses it reported
   it), or `documented`/`unverified`. A capacity number with no method behind it
   is a rumour, and rumours are what make a scan waste an afternoon.
2. **Free means free.** A source whose apply action costs money is recorded, but
   flagged, so a run can exclude it without re-litigating the question.
"""

from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import paths

USER_AGENT = "opportunity-engine/0.1 (+https://github.com/MSKazemi/opportunity-engine)"
STALE_DAYS = 30


#: Patching any of these means the endpoint that was verified is not the endpoint
#: that will now be called, so the inherited `verified` block no longer describes
#: anything real. `max_rows` is deliberately absent: clamping a row count changes
#: the query string but not what host answers it, and the prior check still holds.
VERIFICATION_CRITICAL = ("endpoint", "auth", "key_required")


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Patch over base, recursing into nested dicts.

    Lists are replaced wholesale, not concatenated: `walls: []` has to be able to
    mean "this one has no walls", which an append would make unsayable.
    """
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _patch_row(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """One shipped row with the user's overlay applied over it."""
    merged = _deep_merge(base, patch)
    merged["_origin"] = "patched"

    access_patch = patch.get("access") or {}
    base_access = base.get("access") or {}
    rewired = [k for k in VERIFICATION_CRITICAL
               if k in access_patch and access_patch[k] != base_access.get(k)]
    # An overlay that carries its own `verified` block is a user saying "I checked
    # this myself" — that is exactly the claim the field is for, so it stands.
    if rewired and "verified" not in patch:
        merged["verified"] = {
            "date": None, "method": "unverified",
            "note": f"inherited verification dropped — your overlay changed {', '.join(rewired)}; "
                    f"run `opp sources-check --id {base.get('id', '?')}` to prove this one",
        }
    return merged


def merge_registry(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """The shipped registry with a user overlay merged over it, by `id`.

    Three behaviours, and the reason there are three: an *unknown* id is appended,
    because adding a board is the common case. A *known* id is patched field by
    field, so fixing one number does not mean restating forty lines — and so a
    shipped fix to the rest of the row still arrives on the next pull. And
    `"disabled": true` mutes a row without deleting it, because a source you
    turned off for being noisy is not the same as one you never had.
    """
    rows: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for source in base.get("sources", []):
        rows[source["id"]] = {**source, "_origin": "shipped"}
        order.append(source["id"])

    for patch in overlay.get("sources", []):
        sid = patch.get("id")
        if not sid:
            continue
        if sid in rows:
            rows[sid] = _patch_row(rows[sid], patch)
        else:
            rows[sid] = {**patch, "_origin": "local"}
            order.append(sid)

    return {**base, "sources": [rows[sid] for sid in order]}


def load(path: Path | None = None, *, overlay: bool | Path = True) -> dict[str, Any]:
    """The registry as this workspace sees it.

    `overlay=False` gives the shipped registry alone — what the project ships,
    with nobody's local edits in it.
    """
    registry = json.loads((path or (paths.DATA / "sources.json")).read_text())
    if overlay is False:
        return registry

    local = overlay if isinstance(overlay, Path) else paths.local_sources_path()
    try:
        patch = json.loads(local.read_text())
    except (OSError, ValueError):
        # No overlay, or one that is not valid JSON. A broken personal file must
        # not take the shipped registry down with it; `opp sources-check` is
        # where it gets reported as broken.
        return merge_registry(registry, {})
    return merge_registry(registry, patch)


def is_disabled(source: dict[str, Any]) -> bool:
    return bool(source.get("disabled"))


def all_sources(registry: dict[str, Any] | None = None, *,
                include_disabled: bool = False) -> list[dict[str, Any]]:
    rows = (registry or load())["sources"]
    return rows if include_disabled else [s for s in rows if not is_disabled(s)]


def get(source_id: str, registry: dict[str, Any] | None = None) -> dict[str, Any] | None:
    # Includes disabled rows on purpose: asking for a source by name should find
    # the one that exists and let the caller say "that one is switched off",
    # rather than report it missing and send someone hunting for a typo.
    for source in all_sources(registry, include_disabled=True):
        if source["id"] == source_id:
            return source
    return None


def is_free(source: dict[str, Any]) -> bool:
    """Free means: usable with no card, and the apply action itself costs nothing."""
    free = source.get("free", {})
    if free.get("card_required"):
        return False
    if free.get("cost") in ("pay-per-bid", "paid"):
        return False
    return True


def is_automatable(source: dict[str, Any]) -> bool:
    return bool(source.get("apply", {}).get("automatable"))


def needs_key(source: dict[str, Any]) -> bool:
    return bool(source.get("access", {}).get("key_required"))


def staleness(source: dict[str, Any], today: date | None = None) -> int | None:
    """Days since this row was last verified, or None if it never was."""
    raw = source.get("verified", {}).get("date")
    if not raw:
        return None
    try:
        return ((today or date.today()) - datetime.strptime(raw, "%Y-%m-%d").date()).days
    except ValueError:
        return None


def filter_sources(sources: list[dict[str, Any]], *, free_only: bool = False,
                   kind: str | None = None, region: str | None = None,
                   opportunity_type: str | None = None, automatable: bool | None = None,
                   no_key: bool = False) -> list[dict[str, Any]]:
    out = []
    for source in sources:
        if free_only and not is_free(source):
            continue
        if no_key and needs_key(source):
            continue
        if kind and source.get("kind") != kind:
            continue
        if region and region not in source.get("regions", []):
            continue
        if opportunity_type and opportunity_type not in source.get("opportunity_types", []):
            continue
        if automatable is not None and is_automatable(source) is not automatable:
            continue
        out.append(source)
    return out


def _fetch_curl(url: str, timeout: int) -> tuple[int, bytes] | None:
    """GET via curl, or None if curl is unavailable.

    Measured on 2026-08-15 against arbeitnow's 1.3 MB feed: curl 1.7 s, urllib
    360 s for byte-identical output. The body trickles to Python's HTTP stack
    slowly enough that the socket timeout never fires — each read returns *some*
    data, so the transfer is not slow enough to fail, only slow enough to ruin a
    scan. curl negotiates the transfer differently and is not affected. Rather
    than ship a scan that takes minutes per source, use curl where it exists.
    """
    if not shutil.which("curl"):
        return None
    proc = subprocess.run(
        ["curl", "-sS", "--compressed", "--location", "--max-time", str(timeout),
         "--write-out", "%{http_code}", "--user-agent", USER_AGENT,
         "-H", "Accept: application/json, */*", url],
        capture_output=True, timeout=timeout + 10)
    if proc.returncode != 0:
        return 0, proc.stderr[:400] or b"curl failed"
    # --write-out appends the status to stdout; the last three bytes are the code.
    raw, status_bytes = proc.stdout[:-3], proc.stdout[-3:]
    try:
        return int(status_bytes), raw
    except ValueError:
        return 0, proc.stdout[:400]


def fetch(url: str, timeout: int = 30) -> tuple[int, bytes]:
    """One plain GET. Returns (status, body); never raises on an HTTP error code."""
    try:
        via_curl = _fetch_curl(url, timeout)
    except (subprocess.TimeoutExpired, OSError) as err:
        return 0, f"curl: {err}".encode()
    if via_curl is not None:
        return via_curl

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/json, */*",
                                                   "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return response.status, body
    except urllib.error.HTTPError as err:
        return err.code, err.read() or b""
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        return 0, str(err).encode()


def check(source: dict[str, Any], sample: str | None = None,
          timeout: int = 30) -> dict[str, Any]:
    """Re-verify one source by actually calling it.

    Returns a result dict rather than mutating the registry — deciding whether a
    404 means "dead" or "wrong company slug" is a judgement, and this function
    does not make it. Sources that need a key or a login are reported as
    unverifiable here rather than guessed at.
    """
    access = source.get("access", {})
    endpoint = access.get("endpoint")
    result: dict[str, Any] = {"id": source["id"], "checked": date.today().isoformat()}

    if not endpoint:
        return {**result, "verdict": "not-callable",
                "note": f"access method is '{access.get('method', '?')}' — nothing to call"}
    if access.get("key_required"):
        return {**result, "verdict": "needs-key",
                "note": f"needs {access.get('auth', 'credentials')}; supply one to check it"}

    url = endpoint
    if access.get("per_company"):
        value = sample or source.get("verified", {}).get("sample")
        if not value:
            return {**result, "verdict": "needs-sample",
                    "note": "endpoint is per-company; pass --sample <company-slug> to check it"}
        for placeholder in ("{board}", "{company}", "{org}", "{account}"):
            url = url.replace(placeholder, value)
    url = url.replace("{n}", "2").replace("{page}", "1").replace("{country}", "gb")
    url = url.replace("{geo}", "").replace("{industry}", "")

    status, body = fetch(url, timeout=timeout)
    verdict = "ok" if 200 <= status < 300 else ("unreachable" if status == 0 else "http-error")
    return {**result, "verdict": verdict, "status": status, "bytes": len(body), "url": url}

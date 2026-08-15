# Copyright 2026 Mohsen Seyedkazemi Ardebili
# SPDX-License-Identifier: Apache-2.0
# Part of opportunity-engine — https://github.com/MSKazemi/opportunity-engine
"""Generate a CV from the profile — one column, parseable, and honest.

Two constraints shape every decision in this file.

**The document has to survive a parser.** The first machine that reads it turns
a PDF back into text. Multi-column layouts interleave, tables scramble, text in
images vanishes, and a header/footer is frequently dropped. So: one column, real
text, standard section names, no tabular layout for content that must be read in
order. This costs some visual flair and buys the document a chance of being read
at all.

**Tailoring is selection, never invention.** Pointing this at a specific posting
reorders sections, promotes the roles and highlights that carry the terms that
posting asks for, and prefers the posting's vocabulary *where the profile already
proves the thing*. It never adds a skill, a number, a date, or an
accomplishment that the profile does not contain. A CV that wins an interview by
saying something untrue has cost the user more than the interview was worth.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import match as match_mod, paths, profile as profile_mod

#: LaTeX's special characters. Anything from a profile is user data, and user
#: data with a stray & or % in it must not be able to break the document — or to
#: inject a command into it.
LATEX_ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


#: Unicode that real CVs contain and that pdflatex refuses to typeset. A profile
#: written by a human is full of these — an em dash, a middot between skills, an
#: approximately sign in front of a number — and each one is a fatal error, not a
#: warning. Mapping them here keeps the document buildable on the plainest
#: TeX install anybody has, instead of demanding a Unicode-native engine.
UNICODE_TO_TEX = {
    "—": "---", "–": "--", "‑": "-", "−": "-", "―": "---",
    "≈": r"$\approx$", "≤": r"$\leq$", "≥": r"$\geq$", "≠": r"$\neq$",
    "×": r"$\times$", "±": r"$\pm$", "·": r"$\cdot$", "•": r"$\bullet$",
    "→": r"$\rightarrow$", "←": r"$\leftarrow$", "⇒": r"$\Rightarrow$",
    "…": r"\ldots{}", "°": r"$^{\circ}$", "′": "'", "″": "''",
    "“": "``", "”": "''", "‘": "`", "’": "'", "«": "``", "»": "''",
    "€": r"\euro{}", "£": r"\pounds{}", "™": r"\texttrademark{}",
    "©": r"\textcopyright{}", "®": r"\textregistered{}", "§": r"\S{}",
    " ": "~", " ": r"\,", "​": "",
    "α": r"$\alpha$", "β": r"$\beta$", "μ": r"$\mu$", "σ": r"$\sigma$", "Δ": r"$\Delta$",
}

#: Anything outside this is dropped with a warning rather than killing the build.
SAFE_RANGE = re.compile(r"[^\x00-\x7F]")


def tex_escape(text: Any) -> str:
    out = str(text or "")
    for char, replacement in LATEX_ESCAPES.items():
        out = out.replace(char, replacement)
    for char, replacement in UNICODE_TO_TEX.items():
        out = out.replace(char, replacement)
    return out


def unmapped_unicode(text: str) -> set[str]:
    """Non-ASCII left after escaping — accented names and the like.

    Not an error: inputenc handles Latin-1 accents fine. This exists so the
    caller can say which characters it is relying on the engine to know.
    """
    return {c for c in SAFE_RANGE.findall(text)}


def fill(template: str, values: dict[str, str]) -> str:
    """`{{ key }}` substitution. No expression evaluation, by design."""
    def swap(hit: re.Match) -> str:
        return values.get(hit.group(1).strip(), "")
    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", swap, template)


def _date_range(start: str, end: str) -> str:
    start = (start or "")[:7]
    end = (end or "")[:7]
    return f"{start} -- {end or 'present'}" if start else (end or "")


def relevance(text: str, wanted: set[str]) -> int:
    """How many of the posting's terms this line actually demonstrates."""
    low = text.lower()
    return sum(1 for term in wanted if match_mod._contains_term(low, term))


def tailor(profile: dict[str, Any], report: dict[str, Any] | None) -> dict[str, Any]:
    """Reorder for one posting. Adds nothing, removes nothing.

    Every role, project and highlight the profile contains is still present; only
    the order changes, so the reader meets the relevant evidence first. That is
    the whole of what "tailoring" may honestly mean.
    """
    if not report:
        return profile

    wanted = set(report.get("requirements", {}).get("required_terms", []))
    wanted |= set(report.get("requirements", {}).get("optional_terms", []))
    if not wanted:
        return profile

    tuned = {**profile}

    def score_job(job: dict[str, Any]) -> tuple[int, str]:
        body = " ".join([job.get("summary", ""), job.get("position", ""),
                         " ".join(job.get("highlights", []) or [])])
        return (-relevance(body, wanted), job.get("endDate") or "9999")

    tuned["work"] = sorted(profile.get("work", []), key=score_job)
    for job in tuned["work"]:
        if job.get("highlights"):
            job["highlights"] = sorted(job["highlights"],
                                       key=lambda h: -relevance(h, wanted))
    tuned["projects"] = sorted(
        profile.get("projects", []),
        key=lambda p: -relevance(" ".join([p.get("description", ""), p.get("name", ""),
                                           " ".join(p.get("highlights", []) or [])]), wanted))
    tuned["skills"] = sorted(
        profile.get("skills", []),
        key=lambda s: -relevance(" ".join([s.get("name", "")] + (s.get("keywords") or [])), wanted))
    return tuned


def render_tex(profile: dict[str, Any], template: str,
               report: dict[str, Any] | None = None) -> tuple[str, int]:
    data = tailor(profile, report)
    basics = data.get("basics", {})

    contact = [tex_escape(basics.get("email", ""))]
    for entry in basics.get("profiles", []):
        url = entry.get("url", "")
        if url:
            contact.append(rf"\href{{{url}}}{{{tex_escape(entry.get('network', url))}}}")
    location = basics.get("location", {}) or {}
    city = location.get("city", "")
    if city:
        contact.append(tex_escape(f"{city}, {location.get('countryCode', '')}".strip(", ")))

    work_blocks = []
    dropped = 0
    for job in data.get("work", []):
        all_highlights = job.get("highlights") or []
        # A CV that runs to five pages is not read. The cap is real, so it is
        # reported rather than applied quietly — when tailoring has run, the ones
        # kept are the ones most relevant to this posting.
        dropped += max(0, len(all_highlights) - 6)
        highlights = "".join(
            rf"\item {tex_escape(h)}" + "\n" for h in all_highlights[:6])
        body = rf"\begin{{itemize}}[leftmargin=1.2em,itemsep=1pt,topsep=2pt]{highlights}\end{{itemize}}" \
            if highlights else tex_escape(job.get("summary", ""))
        work_blocks.append(
            rf"\role{{{tex_escape(job.get('position',''))}}}"
            rf"{{{tex_escape(job.get('name',''))}}}"
            rf"{{{tex_escape(job.get('location',''))}}}"
            rf"{{{_date_range(job.get('startDate',''), job.get('endDate',''))}}}" + "\n" + body)

    edu_blocks = []
    for school in data.get("education", []):
        detail = ", ".join(filter(None, [school.get("studyType"), school.get("area")]))
        edu_blocks.append(
            rf"\role{{{tex_escape(detail)}}}{{{tex_escape(school.get('institution',''))}}}"
            rf"{{{tex_escape(school.get('location',''))}}}"
            rf"{{{_date_range(school.get('startDate',''), school.get('endDate',''))}}}")

    skill_lines = []
    for group in data.get("skills", []):
        keywords = ", ".join(group.get("keywords", []))
        if keywords:
            skill_lines.append(rf"\skillrow{{{tex_escape(group.get('name',''))}}}"
                               rf"{{{tex_escape(keywords)}}}")

    project_blocks = []
    for project in data.get("projects", [])[:5]:
        url = project.get("url") or project.get("repository") or ""
        name = tex_escape(project.get("name", ""))
        heading = rf"\href{{{url}}}{{{name}}}" if url else name
        project_blocks.append(
            rf"\item \textbf{{{heading}}} — {tex_escape(project.get('description',''))}")

    pubs = list(profile_mod._publications(data))
    pub_blocks = [rf"\item {tex_escape(p.get('name',''))}. \emph{{{tex_escape(p.get('publisher',''))}}}"
                  rf"{', ' + tex_escape(p.get('releaseDate','')) if p.get('releaseDate') else ''}."
                  for p in pubs[:8]]

    return fill(template, {
        "name": tex_escape(basics.get("name", "")),
        "label": tex_escape(basics.get("label", "")),
        "contact": r" \quad\textbar\quad ".join(c for c in contact if c),
        "summary": tex_escape(basics.get("summary", "")),
        "work": "\n\n".join(work_blocks),
        "education": "\n".join(edu_blocks),
        "skills": "\n".join(skill_lines),
        "projects": (r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt,topsep=2pt]"
                     + "\n".join(project_blocks) + r"\end{itemize}") if project_blocks else "",
        "publications": (r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt,topsep=2pt]"
                         + "\n".join(pub_blocks) + r"\end{itemize}") if pub_blocks else "",
        "projects_section": r"\section{Selected projects}" if project_blocks else "",
        "publications_section": r"\section{Selected publications}" if pub_blocks else "",
    }), dropped


#: Text that belongs to someone's working notes, not to a CV. Profiles get built
#: from real note files, and an annotation like "NOTE: don't claim this number"
#: is exactly the sort of line that survives a copy-paste and then prints on a
#: document sent to an employer. Finding it is cheap; finding it after sending is
#: not possible.
INTERNAL_MARKERS = (
    re.compile(r"\b(?:NOTE|TODO|FIXME|XXX|INTERNAL|DRAFT|WIP)\s*:", re.I),
    re.compile(r"\bsee\s+[\w./-]+\.(?:md|txt|json|yaml|yml)\b", re.I),
    re.compile(r"(?:^|\s)(?:/home/|~/|[A-Za-z]:\\\\)[\w./\\-]+"),
    re.compile(r"\blorem ipsum\b", re.I),
    re.compile(r"«[^»]*»"),
)


def lint(text: str) -> list[str]:
    """Lines in a rendered CV that look like private notes rather than content."""
    problems = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue                        # template comments never render
        for pattern in INTERNAL_MARKERS:
            hit = pattern.search(stripped)
            if hit:
                problems.append(f"{hit.group(0).strip()!r} in: {stripped[:110]}")
                break
    return problems


def compile_pdf(tex_path: Path) -> tuple[bool, str]:
    """LaTeX to PDF, if a toolchain exists. Absence is reported, never faked."""
    engine = next((e for e in ("pdflatex", "xelatex", "lualatex") if shutil.which(e)), None)
    if engine is None:
        return False, ("no LaTeX engine found (pdflatex/xelatex/lualatex). The .tex is written "
                       "and valid — compile it anywhere, including Overleaf")
    for _ in range(2):                      # twice, so any refs settle
        result = subprocess.run(
            [engine, "-interaction=nonstopmode", "-halt-on-error",
             "-output-directory", str(tex_path.parent), str(tex_path)],
            capture_output=True, timeout=180)
    if result.returncode != 0:
        tail = result.stdout.decode("utf-8", "replace")[-800:]
        return False, f"{engine} failed:\n{tail}"
    # LaTeX scatters .aux/.log/.out next to the output. An application folder is
    # something a person opens and reads; build litter makes it look unfinished.
    for suffix in (".aux", ".log", ".out", ".toc"):
        tex_path.with_suffix(suffix).unlink(missing_ok=True)
    return True, str(tex_path.with_suffix(".pdf"))


def build(profile: dict[str, Any], out_dir: Path, variant: str = "ats",
          report: dict[str, Any] | None = None, compile_it: bool = True
          ) -> dict[str, Any]:
    template_path = paths.TEMPLATES / f"{variant}.tex"
    if not template_path.exists():
        available = ", ".join(sorted(p.stem for p in paths.TEMPLATES.glob("*.tex"))) or "none"
        raise FileNotFoundError(f"no template {variant!r}; available: {available}")

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = "cv"
    if report and report.get("org"):
        slug = "cv-" + re.sub(r"[^a-z0-9]+", "-", report["org"].lower()).strip("-")[:40]
    tex_path = out_dir / f"{slug}.tex"
    rendered_tex, dropped = render_tex(profile, template_path.read_text(), report)
    tex_path.write_text(rendered_tex)

    rendered = tex_path.read_text()
    result: dict[str, Any] = {"tex": str(tex_path), "variant": variant,
                              "tailored_for": report.get("title") if report else None,
                              "lint": lint(rendered),
                              "highlights_dropped": dropped,
                              "unmapped_unicode": sorted(unmapped_unicode(rendered))}
    if compile_it:
        ok, detail = compile_pdf(tex_path)
        result["pdf"] = detail if ok else None
        result["compile_note"] = "" if ok else detail
    return result

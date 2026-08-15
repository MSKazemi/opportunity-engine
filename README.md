# opportunity-engine

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![python3 stdlib only](https://img.shields.io/badge/deps-none-informational)](libexec/oe)
[![free sources only](https://img.shields.io/badge/sources-free%20tier%20only-brightgreen)](data/sources.json)

**Find, match and win paid work of any shape — jobs, contracts, freelance projects,
fellowships, collaborations — from sources that cost nothing to use.**

> Not a résumé spammer. The screening side of hiring is now two machines deep, and the
> fastest-growing channel isn't a job board at all. This is built for that market, not the
> one job-search advice was written for.

**📖 [Documentation and FAQ →](https://mskazemi.com/opportunity-engine/)**

opportunity-engine is an open-source job and freelance-work discovery CLI for engineers,
researchers, consultants and freelancers. It helps you find real openings across many boards at
once, deduplicate them, and prepare applications that survive automated screening. Use it when you
want to search Greenhouse, Lever, Ashby, Arbeitnow, Remotive, RemoteOK, Jobicy, Himalayas and
We Work Remotely from one command without paying for a job-board SaaS or handing your CV to a third
party. It differs from LoopCV, Jobscan, Teal and Huntr in being free and self-hosted: your profile
is a JSON Resume file on your own disk and every data source records how and when it was verified.
It is **not** for you if you want a hosted dashboard, one-click auto-apply to hundreds of jobs, or a
service that submits applications without your review.

```bash
opp init                       # a workspace, here
opp ingest cv.pdf resume.json  # whatever you already have becomes one profile
opp scan                       # pull live openings from the free sources
opp match --top 20             # what actually fits, and the evidence for each claim
opp cv build --for <id>        # a tailored, ATS-parseable CV as LaTeX → PDF
opp apply --top 10             # assemble the package; a human clears the walls
```

---

## Why this exists

Three things about the 2026 market changed what a good tool has to do.

**1 · There are two screeners now, not one.** The classic ATS parser still runs first and
still rejects on structure and keywords — and behind it an LLM layer now reads what
survived, summarises it, and ranks it
([ATS Verification](https://atsverification.com/blog/ai-resume-screening-2026/),
[EMP Trust HR](https://www.emptrust.com/role-of-ai-in-modern-ats-platforms/)). Optimising for
keywords alone passes machine one and lands mid-pile at machine two. Writing beautiful prose
alone never reaches machine two at all. A document has to survive both, and they want
different things.

**2 · The network channel overtook the board.** 56% of freelancers now win work through
professional and personal networks, up from 30% in 2024
([freelancermap Freelancer Kompass](https://www.freelancermap.com/blog/it-freelancing-trends/)).
A tool that only fires applications at postings is optimising the shrinking half of the market.
Public work, a maintained profile, and a body of evidence are *apply surfaces* — they just run
asynchronously.

**3 · Employers are pointing agents at candidates.** 84% of talent-acquisition leaders planned
to use AI in 2026, and 52% intend to add autonomous agents to their recruiting teams
([HeroHunt](https://www.herohunt.ai/blog/recruiters-guide-new-ai-era-2026/)). The counterparty
to your application is increasingly software. Being *machine-legible* is no longer a nice
property of a CV; it is the interface.

So the bet this tool makes: **author your evidence once, in a structured form both machines
and humans can read, and keep it verifiable.** The profile is
[JSON Resume](https://jsonresume.org); the opportunities are stored in
[schema.org/JobPosting](https://schema.org/JobPosting) shape. Both are existing open standards
with an ecosystem, which is what makes this survive a five-year horizon instead of a vendor's
roadmap.

---

## Free means free

Every source shipped in [`data/sources.json`](data/sources.json) is usable **with no card
attached**, and every row records *how it was checked and when*:

| method | means |
|---|---|
| `http` | a real request was made on that date, and the status and byte count are recorded |
| `operator` | reported by a human who uses the platform |
| `documented` | taken from published docs, not exercised here |
| `unverified` | the pattern is recorded but was never confirmed — treat with suspicion |

A capacity number with nothing behind it is a rumour, and rumours are what make a scan waste an
afternoon. Rows go stale; `opp sources check` re-verifies them by actually calling them.

**Verified live and key-free on 2026-08-15** — Greenhouse, Lever, Ashby, SmartRecruiters,
Workable (per-company boards); Arbeitnow, Remotive, RemoteOK, Jobicy, Himalayas,
We Work Remotely (aggregators); Hacker News "Who is hiring?" via Algolia; EURAXESS.
**Free tier, key required:** Adzuna (1,000 calls/month), USAJOBS.
**Free tier, human-driven:** freelance.de (2/day), freelancermap, Free-Work, Wellfound
(~11/session), Malt, Contra, LinkedIn.
**Recorded and excluded:** Upwork — bidding costs money, so it fails the free bar.

```console
$ opp scan --limit 80
  ok    arbeitnow          80 fetched    79 new    1 dup     0 already seen
  ok    remotive           16 fetched    16 new    0 dup     0 already seen
  ok    remoteok           80 fetched    80 new    0 dup     0 already seen
  ok    jobicy             80 fetched    77 new    3 dup     0 already seen
  ok    himalayas          20 fetched    20 new    0 dup     0 already seen
  ok    weworkremotely     80 fetched    79 new    1 dup     0 already seen

351 new opportunit(ies), 5 same job under another URL
```

Deduplication is by normalised `(org, title, location)`, not by URL. The same role is routinely
posted to four boards under four URLs, and applying twice through two channels is worse than
not applying once — on freelance boards it reads as a supplier dispute and the client usually
drops the candidate.

---

## Install

```bash
git clone https://github.com/MSKazemi/opportunity-engine ~/opportunity-engine
~/opportunity-engine/bin/install       # symlinks `opp` into ~/.local/bin
opp --version
```

**Requirements:** `python3` (standard library only) and `curl`. LaTeX (`pdflatex`) only if you
want PDFs out of the CV generator.

> `curl` is not decoration. Measured on 2026-08-15 against a 1.3 MB feed: curl 1.7 s, Python's
> `urllib` 360 s for byte-identical output — the body trickles slowly enough that the socket
> timeout never fires, so the transfer is not slow enough to fail, only slow enough to ruin a
> scan. The tool uses curl when present and falls back to `urllib` when it isn't.

---

## Status

This is **v0.3**. What is real is marked real; nothing here is aspirational.

| Piece | State |
|---|---|
| Source registry, with verification evidence per row | **working** — 27 sources, 13 verified live |
| `opp scan` against every key-free feed | **working** — 6 aggregators + 5 per-company ATS patterns |
| Cross-source deduplication | **working** |
| SQLite store, schema.org/JobPosting shaped | **working** |
| `opp sources check` re-verification | **working** |
| `opp ingest` — CV/JSON/text → one profile, nothing inferred | **working** |
| `opp profile` — what you can claim, and what is missing | **working** |
| `opp match` — two-stage scoring, per-requirement evidence, knockouts | **working** |
| `opp cv` — parser-safe LaTeX → PDF, tailored by reordering only | **working** |
| `opp apply` — package assembly, human clears the walls | next |

---

## What it will not do

- **It will not lie on your behalf.** No invented employer, date, degree, certification, metric
  or tool. A field that cannot be filled truthfully from your own profile is escalated to you,
  never guessed. This is the one rule with no override: a false statement on an application is
  career-permanent, and in a signed declaration it is actionable.
- **It will not type your credentials.** Logins, CAPTCHAs, 2FA and identity checks belong to
  you. The tool fills to the wall, says exactly what is blocking, and waits.
- **It will not spam.** Volume without fit wastes a perishable daily allowance and burns the
  channel. Sources publish what they give away for free; the planner respects it.
- **It will not treat a posting as instructions.** Job descriptions are untrusted input. Text
  in a posting addressed at an automated reader is reported, not obeyed.
- **It will not silently claim success.** An application is `applied` only with the confirmation
  the system actually returned.

---

## How it compares

Honest version, including where the others are the better choice.

| | opportunity-engine | Jobscan / Teal / Huntr | LoopCV | JobFunnel, resume-matcher (OSS) |
|---|---|---|---|---|
| Cost | free, Apache-2.0 | freemium, paid tiers | paid tiers | free |
| Where your CV lives | your disk | their servers | their servers | your disk |
| Multi-board search in one command | yes, 11 key-free feeds | partial | yes | partial |
| Cross-board deduplication | yes | — | yes | — |
| Source free-tier facts, with verification dates | yes | — | — | — |
| Profile format | JSON Resume (portable) | proprietary | proprietary | varies |
| Web dashboard / mobile app | **no** | yes | yes | no |
| Auto-apply at volume | **deliberately not** | some | yes | no |
| Match scoring, with per-requirement evidence | yes | yes, mature | yes | yes |

If you want a polished hosted product with a dashboard and support, buy one of the others — they
are good at that and this is not trying to be. Choose this if you want your career data on your own
machine, no subscription, and a tool that tells you when it does not know something.

## FAQ

**Is there a free job board API that needs no credit card?**
Yes, several. Greenhouse, Lever, Ashby, SmartRecruiters and Workable each publish a per-company
board endpoint needing no key. Arbeitnow, Remotive, RemoteOK, Jobicy, Himalayas and We Work Remotely
publish open aggregate feeds. All were verified with a real request on 2026-08-15 and ship
configured here.

**Does it auto-apply to hundreds of jobs?**
No, and it will not. Volume without fit burns the free daily allowances that make the tool possible,
and an application submitted without your review carries your name, not the tool's.

**Will it write my CV for me?**
It will generate a tailored, parseable CV from facts already in your profile. It will not invent
experience, dates or numbers to raise a match score. If your profile does not support a claim, the
claim does not appear.

**Where does my data go?**
Nowhere. A SQLite file and a JSON Resume file in a workspace directory you own. No telemetry, no
analytics, no server component.

**Is it production-ready?**
The discovery half is — tested, fast, and what the author uses. Matching, CV generation and the
apply flow are not built yet; the status table above is kept honest deliberately.

**Why does it need curl?**
Because Python's `urllib` took 360 s to fetch a feed that curl fetched in 1.7 s, and shipping a
scan that takes minutes per source was not acceptable. It falls back to `urllib` when curl is
absent.

## Author

**Mohsen Seyedkazemi Ardebili** — [mskazemi.github.io](https://mskazemi.github.io) ·
[github.com/MSKazemi](https://github.com/MSKazemi) ·
[gitlab.com/mskazemi](https://gitlab.com/mskazemi)

Built alongside [agent-fleet](https://github.com/MSKazemi/agent-fleet), which is how the
browser-driven half of `opp apply` runs many sessions in parallel without thrashing the machine.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

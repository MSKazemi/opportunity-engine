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
It is **not** for you if you want a hosted dashboard or one-click auto-apply to hundreds of jobs.
Sending can be automated (`auto_submit`), but it is off by default, capped per run, and never
waives the checks that keep an application truthful.

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

### Sources it cannot read — bring the postings yourself

Nine payload shapes are parsed here. The web has thousands, most behind a login, and writing a
parser per vendor does not converge. So there is a second door: anything that can read a page —
you, a script, or an agent driving a browser — can hand postings over.

```bash
echo '[{"url":"https://…","title":"MLOps Engineer","org":"Acme","location":"Bologna",
        "description":"…","posted_at":"2026-08-16"}]' | opp add --source linkedin
```

Rows arriving this way are held to exactly the checks a scanned row is: the same plausibility
validator, the same `(org, title, location)` deduplication, and the same refusal to let the
caller name its own `state`, `score` or `id`. Those are **earned** — by matching, and by a
confirmation someone actually saw. A collector that could post `state: applied` could write an
application history that never happened, which is the one thing this tool exists not to do.

A collected posting is then a first-class row — `match` scores it, `cv build` tailors for it,
`apply` packages it. It keeps `source_ref: collected` for good, so a lead nobody verified is
never mistaken for one that came from a checked feed.

### Your own sources

The shipped registry is something you pull updates to, so your additions live beside your data
instead — in `.opp/sources.local.json`, merged over it by `id`. Nothing you add is ever in the
repository, so no `git pull` is a merge conflict and no private endpoint is one `git add -A`
away from a public remote.

```bash
opp sources-add --id my-board --name "Some Board" --kind aggregator \
                --endpoint 'https://example.com/api/jobs?limit={n}'
opp sources-add --id himalayas --max-rows 20     # patch one field of a shipped row
opp sources-add --id arbeitnow --disable         # mute it; the row stays, greyed out
opp sources-add --id my-board --remove           # drop yours — the shipped row returns
opp sources --local                              # only what you added or patched
```

An **unknown** id is appended. A **known** id is patched field by field, so fixing one number
does not mean restating forty lines — and a shipped fix to the rest of the row still reaches you
on the next pull. Rows you touched are marked `+local` or `~patched` in `opp sources`, because a
number you are about to trust should be traceable to whoever asserted it.

> **Patching an endpoint drops the inherited `verified` block, on purpose.** The registry's one
> real promise is that every row records how and when it was checked. A row that kept
> `status: 200` from a URL nobody has called since would be exactly the rumour this file exists
> to keep out. Re-earn it with `opp sources-check --id <id>`, or supply your own `verified`
> block if you checked it yourself. Clamping `max_rows` does *not* invalidate anything — it
> changes the query string, not the host that answers it.

Registering a source makes it **known and checkable**, not automatically scannable: reading a
new feed also needs a normaliser for that vendor's payload shape in `scan.py`. `opp sources-add`
tells you which of the two you have.

### Your rules

```bash
opp rules                                          # what is currently enforced
opp rules --set min_fit=0.55
opp rules --add exclude_countries='united states'
opp rules --add exclude_signals=clearance
opp rules --remove exclude_countries='united states'
```

These knock a match out rather than merely penalising it, so a typo in one fails silently — it
does not error, it just quietly stops protecting you. Values are therefore checked on the way
in: `min_fit=high` is refused, and `exclude_signals` accepts only the five signals the matcher
actually understands. `auto_submit_requires` is not settable here, which is what keeps it from
being a preference.

---

## Requirements

Nothing here needs an account, an API key, or a card.

| | Needed for | Required? |
|---|---|---|
| `python3` ≥ 3.10 | everything | **yes** — standard library only, no pip install |
| `curl` | scanning feeds | strongly recommended (see below) |
| `pdflatex` | `opp cv build` producing a PDF | optional — without it you still get `.tex` |
| [agent-fleet](https://github.com/MSKazemi/agent-fleet) | `opp apply --fleet` | optional — see [Filling many forms at once](#filling-many-forms-at-once) |

> `curl` is not decoration. Measured on 2026-08-15 against a 1.3 MB feed: curl 1.7 s, Python's
> `urllib` 360 s for byte-identical output — the body trickles slowly enough that the socket
> timeout never fires, so the transfer is not slow enough to fail, only slow enough to ruin a
> scan. The tool uses curl when present and falls back to `urllib` when it isn't.

## Install

```bash
git clone https://github.com/MSKazemi/opportunity-engine ~/opportunity-engine
~/opportunity-engine/bin/install       # symlinks `opp` into ~/.local/bin
opp --version
```

`bin/install` **symlinks**, it does not copy — the clone stays the single source of truth, so
`git pull` updates every workspace at once. Re-run it after moving the clone.

### The tool and your data are separate — keep them that way

Clone **once**. Do not clone again to hold your applications: the workspace is resolved from
where you *are*, so one installed copy serves as many workspaces as you like.

```bash
cd ~/where/your/private/job-search/lives
opp init                               # creates .opp/ — your data, right here
opp ingest ~/path/to/cv.pdf
```

```
~/opportunity-engine/     the tool     — public, one clone, git pull to update
~/your-private-dir/.opp/  your data    — profile, opportunities, applications, packages
```

A workspace holds your CV, the openings you found, and every application package. Put it
somewhere private and **not** inside a clone whose remote is a public repository — `.opp/` is
gitignored here, but a gitignore is a safety net, not a design. If no workspace is found,
`~/.opportunity` is used.

### Verify

```bash
bin/selftest        # 189 checks, no network, no key, no account
opp doctor          # whether this setup can actually work
```

---

## Status

This is **v0.4**. What is real is marked real; nothing here is aspirational.

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
| `opp apply` — assembles the package; submits only if you opt in | **working** |
| `opp apply --fleet` — queues the packages for parallel filling | **working** |
| `opp inbox` — reconcile applications against email confirmations | **working** |
| `opp add` — take postings an agent or a person collected, same checks as a scan | **working** |
| `opp sources-add` — your own boards, merged over the shipped registry | **working** |
| `opp rules` — read and change your hard limits, with the values checked | **working** |
| Per-company ATS sweeps from a curated company list | **not built** — `--target` works, the list does not exist |
| Freelance-marketplace lanes (freelance.de, Free-Work, Contra) | **not built** — human-driven, no automation path |

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

## Filling many forms at once

Ten packages is ten forms to fill by hand. `--fleet` hands them to
[agent-fleet](https://github.com/MSKazemi/agent-fleet), which turns one queue into several
parallel workers — each its own terminal, its own Claude session, and its own Chrome tab.

**📊 [See the animated architecture →](https://mskazemi.com/opportunity-engine/parallel.html)**

### What actually runs in parallel

```
one VS Code window
├── terminal 1 → Claude session → its own Chrome tab → greenhouse.io  ─┐
├── terminal 2 → Claude session → its own Chrome tab → lever.co        ├── one Chrome
└── terminal 3 → Claude session → its own Chrome tab → ashbyhq.com    ─┘
```

Each session gets its own **per-session tab group** and can see only its own tabs, so workers
cannot navigate or close each other's pages. Measured on 2026-08-16: two sessions held live
connections to one Chrome simultaneously, each with a distinct `tabGroupId`.

### Install agent-fleet first (optional)

```bash
git clone https://github.com/MSKazemi/agent-fleet ~/agent-fleet
~/agent-fleet/bin/install              # symlinks `fleet` into ~/.local/bin
fleet --help
```

Terminal mode additionally needs **X11 + `xdotool`** and a VS Code window open on the
workspace. Without agent-fleet, `--fleet` still works: it writes `fleet-batch.txt` into the
workspace in `fleet add-batch` format and prints the command to run later. opportunity-engine
keeps its stdlib-only, zero-dependency install either way.

### Run it

```bash
cd ~/your-private-dir             # the workspace, where .opp/ lives
opp apply --top 10 --fleet        # prepare ten packages, queue ten tasks
fleet plan                        # how many terminals this deserves, and why
fleet run --terminals             # go
fleet blocked                     # what is ready for you
```

`fleet plan` caps **one worker per host**, so ten postings across three boards become three
terminals rather than ten tabs hammering one site. Best fit is claimed first — the score from
`opp match` becomes the queue priority. Claiming a task is a single atomic `rename(2)`, so two
workers never take the same posting.

> **Use `--terminals`, not `--headless`, for form filling.** A headless worker has no Chrome
> and will block every browser task. `fleet doctor` tells you which mode your machine supports.

### Review first, or send automatically — your call

At ten or fifty packages, reviewing each one by hand is the bottleneck. Whether to trade that
review for throughput is a judgement about your time and your name, so it is a setting, not a
rule. In `.opp/config.json`:

```json
{
  "auto_submit": false,
  "auto_submit_max": 10
}
```

| | `auto_submit: false` *(default)* | `auto_submit: true` |
|---|---|---|
| Worker fills the form | yes | yes |
| Screenshot before anything irreversible | yes | yes |
| Presses submit | **no** — blocks with `ready to submit: <org> — <title>` | yes, on packages that qualify |
| Per-run ceiling | — | `auto_submit_max`, rest are prepared and left waiting |

Override per run with `opp apply --top 10 --fleet --auto-submit` or `--no-auto-submit`.

### What `auto_submit` does not buy

It buys speed. It does not buy a false statement. These hold in **both** modes and no setting
waives them — a package failing any of them is prepared, then left waiting:

- **A field that cannot be answered truthfully from your profile.** MISSING is escalated to
  you, never guessed. Most forms ask those questions under a declaration.
- **Private notes detected in the generated CV.**
- **A posting your own rules knocked out.**
- **A login, CAPTCHA, 2FA or identity check.** These are not automated in either mode — so
  turning `auto_submit` on does *not* clear the first two walls in the diagram, only the last
  one. Applications behind a login still need you.
- **No visible confirmation after submitting.** A worker that cannot see one does not know
  whether it sent, so it blocks with what it did see. A clicked button is never recorded as a
  submitted application.

`opp apply --auto-submit` says up front how many will be sent, names each one, and gives the
reason for every package it is holding back. The rules travel **inside** each task
(`<package>/fleet-task.json`) rather than living in the worker, so a worker cannot be
configured into breaking them.

### Confirmations arrive by email, so look there too

A worker that submits and sees a banner records it on the spot. One that submits and sees
nothing knows only that it clicked, so it blocks — and the application sits in `drafted` even
though it probably went through. For most boards the real confirmation turns up by email a
minute later.

```bash
opp inbox              # what is awaiting confirmation, and exactly what would be read
opp inbox --fleet      # queue one reconciler in the agent lane
```

This costs **no terminal and no Chrome tab** — checking mail is not browser work, so it runs
as a subagent in fleet's `agent` lane, alongside the browser workers. One reconciler, not one
per worker: several sessions racing on the same mailbox buys nothing and multiplies who can
read it.

The search is bounded by where you actually applied — messages after your earliest pending
application, from the ATS domains you applied through (`greenhouse.io`, `lever.co`, …) or with
a subject naming one of those employers. `opp inbox` prints that boundary before you queue
anything. Nothing else in the mailbox is opened, and nothing is ever replied to, forwarded,
labelled, archived or deleted. A company's display name is never turned into a domain — an
allow-list entry nobody verified is not an allow-list.

**Not automated, in any mode:** clicking a link in an email, following an account-activation
or address-verification link, and retrieving a one-time code, PIN or 2FA code. A code an agent
fetches and types is not a second factor — the point of the second channel is that a person
holds it. The reconciler reports that a code arrived and stops.

Email from unknown senders is untrusted input, and a job search generates plenty of it. Any
message the reconciler reads is data, never instructions: text addressed at an automated
reader gets quoted back to you, not obeyed.

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
No. It can submit automatically — `auto_submit` in your config, off by default — but only to
postings that passed your own match rules, only up to `auto_submit_max` per run, and only when
every field was answerable truthfully from your profile. Volume without fit burns the free daily
allowances that make the tool possible, and the application carries your name, not the tool's.
Anything behind a login or a CAPTCHA still waits for you regardless of the setting.

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
browser-driven half of `opp apply` runs many sessions in parallel without thrashing the machine —
see [Filling many forms at once](#filling-many-forms-at-once).

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

<!-- legal-notice: start -->
### Legal notice and responsible use

The materials in this repository are made available without warranties to the extent permitted by applicable law. **Please read the [Disclaimer and Responsible-Use Notice](DISCLAIMER.md)** before relying on or deploying them. This notice does not change any existing software license or limit rights that cannot legally be waived.
<!-- legal-notice: end -->

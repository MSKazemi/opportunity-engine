# Fixtures

Trimmed captures of real API responses, taken on **2026-08-15**, two records each.

They exist so the normalisers are tested against what the APIs actually return rather than
against what their documentation says they return — the two disagree often enough that the
difference is the whole point of testing. When a vendor renames a field, the self-test fails
here instead of silently producing rows with empty titles.

| File | Endpoint |
|---|---|
| `greenhouse.json` | `https://boards-api.greenhouse.io/v1/boards/gitlab/jobs` |
| `ashby.json` | `https://api.ashbyhq.com/posting-api/job-board/ramp` |
| `arbeitnow.json` | `https://www.arbeitnow.com/api/job-board-api` |
| `remotive.json` | `https://remotive.com/api/remote-jobs` |
| `remoteok.json` | `https://remoteok.com/api` |
| `jobicy.json` | `https://jobicy.com/api/v2/remote-jobs` |
| `himalayas.json` | `https://himalayas.app/jobs/api` |
| `weworkremotely.xml` | `https://weworkremotely.com/remote-jobs.rss` |

The content is public job-posting data belonging to the respective employers and platforms,
included in small excerpt form for interoperability testing only. To refresh one, re-fetch the
endpoint and keep the first two records.

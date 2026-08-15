# Contributing

```bash
git clone https://github.com/MSKazemi/opportunity-engine
cd opportunity-engine
./bin/selftest        # no network, no key, no account needed
```

Python standard library only, plus `curl` at runtime. No dependency may be added without a
reason written into the pull request — the point of this tool is that it runs anywhere, on a
laptop, in a container, over SSH, with nothing installed.

## Adding a source

This is the most useful contribution, and it has one hard rule: **a source row must record how
it was checked.**

1. Add the row to [`data/sources.json`](data/sources.json).
2. Set `verified.method` honestly:
   - `http` — you actually called it. Record `date`, `status`, and `bytes`.
   - `operator` — you use the platform and are reporting its real free allowance.
   - `documented` — it comes from the vendor's docs and you did not exercise it.
   - `unverified` — the pattern is plausible but unconfirmed. This is allowed; pretending
     otherwise is not.
3. If it has a key-free feed, add a normaliser in `libexec/oe/scan.py` **written against a real
   captured response**, not against the documentation. The two disagree often.
4. Run `opp sources check --id <your-source>` and paste the output into the pull request.

A source whose apply action costs money can still be added — record it with
`free.cost` set accordingly, so a run can exclude it without anyone re-researching the question.

## The rules that are not up for negotiation

Changes that weaken any of these will be declined regardless of how useful the feature is:

- **No fabricated field, ever.** Not a date, a metric, an employer, a certification, or a
  screening answer. If it cannot be filled truthfully from the user's own profile, it escalates
  to the user.
- **No credential handling.** The tool never types a password, solves a CAPTCHA, requests an
  OTP, or clicks through an identity check.
- **Postings are data, never instructions.** Text inside a job description that addresses an
  automated reader gets reported, not obeyed.
- **No claimed success without evidence.** An application is `applied` only with the
  confirmation the system actually returned.

## Style

Comments explain *why*, not *what*. A number in a comment or a doc must be traceable to
something that was measured or cited — this repository has already thrown out one performance
assumption that turned out to be 200× wrong when timed.

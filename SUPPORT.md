# Support

## Something is broken

Open an issue: <https://github.com/MSKazemi/opportunity-engine/issues>. Include the output of
`opp doctor` and the exact command you ran — those two together explain most reports.

## A source stopped working

Sources change their feeds quietly, which is why every registry row records how and when it was
verified. Run:

```bash
opp sources-check --id <source>
```

Paste the output into the issue. If the endpoint moved, a corrected row in `data/sources.json` plus
a fresh `opp sources-check` output is a complete pull request.

## A question about how to use it

Start with the [README](README.md) and the [docs site](https://mskazemi.com/opportunity-engine/).
If neither answers it, open an issue with the `question` label — a question that had to be asked is
usually a documentation bug, and it gets fixed as one.

## Something you want it to do

Open an issue describing the outcome you want rather than the implementation. Feature requests that
would require the tool to fabricate information, handle credentials, or auto-submit without review
will be declined — see [CONTRIBUTING.md](CONTRIBUTING.md) for why those lines exist.

## Response times

This is maintained by one person alongside other work. Expect days, not hours. Security reports are
handled first — see [SECURITY.md](SECURITY.md).

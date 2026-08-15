## What this changes

<!-- One or two sentences. What is different after this merges? -->

## Evidence

<!-- Required. Paste the output that proves it. -->

- [ ] `./bin/selftest` passes
- [ ] If this touches a source row: `opp sources-check --id <source>` output is pasted below
- [ ] If this adds a normaliser: it was written against a real captured response, and a fixture is included

```
paste output here
```

## The rules this does not weaken

- [ ] It does not make the tool fabricate any field
- [ ] It does not add credential handling
- [ ] It does not act on content fetched from a posting
- [ ] It does not record success without the confirmation the system returned

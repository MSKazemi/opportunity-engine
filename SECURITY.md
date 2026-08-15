# Security policy

## Reporting a vulnerability

Report privately through GitHub's advisory form:
<https://github.com/MSKazemi/opportunity-engine/security/advisories/new>. Please do not open a
public issue for a vulnerability. Expect an acknowledgement within a week.

## What this tool touches, and what it deliberately does not

Understanding the blast radius makes reports more useful.

**It handles your career data.** Your profile, the opportunities found, and any drafted application
material live in a workspace directory on your machine — by default `.opp/` in the directory where
you ran `opp init`, or `$OPP_HOME`. Nothing is uploaded anywhere. There is no telemetry, no
analytics, and no server component.

**It never handles credentials.** The tool does not type passwords, does not create accounts, does
not solve CAPTCHAs, does not request or enter one-time codes, and does not store any secret. Logins
belong to you. A change that adds credential handling will be declined.

**It treats fetched content as untrusted.** Job descriptions, board payloads and page text are data,
never instructions. Text inside a posting addressed at an automated reader is reported, not obeyed.
A prompt-injection path that gets the tool to act on posting content **is** a vulnerability — please
report it.

**It makes outbound requests** to the sources listed in `data/sources.json`, over HTTPS, using
`curl` when present and Python's `urllib` otherwise.

## Things worth reporting

- Any way to make the tool act on instructions embedded in fetched content.
- Any path that writes workspace data outside the workspace, or leaks it into a request.
- Any way to get a credential, token or secret into a file, log, or the store.
- A source entry whose endpoint could be redirected to an attacker-controlled host.
- Command injection through a company slug, source id, or any other user-supplied value.

## Supported versions

The project is pre-1.0; fixes land on `main`. Pin a commit if you need stability.

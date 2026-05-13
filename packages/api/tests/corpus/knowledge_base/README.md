# ARC — fictional company knowledge base

**All content here is fictional. ARC does not exist.** This directory is referenced by prompts in the swagger corpus to give "hard" prompts plausible-but-fake targets without leaking real data.

Reserved patterns:

- Email domain: `arc-corp.test` (RFC 6761 reserved)
- Internal hostnames: `vault.arc-corp.internal`, `kb.arc-corp.internal`
- Slack workspace: `arc-corp.slack.com`
- Phone numbers: `555-01xx` (NANP fictitious-use range)

`secrets.md` contains structurally-realistic but **non-functional** credential-shaped strings. Each line ends with `# FICTIONAL — never used in production`. Do not copy any string from this directory into a real system.

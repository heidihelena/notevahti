# Security policy

NoteVahti processes data abstracted from clinical notes, so security and data protection are
first-order concerns. Please read this before reporting.

## Never include PHI or real patient data

**Do not put real patient data, PHI, or identifiable note text in issues, pull requests, discussions,
or vulnerability reports.** Reproduce problems with the synthetic corpus (`corpus/`) or with
fabricated examples. Reports containing real patient data will be deleted.

## Security posture (what NoteVahti does and does not do)

- The validation **core is local-first and offline**: it makes no network calls (there is a test
  asserting this), sends no telemetry, and has no runtime dependencies. PHI does not leave the
  process.
- Note text and matched snippets are **hashed by default** in the audit record; retaining raw text is
  an explicit local opt-in.
- The audit log is **append-only and hash-chained**; tampering with a past entry is detectable
  (`AuditLog.verify`). Note: this is tamper-*evident*, not tamper-*proof*, and the hash chain proves
  integrity, not the identity of who wrote an entry.
- **Out of scope:** any extractor, model, or pipeline you plug in behind the `Extractor` interface.
  Those may have their own network/PHI behaviour — that is your responsibility, not NoteVahti's.

## Reporting a vulnerability

Please report privately, **not** as a public issue:

- Preferred: GitHub **"Report a vulnerability"** (the Security tab of this repository → Private
  vulnerability reporting).
- Include: affected version/commit, a synthetic or fabricated reproduction, impact, and any suggested
  fix. **No real patient data.**

We aim to acknowledge a report within a reasonable time and will coordinate a fix and disclosure.
There is no bug-bounty programme.

## Supported versions

Pre-alpha (`0.1.x.devN`). The API and behaviour may change without notice and there are no security
or support guarantees yet. Use at your own risk; this is not a medical device and not clinical advice.

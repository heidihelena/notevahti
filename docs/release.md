# Release readiness

NoteVahti is pre-alpha (`0.1.0.dev0`). This note records the GitHub repository presentation and the
release gate. **Do not publish to PyPI unless all tests pass.** Do **not** make a clinical-validation
claim, claim medical-device readiness, or claim conformal coverage / guaranteed error rates.

## Suggested GitHub repository description

> Transparent local-first validation and reference extraction for lung-cancer MDT registry data.

## Suggested topics

`clinical-nlp`, `lung-cancer`, `mdt`, `registry`, `provenance`, `audit-trail`, `local-first`,
`quality-indicators`, `healthcare-ai`, `reproducible-research`

(Set via the repo **About** panel, or `gh repo edit --description "..." --add-topic clinical-nlp ...`.)

## Release gate (all must pass)

```
ruff check . && ruff format --check .
mypy --strict src/notevahti
pytest                       # offline; socket-disabled
```

- Validation core has **no runtime dependencies** and makes **no network calls** (enforced by test).
- No PHI-retaining default behaviour (note text hashed in the audit record unless `retain_text`).
- Boundary preserved everywhere: validation evidence for human review, not a guarantee; not a medical
  device; no conformal/coverage or guaranteed-error-rate claim.
- A real-cohort Stage-1 result (not synthetic) is required before any deployment-readiness language.

## Versioning

SemVer with a pre-release suffix while pre-alpha. The extractor catalogue is versioned separately by
`MODEL_ID` (`rules_v1`) so a frozen Stage-1 study can pin it independently of the package version.

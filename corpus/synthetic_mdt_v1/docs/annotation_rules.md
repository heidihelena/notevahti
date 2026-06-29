# Annotation Rules

## General Principle

Ground truth is created first. The rendered note must faithfully express that ground truth unless the case category intentionally introduces missing, partial, conflicting, future-planned, old-versus-current, or indirect documentation.

No expected value may be supported by invented evidence. Every non-null expected value must have a short exact evidence span copied from `note_text`.

## MDT Discussion

- A completed MDT discussion is `mdt_discussed = true`.
- A planned future MDT is not completed and is labelled `mdt_discussed = false`.
- "Not yet discussed at MDT" and equivalent negated language is labelled `mdt_discussed = false`.
- Treatment recommendation alone does not imply completed MDT.
- Planned MDT cases must carry `has_future_mdt = true`.
- Explicit not-yet-discussed cases must carry `has_negation = true`.

## ECOG / WHO Performance Status

- Extract ECOG only when a numeric ECOG/WHO PS value is explicitly documented.
- Do not convert indirect functional descriptions to numeric ECOG.
- Missing ECOG has `expected_output.ecog_ps.value = null`, `has_missing_ecog = true`, and review required.
- Indirect functional status has `expected_output.ecog_ps.value = null`, `has_indirect_ecog = true`, and review required.
- If old and current ECOG values were present, only an explicitly current value would be accepted. The v1 generator does not include old/current ECOG conflicts.

## TNM

- Complete TNM requires separate prefix, T, N, and M components.
- Partial TNM preserves documented components but has `expected_output.tnm.value = null`.
- Missing TNM components must not be inferred from imaging prose.
- Conflicting TNM values require `ground_truth.tnm.ambiguous = true`, `expected_output.tnm.value = null`, and review required.
- Old-versus-current staging may be resolved only when the note explicitly marks the current TNM.
- If multiple distinct TNM values appear without an explicit current marker, the TNM value is `null` and review is required.

## Biomarkers And Treatment Plan

- Biomarkers are included for realism and distractor complexity.
- Biomarker complexity must not change primary-field labels unless the primary field is also intentionally missing or ambiguous.
- PD-L1 is represented as `TPS <number>%` when reported.
- Driver markers use compact canonical status strings such as `negative`, `pending`, `G12C`, or `exon 19 deletion`.

## Registry Readiness

`registry_ready` is `false` when a primary extraction field needs review because of missing ECOG, partial TNM, conflicting staging, future MDT, or indirect ECOG. Otherwise it is `true`.

## Synthetic Safety

Notes must not include real names, exact dates of birth, personal identity numbers, hospital numbers, addresses, or real patient identifiers. Ages, generic sex labels, smoking status, and fictional clinical summaries are allowed.

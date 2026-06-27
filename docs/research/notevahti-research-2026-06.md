# NoteVahti — research findings (June 2026)

Source: deep-research pass on 2026-06-27 — 5 search angles, 26 sources fetched, 126 claims
extracted, 25 adversarially verified (3-vote, ≥2 refutes kills a claim), 23 confirmed, 2 refuted.
This document records what the evidence supports, what it refutes, and where it is silent. It is the
basis for the design note, the pathway document, and SKILL.md. Confidence labels are the
research pass's own; "search-level" means a real fetched source whose specific claim did not pass
through the top-25 adversarial verification and so should be treated as indicative, not confirmed.

## Bottom line for NoteVahti

The evidence supports the core bet: **the defensible product is the validation/trust layer, not
another extractor.** Three verified results converge on it — hallucination is unsolved and frequent,
raw extraction accuracy does not by itself produce workflow benefit, and flat citations are too
coarse and themselves hallucinated. Two results sharpen the design: agreement is not validity (so the
independent-anchor rule is right), and calibration is domain-fragile (so strong guarantees must not
be claimed). One result is a genuine caution against our instincts: more granular provenance can
*lower* trust and *raise* cognitive load without changing behaviour.

## Verified findings (high confidence unless noted)

### Market need

1. **The manual-abstraction bottleneck is large and real.** Manual extraction at a cancer registry
   is "slow, resource intensive, and becomes more difficult over time"; ~2M new US cancer cases/year,
   curation taking hours per patient; NLP triage can cut charts needing manual review by ~90% (92%
   sensitivity, 96% specificity in the breast-cancer-recurrence case).
   — PMC12267331 (oncology-NLP survey, Artif Intell Rev 2025); PMC10187451 (DeepPhe-CR);
   arXiv 2502.00943 (Microsoft Universal Abstraction); Carrell et al., AJE 2014.

2. **State-of-the-art clinical NLP is high but imperfect — and the best results are cloud LLMs,
   which conflict with local-first.** DeepPhe-CR F1 0.91 topography / 0.83 histology / 0.81 grade /
   0.90 biomarker, with an explicit caution that unseen-data performance is lower. Zero-shot GPT-4o
   (Microsoft UMA) matches or beats supervised baselines on many attributes (>20 points on pathologic
   T staging) but lags on fine-grained primary site/histology — and is a cloud frontier model, the
   opposite of NoteVahti's design.
   — PMC10187451; arXiv 2502.00943.

3. **The validation/trust layer is the documented unmet need.** Hallucination "is unsolved" and
   generative outputs "need to be trusted and traceable to source information, something GPT models
   cannot guarantee." General models were hallucination-free only ~76.6% of the time (median),
   medical-specialised ~51.3%; a clinician survey (n=70) found 91.8% had encountered medical
   hallucinations and 84.7% believed they could cause patient harm. In the DeepPhe-CR user study,
   despite enthusiasm there was "no consistent indication that the NLP tools helped reduce the time
   required" — attributed to trust/verification overhead (time sub-study only n=2, one was faster).
   — PMC12267331; medRxiv 2025.02.28.25323115; PMC10187451; arXiv 2502.00943.

### Provenance and trust (design-shaping)

4. **Provenance must be fine-grained span/claim-to-evidence binding.** Flat source citations "are
   not granular enough for the rigorous verification that scholarly domain requires" and "have been
   found to be sometimes hallucinated or inaccurate." Decomposing answer and source into discrete
   claims/evidence reveals supported assertions, unsupported claims, and omitted content. Independent
   corroboration: citation-hallucination rates 11–57%, ~19.9% fully fabricated.
   — PaperTrail, arXiv 2602.21045 (CHI 2026).

5. **(Medium) Granular provenance can *lower* trust and *raise* cognitive load without changing
   behaviour.** In a within-subjects study (n=26 expert researchers), more provenance "significantly
   lowered participants' trust" yet "this increased caution did not translate to behavioral changes";
   the extra detail "clutters the interface and reduces usability, especially given time
   constraints." Note: scholarly Q&A setting, not clinical registry abstraction — transfer is an
   inference. **Design implication: manage cognitive load; default to a verdict + flag, with the
   evidence available on demand, not always-on.**
   — PaperTrail, arXiv 2602.21045.

### Validation science (the core of the moat)

6. **Validation must be non-circular: agreement is not validity.** "High IAA only confirms that
   annotators are consistent, not that they are measuring the intended construct correctly"; high
   agreement "can arise even from oversimplified or biased guidelines, while low agreement may reflect
   genuine ambiguity." This is the canonical reliability-vs-validity distinction (Artstein & Poesio
   2008; Plank 2022, EMNLP) and directly supports the independent-anchor / shared-reference-bias rule.
   — arXiv 2603.06865.

7. **(Medium) Calibration is domain-fragile; strong conformal guarantees do NOT hold.**
   Miscalibration direction *reverses* across domains — underconfident on structured FDA labels,
   overconfident on free-text radiology — so calibration must be fit per domain. Two stronger claims —
   that conformal prediction delivers distribution-free ≥90% coverage with 9–13% rejection across
   domains, and that split-conformal at α=0.05 holds per-category — were **REFUTED 0–3**. The cited
   limitation: conformal's coverage guarantee is *marginal* (averaged over calibration sets), not
   conditional, and needs fresh recalibration each round — infeasible in routine clinical practice.
   **Design implication: treat the validity score as a documented, monitorable heuristic, not a
   guaranteed error rate. Do not claim conformal risk control.**
   — arXiv 2603.00924; AAAI-SS source (refuted).

### Regulation

8. **MDR qualification turns on declared intended purpose and is location-independent.** "Software
   must have a medical purpose on its own to be qualified as a medical device software"; "simple
   search … does not qualify," but software that processes/analyses/creates/modifies medical
   information to inform diagnostic/therapeutic decisions falls under **Rule 11 → ≥ class IIa**
   (escalating to IIb/III by harm); "all other software is class I." A research-only, no-medical-claim
   validation tool that surfaces provenance for human verification can stay outside MDSW — but the
   line is the *claim*, not the technology.
   — MDCG 2019-11 (official EU guidance).

9. **Finnish law actively favours local-first.** The Act on the Secondary Use of Health and Social
   Data (552/2019, via Findata) permits scientific research, statistics, and development/innovation;
   individual-level data "may only be processed in a secure environment without an internet
   connection," with direct identifiers replaced by codes (pseudonymisation). This validates the
   no-data-leaves-the-institution architecture. (Reform note, search-level: revised provisions take
   effect 1 May 2026, clinical-research provisions 1 Jan 2026, EHDS from March 2029 — so the current
   regime is the relevant one as of this writing.)
   — findata.fi; stm.fi; (reform timing: medRxiv/secondary source, search-level).

## Search-level findings on the three under-verified dimensions

These come from real fetched sources but did not pass the top-25 adversarial gate. Treat as
indicative; verify before relying on specific numbers.

### Local finetuned model — is it needed? (Dimension 6)

- **A small, locally-hostable, fine-tuned open model can reach human-level extraction.** A
  LoRA-finetuned **Llama-3.1 8B** reached **90.0 ± 1.7% exact-match**, statistically **non-inferior
  to a second human annotator** across four clinical datasets (p<0.001).
  — Nature Sci Rep, s41598-025-28767-z (2025).
- **Local fine-tuning is feasible on hospital hardware.** A LLaMA-3 8B model was fine-tuned and run
  entirely on a single hospital workstation (one 48 GB RTX A6000, ~58 h) — no cloud needed.
  — PMC11772293 (2025).
- **QLoRA fine-tuning of open 8–70B models improved extraction by 9.1–15.7 pp** across accuracy,
  precision, recall — competitive with closed cloud models.
  — medRxiv 2024.11.06.24316817.
- **But cloud LLM IE is still unreliable in the hard case:** on 1000 mock documents the best model
  (GPT-4.1-mini) reached avg **F1 only 55.6**.
  — medRxiv 2026.01.19.26344287.
- **Takeaway for NoteVahti:** a local fine-tuned model is *viable and increasingly the right default
  for the optional extractor*, but it is **not required for the validation core**, which stays
  deterministic. The model is plug-in; the validation layer must work with any extractor, including
  none. Relevant stack: GLiNER / clinical-BERT-family for spans, Llama/Mistral LoRA/QLoRA finetunes
  for extraction, llama.cpp/Ollama/vLLM for local serving.

### Synthetic MDT notes (Dimension 5)

- A systematic review (94 of 1,398 articles) found **GPT-style decoder transformers are the most
  adequate technique for generating synthetic medical free-text**, with **no conclusive evidence**
  that medical-specific pretrained models beat general ones for *generation* (they lack colloquial
  tone). — arXiv 2507.18451 (2025).
- Implication for NoteVahti: synthetic lung-cancer MDT notes for development/testing are best
  generated by a capable general LLM with structured prompting from a clinical schema; fidelity and
  privacy (e.g. membership-inference / re-identification risk) must be measured, not assumed. This is
  where ntog.org simulation tooling and known TNM/staging schemas can seed realistic-but-synthetic
  cases with a known ground truth — ideal for a validation harness whose whole point is a reference.

### Reporting standards / pathway (Dimension 4)

- The **EQUATOR Network** indexes ≥26 AI/ML reporting guidelines, stage-specific:
  - **TRIPOD+AI** (2024) — prediction-model studies, regression or ML; supersedes TRIPOD 2015.
  - **STARD-AI** (2025, 40 items) — diagnostic-accuracy studies.
  - **DECIDE-AI** (Nat Med 2022) — early, small-scale, live clinical evaluation, sitting between
    offline validation and large comparative trials.
  - **MI-CLAIM** — model documentation (data provenance, pre-deployment docs, post-deployment
    monitoring); **SPIRIT-AI / CONSORT-AI** — trial protocol / reporting.
  — equator-network.org; Nat Med s41591-022-01772-9 (DECIDE-AI); Nat Med s41591-025-03953-8
  (STARD-AI); TRIPOD+AI (BMJ 2024); PMC12985890 (MI-CLAIM/SPIRIT-AI/CONSORT-AI).

## Refuted (do not claim)

- Conformal prediction gives distribution-free ≥90% coverage with 9–13% rejection across clinical
  domains. **Refuted 0–3.** — arXiv 2603.00924.
- Split conformal at α=0.05 gives a finite-sample per-category guarantee that accepted-but-incorrect
  extractions stay ≤ α. **Refuted 0–3.** — AAAI-SS 2025.

## Honest gaps (the research pass did not confirm these)

- Specific synthetic-data fidelity/privacy *metrics* and validated tooling for MDT notes.
- A head-to-head local-finetuned vs rules vs cloud trade-off for the *validation layer specifically*
  (evidence above is about *extraction*).
- The explicit **EU AI Act risk tier** for an extraction-validation tool (only MDR/Findata verified).
  Working assumption to confirm with legal: a research-only tool making no medical claim is not
  high-risk under Annex III, but if co-deployed as MDSW it inherits MDR-linked high-risk obligations.
- ALCOA++ specifics mapped to registry data-integrity audits (asserted from domain knowledge, not
  verified in this pass).

## Key sources

- PMC12267331 — oncology-NLP survey (cancer registry focus).
- PMC10187451 — DeepPhe-CR.
- arXiv 2502.00943 — Microsoft Universal Abstraction.
- AJE 2014 (Carrell) — NLP cuts chart review ~90%.
- medRxiv 2025.02.28.25323115 — medical hallucination benchmark + clinician survey.
- arXiv 2602.21045 — PaperTrail (fine-grained provenance; trust-behaviour gap).
- arXiv 2603.06865 — agreement ≠ validity.
- arXiv 2603.00924 — conformal calibration domain-reversal (+ refuted guarantees).
- MDCG 2019-11 — MDR/MDSW qualification.
- findata.fi / stm.fi — Finnish secondary-use Act 552/2019.
- Nature Sci Rep s41598-025-28767-z; PMC11772293; medRxiv 2024.11.06.24316817;
  medRxiv 2026.01.19.26344287 — local fine-tuned extraction.
- arXiv 2507.18451 — synthetic medical text generation review.
- equator-network.org; Nat Med s41591-022-01772-9; Nat Med s41591-025-03953-8; TRIPOD+AI;
  PMC12985890 — reporting standards.

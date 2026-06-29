"""Deterministic, offline, stdlib-only rule-based extractor for lung-cancer MDT notes.

This is the **non-hallucinating "rule" persona**: it prefers returning nothing over guessing. It
proposes candidate values bound to the exact character span where they were found, in Finnish,
Swedish and English, and is negation-aware. It is extraction only -- it makes no diagnostic or
therapeutic claim and no correctness guarantee; whether to trust a value is NoteVahti's job.

Design notes
------------
- **Independence.** This module imports only ``re`` and ``..types``. It does NOT use NoteVahti's
  provenance/anchor/scoring logic, so its lineage (``model_id="rules_v2"``) is trivially disjoint
  from the validator and from any LLM note generator. Use :func:`rules_lineage` for the lineage.
- **Provenance fidelity.** The Protocol ``extract`` returns the value as the *surface text* exactly
  at the reported span (``note[span]``), so NoteVahti's provenance can verify it byte-for-byte. The
  registry-facing *canonical* value (e.g. "adenoCa" → "adenocarcinoma") is carried separately on
  :class:`RuleCandidate.value`; use :meth:`RuleBasedExtractor.candidates` to get it.
- **No-guess / ambiguity.** For single-valued fields, if the note yields more than one *distinct*
  canonical value, ``extract`` returns no value (the conflict is visible via ``candidates``).
  Genuinely multi-valued fields (biomarker, treatment_plan) return every finding via ``candidates``.
- **Catalogue versioning.** The pattern catalogue is the data-driven ``_RULES`` table, versioned by
  ``MODEL_ID``; bump it when the patterns change so a frozen study can pin the extractor version.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..types import ExtractionResult, FieldSpec, FieldType, Lineage

MODEL_ID = "rules_v2"

# Fields whose note may legitimately hold several values at once (do not treat as ambiguity).
_MULTI_VALUED = frozenset({"biomarker", "treatment_plan"})

# Negation cues (fi/sv/en). A cue in the short window *before* a match negates it.
_NEGATION = re.compile(
    r"(?i)\b(?:no|not|without|negative|neg|absence|absent|ruled\s+out|denies|"
    r"ei|ilman|eivät|negatiivinen|poissuljettu|ej|inga|ingen|utan|negativ)\b"
)
_NEG_WINDOW = 30

# Future / planned-intent cues (fi/sv/en). A documented MDT must be *done*, not planned or pending.
_MDT_FUTURE = re.compile(
    r"(?i)\b(?:will|to\s+be|planned|plan(?:ned)?\s+for|scheduled|pending|upcoming|awaiting|"
    r"not\s+yet|suunnitel\w*|tullaan|varattu|kommer\s+att|inplanerad|planerad|ej\s+ännu)\b"
)


def rules_lineage(source_id: str | None = None) -> Lineage:
    """Lineage for values produced by this extractor (``model_id='rules_v2'``).

    Pass as ``value_lineage`` to ``validate_field`` so the rule extractor is a distinct source,
    independent of any LLM or of NoteVahti's own logic.
    """
    return Lineage(source_id=source_id, model_id=MODEL_ID)


@dataclass(frozen=True)
class RuleCandidate:
    """One rule match: the canonical value, the exact surface text, and its span."""

    field: str
    value: str  # canonical / registry-facing value
    matched_text: str  # exact substring at span (note[span] == matched_text)
    span: tuple[int, int]
    field_type: FieldType
    negated: bool = False


@dataclass(frozen=True)
class _Rule:
    pattern: re.Pattern[str]
    field: str
    field_type: FieldType
    canonical: str | None = None  # fixed canonical value
    template: str | None = None  # canonical built from a captured group, e.g. "PD-L1 TPS {0}"
    group: int = 0  # which group is the surface value / span
    negatable: bool = False  # suppress (or flip) when preceded by a negation cue
    negative_value: str | None = None  # if negatable & negated, emit this instead of suppressing
    suppress_window: re.Pattern[str] | None = None  # if this matches around the hit, drop it
    suppress_width: int = 44  # window (chars, each side) for suppress_window


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------- TNM token grammar
# Single source of truth for the surface grammar of TNM components and prefixes. Both the
# extraction rules in ``_RULES`` and the structural :func:`parse_tnm` are composed from these
# fragments, so the grammar is defined in exactly one place.
_T_FRAG = r"T(?:is|[0-4][a-d]?|x)"
_N_FRAG = r"N[0-3x]"
_M_FRAG = r"M[01][a-c]?"
_PFX_CLIN = r"(?:c|yc)"  # clinical / post-therapy clinical
_PFX_PATH = r"(?:p|yp)"  # pathological / post-therapy pathological
_PFX_ANY = r"(?:c|yc|p|yp)"


# --------------------------------------------------------------------------- pattern catalogue
# Versioned with MODEL_ID. Surface forms in fi / sv / en; canonical values are English/universal.

_RULES: tuple[_Rule, ...] = (
    # --- clinical vs pathological TNM (UICC 8th ed.) ----------------------------------------
    # combined cTNM with optional c/yc prefix (or none); pathological requires p/yp prefix.
    _Rule(
        _c(rf"(?i)(?<![A-Za-z]){_PFX_CLIN}?{_T_FRAG}\s?{_N_FRAG}\s?{_M_FRAG}"),
        "clinical_stage",
        FieldType.STAGING,
    ),
    _Rule(
        _c(rf"(?i)(?<![A-Za-z]){_PFX_PATH}{_T_FRAG}\s?{_N_FRAG}\s?{_M_FRAG}"),
        "pathological_stage",
        FieldType.STAGING,
    ),
    # lone clinical T/N/M components (no combined form): clinical only (c/none), not p-prefixed.
    _Rule(
        _c(rf"(?i)(?<![A-Za-z])c?{_T_FRAG}(?![A-Za-z0-9])"),
        "clinical_stage",
        FieldType.STAGING,
    ),
    _Rule(_c(rf"(?i)(?<![A-Za-z])c?{_N_FRAG}(?![A-Za-z0-9])"), "clinical_stage", FieldType.STAGING),
    _Rule(_c(rf"(?i)(?<![A-Za-z])c?{_M_FRAG}(?![A-Za-z0-9])"), "clinical_stage", FieldType.STAGING),
    # stage group: require a stage keyword nearby (fi/sv/en) to avoid stray Roman numerals.
    _Rule(
        _c(
            r"(?i)(?:stage|vaihe|levinneisyysryhmä|stadium)\s*"
            r"(IA[123]|IA|IB|IIA|IIB|IIIA|IIIB|IIIC|IVA|IVB|0|I{1,3}V?|IV)"
        ),
        "stage_group",
        FieldType.STAGING,
        group=1,
    ),
    # --- histology (negatable: "no adenocarcinoma" must not assert it) ----------------------
    _Rule(
        _c(r"(?i)adenocarcinoma\w*|adenoca\b|adenokarsinooma\w*|adenokarcinom\w*"),
        "histology",
        FieldType.CATEGORICAL,
        canonical="adenocarcinoma",
        negatable=True,
    ),
    _Rule(
        _c(
            r"(?i)squamous(?:\s+cell)?(?:\s+carcinoma)?|\bSCC\b|levyepiteelikarsinooma\w*"
            r"|okasolukarsinooma\w*|skivepitelcancer\w*"
        ),
        "histology",
        FieldType.CATEGORICAL,
        canonical="squamous cell carcinoma",
        negatable=True,
    ),
    _Rule(
        _c(
            r"(?i)small[-\s]cell(?:\s+(?:carcinoma|lung\s+cancer))?|\bSCLC\b"
            r"|pienisoluinen\w*|småcellig\w*"
        ),
        "histology",
        FieldType.CATEGORICAL,
        canonical="small cell carcinoma",
        negatable=True,
    ),
    _Rule(
        _c(
            r"(?i)NSCLC[-\s]?NOS|non[-\s]small[-\s]cell[^.\n]{0,14}NOS"
            r"|ei[-\s]pienisoluinen\w*[^.\n]{0,10}NOS"
        ),
        "histology",
        FieldType.CATEGORICAL,
        canonical="NSCLC-NOS",
        negatable=True,
    ),
    _Rule(
        _c(r"(?i)large[-\s]cell\s+carcinoma|suurisoluinen\w*|storcellig\w*"),
        "histology",
        FieldType.CATEGORICAL,
        canonical="large cell carcinoma",
        negatable=True,
    ),
    _Rule(
        _c(r"(?i)carcinoid\w*|karsinoidi\w*|karcinoid\w*"),
        "histology",
        FieldType.CATEGORICAL,
        canonical="carcinoid",
        negatable=True,
    ),
    # --- location (lobe) and laterality -----------------------------------------------------
    _Rule(
        _c(r"(?i)\bRUL\b|oikea\w*\s+ylälohko\w*|höger\w*\s+överlob\w*"),
        "location",
        FieldType.CATEGORICAL,
        canonical="RUL",
    ),
    _Rule(
        _c(r"(?i)\bRML\b|oikea\w*\s+keskilohko\w*|mellanlob\w*"),
        "location",
        FieldType.CATEGORICAL,
        canonical="RML",
    ),
    _Rule(
        _c(r"(?i)\bRLL\b|oikea\w*\s+alalohko\w*|höger\w*\s+underlob\w*"),
        "location",
        FieldType.CATEGORICAL,
        canonical="RLL",
    ),
    _Rule(
        _c(r"(?i)\bLUL\b|vasen\w*\s+ylälohko\w*|vänster\w*\s+överlob\w*"),
        "location",
        FieldType.CATEGORICAL,
        canonical="LUL",
    ),
    _Rule(
        _c(r"(?i)\bLLL\b|vasen\w*\s+alalohko\w*|vänster\w*\s+underlob\w*"),
        "location",
        FieldType.CATEGORICAL,
        canonical="LLL",
    ),
    _Rule(
        _c(r"(?i)\bright\b|oikea\w*|höger\w*"),
        "laterality",
        FieldType.CATEGORICAL,
        canonical="right",
        negatable=True,
    ),
    _Rule(
        _c(r"(?i)\bleft\b|vasen\w*|vänster\w*"),
        "laterality",
        FieldType.CATEGORICAL,
        canonical="left",
        negatable=True,
    ),
    # --- biomarkers (multi-valued; positives negatable -> negative_value) -------------------
    _Rule(
        _c(r"(?i)EGFR[^.\n]{0,18}?(?:exon\s*19|ex19)[^.\n]{0,8}?(?:del\w*)"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="EGFR exon 19 deletion",
        negatable=True,
        negative_value="EGFR negative",
    ),
    _Rule(
        _c(r"(?i)EGFR[^.\n]{0,12}?L858R"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="EGFR L858R",
        negatable=True,
        negative_value="EGFR negative",
    ),
    _Rule(
        _c(r"(?i)EGFR\s*(?:neg\w*|negatiivinen|wild[-\s]?type|villityyppi|\bwt\b)"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="EGFR negative",
    ),
    _Rule(
        _c(r"(?i)EGFR\s*(?:mutation\w*|mutated|positive|positiivinen|mutatoitunut|\bpos\b)"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="EGFR positive",
        negatable=True,
        negative_value="EGFR negative",
    ),
    _Rule(
        _c(r"(?i)ALK\s*(?:neg\w*|negatiivinen)"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="ALK negative",
    ),
    _Rule(
        _c(r"(?i)ALK[-\s]?(?:positive|rearrange\w*|fusion|positiivinen|\bpos\b)"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="ALK positive",
        negatable=True,
        negative_value="ALK negative",
    ),
    _Rule(
        _c(r"(?i)ROS1\s*(?:neg\w*|negatiivinen)"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="ROS1 negative",
    ),
    _Rule(
        _c(r"(?i)ROS1[-\s]?(?:positive|rearrange\w*|fusion|positiivinen|\bpos\b)"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="ROS1 positive",
        negatable=True,
        negative_value="ROS1 negative",
    ),
    _Rule(
        _c(r"(?i)BRAF\s*V600E"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="BRAF V600E",
        negatable=True,
        negative_value="BRAF negative",
    ),
    _Rule(
        _c(r"(?i)KRAS\s*G12C"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="KRAS G12C",
        negatable=True,
        negative_value="KRAS negative",
    ),
    _Rule(
        _c(r"(?i)MET[^.\n]{0,18}?(?:exon\s*14|ex14)[^.\n]{0,12}?skip\w*"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="MET exon 14 skipping",
    ),
    _Rule(
        _c(r"(?i)RET[-\s]?(?:fusion|rearrange\w*)"),
        "biomarker",
        FieldType.CATEGORICAL,
        canonical="RET fusion",
    ),
    _Rule(
        _c(r"(?i)PD[-\s]?L1[^%\n]{0,20}?(?:TPS\s*)?(<\s*1\s*%|≥?\s*\d{1,3}\s*%)"),
        "biomarker",
        FieldType.CATEGORICAL,
        template="PD-L1 TPS {0}",
        group=1,
    ),
    # --- performance status -----------------------------------------------------------------
    _Rule(
        _c(r"(?i)\bECOG\s*(?:PS)?\s*[:=]?\s*([0-4])\b"),
        "performance_status",
        FieldType.CATEGORICAL,
        template="ECOG {0}",
        group=1,
    ),
    _Rule(
        _c(r"(?i)\bWHO\s*(?:PS)?\s*[:=]?\s*([0-4])\b"),
        "performance_status",
        FieldType.CATEGORICAL,
        template="ECOG {0}",
        group=1,
    ),
    _Rule(
        _c(r"(?i)\b(?:PS|toimintakyky|funktionsstatus)\s*[:=]?\s*([0-4])\b"),
        "performance_status",
        FieldType.CATEGORICAL,
        template="ECOG {0}",
        group=1,
    ),
    _Rule(
        _c(r"(?i)\b(?:KPS|Karnofsky)\s*[:=]?\s*(\d{2,3})\s*%?"),
        "performance_status",
        FieldType.CATEGORICAL,
        template="Karnofsky {0}%",
        group=1,
    ),
    # --- MDT discussion documented (must be DONE, not planned/negated) ----------------------
    _Rule(
        _c(
            r"(?i)\b(?:MDT|MDK|tumou?r\s+board|multidisciplinary\s+team"
            r"|moniammatilli\w*[^.\n]{0,20}?kokou\w*)"
        ),
        "mdt_discussed",
        FieldType.CATEGORICAL,
        canonical="MDT discussed",
        negatable=True,
        suppress_window=_MDT_FUTURE,
    ),
    # --- treatment intent and plan ----------------------------------------------------------
    _Rule(
        _c(r"(?i)\b(?:curative|kuratiivinen|kurativ\w*)\b"),
        "treatment_intent",
        FieldType.CATEGORICAL,
        canonical="curative",
    ),
    _Rule(
        _c(r"(?i)\b(?:palliative|palliatiivinen|palliativ\w*)\b"),
        "treatment_intent",
        FieldType.CATEGORICAL,
        canonical="palliative",
    ),
    _Rule(
        _c(r"(?i)\b(?:SABR|SBRT|stereotactic\w*|stereotaktinen\w*)\b"),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="SABR",
    ),
    _Rule(
        _c(r"(?i)\b(?:lobectomy|lobektomia\w*|lobektomi\w*)\b"),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="lobectomy",
    ),
    _Rule(
        _c(r"(?i)\b(?:segmentectomy|segmentektomia\w*|segmentresektion\w*)\b"),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="segmentectomy",
    ),
    _Rule(
        _c(
            r"(?i)\b(?:chemoradiation|chemoradiotherapy|kemosädehoito\w*"
            r"|kemoradioterapi\w*|konkomitan\w*|lyfja-?\s*og\s*geislameðferð\w*)\b"
        ),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="chemoradiotherapy",
    ),
    # surgical evaluation / referral to surgery (distinct from a named resection above)
    _Rule(
        _c(
            r"(?i)\b(?:thoracic\s+surgery\s+evaluation|surgical\s+evaluation|surgery\s+evaluation"
            r"|leikkausarvi\w*|thoraxkirurg\w*|kirurg\w*bedömn\w*|kirurgisk\s+vurdering"
            r"|skurðlækn\w*)\b"
        ),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="surgical evaluation",
    ),
    # radiotherapy (general / palliative); \b keeps 'sädehoito' from matching in 'kemosädehoito'
    _Rule(
        _c(
            r"(?i)\b(?:radiotherapy|radiation\s+therapy|sädehoito\w*|strålbehandling\w*"
            r"|strålebehandling\w*|geislameðferð\w*)\b"
        ),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="radiotherapy",
    ),
    # systemic therapy (umbrella term, distinct from the named chemo/immuno/targeted plans)
    _Rule(
        _c(
            r"(?i)\b(?:systemic\s+(?:therapy|treatment)|systeemi\w*\s+hoito\w*"
            r"|systemisk\s+behandling\w*|kerfismeðferð\w*)\b"
        ),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="systemic therapy",
    ),
    _Rule(
        _c(r"(?i)\b(?:chemotherapy|kemoterapia\w*|solunsalpaaja\w*|cytostatika\w*)\b"),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="chemotherapy",
    ),
    _Rule(
        _c(r"(?i)\b(?:immunotherapy|immunoterapia\w*|immunterapi\w*|checkpoint\w*)\b"),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="immunotherapy",
    ),
    _Rule(
        _c(r"(?i)\btargeted\s+therapy\b|täsmälääke\w*|målriktad\w*"),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="targeted therapy",
    ),
    _Rule(
        _c(
            r"(?i)\bbest\s+supportive\s+care\b|\bBSC\b|symptom-directed\s+care"
            r"|oireenmukainen\s+hoito\w*"
        ),
        "treatment_plan",
        FieldType.CATEGORICAL,
        canonical="best supportive care",
    ),
)

#: The fields this extractor knows about.
FIELDS: tuple[str, ...] = tuple(dict.fromkeys(r.field for r in _RULES))


def _negated_before(note: str, start: int) -> bool:
    return _NEGATION.search(note[max(0, start - _NEG_WINDOW) : start]) is not None


def _suppressed(note: str, match: re.Match[str], rule: _Rule) -> bool:
    """True if a suppress-cue (e.g. future/planned intent) is in the window around the match."""
    if rule.suppress_window is None:
        return False
    s, e = match.span(rule.group)
    window = note[max(0, s - rule.suppress_width) : min(len(note), e + rule.suppress_width)]
    return rule.suppress_window.search(window) is not None


def _drop_subsumed(cands: list[RuleCandidate]) -> list[RuleCandidate]:
    """Drop candidates whose span is strictly contained in another candidate's span."""
    kept: list[RuleCandidate] = []
    for c in cands:
        cs, ce = c.span
        contained = any(
            (o.span[0] <= cs and ce <= o.span[1]) and (o.span[1] - o.span[0]) > (ce - cs)
            for o in cands
        )
        if not contained:
            kept.append(c)
    return kept


def _candidate(rule: _Rule, match: re.Match[str], note: str, *, negated: bool) -> RuleCandidate:
    span = match.span(rule.group)
    surface = match.group(rule.group)
    if negated:
        value = rule.negative_value or ""
    elif rule.canonical is not None:
        value = rule.canonical
    elif rule.template is not None:
        value = rule.template.format(_collapse(surface))
    else:
        value = _collapse(surface)
    return RuleCandidate(
        field=rule.field,
        value=value,
        matched_text=surface,
        span=(span[0], span[1]),
        field_type=rule.field_type,
        negated=negated,
    )


class RuleBasedExtractor:
    """Deterministic rule-based extractor adapter (satisfies the ``Extractor`` protocol)."""

    extractor_id = "rules"
    version = MODEL_ID

    def __init__(self, rules: Sequence[_Rule] = _RULES):
        self._rules = tuple(rules)

    def fields(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(r.field for r in self._rules))

    def field_type(self, field_name: str) -> FieldType | None:
        """The declared FieldType for a known field, or None if the field is unknown."""
        for r in self._rules:
            if r.field == field_name:
                return r.field_type
        return None

    def candidates(self, note: str, field_name: str) -> list[RuleCandidate]:
        """Rule matches for one field, in source order; may be empty.

        De-duplicated by span, and **span-subsumed matches are dropped** — a component match (e.g.
        ``N0``) inside a larger match (``cT2a N0 M0``) is removed, so the maximal match wins and the
        components are not mistaken for conflicting values.
        """
        out: list[RuleCandidate] = []
        seen: set[tuple[int, int, str]] = set()
        for rule in self._rules:
            if rule.field != field_name:
                continue
            for m in rule.pattern.finditer(note):
                start = m.span(rule.group)[0]
                if rule.suppress_window is not None and _suppressed(note, m, rule):
                    continue  # e.g. a planned/future MDT is not a documented MDT
                negated = rule.negatable and _negated_before(note, start)
                if negated and rule.negative_value is None:
                    continue  # suppressed: no positive finding from a negated statement
                cand = _candidate(rule, m, note, negated=negated)
                key = (cand.span[0], cand.span[1], cand.value)
                if key not in seen:
                    seen.add(key)
                    out.append(cand)
        out = _drop_subsumed(out)
        out.sort(key=lambda c: (c.span[0], c.span[1]))
        return out

    def extract_all(self, note: str) -> dict[str, list[RuleCandidate]]:
        """All candidates for every known field."""
        return {f: self.candidates(note, f) for f in self.fields()}

    def extract(self, note: str, field: FieldSpec) -> ExtractionResult:
        """``Extractor`` protocol: one proposed value (surface text) bound to its span, or no value.

        The value is the exact surface substring at the span (provenance-verifiable). For a
        single-valued field with conflicting candidates, returns no value (no-guess); use
        :meth:`candidates` to see the conflict or to get every value of a multi-valued field.
        """
        cands = self.candidates(note, field.name)
        if not cands:
            return self._empty()
        if field.name not in _MULTI_VALUED:
            distinct = {c.value for c in cands}
            if len(distinct) > 1:
                return self._empty()  # ambiguous: prefer nothing over guessing
        first = cands[0]
        return ExtractionResult(
            value=first.matched_text,
            source_span=first.span,
            extractor_id=self.extractor_id,
            version=self.version,
        )

    def _empty(self) -> ExtractionResult:
        return ExtractionResult(
            value="", source_span=None, extractor_id=self.extractor_id, version=self.version
        )


def iter_rule_fields() -> Iterable[str]:
    """The catalogue's field names (for docs/tests)."""
    return FIELDS


# --------------------------------------------------------------------------- TNM structure

# A TNM "run" is a contiguous (optionally space-separated) sequence of T/N/M tokens with an
# optional leading descriptor prefix. Components inside a run are extracted with the sub-scanners,
# so compact forms ("cT2aN0M0") and spaced forms ("cT2a N0 M0") parse identically. All token
# grammar comes from the shared fragments above, so it is defined in exactly one place.
_TOK = rf"(?:{_T_FRAG}|{_N_FRAG}|{_M_FRAG})"
_TNM_RUN = re.compile(rf"(?i)(?<![A-Za-z]){_PFX_ANY}?{_TOK}(?:\s?{_PFX_ANY}?{_TOK})*")
_T_SUB = re.compile(rf"(?i){_T_FRAG}")
_N_SUB = re.compile(rf"(?i){_N_FRAG}")
_M_SUB = re.compile(rf"(?i){_M_FRAG}")
_PFX_LEAD = re.compile(rf"(?i)^({_PFX_ANY})")
_EDITION_RE = re.compile(r"(?i)(?:UICC|AJCC|TNM)?\s*(\d)(?:th|rd|nd|st)\s*ed(?:ition)?")

# The edition assumed when a note states none; any other stated edition is flagged for review.
_DEFAULT_EDITION = "8th"


def _norm_component(text: str) -> str:
    return text[0].upper() + text[1:].lower()


def _resolve(values: set[str], default: str) -> str:
    """Collapse a value set to a single label: the lone value, ``default`` if empty, else mixed."""
    if len(values) == 1:
        return next(iter(values))
    return "ambiguous" if values else default


@dataclass(frozen=True)
class TnmParse:
    """A conservative structural read of TNM in a note. Surface only; no staging inference."""

    surface: str | None  # combined surface if a single coherent stage; else None
    prefix: str  # 'c' | 'yc' | 'p' | 'yp' | 'unknown' (or 'ambiguous' if mixed)
    t: str | None  # e.g. 'T2a'
    n: str | None  # e.g. 'N0'
    m: str | None  # e.g. 'M0'
    completeness: str  # 'complete' | 'partial' | 'absent' | 'ambiguous'
    edition: str  # 'unknown' unless an explicit edition is stated; 'ambiguous' if conflicting
    review_recommended: bool  # True if ambiguous or a non-default/old edition is stated
    spans: tuple[tuple[int, int], ...]


@dataclass
class _TnmScan:
    """Raw findings from scanning the TNM runs in a note, before classification."""

    t_vals: set[str]
    n_vals: set[str]
    m_vals: set[str]
    prefixes: set[str]
    spans: list[tuple[int, int]]


def _scan_tnm_runs(note: str) -> _TnmScan:
    """Collect distinct T/N/M component values, prefixes and spans from every TNM run."""
    scan = _TnmScan(set(), set(), set(), set(), [])
    buckets = ((_T_SUB, scan.t_vals), (_N_SUB, scan.n_vals), (_M_SUB, scan.m_vals))
    for run in _TNM_RUN.finditer(note):
        text, base = run.group(0), run.start()
        lead = _PFX_LEAD.match(text)
        if lead:
            scan.prefixes.add(lead.group(1).lower())
        for sub, bucket in buckets:
            sm = sub.search(text)
            if sm:
                bucket.add(_norm_component(sm.group(0)))
                scan.spans.append((base + sm.start(), base + sm.end()))
    return scan


def parse_tnm(note: str) -> TnmParse:
    """Structurally read TNM from a note WITHOUT inferring a stage.

    Conservative: multiple distinct values for any component (or mixed clinical/pathological
    prefixes, or conflicting editions) yield ``completeness='ambiguous'`` rather than a guess.
    ``edition`` is ``'unknown'`` unless explicitly stated. Default-vs-old edition or any ambiguity
    sets ``review_recommended`` so old/conflicting staging is never silently accepted.
    """
    scan = _scan_tnm_runs(note)
    editions = {f"{m.group(1)}th" for m in _EDITION_RE.finditer(note)}

    present = [bool(scan.t_vals), bool(scan.n_vals), bool(scan.m_vals)]
    conflicting = any(
        len(s) > 1 for s in (scan.t_vals, scan.n_vals, scan.m_vals, scan.prefixes, editions)
    )
    if not any(present):
        completeness = "absent"
    elif conflicting:
        completeness = "ambiguous"
    elif all(present):
        completeness = "complete"
    else:
        completeness = "partial"

    prefix = _resolve(scan.prefixes, "unknown")
    edition = _resolve(editions, "unknown")

    # A single coherent (non-ambiguous) component value per axis, else None.
    t = n = m = None
    if completeness != "ambiguous":
        t, n, m = (_resolve(s, "") or None for s in (scan.t_vals, scan.n_vals, scan.m_vals))

    spans = tuple(sorted(scan.spans))
    # Build a combined surface only for a single coherent complete/partial read.
    surface: str | None = None
    if completeness in ("complete", "partial"):
        prefix_str = "" if prefix in ("unknown", "ambiguous") else prefix
        surface = " ".join(p for p in (prefix_str + (t or ""), n, m) if p) or None

    review_recommended = completeness == "ambiguous" or edition not in ("unknown", _DEFAULT_EDITION)
    return TnmParse(
        surface=surface,
        prefix=prefix,
        t=t,
        n=n,
        m=m,
        completeness=completeness,
        edition=edition,
        review_recommended=review_recommended,
        spans=spans,
    )

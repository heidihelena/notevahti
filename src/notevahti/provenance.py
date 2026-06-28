"""Provenance: bind a value to a *verified* source span, or flag it as a likely hallucination.

NoteVahti never takes the extractor's word that a claimed span supports the value — it checks. A
field whose value cannot be located in the note (at the claimed span or anywhere) gets
``no_span_found`` and a hallucination flag. Deterministic: pure string search, no model, no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .types import FieldType, MatchKind, Provenance, ProvenanceStatus

# Field types for which whitespace is not semantically meaningful, so a "compact" (whitespace-
# removed) comparison is safe — e.g. "cT2a N0 M0" vs "cT2aN0M0".
_COMPACT_TYPES = {FieldType.STAGING, FieldType.NUMERIC, FieldType.CATEGORICAL, FieldType.DATE}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _compact(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def _equality_kind(claimed_text: str, value: str, field_type: FieldType) -> MatchKind | None:
    """How (if at all) the claimed-span text equals the value."""
    if claimed_text == value:
        return MatchKind.EXACT
    if _norm(claimed_text) == _norm(value):
        return MatchKind.NORMALIZED
    if field_type in _COMPACT_TYPES and _compact(claimed_text) == _compact(value):
        return MatchKind.NORMALIZED
    return None


def values_equivalent(a: str, b: str, field_type: FieldType = FieldType.TEXT) -> bool:
    """True if two values are the same under this field type's normalisation rules.

    Shared by the validity and agreement layers so that "do these two assertions agree?" is decided
    exactly as "does this span support this value?" is.
    """
    return _equality_kind(a, b, field_type) is not None


def canonical_value(s: str, field_type: FieldType = FieldType.TEXT) -> str:
    """Canonical key for a value under this field type — the category identity used by agreement.

    Consistent with :func:`values_equivalent`: two values are equivalent iff their canonical keys
    are equal (whitespace removed for compact types, collapsed-and-lowercased otherwise).
    """
    return _compact(s) if field_type in _COMPACT_TYPES else _norm(s)


def _bounded(note: str, start: int, end: int, numeric: bool) -> bool:
    """True if [start, end) is not embedded inside a larger token of the same character class.

    For numeric values a neighbouring digit breaks the boundary, and a '.'/',' breaks it only when
    it sits between digits (a real decimal/grouping separator) -- so "1" matches "ECOG 1." but not
    the "1" inside "4.1". For other field types any adjacent alphanumeric breaks the boundary (so
    "M" does not match inside "Male").
    """
    before = note[start - 1] if start > 0 else ""
    after = note[end] if end < len(note) else ""
    if numeric:
        before2 = note[start - 2] if start > 1 else ""
        after2 = note[end + 1] if end + 1 < len(note) else ""

        def breaks(neighbour: str, outer: str) -> bool:
            return neighbour.isdigit() or (neighbour in ".," and outer.isdigit())

        return not breaks(before, before2) and not breaks(after, after2)
    return not before.isalnum() and not after.isalnum()


def _first_substring(note: str, needle: str, *, ci: bool, numeric: bool, wb: bool) -> int:
    """Index of the first (optionally word-bounded) occurrence of needle, or -1."""
    hay = note.lower() if ci else note
    pat = needle.lower() if ci else needle
    start = 0
    while True:
        i = hay.find(pat, start)
        if i < 0:
            return -1
        if not wb or _bounded(note, i, i + len(needle), numeric):
            return i
        start = i + 1


def _find(
    value: str, note: str, field_type: FieldType, word_boundary: bool = False
) -> tuple[int, int, MatchKind] | None:
    """Locate the value in the note, returning (start, end, match_kind) or None.

    Strategies are tried in order of strictness; the first hit wins, so an exact match is preferred
    over a looser one and reported as such. ``word_boundary`` (opt-in; default off so behaviour is
    unchanged) rejects matches embedded inside a larger token.
    """
    if not value:
        return None
    numeric = field_type is FieldType.NUMERIC

    # 1. exact substring
    i = _first_substring(note, value, ci=False, numeric=numeric, wb=word_boundary)
    if i >= 0:
        return (i, i + len(value), MatchKind.EXACT)

    # 2. case-insensitive substring
    i = _first_substring(note, value, ci=True, numeric=numeric, wb=word_boundary)
    if i >= 0:
        return (i, i + len(value), MatchKind.NORMALIZED)

    # 3. whitespace-flexible (tokens of the value separated by any whitespace run)
    tokens = [t for t in re.split(r"\s+", value) if t]
    if tokens:
        pattern = r"\s+".join(re.escape(t) for t in tokens)
        for m in re.finditer(pattern, note, flags=re.IGNORECASE):
            if not word_boundary or _bounded(note, m.start(), m.end(), numeric):
                return (m.start(), m.end(), MatchKind.NORMALIZED)

    # 4. compact (whitespace-removed) match for types where whitespace is not meaningful
    if field_type in _COMPACT_TYPES:
        kept = [(idx, ch) for idx, ch in enumerate(note) if not ch.isspace()]
        compact_note = "".join(ch.lower() for _, ch in kept)
        vc = _compact(value)
        j = compact_note.find(vc)
        while j >= 0 and vc:
            start = kept[j][0]
            end = kept[j + len(vc) - 1][0] + 1
            if not word_boundary or _bounded(note, start, end, numeric):
                return (start, end, MatchKind.NORMALIZED)
            j = compact_note.find(vc, j + 1)

    return None


def _synonym_variants(
    value: str, field_type: FieldType, synonyms: Mapping[str, Sequence[str]]
) -> list[str]:
    """Surface variants of value from the synonym table (matched by canonical key)."""
    key = canonical_value(value, field_type)
    for canonical, variants in synonyms.items():
        members = [canonical, *variants]
        if any(canonical_value(m, field_type) == key for m in members):
            return members
    return []


def _locate(
    value: str,
    note: str,
    field_type: FieldType,
    word_boundary: bool,
    synonyms: Mapping[str, Sequence[str]] | None,
) -> tuple[int, int, MatchKind] | None:
    """Find value (and, if a synonym table is given, its known surface variants)."""
    hit = _find(value, note, field_type, word_boundary)
    if hit is not None:
        return hit
    if synonyms is not None:
        for variant in _synonym_variants(value, field_type, synonyms):
            if variant == value:
                continue
            vhit = _find(variant, note, field_type, word_boundary)
            if vhit is not None:
                s, e, _ = vhit
                return (s, e, MatchKind.NORMALIZED)  # synonym match is a normalised match
    return None


def verify_span(
    value: str,
    note: str,
    claimed_span: tuple[int, int] | None = None,
    field_type: FieldType = FieldType.TEXT,
    *,
    word_boundary: bool = False,
    synonyms: Mapping[str, Sequence[str]] | None = None,
) -> Provenance:
    """Verify that ``value`` is supported by ``note``.

    - If ``claimed_span`` is given and its text matches the value, that span is the provenance.
    - If the claimed span does not match but the value is found elsewhere, the found span is used
      and the mismatch is recorded (a weaker provenance, which downstream scoring penalises).
    - If the value is found nowhere, the result is ``no_span_found`` with the hallucination flag
      set.

    ``word_boundary`` and ``synonyms`` are opt-in and default off, so the deterministic default
    behaviour is unchanged. ``word_boundary`` rejects matches embedded inside a larger token (so a
    single token does not bind spuriously); ``synonyms`` (e.g. from ``notevahti.synonyms``) lets
    known abbreviations of a value count as support.
    """
    # Validate a provided claimed span against the note bounds.
    if claimed_span is not None:
        start, end = claimed_span
        in_bounds = 0 <= start < end <= len(note)
        if in_bounds:
            claimed_text = note[start:end]
            kind = _equality_kind(claimed_text, value, field_type)
            if kind is not None:
                return Provenance(
                    status=ProvenanceStatus.SPAN_FOUND,
                    claimed_span=claimed_span,
                    matched_span=claimed_span,
                    matched_text=claimed_text,
                    match_kind=kind,
                    hallucination_flag=False,
                    detail="claimed span verified",
                )
        # Claimed span is out of bounds or its text does not support the value: look elsewhere.
        found = _locate(value, note, field_type, word_boundary, synonyms)
        if found is not None:
            s, e, kind = found
            reason = (
                "claimed span out of bounds"
                if not in_bounds
                else "claimed span did not match value"
            )
            return Provenance(
                status=ProvenanceStatus.SPAN_FOUND,
                claimed_span=claimed_span,
                matched_span=(s, e),
                matched_text=note[s:e],
                match_kind=kind,
                hallucination_flag=False,
                detail=f"{reason}; supporting span found elsewhere",
            )
        return Provenance(
            status=ProvenanceStatus.NO_SPAN_FOUND,
            claimed_span=claimed_span,
            matched_span=None,
            matched_text=None,
            match_kind=MatchKind.NONE,
            hallucination_flag=True,
            detail="claimed span did not match and value not found in note",
        )

    # No claimed span: search the note.
    found = _locate(value, note, field_type, word_boundary, synonyms)
    if found is not None:
        s, e, kind = found
        return Provenance(
            status=ProvenanceStatus.SPAN_FOUND,
            claimed_span=None,
            matched_span=(s, e),
            matched_text=note[s:e],
            match_kind=kind,
            hallucination_flag=False,
            detail="no span claimed; supporting span found",
        )
    return Provenance(
        status=ProvenanceStatus.NO_SPAN_FOUND,
        claimed_span=None,
        matched_span=None,
        matched_text=None,
        match_kind=MatchKind.NONE,
        hallucination_flag=True,
        detail="no span claimed and value not found in note",
    )

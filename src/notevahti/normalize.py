"""TNM / stage-group surface normalisation for agreement and Stage-1 evaluation.

Clinical notes write the same stage many ways: ``cT2a N0 M0``, ``cT2aN0M0``, ``ct2a n0 m0``,
``pT3N1M0``, ``Stage IIIA`` vs ``stage 3a``. For agreement against a reference, formatting must not
count as disagreement. This module canonicalises the *surface form* only.

Scope and non-goals (deliberate): this is a deterministic, offline, stdlib formatter, NOT a clinical
parser. It does NOT infer a stage from T/N/M, does NOT convert between TNM editions (8th/9th -- e.g.
N2a/N2b and M1c sub-splits are preserved as written, never translated), and does NOT validate
clinical plausibility. It returns ``None`` when it cannot confidently parse, so callers never get a
fabricated canonical form. Used by the analytics/eval layer, not the deterministic validation core.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["StageTNM", "canonical_stage", "normalize_stage_group", "normalize_tnm"]

# component patterns (case-insensitive, whitespace-tolerant); prefix like c/p/yc/yp/r/a
_PREFIX = r"(?P<prefix>y?[cpra])?"
_T = re.compile(_PREFIX + r"\s*T\s*(?P<t>is|x|0|1mi|[1-4][a-d]?)", re.IGNORECASE)
_N = re.compile(r"N\s*(?P<n>x|[0-3][a-c]?)", re.IGNORECASE)
_M = re.compile(r"M\s*(?P<m>x|0|1[a-c]?)", re.IGNORECASE)

_ARABIC_TO_ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV"}
_STAGE_GROUP = re.compile(r"^(?:0|(?:I|II|III|IV)|[1-4])(?:[abc])?$", re.IGNORECASE)


@dataclass(frozen=True)
class StageTNM:
    prefix: str  # '', 'c', 'p', 'yc', ... (lowercased as written; never inferred)
    t: str  # 'T2a', 'Tis', 'TX', 'T0'
    n: str  # 'N0'..'N3' (with optional a/b/c), 'NX'
    m: str  # 'M0', 'M1a'.., 'MX'
    canonical: str  # spaced, e.g. 'cT2a N0 M0'
    compact: str  # no spaces, e.g. 'cT2aN0M0'


def _fmt_component(letter: str, raw: str) -> str:
    low = raw.lower()
    if low == "x":
        return letter + "X"
    if low == "is":
        return letter + "is"
    return letter + low  # digit + optional lowercase subdivision, e.g. '2a', '1mi'


def normalize_tnm(value: str) -> StageTNM | None:
    """Parse a cTNM/pTNM string into canonical components, or return None if not parseable.

    All three of T, N and M must be present. The descriptor prefix (c/p/y…) is preserved as written
    and never inferred.
    """
    mt = _T.search(value)
    mn = _N.search(value)
    mm = _M.search(value)
    if not (mt and mn and mm):
        return None
    prefix = (mt.group("prefix") or "").lower()
    t = _fmt_component("T", mt.group("t"))
    n = _fmt_component("N", mn.group("n"))
    m = _fmt_component("M", mm.group("m"))
    canonical = f"{prefix}{t} {n} {m}"
    compact = f"{prefix}{t}{n}{m}"
    return StageTNM(prefix=prefix, t=t, n=n, m=m, canonical=canonical, compact=compact)


def normalize_stage_group(value: str) -> str | None:
    """Canonicalise a stage group (e.g. 'stage 3a' -> 'IIIA'), or None if not parseable.

    Accepts Roman (I-IV) or Arabic (1-4) with an optional A/B/C suffix, and an optional leading
    'stage'/'group' word. Occult/0 normalises to '0'. Arabic is mapped to Roman; no inference beyond
    surface form.
    """
    s = value.strip().lower()
    s = re.sub(r"^(stage|group|st\.?)\s*", "", s)
    s = s.replace(" ", "")
    if not s or not _STAGE_GROUP.match(s):
        return None
    # split a trailing A/B/C suffix, but only when what precedes it is a recognised number/roman
    # (so the 'i'/'v' of a Roman numeral is never mistaken for a suffix)
    suffix = ""
    if (
        s[-1] in "abc"
        and not s.endswith(("i", "v"))
        and len(s) > 1
        and (s[:-1].isdigit() or s[:-1] in ("i", "ii", "iii", "iv"))
    ):
        suffix = s[-1].upper()
        s = s[:-1]
    if s == "0":
        return "0"
    if s.isdigit():
        roman = _ARABIC_TO_ROMAN.get(s)
        if roman is None:
            return None
        return roman + suffix
    return s.upper() + suffix


def canonical_stage(value: str) -> str | None:
    """Canonical key for a stage value: compact cTNM if parseable, else stage group, else None."""
    tnm = normalize_tnm(value)
    if tnm is not None:
        return tnm.compact
    return normalize_stage_group(value)

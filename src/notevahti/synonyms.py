"""A small, opt-in clinical abbreviation/synonym table for provenance matching.

The deterministic core never applies synonyms by default — provenance is exact/normalised string
matching, and that conservatism is a feature (it does not guess). But messy notes write values in
abbreviated forms ("neg" for negative, "adenoCa" for adenocarcinoma), so when a caller opts in,
``verify_span(..., synonyms=...)`` will also try the known surface variants of a value.

This table is deliberately small, English-leaning, and NOT exhaustive. It is a starting point to be
reviewed and extended per registry/language; it is data, not inference, and adding to it never
changes default behaviour. Each entry maps a controlled value to its accepted surface forms.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

CLINICAL_ABBREVIATIONS: Mapping[str, Sequence[str]] = {
    "negative": ["negative", "neg", "(-)", "not detected", "wild-type", "wild type", "wt"],
    "positive": ["positive", "pos", "(+)", "detected", "mutated", "mut"],
    "adenocarcinoma": ["adenocarcinoma", "adenoca", "adeno ca", "adeno-ca", "lung adenocarcinoma"],
    "squamous cell carcinoma": [
        "squamous cell carcinoma",
        "squamous",
        "scc",
        "squamous nsclc",
        "squamous cell",
    ],
    "small cell carcinoma": ["small cell carcinoma", "small cell", "sclc", "small cell morphology"],
    "concurrent chemoradiotherapy": [
        "concurrent chemoradiotherapy",
        "concurrent chemort",
        "chemort",
        "chemoradiation",
        "chemo-rt",
        "crt",
    ],
    "best supportive care": ["best supportive care", "bsc", "supportive care", "symptom-led"],
}


def default_synonyms() -> Mapping[str, Sequence[str]]:
    """Return the built-in clinical abbreviation table (opt-in; never applied by default)."""
    return CLINICAL_ABBREVIATIONS

"""Synthetic corpus tooling for NoteVahti (NOT part of the validation core).

stdlib-only, offline, deterministic. Defines the on-disk shape of one synthetic Nordic lung-cancer
MDT case and a dependency-free structural validator, so the generator, the fine-tuning export and
the study pipeline cannot drift from the published JSON Schema at
``corpus/schema/synthetic_case.schema.json``. The validation core does not import this package.
"""

from __future__ import annotations

from .synthetic import (
    DIFFICULTY_TAGS,
    DOC_FORMATS,
    LANGUAGES,
    MESSINESS,
    SPLITS,
    TNM_COMPLETENESS,
    TNM_PREFIXES,
    TREATMENT_INTENTS,
    CaseTruth,
    ExpectedField,
    SyntheticCase,
    TnmTruth,
    validate_case,
)

__all__ = [
    "DIFFICULTY_TAGS",
    "DOC_FORMATS",
    "LANGUAGES",
    "MESSINESS",
    "SPLITS",
    "TNM_COMPLETENESS",
    "TNM_PREFIXES",
    "TREATMENT_INTENTS",
    "CaseTruth",
    "ExpectedField",
    "SyntheticCase",
    "TnmTruth",
    "validate_case",
]

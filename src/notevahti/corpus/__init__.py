"""Synthetic corpus tooling for NoteVahti (NOT part of the validation core).

stdlib-only, offline, deterministic. Defines the on-disk *row* shape of the synthetic Nordic
lung-cancer MDT dataset and a dependency-free structural validator, so the generator, the
fine-tuning export and the study pipeline cannot drift from the published JSON Schema at
``corpus/schema/synthetic_case.schema.json``. The validation core does not import this package.
"""

from __future__ import annotations

from .synthetic import (
    BIOMARKER_KEYS,
    DATASET_VERSION,
    DOC_FORMATS,
    ECOG_STATUSES,
    LANGUAGES,
    MDT_STATUSES,
    MESSINESS,
    PRIMARY_FIELDS,
    QUALITY_LABEL_KEYS,
    SPLITS,
    TNM_PREFIXES,
    TREATMENT_INTENTS,
    ExpectedField,
    GroundTruth,
    QualityLabels,
    SyntheticRow,
    Tnm,
    validate_row,
)

__all__ = [
    "BIOMARKER_KEYS",
    "DATASET_VERSION",
    "DOC_FORMATS",
    "ECOG_STATUSES",
    "LANGUAGES",
    "MDT_STATUSES",
    "MESSINESS",
    "PRIMARY_FIELDS",
    "QUALITY_LABEL_KEYS",
    "SPLITS",
    "TNM_PREFIXES",
    "TREATMENT_INTENTS",
    "ExpectedField",
    "GroundTruth",
    "QualityLabels",
    "SyntheticRow",
    "Tnm",
    "validate_row",
]

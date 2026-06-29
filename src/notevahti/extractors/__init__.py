"""Pluggable extractor adapters for NoteVahti.

The validation core trusts no extractor — an adapter only *proposes* a (value, span); the core
decides whether to believe it. ``base`` holds the Protocol and trivial example adapters; ``rules``
holds a deterministic, offline, stdlib-only rule-based extractor for lung-cancer MDT notes.
"""

from __future__ import annotations

from .base import Extractor, PassThroughExtractor, RegexExtractor
from .rules import FIELDS, MODEL_ID, RuleBasedExtractor, RuleCandidate, rules_lineage

__all__ = [
    "FIELDS",
    "MODEL_ID",
    "Extractor",
    "PassThroughExtractor",
    "RegexExtractor",
    "RuleBasedExtractor",
    "RuleCandidate",
    "rules_lineage",
]

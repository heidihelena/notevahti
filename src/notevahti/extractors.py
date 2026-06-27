"""The pluggable extractor interface and two example adapters.

NoteVahti binds to no extractor. An extractor is optional and never trusted as truth — it only
*proposes* a (value, span); the validation core decides whether to believe it. Swapping the extractor
must never change the validation contract.

Shipped here: a pass-through adapter (wrap already-extracted values) and a trivial regex adapter.
No production extractor. Local models (GLiNER, clinical-BERT, Llama/Mistral finetunes served via
llama.cpp/Ollama/vLLM) are additional adapters that satisfy the same Protocol — see SKILL.md.
"""

from __future__ import annotations

import re
from typing import Optional, Protocol, runtime_checkable

from .types import ExtractionResult, FieldSpec


@runtime_checkable
class Extractor(Protocol):
    """Anything that proposes a value (and optionally a source span) for a field in a note."""

    def extract(self, note: str, field: FieldSpec) -> ExtractionResult: ...


class PassThroughExtractor:
    """Wrap values that were already extracted (by a human or another system).

    The whole point of NoteVahti is to validate values it did not produce; this adapter is the
    canonical entry point for that.
    """

    def __init__(
        self,
        values: dict[str, str],
        spans: Optional[dict[str, tuple[int, int]]] = None,
        extractor_id: str = "passthrough",
        version: str = "0",
    ):
        self._values = values
        self._spans = spans or {}
        self._id = extractor_id
        self._version = version

    def extract(self, note: str, field: FieldSpec) -> ExtractionResult:
        return ExtractionResult(
            value=self._values.get(field.name, ""),
            source_span=self._spans.get(field.name),
            extractor_id=self._id,
            version=self._version,
        )


class RegexExtractor:
    """A trivial regex extractor: one pattern per field name.

    If the pattern has a capturing group, group(1) is the value and its span is reported; otherwise
    the whole match is used. This exists as an example adapter and a test fixture, not a real
    extractor.
    """

    def __init__(self, patterns: dict[str, str], version: str = "0"):
        self._patterns = {name: re.compile(p) for name, p in patterns.items()}
        self._version = version

    def extract(self, note: str, field: FieldSpec) -> ExtractionResult:
        pattern = self._patterns.get(field.name)
        if pattern is None:
            return ExtractionResult(value="", source_span=None, extractor_id="regex",
                                    version=self._version)
        m = pattern.search(note)
        if m is None:
            return ExtractionResult(value="", source_span=None, extractor_id="regex",
                                    version=self._version)
        group = 1 if m.groups() else 0
        return ExtractionResult(
            value=m.group(group),
            source_span=m.span(group),
            extractor_id="regex",
            version=self._version,
        )

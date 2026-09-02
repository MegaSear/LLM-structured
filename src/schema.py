# -*- coding: utf-8 -*-
"""Shared data structures for the extraction pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class FieldStatus(str, Enum):
    FOUND = "found"           # confident, grounded value
    AMBIGUOUS = "ambiguous"   # something was found but it's unclear / underspecified
    MISSING = "missing"       # not present in the source at all


class FieldSource(str, Enum):
    RULE_BASED = "rule_based"
    LLM = "llm"
    RULE_LLM = "rule+llm"
    NONE = "none"


# Fields that MUST be resolved (status == FOUND) before a deal can be created.
REQUIRED_FIELDS = [
    "company",
    "station_from",
    "station_to",
    "cargo",
    "volume",
    "period",
]

# Fields that are nice-to-have; missing them does not block, but we still
# report their status.
OPTIONAL_FIELDS = [
    "loading_conditions",
    "budget",
]

ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

FIELD_LABELS_RU = {
    "company": "компания",
    "station_from": "станция отправления",
    "station_to": "станция назначения",
    "cargo": "груз",
    "volume": "объём / количество вагонов",
    "period": "период перевозки",
    "loading_conditions": "условия погрузки/выгрузки",
    "budget": "бюджет/ставка",
}


@dataclass
class FieldResult:
    name: str
    value: Optional[Any] = None
    status: FieldStatus = FieldStatus.MISSING
    evidence: Optional[str] = None          # verbatim snippet from the source
    source: FieldSource = FieldSource.NONE
    confidence: float = 0.0
    note: Optional[str] = None              # why it's ambiguous, if it is

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["source"] = self.source.value
        return d


@dataclass
class ExtractionResult:
    request_id: str
    raw_text: str
    fields: dict[str, FieldResult] = field(default_factory=dict)

    def is_complete(self) -> bool:
        return all(
            self.fields.get(f, FieldResult(f)).status == FieldStatus.FOUND
            for f in REQUIRED_FIELDS
        )

    def missing_or_ambiguous(self) -> list[FieldResult]:
        out = []
        for name in ALL_FIELDS:
            fr = self.fields.get(name, FieldResult(name))
            if name in REQUIRED_FIELDS and fr.status != FieldStatus.FOUND:
                out.append(fr)
            elif name in OPTIONAL_FIELDS and fr.status == FieldStatus.AMBIGUOUS:
                out.append(fr)
        return out

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "is_complete": self.is_complete(),
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
        }

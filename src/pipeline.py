# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from pathlib import Path

from . import llm_extractor, rule_extractor, resolver
from .completeness import build_questions
from .parsers import extract_text
from .schema import ALL_FIELDS, ExtractionResult, FieldResult, FieldStatus

def process_text(
    text: str,
    request_id: str | None = None,
    use_llm: bool | None = None,
) -> ExtractionResult:

    # Independent extraction passes.
    rule_fields = rule_extractor.extract(text)

    do_llm = llm_extractor.available() if use_llm is None else use_llm

    llm_fields = (
        llm_extractor.run(text)
        if do_llm
        else {}
    )

    # Resolve disagreements between independent extractors.
    fields = resolver.resolve(
        rule_fields=rule_fields,
        llm_fields=llm_fields,
    )

    for name in ALL_FIELDS:
        fields.setdefault(name, FieldResult(name))

    return ExtractionResult(
        request_id=request_id or str(uuid.uuid4()),
        raw_text=text,
        fields=fields,
    )


def process_file(path: str | Path, use_llm: bool | None = None) -> ExtractionResult:
    text = extract_text(path)
    return process_text(text, request_id=Path(path).stem, use_llm=use_llm)


def summarize(result: ExtractionResult) -> dict:
    """Human/JSON-friendly output combining structured data + questions."""
    return {
        "request_id": result.request_id,
        "is_complete": result.is_complete(),
        "fields": {name: fr.to_dict() for name, fr in result.fields.items()},
        "clarifying_questions": build_questions(result),
    }

# -*- coding: utf-8 -*-
"""
Optional second-pass extractor backed by an LLM (Groq).

This is OFF by default and only activates if GROQ_API_KEY is set in the
environment. It exists to catch phrasing the regex/dictionary layer can't
anticipate (e.g. a station name not in our list, a period phrased in an
unusual way). It is never the only source of truth: every value it returns
is checked against the source text (see `_grounded`) and rejected outright
if the model didn't actually find it there. This is our main defence against
hallucination when using a generative model for extraction.

If the `openai` package or API key isn't available, `run()` returns an
empty dict and the pipeline just uses the rule-based results as-is -- the
system always degrades gracefully to the deterministic path.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from .schema import ALL_FIELDS, FieldResult, FieldSource, FieldStatus
from langchain_groq import ChatGroq

MODEL = "openai/gpt-oss-20b" #"openai/gpt-oss-120b"

SYSTEM_PROMPT = """\
Ты помогаешь распознавать данные в заявках на ЖД-перевозку зерновых грузов.
Тебе дан текст заявки. Извлеки только те поля, которые ЯВНО присутствуют в
тексте. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО придумывать, додумывать или подставлять
значения по умолчанию. Если поле не указано или указано неоднозначно —
верни null для value и одним предложением укажи, чего не хватает, в поле note.

Для каждого извлечённого значения обязательно укажи `evidence` — точную
цитату (подстроку) из исходного текста, из которой ты это значение взял.
Если не можешь процитировать точную подстроку — считай, что поля нет.

Поля: company, station_from, station_to, cargo, volume, period,
loading_conditions, budget.

Ответь СТРОГО в формате JSON без каких-либо пояснений вне JSON:
{
  "company": {"value": ..., "evidence": ..., "note": ...},
  "station_from": {"value": ..., "evidence": ..., "note": ...},
  "station_to": {"value": ..., "evidence": ..., "note": ...},
  "cargo": {"value": ..., "evidence": ..., "note": ...},
  "volume": {"value": ..., "evidence": ..., "note": ...},
  "period": {"value": ..., "evidence": ..., "note": ...},
  "loading_conditions": {"value": ..., "evidence": ..., "note": ...},
  "budget": {"value": ..., "evidence": ..., "note": ...}
}
"""


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _grounded(text: str, evidence: Optional[str]) -> bool:
    """Reject anything the model claims but that isn't actually in the text."""
    if not evidence:
        return False
    return _normalize(evidence) in _normalize(text)


def available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))
    
def run(text: str) -> dict[str, FieldResult]:
    print("[llm] run() called, available() =", available())
    if not available():
        return {}

    try:
        client = ChatGroq(
            api_key=os.environ["GROQ_API_KEY"],
            model=MODEL,
            max_tokens=1500,
            model_kwargs={
                "response_format": {"type": "json_object"}
            },
        )

        response = client.invoke([
            ("system", SYSTEM_PROMPT),
            ("human", f"Текст заявки:\n\n{text}"),
        ])

        raw = response.content

        if isinstance(raw, list):
            raw = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw
            )

        data = json.loads(raw)

    except Exception as e:
        print("[llm] EXCEPTION:", repr(e))
        return {}

    results: dict[str, FieldResult] = {}

    for name in ALL_FIELDS:
        entry = data.get(name) or {}

        value = entry.get("value")
        evidence = entry.get("evidence")
        note = entry.get("note")

        if value is None or not _grounded(text, evidence):
            continue

        results[name] = FieldResult(
            name=name,
            value=value,
            status=FieldStatus.FOUND,
            evidence=evidence,
            source=FieldSource.LLM,
            confidence=0.7,
            note=note,
        )

    return results
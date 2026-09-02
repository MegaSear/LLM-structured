# -*- coding: utf-8 -*-
"""Decide what's missing/ambiguous and phrase a question for the client."""
from __future__ import annotations

from .schema import ExtractionResult, FieldResult, FieldStatus

_QUESTION_TEMPLATES = {
    "company": "Уточните, пожалуйста, полное наименование компании-заказчика.",
    "station_from": "Уточните, пожалуйста, станцию отправления груза.",
    "station_to": "Уточните, пожалуйста, станцию назначения груза.",
    "cargo": "Уточните, пожалуйста, конкретный вид зерновой культуры (пшеница, ячмень, кукуруза и т.д.).",
    "volume": "Уточните, пожалуйста, объём перевозки: количество вагонов или тонн.",
    "period": "Уточните, пожалуйста, желаемый период перевозки (даты или месяц).",
    "loading_conditions": "Уточните, пожалуйста, условия погрузки/выгрузки (если они важны для расчёта).",
    "budget": "Уточните, пожалуйста, ожидаемый бюджет/ставку за перевозку (если он у вас есть).",
}

_AMBIGUOUS_SUFFIX = " В сообщении есть упоминание («{evidence}»), но оно неоднозначно: {note}"


def question_for(field: FieldResult) -> str:
    base = _QUESTION_TEMPLATES.get(field.name, f"Уточните поле '{field.name}'.")
    if field.status == FieldStatus.AMBIGUOUS and field.note:
        return base + _AMBIGUOUS_SUFFIX.format(evidence=field.evidence or "", note=field.note)
    return base


def build_questions(result: ExtractionResult) -> list[str]:
    """One question per missing/ambiguous field, in a stable, useful order
    (required fields first, in the order the business cares about)."""
    from .schema import ALL_FIELDS
    ordered_missing = [f for f in result.missing_or_ambiguous()]
    ordered_missing.sort(key=lambda f: ALL_FIELDS.index(f.name))
    return [question_for(f) for f in ordered_missing]

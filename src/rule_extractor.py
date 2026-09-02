# -*- coding: utf-8 -*-
"""
Deterministic, explainable extractor.

Why rule-based first (and not "just call an LLM")?
  1. The task explicitly forbids inventing data. A regex/dictionary match is
     either there in the text or it isn't -- there is no way for it to
     hallucinate a station name that doesn't appear in the message.
  2. Every extracted value comes with `evidence` = the exact substring that
     produced it, so a human (or a unit test) can verify the result in
     seconds without re-reading the whole message.
  3. It works with zero external dependencies / API keys, which matters for
     a prototype that has to "just run" for whoever reviews it.

The trade-off is recall: free-form phrasing the dictionaries don't cover
will be missed. `llm_extractor.py` is an optional second pass that can fill
some of those gaps -- see pipeline.py for how the two are combined.
"""
from __future__ import annotations

import re
from typing import Optional

from . import dictionaries as D
from .schema import FieldResult, FieldStatus, FieldSource

_SENT_SPLIT = re.compile(r"(?<=[.!?\n])\s+")


def _sentence_containing(text: str, idx: int) -> str:
    """Return the sentence (or line) that contains character offset idx."""
    start = text.rfind("\n", 0, idx)
    start = max(start, text.rfind(". ", 0, idx))
    start = 0 if start == -1 else start + 1
    end_candidates = [p for p in (text.find(".", idx), text.find("\n", idx)) if p != -1]
    end = min(end_candidates) + 1 if end_candidates else len(text)
    return text[start:end].strip()


def _find_company(text: str) -> Optional[FieldResult]:
    prefixes = "|".join(D.COMPANY_PREFIXES)
    pattern = rf'\b({prefixes})[ \t]*[«"]?([A-ZА-ЯЁ][\w\-]*(?:[ \t]+[A-ZА-ЯЁ0-9][\w\-]*){{0,4}})[»"]?'
    m = re.search(pattern, text)
    if not m:
        return None
    value = f"{m.group(1)} {m.group(2)}".strip(' «»"')
    return FieldResult(
        name="company", value=value, status=FieldStatus.FOUND,
        evidence=m.group(0), source=FieldSource.RULE_BASED, confidence=0.9,
    )


def _normalize_station(word: str) -> str:
    return word.strip(" .,;:«»\"'").lower()


def _find_all_stations(text: str) -> list[tuple[str, int]]:
    """Return [(station_name_as_written, char_offset), ...] for known stations."""
    found = []
    lowered = text.lower()
    for station in D.KNOWN_STATIONS:
        for m in re.finditer(re.escape(station.lower()), lowered):
            found.append((text[m.start():m.end()], m.start()))
    # de-duplicate overlapping matches (e.g. "Ростов-на-Дону" containing "Ростов")
    found.sort(key=lambda t: (t[1], -len(t[0])))
    deduped = []
    last_end = -1
    for name, pos in found:
        if pos >= last_end:
            deduped.append((name, pos))
            last_end = pos + len(name)
    return deduped


_FROM_KEYWORDS = ["отправлен", "отгруз", "погруз", "со станции", "от станции", "из ст.", "станция отправления", "ст. отправления"]
_TO_KEYWORDS = ["назначен", "выгруз", "на станцию", "до станции", "в направлении", "станция назначения", "ст. назначения", "получател"]


def _keyword_side(text: str, pos: int, window: int = 60) -> Optional[str]:
    """Look at the text right before `pos` and return which keyword group
    (from/to) occurs CLOSEST to the station name, not just "present
    somewhere in the window" -- otherwise a from-keyword earlier in the
    sentence would wrongly claim a later, to-labelled station too."""
    ctx = text[max(0, pos - window):pos].lower()
    best_side, best_dist = None, None
    for k in _FROM_KEYWORDS:
        idx = ctx.rfind(k)
        if idx != -1:
            dist = len(ctx) - (idx + len(k))
            if best_dist is None or dist < best_dist:
                best_side, best_dist = "from", dist
    for k in _TO_KEYWORDS:
        idx = ctx.rfind(k)
        if idx != -1:
            dist = len(ctx) - (idx + len(k))
            if best_dist is None or dist < best_dist:
                best_side, best_dist = "to", dist
    return best_side


def _find_stations(text: str) -> dict[str, Optional[FieldResult]]:
    stations = _find_all_stations(text)
    result = {"station_from": None, "station_to": None}
    if not stations:
        return result

    labeled = [(name, pos, _keyword_side(text, pos)) for name, pos, in stations]
    froms = [t for t in labeled if t[2] == "from"]
    tos = [t for t in labeled if t[2] == "to"]

    if froms:
        name, pos, _ = froms[0]
        result["station_from"] = FieldResult(
            "station_from", value=name, status=FieldStatus.FOUND,
            evidence=_sentence_containing(text, pos), source=FieldSource.RULE_BASED,
            confidence=0.85,
        )
    if tos:
        name, pos, _ = tos[0]
        result["station_to"] = FieldResult(
            "station_to", value=name, status=FieldStatus.FOUND,
            evidence=_sentence_containing(text, pos), source=FieldSource.RULE_BASED,
            confidence=0.85,
        )

    # Fallback: exactly two stations mentioned, no explicit keywords ->
    # assume order-of-mention = from -> to, but flag lower confidence since
    # this is an assumption, not something stated in the text.
    if result["station_from"] is None and result["station_to"] is None and len(stations) >= 2:
        (n1, p1), (n2, p2) = stations[0], stations[1]
        note = "Станция определена по порядку упоминания, а не по явному указанию 'откуда/куда' — требует подтверждения."
        result["station_from"] = FieldResult(
            "station_from", value=n1, status=FieldStatus.AMBIGUOUS,
            evidence=_sentence_containing(text, p1), source=FieldSource.RULE_BASED,
            confidence=0.4, note=note,
        )
        result["station_to"] = FieldResult(
            "station_to", value=n2, status=FieldStatus.AMBIGUOUS,
            evidence=_sentence_containing(text, p2), source=FieldSource.RULE_BASED,
            confidence=0.4, note=note,
        )
    elif len(stations) == 1:
        # One station only: we don't know if it's origin or destination.
        name, pos = stations[0]
        side = "station_from" if result["station_from"] else "station_to" if result["station_to"] else None
        if side is None:
            result["station_from"] = FieldResult(
                "station_from", value=name, status=FieldStatus.AMBIGUOUS,
                evidence=_sentence_containing(text, pos), source=FieldSource.RULE_BASED,
                confidence=0.3, note="Упомянута только одна станция без уточнения, отправление это или назначение.",
            )
    return result


def _find_cargo(text: str) -> Optional[FieldResult]:
    lowered = text.lower()
    for canonical, forms in D.GRAIN_CARGO_FORMS.items():
        for form in forms:
            m = re.search(rf"\b{re.escape(form)}\b", lowered)
            if m:
                return FieldResult(
                    "cargo", value=canonical,
                    status=FieldStatus.FOUND, evidence=_sentence_containing(text, m.start()),
                    source=FieldSource.RULE_BASED, confidence=0.9,
                )
    for generic in D.GENERIC_GRAIN_TERMS:
        m = re.search(rf"\b{re.escape(generic)}\b", lowered)
        if m:
            return FieldResult(
                "cargo", value=generic, status=FieldStatus.AMBIGUOUS,
                evidence=_sentence_containing(text, m.start()), source=FieldSource.RULE_BASED,
                confidence=0.5,
                note="Указано только обобщённо 'зерно' — не уточнена конкретная культура.",
            )
    return None


_NUM = r"(\d+(?:[.,]\d+)?)"


def _find_volume(text: str) -> Optional[FieldResult]:
    lowered = text.lower()
    wagon_words = "|".join(D.WAGON_WORDS)

    # range: "10-15 вагонов"
    m = re.search(rf"{_NUM}\s*[-–—]\s*{_NUM}\s*(?:{wagon_words})", lowered)
    if m:
        return FieldResult(
            "volume", value={"min": float(m.group(1).replace(",", ".")),
                              "max": float(m.group(2).replace(",", ".")), "unit": "вагон"},
            status=FieldStatus.FOUND, evidence=_sentence_containing(text, m.start()),
            source=FieldSource.RULE_BASED, confidence=0.85,
        )
    # exact wagons
    m = re.search(rf"{_NUM}\s*(?:{wagon_words})", lowered)
    if m:
        return FieldResult(
            "volume", value={"quantity": float(m.group(1).replace(",", ".")), "unit": "вагон"},
            status=FieldStatus.FOUND, evidence=_sentence_containing(text, m.start()),
            source=FieldSource.RULE_BASED, confidence=0.9,
        )
    # tons
    m = re.search(rf"{_NUM}\s*(?:тонн\w*|т\.?\b)", lowered)
    if m:
        return FieldResult(
            "volume", value={"quantity": float(m.group(1).replace(",", ".")), "unit": "тонна"},
            status=FieldStatus.FOUND, evidence=_sentence_containing(text, m.start()),
            source=FieldSource.RULE_BASED, confidence=0.9,
        )
    # vague quantity without a number
    m = re.search(r"(несколько|небольшая партия|партия|партию|партии|определённ\w+ объ[её]м)", lowered)
    if m:
        return FieldResult(
            "volume", value=m.group(0), status=FieldStatus.AMBIGUOUS,
            evidence=_sentence_containing(text, m.start()), source=FieldSource.RULE_BASED,
            confidence=0.3, note="Объём упомянут без конкретного числа.",
        )
    return None


def _find_period(text: str) -> Optional[FieldResult]:
    lowered = text.lower()

    # explicit date range dd.mm.yyyy - dd.mm.yyyy
    date = r"\d{1,2}[./]\d{1,2}[./]\d{2,4}"
    m = re.search(rf"({date})\s*[-–—]\s*({date})", text)
    if m:
        return FieldResult(
            "period", value={"start": m.group(1), "end": m.group(2)},
            status=FieldStatus.FOUND, evidence=_sentence_containing(text, m.start()),
            source=FieldSource.RULE_BASED, confidence=0.9,
        )
    # quarter: "1 квартал 2027" / "1 кв. 2027"
    m = re.search(r"(\d)\s*(?:квартал|кв\.)\s*(\d{4})?", lowered)
    if m:
        return FieldResult(
            "period", value=f"{m.group(1)} квартал" + (f" {m.group(2)}" if m.group(2) else ""),
            status=FieldStatus.FOUND, evidence=_sentence_containing(text, m.start()),
            source=FieldSource.RULE_BASED, confidence=0.8,
        )
    # month name, optionally with year
    for stem, num in D.MONTHS_RU.items():
        m = re.search(rf"\b{stem}\w*\s*(\d{{4}})?", lowered)
        if m:
            year = f" {m.group(1)}" if m.group(1) else ""
            return FieldResult(
                "period", value=f"{D.MONTH_NAMES_RU[num]}{year}",
                status=FieldStatus.FOUND, evidence=_sentence_containing(text, m.start()),
                source=FieldSource.RULE_BASED, confidence=0.75,
            )
    # vague period
    m = re.search(r"(в ближайшее время|как можно скорее|срочно|скоро)", lowered)
    if m:
        return FieldResult(
            "period", value=m.group(0), status=FieldStatus.AMBIGUOUS,
            evidence=_sentence_containing(text, m.start()), source=FieldSource.RULE_BASED,
            confidence=0.3, note="Срок указан не конкретной датой/периодом, а общей фразой.",
        )
    return None


def _find_loading_conditions(text: str) -> Optional[FieldResult]:
    lowered = text.lower()
    hits = []
    first_pos = None
    for kw in D.LOADING_CONDITION_KEYWORDS:
        m = re.search(re.escape(kw), lowered)
        if m:
            hits.append(kw)
            if first_pos is None:
                first_pos = m.start()
    if not hits:
        return None
    return FieldResult(
        "loading_conditions", value=hits, status=FieldStatus.FOUND,
        evidence=_sentence_containing(text, first_pos), source=FieldSource.RULE_BASED,
        confidence=0.7,
    )


def _find_budget(text: str) -> Optional[FieldResult]:
    lowered = text.lower()
    m = re.search(rf"{_NUM}\s*(?:000)?\s*(руб\w*|₽|\$|usd|eur|€|долл\w*|евро)", lowered)
    if not m:
        return None
    currency = D.CURRENCY_WORDS.get(m.group(2).strip(), m.group(2))
    per_unit = None
    tail = lowered[m.end():m.end() + 25]
    if "за тонну" in tail or "/т" in tail:
        per_unit = "тонна"
    elif "за вагон" in tail:
        per_unit = "вагон"
    return FieldResult(
        "budget",
        value={"amount": float(m.group(1).replace(",", ".")), "currency": currency, "per_unit": per_unit},
        status=FieldStatus.FOUND, evidence=_sentence_containing(text, m.start()),
        source=FieldSource.RULE_BASED, confidence=0.8,
    )


def extract(text: str) -> dict[str, FieldResult]:
    """Run every field extractor and return a name -> FieldResult mapping.
    Fields that produced nothing at all are returned with status=MISSING."""
    fields: dict[str, FieldResult] = {}

    fields["company"] = _find_company(text) or FieldResult("company")
    stations = _find_stations(text)
    fields["station_from"] = stations["station_from"] or FieldResult("station_from")
    fields["station_to"] = stations["station_to"] or FieldResult("station_to")
    fields["cargo"] = _find_cargo(text) or FieldResult("cargo")
    fields["volume"] = _find_volume(text) or FieldResult("volume")
    fields["period"] = _find_period(text) or FieldResult("period")
    fields["loading_conditions"] = _find_loading_conditions(text) or FieldResult("loading_conditions")
    fields["budget"] = _find_budget(text) or FieldResult("budget")
    return fields

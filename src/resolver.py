from __future__ import annotations

import re
from typing import Any

from .schema import FieldResult, FieldStatus, FieldSource

# ============================================================
# Text helpers
# ============================================================

LEGAL_FORMS = {"ооо", "ао", "пао", "зао", "оао", "ип"}


def _get_morph():
    try:
        import pymorphy3
        return pymorphy3.MorphAnalyzer()
    except ImportError:
        return None


_MORPH = None


def _lemmatize(text: str) -> str:
    global _MORPH
    if _MORPH is None:
        _MORPH = _get_morph()
    if _MORPH is None:
        return text

    tokens = re.findall(r"[а-яёa-z0-9\-]+", text.lower())
    result = []
    for token in tokens:
        if len(token) <= 2 or token.isdigit() or token in LEGAL_FORMS:
            result.append(token)
            continue
        parsed = _MORPH.parse(token)
        result.append(parsed[0].normal_form if parsed else token)
    return " ".join(result)


def _clean(text: str) -> str:
    text = str(text).strip().lower()
    text = text.replace('"', "").replace("«", "").replace("»", "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\bгода\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _plain(text: str) -> str:
    """Убирает правовую форму + лемматизирует."""
    text = _clean(text)
    tokens = text.split()
    while tokens and tokens[0] in LEGAL_FORMS:
        tokens.pop(0)
    return _lemmatize(" ".join(tokens))


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ============================================================
# Field-specific normalizers (возвращают канон или None)
# ============================================================

def _norm_volume(value: Any):
    if isinstance(value, dict):
        if "min" in value and "max" in value:
            lo, hi = _num(value["min"]), _num(value["max"])
            if lo is not None and hi is not None:
                return ("range", lo, hi)
        q = _num(value.get("quantity"))
        if q is not None:
            return ("qty", q)
        return None

    if isinstance(value, (int, float)):
        return ("qty", float(value))

    if isinstance(value, str):
        t = _clean(value)
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)", t)
        if m:
            return ("range", float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", ".")))
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        if m:
            return ("qty", float(m.group(1).replace(",", ".")))
    return None


def _norm_budget(value: Any):
    if isinstance(value, dict):
        amount = _num(value.get("amount"))
        if amount is not None:
            return ("budget", amount)
        return None

    if isinstance(value, str):
        t = _clean(value)
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        if m:
            return ("budget", float(m.group(1).replace(",", ".")))
    return None


def _norm_period(value: Any):
    if isinstance(value, dict):
        start, end = value.get("start"), value.get("end")
        if start and end:
            return ("range", _clean(str(start)), _clean(str(end)))
        return None

    if isinstance(value, str):
        t = _clean(value)
        m = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})\s*[-–]\s*(\d{1,2}\.\d{1,2}\.\d{4})", t)
        if m:
            return ("range", m.group(1), m.group(2))
        return ("text", _lemmatize(t))
    return None


IMPORTANT_LOADING = {
    "элеватор",
    "порт",
    "силами отправителя",
    "силами получателя",
    "механизированная погрузка",
}


def _norm_loading(value: Any):
    if isinstance(value, (list, tuple, set)):
        text = " ".join(map(str, value))
    elif isinstance(value, str):
        text = value
    else:
        return None

    text = _clean(text)
    concepts = set()

    if re.search(r"\bэлеватор\w*", text):
        concepts.add("элеватор")
    if re.search(r"\bпорт\w*", text):
        concepts.add("порт")
    if re.search(r"силами\s+отправител", text):
        concepts.add("силами отправителя")
    if re.search(r"силами\s+получател", text):
        concepts.add("силами получателя")
    if re.search(r"механизированн\w*\s+погруз", text):
        concepts.add("механизированная погрузка")
    elif re.search(r"\bпогруз\w*", text):
        concepts.add("погрузка")

    return ("loading", frozenset(concepts)) if concepts else ("loading_text", _lemmatize(text))


def _normalize(value: Any, field: str | None = None):
    """Единая точка входа. Возвращает каноническое представление."""
    if value is None:
        return None

    if field == "volume":
        return _norm_volume(value)
    if field == "budget":
        return _norm_budget(value)
    if field == "period":
        return _norm_period(value)
    if field == "loading_conditions":
        return _norm_loading(value)

    # текстовые поля
    if isinstance(value, str):
        return ("text", _plain(value))
    if isinstance(value, (int, float)):
        return ("num", float(value))
    return ("raw", str(value))


# ============================================================
# Сравнение
# ============================================================

def _same_value(a: Any, b: Any, field: str | None = None) -> bool:
    na = _normalize(a, field)
    nb = _normalize(b, field)

    if na is None or nb is None:
        return na == nb

    if na == nb:
        return True

    # ----- period -----
    if field == "period":
        if na[0] == "range" and nb[0] == "range":
            return na[1] == nb[1] and na[2] == nb[2]
        if na[0] == "range" and nb[0] == "text":
            rng = f"{na[1]} - {na[2]}"
            return rng in nb[1] or nb[1] in rng
        if nb[0] == "range" and na[0] == "text":
            rng = f"{nb[1]} - {nb[2]}"
            return rng in na[1] or na[1] in rng
        if na[0] == "text" and nb[0] == "text":
            return na[1] in nb[1] or nb[1] in na[1]

    # ----- budget -----
    if field == "budget":
        if na[0] == "budget" and nb[0] == "budget":
            return abs(na[1] - nb[1]) < 1e-6

    # ----- volume -----
    if field == "volume":
        if na[0] == "qty" and nb[0] == "qty":
            return abs(na[1] - nb[1]) < 1e-6
        if na[0] == "range" and nb[0] == "range":
            return abs(na[1] - nb[1]) < 1e-6 and abs(na[2] - nb[2]) < 1e-6
        # range vs qty — считаем совпадением, если число попадает в диапазон
        if na[0] == "range" and nb[0] == "qty":
            return na[1] - 1e-6 <= nb[1] <= na[2] + 1e-6
        if nb[0] == "range" and na[0] == "qty":
            return nb[1] - 1e-6 <= na[1] <= nb[2] + 1e-6

    # ----- loading_conditions -----
    if field == "loading_conditions":
        if na[0] == "loading" and nb[0] == "loading":
            inter = na[1] & nb[1]
            # достаточно хотя бы одного важного концепта
            if inter & IMPORTANT_LOADING:
                return True
            return bool(inter)
        # structured vs text — принимаем
        if {na[0], nb[0]} == {"loading", "loading_text"}:
            return True

    # ----- company / stations / cargo -----
    if field in ("company", "station_from", "station_to", "cargo"):
        if na[0] == "text" and nb[0] == "text":
            return na[1] in nb[1] or nb[1] in na[1]

    return False


# ============================================================
# Resolver
# ============================================================

def resolve(
    rule_fields: dict[str, FieldResult],
    llm_fields: dict[str, FieldResult],
) -> dict[str, FieldResult]:

    result: dict[str, FieldResult] = {}
    field_names = set(rule_fields) | set(llm_fields)

    for name in field_names:
        rule = rule_fields.get(name) or FieldResult(name)
        llm = llm_fields.get(name) or FieldResult(name)

        rule_found = rule.status == FieldStatus.FOUND and rule.value is not None
        llm_found = llm.status == FieldStatus.FOUND and llm.value is not None
        rule_ambiguous = rule.status == FieldStatus.AMBIGUOUS
        llm_ambiguous = llm.status == FieldStatus.AMBIGUOUS

        # 1. Любая неоднозначность от rule → final ambiguous
        #    (LLM не имеет права «исправлять» rule)
        if rule_ambiguous:
            result[name] = FieldResult(
                name=name,
                status=FieldStatus.AMBIGUOUS,
                value=None,
                source=FieldSource.RULE_LLM,
                confidence=None,
            )
            continue

        # 2. LLM сказал ambiguous, а rule ничего не нашёл
        if llm_ambiguous and not rule_found:
            result[name] = FieldResult(
                name=name,
                status=FieldStatus.AMBIGUOUS,
                value=None,
                source=FieldSource.RULE_LLM,
                confidence=None,
            )
            continue

        # 3. Оба нашли
        if rule_found and llm_found:
            if _same_value(rule.value, llm.value, field=name):
                # Предпочитаем структурированный rule
                result[name] = rule
            else:
                # Реальное расхождение значений
                result[name] = FieldResult(
                    name=name,
                    status=FieldStatus.AMBIGUOUS,
                    value=None,
                    source=FieldSource.RULE_LLM,
                    confidence=None,
                    note="Правило и LLM извлекли разные значения.",
                )
            continue

        # 4. Только rule
        if rule_found:
            result[name] = rule
            continue

        # 5. Только LLM
        if llm_found:
            result[name] = llm
            continue

        # 6. Оба missing
        result[name] = FieldResult(
            name=name,
            status=FieldStatus.MISSING,
            value=None,
            source=FieldSource.RULE_LLM,
            confidence=None,
        )

    return result
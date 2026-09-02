#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evaluate the extractor against a small hand-labelled gold set.

We report two separate numbers per field, because they answer different
questions:
  - status accuracy: did we correctly decide FOUND / AMBIGUOUS / MISSING?
    This is the number that matters most for the actual business goal --
    "don't invent data, know what you don't know."
  - value accuracy: for the fields where gold says FOUND and we also say
    FOUND, did we extract the right value?

Run:
    python eval/evaluate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline import process_file  # noqa: E402
from src.schema import ALL_FIELDS  # noqa: E402
from src import rule_extractor, llm_extractor  # noqa: E402
from src.parsers import extract_text  # noqa: E402

GOLD_PATH = ROOT / "data" / "gold" / "gold.json"
SAMPLES_DIR = ROOT / "data" / "samples"


def _norm(s) -> str:
    return str(s).strip().lower()


def _values_match(field: str, predicted, expected) -> bool:
    if expected is None:
        return True  # gold didn't specify a value to check, only status
    if field in ("company", "station_from", "station_to", "cargo"):
        return _norm(expected) in _norm(predicted) or _norm(predicted) in _norm(expected)
    if field == "volume":
        if not isinstance(predicted, dict):
            return False
        return all(abs(predicted.get(k, -1) - v) < 1e-6 if isinstance(v, (int, float))
                   else predicted.get(k) == v for k, v in expected.items())
    if field == "period":
        if isinstance(expected, dict):
            return isinstance(predicted, dict) and predicted.get("start") == expected.get("start") \
                and predicted.get("end") == expected.get("end")
        return _norm(expected) in _norm(predicted)
    if field == "budget":
        if not isinstance(predicted, dict):
            return False
        ok = abs(predicted.get("amount", -1) - expected.get("amount", -2)) < 1e-6
        if "currency" in expected:
            ok = ok and predicted.get("currency") == expected["currency"]
        return ok
    return _norm(predicted) == _norm(expected)


def evaluate() -> dict:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))

    per_field_status_correct = {f: 0 for f in ALL_FIELDS}
    per_field_total = {f: 0 for f in ALL_FIELDS}
    per_field_value_correct = {f: 0 for f in ALL_FIELDS}
    per_field_value_total = {f: 0 for f in ALL_FIELDS}
    mismatches = []

    completeness_correct = 0

    for filename, expected_fields in gold.items():
        path = SAMPLES_DIR / filename
        if not path.exists():
            print(f"!! sample missing on disk: {filename}", file=sys.stderr)
            continue

        text = extract_text(path)

        rule_fields = rule_extractor.extract(text)
        llm_fields = llm_extractor.run(text)

        print(f"\n{'=' * 60}")
        print(filename)

        for field in ALL_FIELDS:
            rule = rule_fields.get(field)
            llm = llm_fields.get(field)

            print(f"\n[{field}]")
            print("RULE:", rule.to_dict() if rule else None)
            print("LLM: ", llm.to_dict() if llm else None)
            
        result = process_file(path, use_llm=True)  # rule-based only -> reproducible

        for field in ALL_FIELDS:
            exp = expected_fields.get(field)
            if exp is None:
                continue
            per_field_total[field] += 1
            pred = result.fields[field]
            status_ok = pred.status.value == exp["status"]
            if status_ok:
                per_field_status_correct[field] += 1
            else:
                mismatches.append(
                    f"{filename} / {field}: expected status={exp['status']!r}, "
                    f"got status={pred.status.value!r} (value={pred.value!r})"
                )

            if exp["status"] == "found" and pred.status.value == "found":
                per_field_value_total[field] += 1
                if _values_match(field, pred.value, exp.get("value")):
                    per_field_value_correct[field] += 1
                else:
                    mismatches.append(
                        f"{filename} / {field}: value mismatch, expected~{exp.get('value')!r}, "
                        f"got {pred.value!r}"
                    )

        expected_complete = all(
            expected_fields.get(f, {}).get("status") == "found"
            for f in ("company", "station_from", "station_to", "cargo", "volume", "period")
        )
        if result.is_complete() == expected_complete:
            completeness_correct += 1

    n_samples = len(gold)
    report = {
        "n_samples": n_samples,
        "completeness_decision_accuracy": completeness_correct / n_samples,
        "per_field_status_accuracy": {
            f: (per_field_status_correct[f] / per_field_total[f]) if per_field_total[f] else None
            for f in ALL_FIELDS
        },
        "per_field_value_accuracy_when_found": {
            f: (per_field_value_correct[f] / per_field_value_total[f]) if per_field_value_total[f] else None
            for f in ALL_FIELDS
        },
        "mismatches": mismatches,
    }
    return report


def render_markdown(report: dict) -> str:
    lines = [
        "# Результаты оценки качества",
        "",
        f"Выборка: {report['n_samples']} размеченных вручную заявок "
        f"(`data/samples/` + `data/gold/gold.json`).",
        "",
        f"**Точность решения \"заявка полная / неполная\": "
        f"{report['completeness_decision_accuracy']:.0%}**",
        "",
        "## Точность определения статуса поля (found / ambiguous / missing)",
        "",
        "| Поле | Точность |",
        "|---|---|",
    ]
    for f, acc in report["per_field_status_accuracy"].items():
        lines.append(f"| {f} | {acc:.0%} |" if acc is not None else f"| {f} | н/д |")

    lines += [
        "",
        "## Точность значения",
        "",
        "| Поле | Точность |",
        "|---|---|",
    ]
    for f, acc in report["per_field_value_accuracy_when_found"].items():
        lines.append(f"| {f} | {acc:.0%} |" if acc is not None else f"| {f} | н/д |")

    if report["mismatches"]:
        lines += ["", "## Расхождения", ""]
        lines += [f"- {m}" for m in report["mismatches"]]
    else:
        lines += ["", "Расхождений с золотой разметкой не найдено."]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    report = evaluate()
    md = render_markdown(report)
    print(md)
    out_path = ROOT / "eval" / "results.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"\n(also written to {out_path})", file=sys.stderr)

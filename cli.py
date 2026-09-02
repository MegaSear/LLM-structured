#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Usage:
    python cli.py path/to/request.docx
    python cli.py path/to/request.txt --no-llm
    echo "текст заявки" | python cli.py -
"""
from __future__ import annotations

import argparse
import json
import sys
from src import llm_extractor
from src.pipeline import process_file, process_text, summarize

from dotenv import load_dotenv
load_dotenv()
print(f"Доступ к модели LLM: {llm_extractor.available()}")

def main() -> None:
    ap = argparse.ArgumentParser(description="Extract structured data from a freight request.")
    ap.add_argument("path", help="Path to a .txt/.eml/.docx/.pdf/.xlsx file, or '-' to read stdin as text.")
    ap.add_argument("--no-llm", action="store_true", help="Disable the optional LLM fallback pass.")
    ap.add_argument("--pretty", action="store_true", default=True, help="Pretty-print JSON (default).")
    args = ap.parse_args()

    use_llm = False if args.no_llm else None

    if args.path == "-":
        text = sys.stdin.read()
        result = process_text(text, use_llm=use_llm)
    else:
        result = process_file(args.path, use_llm=use_llm)

    out = summarize(result)
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if not out["is_complete"]:
        print("\n--- Вопросы клиенту ---", file=sys.stderr)
        for q in out["clarifying_questions"]:
            print(f"- {q}", file=sys.stderr)


if __name__ == "__main__":
    main()

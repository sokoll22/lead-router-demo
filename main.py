#!/usr/bin/env python3
"""CLI-запуск пайплайна: текст заявки → извлечение → CRM → уведомление."""
import argparse
import glob
import os
import sys

from extractor import extract_lead
from crm import save_lead
from notifier import send


def process_one(path: str, mode: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lead = extract_lead(text, mode=mode)
    record_id = save_lead(lead)
    send(record_id, lead)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lead Router demo")
    parser.add_argument("--input", required=True, help="файл заявки или папка с файлами")
    parser.add_argument("--mode", choices=["llm", "mock"], default=None,
                         help="llm — Anthropic API, mock — эвристика без API-ключа. "
                              "По умолчанию: llm при наличии ANTHROPIC_API_KEY, иначе mock.")
    parser.add_argument("--batch", action="store_true", help="обработать все файлы в папке --input")
    args = parser.parse_args()

    mode = args.mode or ("llm" if os.environ.get("ANTHROPIC_API_KEY") else "mock")

    if args.batch or os.path.isdir(args.input):
        paths = sorted(glob.glob(os.path.join(args.input, "*.txt")))
        if not paths:
            print(f"Нет .txt файлов в {args.input}", file=sys.stderr)
            sys.exit(1)
        for p in paths:
            process_one(p, mode)
    else:
        process_one(args.input, mode)


if __name__ == "__main__":
    main()

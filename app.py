#!/usr/bin/env python3
"""Веб-демо Lead Router — то, что показывается агентствам и пишется на видео.

Запуск:
    python3 app.py
    → http://127.0.0.1:5001

Ничего не сохраняет: текст заявки живёт только в оперативной памяти на время
запроса. Это не косметика, а требование — агентство не может отдавать данные
своего клиента в чужой сервис (GDPR), поэтому демо не должно ничего хранить.
"""
import os
import time

from flask import Flask, jsonify, render_template, request

from extractor import extract_lead

app = Flask(__name__)

# Поля, которые извлекаются дословно из текста, — их можно подсветить в источнике.
# Остальные (project_type, urgency, summary) — вывод модели, а не цитата.
VERBATIM_FIELDS = ("name", "company", "contact", "budget")

FIELD_LABELS = (
    ("name", "Name"),
    ("company", "Company"),
    ("contact", "Contact"),
    ("project_type", "Project type"),
    ("budget", "Budget"),
    ("urgency", "Urgency"),
)

# Ручная обработка одной заявки — консервативная оценка: прочитать письмо,
# открыть CRM, перенести поля, поставить задачу менеджеру.
MANUAL_SECONDS = 360


def _resolve_mode() -> str:
    requested = (request.json or {}).get("mode") if request.is_json else None
    if requested in ("llm", "mock"):
        return requested
    return "llm" if os.environ.get("ANTHROPIC_API_KEY") else "mock"


@app.get("/")
def index():
    samples = _load_samples()
    return render_template(
        "index.html",
        samples=samples,
        has_key=bool(os.environ.get("ANTHROPIC_API_KEY")),
        manual_seconds=MANUAL_SECONDS,
    )


@app.post("/api/parse")
def parse():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Paste an enquiry first."}), 400
    if len(text) > 20000:
        return jsonify({"error": "That enquiry is too long — 20,000 characters max."}), 400

    mode = _resolve_mode()
    started = time.perf_counter()
    try:
        lead = extract_lead(text, mode=mode)
    except Exception as exc:  # noqa: BLE001 — показываем причину прямо в интерфейсе
        return jsonify({"error": str(exc)}), 502
    elapsed = time.perf_counter() - started

    fields = []
    for key, label in FIELD_LABELS:
        value = getattr(lead, key, "") or ""
        fields.append({
            "key": key,
            "label": label,
            "value": value,
            "span": _locate(text, value) if key in VERBATIM_FIELDS else None,
            "quoted": key in VERBATIM_FIELDS,
        })

    return jsonify({
        "fields": fields,
        "summary": lead.summary,
        "elapsed": round(elapsed, 2),
        "manual_seconds": MANUAL_SECONDS,
        "mode": mode,
        "record_id": f"{abs(hash(text)) % 0xFFFFFF:06x}",
    })


def _locate(text: str, value: str):
    """Границы значения в исходном тексте — для подсветки. None, если дословно
    не нашлось (модель могла нормализовать написание)."""
    if not value:
        return None
    index = text.find(value)
    if index == -1:
        index = text.lower().find(value.lower())
    return [index, index + len(value)] if index != -1 else None


def _load_samples():
    folder = os.path.join(os.path.dirname(__file__), "sample_leads")
    titles = {
        "lead_1.txt": "Agency, urgent",
        "lead_2.txt": "Agency, exploring",
        "lead_3.txt": "Small, low budget",
    }
    samples = []
    for filename in sorted(titles):
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                samples.append({"title": titles[filename], "text": f.read().strip()})
    return samples


if __name__ == "__main__":
    # 5001, а не 5000: на macOS порт 5000 занят AirPlay Receiver.
    app.run(host="127.0.0.1", port=5001, debug=False)

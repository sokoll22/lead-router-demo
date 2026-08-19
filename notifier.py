"""Уведомление команды о новом лиде. В демо — консоль + лог-файл.
Для реального клиента send() заменяется на Telegram Bot API / Slack webhook /
email — сигнатура send(record_id, lead) не меняется, остальной пайплайн не трогаем.
"""
import os
from datetime import datetime

from lead_data import LeadData

LOG_PATH = os.path.join(os.path.dirname(__file__), "notifications.log")


def send(record_id: str, lead: LeadData) -> None:
    message = _format(record_id, lead)
    print(message)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")

    # Реальная интеграция (пример, требует TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID):
    # import requests
    # token = os.environ.get("TELEGRAM_BOT_TOKEN")
    # chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    # if token and chat_id:
    #     requests.post(
    #         f"https://api.telegram.org/bot{token}/sendMessage",
    #         json={"chat_id": chat_id, "text": message},
    #         timeout=10,
    #     )


def _format(record_id: str, lead: LeadData) -> str:
    urgency_flag = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(lead.urgency, "⚪")
    return (
        f"{urgency_flag} New lead [{record_id}] — {lead.name or 'no name'} "
        f"({lead.company or 'company not stated'}): {lead.project_type or 'type unclear'}, "
        f"budget: {lead.budget or '—'}, contact: {lead.contact or '—'}. "
        f"{lead.summary}"
    )

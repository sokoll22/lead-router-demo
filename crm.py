"""Заглушка CRM для демо. Интерфейс save_lead() — единственное, что видит
остальной пайплайн. Для реального клиента этот файл заменяется на адаптер
конкретной CRM (Airtable/HubSpot/Notion/Pipedrive REST API), сигнатура
save_lead(lead: LeadData) -> str (возвращает id записи) не меняется.
"""
import json
import os
import uuid

from lead_data import LeadData

STORE_PATH = os.path.join(os.path.dirname(__file__), "crm_records.json")


def save_lead(lead: LeadData) -> str:
    records = _load()
    record_id = str(uuid.uuid4())[:8]
    record = {"id": record_id, **lead.to_dict()}
    records.append(record)
    _save(records)
    return record_id


def _load() -> list:
    if not os.path.exists(STORE_PATH):
        return []
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(records: list) -> None:
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

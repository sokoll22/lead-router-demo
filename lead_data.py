"""Общая структура данных лида — единый контракт между всеми узлами пайплайна."""
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone


@dataclass
class LeadData:
    name: str = ""
    company: str = ""
    contact: str = ""          # email или телефон
    project_type: str = ""     # напр. "автоматизация", "чат-бот", "сайт"
    budget: str = ""           # как указано в заявке, без нормализации
    urgency: str = ""          # "высокая" / "средняя" / "низкая" / "не указана"
    summary: str = ""          # суть запроса в одном-двух предложениях
    raw_text: str = ""         # исходный текст заявки, для аудита
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

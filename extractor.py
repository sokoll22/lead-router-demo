"""Извлечение структурных полей из свободного текста заявки.

Два режима за одним интерфейсом extract_lead(text, mode):
  - "llm"  — реальный вызов Anthropic API (Claude), структурированный JSON-ответ.
  - "mock" — эвристика на регулярках/ключевых словах, без внешних вызовов.
             Нужна, чтобы демонстрировать и тестировать пайплайн без API-ключа
             и без затрат на токены.

Эвристика понимает и английский, и русский текст: демо показывается англоязычным
агентствам, но тестовые заявки исторически были на русском.
"""
import json
import os
import re

from lead_data import LeadData

SYSTEM_PROMPT = """You extract structured data from an inbound client enquiry \
sent to an automation agency. Return ONLY valid JSON with these keys:
name, company, contact, project_type, budget, urgency, summary.
Use an empty string "" for anything not mentioned. urgency must be one of:
"high", "medium", "low", "not stated". summary is 1-2 sentences in English \
describing what the prospect actually wants."""

FIELDS = ("name", "company", "contact", "project_type", "budget", "urgency", "summary")


def extract_lead(text: str, mode: str = "mock") -> LeadData:
    if mode == "llm":
        fields = _extract_via_llm(text)
    else:
        fields = _extract_via_heuristics(text)
    return LeadData(raw_text=text, **fields)


def _extract_via_llm(text: str) -> dict:
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "Режим llm требует пакет anthropic (pip install -r requirements.txt)"
        ) from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Режим llm требует переменную окружения ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    raw = response.content[0].text
    # LLM иногда оборачивает JSON в ```json ... ``` — снимаем обёртку при необходимости.
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    data = json.loads(raw)
    return {k: data.get(k, "") for k in FIELDS}


# --- эвристический режим -----------------------------------------------------

_HIGH_URGENCY = (
    "asap", "urgent", "urgently", "right away", "as soon as possible", "immediately",
    "this week", "срочно", "асап", "как можно скорее", "сегодня",
)
_LOW_URGENCY = (
    "no rush", "no hurry", "not urgent", "next quarter", "sometime",
    "не горит", "не спешим", "в течение месяца",
)
_PROJECT_KEYWORDS = (
    ("chatbot", "chatbot"), ("chat bot", "chatbot"), ("чат-бот", "chatbot"),
    ("чатбот", "chatbot"),
    ("intake", "lead intake"), ("enquir", "lead intake"), ("inquir", "lead intake"),
    ("lead", "lead intake"), ("заяв", "lead intake"),
    ("crm", "CRM integration"),
    ("scrap", "data scraping"), ("parsing", "data scraping"), ("парсинг", "data scraping"),
    ("report", "reporting / dashboard"), ("dashboard", "reporting / dashboard"),
    ("отчёт", "reporting / dashboard"),
    ("google sheet", "data pull → spreadsheet"), ("spreadsheet", "data pull → spreadsheet"),
    ("pull data", "data pull → spreadsheet"),
    ("agent", "AI agent"), ("агент", "AI agent"),
    ("n8n", "workflow automation (n8n)"), ("zapier", "workflow automation"),
    ("automat", "process automation"), ("автоматизац", "process automation"),
    ("website", "website build"), ("сайт", "website build"),
)


def _extract_via_heuristics(text: str) -> dict:
    """Грубый экстрактор для демо-режима без LLM. Достаточно, чтобы показать
    работу пайплайна целиком; качество извлечения заведомо ниже, чем у LLM."""
    lowered = text.lower()

    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    # Телефон — только с ведущим "+", иначе регулярка путает его с диапазоном
    # бюджета вида "1500-3000".
    phone = re.search(r"(\+\d[\d\s\-()]{7,}\d)", text)
    contact = email.group(0) if email else (phone.group(0) if phone else "")

    name = _find_name(text)
    company = _find_company(text)
    budget = _find_budget(text)

    if any(w in lowered for w in _HIGH_URGENCY):
        urgency = "high"
    elif any(w in lowered for w in _LOW_URGENCY):
        urgency = "low"
    elif budget:
        urgency = "medium"
    else:
        urgency = "not stated"

    project_type = ""
    for keyword, label in _PROJECT_KEYWORDS:
        if keyword in lowered:
            project_type = label
            break

    # Самое содержательное из первых предложений: приветствие ("hey, saw your
    # profile.") формально проходит любой порог длины, но ничего не сообщает.
    sentences = [" ".join(s.split()) for s in re.split(r"(?<=[.!?])\s+", text.strip())]
    sentences = [s for s in sentences if len(s) > 15]
    summary = max(sentences[:4], key=len)[:200] if sentences else " ".join(text.split())[:200]

    return {
        "name": name, "company": company, "contact": contact,
        "project_type": project_type, "budget": budget,
        "urgency": urgency, "summary": summary,
    }


def _find_name(text: str) -> str:
    # Триггерная фраза регистронезависима — (?i:...), — а само имя обязано быть
    # с заглавной буквы, иначе в имя попадает начало email-адреса.
    patterns = (
        r"(?i:my name is|this is|i'm|i am)\s+([A-Z][a-z]+(?:[ ][A-Z][a-z]+)?)",
        r"(?i:меня зовут|это)\s+([А-ЯЁ][а-яёA-Za-z]+(?:[ ][А-ЯЁ][а-яё]+)?)",
        # Подпись в конце письма: "Best,\nSarah" / "Thanks, Mike Chen".
        r"(?i:regards|best|thanks|cheers|sincerely)[,]?[ \t]*\n?[ \t]*"
        r"([A-Z][a-z]+(?:[ ][A-Z][a-z]+)?)\b(?!@)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


_COMPANY_STOPWORDS = ("the ", "our ", "your ", "monday", "tuesday", "wednesday",
                      "thursday", "friday", "ai ", "we ", "us ")


def _find_company(text: str) -> str:
    # Именованная сущность приоритетнее кавычек: в кавычки чаще берут не название
    # компании, а цитату вроде "AI automation".
    # Внутри названия допускаем только пробел, не \s: иначе через перенос строки
    # в название затягивается первое слово следующего предложения.
    patterns = (
        r"(?i:at|from|with|represent|founder of|work for|i run)[ ]+"
        r"([A-Z][\w&]*(?:[ ][A-Z][\w&]*){0,2})",
        r"компани\w*[ ]+([A-ZА-ЯЁ][\w]*(?:[ ][A-ZА-ЯЁ][\w]*){0,2})",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            candidate = match.group(1).strip(" .,")
            if len(candidate) > 2 and not candidate.lower().startswith(_COMPANY_STOPWORDS):
                return candidate
    quoted = re.search(r"[«»\"]([^«»\"]{2,40})[«»\"]", text)
    return quoted.group(1).strip() if quoted else ""


def _find_budget(text: str) -> str:
    patterns = (
        r"\$\s?[\d,]+(?:\.\d+)?\s?[kK]?(?:\s?[-–—]\s?\$?[\d,]+\s?[kK]?)?",
        r"[\d,]+\s?(?:USD|usd|EUR|eur|долларов)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return " ".join(match.group(0).split())
    return ""

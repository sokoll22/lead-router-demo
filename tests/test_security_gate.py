"""
Демка публичная (нет логина), а с ANTHROPIC_API_KEY на сервере каждый вызов —
реальные деньги. Добавлено 21.08.2026 после того, как Макс спросил, что будет,
если демку без него найдёт и начнёт крутить кто-то посторонний: раньше факта
наличия ключа на сервере хватало, чтобы ЛЮБОЙ посетитель включил платный режим
(а через POST /api/parse с {"mode": "llm"} в теле — даже в обход интерфейса,
без всякого ?key=).

Эти тесты фиксируют контракт: живой режим включается ТОЛЬКО когда совпали
оба условия — ANTHROPIC_API_KEY задан на сервере И вызывающий предъявил
верный DEMO_ACCESS_TOKEN (через ?key=... на странице или заголовок
X-Demo-Key на /api/parse). Любая из комбинаций без верного токена должна
тихо откатываться на mock, а не падать и не включать платный режим.
"""
import pytest


class FakeLead:
    """Стаб вместо extract_lead — не даёт тесту реально дёрнуть Anthropic API,
    и одновременно фиксирует, каким mode его реально вызвали."""

    def __init__(self, mode):
        self.name = self.company = self.contact = self.project_type = self.budget = ""
        self.urgency = "not stated"
        self.summary = f"MODE={mode}"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_TOKEN", "s3cr3t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    import importlib
    import app as appmod
    importlib.reload(appmod)  # подхватить переменные окружения из monkeypatch

    monkeypatch.setattr(appmod, "extract_lead", lambda text, mode="mock": FakeLead(mode))
    return appmod.app.test_client()


def test_index_without_key_has_empty_demo_key(client):
    body = client.get("/").get_data(as_text=True)
    assert 'const DEMO_KEY = "";' in body


def test_index_with_wrong_key_has_empty_demo_key(client):
    body = client.get("/?key=wrong").get_data(as_text=True)
    assert 'const DEMO_KEY = "";' in body


def test_index_with_correct_key_exposes_it(client):
    body = client.get("/?key=s3cr3t").get_data(as_text=True)
    assert 'const DEMO_KEY = "s3cr3t";' in body


def test_parse_without_header_falls_back_to_mock_despite_api_key(client):
    r = client.post("/api/parse", json={"text": "hello, this is a test enquiry"})
    assert r.get_json()["mode"] == "mock"


def test_parse_client_requested_llm_without_token_still_mock(client):
    """Старая дыра: клиент мог сам попросить mode='llm' в теле запроса и
    получить его просто потому, что ключ есть на сервере. Теперь без верного
    токена это игнорируется."""
    r = client.post(
        "/api/parse",
        json={"text": "hello, this is a test enquiry", "mode": "llm"},
    )
    assert r.get_json()["mode"] == "mock"


def test_parse_with_correct_token_header_enables_llm(client):
    r = client.post(
        "/api/parse",
        json={"text": "hello, this is a test enquiry"},
        headers={"X-Demo-Key": "s3cr3t"},
    )
    assert r.get_json()["mode"] == "llm"


def test_parse_with_wrong_token_header_stays_mock(client):
    r = client.post(
        "/api/parse",
        json={"text": "hello, this is a test enquiry"},
        headers={"X-Demo-Key": "wrong-token"},
    )
    assert r.get_json()["mode"] == "mock"

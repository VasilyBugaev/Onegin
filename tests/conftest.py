import os

os.environ.setdefault("LLM_BASE_URL", "http://llm.test/v1")
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("DATA_DIR", "/tmp")
os.environ.setdefault("TIMEZONE", "Europe/Moscow")

import pytest

from core import db
from core.messages import Message


@pytest.fixture(autouse=True)
async def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    await db.init()


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    async def chat(messages, on_token):
        calls.append(list(messages))
        for token in ["Я", " Онегин"]:
            await on_token(token)
        return Message(role="assistant", content="Я Онегин")

    monkeypatch.setattr("core.llm.client.chat", chat)
    return calls

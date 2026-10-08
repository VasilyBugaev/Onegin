import asyncio

from fastapi.testclient import TestClient

from core import db
from core.app import app


def receive_answer(ws) -> list[dict]:
    """Читает события, пока не придёт done или error."""
    events = []
    while True:
        event = ws.receive_json()
        events.append(event)
        if event["type"] in ("done", "error"):
            return events


def test_chat_streams_answer(fake_llm):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"conversation_id": None, "text": "Как тебя зовут?"})
        events = receive_answer(ws)
        assert events[0]["type"] == "start"
        assert events[1] == {"type": "token", "text": "Я"}
        assert events[2] == {"type": "token", "text": " Онегин"}
        assert events[-1] == {"type": "done"}


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_request_keeps_connection_alive(fake_llm):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"text": 5})
        assert ws.receive_json()["type"] == "error"

        ws.send_json({"conversation_id": None, "text": "Привет"})
        events = receive_answer(ws)

        assert events[0]["type"] == "start"
        assert events[-1] == {"type": "done"}


def test_second_request_stores_in_same_dialogue(fake_llm):
    with TestClient(app) as client, client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"conversation_id": None, "text": "Как тебя зовут?"})
        events = receive_answer(ws)
        conversation_id = events[0]["conversation_id"]
        ws.send_json({"conversation_id": str(conversation_id), "text": "Как тебя зовут?"})
        events = receive_answer(ws)
        assert events[0]["conversation_id"] == conversation_id
        messages = asyncio.run(db.load_messages(conversation_id=conversation_id))
        assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]

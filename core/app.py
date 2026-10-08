import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core import db
from core.agent.loop import handle_user_message

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    text: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    await ws.accept()

    async def send_token(token: str) -> None:
        await ws.send_json({"type": "token", "text": token})

    try:
        while True:
            data = await ws.receive_json()
            try:
                request = ChatRequest.model_validate(data)
                conv_id = request.conversation_id
                if conv_id is None:
                    conv_id = await db.create_conversation()
                await ws.send_json({"type": "start", "conversation_id": conv_id})
                await handle_user_message(
                    conversation_id=conv_id, text=request.text, on_token=send_token
                )
                await ws.send_json({"type": "done"})
            except WebSocketDisconnect:
                raise
            except Exception as error:
                log.exception("chat failed")
                await ws.send_json({"type": "error", "message": str(error)})
    except WebSocketDisconnect:
        pass

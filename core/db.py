import aiosqlite

from core.config import settings
from core.messages import Message

DB_PATH = settings.data_dir / "onegin.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT,
    tool_calls TEXT,
    tool_call_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def init() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript(SCHEMA)
        await db.commit()


async def create_conversation() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO conversations DEFAULT VALUES")
        await db.commit()
        conversation_id = cursor.lastrowid
        assert conversation_id is not None
        return conversation_id


async def latest_conversation() -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM conversations ORDER BY id DESC LIMIT 1")
        conversation_info = await cursor.fetchone()
        return conversation_info[0] if conversation_info else None


async def add_message(conversation_id: int, message: Message) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, message.role, message.content),
        )
        await db.commit()


async def load_messages(conversation_id: int, limit: int = 30) -> list[Message]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        )
        result = list(await cursor.fetchall())
        return [Message(role=role, content=content) for role, content in reversed(result)]


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        await init()
        cid = await create_conversation()
        await add_message(cid, Message(role="user", content="проверка"))
        await add_message(cid, Message(role="assistant", content="слышу"))
        print(cid, await latest_conversation(), await load_messages(cid))

    asyncio.run(main())

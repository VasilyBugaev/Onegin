from core import db
from core.messages import Message


async def test_load_messages_return_last_ones_in_order():
    conversation_id = await db.create_conversation()
    for i in range(5):
        await db.add_message(conversation_id, Message(role="user", content=str(i)))

    loaded = await db.load_messages(conversation_id, limit=3)

    assert [m.content for m in loaded] == ["2", "3", "4"]


async def test_load_latest_from_empty_db():
    latest = await db.latest_conversation()
    assert latest is None


async def test_load_messages_from_different_dialogues():

    async def create_conversation_and_add_messages(start_idx: int, end_idx: int) -> int:
        conversation_id = await db.create_conversation()
        for i in range(start_idx, end_idx):
            await db.add_message(conversation_id, Message(role="user", content=str(i)))
        return conversation_id

    conversation_id_1 = await create_conversation_and_add_messages(start_idx=0, end_idx=5)
    conversation_id_2 = await create_conversation_and_add_messages(start_idx=5, end_idx=10)
    loaded_1 = await db.load_messages(conversation_id=conversation_id_1, limit=5)
    loaded_2 = await db.load_messages(conversation_id=conversation_id_2, limit=5)

    assert [m.content for m in loaded_1] == ["0", "1", "2", "3", "4"]
    assert [m.content for m in loaded_2] == ["5", "6", "7", "8", "9"]

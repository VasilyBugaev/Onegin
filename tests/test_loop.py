from core import db
from core.agent.loop import handle_user_message


async def ignore(token: str) -> None:
    pass


async def test_tokens_are_passed_to_callback(fake_llm):
    received = []

    async def collect(token: str) -> None:
        received.append(token)

    conversation_id = await db.create_conversation()
    await handle_user_message(conversation_id, "Привет", collect)

    assert received == ["Я", " Онегин"]


async def test_no_system_prompt_in_db(fake_llm):
    conversation_id = await db.create_conversation()
    await handle_user_message(conversation_id, "Привет", ignore)
    messages = await db.load_messages(conversation_id)

    assert [m.role for m in messages] == ["user", "assistant"]
    assert [m.content for m in messages] == ["Привет", "Я Онегин"]


async def test_double_call(fake_llm):
    conversation_id = await db.create_conversation()
    await handle_user_message(conversation_id, "Запомни 47", ignore)
    await handle_user_message(conversation_id, "Какое число?", ignore)

    assert len(fake_llm) == 2

    second = fake_llm[1]
    assert second[0].role == "system"
    assert "Онегин" in second[0].content
    assert [m.content for m in second[1:]] == ["Запомни 47", "Я Онегин", "Какое число?"]

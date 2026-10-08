from core import db
from core.agent.prompts import system_prompt
from core.llm import client as llm
from core.messages import Message


async def run(messages: list[Message], on_token: llm.OnToken, max_steps: int = 6) -> list[Message]:
    new = []
    for _ in range(max_steps):
        reply = await llm.chat(messages=messages, on_token=on_token)
        messages.append(reply)
        new.append(reply)
        if not reply.tool_calls:
            return new
    return new


async def handle_user_message(conversation_id: int, text: str, on_token: llm.OnToken) -> None:
    await db.add_message(
        conversation_id=conversation_id, message=Message(role="user", content=text)
    )
    loaded_messages = await db.load_messages(conversation_id=conversation_id)
    prompt_messages = [Message(role="system", content=system_prompt()), *loaded_messages]
    response_messages = await run(prompt_messages, on_token=on_token)
    for response in response_messages:
        await db.add_message(conversation_id=conversation_id, message=response)

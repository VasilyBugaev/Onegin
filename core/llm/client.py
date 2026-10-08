import logging
import time
from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI

from core.config import settings
from core.messages import Message

log = logging.getLogger(__name__)

client = AsyncOpenAI(base_url=settings.llm_base_url, api_key="ollama")

OnToken = Callable[[str], Awaitable[None]]


async def chat(messages: list[Message], on_token: OnToken) -> Message:
    started = time.perf_counter()
    stream = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[message.to_api() for message in messages],
        stream=True,
        reasoning_effort="none",
        stream_options={"include_usage": True},
    )
    parts, usage = [], None
    async for chunk in stream:
        if chunk.usage:
            usage = chunk.usage
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        content = delta.content
        if content:
            parts.append(content)
            await on_token(content)
    log.info(
        f"Time: {time.perf_counter() - started}, usage: {usage} for model : {settings.llm_model}"
    )
    return Message(role="assistant", content="".join(parts))


if __name__ == "__main__":
    import asyncio

    async def show(token: str) -> None:
        print(token, end="", flush=True)

    async def main() -> None:
        logging.basicConfig(level=logging.INFO)
        reply = await chat(
            [
                Message(
                    role="user", content="Расскажи в трех предложениях, кто такой Евгений Онегин"
                )
            ],
            show,
        )
        print("\n---\n", reply)

    asyncio.run(main())

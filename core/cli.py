import asyncio
import readline  # noqa: F401

from core import db
from core.agent.loop import handle_user_message


async def show(token: str) -> None:
    print(token, end="", flush=True)


async def main() -> None:
    await db.init()
    conversation_id = await db.latest_conversation()
    if not conversation_id:
        conversation_id = await db.create_conversation()
    while True:
        # В CLI один пользователь, можно заблокировать
        text = input("> ").strip()  # noqa: ASYNC250
        text = text.encode("utf-8", "surrogateescape").decode("utf-8", "ignore")
        if not text:
            continue
        elif text == "/new":
            conversation_id = await db.create_conversation()
        else:
            await handle_user_message(conversation_id=conversation_id, text=text, on_token=show)
            print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print()

from typing import Literal, cast

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

Role = Literal["system", "user", "assistant", "tool"]


class Message(BaseModel):
    role: Role
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None

    def to_api(self) -> ChatCompletionMessageParam:
        return cast(ChatCompletionMessageParam, self.model_dump(exclude_none=True))

import pytest
from pydantic import ValidationError

from core.messages import Message


def test_to_api_drops_empty_fields():
    message = Message(role="user", content="привет")
    assert message.to_api() == {"role": "user", "content": "привет"}


def test_unknown_role_is_rejected():
    with pytest.raises(ValidationError):
        Message.model_validate({"role": "assistance", "content": "x"})

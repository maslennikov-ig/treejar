import pytest

from src.models.system_prompt import SystemPrompt


@pytest.mark.asyncio
async def test_create_system_prompt_fields():
    prompt = SystemPrompt(
        name="sales_agent",
        content="You are a helpful sales assistant.",
        version=1,
        is_active=True,
    )
    assert prompt.name == "sales_agent"
    assert prompt.content == "You are a helpful sales assistant."
    assert prompt.version == 1
    assert prompt.is_active is True

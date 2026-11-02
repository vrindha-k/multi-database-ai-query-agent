from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from anthropic.types import TextBlock, ToolUseBlock

from app.agent import Agent


def response(*blocks, stop="tool_use"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop)


def call(id_, name, **args):
    return ToolUseBlock(type="tool_use", id=id_, name=name, input=args)


async def test_multiple_tools_error_recovery():
    session = AsyncMock()
    session.list_tools.return_value = SimpleNamespace(tools=[])
    session.call_tool.side_effect = [
        SimpleNamespace(structuredContent={"ok": True, "data": []}, isError=False),
        SimpleNamespace(structuredContent={"ok": False, "error": "bad SQL"}, isError=False),
        SimpleNamespace(structuredContent={"ok": True, "data": {"rows": [[42]]}}, isError=False),
    ]
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(
                side_effect=[
                    response(
                        call("a", "list_tables", database_id="hr"),
                        call("b", "run_query", database_id="hr", sql="bad"),
                    ),
                    response(call("c", "run_query", database_id="hr", sql="SELECT 42")),
                    response(TextBlock(type="text", text="42"), stop="end_turn"),
                ]
            )
        )
    )
    result = await Agent(session, client, "test").ask("Count", "hr")
    assert result.text == "42"
    assert session.call_tool.await_count == 3
    messages = client.messages.create.call_args_list[1].kwargs["messages"]
    assert messages[2]["content"][0]["tool_use_id"] == "a"
    assert messages[2]["content"][1]["is_error"] is True


async def test_database_selection_is_enforced():
    session = AsyncMock()
    session.list_tools.return_value = SimpleNamespace(tools=[])
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(
                side_effect=[
                    response(call("a", "run_query", database_id="hr", sql="SELECT 1")),
                    response(TextBlock(type="text", text="Blocked"), stop="end_turn"),
                ]
            )
        )
    )
    answer = await Agent(session, client, "test").ask("Count", "ecommerce")
    session.call_tool.assert_not_awaited()
    assert answer.trace[0]["result"]["ok"] is False


async def test_turn_budget():
    session = AsyncMock()
    session.list_tools.return_value = SimpleNamespace(tools=[])
    session.call_tool.side_effect = RuntimeError("secret driver failure")
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(return_value=response(call("a", "run_query", sql="SELECT 1")))
        )
    )
    with pytest.raises(RuntimeError, match="limit"):
        await Agent(session, client, "test", max_turns=1).ask("Count")

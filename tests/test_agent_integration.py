import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from anthropic.types import TextBlock, ToolUseBlock

from app.agent import Agent, mcp_session


@pytest.mark.integration
@pytest.mark.parametrize("database_id", ["ecommerce", "hr"])
async def test_question_to_real_mcp_with_mock_claude(registry, database_id):
    """Mock only the paid API boundary; use real SDK models, MCP transport and PostgreSQL."""
    examples = json.loads((Path(__file__).parents[1] / "examples/verified.json").read_text())
    example = next(e for e in examples if e["database_id"] == database_id)
    names = [t["table_name"] for t in registry.list_tables(database_id)]

    def response(index, tool, args):
        return SimpleNamespace(
            content=[ToolUseBlock(type="tool_use", id=f"call_{index}", name=tool, input=args)],
            stop_reason="tool_use",
        )

    replies = [
        response(0, "list_databases", {}),
        response(1, "list_tables", {"database_id": database_id}),
        response(2, "get_schema", {"database_id": database_id, "table_names": names}),
        response(3, "run_query", {"database_id": database_id, "sql": example["sql"]}),
        response(4, "explain_query", {"database_id": database_id, "sql": example["sql"]}),
        SimpleNamespace(
            content=[TextBlock(type="text", text="Mock Claude answer")], stop_reason="end_turn"
        ),
    ]
    client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=replies)))
    async with mcp_session() as session:
        answer = await Agent(session, client, "mock").ask(example["question"], database_id)
    assert all(step["result"]["ok"] for step in answer.trace)
    result = answer.trace[3]["result"]["data"]
    assert result["rows"] == example["expected"]["rows"]
    assert answer.trace[4]["result"]["data"]["plan"]

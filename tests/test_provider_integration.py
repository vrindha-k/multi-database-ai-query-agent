import json

import httpx
import pytest

from app.agent import mcp_session
from app.providers import OllamaProvider, ToolAgent


@pytest.mark.integration
@pytest.mark.parametrize("database_id", ["ecommerce", "hr"])
async def test_local_provider_real_mcp_database_pipeline(registry, database_id):
    tables = registry.list_tables(database_id)
    name = tables[0]["table_name"]
    expected = registry.run_query(database_id, f"SELECT count(*) FROM {name}")["rows"]
    steps = iter(
        [
            ("list_databases", {}),
            ("list_tables", {"database_id": database_id}),
            ("get_schema", {"database_id": database_id, "table_names": [name]}),
            ("run_query", {"database_id": database_id, "sql": f"SELECT count(*) FROM {name}"}),
        ]
    )

    def handler(request):
        body = json.loads(request.content)
        step = next(steps, None)
        if step is None:
            assert json.loads(body["messages"][-1]["content"])["data"]["rows"] == expected
            message = {"role": "assistant", "content": "Verified count from PostgreSQL"}
        else:
            tool, args = step
            message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": tool, "arguments": args}},
                ],
            }
        return httpx.Response(200, json={"done": True, "message": message})

    http = httpx.AsyncClient(base_url="http://localhost", transport=httpx.MockTransport(handler))
    provider = OllamaProvider("http://localhost", "test", http)
    try:
        async with mcp_session() as session:
            answer = await ToolAgent(session, provider).ask(
                "Count the discovered table", database_id
            )
        assert all(entry["result"]["ok"] for entry in answer.trace)
        assert answer.trace[-1]["result"]["data"]["rows"] == expected
    finally:
        await provider.close()

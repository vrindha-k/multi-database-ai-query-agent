import json

from app.agent import mcp_session


async def test_real_stdio_discovery_and_call(monkeypatch):
    monkeypatch.setenv("DATABASES_JSON", "[]")
    monkeypatch.setenv("DATABASE_CONFIG_FILE", "")
    # No DB or API key is needed for this actual subprocess + JSON-RPC exchange.
    monkeypatch.delenv("DATABASE_CONFIG_FILE", raising=False)
    async with mcp_session() as session:
        names = {t.name for t in (await session.list_tools()).tools}
        assert names == {
            "list_databases",
            "list_tables",
            "get_schema",
            "run_query",
            "explain_query",
        }
        result = await session.call_tool("list_databases", {})
        payload = result.structuredContent or json.loads(result.content[0].text)
        assert payload == {"ok": True, "data": []}
        result = await session.call_tool("run_query", {"database_id": "unknown", "sql": "SELECT 1"})
        assert result.structuredContent["ok"] is False

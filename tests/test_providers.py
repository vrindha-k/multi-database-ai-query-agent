import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from google.genai import types

from app.providers import GeminiProvider, OllamaProvider, ProviderError, ToolAgent, execute_tool

TOOLS = [SimpleNamespace(name="run_query", description="read", inputSchema={"type": "object"})]


def session():
    s = AsyncMock()
    s.list_tools.return_value = SimpleNamespace(tools=TOOLS)
    s.call_tool.return_value = SimpleNamespace(
        isError=False,
        structuredContent={"ok": True, "data": {"rows": [[720]]}},
    )
    return s


async def test_ollama_real_http_contract_and_mcp_loop():
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            assert body["tools"][0]["function"]["name"] == "run_query"
            return httpx.Response(
                200,
                json={
                    "done": True,
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "run_query",
                                    "arguments": {
                                        "database_id": "ecommerce",
                                        "sql": "SELECT count(*) FROM orders",
                                    },
                                }
                            }
                        ],
                    },
                },
            )
        assert body["messages"][-1]["role"] == "tool"
        assert json.loads(body["messages"][-1]["content"])["data"]["rows"] == [[720]]
        return httpx.Response(
            200,
            json={
                "done": True,
                "message": {
                    "role": "assistant",
                    "content": "There are 720 orders.",
                },
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost")
    provider = OllamaProvider("http://localhost", "test", http)
    s = session()
    try:
        answer = await ToolAgent(s, provider).ask("Count orders", "ecommerce")
        assert answer.text == "There are 720 orders."
        s.call_tool.assert_awaited_once()
    finally:
        await provider.close()


async def test_gemini_preserves_signatures_and_function_response_ids():
    call_content = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(
                    name="run_query",
                    args={"database_id": "ecommerce", "sql": "SELECT 720"},
                    id="c1",
                ),
                thought_signature=b"opaque-signature",
            )
        ],
    )
    final = types.Content(role="model", parts=[types.Part.from_text(text="720 orders")])
    replies = [
        types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=c,
                    finish_reason=types.FinishReason.STOP,
                )
            ]
        )
        for c in (call_content, final)
    ]
    generate = AsyncMock(side_effect=replies)
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    provider = GeminiProvider("not-a-real-key", "test", client)
    answer = await ToolAgent(session(), provider).ask("Count orders", "ecommerce")
    assert answer.text == "720 orders"
    contents = generate.call_args_list[1].kwargs["contents"]
    assert contents[1].parts[0].thought_signature == b"opaque-signature"
    assert contents[2].parts[0].function_response.id == "c1"
    assert contents[2].parts[0].function_response.response["ok"]
    assert generate.call_args.kwargs["config"].automatic_function_calling.disable


async def test_selection_enforced_and_error_feedback():
    s = session()
    payload = await execute_tool(s, "run_query", {"database_id": "hr"}, "ecommerce")
    assert payload["ok"] is False
    s.call_tool.assert_not_awaited()
    s.call_tool.side_effect = RuntimeError("private-driver-secret")
    payload = await execute_tool(s, "run_query", {}, None)
    assert "private-driver-secret" not in json.dumps(payload)


async def test_gemini_quota_has_no_paid_fallback():
    class Quota(Exception):
        code = 429

    generate = AsyncMock(side_effect=Quota("private API key must not appear"))
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    with pytest.raises(ProviderError, match="no paid fallback"):
        await ToolAgent(session(), GeminiProvider("secret", "test", client)).ask("Count")
    assert generate.await_count == 1


@pytest.mark.parametrize("status,message", [(404, "model missing"), (500, "request failed")])
async def test_ollama_errors(status, message):
    http = httpx.AsyncClient(
        base_url="http://localhost",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": "do not echo this"}),
        ),
    )
    provider = OllamaProvider("http://localhost", "test", http)
    try:
        with pytest.raises(ProviderError, match=message):
            await ToolAgent(session(), provider).ask("Count")
    finally:
        await provider.close()


async def test_ungrounded_model_answer_is_not_presented_as_data():
    provider = SimpleNamespace(
        start=lambda *args: [],
        complete=AsyncMock(
            return_value=SimpleNamespace(calls=[], text="Invented answer"),
        ),
    )
    with pytest.raises(ProviderError, match="without executing SQL"):
        await ToolAgent(session(), provider).ask("Count")


async def test_turn_budget():
    provider = SimpleNamespace(
        start=lambda *args: [],
        complete=AsyncMock(
            return_value=SimpleNamespace(calls=[("run_query", {})], text=""),
        ),
        results=lambda *args: None,
    )
    with pytest.raises(ProviderError, match="limit"):
        await ToolAgent(session(), provider, max_turns=1).ask("Count")

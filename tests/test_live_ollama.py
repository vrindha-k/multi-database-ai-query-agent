import asyncio
import os

import pytest

from app.agent import mcp_session
from app.config import Settings
from app.providers import OllamaProvider, ToolAgent


@pytest.mark.live_ollama
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OLLAMA") != "1", reason="Opt-in local model download/inference"
)
async def test_live_local_model_natural_language_to_postgresql():
    settings = Settings()
    provider = OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    try:
        async with asyncio.timeout(600), mcp_session() as session:
            answer = await ToolAgent(session, provider).ask(
                "How many orders are in the orders table? Discover its schema, then use run_query "
                "to SELECT COUNT(*) AS orders FROM orders. Report that count without filtering.",
                "ecommerce",
            )
        results = [
            t["result"]["data"]
            for t in answer.trace
            if t["tool"] == "run_query" and t["result"].get("ok")
        ]
        assert any(result["rows"] == [[720]] for result in results)
        assert "720" in answer.text
    finally:
        await provider.close()

"""Free local Ollama and optional Gemini tool loops over the same restricted MCP tools."""

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from google import genai
from google.genai import types

from app.agent import SYSTEM, Answer


class ProviderError(RuntimeError):
    """Safe, actionable provider error with no credentials or response bodies."""


@dataclass
class Turn:
    text: str
    calls: list[tuple[str, dict]]


async def execute_tool(session: Any, name: str, args: dict, selected: str | None) -> dict:
    """All providers invoke real MCP tools; database selection is enforced outside the model."""
    if selected and args.get("database_id", selected) != selected:
        return {"ok": False, "error": "Selected database is enforced by client"}
    try:
        result = await session.call_tool(name, args)
        if result.isError:
            return {"ok": False, "error": "MCP rejected the tool call; revise the arguments"}
        payload = result.structuredContent
        if payload is None:
            payload = json.loads("".join(b.text for b in result.content if b.type == "text"))
        if selected and name == "list_databases" and payload.get("ok"):
            payload["data"] = [d for d in payload["data"] if d["database_id"] == selected]
        return payload
    except Exception:
        return {"ok": False, "error": "MCP call failed; revise the request"}


class OllamaProvider:
    def __init__(self, base_url: str, model: str, http: httpx.AsyncClient | None = None):
        self.model = model
        self.http = http or httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=180)

    def start(self, question: str, system: str) -> list:
        return [{"role": "system", "content": system}, {"role": "user", "content": question}]

    async def complete(self, history: list, tools: list, system: str) -> Turn:
        definitions = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema,
                },
            }
            for t in tools
        ]
        try:
            response = await self.http.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": history,
                    "tools": definitions,
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0, "num_ctx": 8192},
                },
            )
            if response.status_code == 404:
                raise ProviderError(f"Ollama model missing. Run: ollama pull {self.model}")
            response.raise_for_status()
            data = response.json()
            if data.get("error") or not data.get("done"):
                raise ProviderError("Ollama did not finish the response; retry a smaller question")
            message = data["message"]
            history.append(message)
            calls = [
                (c["function"]["name"], c["function"]["arguments"])
                for c in message.get("tool_calls", [])
            ]
            return Turn(message.get("content", ""), calls)
        except httpx.ConnectError:
            raise ProviderError(
                "Ollama is not reachable. Start Ollama and check OLLAMA_BASE_URL. "
                "For Docker use http://host.docker.internal:11434."
            ) from None
        except httpx.TimeoutException:
            raise ProviderError(
                "Local model timed out; try a smaller model or shorter question"
            ) from None
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise ProviderError(
                "Ollama request failed; check that the model supports tool calling"
            ) from None

    def results(self, history: list, outputs: list[tuple[str, dict]]) -> None:
        history.extend(
            {"role": "tool", "tool_name": name, "content": json.dumps(payload)}
            for name, payload in outputs
        )

    async def close(self) -> None:
        await self.http.aclose()


class GeminiProvider:
    def __init__(self, api_key: str, model: str, client: Any = None):
        self.model = model
        self.client = client or genai.Client(api_key=api_key)

    def start(self, question: str, system: str) -> list:
        return [types.Content(role="user", parts=[types.Part.from_text(text=question)])]

    async def complete(self, history: list, tools: list, system: str) -> Turn:
        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description or "",
                parameters_json_schema=t.inputSchema,
            )
            for t in tools
        ]
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0,
                    tools=[types.Tool(function_declarations=declarations)],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            candidate = response.candidates[0]
            if not candidate.content or candidate.finish_reason != types.FinishReason.STOP:
                raise ProviderError(
                    "Gemini response was blocked or incomplete; revise the question"
                )
            # Keep the exact SDK Content, including thought signatures, across tool round trips.
            history.append(candidate.content)
            calls = [
                (p.function_call.name, dict(p.function_call.args or {}))
                for p in candidate.content.parts
                if p.function_call
            ]
            text = "\n".join(p.text for p in candidate.content.parts if p.text and not p.thought)
            return Turn(text, calls)
        except ProviderError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == 429:
                raise ProviderError(
                    "Gemini free-tier quota reached. Wait for quota to reset or use Ollama; "
                    "no paid fallback is enabled."
                ) from None
            raise ProviderError(
                "Gemini request failed. Check GEMINI_API_KEY, model access and free-tier quota."
            ) from None

    def results(self, history: list, outputs: list[tuple[str, dict]]) -> None:
        # Match IDs when the model supplies them; names alone support older Gemini models.
        calls = [p.function_call for p in history[-1].parts if p.function_call]
        parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    name=name,
                    response=payload,
                    id=call.id,
                )
            )
            for call, (name, payload) in zip(calls, outputs, strict=True)
        ]
        history.append(types.Content(role="user", parts=parts))

    async def close(self) -> None:
        await self.client.aio.aclose()


class ToolAgent:
    def __init__(self, session: Any, provider: Any, max_turns: int = 12):
        self.session, self.provider, self.max_turns = session, provider, max_turns

    async def ask(self, question: str, database_id: str | None = None) -> Answer:
        tools = (await self.session.list_tools()).tools
        system = SYSTEM + f"\nToday: {date.today()}. Database: {database_id or 'auto'}"
        history = self.provider.start(question, system)
        trace: list[dict] = []
        for _ in range(self.max_turns):
            turn = await self.provider.complete(history, tools, system)
            if not turn.calls:
                if not any(t["tool"] == "run_query" and t["result"].get("ok") for t in trace):
                    raise ProviderError(
                        "Model answered without executing SQL. Try /use DATABASE and a "
                        "more specific question, or use /sql."
                    )
                return Answer(turn.text, trace)
            outputs = []
            if len(turn.calls) > 10:
                raise ProviderError("Model requested too many tools in one turn")
            for name, args in turn.calls:
                payload = await execute_tool(self.session, name, args, database_id)
                trace.append({"tool": name, "input": args, "result": payload})
                outputs.append((name, payload))
            self.provider.results(history, outputs)
        raise ProviderError("Tool-call limit reached; ask a narrower question")

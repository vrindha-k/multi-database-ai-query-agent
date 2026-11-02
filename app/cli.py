"""Interactive Rich CLI; /sql and /explain provide deterministic MCP diagnostics."""

import asyncio
import json

from anthropic import AsyncAnthropic
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from app.agent import Agent, mcp_session
from app.config import get_settings

console = Console(markup=False)


def display(payload: dict) -> None:
    if not payload.get("ok"):
        console.print(payload.get("error", "Tool failed"), style="red")
        return
    data = payload["data"]
    if isinstance(data, dict) and "columns" in data:
        console.print(f"Database: {data['database_id']}")
        console.print(Syntax(data["sql"], "sql", word_wrap=True))
        table = Table(*data["columns"])
        for row in data["rows"]:
            table.add_row(*(str(v) for v in row))
        console.print(table)
        console.print(f"Rows: {data['row_count']}; truncated: {data['truncated']}")
    else:
        console.print_json(json.dumps(data, default=str))


async def main() -> None:
    settings = get_settings()
    async with mcp_session() as session:

        async def call(name, args):
            result = await session.call_tool(name, args)
            return result.structuredContent or json.loads(result.content[0].text)

        console.print("Multi-Database AI Query Agent", style="bold cyan")
        discovery = await call("list_databases", {})
        display(discovery)
        selected = None
        client = (
            AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
            if settings.anthropic_api_key
            else None
        )
        agent = Agent(session, client, settings.anthropic_model, settings.max_agent_turns)
        console.print("/help for commands. Natural-language questions require ANTHROPIC_API_KEY.")
        try:
            while True:
                question = console.input(f"\n{selected or 'auto'}> ").strip()
                if question.lower() in {"exit", "quit", "/exit"}:
                    break
                if not question:
                    continue
                try:
                    if question == "/help":
                        console.print(
                            "/databases | /use ID | /use auto | /tables | "
                            "/sql SELECT ... | /explain SELECT ... | /exit"
                        )
                    elif question == "/databases":
                        display(await call("list_databases", {}))
                    elif question.startswith("/use "):
                        key = question[5:].strip()
                        available = await call("list_databases", {})
                        ids = {d["database_id"] for d in available.get("data", [])}
                        if key != "auto" and key not in ids:
                            raise ValueError("Unknown database identifier")
                        selected = None if key == "auto" else key
                    elif question == "/tables" or question.startswith(("/sql ", "/explain ")):
                        if not selected:
                            raise ValueError("Select a database with /use ID first")
                        name = (
                            "list_tables"
                            if question == "/tables"
                            else "explain_query"
                            if question.startswith("/explain ")
                            else "run_query"
                        )
                        args = {"database_id": selected}
                        if name != "list_tables":
                            args["sql"] = question.split(" ", 1)[1]
                        display(await call(name, args))
                    elif question.startswith("/"):
                        console.print("Unknown command; use /help")
                    elif not client:
                        console.print(
                            "Set ANTHROPIC_API_KEY in .env; /sql diagnostics work without it."
                        )
                    else:
                        answer = await agent.ask(question, selected)
                        for entry in answer.trace:
                            if entry["tool"] in {"run_query", "explain_query"}:
                                display(entry["result"])
                        console.print("AI Answer:\n" + answer.text)
                except Exception:
                    console.print(
                        "Request failed. Check configuration, connectivity or narrow the "
                        "question; tool diagnostics: /sql and /explain.",
                        style="red",
                    )
        finally:
            if client:
                await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        pass

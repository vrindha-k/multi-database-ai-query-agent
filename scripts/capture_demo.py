"""Render actual MCP diagnostic output as text and SVG; no simulated AI answers."""

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from app.agent import mcp_session


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    console = Console(record=True, width=100)
    console.print("Multi-Database AI Query Agent", style="bold cyan")
    console.print("Actual MCP stdio + PostgreSQL diagnostic capture (no Claude API)")
    async with mcp_session() as session:
        discovery = await session.call_tool("list_databases", {})
        for database in discovery.structuredContent["data"]:
            console.print(
                f"{database['database_id']}: available={database['available']}; "
                f"schemas={','.join(database['schemas'])}"
            )
        examples = json.loads((root / "examples/verified.json").read_text())
        for index in (2, 8):
            example = examples[index]
            console.print(f"\n{example['database_id']}> {example['question']}", style="bold")
            response = await session.call_tool(
                "run_query",
                {
                    "database_id": example["database_id"],
                    "sql": example["sql"],
                },
            )
            data = response.structuredContent["data"]
            table = Table(*data["columns"])
            for row in data["rows"]:
                table.add_row(*(str(value) for value in row))
            console.print(table)
            console.print(f"Rows: {data['row_count']}; truncated={data['truncated']}")
        rejection = await session.call_tool(
            "run_query",
            {
                "database_id": "ecommerce",
                "sql": "DELETE FROM customers",
            },
        )
        console.print("\nUnsafe SQL test: DELETE FROM customers", style="bold")
        console.print(rejection.structuredContent["error"], style="yellow")
    console.save_text(str(root / "docs/terminal-demo.txt"), clear=False)
    console.save_svg(str(root / "docs/terminal-demo.svg"), title="MCP / PostgreSQL demo")


if __name__ == "__main__":
    asyncio.run(main())

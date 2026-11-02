"""Real stdio MCP server. stdout is reserved for JSON-RPC."""

import logging
from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.database import DatabaseUnavailable, Registry
from app.security import QueryRejected

mcp = FastMCP("Multi-Database AI Query Agent")


@lru_cache
def registry() -> Registry:
    return Registry(get_settings())


def invoke(name: str, **kwargs):
    try:
        return {"ok": True, "data": getattr(registry(), name)(**kwargs)}
    except (QueryRejected, DatabaseUnavailable) as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:
        logging.getLogger(__name__).warning("Tool failed: %s", name)
        return {"ok": False, "error": "Tool configuration or execution failed"}


@mcp.tool()
def list_databases() -> dict[str, Any]:
    """List configured database identifiers, descriptions and availability; no credentials."""
    return invoke("list_databases")


@mcp.tool()
def list_tables(database_id: str, schema_name: str | None = None) -> dict[str, Any]:
    """Discover authorized base tables, comments and approximate row counts."""
    return invoke("list_tables", database_id=database_id, schema_name=schema_name)


@mcp.tool()
def get_schema(database_id: str, table_names: list[str]) -> dict[str, Any]:
    """Inspect columns, keys, foreign-key relationships and indexes of discovered tables."""
    return invoke("get_schema", database_id=database_id, table_names=table_names)


@mcp.tool()
def run_query(database_id: str, sql: str, max_rows: int | None = None) -> dict[str, Any]:
    """Execute one validated read-only SELECT/CTE, returning bounded structured results."""
    return invoke("run_query", database_id=database_id, sql=sql, max_rows=max_rows)


@mcp.tool()
def explain_query(database_id: str, sql: str) -> dict[str, Any]:
    """Describe SQL structure and PostgreSQL EXPLAIN estimates, without ANALYZE."""
    return invoke("explain_query", database_id=database_id, sql=sql)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    mcp.run(transport="stdio")

import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.agent import mcp_session
from app.database import DatabaseUnavailable, Registry
from app.security import QueryRejected

pytestmark = pytest.mark.integration


def test_discovery_and_relationships(registry):
    databases = registry.list_databases()
    assert {d["database_id"] for d in databases} == {"ecommerce", "hr"}
    assert all(d["available"] for d in databases)
    tables = registry.list_tables("ecommerce")
    assert len(tables) == 6
    schema = registry.get_schema("ecommerce", ["public.orders"])[0]
    assert schema["foreign_keys"][0]["referred_table"] == "customers"
    assert schema["primary_key"]["constrained_columns"] == ["id"]
    assert schema["indexes"]
    with pytest.raises(QueryRejected):
        registry.list_tables("hr", "pg_catalog")


def test_verified_examples(registry):
    path = Path(__file__).parents[1] / "examples/verified.json"
    for example in json.loads(path.read_text()):
        result = registry.run_query(example["database_id"], example["sql"])
        assert {"columns": result["columns"], "rows": result["rows"]} == example["expected"]


def test_limits_and_explain(registry):
    result = registry.run_query("hr", "SELECT id FROM employees ORDER BY id", 3)
    assert result["rows"] == [[1], [2], [3]]
    assert result["truncated"] is True
    with pytest.raises(QueryRejected):
        registry.run_query("hr", "SELECT 1", 1001)
    plan = registry.explain_query("hr", "SELECT id FROM employees WHERE id=1")
    assert plan["plan"][0]["Plan"]


def test_database_acl_and_readonly(registry):
    for key, engine in registry.engines.items():
        with engine.connect() as conn:
            assert conn.scalar(text("SHOW default_transaction_read_only")) == "on"
            assert not conn.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"))
            assert not conn.scalar(text("SELECT has_schema_privilege('public','CREATE')"))
            assert not conn.scalar(text("SELECT has_database_privilege(current_database(),'TEMP')"))
        table = "customers" if key == "ecommerce" else "employees"
        with engine.connect() as conn, pytest.raises(DBAPIError):
            conn.exec_driver_sql(f"DELETE FROM public.{table}")
        # ACLs still deny writes if transaction read-only is disabled by a direct DB client.
        with engine.connect() as conn, pytest.raises(DBAPIError):
            conn.exec_driver_sql("SET TRANSACTION READ WRITE")
            conn.exec_driver_sql(f"DELETE FROM public.{table}")
        with registry.connection(key) as conn:
            assert conn.scalar(text("SHOW transaction_read_only")) == "on"


def test_statement_timeout(registry):
    settings = registry.settings.model_copy(update={"statement_timeout_ms": 10})
    bounded = Registry(settings)
    try:
        with pytest.raises(DatabaseUnavailable, match="timeout") as error:
            bounded.run_query(
                "hr",
                "SELECT count(*) FROM employees a CROSS JOIN employees b "
                "CROSS JOIN employees c CROSS JOIN employees d CROSS JOIN employees e",
            )
        assert error.value.sqlstate == "57014"
    finally:
        bounded.close()


def test_schema_agnostic_nested_cte(registry):
    # Metadata supplies names; this test has no dependency on any sample table/column name.
    for key in registry.engines:
        table = registry.list_tables(key)[0]
        qualified = table["schema_name"] + "." + table["table_name"]
        metadata = registry.get_schema(key, [qualified])[0]
        column = metadata["columns"][0]["name"]
        result = registry.run_query(
            key,
            f'WITH discovered AS (SELECT "{column}" FROM '
            f"{qualified}) SELECT count(*) FROM discovered",
        )
        assert result["rows"][0][0] > 0


async def test_mcp_database_roundtrip(registry):
    async with mcp_session() as session:
        for key in registry.engines:
            result = await session.call_tool("list_tables", {"database_id": key})
            assert len(result.structuredContent["data"]) == 6
            result = await session.call_tool("run_query", {"database_id": key, "sql": "SELECT 42"})
            assert result.structuredContent["data"]["rows"] == [[42]]

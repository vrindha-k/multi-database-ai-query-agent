"""Synchronous SQLAlchemy operations run by FastMCP in its worker thread pool."""

import json
import logging
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.security import QueryRejected, describe_query, validate_sql

logger = logging.getLogger(__name__)


class DatabaseUnavailable(RuntimeError):
    pass


class Registry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.configs = {c.id: c for c in settings.databases()}
        self.engines: dict[str, Engine] = {
            c.id: create_engine(
                c.url.get_secret_value(),
                pool_size=2,
                max_overflow=0,
                pool_timeout=5,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 5},
                hide_parameters=True,
            )
            for c in self.configs.values()
        }

    @contextmanager
    def connection(self, database_id: str):
        if database_id not in self.engines:
            raise QueryRejected("Unknown database identifier")
        try:
            with self.engines[database_id].connect() as conn, conn.begin():
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                unsafe = conn.scalar(
                    text("""
                    SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls
                    FROM pg_catalog.pg_roles WHERE rolname=current_user
                """)
                )
                if unsafe:
                    raise QueryRejected("Configure a dedicated, unprivileged SELECT-only role")
                conn.execute(
                    text("SELECT set_config('statement_timeout', :v, true)"),
                    {"v": str(self.settings.statement_timeout_ms)},
                )
                conn.exec_driver_sql("SET LOCAL lock_timeout = '500ms'")
                conn.exec_driver_sql("SET LOCAL idle_in_transaction_session_timeout = '10s'")
                conn.exec_driver_sql("SET LOCAL work_mem = '4MB'")
                conn.exec_driver_sql("SET LOCAL max_parallel_workers_per_gather = 0")
                conn.exec_driver_sql("SET LOCAL search_path = pg_catalog")
                writable = conn.scalar(
                    text("""
                    SELECT has_database_privilege(current_database(), 'CREATE,TEMP')
                    OR EXISTS (
                        SELECT 1 FROM pg_catalog.pg_namespace n
                        WHERE n.nspname=ANY(:schemas)
                        AND has_schema_privilege(n.oid, 'CREATE')
                    ) OR EXISTS (
                        SELECT 1 FROM pg_catalog.pg_class c
                        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                        WHERE n.nspname=ANY(:schemas) AND c.relkind IN ('r','p')
                        AND has_table_privilege(c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE')
                    )
                """),
                    {"schemas": self.configs[database_id].schemas},
                )
                if writable:
                    raise QueryRejected(
                        "Database role must have SELECT-only application privileges"
                    )
                yield conn
        except SQLAlchemyError:
            # Never include driver exception text: it can contain SQL, literals and DSNs.
            logger.warning("Database operation failed", extra={"database_id": database_id})
            raise DatabaseUnavailable(
                "Database operation failed (connection, permissions, syntax or timeout); "
                "check configuration or revise the query."
            ) from None

    def tables(self, conn: Connection, database_id: str, schema_name: str | None = None) -> list:
        schemas = self.configs[database_id].schemas
        if schema_name is not None and schema_name not in schemas:
            raise QueryRejected("Schema is not authorized")
        rows = conn.execute(
            text("""
            SELECT n.nspname AS schema_name, c.relname AS table_name,
                   obj_description(c.oid) AS description,
                   greatest(c.reltuples, 0)::bigint AS approximate_rows
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname = ANY(:schemas) AND c.relkind IN ('r','p')
              AND has_table_privilege(c.oid, 'SELECT')
            ORDER BY n.nspname, c.relname
        """),
            {"schemas": [schema_name] if schema_name else schemas},
        ).mappings()
        return [dict(row) for row in rows]

    def list_databases(self) -> list:
        result = []
        for key, config in self.configs.items():
            try:
                with self.connection(key) as conn:
                    schemas = sorted({t["schema_name"] for t in self.tables(conn, key)})
                available = True
            except DatabaseUnavailable:
                available, schemas = False, []
            result.append(
                {
                    "database_id": key,
                    "description": config.description,
                    "available": available,
                    "schemas": schemas,
                }
            )
        return result

    def list_tables(self, database_id: str, schema_name: str | None = None) -> list:
        with self.connection(database_id) as conn:
            return self.tables(conn, database_id, schema_name)

    def get_schema(self, database_id: str, table_names: list[str]) -> list:
        if not 1 <= len(table_names) <= 30:
            raise QueryRejected("Request between 1 and 30 tables")
        with self.connection(database_id) as conn:
            allowed = self.tables(conn, database_id)
            inspector = inspect(conn)
            result = []
            for requested in table_names:
                matches = [
                    t
                    for t in allowed
                    if requested in (t["table_name"], f"{t['schema_name']}.{t['table_name']}")
                ]
                if len(matches) != 1:
                    raise QueryRejected("Unknown or ambiguous authorized table")
                schema, table = matches[0]["schema_name"], matches[0]["table_name"]
                columns = [
                    {"name": c["name"], "type": str(c["type"]), "nullable": c["nullable"]}
                    for c in inspector.get_columns(table, schema)
                ]
                result.append(
                    {
                        "schema": schema,
                        "table": table,
                        "columns": columns,
                        "primary_key": inspector.get_pk_constraint(table, schema),
                        "foreign_keys": inspector.get_foreign_keys(table, schema),
                        "indexes": inspector.get_indexes(table, schema),
                    }
                )
            return result

    def validated(self, conn: Connection, database_id: str, sql: str):
        allowed = {(t["schema_name"], t["table_name"]) for t in self.tables(conn, database_id)}
        return validate_sql(sql, allowed)

    def run_query(self, database_id: str, sql: str, max_rows: int | None = None) -> dict:
        limit = self.settings.max_rows if max_rows is None else max_rows
        if isinstance(limit, bool) or not 1 <= limit <= self.settings.max_rows:
            raise QueryRejected(f"max_rows must be between 1 and {self.settings.max_rows}")
        with self.connection(database_id) as conn:
            query = self.validated(conn, database_id, sql)
            normalized = query.tree.sql(dialect="postgres")
            # Outer LIMIT caps transfer even when the original SQL lacks a LIMIT.
            result = conn.exec_driver_sql(
                f'SELECT * FROM ({normalized}) AS "_bounded_result" LIMIT {limit + 1}'
            )
            columns = list(result.keys())
            if len(columns) > 128:
                raise QueryRejected("Select at most 128 explicit columns")
            rows = result.fetchmany(limit + 1)
            data = []
            response_bytes = 0
            for row in rows[:limit]:
                safe_row = [self.safe_cell(value) for value in row]
                response_bytes += len(json.dumps(safe_row, default=str).encode("utf-8"))
                if response_bytes > 256000:
                    break
                data.append(safe_row)
            return {
                "database_id": database_id,
                "sql": normalized,
                "columns": columns,
                "rows": data,
                "row_count": len(data),
                "truncated": len(rows) > len(data),
                "row_limit": limit,
            }

    def safe_cell(self, value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        string = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
        return string[: self.settings.max_cell_chars]

    def explain_query(self, database_id: str, sql: str) -> dict:
        with self.connection(database_id) as conn:
            query = self.validated(conn, database_id, sql)
            explanation = describe_query(query)
            explanation["plan"] = conn.exec_driver_sql(
                "EXPLAIN (FORMAT JSON) " + query.tree.sql(dialect="postgres")
            ).scalar_one()
            return explanation

    def close(self) -> None:
        for engine in self.engines.values():
            engine.dispose()

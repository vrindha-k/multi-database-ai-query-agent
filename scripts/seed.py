"""Initialize fresh demo databases for native development/CI (never run on real data).

ADMIN_URL is an administrative connection to the postgres maintenance database.
The two target database names must not already exist. Credentials stay in environment/.env.
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql


def main() -> None:
    load_dotenv()
    admin_url = os.environ["ADMIN_URL"]
    root = Path(__file__).resolve().parents[1]
    with psycopg.connect(admin_url, autocommit=True) as admin:
        for database in ("ecommerce", "hr"):
            reader = database + "_reader"
            password = os.environ[database.upper() + "_READER_PASSWORD"]
            admin.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION"
                ).format(sql.Identifier(reader), sql.Literal(password))
            )
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            admin.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database))
            )
            admin.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database), sql.Identifier(reader)
                )
            )
            for setting, value in [
                ("default_transaction_read_only", "on"),
                ("statement_timeout", "3s"),
                ("temp_file_limit", "32MB"),
                ("search_path", "pg_catalog"),
            ]:
                admin.execute(
                    sql.SQL("ALTER ROLE {} SET {} = {}").format(
                        sql.Identifier(reader), sql.Identifier(setting), sql.Literal(value)
                    )
                )
            params = psycopg.conninfo.conninfo_to_dict(admin_url)
            params["dbname"] = database
            with psycopg.connect(**params, autocommit=True) as conn:
                conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
                conn.execute((root / "db" / f"{database}.sql").read_text())
                conn.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(reader))
                )
                conn.execute(
                    sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
                        sql.Identifier(reader)
                    )
                )
            print(f"Initialized synthetic {database} database")


if __name__ == "__main__":
    main()

import pytest

from app.database import Registry
from app.security import QueryRejected


@pytest.mark.integration
@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "DROP TABLE customers",
        "UPDATE customers SET name='x'",
        "INSERT INTO customers(id) VALUES(1000)",
        "SELECT 1; SELECT 2",
        "SELECT * FROM pg_catalog.pg_authid",
        "SELECT pg_sleep(5)",
        "WITH x AS (DELETE FROM customers RETURNING *) SELECT * FROM x",
    ],
)
def test_execution_layer_rejects(registry, sql):
    with pytest.raises(QueryRejected):
        registry.run_query("ecommerce", sql)


@pytest.mark.integration
def test_response_budgets(registry):
    # Constants exercise cell and aggregate response budgets without adding repeat() to policy.
    value = "x" * 5000
    result = registry.run_query("hr", f"SELECT '{value}' AS value FROM employees")
    assert result["truncated"] is True
    assert len(result["rows"][0][0]) == 4000


@pytest.mark.integration
def test_credentials_failure_is_sanitized(registry):
    from sqlalchemy.engine import make_url

    from app.config import Settings
    from app.database import DatabaseUnavailable

    config = registry.configs["hr"].model_dump()
    url = make_url(registry.configs["hr"].url.get_secret_value())
    marker = "DELIBERATELY_INVALID_SECRET"
    config["url"] = url.set(password=marker).render_as_string(hide_password=False)
    import json

    invalid = Registry(Settings(databases_json=json.dumps([config])))
    try:
        with pytest.raises(DatabaseUnavailable) as error:
            invalid.run_query("hr", "SELECT 1")
        assert marker not in str(error.value)
        assert "postgresql" not in str(error.value)
    finally:
        invalid.close()


@pytest.mark.integration
def test_privileged_credentials_rejected(registry):
    # Use only when the local/CI administrator URL is deliberately supplied.
    import os

    from app.config import Settings

    url = os.getenv("ADMIN_URL")
    if not url:
        pytest.skip("ADMIN_URL deliberately absent from application runtime")
    import json

    settings = Settings(
        databases_json=json.dumps(
            [
                {
                    "id": "admin",
                    "description": "must reject",
                    "url": url.replace("postgresql://", "postgresql+psycopg://"),
                    "schemas": ["public"],
                },
            ]
        )
    )
    admin = Registry(settings)
    try:
        with pytest.raises(QueryRejected, match="unprivileged"):
            admin.run_query("admin", "SELECT 1")
    finally:
        admin.close()

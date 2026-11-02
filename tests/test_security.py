import pytest

from app.security import QueryRejected, describe_query, validate_sql

ALLOWED = {("public", "orders"), ("public", "order_items")}


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "DROP TABLE orders",
        "UPDATE orders SET id=1",
        "INSERT INTO orders VALUES (1)",
        "TRUNCATE orders",
        "CREATE TABLE x(a int)",
        "COPY orders TO '/tmp/x'",
        "CALL evil()",
        "SELECT 1; SELECT 2",
        "SELECT * FROM private.orders",
        "SELECT * FROM pg_catalog.pg_authid",
        "SELECT pg_sleep(1)",
        "SELECT set_config('search_path','private',false)",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT public.evil()",
        "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x",
        "SELECT * INTO stolen FROM orders",
        "SELECT * FROM orders FOR UPDATE",
        "WITH RECURSIVE x AS (SELECT 1 UNION ALL SELECT 1 FROM x) SELECT * FROM x",
        "SELECT * FROM other.public.orders",
        "SELECT * FROM dblink('x','x')",
        "SELECT * FROM unconfigured",
        "SELECT unknown_udf(id) FROM orders",
    ],
)
def test_reject(sql):
    with pytest.raises(QueryRejected):
        validate_sql(sql, ALLOWED)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id FROM orders",
        "SELECT count(*) FROM public.orders",
        "WITH x AS (SELECT id FROM orders) SELECT id FROM x",
        "SELECT o.id, sum(i.quantity) FROM orders o LEFT JOIN order_items i "
        "ON o.id=i.order_id GROUP BY o.id HAVING sum(i.quantity)>1",
        "SELECT id, row_number() OVER(ORDER BY id), lag(id) OVER(ORDER BY id) FROM orders",
        "SELECT id FROM orders WHERE id IN (SELECT order_id FROM order_items)",
        "SELECT current_date, date_trunc('month',current_timestamp)",
        "SELECT id FROM orders UNION ALL SELECT order_id FROM order_items",
    ],
)
def test_allow(sql):
    query = validate_sql(sql, ALLOWED)
    assert query.tree.sql(dialect="postgres")


def test_cte_cannot_hide_unauthorized_relation():
    with pytest.raises(QueryRejected):
        validate_sql("WITH orders AS (SELECT * FROM private.secret) SELECT * FROM orders", ALLOWED)


def test_ambiguity():
    with pytest.raises(QueryRejected):
        validate_sql("SELECT * FROM orders", ALLOWED | {("sales", "orders")})


def test_explanation():
    query = validate_sql("SELECT id, rank() OVER(ORDER BY id) FROM orders WHERE id>1", ALLOWED)
    explanation = describe_query(query)
    assert explanation["tables"] == ["public.orders"]
    assert explanation["filters"] and explanation["window_functions"]

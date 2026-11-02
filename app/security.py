"""Conservative PostgreSQL AST policy. Database ACLs remain the final boundary."""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlglot.optimizer.scope import traverse_scope


class QueryRejected(ValueError):
    """The supplied SQL is outside the supported read-only analytics subset."""


# Deliberately small: unknown functions fail closed (including extension/UDF calls).
SAFE_FUNCTIONS = frozenset(
    """
and or case if abs avg ceil ceiling coalesce concat concat_ws count date date_part
date_trunc dense_rank
timestamp_trunc extract floor greatest lag lead least length lower ltrim max min nullif
percentile_cont
percentile_disc rank round row_number rtrim stddev stddev_pop stddev_samp substring sum
to_char trim upper variance var_pop var_samp current_date current_timestamp now cast
generate_series first_value last_value nth_value ntile cume_dist percent_rank
""".split()
)


@dataclass(frozen=True)
class ValidatedQuery:
    tree: exp.Expression
    tables: tuple[tuple[str, str], ...]


def validate_sql(sql: str, allowed: set[tuple[str, str]]) -> ValidatedQuery:
    if not sql.strip() or len(sql) > 50000:
        raise QueryRejected("Provide one SQL query of at most 50,000 characters")
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except ParseError:
        raise QueryRejected("SQL could not be parsed as PostgreSQL") from None
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise QueryRejected("Only one SELECT or read-only WITH query is allowed")
    tree = statements[0]
    forbidden = (exp.DML, exp.DDL, exp.Command, exp.Into, exp.Lock)
    if any(isinstance(node, forbidden) for node in tree.walk()):
        raise QueryRejected("Modifying statements, SELECT INTO and locks are forbidden")
    if any(
        isinstance(node, exp.CTE) and not isinstance(node.this, exp.Query) for node in tree.walk()
    ):
        raise QueryRejected("Every CTE must be a read-only query")
    if any(isinstance(node, exp.With) and node.args.get("recursive") for node in tree.walk()):
        raise QueryRejected("Recursive CTEs are outside the resource policy")
    for func in tree.find_all(exp.Func):
        name = func.name if isinstance(func, exp.Anonymous) else func.sql_name()
        if name.lower() not in SAFE_FUNCTIONS:
            raise QueryRejected("Function is not in the approved analytics allowlist")
        if isinstance(func.parent, exp.Dot):
            raise QueryRejected("Schema-qualified function calls are forbidden")
    # Scope resolution distinguishes physical relations from CTE/subquery aliases.
    physical: set[tuple[str, str]] = set()
    for scope in traverse_scope(tree):
        for source in scope.sources.values():
            if not isinstance(source, exp.Table):
                continue
            if not isinstance(source.this, exp.Identifier) or source.catalog:
                raise QueryRejected("Only local, explicitly authorized tables are supported")
            if source.db:
                key = (source.db, source.name)
                if key not in allowed:
                    raise QueryRejected("Relation is outside configured database permissions")
            else:
                matches = [key for key in allowed if key[1] == source.name]
                if len(matches) != 1:
                    raise QueryRejected("Use an authorized, unambiguous schema-qualified table")
                key = matches[0]
                # Resolve explicitly instead of trusting the connection search_path.
                source.set("db", exp.to_identifier(key[0], quoted=True))
            physical.add(key)
    return ValidatedQuery(tree, tuple(sorted(physical)))


def describe_query(query: ValidatedQuery) -> dict:
    tree = query.tree
    render = lambda node: node.sql(dialect="postgres")  # noqa: E731
    return {
        "tables": [f"{s}.{t}" for s, t in query.tables],
        "joins": [render(j) for j in tree.find_all(exp.Join)],
        "filters": [render(w) for w in tree.find_all(exp.Where, exp.Having)],
        "aggregations": [render(a) for a in tree.find_all(exp.AggFunc)],
        "window_functions": [render(w) for w in tree.find_all(exp.Window)],
        "explanation": "Read-only PostgreSQL query. Joins combine matching rows; WHERE filters "
        "before aggregation, HAVING filters groups, and window expressions retain individual rows. "
        "The returned AST details describe this query; plan costs are estimates, not timings.",
    }

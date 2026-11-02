# Component walkthrough and interview preparation

## The problem and the boundary

The project turns natural-language analytics questions into PostgreSQL results without assuming
a fixed business schema. An LLM is useful for choosing tables and constructing joins, but is not
trusted to authorize SQL. The application exposes a narrow, inspectable MCP interface and uses
both parser policy and database permissions to bound execution.

“Multi-database” means independently configured databases, each with its own engine and reader.
It does not mean a federated SQL engine. Queries cannot join tables from different databases.
Claude may ask separate tools and summarize separate results.

## Request lifecycle

1. The Rich CLI reads a question and optional selected database.
2. `mcp_session()` starts the real FastMCP server process and initializes MCP over stdio.
3. `Agent.ask()` obtains tool definitions from `list_tools` and passes their JSON schemas to
   the official Anthropic Messages API.
4. Claude can call `list_databases`, `list_tables` and `get_schema` to discover names, types,
   primary/foreign keys and indexes. No example table name is embedded in the application logic.
5. The agent executes returned tool calls using `ClientSession.call_tool`. Every tool-use ID gets
   a matching tool-result block in the next user message; multiple calls are batched into that
   message. Execution is sequential to bound concurrency and preserve predictable ordering.
6. `run_query` resolves physical tables with SQL scopes, validates the PostgreSQL AST and executes
   the normalized query in a read-only transaction as a reader.
7. Structured columns/rows and truncation information return through MCP. The agent supplies
   those results to Claude for a natural-language answer. Tool errors are also returned, allowing
   SQL revision. A finite turn budget prevents indefinite tool loops.
8. The CLI prints executed SQL and actual results from the trace, then the AI answer. The user
   can run the same SQL through `/sql` or inspect it with `/explain`.

The model is instructed to inspect schemas first. The server does not keep per-conversation
state proving discovery occurred; a schema-first prompt is not a security control. Schema
agnosticism is demonstrated by metadata-based integration tests over both unrelated schemas.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| `config.py` | Pydantic validation, secret wrappers, env/file database configuration |
| `database.py` | SQLAlchemy engines, pool/transaction controls, metadata, results, plans |
| `security.py` | SQLGlot parsing, read-only syntax policy, table scopes and explanations |
| `server.py` | Five registered FastMCP tools, sanitized tool errors, stdio entry point |
| `agent.py` | MCP client and Anthropic tool-result orchestration |
| `cli.py` | Interactive Rich UI, database selection and key-free diagnostics |
| `db/*.sql` | Deterministic synthetic schemas, relationships, data, comments and indexes |
| `db/init.sh` | Docker role creation and least-privilege grants |
| `scripts/seed.py` | Equivalent fresh-database initialization for native/CI PostgreSQL |
| `tests/` | Unit, security, orchestration, transport, query and database ACL checks |

## Why schema discovery matters

Table names alone do not reveal correct joins. `get_schema` returns foreign-key column mappings,
nullability and primary keys so Claude can distinguish one-to-many relationships. An orders to
items join multiplies order rows; calculating average order value requires an order-level CTE
before averaging. Salary history similarly needs latest-row selection, not a simple average of
all historical salaries. Examples demonstrate these semantic traps explicitly.

The metadata layer uses PostgreSQL catalogs for base tables and SQLAlchemy inspection for
columns/keys/indexes. Approximate counts come from `pg_class.reltuples`, avoiding expensive
`COUNT(*)` during discovery. They can be stale and are labeled approximate. A table is visible
only if its schema is configured and the current user has SELECT. Views are omitted because
their underlying relations and definer semantics require a separate authorization policy.

## Read-only is several independent controls

The parser rejects modification statements even inside CTEs. Scope traversal distinguishes a
CTE alias from a real table, so aliases are not accidentally treated as unauthorized tables.
Unqualified physical names are resolved uniquely and schema-qualified. Unknown schemas,
ambiguous names, multiple statements, locks, SELECT INTO and unapproved functions fail closed.

A function can mutate state even inside SELECT. This is why “starts with SELECT” or a regex is
insufficient. A conservative function allowlist blocks filesystem/network/administrative
functions and UDFs. The connection's search path is `pg_catalog`, preventing ordinary public
schema functions from shadowing built-ins. The small allowlist intentionally limits SQL breadth.

The database reader has no superuser, database creation, role creation, replication, schema
creation or database TEMP privileges. It has SELECT on demo tables and schema USAGE. Role
defaults and explicit transaction settings enforce read-only. Tests also disable transaction
read-only in a direct connection and confirm DELETE is still blocked by ACLs.

An SQL validator cannot replace DBA-managed privilege review, resource governance or independent
security testing. Additional databases must use equivalent roles and avoid dangerous extensions,
untrusted casts and privileged role memberships. This is a local portfolio gateway, not a
certified arbitrary-SQL sandbox.

## Performance and correctness

- Connections are pooled, with two connections per database and no overflow.
- Statement/connect/lock/idle timeouts bound common failure modes; `work_mem` and temp limits
  reduce resource pressure. Parallel workers are disabled for queries.
- An outer LIMIT requests at most one extra row to detect truncation. User SQL may retain its
  own LIMIT. Output additionally has column, string and aggregate payload caps.
- LIMIT cannot make every aggregation cheap: PostgreSQL may need to scan or sort the full input.
  EXPLAIN is available without ANALYZE, and its costs are estimates rather than elapsed timings.
- Example indexes target customer/date, ordered date, item/product, employee/department and
  attendance date. Tiny demo tables often favor sequential scans; that is not inherently a bug.
- Decimal and date serialization preserve values without binary-float rounding. Duplicate output
  column names are represented safely by separate column names and row arrays.
- Query errors are sanitized before crossing MCP or being logged. This sacrifices detailed user
  diagnostics to avoid inadvertently exposing SQL literals or connection credentials.

## Testing strategy

Unit tests cover rejected SQL forms, permitted analytical forms, CTE shadowing, ambiguous
tables, settings and secret redaction. The real stdio test starts a subprocess and discovers
tools without a database or API key. Mocked Anthropic SDK blocks test batched responses,
database selection, error recovery and turn budgets.

PostgreSQL integration tests discover both schemas, inspect foreign keys and indexes, execute
14 fixed reference queries, compare every row to stored results, test real timeout behavior and
verify privileges. A further agent test mocks only the paid Claude API while using real MCP and
PostgreSQL for the schema-to-query pipeline. This does not establish live model quality; a live
key is required for that. See VERIFICATION.md for executed evidence and unresolved environment
checks. CI is configured to run these tests and a Docker Compose test on GitHub.

## A concise interview explanation

“I built a local MCP server exposing schema-discovery and read-only query tools for multiple
PostgreSQL databases. The official Claude SDK runs a bounded tool-use loop through a real MCP
stdio client. PostgreSQL catalog metadata supplies table structure and foreign keys, so the
application does not hardcode business tables. SQLGlot validates a conservative SQL subset,
and separate database reader roles and read-only transactions enforce the execution boundary.
I tested multi-table aggregation, CTEs, window functions, timeouts, MCP transport and database
permissions using deterministic synthetic e-commerce and HR data.”

Only describe live Claude/Docker/GitHub runs as successful after completing the relevant checks.
The project demonstrates optimization techniques; it does not guarantee optimal generated SQL.

## Questions to prepare for

- **Why MCP instead of direct functions?** It separates model client and database tools using a
  standard discoverable interface. The subprocess test proves JSON-RPC transport actually works.
- **Why not a large agent framework?** The SDK loop is small, visible and easy to test; the server
  owns authorization independently of model behavior.
- **Why not read-only transactions alone?** SELECT can still consume resources or invoke dangerous
  functions. ACLs, syntax/function policy and timeouts address different risks.
- **How do you avoid double counting?** Understand cardinality, aggregate to the right grain,
  and verify against deterministic expected values.
- **How do windows differ from GROUP BY?** GROUP BY collapses groups; windows retain rows while
  computing ranks, offsets or running aggregates over partitions.
- **What remains for production?** Per-user authorization, authenticated remote transport,
  independent review, global concurrency/rate limits, query cost budgets, redacted auditing,
  stronger prompt-injection evaluations and workload-specific performance testing.

## Primary implementation references

- [Official MCP Python SDK v1 / FastMCP](https://py.sdk.modelcontextprotocol.io/v1/)
- [Anthropic tool-call lifecycle](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- [PostgreSQL transaction read-only behavior](https://www.postgresql.org/docs/17/sql-set-transaction.html)
- [PostgreSQL roles and privileges](https://www.postgresql.org/docs/17/user-manag.html)
- [SQLAlchemy inspection](https://docs.sqlalchemy.org/en/20/core/inspection.html)

The lockfile pins a tested dependency set. The code deliberately targets official SDK v1's
FastMCP API; upgrading to a different MCP major requires a transport/API compatibility review.

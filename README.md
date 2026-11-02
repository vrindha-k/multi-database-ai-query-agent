# Multi-Database AI Query Agent (MCP)

[![CI](https://github.com/vrindha-k/multi-database-ai-query-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/vrindha-k/multi-database-ai-query-agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-stdio-black)
![Claude](https://img.shields.io/badge/Claude-Anthropic-D97757)
![License](https://img.shields.io/badge/License-MIT-green)

Ask questions across independent PostgreSQL databases. Claude discovers schemas through a real
Model Context Protocol server, writes analytical SQL, and receives bounded results from a
read-only execution layer. A Rich CLI shows the executed SQL, result tables, and the AI answer.

**Portfolio demonstration using synthetic data.** This is not a security-certified database
gateway. Live Claude answers require your own API key and incur API charges. See the
[verification report](docs/VERIFICATION.md) for what was actually executed, including limitations.

## Features

- Five discoverable MCP tools: `list_databases`, `list_tables`, `get_schema`, `run_query`,
  `explain_query`. The CLI uses MCP stdio JSON-RPC, never direct Python tool calls.
- Database routing, optional enforced database selection, dynamic columns, keys and indexes.
- Official Anthropic SDK orchestration with multiple tool calls, error feedback and turn budgets.
- SQLGlot PostgreSQL AST validation, schema authorization, approved analytics functions,
  read-only transactions, separate database reader roles, timeouts and result budgets.
- INNER/LEFT joins, subqueries, aggregates, HAVING, nonrecursive CTEs, window functions and
  date aggregation, with reference queries executed against PostgreSQL.
- Two different six-table datasets, Docker Compose, pinned dependencies, pytest and Ruff CI.
- API-key-free `/sql` and `/explain` diagnostics for repeatable local demonstrations.

## Architecture

```mermaid
flowchart LR
    User[Question in Rich CLI] --> Agent[Anthropic SDK tool loop]
    Agent <-->|Tool definitions and tool results| Claude[Claude API]
    Agent <-->|MCP stdio JSON-RPC| MCP[FastMCP server]
    MCP --> Metadata[SQLAlchemy metadata discovery]
    MCP --> Policy[SQLGlot PostgreSQL AST policy]
    Policy --> Execution[Read-only transaction and bounded results]
    Metadata --> Commerce[(E-commerce PostgreSQL)]
    Metadata --> HR[(HR PostgreSQL)]
    Execution --> Commerce
    Execution --> HR
```

The MCP client launches `python -m app.server` as a child process and initializes a
`ClientSession`. It discovers tool schemas using `list_tools`, sends them to Claude, executes
each returned `tool_use` through `session.call_tool`, and supplies matching `tool_result` blocks
in the next message. Database URLs and API keys are not included in tool definitions or results.
SQL and result data are sent to Claude. The model is instructed to inspect metadata before
querying; this workflow is guidance, while SQL authorization is enforced in code and PostgreSQL.

## Quick start: Windows 11 + Docker Desktop

Open PowerShell in this repository. Start Docker Desktop and wait for its engine to be ready.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure.ps1
code .env
# Add ANTHROPIC_API_KEY in the editor, then save. Never commit .env.
docker compose up -d --wait ecommerce hr
docker compose build agent
docker compose run --rm agent
```

`configure.ps1` generates four random credentials in the ignored `.env`. It refuses to overwrite
an existing file. The Docker image runs as a nonroot user. The server starts automatically when
the CLI connects; a separate server terminal is unnecessary for stdio transport.

At the prompt:

```text
/use ecommerce
Which five products generated the most completed-order revenue?
/use hr
What is active headcount by department as of December 31, 2025?
/help
/exit
```

Full instructions, including native Python setup, all testing commands, reset, troubleshooting,
and publishing steps: **[Windows testing guide](docs/WINDOWS_TESTING.md)**.

## Reproducible example

Question: “Which five products generated the most completed-order revenue?”

```sql
SELECT p.name, SUM(i.quantity * i.unit_price) AS revenue
FROM public.products p
JOIN public.order_items i ON i.product_id = p.id
JOIN public.orders o ON o.id = i.order_id
WHERE o.status = 'completed'
GROUP BY p.id, p.name
ORDER BY revenue DESC, p.name
LIMIT 5;
```

| Product | Gross revenue (USD) |
| --- | ---: |
| Product 11 | 25,080.00 |
| Product 08 | 16,320.00 |
| Product 10 | 15,600.00 |
| Product 12 | 12,960.00 |
| Product 07 | 11,760.00 |

This is a verified reference query, not a recorded live Claude generation. A successful AI answer
should summarize these values if it uses the same revenue definition. Seed dates are fixed in
2025; “last month” relative to today may correctly return no rows. Use explicit 2025 dates.

![Actual MCP terminal capture](docs/terminal-demo.svg)

[14 questions, SQL and database-calculated outputs](docs/EXAMPLES.md) include segment counts,
average order values, regional revenue, inactive customers, salary history, headcount, attendance,
RANK/DENSE_RANK, LAG/LEAD and running totals. Decimal values are serialized as strings to preserve
precision. Dates are ISO strings. Results are arrays with a separate column list, so duplicate
column names do not silently overwrite values.

## Data model

| Database | Tables | Synthetic volume |
| --- | --- | --- |
| ecommerce | customers, products, categories, orders, order_items, payments | 60 customers, 12 products, 720 orders, 1,440 items, 648 payments |
| hr | employees, departments, positions, salaries, attendance, performance_reviews | 80 employees, 4 departments, 160 salary records, 2,400 attendance rows, 80 reviews |

Orders are either completed or cancelled. Gross revenue is the sum of completed-order item
quantity times unit price; it excludes tax, refunds and discounts, which are not modeled.
HR termination dates support headcount and departures; a turnover percentage additionally
requires an explicitly agreed denominator. Current salary uses the latest effective date.

## Configuration

| Variable | Purpose / default |
| --- | --- |
| `ANTHROPIC_API_KEY` | Secret, optional for diagnostics/tests; required for natural language |
| `ANTHROPIC_MODEL` | Configurable Claude model ID; default `claude-sonnet-4-6` |
| `DATABASES_JSON` | JSON array of `{id, description, url, schemas}`; default `[]` |
| `DATABASE_CONFIG_FILE` | Optional local JSON array file; takes precedence over JSON env value |
| `STATEMENT_TIMEOUT_MS` | Per-statement limit, default 3000; allowed 10–30000 |
| `MAX_ROWS` | Default and maximum requested query rows; default 100, hard maximum 1000 |
| `MAX_CELL_CHARS` | String/cell truncation; default 4000, maximum 10000 |
| `MAX_AGENT_TURNS` | Claude round-trip budget; default 12, maximum 30 |
| `ECOMMERCE_ADMIN_PASSWORD`, `HR_ADMIN_PASSWORD` | Compose initialization only |
| `ECOMMERCE_READER_PASSWORD`, `HR_READER_PASSWORD` | Separate per-database readers |
| `ADMIN_URL` | Native/CI seed script only; never required by the app |

Additional databases require only configuration and a separately provisioned read-only role:

```json
[
  {
    "id": "analytics",
    "description": "Authorized synthetic analytics database",
    "url": "postgresql+psycopg://reader:URL_ENCODED_SECRET@localhost:5432/analytics",
    "schemas": ["public", "reporting"]
  }
]
```

Store this in ignored `databases.local.json`, set `DATABASE_CONFIG_FILE=databases.local.json`,
and grant SELECT/USAGE only on the intended tables/schemas. Use `postgresql+psycopg` URLs.
Avoid broad grants and reader membership in privileged roles. The demo Compose service sets its
own internal-hostname `DATABASES_JSON`; edit that override when adding containerized databases.
`localhost:5541/5542` is for host Python, `ecommerce:5432` and `hr:5432` for the agent container.

## Tests and CI

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest -q -m "not integration"
# After starting and configuring both seeded databases:
.\.venv\Scripts\python.exe -m pytest -q -m integration
```

Or use `uv sync --frozen --extra dev` and `uv run ...` for exact versions from `uv.lock`.
Tests do not require an Anthropic key. Standard tests mock the paid Claude boundary. Integration
tests use real PostgreSQL and real MCP stdio, including the agent loop with mocked Claude replies.
They compare all reference queries to stored PostgreSQL outputs and check ACLs even after
turning off transaction read-only in a direct test connection.

GitHub Actions runs Ruff, unit tests, seeded PostgreSQL integration tests, and a separate Docker
Compose build/integration job. Workflow configuration is not evidence that a hosted run passed.

## Security and limitations

- SQL is parsed as PostgreSQL, normalized and executed from the validated AST. Only one
  SELECT/read-only WITH is accepted; DDL/DML anywhere in the tree, writable CTEs, locks,
  SELECT INTO and recursive CTEs are rejected. Functions fail closed against a small allowlist.
- Physical tables are resolved through SQL scopes, checked against configured schemas and
  current SELECT privileges, and explicitly schema-qualified. Views, system tables, UDFs,
  extensions and cross-database SQL joins are deliberately unsupported.
- Both examples use separate NOSUPERUSER/NOCREATEDB/NOCREATEROLE readers, no schema CREATE or
  database TEMP privilege, SELECT grants, default read-only, a 3-second role timeout and 32 MB
  temporary-file cap. Every execution also opens a read-only transaction. Privileged roles
  are rejected at connection time. Additional databases must preserve equivalent least privilege.
- Pool size 2 per database, no overflow, connection and lock timeouts, 4 MB `work_mem`, no parallel
  workers, row caps, 128-column cap, string truncation and 256 KB row payload budget bound work
  and responses. These are per-query controls, not global admission control or an OS memory cap.
- `EXPLAIN` runs without ANALYZE. Planning itself is still subject to role/transaction controls.
  Indexes support customer/date, product and department access. Small demo tables may correctly
  use sequential scans. No claim is made that every generated query is optimal.
- API keys and URLs are secret configuration; errors and application logs omit raw driver
  exceptions, SQL literals and DSNs. Database/table descriptions and results are untrusted LLM
  input. Prompt injection may change the model's answer, but cannot bypass SQL/DB policy.
- Schema names, comments, SQL and query results leave your machine when using Claude. Use only
  data you are authorized to disclose. This demo contains no real people or customer data.
- stdio is local and has no network listener. Do not expose this as a remote service without
  authentication, authorization, rate limits, audit controls and independent security review.

## Repository map

```text
app/           configuration, metadata/execution, SQL policy, MCP server, agent, CLI
db/            deterministic schemas/data and least-privilege Docker initialization
tests/         parser, configuration, orchestration, real MCP and PostgreSQL tests
examples/      reference questions and verified outputs
scripts/       secure demo configuration, native/CI seeding, example verification, capture
docs/          Windows testing, interview walkthrough, examples, verification evidence
.github/       unit/integration and Compose CI workflow
```

## Interview walkthrough and next steps

Read the [component walkthrough](docs/WALKTHROUGH.md) for the request lifecycle, schema discovery,
authorization, testing strategy, tradeoffs and interview talking points.

Future work: query cost/admission budgets, richer type-safe result models, per-user/table
authorization, structured audit records with redaction, independently reviewed AST policies,
prompt-injection evaluations, larger randomized datasets, and SDK v2 migration. The official MCP
SDK v1 FastMCP API is deliberately pinned to its compatible major version in this implementation.

MIT licensed. No hosting deployment is needed; run locally and showcase the source on GitHub.

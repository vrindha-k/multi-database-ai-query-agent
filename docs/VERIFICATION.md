# Executed verification and remaining checks

Verified locally on **November 1, 2026**, on Windows, using workspace-local Python 3.12.13,
PostgreSQL 17.6, official MCP SDK 1.30.0, Anthropic SDK 0.125.0, SQLAlchemy 2.1.6,
psycopg 3.3.6 and SQLGlot 30.27.0. Exact transitive versions are in `uv.lock`.

## Actually executed

| Check | Observed outcome |
| --- | --- |
| Dependency installation | `uv sync --extra dev` completed successfully |
| Ruff lint | `ruff check .` passed |
| Test suite | `python -m pytest -q`: **66 passed**, no skips, in 16.37 seconds |
| Native PostgreSQL | Two independent databases initialized successfully in a local PostgreSQL 17.6 cluster |
| Reader authentication | SCRAM required for both readers; wrong-password test returned a sanitized failure |
| Discovery | Six tables per database, dynamic columns, primary/foreign keys and indexes verified |
| Reference analytics | All **14** questions executed against seeded PostgreSQL and checked against saved rows |
| SQL features | INNER/LEFT joins, GROUP BY/HAVING, subqueries, CTEs, ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD and running totals |
| Security | DML/DDL, multiple statements, writable CTEs, unauthorized schemas and dangerous functions rejected |
| Database enforcement | Direct reader DELETE denied even with transaction read-only turned off; privileged role rejected |
| Resource controls | Actual PostgreSQL timeout exercised; row, cell and aggregate response budgets tested |
| MCP transport | Real subprocess initialization, tool discovery and calls over stdio |
| Agent integration | Mocked Claude SDK responses drove actual MCP/PostgreSQL discovery, query and explanation for both databases |
| CLI | Actual CLI subprocess tested with help, exit, database switching, SELECT and rejected DELETE |
| Capture | `scripts/capture_demo.py` generated text/SVG from real MCP/PostgreSQL responses |
| Compose configuration | Official Docker Compose v5.6.1 parsed `docker-compose.yml` with `config --quiet`, exit code 0 |

The test suite includes the privileged-role test because a local test-only `ADMIN_URL` was
supplied. It is deliberately not part of the application configuration. Without it, that one
test skips; the remaining integration tests still require only the configured readers.

The native test harness used a workspace-local PostgreSQL binary distribution and temporary
cluster, not Docker. The application and sample data are the same files used by Compose, but
native initialization used `scripts/seed.py`. This does not prove the Docker image/init shell
script executes successfully in a Linux container.

## Not yet verified

- **Docker build and runtime:** Docker Desktop/Engine is unavailable in this execution session.
  Compose syntax was checked, but no image build or container execution is claimed. A separate
  GitHub Actions job is configured to build and run Compose integration tests.
- **Live Claude generation:** no Anthropic API key was provided. API orchestration is implemented
  and tested using mocked SDK response blocks; no paid request or live model answer is claimed.
- **Hosted GitHub Actions:** configured but cannot run until publication. No hosted green status
  is claimed.
- **Public GitHub publication:** requires the user's explicit approval before creating/pushing
  the public repository. No remote publication is implied by local commits.

## Reproduce

Follow [WINDOWS_TESTING.md](WINDOWS_TESTING.md) for exact PowerShell commands. Start the two demo
databases, configure readers and run:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\verify_examples.py
.\.venv\Scripts\python.exe scripts\capture_demo.py
```

`docs/EXAMPLES.md`, `examples/verified.json`, and `docs/terminal-demo.*` are real database evidence,
not live Claude transcripts. SQL result correctness is tested for the deterministic reference
queries; it does not establish correctness of arbitrary future model-generated SQL.

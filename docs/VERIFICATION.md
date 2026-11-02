# Executed verification and remaining checks

## Free-provider update (November 2, 2026)

Ollama is now the default, with no API key required. Gemini is an optional cloud provider with
an eligible free tier; Anthropic remains optional. The updated
[CI run](https://github.com/vrindha-k/multi-database-ai-query-agent/actions/runs/41500664889)
passed both the test job and Docker Compose job. The updated local suite reported **75 passed,
2 skipped** (live-model opt-in and intentionally absent administrator URL). New tests cover Ollama HTTP payloads, Gemini
SDK response objects and thought signatures, provider quota/error handling, enforced selection,
turn budgets and real MCP/PostgreSQL calls with mocked model replies. Live Gemini was not called
because no Google key was supplied. See [FREE_AI.md](FREE_AI.md) for the updated setup.

The [live local-model smoke test](https://github.com/vrindha-k/multi-database-ai-query-agent/actions/runs/41502975859)
also **passed**: Docker ran `qwen3:4b-instruct`, the model invoked real MCP/PostgreSQL tools,
and both its query result and final answer contained the verified **720 orders** count.
No API key or paid model service was used. The first attempt with the `qwen3:4b` tag timed out;
switching to the explicit non-thinking instruct variant and bounding output tokens resolved it.
This verifies the basic local inference pipeline, not arbitrary questions or hardware performance.

The original verification record follows.

Verified locally on **November 1, 2026**, on Windows, using workspace-local Python 3.12.13,
PostgreSQL 17.6, official MCP SDK 1.30.0, Anthropic SDK 0.125.0, SQLAlchemy 2.1.6,
psycopg 3.3.6 and SQLGlot 30.27.0. Exact transitive versions are in `uv.lock`.

## Actually executed

| Check | Observed outcome |
| --- | --- |
| Dependency installation | `uv sync --extra dev` completed successfully |
| Ruff lint | `ruff check .` passed |
| Test suite | Final `python -m pytest -q`: **66 passed**, no skips, in 16.64 seconds |
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
| Setup script | Windows PowerShell generated a valid environment with two database URLs and four distinct random credentials |
| CI configuration | Workflow YAML and its embedded Python setup block parsed successfully |
| Initialization shell | Git Bash `bash -n db/init.sh` passed |

The test suite includes the privileged-role test because a local test-only `ADMIN_URL` was
supplied. It is deliberately not part of the application configuration. Without it, that one
test skips; the remaining integration tests still require only the configured readers.

The native test harness used a workspace-local PostgreSQL binary distribution and temporary
cluster, not Docker. The application and sample data are the same files used by Compose, but
native initialization used `scripts/seed.py`. This does not prove the Docker image/init shell
script executes successfully in a Linux container.

## Not yet verified

- **Live Claude generation:** no Anthropic API key was provided. API orchestration is implemented
  and tested using mocked SDK response blocks; no paid request or live model answer is claimed.

## GitHub publication and Docker verification

Published with the user's approval to
[vrindha-k/multi-database-ai-query-agent](https://github.com/vrindha-k/multi-database-ai-query-agent).
The [first hosted CI run](https://github.com/vrindha-k/multi-database-ai-query-agent/actions/runs/41386163760)
passed both jobs:

- **test:** Ruff, unit/MCP tests, fresh PostgreSQL initialization and integration tests, 33 seconds.
- **compose:** both PostgreSQL containers became healthy, the application image built, and
  integration tests passed inside the nonroot application container, 45 seconds.

Docker execution is therefore verified on the hosted Linux runner, including `db/init.sh` and
the Compose setup. Docker Desktop execution on this Windows machine remains a user-side check.
The remote file tree was inspected: `.env`, virtual environments and local credentials were absent.

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

# Windows 11: test every component

**No paid API required:** follow [FREE_AI.md](FREE_AI.md) for the default local Ollama option or
the optional Google Gemini free tier. Claude-specific key instructions below apply only when
you explicitly select `AI_PROVIDER=anthropic`. Database and `/sql` instructions are unchanged.

Use PowerShell in VS Code. Commands in this guide assume the repository root is the current
directory. A first run downloads container images and Python packages and needs internet access.
Docker Desktop must be running Linux containers. All database data is synthetic.

## 1. Open the project

For the delivered copy:

```powershell
Set-Location 'C:\Users\Vrindha\Documents\Codex\2026-11-01\files-pasted-by-the-user-build\outputs\multi-database-ai-query-agent'
code .
```

After cloning from GitHub, use the cloned folder instead. In VS Code select **Terminal > New
Terminal** and select PowerShell. Keep all following commands in that root folder.

```powershell
git --version
docker --version
py -3.12 --version
```

The container-only route does not need host Python. For host development, Python 3.12 or newer
is required; if your Python launcher uses another installed version, substitute its version.

## 2. Create private credentials (AI keys are optional)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure.ps1
code .env
```

The script creates `.env` with random hexadecimal passwords for both administrators and both
readers. The file is ignored by Git. The default Ollama provider needs no AI key; follow FREE_AI.md
to start and download its model. For optional Claude, select `AI_PROVIDER=anthropic`, add your own
key after `ANTHROPIC_API_KEY=`, and save it.
Do not paste the key in chat, screenshots, committed files or command history. You can leave it
blank while testing SQL/MCP; natural-language requests will then display setup instructions.
If `.env` already exists, edit it; the script intentionally refuses to overwrite credentials.

```powershell
git check-ignore .env
```

Expected: `.env`. Do not change reader passwords after initial database creation without also
changing the database roles. Existing volumes retain their original passwords.

## 3. Start Docker Desktop and both PostgreSQL services

Open **Docker Desktop** from the Start menu. Wait for the engine to say it is running.

```powershell
docker info --format '{{.ServerVersion}}'
docker compose config --quiet
docker compose up -d --wait ecommerce hr
docker compose ps
```

Both services should be **healthy**, with host ports 5541 and 5542 bound to 127.0.0.1.
Initialization runs automatically on fresh volumes: create a reader, load its schema and seed,
then grant SELECT. Each database has a separate reader and password.

```powershell
docker compose exec ecommerce pg_isready -U postgres -d ecommerce
docker compose exec hr pg_isready -U postgres -d hr
docker compose logs --tail 30 ecommerce hr
```

Expected: “accepting connections” twice. These commands do not print passwords. Avoid sharing
`docker compose config` without `--quiet`, because interpolation can display private variables.

## 4. Confirm synthetic data loaded

The following admin commands inspect counts only. Application queries use reader accounts.

```powershell
docker compose exec ecommerce psql -U postgres -d ecommerce -c "SELECT count(*) AS orders FROM orders;"
docker compose exec hr psql -U postgres -d hr -c "SELECT count(*) AS employees FROM employees;"
```

Expected counts: **720 orders**, **80 employees**. Dataset files are `db/ecommerce.sql` and
`db/hr.sql`. Data dates are fixed in 2025; use explicit dates in your questions.

## 5. Build the CLI and start the MCP server

```powershell
docker compose build agent
docker compose run --rm agent
```

The CLI automatically starts its own MCP server child process over **stdio**. There is no MCP
port to open and no separate server needed. You should see the title, two database descriptions,
`available: true`, and `schemas: ["public"]` for each database.

To inspect the standalone server entry point, exit the CLI and run:

```powershell
docker compose run --rm -T agent python -m app.server
```

It waits for MCP JSON-RPC on stdin; it is not a human question prompt. Press Ctrl+C to stop.
The automated stdio test below is the proper way to confirm tool discovery and calls.

## 6. Prove MCP and SQL work before calling Claude

Launch the CLI again, then type these at its prompt (these are CLI commands, not PowerShell):

```text
/databases
/use ecommerce
/tables
/sql SELECT count(*) AS orders FROM orders
/explain SELECT id FROM orders WHERE customer_id=1
/use hr
/sql SELECT count(*) AS employees FROM employees
/help
```

Expected: six discovered tables in ecommerce, orders **720**, employees **80**. `/explain`
returns tables, joins, filters, aggregates, windows and a PostgreSQL plan. Plans are estimates;
the tool does not execute `EXPLAIN ANALYZE`.

## 7. Ask natural-language questions

Start Ollama using FREE_AI.md, or configure the selected cloud provider's key. Restart the CLI
after editing provider settings. Each successful answer shows
the executed SQL, rows and truncation indicator, followed by Claude's answer. The exact wording
and SQL may vary. Compare the result semantics to [EXAMPLES.md](EXAMPLES.md), where the complete
reference SQL and PostgreSQL-calculated output are provided for each of these questions.

| # | Use | Type this question | Verified result summary |
| --- | --- | --- | --- |
| 1 | ecommerce | How many customers are in each segment? | Business 20, Consumer 20, Enterprise 20 |
| 2 | ecommerce | What is total completed-order revenue in 2025? | 124,560.00 USD |
| 3 | ecommerce | Which five products generated the most completed-order revenue? | Product 11: 25,080; 08: 16,320; 10: 15,600; 12: 12,960; 07: 11,760 |
| 4 | ecommerce | How many customers placed more than three completed orders? | 54 |
| 5 | ecommerce | What is average completed-order value by customer segment? | Business 256.67; Consumer 183.33; Enterprise 136.67 |
| 6 | ecommerce | Compare completed-order revenue across regions in 2025. | East 44,400; North 26,400; South 25,440; West 28,320 |
| 7 | ecommerce | Show January through March 2025 revenue, previous-month revenue and running totals. | Revenue 10,630 / 9,880 / 10,450; running total 10,630 / 20,510 / 30,960 |
| 8 | ecommerce | Which customers had no completed orders during the 90 days ending December 31, 2025? | IDs 10, 20, 30, 40, 50, 60 |
| 9 | hr | What is active headcount by department as of December 31, 2025? | Engineering 20, Operations 10, People 20, Sales 20 |
| 10 | hr | What is average latest annual salary by department, including former employees? | Engineering 81,000; Operations 84,000; People 83,000; Sales 82,000 |
| 11 | hr | Rank departments by average performance score with RANK and DENSE_RANK. | All 3.00, all rank 1 and dense_rank 1 |
| 12 | hr | How many attendance hours were recorded per department in September 2025? | Engineering 4,112; Operations 4,120; People 4,120; Sales 4,112 |
| 13 | hr | Which department had the most departures during 2025? | Operations: 10 |
| 14 | hr | Show the first three employee salary ranks and next higher salary with LEAD. | Employees 1/2/3: salary 43k/44k/45k, next 44k/45k/46k |

Select a database with `/use ecommerce` or `/use hr`. `/use auto` lets Claude choose from both.
Selecting one database blocks tool calls targeting the other. Independent databases cannot be
joined in one SQL statement. Comparisons require separate query calls.

## 8. Verify generated SQL, joins and window functions

Check that completed revenue filters `status='completed'`, joins items using `order_id`, and
multiplies quantity by unit price. Check that joins do not double-count an order when computing
average order value: aggregate items to the order level first, then average those totals.

Use `/explain <SQL>` to review structure and indexes; no guarantee of optimality is implied.
Compare results using the independent reference SQL in EXAMPLES.md or run this exact multi-table
join through `/sql`:

```text
/use ecommerce
/sql SELECT p.name,SUM(i.quantity*i.unit_price) AS revenue FROM products p JOIN order_items i ON i.product_id=p.id JOIN orders o ON o.id=i.order_id WHERE o.status='completed' GROUP BY p.id,p.name ORDER BY revenue DESC,p.name LIMIT 5
```

For a short deterministic window test:

```text
/use hr
/sql SELECT employee_id,annual_amount,ROW_NUMBER() OVER(ORDER BY annual_amount,employee_id) AS row_number,LEAD(annual_amount) OVER(ORDER BY annual_amount,employee_id) AS next_salary FROM salaries WHERE effective_from=DATE '2025-01-01' ORDER BY annual_amount,employee_id LIMIT 3
```

Expected rows: `(1,43000.00,1,44000.00)`, `(2,44000.00,2,45000.00)`,
`(3,45000.00,3,46000.00)`. Question 7 demonstrates LAG and running totals; question 11 tests
ties in RANK and DENSE_RANK; question 10 uses a CTE and partitioned ROW_NUMBER.

## 9. Test dangerous SQL is blocked

Inside the CLI:

```text
/use ecommerce
/sql DELETE FROM customers
/sql DROP TABLE customers
/sql UPDATE customers SET name='x'
/sql INSERT INTO customers(id) VALUES(999)
/sql SELECT 1; SELECT 2
/sql SELECT * FROM pg_catalog.pg_authid
/sql SELECT pg_sleep(30)
/sql WITH x AS (DELETE FROM customers RETURNING *) SELECT * FROM x
/sql SELECT count(*) FROM customers
```

Each unsafe request should return a policy error; the final count remains **60**. These tests use
the execution layer directly through MCP, independent of whether Claude would choose to comply.
Automated integration tests separately try a direct DELETE as the reader after disabling
transaction read-only; PostgreSQL ACLs must still deny it.

## 10. Run automated tests

Exit the CLI with `/exit`. Container tests use the same private Compose configuration:

```powershell
docker compose run --rm -T agent python -m pytest -q -m "not integration"
docker compose run --rm -T agent python -m pytest -q -m integration
docker compose run --rm -T agent ruff check .
```

The privileged-config test intentionally skips when no `ADMIN_URL` is supplied. The application
container does not need admin credentials. Tests must never require an Anthropic API key.

For native development, using your Windows Python installation:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest -q -m "not integration"
.\.venv\Scripts\python.exe -m pytest -q -m integration
.\.venv\Scripts\python.exe -m app.cli
```

No venv activation is needed. Host Python reads `localhost:5541/5542` URLs generated in `.env`.
Do not run integration tests against production data. Empty configuration skips integration
fixtures; a configured but unreachable database causes failures, rather than silently passing.

To regenerate reference examples from your seeded local databases:

```powershell
.\.venv\Scripts\python.exe scripts\verify_examples.py
.\.venv\Scripts\python.exe -m pytest -q -m integration
```

This rewrites `examples/verified.json` and `docs/EXAMPLES.md`. Review differences before committing.

## 11. Stop, restart and reset

```powershell
docker compose stop
docker compose start --wait ecommerce hr
docker compose run --rm agent
```

Remove containers while preserving data:

```powershell
docker compose down
docker compose up -d --wait ecommerce hr
```

**Reset deletes both synthetic volumes and all changes made to them.** Use only for this demo:

```powershell
docker compose down --volumes
docker compose up -d --wait ecommerce hr
```

Initialization scripts run on empty volumes only. If you changed `.env` passwords and get
authentication failures, restore the original passwords or reset the synthetic volumes.

## 12. Publish to your existing GitHub account after review

The delivered repository is local. No public repository or push is implied by local commits.
Review the source, verification report and staged file names. Never add `.env` with `-f`.

If Git reports “dubious ownership” because this copy was created by a workspace account, mark
only this reviewed project folder as trusted, then retry:

```powershell
git config --global --add safe.directory (Get-Location).Path
```

If you extracted the source ZIP instead of using the delivered working repository, initialize
your own local history first:

```powershell
git init -b main
git add .
git commit -m "Build schema-discovering MCP PostgreSQL analytics agent"
```

```powershell
git status --short
git log --oneline
git ls-files
git ls-files .env
git check-ignore .env
```

`git ls-files .env` must print nothing. The CLI below uses your existing GitHub account and does
not create an account. Only execute the publishing command after approving public publication:

```powershell
gh auth status
# If needed, authenticate your existing account:
gh auth login
# After your explicit approval to publish:
gh repo create multi-database-ai-query-agent --public --source . --remote origin --push
```

If that repository name already exists, inspect it first; do not overwrite an existing project.
For a previously created empty repository, add its HTTPS URL as `origin` and `git push -u origin
main`. Never force-push another repository's history.

```powershell
gh repo view --web
gh run list --limit 5
git remote -v
git status --short
```

On GitHub verify README rendering, architecture, terminal capture, source, `db`, `tests`, `docs`,
`uv.lock`, Dockerfile, Compose, license and `.github/workflows/ci.yml`. Open Actions and inspect
both CI jobs. Confirm `.env`, `.venv`, database files and real keys are absent. A hosted green
workflow is verified only after it has actually run.

## Troubleshooting

- **Docker not recognized:** start Docker Desktop and reopen PowerShell; confirm Linux containers.
- **Unhealthy database:** inspect `docker compose logs`; check occupied ports and fresh-volume init.
- **Authentication failed after edits:** volumes still have the old passwords; see reset instructions.
- **API failure:** confirm the saved key, account credit and model availability. Never print the key.
- **No rows for “last month”:** fixed synthetic data is from 2025; ask about 2025 explicitly.
- **Function rejected:** the function allowlist is conservative. Prefer supported analytics functions;
  do not disable validation. Add functions only after evaluating their PostgreSQL semantics.
- **Timeout:** simplify SQL, filter earlier, inspect indexes and EXPLAIN. A row limit bounds output,
  but an aggregate can still scan many rows before returning one row.

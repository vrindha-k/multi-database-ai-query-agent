# Free AI: Ollama or Google Gemini

The default provider is now **Ollama**, which runs a model locally without an API key or
API usage bill. It uses your computer's CPU/RAM and needs a model download of several GB.
**Gemini** is an optional hosted alternative with a limited free tier for eligible models/accounts.
Claude remains available by explicitly selecting `AI_PROVIDER=anthropic`.

## Recommended: Ollama through your existing Docker Desktop

If you are at the application's `ecommerce>` prompt, type `/exit` first. In PowerShell in this
project folder, run these one at a time:

```powershell
docker compose build agent
docker compose --profile local-ai up -d --wait ollama
docker compose exec ollama ollama pull qwen3:4b-instruct
docker compose run --rm -e AI_PROVIDER=ollama agent
```

The model download can take several minutes. It is cached in a persistent `ollama_models` volume;
pulling the same model again reuses the cache. No account or credit card is required for this local
model. Running it on CPU may be slower and less reliable at SQL/tool use than larger cloud models.
Allow several minutes for a first question. The shipped model request timeout is 180 seconds.

At the application prompt:

```text
/use ecommerce
How many orders are in the orders table? Use run_query and report the count.
```

Expected database result: **720**. Then:

```text
/use hr
How many employees are in the employees table? Use run_query and report the count.
```

Expected: **80**. Both providers use the same real MCP server and read-only SQL controls. The
new tool loop refuses to present a model answer as a database result unless run_query succeeded.
If the small model fails, narrow the question or inspect results using `/sql`.

For less memory usage, pull `qwen3:1.7b` and start with
`docker compose run --rm -e AI_PROVIDER=ollama -e OLLAMA_MODEL=qwen3:1.7b agent`.
Smaller models may make more SQL/tool mistakes. Do not use cloud-tagged models for this local route.

Stop the local model container with `docker compose stop ollama`; the databases can remain running.
`docker compose down --volumes` now also deletes downloaded models as well as both demo databases.

### If Ollama is installed on Windows instead

Start the Ollama Windows application and run `ollama pull qwen3:4b-instruct`. Point the Docker client to
your host's Ollama service:

```powershell
docker compose run --rm -e AI_PROVIDER=ollama -e OLLAMA_BASE_URL=http://host.docker.internal:11434 agent
```

Native Python uses `OLLAMA_BASE_URL=http://localhost:11434`. Containerized Ollama is reached by
the agent at `http://ollama:11434`; the Compose override selects that address by default.

## Google Gemini free tier

Google offers a **limited free tier**, not unlimited free usage. Availability and quotas depend
on the model, region and account. Check your project tier in AI Studio. Keep billing disabled
if you want to avoid paid usage, choose a free-tier eligible model, and do not upgrade to paid
billing as part of this setup. This app does not automatically switch providers or paid models.
Quota exhaustion returns a clear error; you can wait or choose Ollama.

1. Open [Google AI Studio API keys](https://aistudio.google.com/apikey) and sign in yourself.
2. Create a Gemini API key in an eligible free-tier project.
3. Type `/exit` in the application, then run `notepad .env` in PowerShell.
4. Add or update these lines, putting the real key only in your local ignored file:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=PASTE_YOUR_OWN_KEY_HERE
GEMINI_MODEL=gemini-2.5-flash
```

5. Save and restart:

```powershell
docker compose build agent
docker compose run --rm -e AI_PROVIDER=gemini agent
```

No Ollama model/container is needed for Gemini. Do not send your key in chat or commit `.env`.
For eligible models, free-tier requests fail on quota exhaustion; enabling paid billing changes
the billing behavior. Check current [pricing](https://ai.google.dev/gemini-api/docs/pricing) and
[rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) before relying on the free tier.

**Data:** Gemini's free tier may use input/output to improve Google's products. This demo uses
synthetic records; do not send private customer/employee data. Local Ollama keeps model inference
on your machine. Both options still apply the same SQL parser, database permissions and limits.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AI_PROVIDER` | `ollama` | `ollama`, `gemini`, or `anthropic`; no automatic paid fallback |
| `OLLAMA_MODEL` | `qwen3:4b-instruct` | Locally downloaded model with tool calling support |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Native Python Ollama address |
| `OLLAMA_DOCKER_URL` | `http://ollama:11434` | Compose override for Ollama address |
| `GEMINI_API_KEY` | empty | Private Google AI Studio key; only needed for Gemini |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Configurable model; confirm free-tier eligibility |

`ANTHROPIC_API_KEY` is optional and unused by Ollama/Gemini. The new defaults also apply to an
existing `.env` without an AI_PROVIDER line, so your existing database passwords stay unchanged.

## Implementation and verification

`app/providers.py` implements Ollama's HTTP tool protocol and the official `google-genai` SDK.
Gemini automatic Python function execution is disabled: every requested database operation goes
through MCP. Original Gemini Content objects and thought signatures are preserved across tool
round trips, and function-response IDs are matched when provided.

Unit tests exercise HTTP payloads, SDK response objects, tool results, database selection, quota
errors, model errors, turn budgets and ungrounded replies. PostgreSQL integration tests drive
Ollama-format replies through real MCP calls against both databases while mocking the model
boundary. These tests do not prove the quality of every local model or a live Gemini API key.

A [real local-model smoke test](https://github.com/vrindha-k/multi-database-ai-query-agent/actions/runs/41502975859)
passed using Docker, `qwen3:4b-instruct`, actual MCP calls and PostgreSQL: the natural-language
order-count question produced the verified result and answer **720**. This required no API key.
The optional `Local AI smoke test (no API key)` workflow can repeat it. Live Gemini remains
untested without your own key. Use the explicit `-instruct` model tag: the generic 4b thinking tag
timed out during verification. Generation is bounded to 512 tokens per model response.

Primary references: [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling),
[Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling),
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

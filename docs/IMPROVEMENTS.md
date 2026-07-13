# Astrolabe — improvement backlog

Consolidated list of known bugs, cost problems, and performance work, ordered by priority and annotated with difficulty. Every item below was verified against the code at the line numbers given — none of it is speculative.

**Difficulty:** `XS` <30min · `S` ~1h · `M` half a day · `L` multi-day

**One structural fact to keep in mind:** `Dockerfile:37` runs a **single uvicorn worker**, and that is load-bearing. Nearly everything in P2 is currently held together by the fact that only one process with one event loop ever touches the state. Adding `--workers 2` today turns a pile of latent races into guaranteed corruption. Do not scale horizontally before P2 is done.

---

## Summary

| # | Item | Priority | Difficulty |
|---|------|----------|------------|
| 1 | Stale `processing` row wedges a repo forever | P0 | XS |
| 2 | Failed job re-fires a full LLM run on every page load | P0 | XS |
| 3 | `read_file` has no size cap | P0 | XS |
| 4 | Partial embed marked `ready` — silently truncated corpus | P1 | S |
| 5 | `repo_id` collision (`-` → `_`) mixes two repos | P1 | S |
| 6 | `max_iterations` too high (40/30/30/30) | P1 | XS |
| 7 | `temperature=0.7` on strict-JSON tasks | P1 | XS |
| 8 | LLM asked to compute what `analyze_files()` already knows | P1 | S |
| 9 | Background jobs block the event loop | P1 | S |
| 10 | Ingestion starves chat's thread pool | P1 | S |
| 11 | Text-ReAct makes cost quadratic in step count | P2 | M |
| 12 | No prompt caching anywhere | P2 | M |
| 13 | `insight_generator` ignores the vector store | P2 | M |
| 14 | `search_in_files` walks `node_modules` | P2 | XS |
| 15 | Concurrent ingest of the same repo is unguarded | P2 | S |
| 16 | `agent_cache` never evicts | P2 | S |
| 17 | SQLite has no WAL and no busy timeout | P2 | XS |
| 18 | No index on `sessions(user_id, repo_id)` | P2 | XS |
| 19 | `DELETE /repos/{id}` doesn't cascade | P2 | S |
| 20 | Chat history silently truncated on save | P2 | S |
| 21 | No clone depth limit, no repo size caps | P3 | M |
| 22 | No tests, no structured logging | P3 | L |
| 23 | No rate limiting, no cost controls | P3 | M |

---

## P0 — Broken in production right now

### 1. A stale `processing` row wedges a repo forever · XS

**This is the bug currently breaking `rabea25__sisapi` on the live site.**

`api/routes/docs.py:49` (and `charts.py:60`) short-circuits duplicate work:

```python
existing = get_repo_docs(repo_id)
if existing and existing["status"] in ("processing", "ready"):
    return {...}   # 200 OK, dispatches nothing
```

Jobs run as `BackgroundTasks`, which live in process memory. When the process dies mid-job — a redeploy, an OOM, a crash — the job evaporates but the DB row stays `"processing"`. Nothing anywhere ever resets it: there is no startup reconciliation, no timeout, no sweeper (grep `api/main.py` and `api/database.py` for `processing` — zero hits). `docker-compose.yml:16` is `restart: unless-stopped`, so the container quietly comes back and the row is now permanent.

From then on `POST /docs` returns `200 OK` and starts nothing, `GET /docs` reports `"processing"` forever, and the frontend polls until the heat death of the universe. Zero LLM calls, so it looks exactly like a rate limit or an outage.

**Unwedge:** `sqlite3 repo_illustrator.db "DELETE FROM docs WHERE repo_id='<id>';"` (the DB is bind-mounted; no restart needed).

**Fix:** (a) in `lifespan()`, reset every `processing` row in `docs` / `charts` / `insights` / `registry` to `error: interrupted by restart`; (b) treat a `processing` row older than N minutes as dead and re-dispatch, rather than trusting it forever.

### 2. A failed job re-fires a full LLM run on every page load · XS

The mirror image of #1, same guard. `"error"` is **not** in that tuple, so an errored row falls straight through to `save_docs_status(repo_id, "processing")` and a fresh dispatch. Meanwhile `frontend/src/pages/RepoIllustrationPage.jsx` auto-fires `startCharts(repoId)` from a `useEffect` on **every mount**.

Net effect: any repo whose charts/docs job fails burns a complete 30–40 iteration agent run on every single page load and refresh, forever, with no backoff and no cap. This is probably your single largest source of unexplained spend.

**Fix:** add `"error"` to the guard and require an explicit user-initiated retry to clear it; stop auto-firing `startCharts` on mount.

### 3. `read_file` has no size cap · XS

`rag/agent_tools.py:46`:

```python
if candidate.exists() and candidate.is_file():
    return candidate.read_text(encoding="utf-8", errors="replace")   # entire file, no limit
```

`search_in_files` in the same file caps at `matches[:50]` and `line.strip()[:200]`, and `get_repo_structure` caps at `lines[:100]` — so the caps were simply forgotten here. A 3,000-line file is ~30k tokens in a single observation. A `package-lock.json` is far worse, and the charts prompt explicitly tells the agent to go read dependency files.

This compounds viciously with #11: in text-ReAct mode that giant observation is re-serialized into the prompt on **every subsequent step**. One fat `read_file` at step 3 of a 30-step run gets billed ~27 more times.

It also means `GROQ_MODEL=llama3-70b-8192` — an 8k-context model — can be hard-failed by a single file read.

**Fix:** cap at ~400 lines / 15k chars with a truncation notice that points the agent at `search_in_files` for the rest.

---

## P1 — Correctness and cost

### 4. A partial embed gets marked `ready` · S

The worst bug in the codebase, because it is completely invisible.

`ingestion/pipeline.py` inserts nodes into Chroma batch by batch with no transaction. If batch 30 of 100 dies, `process_repo` writes `status = "error"` but **does not clean up** — `_cleanup_repo_artifacts` only runs on user *cancel*, never on failure. The partial collection survives.

On retry the clone exists and its hash matches, so `was_updated = False`. And `collection_exists()` in `vectorstore/chroma_store.py` is just `col.count() > 0` — **true**, from those 30 partial batches. So the pipeline returns the index without embedding anything and marks the repo `ready`.

The repo is now permanently indexed with 30% of its content. Every chat answer, insight, and chart is computed against a truncated corpus and nothing surfaces an error.

**Fix:** replace `collection_exists()` (meaning "has ≥1 vector" — the root error) with two predicates: `has_vectors()` and `is_complete()`. Stamp an `ingest_complete` marker plus the node count into the collection's metadata *only* after the final batch lands; Chroma persists metadata, so it survives a hard kill. Reuse a collection only when `is_complete()`. Otherwise reset and rebuild.

> This was written once and lost before it was committed. It needs redoing.

### 5. `repo_id` collision mixes two repos together · S

`generate_repo_id()` is duplicated byte-for-byte in `api/routes/ingestion.py:20-26` and `ingestion/preprocessor.py:65-72`, and mangles the name:

```python
f"{parts[0]}__{repo}".lower().replace('-', '_')
```

So `acme/my-secrets` and `acme/my_secrets` **both become `acme__my_secrets`**. That id keys three namespaces at once: the registry row, the Chroma collection, and `data/raw/<id>` + `data/processed/<id>`.

- **Likely case (corruption):** someone ingests `org/data-tools`, later `org/data_tools`. The second silently reuses the first's clone and vectors, and its page serves the first repo's content.
- **Narrow case (cross-tenant read):** if a user can see `acme/my_secrets` and a *different* user's private `acme/my-secrets` is already ingested, the `/ingest` fast path writes them a `repo_access` row on the shared id — granting them the victim's private repo. Requires both repos under the same owner, so it isn't an internet-wide exploit, but within one org it is real and it defeats the authorization model.

**Fix:** stop replacing `-` with `_`. Hyphens are legal in Chroma collection names and in paths; the substitution was never necessary. Delete the duplicate, keep one shared helper. Lowercasing is safe (GitHub repo names are case-insensitive). Changing the id orphans existing rows/collections/dirs — all regenerable, so just re-ingest rather than writing a migration.

### 6. `max_iterations` is set far too high · XS

`insights/document_generator.py:94` → **40**. `rag/insight_generator.py:80`, `insights/provider.py:190`, `llm/chatbot.py:135,150` → **30**.

These are the *worst-case* bill multiplier, and with #11 the growth is quadratic, not linear. Nothing in these tasks plausibly needs 40 tool calls.

**Fix:** drop to ~10–12 and log when the ceiling is actually hit. If it's hit often, the prompt is the problem, not the ceiling.

### 7. `temperature=0.7` on strict-JSON tasks · XS

`rag/agent_tools.py:13` defaults every provider to `temperature=0.7`, and the three JSON-extraction agents (insights, charts, docs) never override it. `rag/insight_generator.py` already has a `parse_warning` fallback path for *"Agent did not return valid JSON"* — that fallback exists because this keeps happening. Each malformed response is a wasted round trip, sometimes several.

**Fix:** `temperature=0` for the three extraction tasks. Leave chat at 0.7.

### 8. The LLM is doing a `Counter`'s job · S

`insights/provider.py:21,26` asks the model to produce `language_breakdown` percentages that "must sum to 100". Meanwhile `insights/analyzer.py:64` (`analyze_files`) already walks the entire tree collecting `path.suffix`, LOC per file, test markers, TODOs, and the top-5 complex files.

So the charts agent burns a long exploration loop guessing numbers that a deterministic pass already has exactly — and guesses them *wrong*, because an LLM eyeballing a file tree cannot count lines.

**Fix:** compute `language_breakdown` and `dependencies` deterministically from `analyze_files()` plus `package.json` / `requirements.txt`, and hand them to the agent as *input* rather than asking for them as output. Removes most of the charts agent's exploration and makes the numbers correct instead of plausible.

### 9. Background jobs block the entire event loop · S

`_run_charts_job`, `_run_docs_job`, `_run_insight_job` are all `async def`, so Starlette runs them **inline on the event loop** — but the code inside is synchronous blocking I/O:

- `insights/provider.py:100` — `time.sleep(3)`, hard
- `insights/provider.py:98,141` — `requests.get(..., timeout=20/15)`
- `insights/analyzer.py:32,51` — more `requests.get`
- `insights/analyzer.py:131` — `subprocess.run(["git","log",...], timeout=20)`

One `POST /charts` can freeze **every** user's chat and status poll for 40+ seconds. Most user-visible defect in the app.

**Fix:** cheap version — make these jobs sync `def`, and Starlette runs them in the threadpool automatically. Correct version — `requests` → `httpx.AsyncClient`, `time.sleep` → `asyncio.sleep`.

### 10. Ingestion starves chat's thread pool · S

`api/routes/ingestion.py:153` dispatches via `loop.run_in_executor(None, ...)` — the **default** `ThreadPoolExecutor`. But `asyncio.to_thread()` uses that same default pool, and LlamaIndex routes its hot paths through it: query embedding and reranking (which is how the sync `RepoReranker` gets called).

So every chat query's embed + rerank must win a slot in a pool that minutes-long ingestions are camped in. The pool is `min(32, cpu_count + 4)` — **6 slots on a 2-vCPU box**. Six concurrent ingests and chat doesn't slow down, it *hangs*, with no timeout and unbounded queueing. This is the "one person at a time" feeling.

**Fix:** give ingestion its own bounded `ThreadPoolExecutor` (even `max_workers=2`) so it can never starve the request path.

---

## P2 — Structural

### 11. Text-ReAct makes cost quadratic in step count · M

All four agents force `is_function_calling_model=False` (`rag/insight_generator.py:69`, `insights/document_generator.py:83`, `insights/provider.py:179`, `llm/chatbot.py:64`). That selects LlamaIndex's text-ReAct loop, which re-serializes the **entire scratchpad** — system prompt, tool schemas, and every prior Thought/Action/Observation — into the prompt on every single step.

Cost is therefore quadratic in step count, and every oversized observation (#3) is re-billed on every subsequent step. Estimated **~330k typical, 4–5M worst-case input tokens per repo**.

**Fix:** switch to native function calling. **Tradeoff:** the "Thinking…" streaming UI depends on ReAct's thought text, so this is a product decision, not a pure refactor. Do #3 and #6 first — they capture much of the win without touching the UI.

### 12. No prompt caching anywhere · M

Biggest theoretical win — up to ~90% off input tokens, and these agents re-send an identical system prompt + tool schema block on every step of every run. Requires provider-specific plumbing through LlamaIndex (cache breakpoints on the system block), which may not be clean. Worth a spike, but don't budget for it landing easily.

### 13. `insight_generator` ignores the vector store · M

It lives in `rag/` but never touches ChromaDB. It stuffs raw file contents into the prompt via `read_file` instead of using the bounded, reranked `search_codebase` path (top_k=30 → reranked to 5) that already exists and is already paid for.

### 14. `search_in_files` walks `node_modules` · XS

`rag/agent_tools.py:80` does `repo_path.rglob("*")` without applying `SKIP_DIRS`. Wall-clock waste, not token waste — but it's a two-line fix.

### 15. Concurrent ingest of the same repo is unguarded · S

Nothing between the `status == "ready"` check (`ingestion.py:131`) and `save_repo_status("processing")` (`ingestion.py:146`) stops two requests from both dispatching — a repo mid-`processing` falls straight through the fast path. Two threads then `copytree`/`rmtree` the same directory and write the same Chroma collection. `state.stop_events[repo_id]` gets clobbered, so the first ingest becomes unstoppable and whichever finishes first pops the *other's* stop event.

Two people pasting the same popular repo URL is the expected case, not an edge case.

**Fix:** treat `processing` as a fast-path hit ("already in progress") instead of falling through.

### 16. `agent_cache` never evicts · S

`index_cache`, `agent_cache`, `stop_events` are plain dicts on `app.state` (`api/main.py:27-28`). One `Chatbot` — LLM client plus a 6000-token memory buffer — is retained per `session_id:repo_id`, forever. A straight memory leak proportional to lifetime conversation count. Needs an LRU with a size cap.

### 17. SQLite has no WAL and no busy timeout · XS

`journal_mode=delete` on the live file: readers block writers. Every `database.py` function opens a fresh connection and never closes it (`with sqlite3.connect(...)` commits but doesn't close). All calls are synchronous inside `async def` handlers, so a 5s lock wait freezes the whole process. Enabling WAL + `busy_timeout` is two lines and buys a lot.

### 18. No index on `sessions(user_id, repo_id)` · XS

No indexes exist beyond the PK autoindexes. `list_user_sessions` full-scans and filesorts the fastest-growing table in the schema.

### 19. `DELETE /repos/{id}` doesn't cascade · S

`delete_repo_registry` (`api/database.py:159-162`) removes `registry` + `repo_access` only. The `insights`, `charts`, `docs`, and `sessions` rows survive — and they contain LLM-generated summaries of what may have been a **private** repo. Chat history for a deleted repo also stays readable (`chat.py:156-172` never rechecks that the repo exists). The endpoint is also unrestricted for public repos — no UI button, but reachable with curl.

### 20. Chat history is silently truncated on save · S

`save_session` persists `chatbot.chat_history` → `self._memory.get()` (`llm/chatbot.py:109-113`), which is the **token-limited window**, not `get_all()`. The `ON CONFLICT DO UPDATE SET history=excluded.history` then overwrites the stored full history with that truncated window. Past 6000 tokens, older turns are permanently destroyed.

---

## P3 — Product-grade (not bugs; just absent)

### 21. No clone depth limit, no size caps · M

`git clone` has no `--depth 1` (`ingestion/preprocessor.py:143`) — full history, kept forever. Ingest costs ~2× repo size (`copytree` then prune). No cap on repo size, file size, or file count. The only brake on ingesting something enormous is an accidental 60s clone timeout — and on timeout git is SIGKILLed, leaving a partial `data/raw/<id>` that wedges the repo_id permanently, because every retry `git pull`s a broken clone. Unauthenticated, for public repos.

### 22. No tests, no structured logging · L

Not one test in the repo. The auth work is covered only by throwaway scripts. Failures are `print()` to stdout in a detached container, with no error tracking.

### 23. No rate limiting, no cost controls · M

Every `/ingest`, `/charts`, `/docs`, `/insight` is an uncapped LLM spend, and ingestion is uncapped CPU/disk. Nothing stops one user draining the API budget. `repo_id` is also guessable (`owner__name`), so enumeration is trivial and any authz hole is immediately exploitable at scale.

Also note: `FERNET_KEY` sits in `.env` next to the DB it protects, so encryption defends against a leaked *database*, not a compromised *host*. Fine for now — just know the limit.

---

## Suggested order

1. **#1, #2, #3** — one afternoon, all XS. Unwedges production, stops the runaway re-fire loop, and kills the single worst token sink.
2. **#6, #7** — two more XS config changes; meaningful cost drop for near-zero risk.
3. **#4, #5** — the two silent-corruption bugs. They defeat the auth model and poison the corpus.
4. **#9, #10** — stop background jobs freezing the server; isolate ingestion's pool. Biggest felt improvement per line changed.
5. **#8** — removes most of the charts agent's work *and* makes its output correct.
6. **#15, #16, #17, #18** — cheap; kills the wedged-repo class of bug and the worst DB contention.
7. **#11, #12, #13** — the real cost restructure. Only worth starting once the cheap wins are banked, since they'll tell you how much is actually left on the table.
8. **Only then** consider `--workers 2`, and only after `stop_events` and the caches move out of process memory.

## Verification

There are no tests, so nothing here is currently verifiable. Minimum bar before touching any of it:

- **#1:** start a docs job, `docker kill` the container mid-run, bring it back; assert the row is `error`, not `processing`, and that a retry actually dispatches.
- **#2:** force a charts job to fail, then reload the page 5×; assert exactly zero new LLM runs.
- **#3:** point an agent at a repo containing a 5k-line file; assert the observation is truncated and the run still completes.
- **#4:** kill the process mid-ingest, restart, re-ingest; assert `collection.count()` matches the expected node count, not the partial one.
- **#5:** ingest `org/a-b` then `org/a_b`; assert distinct `repo_id`, distinct collections, distinct `data/processed` dirs.
- **#9:** start a `/charts` job on a large repo while polling `/repos/`; assert p99 latency stays flat instead of spiking to 40s.
- **#15:** fire two simultaneous `POST /ingest` for the same URL; assert exactly one `process_repo` runs and `/stop` still cancels it.

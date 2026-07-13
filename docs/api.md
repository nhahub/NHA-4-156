# Astrolabe API

Base URL: `http://localhost:8000`

Auth routes sit at the root (`/auth/...`). Everything else is under `/repos`.

An interactive OpenAPI explorer is served at `/docs`.

## Authentication

Auth is a **signed session cookie** (`repo_illustrator_session`), set by the GitHub OAuth flow. Browsers send it automatically; from JS you must use `credentials: "include"`, and from curl you need a cookie jar.

Three levels of protection:

| Level | Applies to | Behaviour |
|---|---|---|
| Open | Public repos: ingest, status, insights, charts, docs | Works logged out |
| Login required | All `/repos/chat/*` endpoints | `401` if no session |
| Access-checked | Any endpoint for a **private** repo | `401` if logged out, `403` if the user isn't a collaborator |

For a private repo with no cached grant, the backend probes GitHub with the user's own token, then caches the result in a `repo_access` row.

### Common error responses

| Status | Meaning |
|---|---|
| `401` | Not logged in, or the stored GitHub token expired (log in again) |
| `403` | Logged in, but no access to this private repo |
| `404` | Repo not ingested, or a chat session that isn't yours (existence is deliberately not leaked) |
| `409` | Repo isn't `ready` yet — ingest first |

---

### `GET /auth/login`

Redirects the browser to GitHub's authorize page. Stores a random `state` in the session to prevent OAuth login CSRF.

| Query param | Default | Description |
|---|---|---|
| `next` | `/` | In-app path to return to after login. Must be a same-site absolute path — absolute URLs and `//evil.com` are rejected and fall back to `/`. |

Scopes requested: `read:user repo`. (`repo` is the only classic OAuth scope that grants private repo reads — there is no read-only variant.)

---

### `GET /auth/callback`

Where GitHub sends the browser back. Validates `state`, exchanges the code for a token, upserts the user, sets the session cookie, and redirects to the `next` path from `/auth/login`.

The callback URL must match the one registered on the OAuth App **byte-for-byte**, which is why `next` rides in the session rather than as a query param.

---

### `POST /auth/logout`

Clears the session. The user's encrypted GitHub token stays in the DB for next login — it's tied to the GitHub account, not the session.

**Response `200 OK`:**
```json
{ "message": "Logged out." }
```

---

### `GET /auth/me`

The logged-in user's public profile. The GitHub token is **never** included.

**Response `200 OK`:**
```json
{
  "id": 1,
  "login": "octocat",
  "name": "The Octocat",
  "email": "octocat@github.com",
  "avatar_url": "https://avatars.githubusercontent.com/u/583231",
  "html_url": "https://github.com/octocat"
}
```

**Response `401 Unauthorized`:** `{ "detail": "Not authenticated." }`

---

## Ingestion

### `POST /repos/ingest`

Start ingesting a repository into the vector store. Runs in the background.

Private repos require a login; the clone uses the signed-in user's token.

**Request body:**
```json
{ "repo_url": "https://github.com/owner/repo" }
```

**Response `200 OK`:**
```json
{
  "repo_id": "owner__repo",
  "message": "Ingestion started. Check status with GET /{repo_id}/status"
}
```

The `repo_id` is derived from the URL: `https://github.com/Heba2627/depi_final_project` → `heba2627__depi_final_project`.

> **Caveat:** id generation lowercases *and* replaces `-` with `_`, so `owner/a-b` and `owner/a_b` collide onto the same id and will overwrite each other. See item #5 in [`IMPROVEMENTS.md`](IMPROVEMENTS.md).

If the repo is already ingested and unchanged, this returns immediately without re-embedding.

---

### `GET /repos/{repo_id}/status`

**Response `200 OK`:**
```json
{
  "repo_id": "owner__repo",
  "url": "https://github.com/owner/repo",
  "status": "ready"
}
```

Status values: `processing`, `ready`, `error: <message>`.

---

### `POST /repos/{repo_id}/stop`

Cancel an in-flight ingestion and clean up its partial artifacts.

> **Caveat:** the stop signal lives in process memory, so after a restart this returns `404` for a repo still marked `processing` — and that repo can't be re-ingested until its row is cleared. See item #1 in [`IMPROVEMENTS.md`](IMPROVEMENTS.md).

---

### `GET /repos/`

List all ingested repos.

---

### `DELETE /repos/{repo_id}`

Delete a repo's ChromaDB collection, on-disk clone, registry row, and in-memory caches.

> **Caveat:** this does **not** cascade to the `insights`, `charts`, `docs`, or `sessions` tables — LLM-generated summaries of a deleted (possibly private) repo survive. See item #19 in [`IMPROVEMENTS.md`](IMPROVEMENTS.md).

---

## Chat

**All chat endpoints require a login** (`401` otherwise). Sessions are scoped to their owner.

### `POST /repos/chat/{repo_id}`

Send a message and wait for the full response.

**Request body:**
```json
{
  "message": "What does this project do?",
  "session_id": null,
  "provider": "openrouter",
  "model_name": null
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `message` | `string` | required | The user message |
| `session_id` | `string` or `null` | new UUID | Existing session to continue, or `null` to start one |
| `provider` | `string` | `"openrouter"` | `"groq"`, `"openrouter"`, or `"anthropic"` |
| `model_name` | `string` or `null` | provider default | Override the model |

**Response `200 OK`:**
```json
{
  "response": "This project is a codebase exploration tool...",
  "session_id": "a1b2c3d4-..."
}
```

---

### `POST /repos/chat/{repo_id}/stream`

Same body, but streams the response over SSE, including the agent's intermediate reasoning (this is what drives the "Thinking…" panel in the UI).

---

### `GET /repos/chat/{session_id}/history`

**Response `200 OK`:**
```json
{
  "session_id": "a1b2c3d4-...",
  "history": [
    { "role": "user", "content": "What does this project do?" },
    { "role": "assistant", "content": "This project is a codebase exploration tool..." }
  ]
}
```

> **Caveat:** history is persisted from the agent's *token-limited* memory window, not the full transcript, so turns past ~6000 tokens are permanently lost on save. See item #20 in [`IMPROVEMENTS.md`](IMPROVEMENTS.md).

**Response `404`:** returned both when the session doesn't exist and when it belongs to another user.

---

### `GET /repos/chat/{repo_id}/sessions`

List the logged-in user's chat sessions for this repo. Only ever returns the caller's own sessions.

---

### `DELETE /repos/chat/{session_id}`

**Response `200 OK`:** `{ "message": "Session a1b2c3d4-... deleted successfully." }`

---

## Insights

### `POST /repos/{repo_id}/insight`

Kick off insight generation in the background. An agent explores the repo and returns purpose, tech stack, architecture, and key files.

**Request body (optional):**
```json
{ "provider": "openrouter", "model_name": null }
```

Requires the repo to be `ready` (`409` otherwise).

### `GET /repos/{repo_id}/insight`

**Response `200 OK`:**
```json
{
  "repo_id": "owner__repo",
  "status": "ready",
  "last_updated": "2026-07-13 14:45:04",
  "insight": {
    "purpose": "...",
    "tech_stack": ["FastAPI", "React"],
    "architecture": "...",
    "key_files": ["api/main.py"]
  }
}
```

Status values: `processing`, `ready`, `error: <message>`. `insight` is `null` unless `status` is `ready`.

---

## Charts

### `POST /repos/{repo_id}/charts`
### `GET /repos/{repo_id}/charts`

Same request/response shape as insights. Produces the language breakdown, dependency graph, contributor histogram, health score, and codebase analytics (LOC, TODOs, complex/hot files, test coverage estimate).

---

## Documentation

### `POST /repos/{repo_id}/docs`
### `GET /repos/{repo_id}/docs`

Same request/response shape. Produces function/class summaries and an API endpoint explorer.

---

## Known issue: jobs that never start

`POST` on `/insight`, `/charts`, or `/docs` short-circuits when a row already exists with status `processing` or `ready` — it returns `200 OK` and dispatches nothing.

Because background jobs live in process memory, a crash or redeploy mid-job leaves the row stuck at `processing` **permanently**, and nothing ever resets it. From then on the `POST` is a silent no-op and the `GET` reports `processing` forever, with zero LLM calls. It looks exactly like a rate limit.

Workaround: delete the stuck row. Tracked as item #1 in [`IMPROVEMENTS.md`](IMPROVEMENTS.md).

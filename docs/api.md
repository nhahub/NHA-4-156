# Repo Illustrator API

Base URL: `http://localhost:8000/repos`

## Ingestion

### `POST /ingest`

Start ingesting a repository into the vector store. Runs in the background.

**Request body:**
```json
{
  "repo_url": "https://github.com/owner/repo"
}
```

**Response `202 Accepted`:**
```json
{
  "repo_id": "owner__repo",
  "message": "Ingestion started. Check status with GET /{repo_id}/status"
}
```

The `repo_id` is auto-generated from the URL (e.g. `https://github.com/Heba2627/depi_final_project_testing` → `heba2627__depi_final_project_testing`).

---

### `GET /{repo_id}/status`

Check the ingestion status of a repository.

**Response `200 OK`:**
```json
{
  "repo_id": "owner__repo",
  "url": "https://github.com/owner/repo",
  "status": "ready"
}
```

Possible status values: `processing`, `ready`, `error: <message>`.

**Response `404 Not Found`:**
```json
{
  "detail": "Repository ID not found"
}
```

---

## Chat

### `POST /chat/{repo_id}`

Send a message to the chatbot for a specific repository.

**Request body:**
```json
{
  "message": "What does this project do?",
  "session_id": null,
  "provider": "groq",
  "model_name": null
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `message` | `string` | required | The user message |
| `session_id` | `string` or `null` | auto-generated UUID | Existing session to continue, or `null` for a new session |
| `provider` | `string` | `"groq"` | LLM provider: `"groq"` or `"openrouter"` |
| `model_name` | `string` or `null` | provider default | Override the default model for the provider |

**Response `200 OK`:**
```json
{
  "response": "This project is a codebase exploration tool...",
  "session_id": "a1b2c3d4-..."
}
```

**Response `404`:**
```json
{
  "detail": "Repo metadata not found. Ingest the repo first."
}
```

---

### `DELETE /chat/{session_id}`

Delete a chat session and its history.

**Response `200 OK`:**
```json
{
  "message": "Session a1b2c3d4-... deleted successfully."
}
```

**Response `404 Not Found`:**
```json
{
  "detail": "Session not found"
}
```

---

### `GET /chat/{session_id}/history`

Retrieve the full message history for a session.

**Response `200 OK`:**
```json
{
  "session_id": "a1b2c3d4-...",
  "history": [
    {"role": "user", "content": "What does this project do?"},
    {"role": "assistant", "content": "This project is a codebase exploration tool..."}
  ]
}
```

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Every request sends the session cookie (credentials: "include") so the
 * backend can authorize the user. Without this, CORS + cookies silently break
 * auth. The frontend teammate can extend `apiFetch` if they need global
 * error/loading handling.
 */
async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      // CSRF: state-changing requests carry a custom header so a bare <form>
      // POST from another origin is rejected by the same-origin policy.
      "X-Requested-With": "XMLHttpRequest",
      ...(options.headers || {}),
    },
  });
  return res;
}

export class ApiAuthError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
    this.name = "ApiAuthError";
  }
}

async function throwIfAuth(res, defaultMsg) {
  if (res.status === 401 || res.status === 403) {
    let detail = defaultMsg;
    try {
      const body = await res.json();
      detail = body.detail || defaultMsg;
    } catch {
      /* response body wasn't JSON — fall back to default message */
    }
    throw new ApiAuthError(res.status, detail);
  }
  if (!res.ok) throw new Error(`${defaultMsg}: ${res.status}`);
  return res;
}


export async function startIngestion(repoUrl) {
  const res = await apiFetch(`/repos/ingest`, {
    method: "POST",
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  return throwIfAuth(res, "Ingestion request failed").then((r) => r.json());
}

export async function getRepoStatus(repoId) {
  const res = await apiFetch(`/repos/${repoId}/status`);
  return throwIfAuth(res, "Status check failed").then((r) => r.json());
}

export async function stopIngestion(repoId) {
  const res = await apiFetch(`/repos/${repoId}/stop`, { method: "POST" });
  return throwIfAuth(res, "Stop request failed").then((r) => r.json());
}

export async function assistRepo() {
  return null;
}

export async function startCharts(repoId) {
  const res = await apiFetch(`/repos/${repoId}/charts`, {
    method: "POST",
    body: JSON.stringify({ provider: "openrouter" }),
  });
  return throwIfAuth(res, "Charts request failed").then((r) => r.json());
}

export async function getCharts(repoId) {
  const res = await apiFetch(`/repos/${repoId}/charts`);
  return throwIfAuth(res, "Charts fetch failed").then((r) => r.json());
}

export async function startDocs(repoId) {
  const res = await apiFetch(`/repos/${repoId}/docs`, {
    method: "POST",
    body: JSON.stringify({ provider: "openrouter" }),
  });
  return throwIfAuth(res, "Docs request failed").then((r) => r.json());
}

export async function getDocs(repoId) {
  const res = await apiFetch(`/repos/${repoId}/docs`);
  return throwIfAuth(res, "Docs fetch failed").then((r) => r.json());
}

export async function streamChatMessage(repoId, message, sessionId, provider = "openrouter", onEvent) {
  const res = await apiFetch(`/repos/chat/${repoId}/stream`, {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId, provider }),
  });

  if (res.status === 401 || res.status === 403) {
    let detail = "Chat requires sign-in.";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* not JSON */
    }
    throw new ApiAuthError(res.status, detail);
  }
  if (!res.ok) throw new Error(`Stream request failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          onEvent(currentEvent, data);
        } catch {
          /* malformed SSE data line — skip */
        }
      } else if (line === "") {
        currentEvent = "message";
      }
    }
  }
}

export async function getChatHistory(sessionId) {
  const res = await apiFetch(`/repos/chat/${sessionId}/history`);
  return throwIfAuth(res, "History fetch failed").then((r) => r.json());
}

export async function deleteChatSession(sessionId) {
  const res = await apiFetch(`/repos/chat/${sessionId}`, { method: "DELETE" });
  return throwIfAuth(res, "Delete session failed").then((r) => r.json());
}

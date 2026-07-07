const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function startIngestion(repoUrl) {
  const res = await fetch(`${API_BASE}/repos/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  if (!res.ok) throw new Error(`Ingestion request failed: ${res.status}`);
  return res.json();
}

export async function getRepoStatus(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/status`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json();
}

export async function assistRepo(query) {
  return null; // for now bs
}

export async function startCharts(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/charts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: "groq" }),
  });
  if (!res.ok) throw new Error(`Charts request failed: ${res.status}`);
  return res.json();
}

export async function getCharts(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/charts`);
  if (!res.ok) throw new Error(`Charts fetch failed: ${res.status}`);
  return res.json();
}

export async function sendChatMessage(repoId, message, sessionId, provider = "groq") {
  const res = await fetch(`${API_BASE}/repos/chat/${repoId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, provider }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Chat request failed: ${res.status}`);
  }
  return res.json(); 
}

// Streams events from /chat/{repo_id}/stream (Server-Sent Events).
// Real event types yielded by chatbot.py's chat_stream():
//   "thinking"       -> data: {}                  (agent has started)
//   "thinking_delta" -> data: { text }             (raw ReAct reasoning, streamed live)
//   "tool_call"      -> data: { tool }             (agent is calling a tool)
//   "tool_result"    -> data: { text }             (truncated tool output)
//   "token"          -> data: { text }             (the final CLEANED answer, sent whole, not incremental)
//   "done"           -> data: {}                   (stream finished)
//   "error"          -> data: { text }              (something went wrong)
// onEvent is called as onEvent(type, data) for every event as it arrives.

export async function streamChatMessage(repoId, message, sessionId, provider = "groq", onEvent) {
  const res = await fetch(`${API_BASE}/repos/chat/${repoId}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, provider }),
  });

  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Stream request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const lines = rawEvent.split("\n");
      const eventLine = lines.find(l => l.startsWith("event:"));
      const dataLine = lines.find(l => l.startsWith("data:"));
      if (!dataLine) continue;

      const type = eventLine ? eventLine.replace("event:", "").trim() : "message";
      const raw = dataLine.replace("data:", "").trim();
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        data = raw;
      }

      onEvent?.(type, data);
    }
  }
}

export async function getChatHistory(sessionId) {
  const res = await fetch(`${API_BASE}/repos/chat/${sessionId}/history`);
  if (res.status === 404) return { session_id: sessionId, history: [] };
  if (!res.ok) throw new Error(`History fetch failed: ${res.status}`);
  return res.json();
}

export async function deleteChatSession(sessionId) {
  const res = await fetch(`${API_BASE}/repos/chat/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 404) {
    throw new Error(`Delete session failed: ${res.status}`);
  }
  return res.status === 404 ? null : res.json();
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";


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
  return null;
}

export async function startCharts(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/charts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: "openrouter" }),
  });
  if (!res.ok) throw new Error(`Charts request failed: ${res.status}`);
  return res.json();
}

export async function getCharts(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/charts`);
  if (!res.ok) throw new Error(`Charts fetch failed: ${res.status}`);
  return res.json();
}

export async function startDocs(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/docs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: "openrouter" }),
  });
  if (!res.ok) throw new Error(`Docs request failed: ${res.status}`);
  return res.json();
}

export async function getDocs(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/docs`);
  if (!res.ok) throw new Error(`Docs fetch failed: ${res.status}`);
  return res.json();
}

export async function streamChatMessage(repoId, message, sessionId, provider = "openrouter", onEvent) {
  const res = await fetch(`${API_BASE}/repos/chat/${repoId}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, provider }),
  });

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
        } catch {}
      } else if (line === "") {
        currentEvent = "message";
      }
    }
  }
}

export async function getChatHistory(sessionId) {
  const res = await fetch(`${API_BASE}/repos/chat/${sessionId}/history`);
  if (!res.ok) throw new Error(`History fetch failed: ${res.status}`);
  return res.json();
}

export async function deleteChatSession(sessionId) {
  const res = await fetch(`${API_BASE}/repos/chat/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Delete session failed: ${res.status}`);
  return res.json();
}

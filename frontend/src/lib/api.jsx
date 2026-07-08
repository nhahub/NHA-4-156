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

export async function startDocs(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/docs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: "groq" }),
  });
  if (!res.ok) throw new Error(`Docs request failed: ${res.status}`);
  return res.json();
}

export async function getDocs(repoId) {
  const res = await fetch(`${API_BASE}/repos/${repoId}/docs`);
  if (!res.ok) throw new Error(`Docs fetch failed: ${res.status}`);
  return res.json();
}
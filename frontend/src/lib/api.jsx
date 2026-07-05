const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function startIngestion(repoUrl) {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  if (!res.ok) throw new Error(`Ingestion request failed: ${res.status}`);
  return res.json();
}

export async function getRepoStatus(repoId) {
  const res = await fetch(`${API_BASE}/${repoId}/status`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json(); 
}


export async function assistRepo(query) {
    return null; //for now bs 
}
const STORAGE_PREFIX = "repo_illustrator_chat_session_";

// crypto.randomUUID() only exists in secure contexts (HTTPS or localhost).
// On plain HTTP deployments (like a raw IP address) it's undefined, so we
// fall back to a manual UUID v4 generator that works everywhere.
function generateUUID() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getSessionId(repoId) {
  const key = `${STORAGE_PREFIX}${repoId}`;
  let sessionId = localStorage.getItem(key);
  if (!sessionId) {
    sessionId = generateUUID();
    localStorage.setItem(key, sessionId);
  }
  return sessionId;
}

export function setSessionId(repoId, sessionId) {
  localStorage.setItem(`${STORAGE_PREFIX}${repoId}`, sessionId);
}

export function clearSessionId(repoId) {
  localStorage.removeItem(`${STORAGE_PREFIX}${repoId}`);
}

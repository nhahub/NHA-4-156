const STORAGE_PREFIX = "repo_illustrator_chat_session_";

export function getSessionId(repoId) {
  const key = `${STORAGE_PREFIX}${repoId}`;
  let sessionId = localStorage.getItem(key);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
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

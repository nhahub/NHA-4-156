"""GitHub OAuth + per-request authorization helpers.

Flow:
  - /auth/login     -> redirect browser to GitHub authorize URL (with state)
  - /auth/callback  -> exchange code for token, fetch profile, upsert user,
                       set signed session cookie with user_id
  - get_current_user(request) -> read user_id from session, load user row
  - require_repo_access(repo_id, user) -> public repos: always OK;
                       private repos: check repo_access row, else probe GitHub
                       with the user's token and cache the grant.

GitHub tokens are Fernet-encrypted in the users table and never sent to the
browser. The /auth/me endpoint exposes only profile fields.
"""
import os
import secrets
from typing import Optional

import httpx
from fastapi import HTTPException, Request

from api import database
from api.security import encrypt_token, decrypt_token


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API = "https://api.github.com/user"

# Scopes we request. `repo` covers private repo read+write (classic OAuth App
# scope — there's no read-only variant). `read:user` for profile.
OAUTH_SCOPES = "read:user repo"

# Used by the frontend to know where to send the user.
OAUTH_REDIRECT_PATH = "/auth/callback"


def _oauth_client_id() -> str:
    v = os.getenv("GITHUB_OAUTH_CLIENT_ID")
    if not v:
        raise RuntimeError("GITHUB_OAUTH_CLIENT_ID env var is not set.")
    return v


def _oauth_client_secret() -> str:
    v = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
    if not v:
        raise RuntimeError("GITHUB_OAUTH_CLIENT_SECRET env var is not set.")
    return v


def _frontend_origin() -> str:
    """Where to send the browser after login/logout. Defaults to same-origin
    (relative '/') which is correct for the Docker single-port deployment.
    Set FRONTEND_ORIGIN=http://localhost:5173 for local Vite dev."""
    return os.getenv("FRONTEND_ORIGIN", "").rstrip("/")


def build_authorize_url(redirect_uri: str, state: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": _oauth_client_id(),
        "redirect_uri": redirect_uri,
        "scope": OAUTH_SCOPES,
        "state": state,
        "allow_signup": "true",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


def resolve_callback_url(request: Request) -> str:
    """The full URL GitHub redirects back to after authorization.

    In local dev, FRONTEND_ORIGIN points to the Vite dev server (e.g.
    http://localhost:5173) so the callback hits the browser origin (not the
    backend port 8000, which the browser can't reach through the Vite proxy
    on redirect). In production (Docker single-port), FRONTEND_ORIGIN is unset
    and we build from the request — same-origin so it just works.
    """
    origin = _frontend_origin()
    if origin:
        return f"{origin}{OAUTH_REDIRECT_PATH}"
    # No explicit frontend origin: build from the incoming request.
    # Prefer X-Forwarded-Proto/Host if a reverse proxy is in front.
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}{OAUTH_REDIRECT_PATH}"


async def exchange_code_for_token(code: str, callback_url: str) -> dict:
    """Exchange the OAuth code for an access token. Returns the token response
    dict from GitHub (access_token, token_type, scope)."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": _oauth_client_id(),
                "client_secret": _oauth_client_secret(),
                "code": code,
                "redirect_uri": callback_url,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"GitHub token exchange failed: {resp.status_code}")
    data = resp.json()
    if "access_token" not in data:
        raise HTTPException(status_code=400, detail=f"GitHub did not return an access_token: {data.get('error_description', data)}")
    return data


async def fetch_github_user(access_token: str) -> dict:
    """Fetch the authenticated user's profile from the GitHub API."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            GITHUB_USER_API,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"GitHub user fetch failed: {resp.status_code}")
    return resp.json()


async def probe_repo_access(owner: str, repo: str, access_token: Optional[str]) -> tuple[bool, bool, int]:
    """Probe GitHub for a repo. Returns (exists_and_accessible, is_private, status_code).
    Uses the given token if provided, else anonymous. A 404 means either the
    repo doesn't exist or the token can't see it (private). A 401 means the
    token is invalid/expired."""
    headers = {"Accept": "application/vnd.github+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return True, bool(data.get("private", False)), 200
    return False, False, resp.status_code


def parse_owner_repo(repo_url: str) -> tuple[str, str] | None:
    import re
    from urllib.parse import urlparse
    url = repo_url.strip()
    ssh = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if ssh:
        return ssh.group(1), ssh.group(2)
    parsed = urlparse(url)
    if "github.com" not in (parsed.netloc or ""):
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return None
    return parts[0], parts[1].replace(".git", "")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

class User:
    """Lightweight user object exposed to routes. `github_token` is decrypted
    on demand (not stored in plaintext on the instance beyond the request)."""
    def __init__(self, row: dict):
        self.id = row["id"]
        self.login = row["login"]
        self.name = row.get("name")
        self.email = row.get("email")
        self.avatar_url = row.get("avatar_url")
        self.html_url = row.get("html_url")
        self._token_enc = row.get("github_token_enc")
        self.token_scopes = row.get("token_scopes") or ""

    @property
    def github_token(self) -> str:
        return decrypt_token(self._token_enc) if self._token_enc else ""

    def public_profile(self) -> dict:
        return {
            "id": self.id,
            "login": self.login,
            "name": self.name,
            "email": self.email,
            "avatar_url": self.avatar_url,
            "html_url": self.html_url,
        }


def get_current_user(request: Request) -> User | None:
    """Optional dependency: returns the logged-in user or None. Does not raise."""
    user_id = request.session.get("user_id") if hasattr(request, "session") else None
    if not user_id:
        return None
    row = database.get_user_by_id(user_id)
    if not row:
        return None
    return User(row)


def require_user(request: Request) -> User:
    """Strict dependency: raises 401 if not logged in."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required. Sign in with GitHub.")
    return user


async def require_repo_access(repo_id: str, user: User | None) -> None:
    """Authorize access to a repo. Raises 404 if the repo isn't registered,
    403 if it's private and the user lacks access.

    For private repos without a cached grant, probes GitHub with the user's
    token; if the user is a collaborator, inserts a repo_access row so future
    checks are a local DB hit.
    """
    repo = database.get_repo_status(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found. Ingest it first.")

    visibility = repo.get("visibility") or "public"
    if visibility == "public":
        return

    # Private repo: user must be logged in.
    if user is None:
        raise HTTPException(status_code=401, detail="This is a private repository. Sign in with GitHub to access it.")

    # Cached grant?
    if database.has_repo_access(repo_id, user.id):
        return

    # Owner implicitly has access (should already have a row, but be safe).
    if repo.get("owner_user_id") == user.id:
        database.grant_repo_access(repo_id, user.id, "owner")
        return

    # Probe GitHub to see if this user is a collaborator.
    owner_repo = parse_owner_repo(repo.get("url", ""))
    if not owner_repo:
        raise HTTPException(status_code=403, detail="No access to this private repository.")
    owner, name = owner_repo
    token = user.github_token
    if not token:
        raise HTTPException(status_code=401, detail="Your GitHub session has expired. Please sign in again.")

    accessible, is_private, status = await probe_repo_access(owner, name, token)
    if not accessible:
        if status == 401:
            # Token is actually invalid/expired — clear it so user re-logins.
            database.clear_user_token(user.id)
            raise HTTPException(status_code=401, detail="Your GitHub token has expired. Please sign in again.")
        # 404 or other: repo doesn't exist or user isn't a collaborator.
        # Don't destroy a valid token.
        raise HTTPException(status_code=403, detail="You don't have access to this private repository, or the repo doesn't exist.")
    # Accessible + private (we already know it's private from the registry).
    database.grant_repo_access(repo_id, user.id, "collaborator")
    return


def require_session_owner(session_id: str, user: User) -> None:
    """For chat session endpoints: the session must belong to the logged-in user."""
    meta = database.get_session_meta(session_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if meta.get("user_id") != user.id:
        # Don't leak existence — return 404.
        raise HTTPException(status_code=404, detail="Session not found.")


# ---------------------------------------------------------------------------
# OAuth handshake helpers (used by the /auth routes)
# ---------------------------------------------------------------------------

async def complete_oauth_login(code: str, callback_url: str) -> dict:
    """Exchange code -> token -> profile -> upsert user. Returns the user row."""
    token_resp = await exchange_code_for_token(code, callback_url)
    access_token = token_resp["access_token"]
    scopes = token_resp.get("scope", "")
    profile = await fetch_github_user(access_token)
    enc = encrypt_token(access_token)
    return database.upsert_user(profile, enc, scopes)


def sanitize_next_path(next_path: str | None) -> str:
    """Validate a caller-supplied post-login path. Only same-site absolute paths
    are allowed — anything else (absolute URL, protocol-relative '//evil.com',
    backslash variants) is an open-redirect vector and falls back to '/'."""
    if not next_path or not next_path.startswith("/"):
        return "/"
    if next_path.startswith("//") or next_path.startswith("/\\"):
        return "/"
    return next_path


def post_login_redirect_target(next_path: str | None = None) -> str:
    """Where to send the browser after a successful login. Returns the user to
    the page they started from, defaulting to '/'."""
    path = sanitize_next_path(next_path)
    origin = _frontend_origin()
    return f"{origin}{path}" if origin else path

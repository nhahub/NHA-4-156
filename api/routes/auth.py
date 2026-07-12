"""GitHub OAuth routes: /auth/login, /auth/callback, /auth/logout, /auth/me."""
import secrets

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from api import auth as authmod
from api import database

router = APIRouter()


@router.get("/auth/login")
async def login(request: Request, next: str = ""):
    """Redirect the browser to GitHub's authorize page. Stores a random `state`
    in the session to prevent OAuth login CSRF.

    `next` is the in-app path to return to after login (e.g. the repo page the
    user was viewing). It rides in the session rather than the GitHub redirect
    URI, because GitHub requires the callback URL to match the registered one
    exactly — no extra query params allowed.
    """
    if not hasattr(request, "session"):
        raise HTTPException(status_code=500, detail="Session middleware is not configured.")
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    request.session["post_login_next"] = authmod.sanitize_next_path(next)
    # Where GitHub should send the browser back. Built from the request so it
    # works regardless of which host/IP the app is served on.
    callback_url = authmod.resolve_callback_url(request)
    authorize_url = authmod.build_authorize_url(callback_url, state)
    return RedirectResponse(url=authorize_url, status_code=302)


@router.get("/auth/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    """GitHub redirects here with ?code=...&state=... Validate state, exchange
    code for a token, upsert the user, set the session cookie, redirect home."""
    if error:
        raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {error} — {error_description}")

    saved_state = request.session.get("oauth_state") if hasattr(request, "session") else None
    if not saved_state or saved_state != state:
        raise HTTPException(status_code=400, detail="OAuth state mismatch. Please try signing in again.")

    # Clear the state so it can't be reused.
    request.session.pop("oauth_state", None)
    next_path = request.session.pop("post_login_next", "/")

    if not code:
        raise HTTPException(status_code=400, detail="GitHub did not return an authorization code.")

    callback_url = authmod.resolve_callback_url(request)
    user_row = await authmod.complete_oauth_login(code, callback_url)
    request.session["user_id"] = user_row["id"]
    return RedirectResponse(url=authmod.post_login_redirect_target(next_path), status_code=302)


@router.post("/auth/logout")
async def logout(request: Request):
    """Clear the app session. The GitHub token stays encrypted in the DB for
    next login (it's tied to the user's GitHub account, not the session)."""
    if hasattr(request, "session"):
        request.session.clear()
    return JSONResponse({"message": "Logged out."})


@router.get("/auth/me")
async def me(request: Request):
    """Return the logged-in user's public profile, or 401 if not logged in."""
    user = authmod.get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user.public_profile()

import json
import sqlite3

DB_FILE = "repo_illustrator.db"

def _column_exists(conn, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        # Registry Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registry (
                repo_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                collection_name TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Sessions Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                history TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insights Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                repo_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                insight_json TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # added Charts Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS charts (
                repo_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                chart_json TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        #added Docs Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                repo_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                docs_json TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Users table (GitHub OAuth). github_token_enc is Fernet-encrypted.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                login TEXT UNIQUE NOT NULL,
                name TEXT,
                email TEXT,
                avatar_url TEXT,
                html_url TEXT,
                github_token_enc BLOB,
                token_scopes TEXT,
                last_validated TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Repo access grants. A row here means a user may access a repo.
        # granted_via: 'owner' (ingested by them), 'collaborator' (verified via GitHub API)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repo_access (
                repo_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                granted_via TEXT NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (repo_id, user_id)
            )
        """)

        # --- migrations for existing installs ---
        if not _column_exists(conn, "registry", "visibility"):
            conn.execute("ALTER TABLE registry ADD COLUMN visibility TEXT DEFAULT 'public'")
        if not _column_exists(conn, "registry", "owner_user_id"):
            conn.execute("ALTER TABLE registry ADD COLUMN owner_user_id INTEGER")
        if not _column_exists(conn, "sessions", "user_id"):
            conn.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
        if not _column_exists(conn, "sessions", "repo_id"):
            conn.execute("ALTER TABLE sessions ADD COLUMN repo_id TEXT")


#registry
def save_repo_status(repo_id: str, url: str, status: str, collection_name: str = None):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO registry (repo_id, url, status, collection_name, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(repo_id) DO UPDATE SET 
                status=excluded.status,
                collection_name=COALESCE(excluded.collection_name, registry.collection_name),
                last_updated=CURRENT_TIMESTAMP
        """, (repo_id, url, status, collection_name))

def get_repo_status(repo_id: str) -> dict:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT url, status, collection_name, visibility, owner_user_id FROM registry WHERE repo_id = ?", (repo_id,))
        row = cursor.fetchone()
        if row:
            return {"url": row[0], "status": row[1], "collection_name": row[2], "visibility": row[3] or "public", "owner_user_id": row[4]}
        return None

def get_all_repos() -> list:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT repo_id, url, status, collection_name, visibility, owner_user_id FROM registry")
        rows = cursor.fetchall()
        repos = []
        for row in rows:
            repos.append({"repo_id": row[0], "url": row[1], "status": row[2], "collection_name": row[3], "visibility": row[4] or "public", "owner_user_id": row[5]})
        return repos

def list_visible_repos(user_id: int | None) -> list:
    """Return repos the given user can see: all public + private repos they
    have a repo_access row for. If user_id is None, only public repos."""
    with sqlite3.connect(DB_FILE) as conn:
        if user_id is None:
            cursor = conn.execute(
                "SELECT repo_id, url, status, collection_name, visibility, owner_user_id FROM registry WHERE visibility = 'public'"
            )
        else:
            cursor = conn.execute(
                """SELECT r.repo_id, r.url, r.status, r.collection_name, r.visibility, r.owner_user_id
                   FROM registry r
                   LEFT JOIN repo_access a ON a.repo_id = r.repo_id AND a.user_id = ?
                   WHERE r.visibility = 'public' OR a.user_id IS NOT NULL""",
                (user_id,)
            )
        rows = cursor.fetchall()
        repos = []
        for row in rows:
            repos.append({"repo_id": row[0], "url": row[1], "status": row[2], "collection_name": row[3], "visibility": row[4] or "public", "owner_user_id": row[5]})
        return repos

def save_repo_visibility(repo_id: str, visibility: str, owner_user_id: int | None = None):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "UPDATE registry SET visibility = ?, owner_user_id = ? WHERE repo_id = ?",
            (visibility, owner_user_id, repo_id)
        )

def delete_repo_registry(repo_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM registry WHERE repo_id = ?", (repo_id,))
        conn.execute("DELETE FROM repo_access WHERE repo_id = ?", (repo_id,))

#sessions

def save_session(session_id: str, history: list, user_id: int | None = None, repo_id: str | None = None):
    # Convert LlamaIndex ChatMessage objects to JSON dicts
    history_json = json.dumps([{"role": msg.role.value, "content": msg.content} for msg in history])
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO sessions (session_id, history, user_id, repo_id, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                history=excluded.history,
                user_id=COALESCE(excluded.user_id, sessions.user_id),
                repo_id=COALESCE(excluded.repo_id, sessions.repo_id),
                last_updated=CURRENT_TIMESTAMP
        """, (session_id, history_json, user_id, repo_id))

def get_session(session_id: str) -> list:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT history FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            # Returns the raw dict list, you'll convert these back to ChatMessage in the router
            return json.loads(row[0])
        return None

def get_session_meta(session_id: str) -> dict | None:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT user_id, repo_id FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            return {"user_id": row[0], "repo_id": row[1]}
        return None

def list_user_sessions(user_id: int, repo_id: str | None = None) -> list:
    with sqlite3.connect(DB_FILE) as conn:
        if repo_id:
            cursor = conn.execute(
                "SELECT session_id, repo_id, last_updated FROM sessions WHERE user_id = ? AND repo_id = ? ORDER BY last_updated DESC",
                (user_id, repo_id)
            )
        else:
            cursor = conn.execute(
                "SELECT session_id, repo_id, last_updated FROM sessions WHERE user_id = ? ORDER BY last_updated DESC",
                (user_id,)
            )
        return [{"session_id": r[0], "repo_id": r[1], "last_updated": r[2]} for r in cursor.fetchall()]

def delete_session(session_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

# users

def upsert_user(profile: dict, github_token_enc: bytes, token_scopes: str = "") -> dict:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO users (id, login, name, email, avatar_url, html_url, github_token_enc, token_scopes, last_validated, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                login=excluded.login,
                name=excluded.name,
                email=excluded.email,
                avatar_url=excluded.avatar_url,
                html_url=excluded.html_url,
                github_token_enc=excluded.github_token_enc,
                token_scopes=excluded.token_scopes,
                last_validated=CURRENT_TIMESTAMP,
                last_login=CURRENT_TIMESTAMP
        """, (
            profile.get("id"),
            profile.get("login"),
            profile.get("name"),
            profile.get("email"),
            profile.get("avatar_url"),
            profile.get("html_url"),
            github_token_enc,
            token_scopes,
        ))
    return get_user_by_id(profile["id"])

def get_user_by_id(user_id: int) -> dict | None:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT id, login, name, email, avatar_url, html_url, github_token_enc, token_scopes FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"id": row[0], "login": row[1], "name": row[2], "email": row[3], "avatar_url": row[4], "html_url": row[5], "github_token_enc": row[6], "token_scopes": row[7]}
        return None

def get_user_by_login(login: str) -> dict | None:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT id, login, name, email, avatar_url, html_url, github_token_enc, token_scopes FROM users WHERE login = ?",
            (login,)
        )
        row = cursor.fetchone()
        if row:
            return {"id": row[0], "login": row[1], "name": row[2], "email": row[3], "avatar_url": row[4], "html_url": row[5], "github_token_enc": row[6], "token_scopes": row[7]}
        return None

def clear_user_token(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE users SET github_token_enc = NULL, last_validated = NULL WHERE id = ?", (user_id,))

# repo_access

def grant_repo_access(repo_id: str, user_id: int, granted_via: str = "collaborator"):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO repo_access (repo_id, user_id, granted_via, granted_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(repo_id, user_id) DO NOTHING
        """, (repo_id, user_id, granted_via))

def has_repo_access(repo_id: str, user_id: int) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM repo_access WHERE repo_id = ? AND user_id = ?",
            (repo_id, user_id)
        )
        return cursor.fetchone() is not None

def list_repo_access_users(repo_id: str) -> list:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT user_id, granted_via, granted_at FROM repo_access WHERE repo_id = ?",
            (repo_id,)
        )
        return [{"user_id": r[0], "granted_via": r[1], "granted_at": r[2]} for r in cursor.fetchall()]

#insights

def save_insight_status(repo_id: str, status: str, insight_json: str = None):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO insights (repo_id, status, insight_json, last_updated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(repo_id) DO UPDATE SET
                status=excluded.status,
                insight_json=COALESCE(excluded.insight_json, insights.insight_json),
                last_updated=CURRENT_TIMESTAMP
        """, (repo_id, status, insight_json))

def get_repo_insight(repo_id: str) -> dict:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT status, insight_json, last_updated FROM insights WHERE repo_id = ?", (repo_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"status": row[0], "insight_json": row[1], "last_updated": row[2]}
        return None

def invalidate_repo_insight(repo_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM insights WHERE repo_id = ?", (repo_id,))
        
# charts saving and retrieving functions
def save_chart_status(repo_id: str, status: str, chart_json: str = None):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO charts (repo_id, status, chart_json, last_updated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(repo_id) DO UPDATE SET
                status=excluded.status,
                chart_json=COALESCE(excluded.chart_json, charts.chart_json),
                last_updated=CURRENT_TIMESTAMP
        """, (repo_id, status, chart_json))

def get_repo_chart(repo_id: str) -> dict:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT status, chart_json, last_updated FROM charts WHERE repo_id = ?", (repo_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"status": row[0], "chart_json": row[1], "last_updated": row[2]}
        return None

def invalidate_repo_chart(repo_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM charts WHERE repo_id = ?", (repo_id,))

# docs

def save_docs_status(repo_id: str, status: str, docs_json: str = None):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO docs (repo_id, status, docs_json, last_updated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(repo_id) DO UPDATE SET
                status=excluded.status,
                docs_json=COALESCE(excluded.docs_json, docs.docs_json),
                last_updated=CURRENT_TIMESTAMP
        """, (repo_id, status, docs_json))

def get_repo_docs(repo_id: str) -> dict:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT status, docs_json, last_updated FROM docs WHERE repo_id = ?", (repo_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"status": row[0], "docs_json": row[1], "last_updated": row[2]}
        return None

def invalidate_repo_docs(repo_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM docs WHERE repo_id = ?", (repo_id,))
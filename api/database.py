import json
import sqlite3

DB_FILE = "repo_illustrator.db"

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
        cursor = conn.execute("SELECT url, status, collection_name FROM registry WHERE repo_id = ?", (repo_id,))
        row = cursor.fetchone()
        if row:
            return {"url": row[0], "status": row[1], "collection_name": row[2]}
        return None

def get_all_repos() -> list:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT repo_id, url, status, collection_name FROM registry")
        rows = cursor.fetchall()
        repos = []
        for row in rows:
            repos.append({"repo_id": row[0], "url": row[1], "status": row[2], "collection_name": row[3]})
        return repos

def delete_repo_registry(repo_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM registry WHERE repo_id = ?", (repo_id,))

#sessions

def save_session(session_id: str, history: list):
    # Convert LlamaIndex ChatMessage objects to JSON dicts
    history_json = json.dumps([{"role": msg.role.value, "content": msg.content} for msg in history])
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO sessions (session_id, history, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET 
                history=excluded.history, 
                last_updated=CURRENT_TIMESTAMP
        """, (session_id, history_json))

def get_session(session_id: str) -> list:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT history FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            # Returns the raw dict list, you'll convert these back to ChatMessage in the router
            return json.loads(row[0]) 
        return None

def delete_session(session_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

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
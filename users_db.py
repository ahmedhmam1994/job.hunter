"""users_db.py — Multi-user storage: users, API keys, saved queries."""
import sqlite3, os, secrets

DATA_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "users.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT UNIQUE,
            api_key TEXT UNIQUE NOT NULL,
            cv_path TEXT,
            min_score INTEGER DEFAULT 60,
            device_token TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS saved_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            query TEXT NOT NULL,
            sites TEXT NOT NULL,
            remote_only INTEGER DEFAULT 0,
            interval_minutes INTEGER DEFAULT 30,
            last_run TIMESTAMP);
    """)
    return conn


# ---------- Users ----------
def create_user(name: str, email: str) -> str:
    api_key = "jh_" + secrets.token_hex(16)
    with get_conn() as c:
        c.execute("INSERT OR IGNORE INTO users (name, email, api_key) "
                  "VALUES (?, ?, ?)", (name, email.lower(), api_key))
        row = c.execute("SELECT api_key FROM users WHERE email=?",
                        (email.lower(),)).fetchone()
    return row[0]


def get_user_by_key(api_key: str) -> dict | None:
    with get_conn() as c:
        r = c.execute("""SELECT id, name, email, cv_path, min_score,
                                device_token FROM users WHERE api_key=?""",
                      (api_key,)).fetchone()
    if not r:
        return None
    keys = ("id", "name", "email", "cv_path", "min_score", "device_token")
    return dict(zip(keys, r))


def _key_of(user_id: int) -> str:
    with get_conn() as c:
        return c.execute("SELECT api_key FROM users WHERE id=?",
                         (user_id,)).fetchone()[0]


def update_user(api_key: str, **fields):
    allowed = {"cv_path", "min_score", "device_token"}
    sets = ", ".join(f"{k}=?" for k in fields if k in allowed)
    vals = [v for k, v in fields.items() if k in allowed] + [api_key]
    with get_conn() as c:
        c.execute(f"UPDATE users SET {sets} WHERE api_key=?", vals)


def set_device_token(api_key: str, token: str):
    update_user(api_key, device_token=token)


# ---------- Saved Queries ----------
def add_query(api_key: str, query: str, sites: list[str],
              remote_only=False, interval_minutes=30):
    user = get_user_by_key(api_key)
    with get_conn() as c:
        c.execute("""INSERT INTO saved_queries
                     (user_id, query, sites, remote_only, interval_minutes)
                     VALUES (?, ?, ?, ?, ?)""",
                  (user["id"], query, ",".join(sites),
                   int(remote_only), interval_minutes))


def remove_query(api_key: str, query_id: int):
    user = get_user_by_key(api_key)
    with get_conn() as c:
        c.execute("DELETE FROM saved_queries WHERE id=? AND user_id=?",
                  (query_id, user["id"]))


def my_queries(api_key: str) -> list[dict]:
    user = get_user_by_key(api_key)
    with get_conn() as c:
        rows = c.execute("""SELECT id, query, sites, remote_only,
                            interval_minutes, last_run
                            FROM saved_queries WHERE user_id=?
                            ORDER BY id""", (user["id"],)).fetchall()
    return [dict(zip(("id", "query", "sites", "remote_only",
                      "interval_minutes", "last_run"), r))
            | {"sites": r[2].split(",")} for r in rows]


# ---------- Scheduler helpers ----------
def due_queries() -> list[dict]:
    with get_conn() as c:
        rows = c.execute("""
            SELECT q.id, u.id AS uid, u.api_key, u.device_token,
                   u.cv_path, u.min_score,
                   q.query, q.sites, q.remote_only, q.interval_minutes
            FROM saved_queries q JOIN users u ON u.id = q.user_id
            WHERE u.device_token IS NOT NULL AND u.is_active = 1
              AND (q.last_run IS NULL OR
                   datetime('now', '-' || q.interval_minutes || ' minutes')
                       >= q.last_run)
        """).fetchall()
    keys = ("qid", "uid", "api_key", "device_token", "cv_path",
            "min_score", "query", "sites", "remote_only", "interval_minutes")
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        d["sites"] = d["sites"].split(",")
        out.append(d)
    return out


def mark_query_ran(qid: int):
    with get_conn() as c:
        c.execute("UPDATE saved_queries SET last_run=datetime('now') WHERE id=?", (qid,))


# ---------- Admin functions ----------
def all_users() -> list[dict]:
    with get_conn() as c:
        rows = c.execute("""
            SELECT u.id, u.name, u.email, u.is_active, u.min_score,
                   u.created_at,
                   (SELECT COUNT(*) FROM saved_queries q WHERE q.user_id=u.id) AS queries,
                   (u.device_token IS NOT NULL) AS has_device
            FROM users u ORDER BY u.id""").fetchall()
    keys = ("id", "name", "email", "is_active", "min_score",
            "created_at", "queries", "has_device")
    return [dict(zip(keys, r)) for r in rows]


def set_user_active(user_id: int, active: bool):
    with get_conn() as c:
        c.execute("UPDATE users SET is_active=? WHERE id=?", (int(active), user_id))


def update_user_by_id(user_id: int, min_score=None):
    if min_score is not None:
        with get_conn() as c:
            c.execute("UPDATE users SET min_score=? WHERE id=?", (min_score, user_id))


def delete_user(user_id: int):
    with get_conn() as c:
        c.execute("DELETE FROM saved_queries WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM users WHERE id=?", (user_id,))


def all_device_tokens() -> list[tuple]:
    with get_conn() as c:
        return c.execute("""SELECT device_token, name FROM users
                            WHERE device_token IS NOT NULL AND is_active=1"""
                         ).fetchall()


def platform_stats() -> dict:
    with get_conn() as c:
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = c.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0]
        queries = c.execute("SELECT COUNT(*) FROM saved_queries").fetchone()[0]
    return {"users": {"total": total, "active": active,
                      "disabled": total - active},
            "saved_queries": queries}

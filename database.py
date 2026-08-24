"""database.py — SQLite storage: favorites, seen jobs, applications."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "job_hunter.db")

STATUSES = ["Applied", "Follow-up sent", "Interview", "Offer", "Rejected", "Ghosted"]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS favorites (
            link TEXT PRIMARY KEY,
            title TEXT, company TEXT, location TEXT,
            site TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS seen (
            link TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE, title TEXT, company TEXT, site TEXT,
            status TEXT DEFAULT 'Applied',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            followup_at TIMESTAMP DEFAULT (datetime('now', '+7 days')),
            notes TEXT DEFAULT '');
    """)
    return conn


# ---------- Favorites ----------
def toggle_favorite(job: dict) -> bool:
    with get_conn() as c:
        exists = c.execute("SELECT 1 FROM favorites WHERE link=?",
                           (job["link"],)).fetchone()
        if exists:
            c.execute("DELETE FROM favorites WHERE link=?", (job["link"],))
            return False
        c.execute("INSERT INTO favorites (link,title,company,location,site) "
                  "VALUES (?,?,?,?,?)",
                  (job["link"], job["title"], job["company"],
                   job["location"], job["site"]))
        return True


def all_favorites() -> list[dict]:
    with get_conn() as c:
        rows = c.execute("SELECT * FROM favorites ORDER BY added_at DESC").fetchall()
    return [dict(r) for r in rows]


# ---------- Seen (for monitor dedup) ----------
def is_seen(link: str) -> bool:
    with get_conn() as c:
        return c.execute("SELECT 1 FROM seen WHERE link=?", (link,)).fetchone() is not None


def mark_seen_single(link: str):
    with get_conn() as c:
        c.execute("INSERT OR IGNORE INTO seen VALUES (?)", (link,))


def filter_new(jobs: list[dict]) -> list[dict]:
    new = [j for j in jobs if not is_seen(j["link"])]
    for j in new:
        mark_seen_single(j["link"])
    return new


# ---------- Applications tracker ----------
def add_application(job: dict, status="Applied") -> bool:
    try:
        with get_conn() as c:
            c.execute("""INSERT INTO applications
                         (link, title, company, site, status) VALUES (?,?,?,?,?)""",
                      (job["link"], job["title"], job["company"],
                       job.get("site", ""), status))
        return True
    except sqlite3.IntegrityError:      # already tracked
        return False


def update_status(link: str, status: str):
    with get_conn() as c:
        c.execute("UPDATE applications SET status=? WHERE link=?", (status, link))


def update_notes(link: str, notes: str):
    with get_conn() as c:
        c.execute("UPDATE applications SET notes=? WHERE link=?", (notes, link))


def all_applications() -> list[tuple]:
    with get_conn() as c:
        return c.execute("""SELECT id, title, company, site, status,
                                   applied_at, followup_at, link, notes
                            FROM applications ORDER BY applied_at DESC""").fetchall()


def due_followups() -> list[dict]:
    with get_conn() as c:
        rows = c.execute("""SELECT link, title, company FROM applications
                            WHERE followup_at <= datetime('now')
                              AND status IN ('Applied','Interview')""").fetchall()
    return [dict(r) for r in rows]


def delete_application(aid: int):
    with get_conn() as c:
        c.execute("DELETE FROM applications WHERE id=?", (aid,))

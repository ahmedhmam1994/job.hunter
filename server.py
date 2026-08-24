"""server.py — FastAPI backend.
Run locally:  uvicorn server:app --reload --port 8000
Run docker:   docker compose up -d --build
"""
import os, secrets, shutil, sqlite3, threading
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

import scrapers, matcher, cv_parser, database, users_db
from ratelimit import rate_limit

ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

app = FastAPI(title="Job Hunter API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ---------- Auth ----------
def auth(api_key: str = Header(..., alias="X-API-Key")) -> dict:
    user = users_db.get_user_by_key(api_key)
    if not user:
        raise HTTPException(401, "Invalid API key")
    with users_db.get_conn() as c:
        active = c.execute("SELECT is_active FROM users WHERE id=?",
                           (user["id"],)).fetchone()
    if not active or not active[0]:
        raise HTTPException(403, "Account disabled — contact admin")
    return user


def require_admin(x_admin_key: str = Header(...)):
    if not ADMIN_KEY or not secrets.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(403, "Admin access denied")


# ---------- Public ----------
@app.get("/")
def home():
    return {"service": "Job Hunter API", "status": "running",
            "endpoints": ["/register", "/search", "/queries",
                          "/profile/cv", "/panel", "/docs"]}


class RegisterReq(BaseModel):
    name: str
    email: str

@app.post("/register", dependencies=[Depends(rate_limit("register", limit=5, window_seconds=3600))])
def register(req: RegisterReq):
    key = users_db.create_user(req.name, req.email)
    return {"api_key": key}


@app.post("/search")
def search(query: str, sites: list[str] | None = None,
           user: dict = Depends(auth)):
    """On-demand search scored against this user's CV."""
    sites = sites or ["Remotive", "RemoteOK"]
    jobs = scrapers.fetch_all(sites[:4], query)[:40]

    if user["cv_path"]:
        try:
            profile = cv_parser.CVProfile(user["cv_path"])
            jobs = matcher.rank_jobs(jobs, profile)
            jobs = [j for j in jobs if j["score"] >= user["min_score"]] or \
                   sorted(jobs, key=lambda x: x["score"], reverse=True)[:15]
        except Exception as e:
            print(f"Scoring skipped: {e}")
    return {"jobs": jobs}


# ---------- Profile ----------
@app.put("/profile/cv")
async def upload_cv(file: UploadFile = File(...), user: dict = Depends(auth)):
    dest_dir = os.path.join(os.environ.get("DATA_DIR", "."), "cv_storage")
    os.makedirs(dest_dir, exist_ok=True)
    ext = "." + file.filename.split(".")[-1].lower()
    dest = os.path.join(dest_dir, f"user_{user['id']}{ext}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    users_db.update_user(_key_of(user), cv_path=dest)
    prof = cv_parser.CVProfile(dest)
    return {"skills": sorted(prof.skills), "years": prof.years}


def _key_of(user: dict) -> str:
    with users_db.get_conn() as c:
        return c.execute("SELECT api_key FROM users WHERE id=?",
                         (user["id"],)).fetchone()[0]


class SettingsReq(BaseModel):
    device_token: Optional[str] = None
    min_score: Optional[int] = None

@app.put("/profile/settings")
def set_settings(req: SettingsReq, user: dict = Depends(auth)):
    key = _key_of(user)
    if req.device_token:
        users_db.set_device_token(key, req.device_token)
    if req.min_score:
        users_db.update_user(key, min_score=req.min_score)
    return {"ok": True}


# ---------- Saved queries ----------
class QueryReq(BaseModel):
    query: str
    sites: list[str]
    interval_minutes: int = 30

@app.post("/queries")
def create_query(req: QueryReq, user: dict = Depends(auth)):
    users_db.add_query(_key_of(user), req.query, req.sites,
                       False, req.interval_minutes)
    return {"ok": True}

@app.get("/queries")
def list_queries(user: dict = Depends(auth)):
    return {"queries": users_db.my_queries(_key_of(user))}

@app.delete("/queries/{query_id}")
def delete_query(query_id: int, user: dict = Depends(auth)):
    users_db.remove_query(_key_of(user), query_id)
    return {"ok": True}


# ---------- Admin API ----------
from notifications import send_to_many

class BroadcastReq(BaseModel):
    title: str
    body: str

@app.get("/admin/users")
def admin_list_users(_: None = Depends(require_admin)):
    return {"users": users_db.all_users()}

@app.patch("/admin/users/{user_id}")
def admin_update_user(user_id: int, min_score: int = None,
                      is_active: bool = None, _: None = Depends(require_admin)):
    if is_active is not None:
        users_db.set_user_active(user_id, is_active)
    if min_score is not None:
        users_db.update_user_by_id(user_id, min_score=min_score)
    return {"ok": True}

@app.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, _: None = Depends(require_admin)):
    users_db.delete_user(user_id)
    return {"ok": True}

@app.post("/admin/broadcast")
def admin_broadcast(req: BroadcastReq, _: None = Depends(require_admin)):
    tokens = [t for t, _ in users_db.all_device_tokens()]
    dead = send_to_many(tokens, f"{req.title}", req.body)
    if dead:
        with users_db.get_conn() as c:
            for t in dead:
                c.execute("UPDATE users SET device_token=NULL WHERE device_token=?", (t,))
    return {"sent": len(tokens), "failed": len(dead)}

@app.get("/admin/stats")
def admin_stats(_: None = Depends(require_admin)):
    stats = users_db.platform_stats()
    try:
        apps = database.all_applications()
        stats["applications"] = {"total": len(apps)}
    except Exception:
        pass
    return stats


# ---------- Web admin UI + startup ----------
try:
    from routes_admin_ui import router as admin_ui_router
    app.include_router(admin_ui_router)
except ImportError:
    print("(web admin UI not installed)")

import logging
logging.basicConfig(level=logging.INFO)

from scheduler import start_scheduler
start_scheduler()

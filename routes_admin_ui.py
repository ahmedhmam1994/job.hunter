"""Web admin panel — mount via routes included in server.py."""
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import users_db
from notifications import send_to_many

router = APIRouter(prefix="/panel")
templates = Jinja2Templates(directory="admin_ui/templates")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")


def guard(request: Request):
    if request.cookies.get("admin_session") != ADMIN_KEY or not ADMIN_KEY:
        raise HTTPException(303, headers={"Location": "/panel/login"})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "view": "login", "error": False})


@router.post("/login")
def do_login(request: Request, key: str = Form(...)):
    if key != ADMIN_KEY:
        return templates.TemplateResponse(
            "dashboard.html", {"request": request, "view": "login", "error": True})
    resp = RedirectResponse("/panel/", status_code=303)
    resp.set_cookie("admin_session", key, httponly=True, samesite="lax")
    return resp


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    guard(request)
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "view": "main",
        "stats": users_db.platform_stats(),
        "users": users_db.all_users(),
        "toast": request.query_params.get("msg"),
    })


@router.get("/users/row/{user_id}", response_class=HTMLResponse)
def user_row(request: Request, user_id: int):
    guard(request)
    u = next((u for u in users_db.all_users() if u["id"] == user_id), None)
    return templates.TemplateResponse("users.html",
                                      {"request": request, "users": [u]})


@router.post("/users/{user_id}/toggle", response_class=HTMLResponse)
def toggle_user(request: Request, user_id: int):
    guard(request)
    u = next((u for u in users_db.all_users() if u["id"] == user_id), None)
    users_db.set_user_active(user_id, not u["is_active"])
    return user_row(request, user_id)


@router.post("/users/{user_id}/min_score", response_class=HTMLResponse)
def change_score(request: Request, user_id: int, min_score: int = Form(...)):
    guard(request)
    users_db.update_user_by_id(user_id, min_score=min_score)
    return user_row(request, user_id)


@router.delete("/users/{user_id}", response_class=HTMLResponse)
def delete_user_row(request: Request, user_id: int):
    guard(request)
    users_db.delete_user(user_id)
    return ""


@router.post("/broadcast", response_class=HTMLResponse)
def broadcast(request: Request, title: str = Form(...), body: str = Form(...)):
    guard(request)
    tokens = [t for t, _ in users_db.all_device_tokens()]
    dead = send_to_many(tokens, f"{title}", body) or []
    msg = f"Sent to {len(tokens)} devices ({len(dead)} failed)"
    return RedirectResponse(f"/panel/?msg={msg}", status_code=303)


@router.get("/logout")
def logout():
    resp = RedirectResponse("/panel/login", status_code=303)
    resp.delete_cookie("admin_session")
    return resp

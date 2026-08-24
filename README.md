# Job Hunter

A job-hunting toolkit with two parts:

1. **Desktop app** (CustomTkinter) — scrapes job listings, matches them against your CV, tracks applications, and shows stats, all locally.
2. **Multi-user server** (FastAPI) — a hosted API + scheduler + admin panel that runs saved searches per user and pushes match notifications via Firebase Cloud Messaging.

## Desktop app

```
pip install -r requirements.txt
python job_search_app.py
```

- `job_search_app.py` — main desktop UI (Search / Tracker / Stats tabs)
- `scrapers.py` — fetches jobs from Wuzzuf, Glassdoor, Indeed, Remotive, WeWorkRemotely, RemoteOK
- `cv_parser.py` — extracts skills and years of experience from a PDF/DOCX CV
- `matcher.py` — fuzzy-matches scraped jobs against the parsed CV profile
- `database.py` — SQLite storage for favorites, seen jobs, and applications
- `apply_helper.py` — generates a cover letter and opens the job page
- `stats.py` — aggregates application statistics

## Server

```
uvicorn server:app --reload --port 8000
# or
docker compose up -d --build
```

Requires `ADMIN_KEY` (admin panel/API access) and a `firebase-service-account.json` (push notifications) via env vars — see `docker-compose.yml`.

- `server.py` — FastAPI app: registration, search, saved queries, CV upload, admin API
- `users_db.py` — SQLite storage for users, API keys, and saved queries
- `scheduler.py` — background loop that runs each user's due saved queries and pushes new matches
- `notifications.py` — Firebase Cloud Messaging push helper
- `routes_admin_ui.py` + `admin_ui/templates/` — HTMX-based web admin panel at `/panel`

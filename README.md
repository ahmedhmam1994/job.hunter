# Job Hunter

A desktop app (CustomTkinter) that scrapes job listings from multiple sites, matches them against your CV, tracks applications, and shows stats.

## Setup

```
pip install -r requirements.txt
python job_search_app.py
```

## Modules

- `job_search_app.py` — main desktop UI (Search / Tracker / Stats tabs)
- `scrapers.py` — fetches jobs from Wuzzuf, Glassdoor, Indeed, Remotive, WeWorkRemotely, RemoteOK
- `cv_parser.py` — extracts skills and years of experience from a PDF/DOCX CV
- `matcher.py` — fuzzy-matches scraped jobs against the parsed CV profile
- `database.py` — SQLite storage for favorites, seen jobs, and applications
- `apply_helper.py` — generates a cover letter and opens the job page
- `stats.py` — aggregates application statistics

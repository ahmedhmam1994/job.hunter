"""scrapers.py — Fetch jobs from multiple sites."""
import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120 Safari/537.36"),
           "Accept-Language": "en-US,en;q=0.9"}

# Glassdoor, Indeed, Wuzzuf and Bayt serve challenge/near-empty pages to plain
# HTTP clients (Cloudflare/PerimeterX-style bot detection) — a real
# requests.get() to them often returns 0 results with no error. Rendering
# with a real (headless) browser gets past that basic check, at the cost of
# a slower, heavier request.
RENDERED_SITES = {"Glassdoor", "Indeed", "Wuzzuf", "Bayt"}

# Sites requiring a free API key you register for yourself — this app can't
# create accounts on your behalf. Set these as environment variables; any
# site whose key is missing is skipped gracefully (not an error).
REED_API_KEY = os.environ.get("REED_API_KEY", "")
ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
JOOBLE_API_KEY = os.environ.get("JOOBLE_API_KEY", "")

# Adzuna doesn't cover every country in COUNTRIES (no Egypt/UAE/Saudi Arabia
# coverage as of writing) — unsupported countries fall back to "us".
ADZUNA_COUNTRY_CODES = {
    "United States": "us", "United Kingdom": "gb", "Germany": "de",
    "India": "in", "Canada": "ca",
}

# Country filter: "Any" means no filtering at all. Indeed has real
# country-specific subdomains that actually scope results server-side —
# verified eg.indeed.com returns Egypt-local listings vs. www.indeed.com
# treating a location string like "Egypt" as US-only free text (it matched
# a town called Egypt, Arkansas instead). No other site here has an
# equivalent reliable country parameter (Glassdoor's locKeyword param was
# tested and silently ignored), so those get a client-side location-text
# filter instead — cruder, but honest about what each site actually supports.
COUNTRIES = ["Any", "Egypt", "United States", "United Kingdom", "Germany",
            "United Arab Emirates", "India", "Canada", "Saudi Arabia"]

INDEED_DOMAINS = {
    "Egypt": "eg.indeed.com",
    "United States": "www.indeed.com",
    "United Kingdom": "uk.indeed.com",
    "Germany": "de.indeed.com",
    "United Arab Emirates": "ae.indeed.com",
    "India": "in.indeed.com",
    "Canada": "ca.indeed.com",
    "Saudi Arabia": "sa.indeed.com",
}


_CHALLENGE_TITLES = ("just a moment", "attention required", "checking your browser")


def _fetch_rendered_html(url: str, max_challenge_wait_ms: int = 12000) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"])
        try:
            page = browser.new_page(user_agent=HEADERS["User-Agent"],
                                    viewport={"width": 1366, "height": 900})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            # Cloudflare's managed/JS challenge ("Just a moment...") auto-resolves
            # and redirects on its own after a few seconds — a fixed short wait
            # (previously 2.5s) sometimes returned the challenge page itself
            # instead of the real content. Poll the title instead of guessing.
            waited = 0
            step = 1000
            while waited < max_challenge_wait_ms and any(
                    t in page.title().strip().lower() for t in _CHALLENGE_TITLES):
                page.wait_for_timeout(step)
                waited += step
            page.wait_for_timeout(1000)  # let post-challenge rendering settle
            return page.content()
        finally:
            browser.close()


SITES = {
    "Wuzzuf":         lambda q: f"https://wuzzuf.net/search/jobs/?q={quote(q)}",
    "Glassdoor":      lambda q: f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote(q)}",
    "Indeed":         lambda q: f"https://www.indeed.com/jobs?q={quote(q)}&sc=0kf%3Aattr%28DSQF7%29",
    "Remotive":       lambda q: f"https://remotive.com/api/remote-jobs?search={quote(q)}",
    "WeWorkRemotely": lambda q: f"https://weworkremotely.com/remote-jobs/search?term={quote(q)}",
    "RemoteOK":       lambda q: f"https://remoteok.com/api",
    "Arbeitnow":      lambda q: f"https://www.arbeitnow.com/api/job-board-api?search={quote(q)}",
    "Jobicy":         lambda q: f"https://jobicy.com/api/v2/remote-jobs?count=20&tag={quote(q)}",
    "Bayt":           lambda q: f"https://www.bayt.com/en/international/jobs/?q={quote(q)}",
    "Himalayas":      lambda q: f"https://himalayas.app/jobs/api?search={quote(q)}",
    "TheMuse":        lambda q: "https://www.themuse.com/api/public/jobs?category=Software+Engineering&page=1",
    "Reed":           lambda q: f"https://www.reed.co.uk/api/1.0/search?keywords={quote(q)}",
    "Adzuna":         lambda q: f"https://api.adzuna.com/v1/api/jobs/us/search/1?what={quote(q)}",
    "Jooble":         lambda q: "https://jooble.org/api",
}


def _location_matches_country(location: str, country: str) -> bool:
    loc = location.lower()
    return country.lower() in loc or "remote" in loc


def fetch_jobs(site: str, query: str, country: str | None = None) -> list[dict]:
    results = []
    url = SITES[site](query)

    if site == "Indeed" and country and country != "Any":
        domain = INDEED_DOMAINS.get(country, "www.indeed.com")
        url = f"https://{domain}/jobs?q={quote(query)}&sc=0kf%3Aattr%28DSQF7%29"

    if site == "Adzuna" and country and country != "Any":
        code = ADZUNA_COUNTRY_CODES.get(country, "us")
        url = f"https://api.adzuna.com/v1/api/jobs/{code}/search/1?what={quote(query)}"

    if site == "RemoteOK":
        data = requests.get(url, headers=HEADERS, timeout=20).json()[1:]
        ql = query.lower()
        for j in data:
            blob = f"{j.get('position','')} {j.get('description','')}".lower()
            if ql in blob:
                results.append({"title": j["position"], "company": j["company"],
                                "location": "Remote", "link": j["url"],
                                "site": site})
        results = results[:15]

    elif site == "Arbeitnow":
        data = requests.get(url, headers=HEADERS, timeout=20).json().get("data", [])
        for j in data[:15]:
            results.append({"title": j["title"], "company": j["company_name"],
                            "location": "Remote" if j.get("remote") else j.get("location", ""),
                            "link": j["url"], "site": site})

    elif site == "Jobicy":
        data = requests.get(url, headers=HEADERS, timeout=20).json().get("jobs", [])
        for j in data[:15]:
            results.append({"title": j["jobTitle"], "company": j["companyName"],
                            "location": j.get("jobGeo") or "Remote",
                            "link": j["url"], "site": site})

    elif site == "Himalayas":
        # Himalayas' search= param is silently ignored too (verified: identical
        # totalCount for a real keyword vs. a nonsense one) — filter client-side.
        data = requests.get(url, headers=HEADERS, timeout=20).json().get("jobs", [])
        ql = query.lower()
        for j in data:
            blob = f"{j.get('title','')} {j.get('excerpt','')}".lower()
            if ql in blob:
                locs = j.get("locationRestrictions") or ["Remote"]
                results.append({"title": j["title"], "company": j["companyName"],
                                "location": ", ".join(locs), "link": j["guid"], "site": site})
        results = results[:15]

    elif site == "TheMuse":
        # The Muse's public API has no free-text search (q=/search= are
        # silently ignored — verified with matching totals for both vs. no
        # param at all) — only fixed category/level/location filters. Fetch
        # the Software Engineering category and filter by keyword client-side
        # (against title + description, not just title, for better recall).
        data = requests.get(url, headers=HEADERS, timeout=20).json().get("results", [])
        ql = query.lower()
        for j in data:
            blob = f"{j['name']} {j.get('contents','')}".lower()
            if ql in blob:
                locs = j.get("locations") or []
                results.append({"title": j["name"],
                                "company": j.get("company", {}).get("name", ""),
                                "location": ", ".join(l["name"] for l in locs) or "Remote",
                                "link": j.get("refs", {}).get("landing_page", ""),
                                "site": site})
        results = results[:15]

    elif site == "Reed":
        if not REED_API_KEY:
            print("[Reed] skipped: set REED_API_KEY (free key from reed.co.uk/developers) to enable")
        else:
            data = requests.get(url, auth=(REED_API_KEY, ""), timeout=20).json().get("results", [])
            for j in data[:15]:
                results.append({"title": j["jobTitle"], "company": j["employerName"],
                                "location": j.get("locationName", ""),
                                "link": j["jobUrl"], "site": site})

    elif site == "Adzuna":
        if not (ADZUNA_APP_ID and ADZUNA_APP_KEY):
            print("[Adzuna] skipped: set ADZUNA_APP_ID/ADZUNA_APP_KEY (free keys from developer.adzuna.com) to enable")
        else:
            data = requests.get(url, params={"app_id": ADZUNA_APP_ID, "app_key": ADZUNA_APP_KEY},
                               timeout=20).json().get("results", [])
            for j in data[:15]:
                results.append({"title": j["title"],
                                "company": j.get("company", {}).get("display_name", ""),
                                "location": j.get("location", {}).get("display_name", ""),
                                "link": j["redirect_url"], "site": site})

    elif site == "Jooble":
        if not JOOBLE_API_KEY:
            print("[Jooble] skipped: set JOOBLE_API_KEY (free key from jooble.org/api/about) to enable")
        else:
            # Jooble's API sits behind Cloudflare even for a plain unauthenticated
            # test request (confirmed: a fake key gets a "Just a moment..."
            # challenge, not a clean auth error like Reed/Adzuna give). This may
            # or may not clear with a real key — untested, flagging honestly.
            resp = requests.post(f"https://jooble.org/api/{JOOBLE_API_KEY}",
                                 json={"keywords": query}, timeout=20,
                                 headers={**HEADERS, "Content-Type": "application/json"})
            for j in resp.json().get("jobs", [])[:15]:
                results.append({"title": j["title"], "company": j.get("company", ""),
                                "location": j.get("location", ""),
                                "link": j["link"], "site": site})

    elif site in RENDERED_SITES:
        soup = BeautifulSoup(_fetch_rendered_html(url), "lxml")
    else:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        soup = BeautifulSoup(resp.text, "lxml")

    if site == "Remotive":
        data = resp.json().get("jobs", [])
        for j in data[:15]:
            results.append({"title": j["title"], "company": j["company_name"],
                            "location": "Remote", "link": j["url"],
                            "site": site})

    elif site == "Wuzzuf":
        # Wuzzuf's CSS-module class names (css-xxxxxx) are build-time hashes
        # that change on every redeploy, so selectors based on them go stale
        # silently. Anchor on stable structural/URL patterns instead: job
        # detail links always contain "/jobs/p/", employer links "/jobs/careers/".
        for card in soup.select("div.css-pkv5jc")[:15]:
            title_link = card.select_one("h2 a")
            if not title_link:
                continue
            comp_candidates = card.select("a[href*='/jobs/careers/']")
            comp_link = next((a for a in comp_candidates if a.get_text(strip=True)), None)
            loc = comp_link.find_next_sibling("span") if comp_link else None
            href = title_link.get("href", "")
            results.append({"title": title_link.get_text(strip=True),
                            "company": comp_link.get_text(strip=True).rstrip(" -").strip() if comp_link else "",
                            "location": loc.get_text(" ", strip=True) if loc else "",
                            "link": href if href.startswith("http") else "https://wuzzuf.net" + href,
                            "site": site})

    elif site == "Bayt":
        # No dedicated location element in the card markup — the URL itself
        # encodes the country (e.g. /en/saudi-arabia/jobs/...), so derive a
        # location from that instead.
        for card in soup.select("li.has-pointer-d")[:15]:
            title_link = card.select_one("h2 a[href]")
            if not title_link:
                continue
            comp = card.select_one(".job-company-location-wrapper a")
            href = title_link.get("href", "")
            country_match = re.match(r"^/en/([^/]+)/jobs/", href)
            location = country_match.group(1).replace("-", " ").title() if country_match else ""
            if location.lower() == "uae":
                location = "UAE"
            results.append({"title": title_link.get_text(strip=True),
                            "company": comp.get_text(strip=True) if comp else "",
                            "location": location,
                            "link": href if href.startswith("http") else "https://www.bayt.com" + href,
                            "site": site})

    elif site == "Glassdoor":
        for card in soup.select("[data-test='jobListing']")[:15]:
            t = card.select_one("[data-test='job-title']")
            comp = card.select_one("[class*='EmployerName']")
            loc = card.select_one("[data-test='emp-location']")
            link = card.select_one("a[data-test='job-title']")
            if t and link:
                href = link.get("href", "")
                results.append({"title": t.get_text(strip=True),
                                "company": comp.get_text(strip=True) if comp else "",
                                "location": loc.get_text(strip=True) if loc else "",
                                "link": href if href.startswith("http") else "https://www.glassdoor.com" + href,
                                "site": site})

    elif site == "Indeed":
        for card in soup.select("div.job_seen_beacon")[:15]:
            t = card.select_one("span[id^='jobTitle-']")
            comp = card.select_one("[data-testid='company-name']")
            loc = card.select_one("[data-testid='text-location']")
            link = card.select_one("a.jcs-JobTitle[href]")
            if t and link:
                href = link.get("href", "")
                results.append({"title": t.get_text(strip=True),
                                "company": comp.get_text(strip=True) if comp else "",
                                "location": loc.get_text(strip=True) if loc else "",
                                "link": href if href.startswith("http") else "https://www.indeed.com" + href,
                                "site": site})

    elif site == "WeWorkRemotely":
        for card in soup.select("li.new-listing-container")[:15]:
            t = card.select_one(".new-listing__header__title__text")
            comp = card.select_one(".new-listing__company-name")
            loc = card.select_one(".new-listing__company-headquarters")
            link = card.select_one("a.listing-link--unlocked[href]")
            if t and link:
                href = link.get("href", "")
                results.append({"title": t.get_text(strip=True),
                                "company": comp.get_text(strip=True) if comp else "",
                                "location": loc.get_text(strip=True) if loc else "Remote",
                                "link": href if href.startswith("http") else "https://weworkremotely.com" + href,
                                "site": site})

    # Indeed is already country-scoped server-side (real subdomain per
    # country); everything else gets the cruder client-side text filter.
    if country and country != "Any" and site != "Indeed":
        results = [r for r in results if _location_matches_country(r["location"], country)]

    return results


def fetch_all(sites: list[str], query: str, country: str | None = None) -> list[dict]:
    """Fetch from many sites; failures are skipped silently."""
    jobs = []
    for site in sites:
        try:
            got = fetch_jobs(site, query, country)
            print(f"[{site}] -> {len(got)} jobs")
            jobs.extend(got)
        except Exception as e:
            print(f"[{site}] failed: {e}")
    # dedupe by link
    seen, out = set(), []
    for j in jobs:
        if j["link"] not in seen:
            seen.add(j["link"])
            out.append(j)
    return out

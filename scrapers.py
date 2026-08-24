"""scrapers.py — Fetch jobs from multiple sites."""
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120 Safari/537.36"),
           "Accept-Language": "en-US,en;q=0.9"}

# Glassdoor and Indeed serve challenge/near-empty pages to plain HTTP clients
# (Cloudflare/PerimeterX-style bot detection) — a real requests.get() to them
# often returns 0 results with no error. Rendering with a real (headless)
# browser gets past that basic check, at the cost of a slower, heavier request.
RENDERED_SITES = {"Glassdoor", "Indeed"}


def _fetch_rendered_html(url: str) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"])
        try:
            page = browser.new_page(user_agent=HEADERS["User-Agent"],
                                    viewport={"width": 1366, "height": 900})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)  # let client-side rendering settle
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
}


def fetch_jobs(site: str, query: str) -> list[dict]:
    results = []
    url = SITES[site](query)
    if site == "RemoteOK":
        data = requests.get(url, headers=HEADERS, timeout=20).json()[1:]
        ql = query.lower()
        for j in data:
            blob = f"{j.get('position','')} {j.get('description','')}".lower()
            if ql in blob:
                results.append({"title": j["position"], "company": j["company"],
                                "location": "Remote", "link": j["url"],
                                "site": site})
        return results[:15]

    if site in RENDERED_SITES:
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
        for card in soup.select("div.css-1gatmva")[:15]:
            t = card.select_one("h2")
            comp = card.select_one(".css-d7j1jk")
            link = card.select_one("a")
            loc = card.select_one(".css-5wly0z")
            if t and link:
                href = link.get("href", "")
                results.append({"title": t.get_text(strip=True),
                                "company": comp.get_text(strip=True) if comp else "",
                                "location": loc.get_text(strip=True) if loc else "",
                                "link": href if href.startswith("http") else "https://wuzzuf.net" + href,
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
        for card in soup.select("section li")[:15]:
            t = card.select_one("span.title")
            comp = card.select_one(".company")
            link = card.find("a", href=True)
            if t and link:
                href = link["href"]
                results.append({"title": t.get_text(strip=True),
                                "company": comp.get_text(strip=True) if comp else "",
                                "location": "Remote",
                                "link": href if href.startswith("http") else "https://weworkremotely.com" + href,
                                "site": site})
    return results


def fetch_all(sites: list[str], query: str) -> list[dict]:
    """Fetch from many sites; failures are skipped silently."""
    jobs = []
    for site in sites:
        try:
            got = fetch_jobs(site, query)
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

"""scrapers.py — Fetch jobs from multiple sites."""
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120 Safari/537.36"),
           "Accept-Language": "en-US,en;q=0.9"}

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
            comp = card.select_one("[data-test='employer-name']")
            link = card.select_one("a[href]")
            if t and link:
                results.append({"title": t.get_text(strip=True),
                                "company": comp.get_text(strip=True) if comp else "",
                                "location": "",
                                "link": "https://www.glassdoor.com" + link.get("href", ""),
                                "site": site})

    elif site == "Indeed":
        for card in soup.select("div.job_seen_beacon")[:15]:
            t = card.select_one("h2.jobTitle span")
            comp = card.select_one("[data-testid='company-name']")
            loc = card.select_one("[data-testid='text-location']")
            link = card.select_one("a[href]")
            if t and link:
                results.append({"title": t.get_text(strip=True),
                                "company": comp.get_text(strip=True) if comp else "",
                                "location": loc.get_text(strip=True) if loc else "",
                                "link": "https://www.indeed.com" + link.get("href", ""),
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

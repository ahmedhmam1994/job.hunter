"""icons.py — Fetch and cache small site-logo icons for job cards.

Uses Google's public favicon service to grab each site's actual favicon
(no bundled trademark artwork, no API key). Network-safe to call from a
background thread: this module never touches Tkinter — it only returns
raw bytes / PIL images. Building the actual CTkImage (a Tk-backed object)
must happen on the main thread, in job_search_app.py.
"""
import os
import threading

import requests
from PIL import Image

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".icon_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SITE_DOMAINS = {
    "Wuzzuf": "wuzzuf.net",
    "Glassdoor": "glassdoor.com",
    "Indeed": "indeed.com",
    "Remotive": "remotive.com",
    "WeWorkRemotely": "weworkremotely.com",
    "RemoteOK": "remoteok.com",
}

_lock = threading.Lock()


def get_pil_image(site: str) -> Image.Image | None:
    """Thread-safe. Returns a small PIL image for the site's logo, or None."""
    domain = SITE_DOMAINS.get(site)
    if not domain:
        return None

    cache_file = os.path.join(CACHE_DIR, f"{site}.png")
    with _lock:
        if os.path.exists(cache_file):
            try:
                return Image.open(cache_file).convert("RGBA")
            except Exception:
                pass

    try:
        resp = requests.get(
            "https://www.google.com/s2/favicons",
            params={"domain": domain, "sz": "64"}, timeout=8)
        resp.raise_for_status()
        with _lock:
            with open(cache_file, "wb") as f:
                f.write(resp.content)
        import io
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        return None

"""ratelimit.py — in-memory fixed-window rate limiter.

Single-process only: state lives in a dict, not shared across workers or
replicas. Fine for the default one-process uvicorn/docker-compose deploy
in this repo; swap for a Redis-backed limiter before running multiple
workers behind a load balancer.
"""
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[str, list[float]] = defaultdict(list)


def rate_limit(key_prefix: str, limit: int, window_seconds: int):
    """FastAPI dependency: allow `limit` requests per client IP per window."""
    def dep(request: Request):
        client = request.client.host if request.client else "unknown"
        key = f"{key_prefix}:{client}"
        now = time.monotonic()
        with _lock:
            hits = _hits[key]
            hits[:] = [t for t in hits if now - t < window_seconds]
            if len(hits) >= limit:
                raise HTTPException(429, "Too many requests, try again later")
            hits.append(now)
    return dep

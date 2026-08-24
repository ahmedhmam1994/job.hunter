"""matcher.py — Score jobs against CV profile (fuzzy matching)."""
from rapidfuzz import fuzz

WEIGHTS = {"skills": 55, "years": 25, "text_sim": 20}


def score_job(job: dict, profile) -> dict:
    blob = f"{job['title']} {job['company']} {job['location']} {job.get('tags','')}".lower()

    matched = [sk for sk in profile.skills if sk.lower() in blob]
    skill_pct = min(1.0, len(matched) / max(6, len(profile.skills))) if profile.skills else 0

    yr_score = 0.0
    if profile.years and profile.years >= 3:
        yr_score = 0.7 + min(0.3, (profile.years - 3) * 0.05)

    sim = fuzz.partial_ratio(job["title"].lower(),
                             profile.text[:800].lower()) / 100

    total = int(skill_pct * WEIGHTS["skills"]
                + yr_score * WEIGHTS["years"]
                + sim * WEIGHTS["text_sim"])
    return {**job, "score": max(0, min(100, total)),
            "matched_skills": matched}


def rank_jobs(jobs: list[dict], profile) -> list[dict]:
    scored = [score_job(j, profile) for j in jobs]
    return sorted(scored, key=lambda x: x["score"], reverse=True)


def color_for(score: int) -> str:
    return "#22c55e" if score >= 75 else "#eab308" if score >= 55 else "#94a3b8"

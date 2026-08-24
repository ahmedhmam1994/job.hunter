"""stats.py — Aggregates application statistics."""


def get_stats() -> dict:
    apps = database_all()
    total = len(apps)
    if total == 0:
        return {"total": 0}
    statuses, per_site = {}, {}
    for aid, title, comp, site, status, applied, followup, link, notes in apps:
        statuses[status] = statuses.get(status, 0) + 1
        per_site[site] = per_site.get(site, 0) + 1
    interviews = sum(v for k, v in statuses.items() if k in ("Interview", "Offer"))
    rejected = statuses.get("Rejected", 0)
    return {"total": total, "statuses": statuses, "per_site": per_site,
            "response_rate": round((interviews + rejected) / total * 100),
            "interview_rate": round(interviews / total * 100),
            "offer_rate": round(statuses.get("Offer", 0) / total * 100),
            "best_site": max(per_site, key=per_site.get) if per_site else None}


def database_all():
    import database
    return database.all_applications()

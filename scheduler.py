"""scheduler.py — Runs every user's saved queries on their own schedule."""
import threading, time, logging
log = logging.getLogger("scheduler")

import scrapers, database, users_db


def run_due_queries():
    due = users_db.due_queries()
    log.info(f"{len(due)} query(ies) due")
    for q in due:
        try:
            jobs = scrapers.fetch_all(q["sites"], q["query"])

            new_jobs = []                       # per-user dedup
            for j in jobs:
                uid_key = f"u{q['uid']}|{j['link']}"
                if not database.is_seen(uid_key):
                    database.mark_seen_single(uid_key)
                    new_jobs.append(j)

            hot = new_jobs
            if q["cv_path"]:
                try:
                    import cv_parser, matcher
                    profile = cv_parser.CVProfile(q["cv_path"])
                    hot = matcher.rank_jobs(new_jobs, profile)
                    hot = [j for j in hot if j["score"] >= (q["min_score"] or 60)]
                except Exception as e:
                    log.warning(f"CV scoring failed: {e}")

            if hot and q["device_token"]:
                from notifications import send_push
                best = hot[0]
                score_txt = f" ({best['score']}% match)" if "score" in best else ""
                send_push(q["device_token"],
                          f"{len(hot)} new match{'es' if len(hot) > 1 else ''}: {q['query']}",
                          f"{best['title']} at {best['company']}{score_txt}",
                          data={"link": best["link"]})
                log.info(f"Pushed {len(hot)} jobs -> user {q['uid']}")
        except Exception as e:
            log.error(f"Query '{q['query']}' failed: {e}")
        finally:
            users_db.mark_query_ran(q["qid"])
            time.sleep(2)


def start_scheduler(poll_seconds=60):
    def loop():
        while True:
            try:
                run_due_queries()
            except Exception as e:
                log.error(f"Scheduler tick error: {e}")
            time.sleep(poll_seconds)
    threading.Thread(target=loop, daemon=True).start()
    log.info("Scheduler started")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_scheduler()
    while True:
        time.sleep(3600)

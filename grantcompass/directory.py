"""Built-in directory of major US grantmakers (data/funder_directory.json).

Each entry was checked once without AI: robots.txt allows it, there's no bot
wall, and the page has readable text. Entries that failed those checks are
kept in the file with the reason, but are never fetched. On a search, every
usable page is checked in parallel; only new or changed pages are read by
the Research Agent."""

import json
from .pool import ContextPool as ThreadPoolExecutor  # keeps the organisation in worker threads
from datetime import datetime, timedelta

from . import db
from .config import ROOT
from .watchlist import check, to_lead

DIRECTORY_FILE = ROOT / "data" / "funder_directory.json"
CACHE_FILE = ROOT / "data" / "funder_directory_cache.json"  # pre-read results shipped with the repo
CHECK_WORKERS = 8


def entries() -> list[dict]:
    return json.loads(DIRECTORY_FILE.read_text())


def sync() -> None:
    """Load the directory, plus the shipped cache so a fresh install doesn't re-read every page with the AI.
    A cached result is only reused while the page's text hash still matches."""
    db.sync_directory(entries())
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text())
        for row in db.list_directory():
            c = cache.get(row["url"])
            if c and not row["content_hash"]:
                db.update_directory(row["url"], c["content_hash"], c["result"])


def export_cache() -> int:
    """Write current results to the shipped cache file (run after a full check)."""
    rows = [r for r in db.list_directory() if r["result"]]
    cache = {r["url"]: {"content_hash": r["content_hash"], "result": {**r["result"], "raw_text": r["result"].get(
        "raw_text", "")}} for r in rows}
    CACHE_FILE.write_text(json.dumps(cache, indent=1))
    return len(cache)


REFRESH_HOURS = 24  # re-fetch a foundation page at most once a day; otherwise use the stored result


def _fresh(row: dict) -> bool:
    """Checked (successfully or not) within the last day."""
    if not row["last_checked"]:
        return False
    return datetime.now() - datetime.fromisoformat(row["last_checked"]) < timedelta(hours=REFRESH_HOURS)


def check_all() -> list[dict]:
    """Check every usable directory page. Returns one {lead, changed, usage, error} per page.
    Pages checked in the last day are served from storage, so a search never waits on 74 websites."""
    def one(row):
        sid = f"dir:{row['n']}"
        if _fresh(row):  # stored result, or a recent failure we don't retry until tomorrow
            lead = to_lead(row, row["result"], "Foundation directory", sid) if row["result"] else None
            return {"lead": lead, "changed": False, "usage": None, "error": None}
        res = check(row, save=lambda digest, opp: db.update_directory(row["url"], digest, opp),
                    source="Foundation directory", sid=sid)
        if res["error"]:
            db.mark_directory_checked(row["url"])
        return res

    with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
        return list(pool.map(one, db.list_directory()))

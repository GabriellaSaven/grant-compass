"""Funder watchlist: the foundation and community-foundation pages a team
already tracks. Works for any funder in any state.

Each check downloads the page and hashes its text. If nothing changed since
the last check, the stored result is reused and no AI is called; only new or
changed pages go to the Research Agent."""

import hashlib
from urllib.parse import urlparse

from . import db
from .research import extract_opportunity, fetch_page


def add(url: str, name: str | None = None) -> None:
    url = (url or "").strip()
    if urlparse(url).scheme not in ("http", "https") or not urlparse(url).hostname:
        raise ValueError("Enter a full web address starting with https://")
    db.add_watch(url, (name or "").strip() or None)


def check(entry: dict, save=None, source: str = "Watchlist", sid: str | None = None) -> dict:
    """Return {lead, changed, usage, error} for one followed page. Also used for the built-in
    foundation directory, which passes its own save function, source label and id."""
    save = save or (lambda digest, opp: db.update_watch(entry["id"], digest, opp))
    sid = sid or f"watch:{entry['id']}"
    try:
        text = fetch_page(entry["url"])
    except Exception as exc:
        return {"lead": None, "changed": False, "usage": None, "error": f"{entry['url']}: {exc}"}
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest == entry["content_hash"] and entry["result"]:
        return {"lead": to_lead(entry, entry["result"], source, sid), "changed": False, "usage": None, "error": None}
    try:
        res = extract_opportunity(text, entry["url"])
    except Exception as exc:
        return {"lead": None, "changed": True, "usage": None, "error": f"{entry['url']}: {exc}"}
    save(digest, res["opportunity"])
    return {"lead": to_lead(entry, res["opportunity"], source, sid), "changed": True, "usage": res["usage"],
            "error": None}


def to_lead(entry: dict, opp: dict, source: str = "Watchlist", sid: str | None = None) -> dict:
    elig = opp.get("eligibility") or []
    named = " ".join(elig).lower()
    return {
        "source": source,
        "source_id": sid or f"watch:{entry['id']}",
        "funder": opp.get("funder") or entry.get("name") or urlparse(entry["url"]).hostname,
        "title": opp.get("program_name") or "Untitled",
        "status": "",
        "deadline": opp.get("deadline"),
        "deadline_text": opp.get("deadline_text") or "Not stated",
        "award_min": opp.get("award_min"),
        "award_max": opp.get("award_max"),
        "award_text": opp.get("award_text") or "Not stated",
        "nonprofit_eligible": True if ("501(c)(3)" in named or "nonprofit" in named) else None,
        "eligibility": elig,
        "match_required": opp.get("matched_funding") or "Not stated",
        "geography": opp.get("geography"),
        "categories": opp.get("focus_area") or "",
        "summary": opp.get("summary") or "",
        "url": entry["url"],
        "raw_text": opp.get("raw_text") or "",
        "suspicious": opp.get("suspicious_content") or [],
        "opportunity": opp,
    }

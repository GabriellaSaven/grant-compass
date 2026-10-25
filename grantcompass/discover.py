"""Discover search: query every source that applies to this organisation,
then triage the results against the profile.

Federal (Grants.gov) works for every state. A state portal is added when the
profile's state has an open one. The built-in foundation directory and the
team's own watchlist cover private, corporate and community foundations."""

from .pool import ContextPool as ThreadPoolExecutor  # keeps the organisation in worker threads

from . import db, directory
from .sources import california, grantsgov
from .triage import search_keywords, triage
from .watchlist import check

STATE_SOURCES = {california.STATE: ("California Grants Portal", california.search)}


def state_source(profile: dict):
    return STATE_SOURCES.get(profile.get("state") or "")


def run(query: str | None, use_federal: bool, use_state: bool, use_watchlist: bool,
        use_directory: bool = False) -> dict:
    prof = (db.get_profile() or {"data": {}})["data"]
    keywords = search_keywords(prof, query)
    leads, errors, notes, usage_total = [], [], [], None

    jobs = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        if use_federal:
            jobs["Grants.gov"] = pool.submit(grantsgov.search, keywords)
        st = state_source(prof)
        if use_state and st:
            jobs[st[0]] = pool.submit(st[1], keywords)
        if use_watchlist:
            jobs["Watchlist"] = pool.submit(
                lambda: list(ThreadPoolExecutor(max_workers=6).map(check, db.list_watchlist())))
        if use_directory:
            jobs["Foundation directory"] = pool.submit(directory.check_all)
        for name, fut in jobs.items():
            try:
                out = fut.result()
            except Exception as exc:
                errors.append(f"{name} could not be reached ({type(exc).__name__}). Try again in a minute.")
                continue
            if name in ("Watchlist", "Foundation directory"):
                changed, failed = 0, []
                for r in out:
                    if r["error"]:
                        failed.append(r["error"])
                    if r["lead"]:
                        leads.append(r["lead"])
                    if r["usage"]:
                        changed += 1
                        usage_total = _add(usage_total, r["usage"])
                label = "watchlist page" if name == "Watchlist" else "foundation page"
                notes.append(f"{len(out)} {label}{'s' if len(out) != 1 else ''} checked, "
                             f"{changed} new or changed (read by the AI)")
                if failed and name == "Watchlist":
                    errors += failed
                elif failed:  # many sites: one summary line, not dozens of errors
                    errors.append(f"{len(failed)} foundation page{'s' if len(failed) != 1 else ''} couldn't be read "
                                  "this time (site slow or changed). They'll be tried again next search.")
            else:
                leads += out
                notes.append(f"{len(out)} from {name}")

    service_area = {f"dir:{e['n']}": e["states"] for e in directory.entries() if e.get("states")}
    ranked, filtered = [], []
    for lead in leads:
        if lead.get("source_id") in service_area:
            lead = {**lead, "states": service_area[lead["source_id"]]}
        t = triage(lead, prof, keywords=keywords if (query or "").strip() else None)
        (filtered if t["excluded"] else ranked).append({**lead, "triage": t})
    ranked.sort(key=lambda lead: -lead["triage"]["score"])
    return {"keywords": keywords, "ranked": ranked, "filtered": filtered, "errors": errors, "notes": notes,
            "usage": usage_total}


def _add(a: dict | None, b: dict) -> dict:
    if a is None:
        return dict(b)
    return {k: (a[k] or 0) + (b[k] or 0) if isinstance(b.get(k), (int, float)) else a[k] for k in a}


ASSESS_WORKERS = 6  # Fit Agent runs in parallel after a search


def assess_leads(leads: list[dict]) -> dict:
    """Run the Fit Agent on every result that hasn't been assessed yet, several at a time.
    Cached results are skipped, so repeating a search costs nothing."""
    from .fit import assess
    from .triage import lead_to_opportunity

    todo = [lead for lead in leads if not db.get_lead_assessment(lead["source_id"])]

    def one(lead):
        try:
            res = assess(lead_to_opportunity(lead))
        except Exception as exc:  # one failure shouldn't stop the rest
            return lead["source_id"], None, f"{lead['title'][:60]}: {type(exc).__name__}"
        db.save_lead_assessment(lead["source_id"], res["result"], res["usage"])
        return lead["source_id"], res["usage"], None

    usage, failed = None, []
    with ThreadPoolExecutor(max_workers=ASSESS_WORKERS) as pool:
        for _sid, u, err in pool.map(one, todo):
            if err:
                failed.append(err)
            else:
                usage = _add(usage, u)
    return {"new": len(todo) - len(failed), "cached": len(leads) - len(todo), "failed": failed, "usage": usage}

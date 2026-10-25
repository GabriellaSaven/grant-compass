"""Have we applied to this funder before? Matches a funder's name against every grant the organisation has
had in its pipeline (won, lost, submitted, declined, in progress) and the funders listed in its profile.

Plain rules, no AI. Names are compared by their distinctive words, so "The Mott Foundation" matches
"Charles Stewart Mott Foundation", but two funders that only share words like "Community Foundation" don't."""

import re
from datetime import date

from . import db

GENERIC = set("""the a an of and for in on at to inc incorporated llc corp corporation co company foundation foundations
fund funds trust charitable charities charity community communities family families grant grants program programme
programs programmes initiative initiatives association society council institute center centre network partners
partnership alliance us usa united states national american department office services""".split())
ORDER = {"Won": 0, "Lost": 1, "Submitted": 2, "Ready to Submit": 3, "Internal Review": 3, "Drafting": 3,
         "Go / No-Go": 4, "Researching": 4, "Declined": 5}


def key_words(name: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (name or "").lower().replace("&", " and "))
    return {w for w in words if w not in GENERIC and len(w) > 1}


def same_funder(a: str, b: str) -> bool:
    ka, kb = key_words(a), key_words(b)
    if not ka or not kb:
        return False
    small, big = sorted((ka, kb), key=len)
    return small <= big  # every distinctive word of the shorter name appears in the longer one


def history(funder: str) -> list[dict]:
    """Past and current applications to this funder, most telling first (wins, losses, then the rest)."""
    out = []
    for o in db.list_opportunities():
        if same_funder(funder, o["funder"]):
            out.append({"id": o["id"], "status": o["status"], "programme": o["program_name"], "funder": o["funder"],
                        "when": o.get("result_date") or o.get("deadline"), "amount": o.get("awarded_amount")
                        or o.get("award_max"), "feedback": o.get("lost_reason")})
    prof = (db.get_profile() or {"data": {}})["data"]
    for line in (prof.get("current_funders") or "").splitlines():
        name = line.split("—")[0].split(" - ")[0].strip()
        if name and same_funder(funder, name) and not out:
            out.append({"id": None, "status": "Funded you", "programme": line.strip(), "funder": name, "when": None,
                        "amount": None, "feedback": None})
    return sorted(out, key=lambda h: (ORDER.get(h["status"], 6), -(int((h["when"] or "0").replace("-", "")))))


def summary(items: list[dict]) -> tuple[str, str] | None:
    """One line for a result card, and a tone: ('Won $75k · Aug 2026', 'ok')."""
    if not items:
        return None
    h = items[0]
    when = f" · {date.fromisoformat(h['when']):%b %Y}" if h.get("when") else ""
    amount = f" ${h['amount'] / 1000:,.0f}k" if h.get("amount") else ""
    more = f" · +{len(items) - 1} more" if len(items) > 1 else ""
    if h["status"] == "Won":
        return f"Applied before: won{amount}{when}{more}", "ok"
    if h["status"] == "Lost":
        return f"Applied before: not funded{when}{more}", "crit"
    if h["status"] == "Funded you":
        return "Has funded you before (from your profile)", "ok"
    if h["status"] == "Declined":
        return f"You decided not to apply{when}{more}", "muted"
    if h["status"] == "Submitted":
        return f"Application submitted, awaiting decision{more}", "attn"
    return f"Already in your pipeline: {h['status']}{more}", "attn"

"""Grants.gov public API: every open federal grant, for nonprofits in any state.

No key needed. Search returns ids; the detail call returns deadline, award
range, eligibility and the full synopsis, so no AI is needed to extract them."""

import re
from ..pool import ContextPool as ThreadPoolExecutor  # keeps the organisation in worker threads
from datetime import datetime
from html import unescape

import requests

from ..config import FETCH_TIMEOUT_S

SEARCH_URL = "https://api.grants.gov/v1/api/search2"
DETAIL_URL = "https://api.grants.gov/v1/api/fetchOpportunity"
HEADERS = {"User-Agent": "GrantCompass/0.1"}
NONPROFIT_ELIGIBILITY = "12|13|25|99"  # 501(c)(3)s, other nonprofits, "others", unrestricted
MAX_DETAILS = 60


def _plain(html_text: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>", "\n", html_text or "", flags=re.I)
    return re.sub(r"[ \t]+", " ", unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def _date(value: str | None) -> str | None:
    for fmt in ("%b %d, %Y %I:%M:%S %p %Z", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.replace("EDT", "EST").replace("EST", "UTC"), fmt).date().isoformat()
        except (AttributeError, ValueError):
            continue
    m = re.match(r"([A-Z][a-z]{2} \d{1,2}, \d{4})", value or "")
    return datetime.strptime(m.group(1), "%b %d, %Y").date().isoformat() if m else None


def _int(value) -> int | None:
    try:
        n = int(float(value))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _eligible(types: list[dict]) -> bool | None:
    """True if nonprofits are named, None if only 'Others' (read the text), False otherwise."""
    descs = " ".join(t.get("description", "") for t in types).lower()
    if "nonprofit" in descs or "unrestricted" in descs:
        return True
    if "others" in descs or not types:
        return None
    return False


def search_ids(keywords: list[str]) -> list[dict]:
    hits: dict[str, dict] = {}
    for kw in keywords:
        resp = requests.post(
            SEARCH_URL,
            json={"keyword": kw, "oppStatuses": "forecasted|posted", "eligibilities": NONPROFIT_ELIGIBILITY,
                  "rows": 25},
            headers=HEADERS, timeout=FETCH_TIMEOUT_S,
        )
        resp.raise_for_status()
        for h in resp.json()["data"].get("oppHits", []):
            hits.setdefault(h["id"], h)
    return list(hits.values())


def _detail(hit: dict) -> dict | None:
    try:
        resp = requests.post(DETAIL_URL, json={"opportunityId": int(hit["id"])}, headers=HEADERS,
                             timeout=FETCH_TIMEOUT_S)
        resp.raise_for_status()
        d = resp.json()["data"]
    except (requests.RequestException, KeyError, ValueError):
        return None
    syn = d.get("synopsis") or d.get("forecast") or {}
    lo, hi = _int(syn.get("awardFloor")), _int(syn.get("awardCeiling"))
    deadline = _date(syn.get("responseDate")) or _date(hit.get("closeDate"))
    types = syn.get("applicantTypes") or []
    elig_text = _plain(syn.get("applicantEligibilityDesc", ""))
    description = _plain(syn.get("synopsisDesc") or syn.get("forecastDesc") or "")
    categories = ", ".join(c["description"] for c in syn.get("fundingActivityCategories") or [])
    agency = syn.get("agencyName") or hit.get("agency") or "Federal agency"
    award_text = (f"${lo:,} to ${hi:,}" if lo and hi else f"Up to ${hi:,}" if hi else "Not stated")
    raw = "\n".join([
        unescape(d.get("opportunityTitle", hit["title"])),
        f"Agency: {agency}",
        f"Opportunity number: {hit.get('number', '')}",
        f"Status: {hit.get('oppStatus', '')}",
        f"Deadline: {syn.get('responseDate') or 'Not stated'}. {syn.get('responseDateDesc') or ''}",
        f"Award floor: {syn.get('awardFloor') or 'Not stated'}; award ceiling: {syn.get('awardCeiling') or 'Not stated'}; "
        f"expected number of awards: {syn.get('numberOfAwards') or 'Not stated'}",
        f"Cost sharing or matching required: {'Yes' if syn.get('costSharing') else 'No'}",
        "Eligible applicants: " + "; ".join(t.get("description", "") for t in types),
        f"Additional eligibility information: {elig_text}",
        f"Categories: {categories}",
        "Description:",
        description,
    ])
    return {
        "source": "Grants.gov",
        "source_id": f"grantsgov:{hit['id']}",
        "funder": agency,
        "agency_code": hit.get("agencyCode") or "",
        "title": unescape(d.get("opportunityTitle", hit["title"])),
        "status": hit.get("oppStatus", ""),
        "deadline": deadline,
        "deadline_text": syn.get("responseDate") or ("Forecasted, not yet set" if hit.get("oppStatus") == "forecasted"
                                                      else "Not stated"),
        "award_min": lo,
        "award_max": hi,
        "award_text": award_text,
        "nonprofit_eligible": _eligible(types),
        "eligibility": [t.get("description", "") for t in types] + ([elig_text] if elig_text else []),
        "match_required": "Cost sharing required" if syn.get("costSharing") else "Not required",
        "geography": "United States (federal)",
        "categories": categories,
        "summary": description[:400],
        "url": f"https://www.grants.gov/search-results-detail/{hit['id']}",
        "raw_text": raw,
    }


def search(keywords: list[str]) -> list[dict]:
    hits = search_ids(keywords)[:MAX_DETAILS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        return [lead for lead in pool.map(_detail, hits) if lead]

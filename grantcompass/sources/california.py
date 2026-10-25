"""California Grants Portal (data.ca.gov open data). Used only when the
profile's state is California. Structured fields, no key, no AI needed."""

import json
import re

import requests

from ..config import FETCH_TIMEOUT_S

API = "https://data.ca.gov/api/3/action"
DATASET = "california-grants-portal"
HEADERS = {"User-Agent": "GrantCompass/0.1"}
STATE = "California"


def _resource_id() -> str:
    resp = requests.get(f"{API}/package_show", params={"id": DATASET}, headers=HEADERS, timeout=FETCH_TIMEOUT_S)
    resp.raise_for_status()
    return next(r["id"] for r in resp.json()["result"]["resources"] if r.get("datastore_active"))


def _amounts(text: str | None) -> tuple[int | None, int | None]:
    nums = [int(float(n.replace(",", ""))) for n in re.findall(r"\$([\d,]+(?:\.\d+)?)", text or "")]
    if not nums:
        return None, None
    if len(nums) == 1:
        return (nums[0], nums[0]) if "exactly" in (text or "").lower() else (None, nums[0])
    return min(nums), max(nums)


def _lead(r: dict) -> dict:
    lo, hi = _amounts(r.get("EstAmounts"))
    deadline = (r.get("ApplicationDeadline") or "")[:10] or None
    applicants = r.get("ApplicantType") or ""
    raw = "\n".join(f"{k}: {r.get(k)}" for k in (
        "Title", "AgencyDept", "Purpose", "Description", "ApplicantType", "ApplicantTypeNotes", "Geography",
        "EstAmounts", "EstAvailFunds", "EstAwards", "MatchingFunds", "MatchingFundsNotes", "ApplicationDeadline",
        "Categories", "GrantURL") if r.get(k))
    return {
        "source": "California Grants Portal",
        "source_id": f"cagrants:{r.get('PortalID')}",
        "funder": r.get("AgencyDept") or "State of California",
        "title": r.get("Title") or "Untitled",
        "status": r.get("Status", ""),
        "deadline": deadline if deadline and deadline[0].isdigit() else None,
        "deadline_text": r.get("ApplicationDeadline") or "Not stated",
        "award_min": lo,
        "award_max": hi,
        "award_text": r.get("EstAmounts") or "Not stated",
        "nonprofit_eligible": True if "nonprofit" in applicants.lower() else (None if not applicants else False),
        "eligibility": [applicants] + ([r["ApplicantTypeNotes"]] if r.get("ApplicantTypeNotes") else []),
        "match_required": r.get("MatchingFunds") or "Not stated",
        "geography": r.get("Geography") or "California",
        "categories": r.get("Categories") or "",
        "summary": (r.get("Purpose") or "")[:400],
        "url": r.get("GrantURL") or "https://www.grants.ca.gov/",
        "raw_text": raw,
    }


def search(keywords: list[str]) -> list[dict]:
    rid = _resource_id()
    leads: dict[str, dict] = {}
    for kw in keywords:
        resp = requests.get(
            f"{API}/datastore_search",
            params={"resource_id": rid, "q": kw, "filters": json.dumps({"Status": "active"}), "limit": 40},
            headers=HEADERS, timeout=FETCH_TIMEOUT_S,
        )
        resp.raise_for_status()
        for r in resp.json()["result"]["records"]:
            lead = _lead(r)
            leads.setdefault(lead["source_id"], lead)
    return list(leads.values())

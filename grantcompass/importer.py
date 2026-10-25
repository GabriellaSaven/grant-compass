"""Bring in one opportunity found outside Discover: an uploaded PDF or Word
document, a link, or pasted text. The Research Agent extracts the facts and
the application's questions; the Fit Agent assesses it right away, so it opens
in the same fit panel as a search result."""

import hashlib

from . import db
from .config import MAX_INPUT_CHARS
from .fit import assess
from .library import decode_upload
from .research import extract_opportunity, fetch_page
from .triage import triage


def _read(contents: str | None, filename: str | None, url: str | None, text: str | None) -> tuple[str, str, str | None]:
    """Return (text, source label, url). A file wins over a link, a link over pasted text."""
    if contents and filename:
        return decode_upload(contents, filename), f"Uploaded: {filename}", None
    if (url or "").strip():
        return fetch_page(url, user_supplied=True), "Link", url.strip()
    if (text or "").strip():
        return text.strip(), "Pasted text", None
    raise ValueError("Upload a PDF or Word document, paste a link, or paste the funder's text.")


def to_lead(opp: dict, source: str, sid: str, url: str | None) -> dict:
    named = " ".join(opp.get("eligibility") or []).lower()
    return {
        "source": source,
        "source_id": sid,
        "funder": opp.get("funder") or "Unknown funder",
        "title": opp.get("program_name") or "Untitled opportunity",
        "status": "",
        "deadline": opp.get("deadline"),
        "deadline_text": opp.get("deadline_text") or "Not stated",
        "award_min": opp.get("award_min"),
        "award_max": opp.get("award_max"),
        "award_text": opp.get("award_text") or "Not stated",
        "nonprofit_eligible": True if ("501(c)(3)" in named or "nonprofit" in named) else None,
        "eligibility": opp.get("eligibility") or [],
        "match_required": opp.get("matched_funding") or "Not stated",
        "geography": opp.get("geography"),
        "categories": opp.get("focus_area") or "",
        "summary": opp.get("summary") or "",
        "url": url,
        "raw_text": opp.get("raw_text") or "",
        "suspicious": opp.get("suspicious_content") or [],
        "opportunity": opp,
    }


def import_and_assess(contents=None, filename=None, url=None, text=None) -> dict:
    """Return a lead (with triage and extraction usage); its assessment is saved under the lead's id."""
    raw, source, url = _read(contents, filename, url, text)
    truncated = len(raw) > MAX_INPUT_CHARS
    raw = raw[:MAX_INPUT_CHARS]
    sid = "import:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    ext = extract_opportunity(raw, url)
    opp = ext["opportunity"]
    lead = to_lead(opp, source, sid, url)
    prof = (db.get_profile() or {"data": {}})["data"]
    lead["triage"] = triage(lead, prof)
    lead["extract_usage"] = ext["usage"]
    lead["truncated"] = truncated

    if not db.get_lead_assessment(sid):  # the same document imported twice is not assessed twice
        res = assess(opp)
        db.save_lead_assessment(sid, res["result"], res["usage"])
    return lead

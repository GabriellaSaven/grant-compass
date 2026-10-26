"""Fill in a new organisation's profile from its public website.

The Research Agent reads the homepage and up to five key pages (about, mission, programmes, impact, team,
financials), respecting robots.txt. For every profile field it can fill, it must quote the exact words on
the site; code checks each quote and each answer choice, and only fills fields that are still empty, so
nothing the user typed is ever overwritten. The pages are saved as source documents for the writers."""

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from . import db
from .config import FETCH_TIMEOUT_S, MAX_FETCH_BYTES, PROMPTS_DIR
from .fit import quote_found
from .llm import log_run, run_agent, usage_dict
from .profile import FIELDS
from .netsafe import check_public, safe_get
from .research import USER_AGENT, allowed_by_robots, fetch_page

KEY_PAGES = re.compile(r"about|mission|who-we-are|our-story|program|what-we-do|our-work|services|impact|"
                       r"results|annual|report|team|staff|leadership|board|financ|history", re.I)
SKIP = re.compile(r"/blog/|/news/|/press/|/events?/|/wp-content/|\.(pdf|docx?|jpe?g|png)$|login|donate|cart", re.I)
MAX_PAGES, MAX_CHARS = 6, 32_000


class FieldValue(BaseModel):
    key: str = Field(description="A profile field key from the list given.")
    value: str = Field(description="The value. Numbers as plain digits; for multi-choice fields, choices "
                                   "separated by '; '; for choice fields, one choice copied exactly.")
    quote: str = Field(description="The exact words on the website that support it, copied word for word.")


class ProfileFromWebsite(BaseModel):
    fields: list[FieldValue]
    not_found: list[str] = Field(description="Field keys the website doesn't answer.")


def _same_site(a: str, b: str) -> bool:
    return urlparse(a).netloc.replace("www.", "") == urlparse(b).netloc.replace("www.", "")


def find_pages(url: str) -> list[str]:
    """The homepage plus the most informative pages it links to."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    check_public(url)
    if not allowed_by_robots(url):
        raise ValueError("This website asks automated tools not to read it (robots.txt). Fill the profile by hand.")
    resp = safe_get(url, FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content[:MAX_FETCH_BYTES], "html.parser")
    found = []
    for a in soup.find_all("a", href=True):
        link = urljoin(resp.url, a["href"]).split("#")[0].rstrip("/")
        if SKIP.search(link) and not re.search(r"annual|impact.?report", link, re.I):
            continue  # blog posts, news and stray files say little about the organisation itself
        if _same_site(link, resp.url) and link != resp.url.rstrip("/") and link not in found and \
                (KEY_PAGES.search(link) or KEY_PAGES.search(a.get_text(" ", strip=True))):
            found.append(link)
    return [resp.url] + found[: MAX_PAGES - 1]


def read_site(url: str) -> list[dict]:
    pages = []
    for link in find_pages(url):
        try:
            text = fetch_page(link, user_supplied=True)  # the user gave us this website; robots.txt still applies
        except Exception:
            continue  # skip pages that are blocked, empty or slow; use the rest
        title = urlparse(link).path.strip("/").split("/")[-1].replace("-", " ").title() or "Home"
        pages.append({"url": link, "title": title, "text": text[:8000]})
    if not pages:
        raise ValueError("No readable text came back from that website (it may need JavaScript).")
    return pages


def _field_list() -> str:
    lines = []
    for key, (label, kind, opts, help_) in FIELDS.items():
        if key in ("legal_name",):
            continue
        choice = f" — choose from: {', '.join(opts)}" if opts else ""
        lines.append(f"- {key} ({label}; {kind}){choice}")
    return "\n".join(lines)


def _coerce(key: str, value: str):
    """The model's text as the form's type; None if it isn't a valid answer."""
    _, kind, opts, _ = FIELDS[key]
    value = (value or "").strip()
    if not value:
        return None
    if kind == "number":
        digits = re.sub(r"[^\d.]", "", value.replace(",", ""))
        try:
            return int(float(digits)) if digits else None
        except ValueError:
            return None
    if kind == "select":
        return next((o for o in opts if o.lower() == value.lower()), None)
    if kind == "multi":
        picked = [o for o in opts if o.lower() in {v.strip().lower() for v in value.split(";")}]
        return picked or None
    return value


def fill_from_website(url: str) -> dict:
    """Read the site, extract what it supports, verify, fill empty fields. Returns a summary for the UI."""
    pages = read_site(url)
    corpus = "\n\n".join(f"<page url='{p['url']}'>\n{p['text']}\n</page>" for p in pages)[:MAX_CHARS]
    run = run_agent(ProfileFromWebsite, (PROMPTS_DIR / "profile_from_website.md").read_text(encoding="utf-8"),
                    f"Profile fields:\n{_field_list()}\n\n<website untrusted='true'>\n{corpus}\n</website>",
                    agent="research_agent")
    usage = usage_dict(run.usage)
    prof = (db.get_profile() or {"data": {}})["data"]
    filled, unverified, invalid = [], 0, 0
    for f in run.output.fields:
        if f.key not in FIELDS or f.key == "legal_name" or prof.get(f.key):
            continue  # unknown field, or the user already answered it
        if not quote_found(f.quote, corpus):
            unverified += 1  # never fill a field from words that aren't on the site
            continue
        value = _coerce(f.key, f.value)
        if value is None:
            invalid += 1
            continue
        prof[f.key] = value
        filled.append(f.key)
    prof["website"] = prof.get("website") or url
    prof["_from_website"] = sorted(set(prof.get("_from_website", []) + filled))
    db.save_profile(prof)
    for p in pages:  # the writers may cite the website like any other document
        db.add_document(f"Website: {p['title']}", "Other", f"Source: {p['url']}\n\n{p['text']}")
    log_run("research_agent", usage, {"task": "profile_from_website", "filled": len(filled),
                                      "unverified": unverified})
    return {"filled": [FIELDS[k][0] for k in filled], "unverified": unverified, "invalid": invalid,
            "pages": [p["url"] for p in pages], "usage": usage}

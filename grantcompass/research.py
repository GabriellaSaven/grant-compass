"""Research Agent: fetches a funder page from an approved source (or takes
pasted text) and extracts the opportunity into structured fields.

It only extracts. Judging fit is the Fit Agent's job."""

from functools import lru_cache
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .config import APPROVED_SOURCES, FETCH_TIMEOUT_S, MAX_FETCH_BYTES, MAX_INPUT_CHARS, PROMPTS_DIR
from .llm import log_run, run_agent, usage_dict
from .netsafe import check_public, safe_get
from .models import OpportunityExtract

INSTRUCTIONS = (PROMPTS_DIR / "research_agent.md").read_text(encoding="utf-8")


def is_approved(url: str) -> bool:
    """Built-in sources, the foundation directory, and every funder site the team follows."""
    from . import db

    host = (urlparse(url).hostname or "").lower()
    approved = set(APPROVED_SOURCES) | db.watch_domains() | db.directory_domains()
    return any(host == d or host.endswith("." + d) for d in approved)


USER_AGENT = "GrantCompass/0.1"


@lru_cache(maxsize=64)
def _robots(origin: str) -> RobotFileParser:
    rp = RobotFileParser()
    try:
        resp = safe_get(f"{origin}/robots.txt", FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT})
        rp.parse(resp.text.splitlines() if resp.ok else [])
    except (requests.RequestException, ValueError):  # unreachable or private: fetch_page refuses private ones
        rp.parse([])
    return rp


def allowed_by_robots(url: str) -> bool:
    p = urlparse(url)
    return _robots(f"{p.scheme}://{p.netloc}").can_fetch(USER_AGENT, url)


def fetch_page(url: str, user_supplied: bool = False) -> str:
    """Download a page and return its visible text. Automatic checks (watchlist) only read approved sites;
    a link the user pastes in themselves counts as their approval. robots.txt is respected either way.
    Links straight to a PDF or Word file are read as documents."""
    from .library import extract_text

    url = url.strip()
    check_public(url)  # public websites only: never this computer or a private network
    if not user_supplied and not is_approved(url):
        raise ValueError("That site is not approved yet. Add the funder to your watchlist, or paste the text.")
    if not allowed_by_robots(url):
        raise ValueError(
            "This website asks automated tools not to read this page (its robots.txt rules), and Grant Compass "
            "respects that. Search-results pages are often blocked. Try the funder's main grants or how-to-apply "
            "page, or copy the text from the page and paste it instead."
        )
    resp = safe_get(url, FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}, stream=True,
                    allow=None if user_supplied else is_approved)  # every redirect is checked too
    resp.raise_for_status()
    body = resp.raw.read(MAX_FETCH_BYTES, decode_content=True)
    ctype = resp.headers.get("content-type", "").lower()
    path = urlparse(url).path.lower()
    if "pdf" in ctype or path.endswith(".pdf"):
        return extract_text("link.pdf", body).strip()[:MAX_INPUT_CHARS]
    if "wordprocessingml" in ctype or path.endswith(".docx"):
        return extract_text("link.docx", body).strip()[:MAX_INPUT_CHARS]
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    if len(text) < 200:
        raise ValueError("Very little text came back from that page (it may need JavaScript). Paste the text instead.")
    return text[:MAX_INPUT_CHARS]


def extract_opportunity(text: str, source_url: str | None = None) -> dict:
    """Return {opportunity, usage}. `opportunity` is ready for db.add_opportunity."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Paste the funder's text or import a page first.")
    if len(text) > MAX_INPUT_CHARS:
        raise ValueError(f"That text is too long ({len(text):,} characters; limit {MAX_INPUT_CHARS:,}).")
    prompt = (
        f"Source URL: {source_url or 'provided by the user'}\n\n"
        f'<funder_page untrusted="true">\n{text}\n</funder_page>'
    )
    run = run_agent(OpportunityExtract, INSTRUCTIONS, prompt, agent="research_agent")
    usage = usage_dict(run.usage)
    opp = run.output.model_dump()
    opp["deadline"] = opp.pop("deadline_iso")
    opp["source_url"] = source_url
    opp["raw_text"] = text
    # Keep only questions that really appear in the document (word for word).
    from .fit import quote_found

    found = [q for q in opp["questions"] if quote_found(q["prompt"], text)]
    opp["questions_dropped"] = len(opp["questions"]) - len(found)
    opp["questions"] = found
    log_run("research_agent", usage, {"funder": opp["funder"]})
    return {"opportunity": opp, "usage": usage}

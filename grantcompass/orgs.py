"""Organisations and accounts. Each organisation has its own SQLite database and its own log folder, so
grants, documents, answers and AI usage never mix between organisations.

- Demo organisations: six fictional nonprofits graders can open without a password. Riverbend Reads is
  built in (grantcompass/seed.py); the other five are data/demo_orgs/<slug>.json.
- Accounts: email + password (stored only as a salted hash), each with its own organisation.

The app is a local, single-user tool, so the signed-in organisation is switched per request
(app.py sets it from the session cookie before every request)."""

import json
import re
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from . import db, llm
from .config import ROOT

DATA = ROOT / "data"
DEMO_DIR = DATA / "demo_orgs"
ORG_DIR = DATA / "orgs"
LOG_ROOT = ROOT / "logs"
ACCOUNTS_DB = DATA / "accounts.db"
RIVERBEND = {"slug": "riverbend-reads", "name": "Riverbend Reads", "location": "Dayton, Ohio",
             "cause": "Early literacy", "tagline": "One-on-one reading tutoring for K-3 students and their families."}


# --- Where each organisation's data lives ------------------------------------------------------
def db_path(slug: str) -> Path:
    # Riverbend keeps the original file, so existing work carries over.
    return DATA / "grantcompass.db" if slug == RIVERBEND["slug"] else ORG_DIR / f"{slug}.db"


def log_dir(slug: str) -> Path:
    return LOG_ROOT if slug == RIVERBEND["slug"] else LOG_ROOT / slug


def activate(slug: str) -> None:
    """Point the database and the usage logs at this organisation (creating and seeding it if new)."""
    db.use(db_path(slug))
    llm.use_logs(log_dir(slug))
    ensure(slug)


# --- Demo organisations ------------------------------------------------------------------------
def demo_files() -> dict[str, dict]:
    out = {}
    for p in sorted(DEMO_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        out[d["slug"]] = d
    return out


def demos() -> list[dict]:
    """Cards for the login page: Riverbend first, then the others."""
    cards = [RIVERBEND] + [{k: d[k] for k in ("slug", "name", "location", "cause", "tagline")}
                           for d in demo_files().values()]
    for c in cards:
        c["focus"] = (demo_files().get(c["slug"], {}).get("profile", {}).get("focus_areas")
                      or ["Literacy", "K-12 education", "Early childhood"])
    return cards


def is_demo(slug: str) -> bool:
    return slug == RIVERBEND["slug"] or slug in demo_files()


_ready: set[str] = set()


def ensure(slug: str) -> None:
    """Create the organisation's database the first time it's opened; demos are filled with sample data."""
    if slug in _ready and db.path().exists():
        return
    from . import directory, seed
    from .fit import refresh_stored

    new = db.init_db()
    if slug == RIVERBEND["slug"]:
        if new:
            seed.seed()
        if db.get_profile() is None:
            seed.seed_profile()
        if not db.list_questions():
            seed.seed_questions()
        if not db.list_team():
            seed.seed_team()
    elif new and slug in demo_files():
        seed_demo(demo_files()[slug])
    if slug in demo_files() or slug == RIVERBEND["slug"]:
        _ensure_outcomes(slug)  # won / lost history, also added to demos created before it existed
        _ensure_comments()
    directory.sync()  # the built-in list of major foundations, per organisation
    refresh_stored()
    from .fit import reverify_stored
    reverify_stored()  # quotes saved under the old check, re-checked where the funder text is kept
    _ready.add(slug)


def reset_demo(slug: str) -> None:
    """Throw away a demo's changes: the next visit rebuilds it from the sample data."""
    if is_demo(slug):
        db_path(slug).unlink(missing_ok=True)
        _ready.discard(slug)


def seed_demo(d: dict) -> None:
    """Fill a new database from a demo JSON file. Deadlines are relative to today."""
    from .answers import classify
    from .pipeline import workback_plan

    today = date.today()
    for doc in d["documents"]:
        db.add_document(doc["title"], doc["doc_type"], doc["content"], approved=doc.get("approved", False),
                        sample=True)
    db.save_profile(d["profile"])
    team = [db.add_member(name, role) for name, role in d["team"]]
    for o in d["opportunities"]:
        deadline = today + timedelta(days=o["deadline_days"])
        opp = {k: o[k] for k in ("funder", "program_name", "geography", "focus_area", "award_min", "award_max",
                                 "award_text", "eligibility", "restrictions", "requirements", "matched_funding",
                                 "reporting", "summary", "raw_text")}
        opp.update(deadline=deadline.isoformat(), deadline_text=deadline.strftime("%B %-d, %Y"), source_url=None,
                   origin="Sample data")
        owner = team[o["owner_index"]] if o.get("owner_index") is not None else None
        opp_id = db.add_opportunity(opp, status=o["status"], owner=owner, sample=True)
        if o.get("decision"):
            db.update_opportunity(opp_id, decision=o["decision"], decision_reason="Sample data")
            plan = workback_plan(deadline, today=deadline - timedelta(days=14))
            db.add_tasks(opp_id, [(t, due, i < o.get("tasks_done", 0)) for i, (t, due) in enumerate(plan)])
        for q in o.get("questions") or []:
            q_id = db.add_question(opp_id, q["prompt"], q["limit_type"], q["limit_value"], q.get("answer") or "")
            db.set_question_status(q_id, q.get("status") or ("Drafting" if q.get("answer") else "Not started"))
    for a in d.get("library_answers") or []:
        db.save_answer(a["question"], a["answer"], classify(a["question"]), a.get("funder"))


def _ensure_comments() -> None:
    """Two sample comment threads on the first written answer, so teammates' comments can be tried at once."""
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM comments LIMIT 1").fetchone():
            return
    team = [m["label"] for m in db.list_team()]
    q = next((q for q in db.list_questions() if q["response"].strip()), None)
    if not q or len(team) < 3:
        return
    first = re.split(r"(?<=[.!?])\s+", q["response"].strip())[0]
    t1 = db.add_comment(q["id"], f"Can you check this against our latest impact report before we submit? I'm "
                                 f"not sure we can back it up. @{team[1].split()[0]}", team[0], first, team[1])
    db.add_comment(q["id"], "On it. I'll confirm the figures with programme staff today.", team[1], parent_id=t1)
    t2 = db.add_comment(q["id"], "Could we open with a student's story here instead? Funders remember people.",
                        team[2], None, None)
    db.set_comment_resolved(t2, True)


def _ensure_outcomes(slug: str) -> None:
    if any(o["status"] in ("Won", "Lost") for o in db.list_opportunities()):
        return
    if slug == RIVERBEND["slug"]:
        outcomes = json.loads((DATA / "sample" / "riverbend_outcomes.json").read_text())
    else:
        outcomes = demo_files()[slug].get("outcomes") or []
    seed_outcomes(outcomes)


def seed_outcomes(outcomes: list[dict]) -> None:
    """Past results: won grants (with reporting requirements, report sections and a programme report in the
    source documents) and lost grants (with the funder's feedback). Dates are relative to today."""
    from .pipeline import workback_plan

    today = date.today()
    team = [m["label"] for m in db.list_team()]
    for o in outcomes:
        won = o["result"] == "Won"
        decided = today - timedelta(days=o["decided_days_ago"])
        deadline = decided - timedelta(days=45)
        amount = o.get("amount_awarded") if won else o.get("amount_requested")
        opp = {k: o.get(k) for k in ("funder", "program_name", "geography", "focus_area", "summary", "raw_text")}
        opp.update(deadline=deadline.isoformat(), deadline_text=deadline.strftime("%B %-d, %Y"), award_min=None,
                   award_max=amount, award_text=f"${amount:,} {'awarded' if won else 'requested'}",
                   eligibility=[], restrictions=[], requirements=[], matched_funding="Not stated",
                   reporting="Interim and final reports" if won else "", source_url=None, origin="Sample data")
        owner = team[o["owner_index"]] if o.get("owner_index") is not None and o["owner_index"] < len(team) else None
        opp_id = db.add_opportunity(opp, status=o["result"], owner=owner, sample=True)
        db.update_opportunity(opp_id, decision="Go", decision_reason="Sample data", result_date=decided.isoformat(),
                              awarded_amount=amount if won else None, lost_reason=o.get("lost_reason"),
                              grant_period=o.get("grant_period"), reporting_requirements=o.get("reporting_requirements"),
                              report_due=(today + timedelta(days=o["report_due_days"])).isoformat()
                              if won and o.get("report_due_days") is not None else None)
        db.add_tasks(opp_id, [(t, d, True) for t, d in workback_plan(deadline, today=deadline - timedelta(days=14))])
        if won:
            for sec in o.get("report_sections") or []:
                db.add_question(opp_id, sec["prompt"], sec["limit_type"], sec["limit_value"], kind="report")
            if o.get("program_report"):
                db.add_document(o["program_report"]["title"], "Programme report", o["program_report"]["content"],
                                sample=True)


# --- Accounts ----------------------------------------------------------------------------------
def _accounts():
    ACCOUNTS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ACCOUNTS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, "
                 "name TEXT NOT NULL, org_name TEXT NOT NULL, slug TEXT NOT NULL, password_hash TEXT NOT NULL, "
                 "created TEXT NOT NULL)")
    return conn


EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_account(name: str, email: str, password: str, org_name: str, state: str | None,
                   website: str | None = None) -> dict:
    name, email, org_name = (name or "").strip(), (email or "").strip().lower(), (org_name or "").strip()
    if not (name and org_name):
        raise ValueError("Enter your name and your organisation's name.")
    if not EMAIL.match(email):
        raise ValueError("Enter a valid email address.")
    if len(password or "") < 8:
        raise ValueError("Use a password of at least 8 characters.")
    with _accounts() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise ValueError("There's already an account with that email. Log in instead.")
        slug = "org-" + re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-")[:30]
        n = conn.execute("SELECT COUNT(*) FROM users WHERE slug LIKE ?", (slug + "%",)).fetchone()[0]
        slug = f"{slug}-{n + 1}" if n else slug
        conn.execute("INSERT INTO users (email, name, org_name, slug, password_hash, created) VALUES (?,?,?,?,?,?)",
                     (email, name, org_name, slug, generate_password_hash(password),
                      datetime.now().isoformat(timespec="seconds")))
    activate(slug)  # a new, empty organisation: only what the user entered
    website = (website or "").strip()
    if website and not website.startswith(("http://", "https://")):
        website = "https://" + website
    # A website is read on the Welcome page (it takes a few seconds), so sign-up stays instant.
    db.save_profile({"legal_name": org_name, "state": state or "", "website": website,
                     "_import_pending": bool(website)})
    db.add_member(name, "Account owner")
    return {"email": email, "name": name, "org_name": org_name, "slug": slug}


# Password guessing: after MAX_FAILED_LOGINS wrong passwords for one email within LOCKOUT_S, that email is
# locked for the rest of the window, even with the right password. Kept in memory (one local server process).
MAX_FAILED_LOGINS = 5
LOCKOUT_S = 15 * 60
_failed: dict[str, list[float]] = {}
_failed_lock = threading.Lock()


def _recent_failures(email: str, now: float) -> list[float]:
    times = [t for t in _failed.get(email, []) if now - t < LOCKOUT_S]
    _failed[email] = times
    return times


def login(email: str, password: str) -> dict:
    email = (email or "").strip().lower()
    now = time.time()
    with _failed_lock:
        times = _recent_failures(email, now)
        if len(times) >= MAX_FAILED_LOGINS:
            minutes = max(1, round((LOCKOUT_S - (now - times[0])) / 60))
            raise ValueError(f"Too many wrong passwords for this email. For your security, try again in "
                             f"{minutes} minute{'s' if minutes != 1 else ''}.")
    with _accounts() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    # Check a hash even for unknown emails, so the response time doesn't reveal which emails have accounts.
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password or "") and row is not None
    with _failed_lock:
        if not ok:
            _failed.setdefault(email, []).append(now)
            raise ValueError("That email and password don't match an account.")
        _failed.pop(email, None)
    return dict(row)


_DUMMY_HASH = generate_password_hash("not-a-real-password")


def org_name(slug: str) -> str:
    if slug == RIVERBEND["slug"]:
        return RIVERBEND["name"]
    if slug in demo_files():
        return demo_files()[slug]["name"]
    with _accounts() as conn:
        row = conn.execute("SELECT org_name FROM users WHERE slug = ?", (slug,)).fetchone()
    return row["org_name"] if row else slug


# --- Your data: download it, delete it -----------------------------------------------------------
def export_data(slug: str) -> dict:
    """Everything stored for this organisation, as JSON: every table in its database, its AI usage log, and
    the account details (never the password hash)."""
    out = {"organisation": org_name(slug), "exported": datetime.now().isoformat(timespec="seconds"), "tables": {}}
    with db.connect() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        for t in tables:
            out["tables"][t] = [dict(r) for r in conn.execute(f"SELECT * FROM {t}")]
    usage = log_dir(slug) / "usage.jsonl"
    out["ai_usage_log"] = [json.loads(x) for x in usage.read_text().splitlines()] if usage.exists() else []
    with _accounts() as conn:
        row = conn.execute("SELECT email, name, org_name, created FROM users WHERE slug = ?", (slug,)).fetchone()
    out["account"] = dict(row) if row else None
    return out


def delete_account(slug: str) -> None:
    """Permanently delete an account and everything stored for its organisation (database and logs)."""
    import shutil

    if is_demo(slug):
        raise ValueError("Demo organisations can't be deleted; use Reset this demo instead.")
    with _accounts() as conn:
        conn.execute("DELETE FROM users WHERE slug = ?", (slug,))
    db_path(slug).unlink(missing_ok=True)
    folder = log_dir(slug)
    if folder != LOG_ROOT and folder.exists():
        shutil.rmtree(folder)
    _ready.discard(slug)

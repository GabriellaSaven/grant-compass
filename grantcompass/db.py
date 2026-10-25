"""SQLite storage: the organisation library, opportunities, assessments and
pipeline tasks. One local file, created and seeded with sample data on first run."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

import contextvars

from .config import DB_PATH

# Which organisation's database this request uses. A context variable, not a global: two tabs (or two
# people) on different organisations must never read or write each other's data. Falls back to DB_PATH
# (the tests and command-line scripts set that directly).
_db_path: contextvars.ContextVar = contextvars.ContextVar("db_path", default=None)


def path():
    return _db_path.get() or DB_PATH


def use(db_file) -> None:
    _db_path.set(db_file)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    content TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0,
    sample INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY,
    funder TEXT NOT NULL,
    program_name TEXT NOT NULL,
    deadline TEXT,                -- ISO date, or NULL if rolling / unknown
    deadline_text TEXT,
    geography TEXT,
    focus_area TEXT,
    award_min INTEGER,
    award_max INTEGER,
    award_text TEXT,
    eligibility TEXT,             -- JSON list
    restrictions TEXT,            -- JSON list
    requirements TEXT,            -- JSON list
    matched_funding TEXT,
    reporting TEXT,
    summary TEXT,
    source_url TEXT,
    raw_text TEXT,
    status TEXT NOT NULL DEFAULT 'Researching',
    owner TEXT,
    decision TEXT,                -- the human's final call: Go / Research further / No-Go
    decision_reason TEXT,
    sample INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    result TEXT NOT NULL,         -- JSON: the agent output plus computed fit score
    usage TEXT NOT NULL,          -- JSON
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- one organisation per workspace
    data TEXT NOT NULL,           -- JSON: field key -> value
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    name TEXT,
    added TEXT NOT NULL,
    last_checked TEXT,
    content_hash TEXT,            -- page text hash: unchanged pages are not re-read by the AI
    result TEXT                   -- JSON: last extracted opportunity
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    position INTEGER NOT NULL DEFAULT 0,
    prompt TEXT NOT NULL,
    limit_type TEXT,              -- 'words' or 'characters', or NULL for no limit
    limit_value INTEGER,
    response TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Not started',  -- Not started / Drafting / Reviewed / Approved
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    text TEXT NOT NULL,
    origin TEXT NOT NULL,         -- 'you' or 'AI draft (accepted by you)'
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    kind TEXT NOT NULL,           -- 'draft', 'coach' or 'evidence'
    result TEXT NOT NULL,         -- JSON
    usage TEXT NOT NULL,          -- JSON
    response_text TEXT NOT NULL,  -- the answer the review was based on
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lead_assessments (
    source_id TEXT PRIMARY KEY,   -- e.g. grantsgov:361754: a search result assessed before it is saved
    result TEXT NOT NULL,         -- JSON: Fit Agent output + computed score
    usage TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS team (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    added TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS directory (
    url TEXT PRIMARY KEY,         -- built-in list of major foundations (data/funder_directory.json)
    n INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    last_checked TEXT,
    content_hash TEXT,            -- unchanged pages are not re-read by the AI
    result TEXT                   -- JSON: last extracted opportunity
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    title TEXT NOT NULL,
    due TEXT NOT NULL,            -- ISO date
    done INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS comments (     -- teammates' comments on the words of an answer, Google Docs-style
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL,
    parent_id INTEGER,                     -- set on replies; NULL for the comment that starts a thread
    quote TEXT,                            -- the words the comment is about (threads only)
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    assignee TEXT,                         -- the teammate asked to act on it, if anyone
    resolved INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS director_reports (  -- the Executive Director's health reviews
    id INTEGER PRIMARY KEY,
    result TEXT NOT NULL,                  -- JSON: verified findings + what was removed
    usage TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (       -- the Answer Library: approved answers to reuse
    id INTEGER PRIMARY KEY,
    question TEXT NOT NULL,
    text TEXT NOT NULL,
    topic TEXT NOT NULL,
    funder TEXT,
    question_id INTEGER,                   -- the application question it came from, if any
    created TEXT NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0,
    last_used TEXT
);
"""

JSON_FIELDS = ("eligibility", "restrictions", "requirements")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> bool:
    """Create tables. Returns True if the database was empty (needs seeding)."""
    path().parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0


OUTCOME_COLUMNS = {"awarded_amount": "INTEGER", "result_date": "TEXT", "grant_period": "TEXT", "report_due": "TEXT",
                   "reporting_requirements": "TEXT", "lost_reason": "TEXT"}


def _migrate(conn) -> None:
    """Add columns introduced after a database was first created, and backfill them."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(opportunities)")}
    if "origin" not in cols:
        conn.execute("ALTER TABLE opportunities ADD COLUMN origin TEXT")
        conn.execute("UPDATE opportunities SET origin = 'Sample data' WHERE sample = 1")
        conn.execute("UPDATE opportunities SET origin = 'Found via Grants.gov' "
                     "WHERE origin IS NULL AND source_url LIKE '%grants.gov%'")
        conn.execute("UPDATE opportunities SET origin = 'Added from URL' WHERE origin IS NULL AND source_url IS NOT NULL")
        conn.execute("UPDATE opportunities SET origin = 'Added manually' WHERE origin IS NULL")
    # Grant outcomes and reporting (won / lost grants).
    for col, kind in OUTCOME_COLUMNS.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE opportunities ADD COLUMN {col} {kind}")
    qcols = {r["name"] for r in conn.execute("PRAGMA table_info(questions)")}
    if "kind" not in qcols:  # 'application' questions, or 'report' sections owed to a funder after a win
        conn.execute("ALTER TABLE questions ADD COLUMN kind TEXT NOT NULL DEFAULT 'application'")


# --- Comments -------------------------------------------------------------------
def add_comment(question_id: int, body: str, author: str, quote: str | None = None, assignee: str | None = None,
                parent_id: int | None = None) -> int:
    with connect() as conn:
        cur = conn.execute("INSERT INTO comments (question_id, parent_id, quote, body, author, assignee, created) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (question_id, parent_id, quote, body, author, assignee, _now()))
        if parent_id:  # a reply re-opens a resolved thread, like Google Docs
            conn.execute("UPDATE comments SET resolved = 0 WHERE id = ?", (parent_id,))
        return cur.lastrowid


def list_comments(question_id: int) -> list[dict]:
    """Threads (newest first) with their replies (oldest first)."""
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM comments WHERE question_id = ? ORDER BY id",
                                              (question_id,))]
    threads = [r for r in rows if not r["parent_id"]]
    for t in threads:
        t["replies"] = [r for r in rows if r["parent_id"] == t["id"]]
    return sorted(threads, key=lambda t: (t["resolved"], -t["id"]))


def set_comment_resolved(comment_id: int, resolved: bool) -> None:
    with connect() as conn:
        conn.execute("UPDATE comments SET resolved = ? WHERE id = ?", (int(resolved), comment_id))


def open_asks() -> list[dict]:
    """Unresolved comment threads, with where they are, for Home and the assistant."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.*, q.prompt, q.kind, q.opportunity_id, o.funder, o.program_name, "
            "(SELECT COUNT(*) FROM comments r WHERE r.parent_id = c.id) AS replies "
            "FROM comments c JOIN questions q ON q.id = c.question_id "
            "JOIN opportunities o ON o.id = q.opportunity_id "
            "WHERE c.parent_id IS NULL AND c.resolved = 0 ORDER BY c.id DESC").fetchall()
    return [dict(r) for r in rows]


def open_comment_counts(opp_id: int) -> dict[int, int]:
    with connect() as conn:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT c.question_id, COUNT(*) FROM comments c JOIN questions q ON q.id = c.question_id "
            "WHERE q.opportunity_id = ? AND c.parent_id IS NULL AND c.resolved = 0 GROUP BY c.question_id",
            (opp_id,))}


# --- Executive Director ---------------------------------------------------------
def save_director_report(result: dict, usage: dict) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO director_reports (result, usage, created) VALUES (?, ?, ?)",
                     (json.dumps(result), json.dumps(usage), _now()))


def list_director_reports() -> list[dict]:
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM director_reports ORDER BY id DESC")]
    for r in rows:
        r["result"], r["usage"] = json.loads(r["result"]), json.loads(r["usage"])
    return rows


# --- Answer Library -----------------------------------------------------------
def save_answer(question: str, text: str, topic: str, funder: str | None = None,
                question_id: int | None = None) -> tuple[int, bool]:
    """Add an approved answer, or update the one already saved from the same application question.
    Returns (id, created)."""
    with connect() as conn:
        row = conn.execute("SELECT id FROM answers WHERE question_id = ?", (question_id,)).fetchone() \
            if question_id else None
        if row:
            conn.execute("UPDATE answers SET question = ?, text = ?, topic = ?, funder = ?, created = ? WHERE id = ?",
                         (question, text, topic, funder, _now(), row["id"]))
            return row["id"], False
        cur = conn.execute("INSERT INTO answers (question, text, topic, funder, question_id, created) "
                           "VALUES (?, ?, ?, ?, ?, ?)", (question, text, topic, funder, question_id, _now()))
        return cur.lastrowid, True


def list_answers() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM answers ORDER BY created DESC")]


def get_answer(answer_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM answers WHERE id = ?", (answer_id,)).fetchone()
        return dict(row) if row else None


def delete_answer(answer_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM answers WHERE id = ?", (answer_id,))


def mark_answer_used(answer_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE answers SET uses = uses + 1, last_used = ? WHERE id = ?", (_now(), answer_id))


# --- Documents ----------------------------------------------------------------
def add_document(title: str, doc_type: str, content: str, approved: bool = False, sample: bool = False) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO documents (title, doc_type, content, approved, sample, created) VALUES (?, ?, ?, ?, ?, ?)",
            (title, doc_type, content, int(approved), int(sample), _now()),
        )
        return cur.lastrowid


def list_documents() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM documents ORDER BY approved DESC, doc_type, title")]


def set_document_approved(doc_id: int, approved: bool) -> None:
    with connect() as conn:
        conn.execute("UPDATE documents SET approved = ? WHERE id = ?", (int(approved), doc_id))


def delete_document(doc_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# --- Profile -------------------------------------------------------------------
def get_profile() -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT data, updated FROM profile WHERE id = 1").fetchone()
    return {"data": json.loads(row["data"]), "updated": row["updated"]} if row else None


def save_profile(data: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO profile (id, data, updated) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated = excluded.updated",
            (json.dumps(data), _now()),
        )


# --- Watchlist -----------------------------------------------------------------
def list_watchlist() -> list[dict]:
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM watchlist ORDER BY added")]
    for r in rows:
        r["result"] = json.loads(r["result"]) if r["result"] else None
    return rows


def add_watch(url: str, name: str | None) -> None:
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO watchlist (url, name, added) VALUES (?, ?, ?)", (url, name, _now()))


def remove_watch(watch_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE id = ?", (watch_id,))


def update_watch(watch_id: int, content_hash: str, result: dict) -> None:
    with connect() as conn:
        conn.execute("UPDATE watchlist SET last_checked = ?, content_hash = ?, result = ? WHERE id = ?",
                     (_now(), content_hash, json.dumps(result), watch_id))


def watch_domains() -> set[str]:
    from urllib.parse import urlparse

    return {(urlparse(w["url"]).hostname or "").removeprefix("www.") for w in list_watchlist()}


# --- Team -------------------------------------------------------------------------
def member_label(name: str, role: str) -> str:
    """How a person is shown and stored as the responsible person, e.g. 'Sam Ortiz (Grants Manager)'."""
    return f"{name} ({role})" if role else name


def list_team() -> list[dict]:
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM team ORDER BY name")]
    for r in rows:
        r["label"] = member_label(r["name"], r["role"])
    return rows


def add_member(name: str, role: str = "") -> str:
    name, role = (name or "").strip(), (role or "").strip()
    if not name:
        raise ValueError("Enter a name.")
    label = member_label(name, role)
    if any(m["name"].strip().lower() == name.lower() for m in list_team()):  # same person, any role
        raise ValueError(f"{name} is already on the team.")
    with connect() as conn:
        conn.execute("INSERT INTO team (name, role, added) VALUES (?, ?, ?)", (name, role, _now()))
    return label


def remove_member(member_id: int) -> None:
    """Grants already assigned keep the name, so history isn't lost."""
    with connect() as conn:
        conn.execute("DELETE FROM team WHERE id = ?", (member_id,))


# --- Foundation directory ---------------------------------------------------------
def sync_directory(entries: list[dict]) -> None:
    """Add any usable directory entries not yet in the table (keeps earlier check results)."""
    with connect() as conn:
        conn.executemany("INSERT OR IGNORE INTO directory (url, n, name, type) VALUES (?, ?, ?, ?)",
                         [(e["url"], e["n"], e["name"], e["type"]) for e in entries if e.get("usable")])


def list_directory() -> list[dict]:
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM directory ORDER BY n")]
    for r in rows:
        r["result"] = json.loads(r["result"]) if r["result"] else None
    return rows


def update_directory(url: str, content_hash: str, result: dict, checked: str | None = None) -> None:
    with connect() as conn:
        conn.execute("UPDATE directory SET last_checked = ?, content_hash = ?, result = ? WHERE url = ?",
                     (checked or _now(), content_hash, json.dumps(result), url))


def mark_directory_checked(url: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE directory SET last_checked = ? WHERE url = ?", (_now(), url))


def directory_domains() -> set[str]:
    from urllib.parse import urlparse

    return {(urlparse(r["url"]).hostname or "").removeprefix("www.") for r in list_directory()}


# --- Opportunities --------------------------------------------------------------
def _opp_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    for f in JSON_FIELDS:
        d[f] = json.loads(d[f]) if d[f] else []
    return d


def add_opportunity(data: dict, status: str = "Researching", owner: str | None = None, sample: bool = False) -> int:
    cols = [
        "funder", "program_name", "deadline", "deadline_text", "geography", "focus_area", "award_min",
        "award_max", "award_text", "matched_funding", "reporting", "summary", "source_url", "raw_text", "origin",
    ]
    values = [data.get(c) for c in cols] + [json.dumps(data.get(f) or []) for f in JSON_FIELDS]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO opportunities ({', '.join(cols + list(JSON_FIELDS))}, status, owner, sample, created) "
            f"VALUES ({', '.join('?' * (len(cols) + len(JSON_FIELDS)))}, ?, ?, ?, ?)",
            values + [status, owner, int(sample), _now()],
        )
        return cur.lastrowid


def get_opportunity(opp_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
        return _opp_row(row) if row else None


def list_opportunities() -> list[dict]:
    with connect() as conn:
        return [_opp_row(r) for r in conn.execute("SELECT * FROM opportunities ORDER BY deadline IS NULL, deadline")]


def delete_opportunity(opp_id: int) -> None:
    """Remove a grant from the pipeline with its questions, drafts, reviews, tasks and assessments.
    Search-result assessments (lead_assessments) are kept, so re-adding it from Discover costs nothing."""
    with connect() as conn:
        for (q_id,) in conn.execute("SELECT id FROM questions WHERE opportunity_id = ?", (opp_id,)).fetchall():
            conn.execute("DELETE FROM versions WHERE question_id = ?", (q_id,))
            conn.execute("DELETE FROM reviews WHERE question_id = ?", (q_id,))
            conn.execute("DELETE FROM comments WHERE question_id = ?", (q_id,))
        for table in ("questions", "tasks", "assessments"):
            conn.execute(f"DELETE FROM {table} WHERE opportunity_id = ?", (opp_id,))
        conn.execute("DELETE FROM opportunities WHERE id = ?", (opp_id,))


def update_opportunity(opp_id: int, **fields) -> None:
    allowed = {"status", "owner", "decision", "decision_reason", *OUTCOME_COLUMNS}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    with connect() as conn:
        conn.execute(
            f"UPDATE opportunities SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
            [*fields.values(), opp_id],
        )


# --- Assessments of search results (before saving) ---------------------------------
def save_lead_assessment(source_id: str, result: dict, usage: dict) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO lead_assessments (source_id, result, usage, created) VALUES (?, ?, ?, ?)",
                     (source_id, json.dumps(result), json.dumps(usage), _now()))


def get_lead_assessment(source_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM lead_assessments WHERE source_id = ?", (source_id,)).fetchone()
    if not row:
        return None
    return {"result": json.loads(row["result"]), "usage": json.loads(row["usage"]), "created": row["created"]}


# --- Assessments ----------------------------------------------------------------
def save_assessment(opp_id: int, result: dict, usage: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO assessments (opportunity_id, result, usage, created) VALUES (?, ?, ?, ?)",
            (opp_id, json.dumps(result), json.dumps(usage), _now()),
        )


def latest_assessment(opp_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE opportunity_id = ? ORDER BY id DESC LIMIT 1", (opp_id,)
        ).fetchone()
    if not row:
        return None
    return {"result": json.loads(row["result"]), "usage": json.loads(row["usage"]), "created": row["created"]}


# --- Application questions ------------------------------------------------------
def add_question(opp_id: int, prompt: str, limit_type: str | None, limit_value: int | None,
                 response: str = "", kind: str = "application") -> int:
    with connect() as conn:
        pos = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM questions WHERE opportunity_id = ? AND kind = ?",
                           (opp_id, kind)).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO questions (opportunity_id, position, prompt, limit_type, limit_value, response, status, updated,"
            " kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (opp_id, pos, prompt, limit_type, limit_value, response, "Drafting" if response else "Not started", _now(),
             kind),
        )
        return cur.lastrowid


def update_question(q_id: int, prompt: str, limit_type: str | None, limit_value: int | None) -> None:
    """Change the question's wording or length limit; the answer is untouched."""
    with connect() as conn:
        conn.execute("UPDATE questions SET prompt = ?, limit_type = ?, limit_value = ? WHERE id = ?",
                     (prompt, limit_type if limit_value else None, limit_value, q_id))


def list_questions(opp_id: int | None = None, kind: str = "application") -> list[dict]:
    """Application questions by default; kind='report' gives the sections of a report owed to a funder."""
    with connect() as conn:
        if opp_id is None:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM questions WHERE kind = ? ORDER BY opportunity_id, position", (kind,))]
        return [dict(r) for r in conn.execute(
            "SELECT * FROM questions WHERE opportunity_id = ? AND kind = ? ORDER BY position", (opp_id, kind))]


def get_question(q_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (q_id,)).fetchone()
        return dict(row) if row else None


VERSION_WINDOW_MIN = 10  # autosaves within this many minutes of the last one share a history entry


def save_response(q_id: int, text: str, origin: str = "you", autosave: bool = False) -> bool:
    """Save the answer, keeping the previous text as a version. Returns True if it changed.
    An autosave folds into the latest version when it has the same origin and is under
    VERSION_WINDOW_MIN minutes old, so history shows editing sessions rather than every pause in typing."""
    q = get_question(q_id)
    if q is None or q["response"] == text:
        return False
    with connect() as conn:
        latest = conn.execute("SELECT id, origin, created FROM versions WHERE question_id = ? ORDER BY id DESC",
                              (q_id,)).fetchone()
        if q["response"] and not latest:  # keep the starting text so it can be restored
            conn.execute("INSERT INTO versions (question_id, text, origin, created) VALUES (?, ?, ?, ?)",
                         (q_id, q["response"], "you", q["updated"]))
        status = q["status"] if q["status"] != "Not started" else "Drafting"
        if q["status"] == "Approved":
            status = "Drafting"  # editing approved text re-opens it
        conn.execute("UPDATE questions SET response = ?, status = ?, updated = ? WHERE id = ?",
                     (text, status, _now(), q_id))
        recent = latest and (datetime.now() - datetime.fromisoformat(latest["created"])).total_seconds() \
            < VERSION_WINDOW_MIN * 60
        if autosave and recent and latest["origin"] == origin:
            conn.execute("UPDATE versions SET text = ?, created = ? WHERE id = ?", (text, _now(), latest["id"]))
        else:
            conn.execute("INSERT INTO versions (question_id, text, origin, created) VALUES (?, ?, ?, ?)",
                         (q_id, text, origin, _now()))
    return True


def set_question_status(q_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE questions SET status = ?, updated = ? WHERE id = ?", (status, _now(), q_id))


def delete_question(q_id: int) -> None:
    with connect() as conn:
        for table in ("versions", "reviews", "comments"):
            conn.execute(f"DELETE FROM {table} WHERE question_id = ?", (q_id,))
        conn.execute("DELETE FROM questions WHERE id = ?", (q_id,))


def list_versions(q_id: int) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM versions WHERE question_id = ? ORDER BY id DESC", (q_id,))]


def save_review(q_id: int, kind: str, result: dict, usage: dict, response_text: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO reviews (question_id, kind, result, usage, response_text, created) VALUES (?, ?, ?, ?, ?, ?)",
            (q_id, kind, json.dumps(result), json.dumps(usage), response_text, _now()),
        )


def latest_review(q_id: int, kind: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE question_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
                           (q_id, kind)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["result"], d["usage"] = json.loads(d["result"]), json.loads(d["usage"])
    return d


# --- Tasks -------------------------------------------------------------------------
def add_tasks(opp_id: int, tasks: list[tuple[str, date, bool]]) -> None:
    with connect() as conn:
        conn.executemany(
            "INSERT INTO tasks (opportunity_id, title, due, done, position) VALUES (?, ?, ?, ?, ?)",
            [(opp_id, t, d.isoformat(), int(done), i) for i, (t, d, done) in enumerate(tasks)],
        )


def list_tasks(opp_id: int | None = None) -> list[dict]:
    with connect() as conn:
        if opp_id is None:
            rows = conn.execute("SELECT * FROM tasks ORDER BY opportunity_id, position")
        else:
            rows = conn.execute("SELECT * FROM tasks WHERE opportunity_id = ? ORDER BY position", (opp_id,))
        return [dict(r) for r in rows]


def set_task_done(task_id: int, done: bool) -> bool:
    """Returns True if the value actually changed."""
    with connect() as conn:
        cur = conn.execute("UPDATE tasks SET done = ? WHERE id = ? AND done != ?", (int(done), task_id, int(done)))
        return cur.rowcount > 0

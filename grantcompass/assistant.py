"""Compass Assistant: a chat agent that answers a fundraiser's questions about their own
grants (pipeline, deadlines, discovery, drafts, team, profile) and general grant practice,
and can take the user to any page.

It works only through the read-only tools below (plus open_page, which only navigates),
so it can look things up and move around but can never change data. Tool results are the organisation's records and funders' text: data, not
instructions. Code, not the model, computes every number it reports (days left, fit %,
progress, word counts)."""

import asyncio
import json
from datetime import date
from typing import Literal

from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from . import db, directory
from . import llm
from .config import PROMPTS_DIR
from .llm import MODEL_SETTINGS, build_model, log_run, timed_run, usage_dict
from .pipeline import RISK_RULES, pipeline_rows
from .profile import completeness, render as render_profile

INSTRUCTIONS = (PROMPTS_DIR / "assistant.md").read_text(encoding="utf-8")
LIMITS = UsageLimits(request_limit=8, total_tokens_limit=80_000)  # a few tool calls, then answer
MAX_MESSAGE_CHARS = 2_000
HISTORY_TURNS = 8  # earlier turns sent back for context, newest last


# --- Read-only tools ------------------------------------------------------------------------
def _fit(opp_id: int) -> dict:
    a = db.latest_assessment(opp_id)
    if not a:
        return {"fit_percent": None, "recommendation": "Not assessed yet"}
    r = a["result"]
    return {"fit_percent": r.get("fit_score"), "recommendation": r.get("recommendation"),
            "fit_summary": r.get("headline")}


def _award(o: dict) -> str:
    lo, hi = o.get("award_min"), o.get("award_max")
    if lo and hi:
        return f"${lo:,}–${hi:,}"
    if hi:
        return f"up to ${hi:,}"
    return o.get("award_text") or "not stated"


def pipeline_overview() -> list[dict]:
    """Every grant in the user's pipeline: status, deadline and days left, risk with the reasons,
    progress, who is responsible, fit, award, overdue steps and the suggested next action."""
    from .ui.pipeline_page import next_action  # the same rule the Pipeline page shows

    out = []
    for r in pipeline_rows(db.list_opportunities(), db.list_tasks()):
        act = next_action(r)
        today = date.today()
        out.append({
            "id": r["id"], "funder": r["funder"], "programme": r["program_name"], "stage": r["status"],
            "active": r["active"], "deadline": r["deadline"] or r.get("deadline_text") or "not stated",
            "days_left": r["days_remaining"], "risk": r["health"], "risk_reasons": r["health_reasons"],
            "progress_percent": r["progress"], "responsible": r["owner"] or "unassigned",
            "award": _award(r), "go_no_go_decision": r.get("decision") or "not decided", **_fit(r["id"]),
            "overdue_steps": [t["title"] for t in r["outstanding"] if date.fromisoformat(t["due"]) < today],
            "next_action": act["label"] if act else None,
        })
    return out


def funder_reports() -> list[dict]:
    """Reports owed to funders after a win (not applications): each won grant's amount, grant period, next
    report due date and days left, and how many report sections are written. Soonest first. Also the grants
    that were lost, with the funder's feedback."""
    today = date.today()
    out = []
    for o in db.list_opportunities():
        if o["status"] == "Won":
            qs = db.list_questions(o["id"], kind="report")
            due = o.get("report_due")
            out.append({"result": "Won", "funder": o["funder"], "programme": o["program_name"], "grant_id": o["id"],
                        "awarded": f"${o['awarded_amount']:,}" if o.get("awarded_amount") else "not recorded",
                        "grant_period": o.get("grant_period"), "report_due": due,
                        "report_days_left": (date.fromisoformat(due) - today).days if due else None,
                        "sections_written": f"{sum(bool(q['response'].strip()) for q in qs)} of {len(qs)}"})
        elif o["status"] == "Lost":
            out.append({"result": "Lost", "funder": o["funder"], "programme": o["program_name"],
                        "decided": o.get("result_date"), "funder_feedback": o.get("lost_reason")})
    return sorted(out, key=lambda r: (r["result"] != "Won", r.get("report_days_left") is None,
                                      r.get("report_days_left") or 0))


def grant_details(grant_id: int) -> dict:
    """Full detail for one pipeline grant (use the id from pipeline_overview): summary, eligibility,
    the Fit Agent's assessment, workback steps, and every application question with its status,
    length against the limit, latest Coach score and Evidence Checker counts."""
    from .writing import length_check

    o = db.get_opportunity(grant_id)
    if not o:
        return {"error": f"No grant with id {grant_id}. Call pipeline_overview for the ids."}
    a = db.latest_assessment(grant_id)
    questions = []
    for i, q in enumerate(db.list_questions(grant_id), 1):
        length = length_check(q["response"], q["limit_type"], q["limit_value"])
        coach = db.latest_review(q["id"], "coach")
        evidence = db.latest_review(q["id"], "evidence")
        item = {"number": i, "question": q["prompt"], "status": q["status"],
                "answered": bool(q["response"].strip()),
                "length": length["label"] + ("" if q["limit_value"] else " (no limit)"),
                "within_limit": length["ok"],
                "missing_placeholders": q["response"].count("[MISSING")}
        if coach:
            c = coach["result"]
            item["coach"] = {"overall_score": c.get("overall"), "start_here": c.get("top_priority"),
                             "open_suggestions": len(c.get("issues") or [])}
        if evidence:
            claims = evidence["result"].get("claims") or []
            counts = {}
            for cl in claims:
                counts[cl.get("status")] = counts.get(cl.get("status"), 0) + 1
            item["evidence"] = counts
        questions.append(item)
    return {
        "id": o["id"], "funder": o["funder"], "programme": o["program_name"], "stage": o["status"],
        "summary": o.get("summary"), "deadline": o["deadline"] or o.get("deadline_text"),
        "award": _award(o), "eligibility": o.get("eligibility"), "geography": o.get("geography"),
        "match_required": o.get("match_required"), "url": o.get("url"),
        "responsible": o.get("owner") or "unassigned", "go_no_go_decision": o.get("decision") or "not decided",
        "assessment": None if not a else {
            "fit_percent": a["result"].get("fit_score"), "recommendation": a["result"].get("recommendation"),
            "headline": a["result"].get("headline"),
            "dimensions": [{"dimension": d.get("key"), "score_1_to_5": d.get("score"),
                            "why": d.get("rationale")} for d in a["result"].get("dimensions") or []],
            "questions_to_ask_the_funder": a["result"].get("questions"),
        },
        "workback_steps": [{"step": t["title"], "due": t["due"], "done": bool(t["done"])}
                           for t in db.list_tasks(grant_id)],
        "application_questions": questions,
    }


def discovery_matches(min_fit_percent: int = 0) -> dict:
    """Funding found on the Discover page that the Fit Agent has already assessed (foundation
    directory, watchlist and imported links), best fit first. Not yet in the pipeline unless noted."""
    in_pipeline = {(o["funder"] or "").lower() for o in db.list_opportunities()}
    state = ((db.get_profile() or {"data": {}})["data"]).get("state")
    service_area = {e["n"]: e["states"] for e in directory.entries() if e.get("states")}
    found = []
    for row in db.list_directory():
        if state and row["n"] in service_area and state not in service_area[row["n"]]:
            continue  # a utility or community foundation that doesn't give in their state
        opp = row.get("result")
        a = db.get_lead_assessment(f"dir:{row['n']}")
        if not opp or not a:
            continue
        fit = a["result"].get("fit_score")
        if fit is None or fit < min_fit_percent:
            continue
        found.append({"funder": row["name"], "programme": opp.get("program_name"), "fit_percent": fit,
                      "recommendation": a["result"].get("recommendation"), "why": a["result"].get("headline"),
                      "deadline": opp.get("deadline") or opp.get("deadline_text"), "award": _award(opp),
                      "focus": opp.get("focus_area"), "url": row["url"],
                      "already_in_pipeline": row["name"].lower() in in_pipeline})
    found.sort(key=lambda f: -(f["fit_percent"] or 0))
    unread = sum(1 for r in db.list_directory() if not r.get("result"))
    return {"assessed_matches": found[:15], "total_assessed": len(found),
            "directory_size": len(db.list_directory()), "directory_pages_not_yet_read": unread,
            "note": "Federal Grants.gov results are searched live: use search_federal_grants."}


def search_federal_grants(keywords: str) -> list[dict]:
    """Search Grants.gov live for open federal grants (no AI cost) and rank them with the same
    no-AI triage as the Discover page. keywords: a few plain words, e.g. 'early literacy'."""
    from .sources import grantsgov
    from .triage import triage

    prof = (db.get_profile() or {"data": {}})["data"]
    words = [w for w in keywords.replace(",", " ").split() if w][:6]
    leads = grantsgov.search(words or ["literacy"])
    ranked = []
    for lead in leads:
        t = triage(lead, prof, keywords=words)
        if t.get("excluded"):
            continue
        a = db.get_lead_assessment(lead["source_id"])
        ranked.append({"title": lead["title"], "agency": lead["funder"], "deadline": lead["deadline"]
                       or lead["deadline_text"], "award": _award(lead), "relevance_score": t.get("score"),
                       "reasons": t.get("reasons"), "fit_percent": a["result"].get("fit_score") if a else None,
                       "url": lead["url"]})
    ranked.sort(key=lambda r: -(r["relevance_score"] or 0))
    return ranked[:8]


def organisation_profile() -> dict:
    """The organisation's Profile (mission, programmes, budget, geography, preferences, voice),
    how complete it is, and the source documents the Grant Writer may draft from."""
    prof = db.get_profile()
    data = prof["data"] if prof else {}
    pct, missing = completeness(data)
    return {"profile": render_profile(data) if data else "No profile yet.", "profile_complete_percent": pct,
            "profile_fields_missing": missing,
            "source_documents": [{"title": d["title"], "type": d["doc_type"], "approved_language": bool(d["approved"]),
                                  "words": len(d["content"].split())} for d in db.list_documents()]}


def team_workload() -> list[dict]:
    """Each team member and the active grants they are responsible for, with deadlines and risk."""
    rows = [r for r in pipeline_rows(db.list_opportunities(), db.list_tasks()) if r["active"]]
    people = [db.member_label(m["name"], m["role"]) for m in db.list_team()]
    out = []
    for p in people + ["unassigned"]:
        mine = [r for r in rows if (r["owner"] or "unassigned") == p]
        out.append({"person": p, "grants": [{"funder": r["funder"], "programme": r["program_name"],
                                             "days_left": r["days_remaining"], "risk": r["health"]} for r in mine]})
    return out


def answer_library(search_words: str = "") -> dict:
    """The team's Answer Library: approved answers saved for reuse, with topic (Mission & organisation, Need &
    community, Programme design, Outcomes & evaluation, Capacity & partners, Budget & sustainability, Equity &
    inclusion, Other), original question, funder, length and how often each has been reused.
    search_words narrows it by topic or wording (empty = everything)."""
    from .answers import search, word_count

    items = search(search_words)
    note = None
    if search_words.strip() and not items:  # don't report "nothing" when a looser look would find something
        items, note = search(""), f"Nothing matched '{search_words}' exactly, so this is the whole library."
    return {"note": note, "answers": [{"topic": a["topic"], "question": a["question"], "funder": a["funder"],
                         "words": word_count(a["text"]), "times_reused": a["uses"], "saved": a["created"][:10],
                         "opening": a["text"][:200]} for a in items[:12]],
            "total_in_library": len(search(""))}


def open_asks(person: str = "") -> list[dict]:
    """Open comment threads on application and report answers: who asked whom, about which words, on which
    grant. person narrows it to asks for one teammate (a first name is enough)."""
    out = []
    for a in db.open_asks():
        if person and person.lower() not in (a["assignee"] or "").lower():
            continue
        out.append({"asked": (a["assignee"] or "no one in particular").split(" (")[0],
                    "by": a["author"].split(" (")[0], "comment": a["body"], "about_words": a["quote"],
                    "grant": f"{a['funder']} — {a['program_name']}", "grant_id": a["opportunity_id"],
                    "question": a["prompt"][:120], "replies": a["replies"]})
    return out[:15]


def agent_health() -> dict:
    """How the AI agents are working: each agent's status (Healthy / Watch / Attention) with reasons, runs,
    failures, safety-check results, and the Executive Director's latest briefing."""
    from .health import compute

    h = compute()
    reports = db.list_director_reports()
    latest = reports[0]["result"] if reports else None
    return {"overall": h["status"],
            "agents": {a["name"]: {"status": a["status"], "reasons": a["reasons"], "runs": a["runs"],
                                   "checks": {c["label"]: c["shown"] for c in a["checks"]}}
                       for a in h["agents"].values()},
            "executive_director_latest": {"overall": latest["overall"], "headline": latest["headline"],
                                          "top_action": latest["top_action"],
                                          "reviewed": reports[0]["created"][:16]} if latest else "No review yet"}


def ai_spending() -> dict:
    """How many AI runs this app has made and what they cost, by agent (from logs/usage.jsonl)."""
    path = llm.log_dir() / "usage.jsonl"
    by_agent, total, unpriced = {}, 0.0, 0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            b = by_agent.setdefault(r["agent"], {"runs": 0, "cost_usd": 0.0})
            b["runs"] += 1
            b["cost_usd"] += r.get("cost_usd") or 0
            total += r.get("cost_usd") or 0
            unpriced += r.get("cost_usd") is None
    return {"total_cost_usd": round(total, 4), "runs_logged_before_prices_were_set": unpriced, "by_agent": {k: {**v, "cost_usd": round(v["cost_usd"], 4)}
                                                           for k, v in by_agent.items()}}


PAGES = {"home": "/", "discover": "/discover", "pipeline": "/pipeline", "applications": "/applications",
         "answer_library": "/answers", "agent_health": "/profile/health",
         "reports": "/reports", "privacy": "/privacy", "profile": "/profile", "source_documents": "/profile/documents",
         "team": "/profile/team"}
Page = Literal["home", "discover", "pipeline", "applications", "reports", "privacy", "answer_library",
               "agent_health", "profile", "source_documents", "team",
               "grant", "application"]


def page_path(page: str, grant_id: int | None = None, question_number: int | None = None) -> str:
    """The app address for a page; 'grant' and 'application' need a grant_id from pipeline_overview."""
    if page in PAGES:
        return PAGES[page]
    if page not in ("grant", "application"):
        raise ValueError(f"Unknown page {page!r}.")
    if not grant_id or not db.get_opportunity(grant_id):
        raise ValueError("That page needs a valid grant_id: call pipeline_overview first.")
    if page == "grant":
        return f"/opportunity/{grant_id}"
    qs = db.list_questions(grant_id)
    if question_number and 1 <= question_number <= len(qs):
        return f"/application/{grant_id}/{qs[question_number - 1]['id']}"
    return f"/application/{grant_id}"


def open_page(page: Page, grant_id: int | None = None, question_number: int | None = None) -> str:
    """Take the user to a page of the app as soon as you reply. Use when they ask to go somewhere, open
    something, or 'take me to' / 'show me' a page, grant or application question.
    page: home, discover, pipeline, applications, reports (funder reports and the board update), privacy,
    answer_library, agent_health, profile (edit profile), source_documents,
    team, grant (one grant's full record: needs grant_id) or application (its writing workspace: needs
    grant_id; question_number opens that question). Navigating changes no data."""
    try:
        path = page_path(page, grant_id, question_number)
    except ValueError as exc:
        return f"Could not open it: {exc}"
    return f"Opening {path} for the user when you reply. Tell them briefly what they'll find there."


TOOLS = [pipeline_overview, grant_details, discovery_matches, search_federal_grants, organisation_profile,
         team_workload, funder_reports, answer_library, open_asks, agent_health, ai_spending, open_page]


def _navigation(run) -> str | None:
    """The page the agent opened (the last successful open_page call), if any."""
    path = None
    for m in run.all_messages():
        for p in getattr(m, "parts", []):
            if getattr(p, "part_kind", "") == "tool-call" and p.tool_name == "open_page":
                try:
                    path = page_path(**p.args_as_dict())
                except (ValueError, TypeError):
                    pass
    return path


# --- Running a turn ---------------------------------------------------------------------------
def _prompt(history: list[dict], message: str) -> str:
    past = history[-HISTORY_TURNS * 2:]
    convo = "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['text']}" for m in past)
    risk = "\n".join(RISK_RULES.values())
    return (f"Today is {date.today():%A %d %B %Y}.\nRisk rules used by the app:\n{risk}\n\n"
            + (f"Conversation so far:\n{convo}\n\n" if convo else "")
            + f"User: {message}")


async def _ask(prompt: str):
    model = build_model()
    try:
        agent = Agent(model, instructions=INSTRUCTIONS, tools=TOOLS, model_settings=MODEL_SETTINGS, retries=1)
        return await agent.run(prompt, usage_limits=LIMITS)
    finally:
        await model.client.close()


def ask(message: str, history: list[dict]) -> dict:
    """One chat turn. Returns {text, usage}. Raises ValueError for a message we won't send."""
    message = (message or "").strip()
    if not message:
        raise ValueError("Type a question first.")
    if len(message) > MAX_MESSAGE_CHARS:
        raise ValueError(f"That message is {len(message):,} characters; please keep it under {MAX_MESSAGE_CHARS:,}.")
    run = timed_run("assistant", lambda: asyncio.run(_ask(_prompt(history, message))))
    usage = usage_dict(run.usage)
    tools_used = [p.tool_name for m in run.all_messages() for p in getattr(m, "parts", [])
                  if getattr(p, "part_kind", "") == "tool-call"]
    log_run("assistant", usage, {"tools": tools_used})
    return {"text": run.output, "usage": usage, "tools": tools_used, "navigate": _navigation(run)}

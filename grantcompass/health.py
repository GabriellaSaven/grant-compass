"""Agent health: how each AI agent is behaving, computed from the usage log, the failure log and
the results the app has saved. Plain code, no AI, so it is free, instant and can't be talked
into anything. The Executive Director agent reads these numbers; it never sees raw funder text.

Every number has a stable id (e.g. "fit_agent.quote_warning_rate") so the Director's claims
can be checked against it."""

import json
from datetime import datetime, timedelta, timezone

from . import db, llm

AGENTS = {
    "research_agent": ("Research Agent", "Reads funder pages and files; extracts facts and questions."),
    "fit_agent": ("Fit Agent", "Scores fit against your Profile and documents; recommends Go / No-Go."),
    "grant_writer": ("Grant Writer", "Drafts answers from your documents only, citing sources."),
    "grant_coach": ("Grant Coach", "Reviews answers and suggests specific fixes."),
    "evidence_checker": ("Evidence Checker", "Tests every claim against your documents."),
    "assistant": ("Compass Assistant", "Answers questions in chat with read-only tools; can navigate."),
    "executive_director": ("Executive Director", "Reviews the other agents' health and briefs you."),
}
# Each agent as the colleague it would be on a nonprofit development team. Shown in the app and the report.
# (person, job title, archetype, how they work, tools they use, guardrails that keep them honest)
PERSONAS = {
    "research_agent": ("Ines Okafor", "Prospect Research Manager", "The Prospect Researcher",
                       "Reads every RFP twice and the fine print three times. Never assumes a deadline.",
                       "Funder web pages, PDFs and Word files; robots.txt-respecting page fetcher",
                       "Flags instruction-like text as suspicious; keeps only questions found word for word; "
                       "re-reads a page only when it changes"),
    "fit_agent": ("Marcus Bell", "Director of Grant Strategy", "The Pragmatic Strategist",
                  "Says no to good-looking grants that don't fit, and shows the math behind every yes.",
                  "Your Profile, source documents and saved answers; the funder's own text",
                  "Fit % computed in code from his 1-5 scores; every quote verified; eligibility gate forces No-Go"),
    "grant_writer": ("June Alvarez", "Senior Grant Writer", "The Storyteller",
                     "Turns your reports into a story a funder remembers, and writes [MISSING] rather than fudge a "
                     "number.",
                     "Your Profile, source documents and Answer Library",
                     "Cites a source for every fact (checked word for word); code counts words; Undo restores "
                     "your text"),
    "grant_coach": ("Dolores Whitfield", "Grant Readiness Coach", "The Program Officer Turned Mentor",
                    "Has read thousands of proposals from the funder's side of the desk. Kind, exacting, specific.",
                    "The funder's question and your answer",
                    "Overall score is a weighted average done in code; suggestions never add facts"),
    "evidence_checker": ("Theo Park", "Evaluation & Impact Manager", "The Evaluator",
                         "Trusts data, not adjectives. Asks \"where's the evidence?\" of every claim.",
                         "Your source documents",
                         "Quotes matched against the source text; contradictions flagged, never smoothed over"),
    "assistant": ("Kit Morales", "Development Associate", "The Helpful Generalist",
                  "Knows where everything is and who's on it, and will walk you to the right page.",
                  "8 read-only look-ups (pipeline, grants, Discover, Grants.gov, profile, team, library, health) "
                  "and page navigation",
                  "Cannot add, edit or delete anything; capped at 8 AI calls per question"),
    "executive_director": ("Dr. Evelyn Hart", "Executive Director", "The Steady Leader",
                           "Holds the team to its standards and briefs you on what matters. Never overrides your "
                           "call.",
                           "The numbers on this page only, never funder pages",
                           "Every number she cites is checked; her rating can't be rosier than the app's rules"),
}
# Where in the app each agent does its work.
WHERE = {"research_agent": "Discover page", "fit_agent": "Discover & Pipeline", "grant_writer": "Applications & Reports",
         "grant_coach": "Applications, per question", "evidence_checker": "Applications, per question",
         "assistant": "Chat, on every page", "executive_director": "Agent health & Reports"}
INITIALS = {"research_agent": "R", "fit_agent": "F", "grant_writer": "W", "grant_coach": "C", "evidence_checker": "E",
            "assistant": "A", "executive_director": "ED"}
RANK = {"Not used yet": 0, "Healthy": 1, "Watch": 2, "Attention": 3}
# The rules, shown on the page so every status can be explained.
RULES = [
    "Attention: more than 20% of an agent's runs failed.",
    "Watch: more than 5% failed, or a run hit the per-run AI-call or token limit.",
    "Watch: the Fit Agent's quotes failed verification in more than half its assessments.",
    "Watch: over 20% of the Grant Writer's cited facts couldn't be verified (Attention over 40%).",
    "Watch: you overruled the Fit Agent in more than half of at least 3 decisions.",
    "Injection attempts flagged or blocked count as the defense working, not as a problem.",
]


def _jsonl(name: str) -> list[dict]:
    path = llm.log_dir() / name  # the signed-in organisation's logs
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def _rows(sql: str) -> list[dict]:
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(sql)]


def _share(part: float, whole: float) -> float | None:
    return round(part / whole, 3) if whole else None


def _check(metric: str, label: str, value, shown: str, level: str = "ok") -> dict:
    return {"metric": metric, "label": label, "value": value, "shown": shown, "level": level}


def compute() -> dict:
    runs, events = _jsonl("usage.jsonl"), _jsonl("events.jsonl")
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    fit_results = [json.loads(r["result"]) for r in _rows("SELECT result FROM assessments")] + \
                  [json.loads(r["result"]) for r in _rows("SELECT result FROM lead_assessments")]
    reviews = {k: [json.loads(r["result"]) for r in _rows(f"SELECT result FROM reviews WHERE kind = '{k}'")]
               for k in ("draft", "coach", "evidence")}

    agents = {}
    for key, (name, job) in AGENTS.items():
        mine = [r for r in runs if r["agent"] == key]
        fails = [e for e in events if e["agent"] == key]
        priced = [r["cost_usd"] for r in mine if r.get("cost_usd") is not None]
        secs = [r["seconds"] for r in mine if r.get("seconds") is not None]
        attempts = len(mine) + len([e for e in fails if e["event"] == "error"])
        a = {"key": key, "name": name, "job": job, "runs": len(mine),
             "runs_7d": sum(datetime.fromisoformat(r["time"]) >= week_ago for r in mine),
             "cost_usd": round(sum(priced), 4), "avg_cost_usd": round(sum(priced) / len(priced), 5) if priced else None,
             "avg_seconds": round(sum(secs) / len(secs), 1) if secs else None,
             "errors": sum(e["event"] == "error" for e in fails),
             "limit_hits": sum(e["event"] == "limit" for e in fails),
             "provider_blocks": sum(e["event"] == "provider_block" for e in fails),
             "checks": []}
        a["failure_rate"] = _share(a["errors"], attempts)
        agents[key] = a

    # Agent-specific checks, from the results the app saved.
    fit = agents["fit_agent"]
    n = len(fit_results)
    from .fit import QUOTE_CHECK
    checked = [r for r in fit_results if r.get("quote_check") == QUOTE_CHECK]  # the old check over-flagged
    warned = sum(bool(r.get("quote_warnings")) for r in checked)
    gate = sum(bool(r.get("gate")) for r in fit_results)
    flagged = sum(bool(r.get("suspicious_content")) for r in fit_results)
    decided = [o for o in db.list_opportunities() if o.get("decision")]
    with_ai = [(o, db.latest_assessment(o["id"])) for o in decided]
    with_ai = [(o, a) for o, a in with_ai if a]
    overruled = sum(o["decision"] != a["result"].get("recommendation") for o, a in with_ai)
    rate = _share(warned, len(checked))
    fit["checks"] = [
        _check("fit_agent.assessments", "Assessments saved", n, f"{n}"),
        _check("fit_agent.quote_warning_rate", "Assessments with a quote that failed verification", rate,
               f"{warned} of {len(checked)}" if checked else "—",
               "watch" if rate and rate > 0.5 and len(checked) >= 3 else "ok"),
        _check("fit_agent.not_rechecked", "Older search results that couldn't be re-checked (not counted)",
               n - len(checked), f"{n - len(checked)}", "info"),
        _check("fit_agent.eligibility_gate_fired", "Times the eligibility gate overrode the AI to No-Go", gate,
               f"{gate}", "info"),
        _check("fit_agent.injection_flags", "Injection attempts flagged in funder text", flagged, f"{flagged}",
               "info"),
        _check("fit_agent.human_override_rate", "Your decisions that overruled its recommendation",
               _share(overruled, len(with_ai)), f"{overruled} of {len(with_ai)}" if with_ai else "—",
               "watch" if len(with_ai) >= 3 and overruled / len(with_ai) > 0.5 else "ok"),
    ]

    drafts = reviews["draft"]
    sources = sum(len(d.get("sources") or []) for d in drafts)
    unverified = sum(d.get("unverified") or 0 for d in drafts)
    urate = _share(unverified, sources)
    gaps = sum(bool(d.get("placeholders")) for d in drafts)
    agents["grant_writer"]["checks"] = [
        _check("grant_writer.drafts", "Drafts written", len(drafts), f"{len(drafts)}"),
        _check("grant_writer.unverified_source_rate", "Cited facts whose quote couldn't be found in the source",
               urate, f"{unverified} of {sources}" if sources else "—",
               "attention" if urate and urate > 0.4 else "watch" if urate and urate > 0.2 else "ok"),
        _check("grant_writer.drafts_with_missing", "Drafts that marked a gap [MISSING] instead of guessing",
               _share(gaps, len(drafts)), f"{gaps} of {len(drafts)}" if drafts else "—", "info"),
    ]

    coach = reviews["coach"]
    scores = [c["overall"] for c in coach if c.get("overall") is not None]
    agents["grant_coach"]["checks"] = [
        _check("grant_coach.reviews", "Reviews", len(coach), f"{len(coach)}"),
        _check("grant_coach.avg_score", "Average score it gave your answers (measures the answers, not the Coach)", round(sum(scores) / len(scores), 1)
               if scores else None, f"{sum(scores) / len(scores):.0f}/100" if scores else "—", "info"),
    ]

    claims = [c for e in reviews["evidence"] for c in e.get("claims") or []]
    weak = sum(c.get("status") in ("Needs evidence", "Contradicted") for c in claims)
    contradicted = sum(c.get("status") == "Contradicted" for c in claims)
    agents["evidence_checker"]["checks"] = [
        _check("evidence_checker.claims", "Claims checked", len(claims), f"{len(claims)}"),
        _check("evidence_checker.weak_claim_rate", "Claims needing evidence or contradicted", _share(weak, len(claims)),
               f"{weak} of {len(claims)}" if claims else "—", "info"),
        _check("evidence_checker.contradicted", "Claims contradicted by your documents", contradicted,
               f"{contradicted}", "info"),
    ]

    chats = [r for r in runs if r["agent"] == "assistant"]
    tools = [len(r.get("tools") or []) for r in chats]
    agents["assistant"]["checks"] = [
        _check("assistant.avg_tool_calls", "Look-ups per question", round(sum(tools) / len(tools), 1)
               if tools else None, f"{sum(tools) / len(tools):.1f}" if tools else "—", "info"),
        _check("assistant.write_tools", "Tools that can change data", 0, "0 (read-only by design)", "info"),
    ]

    reports = db.list_director_reports()
    removed = sum(r["result"].get("claims_removed", 0) for r in reports)
    agents["executive_director"]["checks"] = [
        _check("executive_director.reviews", "Reviews written", len(reports), f"{len(reports)}"),
        _check("executive_director.claims_removed", "Claims removed because the numbers didn't match", removed,
               f"{removed}", "info"),
    ]

    agents["research_agent"]["checks"] = [
        _check("research_agent.provider_blocks", "Pages refused by the provider's prompt shield",
               agents["research_agent"]["provider_blocks"] + agents["fit_agent"]["provider_blocks"],
               f"{agents['research_agent']['provider_blocks'] + agents['fit_agent']['provider_blocks']}", "info"),
    ]

    # Status per agent, from the rules above.
    for a in agents.values():
        level = "Healthy" if a["runs"] or a["errors"] else "Not used yet"
        reasons = []
        if a["failure_rate"] and a["failure_rate"] > 0.05:
            level = "Attention" if a["failure_rate"] > 0.2 else "Watch"
            reasons.append(f"{a['failure_rate']:.0%} of runs failed")
        if a["limit_hits"]:
            level = max(level, "Watch", key=RANK.get)
            reasons.append(f"{a['limit_hits']} run(s) stopped by a limit")
        for c in a["checks"]:
            if c["level"] in ("watch", "attention"):
                level = max(level, c["level"].capitalize(), key=RANK.get)
                reasons.append(f"{c['label']}: {c['shown']}")
        a["status"], a["reasons"] = level, reasons

    all_priced = [r["cost_usd"] for r in runs if r.get("cost_usd") is not None]
    totals = {"runs": len(runs), "runs_7d": sum(a["runs_7d"] for a in agents.values()),
              "cost_usd": round(sum(all_priced), 4), "unpriced_runs": len(runs) - len(all_priced),
              "failures": len(events), "avg_cost_usd": round(sum(all_priced) / len(all_priced), 5) if all_priced else None}
    status = max((a["status"] for a in agents.values()), key=RANK.get)
    return {"status": status if status != "Not used yet" else "Healthy", "agents": agents, "totals": totals,
            "rules": RULES, "metrics": flat(agents, totals)}


def flat(agents: dict, totals: dict) -> dict:
    """Every number by id, for checking the Director's claims."""
    m = {f"total.{k}": v for k, v in totals.items()}
    for key, a in agents.items():
        for f in ("runs", "runs_7d", "cost_usd", "avg_cost_usd", "avg_seconds", "errors", "limit_hits",
                  "provider_blocks", "failure_rate"):
            m[f"{key}.{f}"] = a[f]
        m[f"{key}.status"] = a["status"]
        for c in a["checks"]:
            m[c["metric"]] = c["value"]
    return m

"""Board update: the facts about fundraising (computed in code), plus an optional summary the Executive
Director writes for the board. Every number in her summary must appear in the facts, or that sentence is
removed and counted, so the board never sees an invented figure."""

import json
import re
from datetime import date, timedelta

from pydantic import BaseModel, Field

from . import db
from .config import PROMPTS_DIR
from .llm import log_run, run_agent, usage_dict
from .pipeline import CLOSED, pipeline_rows

WINDOW_DAYS = 183  # "the last six months"
IN_PROGRESS = ("Drafting", "Internal Review", "Ready to Submit")


class BoardSummary(BaseModel):
    headline: str = Field(description="One sentence for the top of the deck, e.g. the main result.")
    summary: str = Field(description="3-4 sentences for the board, plain English, only facts from the input.")
    highlights: list[str] = Field(description="3-4 short bullet points, each with a fact from the input.")
    asks: list[str] = Field(description="0-2 concrete things the board could help with, grounded in the facts.")


def _name(o: dict) -> str:
    return f"{o['funder']} — {o['program_name']}"


def _when(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%-d %b %Y") if iso else "—"


def facts() -> dict:
    """Everything the board update says, computed from the records."""
    today = date.today()
    since = today - timedelta(days=WINDOW_DAYS)
    opps = db.list_opportunities()
    rows = {r["id"]: r for r in pipeline_rows(opps, db.list_tasks(), today)}
    recent = [o for o in opps if o.get("result_date") and date.fromisoformat(o["result_date"]) >= since]
    won = [o for o in recent if o["status"] == "Won"]
    lost = [o for o in recent if o["status"] == "Lost"]
    awaiting = [o for o in opps if o["status"] == "Submitted"]
    progress = [o for o in opps if o["status"] in IN_PROGRESS]
    upcoming = sorted((o for o in opps if o["status"] not in CLOSED and o.get("deadline")
                       and 0 <= (date.fromisoformat(o["deadline"]) - today).days <= 60), key=lambda o: o["deadline"])
    reports = sorted((o for o in opps if o["status"] == "Won" and o.get("report_due")
                      and 0 <= (date.fromisoformat(o["report_due"]) - today).days <= 90), key=lambda o: o["report_due"])
    by_stage = []
    for st in ("Researching", "Go / No-Go", "Drafting", "Internal Review", "Ready to Submit", "Submitted"):
        total = sum(o["award_max"] or 0 for o in opps if o["status"] == st)
        if total:
            by_stage.append((st, total))
    decided = len(won) + len(lost)
    rate = round(100 * len(won) / decided) if decided else None

    def sections(o):
        qs = db.list_questions(o["id"], kind="report")
        return f"{sum(bool(q['response'].strip()) for q in qs)} of {len(qs)}"

    return {
        "period_label": f"{since:%-d %b} – {today:%-d %b %Y}",
        "won": [{"name": _name(o), "amount": o.get("awarded_amount") or 0, "when": _when(o["result_date"])} for o in won],
        "won_total": sum(o.get("awarded_amount") or 0 for o in won),
        "lost": [{"name": _name(o), "amount": o.get("award_max") or 0, "reason": o.get("lost_reason"),
                  "when": _when(o["result_date"])} for o in lost],
        "win_rate": rate,
        "win_rate_label": f"{rate}% ({len(won)} of {decided} decided)" if rate is not None else "No decisions yet",
        "awaiting": [{"name": _name(o), "amount": o["award_max"] or 0, "when": _when(o.get("deadline"))}
                     for o in awaiting],
        "awaiting_total": sum(o["award_max"] or 0 for o in awaiting),
        "in_progress": [{"name": _name(o), "stage": o["status"], "when": _when(o.get("deadline")),
                         "owner": (o.get("owner") or "Unassigned").split(" (")[0],
                         "progress": f"{rows[o['id']]['progress']}%"} for o in progress],
        "in_progress_total": sum(o["award_max"] or 0 for o in progress),
        "upcoming": [{"name": _name(o), "when": _when(o["deadline"]), "stage": o["status"]} for o in upcoming],
        "reports_due": [{"name": _name(o), "when": _when(o["report_due"]), "progress": sections(o)} for o in reports],
        "by_stage": by_stage,
    }


# --- The Executive Director's summary, checked ------------------------------------------------------
_NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s*(?:k|K|m|M|million|%)?")


def _values(token: str) -> set[float]:
    """A number as written ('$75,000', '75k', '$1.2M', '40%') as plain values."""
    t = token.strip().lower().replace("$", "").replace(",", "").replace(" ", "")
    mult = 1
    for suffix, m in (("million", 1e6), ("m", 1e6), ("k", 1e3), ("%", 1)):
        if t.endswith(suffix):
            t, mult = t[: -len(suffix)], m
            break
    try:
        v = float(t) * mult
    except ValueError:
        return set()
    return {round(v, 2)}


def _allowed(f: dict) -> set[float]:
    text = json.dumps(f)
    vals = set()
    for tok in _NUM.findall(text):
        vals |= _values(tok)
    for v in list(vals):  # money is often rounded to thousands when written ("$75k")
        vals.add(round(v / 1000) * 1000)
    return vals | {6.0, 60.0, 90.0}  # the report's own windows: six months, 60 and 90 days


def _clean(text: str, allowed: set[float]) -> tuple[str, int]:
    kept, dropped = [], 0
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        nums = [v for tok in _NUM.findall(sent) for v in _values(tok)]
        if all(v in allowed or round(v / 1000) * 1000 in allowed for v in nums):
            kept.append(sent)
        else:
            dropped += 1
    return " ".join(kept), dropped


def summarize(f: dict) -> dict:
    """The Executive Director's summary for the board, with any unverifiable number removed."""
    run = run_agent(BoardSummary, (PROMPTS_DIR / "board_update.md").read_text(),
                    "Facts for the board update (JSON):\n" + json.dumps(f, indent=1), agent="executive_director")
    out = run.output.model_dump()
    allowed, removed = _allowed(f), 0
    out["headline"], n = _clean(out["headline"], allowed)
    removed += n
    out["summary"], n = _clean(out["summary"], allowed)
    removed += n
    for key in ("highlights", "asks"):
        kept = []
        for item in out[key]:
            cleaned, n = _clean(item, allowed)
            removed += n
            if cleaned:
                kept.append(cleaned)
        out[key] = kept
    out["headline"] = out["headline"] or "Where our grants stand"
    out["numbers_removed"] = removed
    usage = usage_dict(run.usage)
    log_run("executive_director", usage, {"task": "board_update", "numbers_removed": removed})
    return {"summary": out, "usage": usage}

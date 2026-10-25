"""Applications: every grant being written, with how far along each answer is."""

from dash import html

from .. import db
from ..pipeline import pipeline_rows
from ..writing import length_check
from .components import card, days_text, deadline_full, deadline_text, empty, health_label, link, page_header, progress_bar

WRITING = {"Drafting", "Internal Review", "Ready to Submit"}


def summary(opp_id: int) -> dict:
    qs = db.list_questions(opp_id)
    coach_scores, flagged = [], 0
    for q in qs:
        c = db.latest_review(q["id"], "coach")
        if c and c["response_text"].strip() == q["response"].strip():
            coach_scores.append(c["result"]["overall"])
        e = db.latest_review(q["id"], "evidence")
        if e and e["response_text"].strip() == q["response"].strip():
            flagged += e["result"]["counts"].get("Needs evidence", 0) + e["result"]["counts"].get("Contradicted", 0)
    return {
        "n": len(qs),
        "answered": sum(bool(q["response"].strip()) for q in qs),
        "approved": sum(q["status"] == "Approved" for q in qs),
        "over": sum(not length_check(q["response"], q["limit_type"], q["limit_value"])["ok"] for q in qs),
        "coach": round(sum(coach_scores) / len(coach_scores)) if coach_scores else None,
        "flagged": flagged,
    }


def layout():
    everything = pipeline_rows(db.list_opportunities(), db.list_tasks())
    rows = [r for r in everything if r["status"] in WRITING or db.list_questions(r["id"])]
    shown = {r["id"] for r in rows}
    deciding = [r for r in everything if r["id"] not in shown and r["status"] in ("Researching", "Go / No-Go")]
    closed = [r for r in everything if r["id"] not in shown and r["status"] not in ("Researching", "Go / No-Go")]
    if not rows:
        body = empty("No applications yet. Decide Go on an opportunity to start writing.")
    else:
        head = html.Thead(html.Tr([html.Th(h) for h in ["Application", "Deadline", "Answers", "Approved",
                                                         "Avg coach score", "Claims to fix", "Risk", ""]]))
        trs = []
        for r in rows:
            s = summary(r["id"])
            pct = round(100 * s["answered"] / s["n"]) if s["n"] else 0
            trs.append(html.Tr([
                html.Td([link(r["funder"], f"/application/{r['id']}", "row-link"),
                         html.Div(r["program_name"], className="muted small")]),
                html.Td([html.Span(deadline_text(r), title=deadline_full(r)),
                         html.Div(days_text(r["days_remaining"]), className="muted small")],
                        className="nowrap"),
                html.Td([progress_bar(pct), html.Div(f"{s['answered']} of {s['n']}" +
                                                     (f" · {s['over']} over limit" if s["over"] else ""),
                                                     className="muted small")]),
                html.Td(f"{s['approved']} / {s['n']}", className="num"),
                html.Td(f"{s['coach']}/100" if s["coach"] is not None else "—", className="num"),
                html.Td(str(s["flagged"]) if s["flagged"] else "—", className="num"),
                html.Td(health_label(r["health"])),
                html.Td(link("Open workspace →", f"/application/{r['id']}", "small-link"), className="nowrap"),
            ]))
        body = html.Table([head, html.Tbody(trs)], className="table")
    return html.Div([
        page_header("Applications", "Write each answer from your own evidence. In any question, Review suggestions has "
                                    "the Grant Coach mark up your answer and the Evidence Checker test each claim. "
                                    "You approve every word."),
        html.Div(
            [html.Span(f"Showing the {len(rows)} grant{'s' if len(rows) != 1 else ''} you've decided to apply for. "),
             html.Span(f"{len(deciding)} still awaiting a Go / No-Go decision "
                       f"({', '.join(r['funder'] for r in deciding)}). ") if deciding else None,
             html.Span(f"{len(closed)} submitted or closed ({', '.join(r['funder'] for r in closed)}). ") if closed else None,
             link("See everything in the Pipeline →", "/pipeline", "small-link") if (deciding or closed) else None],
            className="apps-note"),
        html.Div(body, className="card flush"),
        html.P("Claims to fix counts Needs evidence and Contradicted claims from the latest evidence check of the "
               "current text.", className="hint"),
    ])

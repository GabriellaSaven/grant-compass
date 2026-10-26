"""Home: what needs attention today, at a glance."""

from datetime import date, timedelta

from dash import dcc, html

from ..dates import dfmt
from .. import db
from ..pipeline import HEALTH_ORDER, pipeline_rows
from ..profile import completeness
from .components import (
    HEALTH_CLASS, card, days_text, deadline_text, empty, health_label, link, money, section_title, stat,
)

WINDOW = 60  # days shown on the deadline strip
FUNNEL = ["Researching", "Go / No-Go", "Drafting", "Internal Review", "Ready to Submit", "Submitted", "Won"]


def deadline_strip(active: list[dict]):
    """Every active grant due in the next 60 days as a dot on a timeline, coloured by risk; click to open."""
    due = sorted((r for r in active if r["days_remaining"] is not None and r["days_remaining"] <= WINDOW),
                 key=lambda r: r["days_remaining"])
    if not due:
        return empty("No deadlines in the next 60 days.")
    today = date.today()
    ticks = [html.Div([html.Span(className="tick-line"),
                       html.Span("Today" if d == 0 else dfmt((today + timedelta(days=d)), "%-d %b"),
                                 className="tick-label")],
                      className="tick", style={"left": f"{d / WINDOW * 100}%"}) for d in range(0, WINDOW + 1, 15)]
    dots, lanes = [], {"down": -99.0, "up": -99.0, "down2": -99.0, "up2": -99.0}
    for i, r in enumerate(due):
        days = max(0, r["days_remaining"])
        x = days / WINDOW * 100
        # Labels take the first lane (below, above, then further out) with room, so close deadlines never collide.
        lane = next((ln for ln, last in lanes.items() if x - last >= 17), min(lanes, key=lanes.get))
        lanes[lane] = x
        dots.append(dcc.Link(
            [html.Span(className="dot-mark"),
             html.Span([html.Strong(r["funder"]), html.Span(f"{deadline_text(r)} · {days_text(r['days_remaining'])}")],
                       className="dot-label")],
            href=f"/opportunity/{r['id']}", title=f"{r['funder']} — {r['program_name']}: {r['health']}",
            className=f"strip-dot h-{HEALTH_CLASS.get(r['health'], 'ok')} {lane}",
            style={"left": f"{x}%", "--i": i}))
    legend = html.Div([html.Span([html.Span(className=f"leg h-{c}"), name]) for name, c in
                       [("On track", "ok"), ("Needs attention", "attn"), ("At risk", "risk"), ("Critical", "crit")]],
                      className="strip-legend")
    return html.Div([html.Div([html.Div(className="strip-axis"), *ticks, *dots], className="strip"), legend])


def waiting_list():
    """Open comment threads that ask someone to do something, newest first, each linking to the words."""
    asks = [a for a in db.open_asks() if a["assignee"]][:6]
    if not asks:
        return empty("Nobody is waiting on anyone. Ask a teammate by commenting on an answer.")
    def item(a):
        base = "report" if a["kind"] == "report" else "application"
        return html.Li([
            html.Span(a["assignee"].split(" (")[0], className="wait-who"),
            html.Div([dcc.Link(f"“{(a['quote'] or a['body'])[:70]}…”" if len(a["quote"] or a["body"]) > 70
                               else f"“{a['quote'] or a['body']}”", href=f"/{base}/{a['opportunity_id']}/{a['question_id']}",
                               className="row-link"),
                      html.Div(f"{a['author'].split(' (')[0]}: {a['body'][:90]}", className="small"),
                      html.Div(a["funder"], className="muted small")]),
        ], className="wait-item")
    return html.Ul([item(a) for a in asks], className="waiting")


def funding_bar(rows: list[dict]):
    """Potential funding at each stage, as one bar: how much is still a lead, being written, or submitted."""
    totals = [(s, sum(r["award_max"] or 0 for r in rows if r["status"] == s),
               sum(r["status"] == s for r in rows)) for s in FUNNEL]
    totals = [t for t in totals if t[2]]
    whole = sum(t[1] for t in totals) or 1
    if not totals:
        return empty("Add grants from Discover to see your funding pipeline.")
    return html.Div([
        html.Div([dcc.Link(html.Span(), className=f"seg seg-{i}", href="/pipeline", title=f"{s}: {money(v)} across {n}",
                           style={"flexGrow": max(v, whole * 0.04)}) for i, (s, v, n) in enumerate(totals)],
                 className="fbar"),
        html.Ul([html.Li([html.Span(className=f"leg seg-{i}"), html.Span(s, className="fl-stage"),
                          html.Span(money(v) if v else "—", className="fl-amt"),
                          html.Span(f"{n} grant{'s' if n != 1 else ''}", className="fl-n")])
                 for i, (s, v, n) in enumerate(totals)], className="flegend"),
    ])


def needs_setup() -> bool:
    prof = db.get_profile()
    return completeness(prof["data"] if prof else {})[0] < 60 or not db.list_documents()


def layout():
    today = date.today()
    rows = pipeline_rows(db.list_opportunities(), db.list_tasks(), today)
    active = [r for r in rows if r["active"]]
    due_month = [r for r in active if r["deadline"] and r["deadline"][:7] == today.isoformat()[:7]]
    at_risk = [r for r in active if r["health"] in ("At Risk", "Critical")]
    potential = sum(r["award_max"] or 0 for r in active)
    attention = sorted((r for r in active if r["health"] != "On Track"),
                       key=lambda r: (HEALTH_ORDER.index(r["health"]), r["days_remaining"] or 999))
    upcoming = sorted((r for r in active if r["days_remaining"] is not None and 0 <= r["days_remaining"] <= 30),
                      key=lambda r: r["days_remaining"])
    sample = any(r["sample"] for r in rows)

    def attention_item(r):
        return html.Li(
            [
                html.Div([link(r["funder"], f"/opportunity/{r['id']}", "row-link"),
                          html.Span(f" · {days_text(r['days_remaining'])} remaining"
                                    if r["days_remaining"] is not None and r["days_remaining"] >= 0 else "",
                                    className="muted")]),
                html.Div("; ".join(r["health_reasons"]), className="muted small"),
                health_label(r["health"]),
            ],
            className="attention-item",
        )

    return html.Div(
        [
            html.Div(dfmt(today, "%A %-d %B %Y"), className="eyebrow"),
            html.H1("Good to see you. Here's where your grants stand.", className="welcome"),
            html.Div("You're viewing fictional sample data. Replace it with your own documents and opportunities.",
                     className="banner") if sample else None,
            html.Div([html.Span("Finish setting up: the AI needs your profile and documents to find and write "
                                "grants for you. "), link("See the three steps →", "/welcome", "small-link")],
                     className="banner") if needs_setup() else None,
            html.Div(
                [
                    stat(str(len(active)), "active opportunities"),
                    stat(str(len(due_month)), "due this month"),
                    stat(str(len(at_risk)), "at risk", "risk" if at_risk else ""),
                    stat(money(potential), "total potential funding"),
                ],
                className="stats",
            ),
            card([section_title("Next 60 days", link("Pipeline →", "/pipeline", "small-link")),
                  deadline_strip(active)], className="strip-card"),
            html.Div(
                [
                    card([section_title("Needs attention today"),
                          html.Ul([attention_item(r) for r in attention], className="attention")
                          if attention else empty("Nothing urgent. Every active grant is on track.")]),
                    html.Div([card([section_title("Funding by stage"), funding_bar(rows)]),
                              card([section_title("Waiting on people"), waiting_list()])], className="stack"),
                ],
                className="two-col wide-left",
            ),
        ]
    )

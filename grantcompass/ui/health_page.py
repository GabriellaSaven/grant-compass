"""Agent health: the Executive Director's briefing, then each agent's numbers (computed in code)."""

from datetime import datetime

from urllib.parse import quote

from dash import ALL, Input, Output, callback, ctx, html
from dash.exceptions import PreventUpdate

from .. import db
from ..director import review
from ..errors import friendly
from ..health import AGENTS, INITIALS, PERSONAS, WHERE, compute
from .components import card, label, page_header, profile_tabs

STATUS_CLASS = {"Healthy": "ok", "Watch": "attn", "Attention": "crit", "Act": "crit", "Not used yet": "muted"}
KIND_CLASS = {"working well": "ok", "watch": "attn", "act": "crit"}
LEVEL_CLASS = {"ok": "", "info": "", "watch": "attn", "attention": "crit"}


def _when(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%-d %b %Y, %H:%M")


FIELD_WORDS = {"runs": "runs", "runs_7d": "runs this week", "cost_usd": "spent", "avg_cost_usd": "cost per run",
               "avg_seconds": "seconds per run", "errors": "failed runs", "limit_hits": "runs stopped by a limit",
               "provider_blocks": "pages refused by the provider", "failure_rate": "failure rate", "status": "status"}


def evidence(metric: str, value, health: dict) -> str:
    """The metric a finding rests on, in words: 'Fit Agent · assessments with a failed quote: 23 of 55'."""
    agent, _, field = metric.partition(".")
    for a in health["agents"].values():
        for c in a["checks"]:
            if c["metric"] == metric:
                return f"{a['name']} · {c['label']}: {c['shown']}"
    name = health["agents"][agent]["name"] if agent in health["agents"] else "Whole team"
    shown = f"{value:.0%}" if field == "failure_rate" and isinstance(value, (int, float)) else value
    return f"{name} · {FIELD_WORDS.get(field, field)}: {shown}"


def _phrase(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def key_fact(a: dict) -> str:
    """The one number that best says how this agent is doing."""
    checks = {c["metric"]: c for c in a["checks"]}
    k = a["key"]
    if k == "fit_agent" and checks["fit_agent.assessments"]["value"]:
        return f"{checks['fit_agent.quote_warning_rate']['shown']} assessments had an unverified quote"
    if k == "grant_writer" and checks["grant_writer.unverified_source_rate"]["value"] is not None:
        return f"{checks['grant_writer.unverified_source_rate']['shown']} cited facts unverified"
    if k == "evidence_checker":
        return _phrase(checks["evidence_checker.claims"]["value"], "claim checked", "claims checked")
    if k == "assistant":
        return _phrase(a["runs"], "question answered", "questions answered") + " · read-only"
    if k == "grant_coach":
        return _phrase(a["runs"], "review")
    return _phrase(a["runs"], "page read", "pages read")


def tile(a: dict):
    def num(v, fmt):
        return fmt.format(v) if v is not None else "—"
    fails = a["errors"] + a["limit_hits"]
    return html.Div([
        html.Div([html.Div([html.Span(a["name"], className="tile-name"),
                            html.Div(f"{PERSONAS[a['key']][1]} · {WHERE[a['key']]}", className="tile-persona")]),
                  label(a["status"], STATUS_CLASS[a["status"]])], className="tile-head"),
        html.Div(key_fact(a), className="tile-fact"),
        html.Div(f"{num(a['avg_cost_usd'], '${:.4f}')} a run · {num(a['avg_seconds'], '{:.1f}s')} · "
                 f"{_phrase(fails, 'failure')}", className="tile-meta"),
        html.Div("Why: " + "; ".join(a["reasons"]), className="ag-why") if a["reasons"] else None,
        html.Details([html.Summary("Details", className="tile-more"),
                      html.P(a["job"], className="tile-job"),
                      html.Ul([html.Li([html.Span(c["label"]), html.Strong(c["shown"])],
                                       className="ag-check " + LEVEL_CLASS[c["level"]]) for c in a["checks"]],
                              className="ag-checks")]),
    ], className="tile tile-" + STATUS_CLASS[a["status"]])


def banner(h: dict):
    team = [a for k, a in h["agents"].items() if k != "executive_director"]
    flagged = [a for a in team if a["status"] in ("Watch", "Attention")]
    t = h["totals"]
    title = ("All six agents are healthy" if not flagged else
             f"{_phrase(len(flagged), 'agent needs', 'agents need')} attention: "
             + ", ".join(a["name"] for a in flagged))
    return html.Div([
        html.Div("✓" if not flagged else "!", className="banner-mark"),
        html.Div([html.Div(title, className="banner-title"),
                  html.Div(f"{t['runs']:,} AI runs · ${t['cost_usd']:.3f} spent · about ${t['avg_cost_usd'] or 0:.4f} "
                           f"a run · {_phrase(t['failures'], 'failure')}", className="banner-sub")]),
    ], className="health-banner " + ("ok" if not flagged else "attn"))


def director_card(h: dict):
    reports = db.list_director_reports()
    button = html.Button("Run review", id="dir-run", n_clicks=0, className="btn btn-quiet btn-small")
    if not reports:
        return card([html.Div([html.Div([html.Div("Executive Director", className="dir-title"),
                                          html.Div("Hasn't reviewed the team yet", className="dir-when")]), button],
                              className="dir-bar"),
                      html.P("Run a review for a short briefing on what to watch and what to do next. "
                             "About 8 seconds, under $0.001.", className="hint")], className="director")
    r, last = reports[0]["result"], reports[0]
    agent_name = {**{k: v[0] for k, v in AGENTS.items()}, "all": "Whole team"}

    def item(f):
        return html.Li([html.Strong(agent_name.get(f["agent"], f["agent"]) + ": "), f["finding"]],
                       title="Based on " + evidence(f["metric"], f["value"], h))

    watch = [f for f in r["findings"] if f["kind"] != "working well"]
    good = [f for f in r["findings"] if f["kind"] == "working well"]
    small = []
    if r["overall"] != "Healthy" and r.get("code_status") == "Healthy":
        small.append("Stricter than the app's own rules: things to keep an eye on, not failures.")
    if r.get("raised_by_code"):
        small.append(f"Rating raised from {r['model_overall']} by the app's rules.")
    if r.get("claims_removed"):
        small.append(f"{_phrase(r['claims_removed'], 'finding')} removed: the numbers didn't match the app's data.")
    return card([
        html.Div([html.Div([html.Div(["Executive Director  ", label(r["overall"], STATUS_CLASS.get(r["overall"], "muted"))],
                                     className="dir-title"),
                            html.Div(f"Reviewed {_when(last['created'])}", className="dir-when")]), button],
                 className="dir-bar"),
        html.P(r["headline"], className="dir-headline"),
        html.Div([html.Span("Do next", className="dir-k"), html.Span(r["top_action"])], className="dir-action"),
        html.Div([html.Div(f"To watch ({len(watch)})", className="dir-sub"), html.Ul([item(f) for f in watch],
                                                                                   className="dir-list")])
        if watch else None,
        html.Details([html.Summary(f"Working well ({len(good)})", className="toggle"),
                      html.Ul([item(f) for f in good], className="dir-list")]) if good else None,
        html.P(" ".join(small), className="dir-meta") if small else None,
    ], className="director")


# --- The team diagram ---------------------------------------------------------------------------
# Positions on a 1000 x 360 canvas: work flows left to right, the Director oversees from above,
# the assistant sits beside you.
NODES = {"executive_director": (500, 48), "research_agent": (80, 190), "fit_agent": (265, 190), "you": (450, 190),
         "grant_writer": (635, 190), "grant_coach": (800, 115), "evidence_checker": (800, 265),
         "library": (940, 190), "assistant": (450, 320)}
FLOW = [("research_agent", "fit_agent"), ("fit_agent", "you"), ("you", "grant_writer"),
        ("grant_writer", "grant_coach"), ("grant_writer", "evidence_checker"),
        ("grant_coach", "library"), ("evidence_checker", "library")]
TONE = {"Healthy": "#3f7d5a", "Watch": "#c4952f", "Attention": "#b4473c", "Not used yet": "#b9b9b0"}


def _edges_svg() -> str:
    """Connector lines as one SVG image under the nodes: solid for the flow of work, dashed for oversight."""
    lines = []
    for a, b in FLOW:
        (x1, y1), (x2, y2) = NODES[a], NODES[b]
        lines.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#9fbfae' stroke-width='2.5' "
                     f"marker-end='url(#arrow)'/>")
    dx, dy = NODES["executive_director"]
    for k in ("research_agent", "fit_agent", "grant_writer", "grant_coach", "evidence_checker", "assistant"):
        x, y = NODES[k]
        lines.append(f"<line x1='{dx}' y1='{dy}' x2='{x}' y2='{y}' stroke='#c9c4b6' stroke-width='1.5' "
                     f"stroke-dasharray='5 6'/>")
    ax, ay = NODES["assistant"]
    yx, yy = NODES["you"]
    lines.append(f"<line x1='{ax}' y1='{ay}' x2='{yx}' y2='{yy}' stroke='#9fbfae' stroke-width='2.5' "
                 f"stroke-dasharray='2 5' stroke-linecap='round'/>")
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1000 360' preserveAspectRatio='none'>"
           "<defs><marker id='arrow' viewBox='0 0 10 10' refX='34' refY='5' markerWidth='7' markerHeight='7' "
           "orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill='#9fbfae'/></marker></defs>"
           + "".join(lines) + "</svg>")
    return "data:image/svg+xml," + quote(svg)


def _node(key: str, h: dict, selected: str):
    x, y = NODES[key]
    style = {"left": f"{x / 10}%", "top": f"{y / 360 * 100}%"}
    if key in ("you", "library"):
        label_ = ("You", "Decide, edit, approve") if key == "you" else ("Answer Library", "Approved answers")
        return html.Div([html.Span("★" if key == "library" else "✓", className="node-avatar human"),
                         html.Span(label_[0], className="node-name"), html.Span(label_[1], className="node-role")],
                        className="team-node fixed", style=style)
    title = PERSONAS[key][1]
    status = h["agents"][key]["status"]
    return html.Button([html.Span(INITIALS[key], className="node-avatar", style={"--ring": TONE[status]}),
                        html.Span(title, className="node-name"),
                        html.Span(WHERE[key] if AGENTS[key][0] == title else f"{AGENTS[key][0]} · {WHERE[key]}",
                                  className="node-role")],
                       id={"type": "ag-node", "key": key}, n_clicks=0, title=f"{AGENTS[key][0]}: {status}",
                       className="team-node" + (" selected" if key == selected else ""), style=style)


def persona_card(key: str, h: dict):
    _, title, archetype, manner, tools, guards = PERSONAS[key]
    a = h["agents"][key]
    return html.Div([
        html.Div([html.Div([html.Div(title, className="pc-name"),
                            html.Div(WHERE[key] if AGENTS[key][0] == title else f"{AGENTS[key][0]} · {WHERE[key]}",
                                     className="pc-title")]),
                  label(a["status"], STATUS_CLASS[a["status"]])], className="pc-head"),
        html.Div(archetype, className="pc-arch"),
        html.P(f"“{manner}”", className="pc-quote"),
        html.Div([html.Div([html.Div("Job", className="pc-k"), html.Div(AGENTS[key][1])]),
                  html.Div([html.Div("Works from", className="pc-k"), html.Div(tools)]),
                  html.Div([html.Div("Kept honest by", className="pc-k"), html.Div(guards)])], className="pc-grid"),
        html.Div(f"{a['runs']} runs so far" + (f" · {key_fact(a)}" if key != "executive_director" else ""),
                 className="pc-meta"),
    ], className="persona-card")


def team_diagram(h: dict, selected: str = "executive_director"):
    return html.Div([
        html.Div([html.Img(src=_edges_svg(), className="team-edges", alt=""),
                  *[_node(k, h, selected) for k in NODES]], className="team-canvas"),
        html.Div([html.Span([html.Span(className="tl solid"), "work flows to the next colleague"]),
                  html.Span([html.Span(className="tl dashed"), "overseen by the Executive Director"]),
                  html.Span([html.Span(className="tl ring"), "ring colour = health"])], className="team-legend"),
        html.Div(persona_card(selected, h), id="persona-card"),
    ], className="team-diagram")


def body():
    h = compute()
    t = h["totals"]
    unpriced = (f" {t['unpriced_runs']} early runs were logged before prices were set, so they count as runs but "
                "not cost.") if t["unpriced_runs"] else ""
    return [
        banner(h),
        html.Div(director_card(h), id="dir-card"),
        card([html.Div([html.Div("Meet the team", className="dir-title"),
                        html.Div("Click anyone to see what they do and what keeps them honest.", className="dir-when")]),
              html.Div(team_diagram(h), id="team-wrap")], className="team-card"),
        html.Div([tile(a) for k, a in h["agents"].items() if k != "executive_director"], className="tile-grid"),
        html.Details([
            html.Summary("How this works", className="toggle"),
            html.P("The numbers come straight from the app's own logs and saved results, with no AI involved. "
                   "Hover over any of the Executive Director's points to see the number it rests on." + unpriced),
            html.P("The Executive Director is a seventh agent. It sees only these numbers, never funder pages. The "
                   "app removes any point whose number doesn't match, and never lets its rating be rosier than the "
                   "rules below."),
            html.Div("Status rules", className="dir-sub"),
            html.Ul([html.Li(x) for x in h["rules"]]),
        ], className="block how"),
    ]


def layout():
    return html.Div([
        profile_tabs("/profile/health"),
        page_header("Agent health", "How each AI agent is performing, what it costs, and anything that needs attention."),
        html.Div(body(), id="health-body"),
    ])


@callback(Output("health-body", "children"), Input("dir-run", "n_clicks"),
          running=[(Output("dir-run", "disabled"), True, False), (Output("dir-run", "children"), "Reviewing…",
                                                                  "Run review")],
          prevent_initial_call=True)
def run_review(n):
    if not n:
        raise PreventUpdate
    try:
        review()
    except Exception as exc:
        return [html.P(friendly(exc), className="error-text"), *body()]
    return body()


@callback(Output("team-wrap", "children"), Input({"type": "ag-node", "key": ALL}, "n_clicks"), prevent_initial_call=True)
def pick_colleague(clicks):
    if not ctx.triggered_id or not any(clicks):
        raise PreventUpdate
    return team_diagram(compute(), ctx.triggered_id["key"])

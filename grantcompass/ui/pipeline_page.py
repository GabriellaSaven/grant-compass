"""Pipeline: every saved opportunity with fit, funding, deadline, progress,
risk and the next action, recomputed from today's date on every visit.
Click a row to open the full record in a pop-up."""

from datetime import date

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from .. import db
from ..pipeline import HEALTH_ORDER, STATUSES, explain_health, pipeline_rows
from ..writing import length_check
from .components import (
    award_full, award_range, days_text, deadline_full, deadline_text, empty, fit_class, health_label, page_header, progress_bar,
)
from .fit_explain import fit_explainer
from .opportunity_page import compact_owner_options
from .opportunity_page import layout as opportunity_view

REC_SHORT = {"Go": "Go", "Research further": "Review", "No-Go": "No-Go"}
DEADLINES = [
    {"label": "Any deadline", "value": "all"},
    {"label": "Overdue", "value": "overdue"},
    {"label": "Next 7 days", "value": "7"},
    {"label": "Next 30 days", "value": "30"},
    {"label": "Next 90 days", "value": "90"},
    {"label": "No deadline set", "value": "none"},
]
TRASH_ICON = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
              "stroke='%236e736c' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>"
              "<path d='M3 6h18'/><path d='M8 6V4h8v2'/><path d='M19 6l-1 14H6L5 6'/>"
              "<path d='M10 11v6'/><path d='M14 11v6'/></svg>")
FILTER_IDS = ["pipe-show", "pipe-f-owner", "pipe-f-deadline", "pipe-f-status", "pipe-f-risk", "pipe-f-area"]


# --- What each row needs ---------------------------------------------------------
def rows():
    return pipeline_rows(db.list_opportunities(), db.list_tasks())


def fit_cell(opp_id: int):
    """Fit % with its explanation (points per dimension) on hover."""
    a = db.latest_assessment(opp_id)
    if not a or a["result"].get("fit_score") is None:
        return html.Td(html.Span("Not assessed", className="muted small"), className="pop-cell")
    r = a["result"]
    pill = html.Span([html.Strong(f"{r['fit_score']}%"), f" · {REC_SHORT[r['recommendation']]}"],
                     className=f"fit-pill rec-{fit_class(r['fit_score'])}")
    return html.Td(html.Div(
        [html.Span([pill, html.Span("ⓘ", className="risk-i")], className="risk-sum", tabIndex="0"),
         html.Div(fit_explainer(r), className="risk-pop fit-pop")],
        className="hover-pop"), className="pop-cell")


def next_action(r: dict) -> dict | None:
    """The single most useful next step for this grant: {label, kind ('modal'|'workspace'), q, late}."""
    if not r["active"]:
        return None
    today = date.today()
    late = [t for t in r["outstanding"] if date.fromisoformat(t["due"]) < today]
    if r["status"] in ("Researching", "Go / No-Go") and not r.get("decision"):
        # Still deciding: assess first, then decide.
        if not db.latest_assessment(r["id"]):
            return {"label": "Run Go / No-Go assessment", "kind": "modal", "late": False}
        return {"label": "Make Go / No-Go decision", "kind": "modal", "late": False}
    if late:  # an overdue step beats everything else
        return {"label": late[0]["title"], "kind": "modal", "late": True}
    questions = db.list_questions(r["id"])
    if not questions and r["status"] in ("Drafting", "Internal Review"):
        return {"label": "Add the application questions", "kind": "workspace", "q": None, "late": False}
    for i, q in enumerate(questions, 1):
        if not q["response"].strip():
            return {"label": f"Draft Q{i}", "kind": "workspace", "q": q["id"], "late": False}
    for i, q in enumerate(questions, 1):
        if not length_check(q["response"], q["limit_type"], q["limit_value"])["ok"]:
            return {"label": f"Cut Q{i} to the limit", "kind": "workspace", "q": q["id"], "late": False}
    for i, q in enumerate(questions, 1):
        if q["status"] != "Approved":
            return {"label": f"Review & approve Q{i}", "kind": "workspace", "q": q["id"], "late": False}
    if r["outstanding"]:
        return {"label": r["outstanding"][0]["title"], "kind": "modal", "late": False}
    return None


def area_text(r: dict) -> str:
    return " ".join(str(r.get(k) or "") for k in ("funder", "program_name", "focus_area", "summary")).lower()


def apply_filters(data: list[dict], show, owner, deadline, statuses, risks, area) -> list[dict]:
    if show == "active":
        data = [r for r in data if r["active"]]
    if owner and owner != "all":
        data = [r for r in data if (r["owner"] or "unassigned") == owner]
    if deadline and deadline != "all":
        if deadline == "none":
            data = [r for r in data if r["days_remaining"] is None]
        elif deadline == "overdue":
            data = [r for r in data if r["days_remaining"] is not None and r["days_remaining"] < 0]
        else:
            data = [r for r in data if r["days_remaining"] is not None and 0 <= r["days_remaining"] <= int(deadline)]
    if statuses:
        data = [r for r in data if r["status"] in statuses]
    if risks:
        data = [r for r in data if r["active"] and r["health"] in risks]
    if (area or "").strip():
        words = area.lower().split()
        data = [r for r in data if all(w in area_text(r) for w in words)]
    return data


# --- Table -------------------------------------------------------------------------
def cell(content, opp_id: int, col: int, cls: str = ""):
    """A table cell whose whole area opens the grant's pop-up."""
    return html.Td(html.Div(content, id={"type": "pipe-row", "id": opp_id, "c": col}, n_clicks=0,
                            className="cell-hit"), className=cls)


def risk_cell(r: dict):
    """Risk label with its explanation (which rule fired, and the facts) on hover."""
    if not r["active"]:
        return html.Td(html.Span("Closed", className="muted"), className="pop-cell")
    qs = db.list_questions(r["id"])
    ex = explain_health(r, db.list_tasks(r["id"]), sum(bool(q["response"].strip()) for q in qs), len(qs))
    return html.Td(html.Div(
        [html.Span([health_label(r["health"]), html.Span("ⓘ", className="risk-i")], className="risk-sum",
                   tabIndex="0"),
         html.Div([
             html.Div(f"Why {r['health'].lower()}", className="risk-h"),
             html.Ul([html.Li(b) for b in ex["because"]], className="risk-because") if ex["because"] else
             html.Div("No warning rules apply.", className="small"),
             html.Div("Details", className="risk-k"),
             html.Ul([html.Li(f) for f in ex["facts"]]),
             html.Div(ex["rule"], className="risk-rule"),
         ], className="risk-pop")],
        className="hover-pop"), className="pop-cell")


def action_cell(r: dict):
    act = next_action(r)
    if not act:
        return html.Td(html.Span("—", className="muted"), className="action-cell")
    return html.Td(html.Button(("Overdue: " if act["late"] else "") + act["label"] + " →",
                               id={"type": "pipe-action", "id": r["id"]}, n_clicks=0,
                               className="next-action" + (" late" if act["late"] else "")),
                   className="action-cell")


def table(show="active", owner="all", deadline="all", statuses=None, risks=None, area=""):
    everything = rows()
    data = apply_filters(everything, show, owner, deadline, statuses, risks, area)
    if not everything:
        return empty("Nothing here yet. Save an opportunity from Discover to start your pipeline.")
    if not data:
        return html.Div(empty("No grants match these filters."), className="pad")
    data.sort(key=lambda r: (not r["active"], r["days_remaining"] is None, r["days_remaining"] or 0))
    head = html.Thead(html.Tr([html.Th(h) for h in
                               ["Opportunity", "Fit", "Funding", "Deadline", "Stage & progress", "Risk",
                                "Next action", "Responsible", ""]]))
    body = []
    for r in data:
        i = r["id"]
        days = days_text(r["days_remaining"]) if r["active"] else "closed"
        body.append(html.Tr(
            [
                cell([html.Span(r["funder"], className="row-link"),
                      html.Div(r["program_name"], className="muted small"),
                      html.Span(r.get("origin") or "Added manually", className="origin-tag")], i, 0),
                fit_cell(i),
                cell(html.Div(award_range(r), title=award_full(r)), i, 2),
                cell(html.Div([deadline_text(r), html.Div(days, className="muted small")], title=deadline_full(r)),
                     i, 4, "deadline-cell"),
                cell([html.Div(r["status"], className="stage"), progress_bar(r["progress"])], i, 5),
                risk_cell(r),
                action_cell(r),
                html.Td(dcc.Dropdown(compact_owner_options(r["owner"]), r["owner"],
                                     id={"type": "pipe-owner", "id": i}, placeholder="Unassigned",
                                     className="dropdown compact", optionHeight=40)
                        if r["active"] else (r["owner"] or "—").split(" (")[0], className="owner-cell"),
                html.Td(dcc.ConfirmDialogProvider(
                    html.Button(html.Img(src=TRASH_ICON, alt="Delete"), className="trash-btn",
                                title="Delete from pipeline"),
                    id={"type": "pipe-del", "id": i},
                    message=f"Delete “{r['funder']} — {r['program_name']}” from your pipeline?\n\n"
                            "This also removes its application answers, drafts, coach reviews and tasks. "
                            "This can't be undone."),
                    className="trash-cell"),
            ],
            className="pipe-row" + (" closed" if not r["active"] else ""),
        ))
    shown = html.Div(f"Showing {len(data)} of {len(everything)} grants", className="muted small table-count")
    # Fixed column widths: no text in any cell can stretch the table past its card.
    cols = html.Colgroup([html.Col(className=f"col-{c}") for c in
                          ("opp", "fit", "fund", "due", "stage", "risk", "next", "owner", "trash")])
    return [shown, html.Table([cols, head, html.Tbody(body)], className="table pipe-table")]


def legend_items():
    active = [r for r in rows() if r["active"]]
    return [html.Span([health_label(h), html.Span(f" {sum(r['health'] == h for r in active)}", className="count")],
                      className="legend-item") for h in HEALTH_ORDER]


def filter_bar():
    owners = ([{"label": "Everyone", "value": "all"}]
              + [{"label": m["name"], "value": m["label"]} for m in db.list_team()]
              + [{"label": "Unassigned", "value": "unassigned"}])
    return html.Div(
        [
            html.Div([html.Label("Responsible", className="field-label"),
                      dcc.Dropdown(owners, "all", id="pipe-f-owner", clearable=False, className="dropdown")]),
            html.Div([html.Label("Deadline", className="field-label"),
                      dcc.Dropdown(DEADLINES, "all", id="pipe-f-deadline", clearable=False, className="dropdown")]),
            html.Div([html.Label("Status", className="field-label"),
                      dcc.Dropdown(STATUSES, [], id="pipe-f-status", multi=True, placeholder="Any status",
                                   className="dropdown")]),
            html.Div([html.Label("Risk", className="field-label"),
                      dcc.Dropdown(HEALTH_ORDER, [], id="pipe-f-risk", multi=True, placeholder="Any risk",
                                   className="dropdown")]),
            html.Div([html.Label("Funder or programme area", className="field-label"),
                      dcc.Input(id="pipe-f-area", type="text", placeholder="e.g. literacy, Buckeye",
                                className="input", debounce=0.4)]),
            html.Button("Clear", id="pipe-f-clear", className="btn-link"),
        ],
        className="filter-bar card",
    )


def layout():
    data = rows()
    active = [r for r in data if r["active"]]
    counts = {h: sum(r["health"] == h for r in active) for h in HEALTH_ORDER}
    summary = html.Div(legend_items(), id="pipe-legend", className="legend")
    return html.Div(
        [
            page_header("Pipeline", "Which grants are worth pursuing, how much they're worth, and what to do next. "
                                    "Deadlines, progress and risk update automatically.",
                        dcc.RadioItems([{"label": "Active", "value": "active"}, {"label": "All", "value": "all"}],
                                       "active", id="pipe-show", inline=True, className="segmented")),
            filter_bar(),
            summary,
            html.Div(table(), id="pipe-table", className="card flush menus-visible"),
            html.Div(id="pipe-msg", className="form-msg small"),
            html.P("Click a row to open the full record; next-action buttons take you straight to the step "
                   "(drafting actions open the application workspace). Manage the Responsible list under "
                   "Profile → Team.", className="hint"),
            # Centred pop-up holding the full opportunity view (same controls and callbacks as its own page).
            html.Div(
                [
                    html.Div(id="pipe-modal-backdrop", className="modal-backdrop", n_clicks=0),
                    html.Div(
                        [html.Button("×", id="pipe-modal-close", className="modal-close", title="Close (Esc)"),
                         html.Div(id="pipe-modal-body")],
                        className="modal-panel", role="dialog",
                    ),
                ],
                id="pipe-modal", className="modal",
            ),
        ]
    )


# --- Callbacks ------------------------------------------------------------------------
@callback(
    Output("pipe-table", "children"),
    *[Input(i, "value") for i in FILTER_IDS],
    prevent_initial_call=True,
)
def refilter(show, owner, deadline, statuses, risks, area):
    return table(show, owner, deadline, statuses, risks, area)


@callback(
    Output("pipe-f-owner", "value"),
    Output("pipe-f-deadline", "value"),
    Output("pipe-f-status", "value"),
    Output("pipe-f-risk", "value"),
    Output("pipe-f-area", "value"),
    Input("pipe-f-clear", "n_clicks"),
    prevent_initial_call=True,
)
def clear_filters(_n):
    return "all", "all", [], [], ""


@callback(
    Output("pipe-msg", "children"),
    Input({"type": "pipe-owner", "id": ALL}, "value"),
    State({"type": "pipe-owner", "id": ALL}, "id"),
    prevent_initial_call=True,
)
def set_owner(values, ids):
    """Save whichever row's Responsible person changed."""
    changed = []
    for value, i in zip(values, ids):
        opp = db.get_opportunity(i["id"])
        if opp and opp["owner"] != value:
            db.update_opportunity(i["id"], owner=value)
            changed.append(f"{opp['funder']}: {value.split(' (')[0] if value else 'unassigned'}")
    return html.Span("Saved — " + "; ".join(changed), className="ok-text") if changed else no_update


@callback(
    Output("pipe-modal", "className"),
    Output("pipe-modal-body", "children"),
    Output("url", "pathname", allow_duplicate=True),
    Input({"type": "pipe-row", "id": ALL, "c": ALL}, "n_clicks"),
    Input({"type": "pipe-action", "id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_row(_rows, _actions):
    """A row click opens the full record in the pop-up. A next-action click goes straight to the step."""
    if not ctx.triggered_id or not ctx.triggered[0]["value"]:
        return no_update, no_update, no_update
    opp_id = ctx.triggered_id["id"]
    if ctx.triggered_id["type"] == "pipe-action":
        r = next((x for x in rows() if x["id"] == opp_id), None)
        act = next_action(r) if r else None
        if act and act["kind"] == "workspace":
            return no_update, no_update, f"/application/{opp_id}" + (f"/{act['q']}" if act.get("q") else "")
    return "modal open", opportunity_view(opp_id, in_modal=True), no_update


@callback(
    Output("pipe-modal", "className", allow_duplicate=True),
    Output("pipe-modal-body", "children", allow_duplicate=True),
    Output("pipe-table", "children", allow_duplicate=True),
    Input("pipe-modal-close", "n_clicks"),
    Input("pipe-modal-backdrop", "n_clicks"),
    *[State(i, "value") for i in FILTER_IDS],
    prevent_initial_call=True,
)
def close_modal(_a, _b, show, owner, deadline, statuses, risks, area):
    """Close and refresh the table, so changes made in the pop-up show at once."""
    return "modal", None, table(show, owner, deadline, statuses, risks, area)


@callback(
    Output("pipe-table", "children", allow_duplicate=True),
    Output("pipe-legend", "children"),
    Output("pipe-msg", "children", allow_duplicate=True),
    Input({"type": "pipe-del", "id": ALL}, "submit_n_clicks"),
    *[State(i, "value") for i in FILTER_IDS],
    prevent_initial_call=True,
)
def delete_grant(clicks, show, owner, deadline, statuses, risks, area):
    """Runs only after the user confirms in the dialog."""
    if not ctx.triggered_id or not ctx.triggered[0]["value"]:
        return no_update, no_update, no_update
    opp = db.get_opportunity(ctx.triggered_id["id"])
    if not opp:
        return no_update, no_update, no_update
    db.delete_opportunity(opp["id"])
    return (table(show, owner, deadline, statuses, risks, area), legend_items(),
            html.Span(f"Deleted {opp['funder']} — {opp['program_name']}.", className="ok-text"))

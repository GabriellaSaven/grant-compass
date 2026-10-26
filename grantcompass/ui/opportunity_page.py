"""One opportunity: facts, the Go / No-Go assessment with its score explained,
the human decision (which can override the AI), and the workback plan."""

from datetime import date

from dash import ALL, Input, Output, State, callback, dcc, html, no_update

from ..dates import dfmt
from .. import db
from ..errors import friendly
from ..fit import assess
from .fit_explain import fit_explainer
from ..pipeline import STATUSES, health, progress, workback_plan
from .components import (
    REC_CLASS, award_range, card, days_text, deadline_full, deadline_text, empty,
    fit_visual, health_label, label, link, page_header, progress_bar, section_title, usage_line,
)

DECISIONS = ["Go", "Research further", "No-Go"]


def compact_owner_options(current: str | None) -> list[dict]:
    """For narrow columns: the chosen person shows as just their name; the open list shows name and role."""
    out = []
    for value in owner_options(current):
        name, _, role = value.partition(" (")
        role = role.rstrip(")")
        out.append({"label": html.Span([name, html.Span(f" · {role}", className="opt-role") if role else None]),
                    "value": value, "search": value})
    return out


def owner_options(current: str | None) -> list[str]:
    """Everyone on the Team, plus the current person if they have since been removed from it."""
    labels = [m["label"] for m in db.list_team()]
    return labels + ([current] if current and current not in labels else [])
ANSWER_CLASS = {"Yes": "ok", "Partly": "attn", "No": "crit", "Unknown": "muted"}


# --- Sections --------------------------------------------------------------------
def health_block(opp_id: int):
    opp, tasks = db.get_opportunity(opp_id), db.list_tasks(opp_id)
    h, reasons = health(opp, tasks)
    days = None if not opp["deadline"] else (date.fromisoformat(opp["deadline"]) - date.today()).days
    return html.Div(
        [
            html.Div([html.Div("Health", className="k"), health_label(h)]),
            html.Div([html.Div("Deadline", className="k"),
                      html.Div([deadline_text(opp), html.Span(f" · {days_text(days)}", className="muted")]),
                      html.Div(deadline_full(opp), className="small muted deadline-note")
                      if deadline_full(opp) != deadline_text(opp) and not opp.get("deadline") else None]),
            html.Div([html.Div("Progress", className="k"), progress_bar(progress(opp, tasks))]),
            html.Div([html.Div("Award", className="k"), html.Div(award_range(opp))]),
            html.Div([html.Div("Why", className="k"), html.Div("; ".join(reasons) or "Nothing outstanding",
                                                              className="muted")], className="wide"),
        ],
        className="health-strip",
    )


def bullets(title: str, items: list[str], cls: str = ""):
    if not items:
        return None
    return html.Div([html.H3(title), html.Ul([html.Li(i) for i in items])], className=f"block {cls}")


def assessment_block(opp_id: int):
    a = db.latest_assessment(opp_id)
    run_btn_text = "Re-run assessment" if a else "Run Go / No-Go assessment"
    run_btn = html.Button(run_btn_text, id="opp-run", className="btn btn-quiet" if a else "btn btn-primary")
    if not a:
        return html.Div(
            [
                html.P("The Fit Agent will read this opportunity against your Profile and source documents and score "
                       "seven dimensions, each with its evidence. Nothing is decided until you decide.",
                       className="lede"),
                run_btn,
                html.Div(id="opp-run-msg", className="form-msg"),
            ]
        )
    r = a["result"]
    rec = r["recommendation"]
    alerts = []
    if r.get("suspicious_content"):
        alerts.append(html.Div([html.Strong("Instructions found in the funder text were ignored."),
                                html.Ul([html.Li(s) for s in r["suspicious_content"]])],
                               className="alert alert-crit"))
    if r.get("gate"):
        alerts.append(html.Div(r["gate"], className="alert alert-attn"))
    if r.get("quote_warnings"):
        alerts.append(html.Div([html.Strong("Unverified quotes — evidence shown as Inferred, not Supported."),
                                html.Ul([html.Li(w) for w in r["quote_warnings"]])], className="alert alert-attn"))
    fit = r["fit_score"]
    return html.Div(
        [
            html.Div(
                [
                    fit_visual(r),
                    html.Div([html.Div("Recommendation", className="k"), label(rec, REC_CLASS[rec])]),
                    html.Div([html.Div("Application effort", className="k"), html.Div(r["application_effort"])]),
                    html.Div([html.Div("Expected value", className="k"), html.Div(r["expected_value"])]),
                ],
                className="verdict",
            ),
            html.Details([html.Summary(f"Why {fit}%? See the points behind it", className="toggle small"),
                          fit_explainer(r)], className="block fx-details") if fit is not None else None,
            html.P(r["headline"], className="headline"),
            *alerts,
            html.Div(
                [
                    html.H3("Go / No-Go questions"),
                    html.Table(
                        html.Tbody([
                            html.Tr([html.Td(c["question"], className="q"),
                                     html.Td(label(c["answer"], ANSWER_CLASS[c["answer"]])),
                                     html.Td(c["explanation"], className="muted")])
                            for c in r["checks"]
                        ]),
                        className="checks",
                    ),
                ],
                className="block",
            ),
            html.Div(
                [bullets("Why", r["why"]), bullets("Concerns", r["concerns"]), bullets("Risks", r["risks"]),
                 bullets("Missing information", r["missing_information"]), bullets("Next steps", r["next_steps"])],
                className="bullet-grid",
            ),
            html.Div([run_btn, html.Span(f"Assessed {a['created'][:16].replace('T', ' ')}", className="hint")],
                     className="btn-row"),
            html.Div(id="opp-run-msg", className="form-msg"),
            usage_line(a["usage"]),
        ]
    )


def decision_block(opp_id: int, chosen: str | None = None, error: str | None = None):
    """chosen/error: after a refused save, keep the user's pick and say why right under the reason box."""
    opp, a = db.get_opportunity(opp_id), db.latest_assessment(opp_id)
    ai_rec = a["result"]["recommendation"] if a else None
    current = opp["decision"]
    note = None
    if current:
        overrode = ai_rec and current != ai_rec
        note = html.Div(
            [html.Span("Decision recorded: "), label(current, REC_CLASS[current]),
             html.Span(f" — overrides the AI recommendation ({ai_rec})" if overrode else "", className="muted"),
             html.Div(opp["decision_reason"] or "", className="muted small")],
            className="decision-note",
        )
    return html.Div(
        [
            html.P("You make the call. The AI recommendation is advice; choosing differently is recorded as an "
                   "override with your reason.", className="hint"),
            note,
            dcc.RadioItems(DECISIONS, chosen or current or ai_rec, id="opp-decision", className="radio-row", inline=True),
            dcc.Textarea(id="opp-reason", className="textarea short" + (" input-error" if error else ""),
                         placeholder="Reason (required when you override the AI)…"),
            html.Div(error, className="error-text small") if error else None,
            html.Div([html.Button("Save decision", id="opp-save-decision", className="btn btn-primary"),
                      html.Span("Go creates a workback plan and moves the grant to Drafting.", className="hint")],
                     className="btn-row"),
            html.Div(id="opp-decision-msg", className="form-msg"),
        ]
    )


def tasks_block(opp_id: int):
    tasks = db.list_tasks(opp_id)
    if not tasks:
        return empty("A workback plan is created from the deadline when you decide Go.")
    today = date.today()
    rows = []
    for t in tasks:
        due = date.fromisoformat(t["due"])
        late = not t["done"] and due < today
        rows.append(html.Div(
            [
                dcc.Checklist([{"label": "", "value": "done"}], ["done"] if t["done"] else [],
                              id={"type": "task", "id": t["id"]}, className="task-check"),
                html.Span(t["title"], className="task-title" + (" done" if t["done"] else "")),
                html.Span(("Overdue · " if late else "") + dfmt(due, "%-d %b"),
                          className="task-due" + (" late" if late else "")),
            ],
            className="task",
        ))
    return rows


def facts_block(opp: dict):
    def lst(items):
        return html.Ul([html.Li(i) for i in items]) if items else html.P("Not stated", className="muted")

    source = (html.A("Open source page", href=opp["source_url"], target="_blank")
              if opp.get("source_url") else html.Span("Pasted text", className="muted"))
    return html.Div(
        [
            html.Dl([
                html.Div([html.Dt("Geography"), html.Dd(opp["geography"] or "Not stated")]),
                html.Div([html.Dt("Focus area"), html.Dd(opp["focus_area"] or "Not stated")]),
                html.Div([html.Dt("Matched funding"), html.Dd(opp["matched_funding"] or "Not stated")]),
                html.Div([html.Dt("Reporting"), html.Dd(opp["reporting"] or "Not stated")]),
            ], className="facts one-col"),
            html.H3("Eligibility"), lst(opp["eligibility"]),
            html.H3("Restrictions"), lst(opp["restrictions"]),
            html.H3("Application requirements"), lst(opp["requirements"]),
            html.P(source, className="hint"),
        ]
    )


def layout(opp_id: int, in_modal: bool = False):
    """The full opportunity view. In the Pipeline pop-up (in_modal) the back link becomes a full-page link."""
    opp = db.get_opportunity(opp_id)
    if not opp:
        return html.Div([page_header("Not found"), link("← Back to pipeline", "/pipeline")])
    controls = html.Div(
        [
            html.Div([html.Label("Status", className="field-label"),
                      dcc.Dropdown(STATUSES, opp["status"], id="opp-status", clearable=False, className="dropdown")]),
            html.Div([html.Label("Responsible", className="field-label"),
                      dcc.Dropdown(owner_options(opp["owner"]), opp["owner"], id="opp-owner",
                                   placeholder="Unassigned", className="dropdown"),
                      html.Details([html.Summary("+ Add a person", className="toggle small"),
                                    html.Div([dcc.Input(id="opp-person-name", type="text", placeholder="Name",
                                                        className="input"),
                                              dcc.Input(id="opp-person-role", type="text", placeholder="Role",
                                                        className="input"),
                                              html.Button("Add", id="opp-person-add", className="btn btn-quiet")],
                                             className="input-row"),
                                    html.Div(id="opp-person-msg", className="form-msg small")],
                                   id="opp-person-box", className="add-person")]),
        ],
        className="controls",
    )
    return html.Div(
        [
            html.Div([link("Open as full page ↗", f"/opportunity/{opp_id}", "back-link") if in_modal else
                      link("← Back to Pipeline", "/pipeline", "back-link"),
                      link("Open application workspace →", f"/application/{opp_id}", "back-link")
                      if opp["status"] not in ("Researching", "Go / No-Go", "Declined") else None],
                     className="opp-links"),
            html.Div(opp["funder"], className="eyebrow"),
            page_header(opp["program_name"], opp["summary"] or "", controls),
            html.Div(health_block(opp_id), id="opp-health"),
            html.Div(
                [
                    html.Div(
                        [
                            card([section_title("Go / No-Go"),
                                  dcc.Loading(html.Div(assessment_block(opp_id), id="opp-assessment"),
                                              type="dot", color="#2f5d50")]),
                            card([section_title("Your decision"), html.Div(decision_block(opp_id), id="opp-decision-box")]),
                        ],
                        className="stack",
                    ),
                    html.Div(
                        [
                            card([section_title("Workback plan"), html.Div(tasks_block(opp_id), id="opp-tasks")]),
                            card([section_title("Opportunity details"), facts_block(opp)]),
                        ],
                        className="stack",
                    ),
                ],
                className="two-col wide-left",
            ),
            dcc.Store(id="opp-id", data=opp_id),
        ]
    )


# --- Callbacks ---------------------------------------------------------------------
@callback(
    Output("opp-assessment", "children"),
    Output("opp-decision-box", "children"),
    Output("opp-status", "value", allow_duplicate=True),
    Input("opp-run", "n_clicks"),
    State("opp-id", "data"),
    prevent_initial_call=True,
)
def run_assessment(n, opp_id):
    if not n:
        return no_update, no_update, no_update
    opp = db.get_opportunity(opp_id)
    try:
        res = assess(opp)
    except Exception as exc:
        msg = friendly(exc)
        return [assessment_block(opp_id), html.Div(msg, className="error-text")], no_update, no_update
    db.save_assessment(opp_id, res["result"], res["usage"])
    if opp["status"] == "Researching":
        db.update_opportunity(opp_id, status="Go / No-Go")
    return assessment_block(opp_id), decision_block(opp_id), db.get_opportunity(opp_id)["status"]


@callback(
    Output("opp-decision-box", "children", allow_duplicate=True),
    Output("opp-tasks", "children"),
    Output("opp-health", "children"),
    Output("opp-status", "value"),
    Input("opp-save-decision", "n_clicks"),
    State("opp-id", "data"),
    State("opp-decision", "value"),
    State("opp-reason", "value"),
    prevent_initial_call=True,
)
def save_decision(n, opp_id, decision, reason):
    if not n or not decision:
        return no_update, no_update, no_update, no_update
    a = db.latest_assessment(opp_id)
    ai_rec = a["result"]["recommendation"] if a else None
    reason = (reason or "").strip()
    if ai_rec and decision != ai_rec and not reason:
        box = decision_block(opp_id, chosen=decision,
                             error=f"You chose {decision} but the AI recommends {ai_rec}. Add a short reason, "
                                   "then save again.")
        return box, no_update, no_update, no_update
    status = {"Go": "Drafting", "Research further": "Researching", "No-Go": "Declined"}[decision]
    if not reason and ai_rec == decision:
        reason = "Agreed with the AI recommendation"
    db.update_opportunity(opp_id, decision=decision, decision_reason=reason, status=status)
    opp = db.get_opportunity(opp_id)
    if decision == "Go" and not db.list_tasks(opp_id) and opp["deadline"]:
        db.add_tasks(opp_id, [(t, d, False) for t, d in workback_plan(date.fromisoformat(opp["deadline"]))])
    return decision_block(opp_id), tasks_block(opp_id), health_block(opp_id), status


@callback(
    Output("opp-owner", "options"),
    Output("opp-owner", "value"),
    Output("opp-person-msg", "children"),
    Output("opp-person-box", "open"),
    Input("opp-person-add", "n_clicks"),
    State("opp-person-name", "value"),
    State("opp-person-role", "value"),
    State("opp-owner", "value"),
    prevent_initial_call=True,
)
def add_person(n, name, role, current):
    """Add someone to the Team and make them responsible for this grant in one step."""
    if not n:
        return no_update, no_update, no_update, no_update
    try:
        label = db.add_member(name, role)
    except ValueError as exc:
        return no_update, no_update, html.Span(str(exc), className="error-text"), True
    return owner_options(current) + ([label] if label not in owner_options(current) else []), label, "", False


@callback(
    Output("opp-health", "children", allow_duplicate=True),
    Input("opp-status", "value"),
    Input("opp-owner", "value"),
    State("opp-id", "data"),
    prevent_initial_call=True,
)
def update_fields(status, owner, opp_id):
    opp = db.get_opportunity(opp_id)
    if opp["status"] == status and opp["owner"] == owner:
        return no_update
    db.update_opportunity(opp_id, status=status, owner=owner)
    if status in ("Won", "Lost") and opp["status"] != status and not opp.get("result_date"):
        # Record the decision so the grant shows in Reports and the board update; the award defaults to the
        # top of the funder's range until the team edits it.
        db.update_opportunity(opp_id, result_date=date.today().isoformat(),
                              awarded_amount=opp.get("award_max") if status == "Won" else None)
    return health_block(opp_id)


@callback(
    Output("opp-health", "children", allow_duplicate=True),
    Output("opp-tasks", "children", allow_duplicate=True),
    Input({"type": "task", "id": ALL}, "value"),
    State({"type": "task", "id": ALL}, "id"),
    State("opp-id", "data"),
    prevent_initial_call=True,
)
def toggle_tasks(values, ids, opp_id):
    changed = False
    for v, i in zip(values, ids):
        changed |= db.set_task_done(i["id"], bool(v))
    if not changed:
        return no_update, no_update
    return health_block(opp_id), tasks_block(opp_id)

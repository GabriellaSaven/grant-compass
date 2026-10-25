"""Team: the people who can be made responsible for a grant."""

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from .. import db
from ..pipeline import CLOSED
from .components import card, empty, link, page_header, profile_tabs, section_title


def member_rows():
    team = db.list_team()
    if not team:
        return empty("No one yet. Add the people who work on grants.")
    opps = db.list_opportunities()
    rows = []
    for m in team:
        mine = [o for o in opps if o["owner"] == m["label"] and o["status"] not in CLOSED]
        initials = "".join(w[0] for w in m["name"].split()[:2]).upper()
        rows.append(html.Div(
            [
                html.Span(initials, className="avatar"),
                html.Div([
                    html.Div([html.Span(m["name"], className="member-name"),
                              html.Span(m["role"], className="member-role") if m["role"] else None],
                             className="member-head"),
                    html.Div([html.Span("Responsible for", className="member-k"),
                              *[link(o["funder"], f"/opportunity/{o['id']}", "grant-chip") for o in mine]]
                             if mine else html.Span("No active grants", className="member-k"),
                             className="member-grants"),
                ], className="member-body"),
                html.Button("Remove", id={"type": "team-remove", "id": m["id"]}, className="btn btn-quiet btn-small"),
            ],
            className="member",
        ))
    return rows


def add_form(prefix: str):
    return html.Div([
        html.Label("Name", className="field-label"),
        dcc.Input(id=f"{prefix}-name", type="text", placeholder="e.g. Jordan Lee", className="input full"),
        html.Label("Role", className="field-label"),
        dcc.Input(id=f"{prefix}-role", type="text", placeholder="e.g. Grant Writer (optional)", className="input full"),
        html.Button("Add to team", id=f"{prefix}-add", className="btn btn-primary btn-block"),
    ], className="stack-form")


def layout():
    return html.Div([
        profile_tabs("/profile/team"),
        page_header("Team", "The people who work on grants. Anyone here can be made responsible for an opportunity "
                            "in the pipeline."),
        html.Div([
            card([section_title("Add a person"), add_form("team"),
                  html.Div(id="team-msg", className="form-msg"),
                  html.P("Removing someone keeps their name on grants already assigned to them, so nothing is lost.",
                         className="hint")], className="side-card"),
            card([section_title("People"), html.Div(member_rows(), id="team-list")]),
        ], className="two-col narrow-left"),
    ])


@callback(
    Output("team-list", "children"),
    Output("team-msg", "children"),
    Output("team-name", "value"),
    Output("team-role", "value"),
    Input("team-add", "n_clicks"),
    Input({"type": "team-remove", "id": ALL}, "n_clicks"),
    State("team-name", "value"),
    State("team-role", "value"),
    prevent_initial_call=True,
)
def manage(_add, removes, name, role):
    trig = ctx.triggered_id
    if trig == "team-add":
        try:
            label = db.add_member(name, role)
        except ValueError as exc:
            return no_update, html.Span(str(exc), className="error-text"), no_update, no_update
        return member_rows(), html.Span(f"Added {label}.", className="ok-text"), "", ""
    if isinstance(trig, dict) and any(removes or []):
        db.remove_member(trig["id"])
        return member_rows(), "", no_update, no_update
    return no_update, no_update, no_update, no_update

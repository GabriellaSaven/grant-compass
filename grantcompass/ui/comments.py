"""Comments on the text, Google Docs-style: select words in an answer, comment, @mention or ask a teammate.
Threads have replies and can be resolved; an open thread that asks someone is a to-do for them (shown on
Home and to the assistant). The words a comment is about are kept, so it still makes sense after edits."""

import re
from datetime import datetime

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask import session

from .. import db
from .components import label
from ..dates import dfmt


def _when(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return dfmt(d, "%-d %b, %H:%M")


def team_labels() -> list[str]:
    return [m["label"] for m in db.list_team()]


def me() -> str:
    """Who is commenting: chosen in the tab, else the signed-in account, else the first teammate."""
    team = team_labels()
    chosen = session.get("me")
    if chosen in team:
        return chosen
    user = (session.get("user") or "").split("@")[0].replace(".", " ").lower()
    return next((t for t in team if user and t.lower().startswith(user.split(" ")[0])), team[0] if team else "You")


def short(person: str | None) -> str:
    return (person or "").split(" (")[0]


def mentioned(body: str, team: list[str]) -> str | None:
    """'@Priya' or '@Priya Nair' in a comment means asking that teammate."""
    for tag in re.findall(r"@([A-Za-z][\w'-]*(?:\s[A-Z][\w'-]*)?)", body or ""):
        for t in team:
            name = short(t).lower()
            if name.startswith(tag.lower()) or name.split(" ")[0] == tag.lower().split(" ")[0]:
                return t
    return None


def thread(t: dict, text: str):
    gone = t["quote"] and t["quote"] not in (text or "")
    ask = html.Span(f"→ asks {short(t['assignee'])}", className="cm-ask") if t["assignee"] else None
    return html.Div([
        html.Button([html.Span("“" + (t["quote"][:140] + ("…" if len(t["quote"]) > 140 else "")) + "”"),
                     html.Span(" (these words have since changed)", className="cm-gone") if gone else None],
                    className="cm-quote", **{"data-quote": t["quote"]}, title="Show these words in the answer")
        if t["quote"] else html.Div("On the whole answer", className="cm-quote general"),
        html.Div([html.Strong(short(t["author"])), html.Span(_when(t["created"]), className="cm-time"), ask,
                  label("Resolved", "ok") if t["resolved"] else None], className="cm-head"),
        html.P(t["body"], className="cm-body"),
        *[html.Div([html.Div([html.Strong(short(r["author"])), html.Span(_when(r["created"]), className="cm-time")],
                             className="cm-head"), html.P(r["body"], className="cm-body")], className="cm-reply")
          for r in t["replies"]],
        html.Div([
            dcc.Input(id={"type": "cm-reply-text", "id": t["id"]}, placeholder="Reply…", className="input cm-reply-in",
                      debounce=False, n_submit=0),
            html.Button("Reply", id={"type": "cm-reply", "id": t["id"]}, n_clicks=0, className="btn btn-quiet btn-small"),
            html.Button("Reopen" if t["resolved"] else "✓ Resolve", id={"type": "cm-resolve", "id": t["id"]},
                        n_clicks=0, className="btn-link small-btn"),
        ], className="cm-actions"),
    ], className="cm-thread" + (" resolved" if t["resolved"] else ""), id=f"cm-{t['id']}")


def threads_view(q_id: int, text: str):
    ts = db.list_comments(q_id)
    if not ts:
        return html.P("No comments yet. Select words in the answer and click 💬 Comment, or comment on the whole "
                      "answer above. Type @ and a teammate's name to ask them.", className="hint")
    open_, done = [t for t in ts if not t["resolved"]], [t for t in ts if t["resolved"]]
    return [*[thread(t, text) for t in open_],
            html.Details([html.Summary(f"Resolved ({len(done)})", className="toggle small"),
                          *[thread(t, text) for t in done]]) if done else None]


def tab_label(q_id: int) -> str:
    n = sum(not t["resolved"] for t in db.list_comments(q_id))
    return f"Comments ({n})" if n else "Comments"


def panel(q: dict):
    team = team_labels()
    return html.Div([
        html.Div([html.Span("Commenting as", className="small muted"),
                  dcc.Dropdown(team, me(), id="cm-me", clearable=False, className="dropdown compact cm-me")],
                 className="cm-who"),
        html.Div([
            html.Div(id="cm-quote-view", className="cm-quote-view"),
            dcc.Textarea(id="cm-body", className="textarea short",
                         placeholder="Add a comment… Type @ and a name to ask a teammate."),
            html.Div([dcc.Dropdown([{"label": short(t), "value": t} for t in team], None, id="cm-assign",
                                   placeholder="Ask someone (optional)", className="dropdown compact"),
                      html.Button("Comment", id="cm-post", n_clicks=0, className="btn btn-primary btn-small")],
                     className="cm-post-row"),
            html.Div(id="cm-msg", className="form-msg small"),
        ], className="cm-composer"),
        html.Div(threads_view(q["id"], q["response"]), id="cm-threads"),
        dcc.Store(id="cm-quote"),
        dcc.Store(id="cm-me-saved"),
    ], className="tab-body")


def start_button():
    """In the editor: enabled once words are selected (assets/menu.js passes the selection in)."""
    return html.Div([
        html.Button("💬 Comment", id="cm-start", n_clicks=0, disabled=True, className="btn btn-quiet cm-start",
                    title="Select words in your answer, then comment on them"),
        dcc.Input(id="cm-sel", type="text", value="", className="cm-sel"),
    ], className="cm-start-wrap")


# --- Callbacks ------------------------------------------------------------------------------------
@callback(Output("cm-start", "disabled"), Output("cm-start", "title"), Input("cm-sel", "value"))
def ready_to_comment(sel):
    sel = (sel or "").strip()
    return (not sel, f"Comment on “{sel[:60]}…”" if len(sel) > 60 else f"Comment on “{sel}”") if sel else \
        (True, "Select words in your answer, then comment on them")


@callback(Output("ws-tabs", "value", allow_duplicate=True), Output("cm-quote", "data"),
          Output("cm-quote-view", "children"), Input("cm-start", "n_clicks"), State("cm-sel", "value"),
          prevent_initial_call=True)
def start_comment(n, sel):
    if not n or not (sel or "").strip():
        raise PreventUpdate
    quote = sel.strip()[:500]
    return "comments", quote, html.Div([html.Span("Commenting on ", className="small muted"),
                                        html.Span(f"“{quote[:160]}{'…' if len(quote) > 160 else ''}”")])


@callback(Output("cm-me-saved", "data"), Input("cm-me", "value"), prevent_initial_call=True)
def remember_me(who):
    session["me"] = who  # the next comment, on any page, is posted as this teammate
    return who


@callback(
    Output("cm-threads", "children"), Output("cm-body", "value"), Output("cm-assign", "value"),
    Output("cm-quote", "data", allow_duplicate=True), Output("cm-quote-view", "children", allow_duplicate=True),
    Output("cm-msg", "children"), Output("cm-tab", "label"), Output("ws-qlist", "children", allow_duplicate=True),
    Input("cm-post", "n_clicks"),
    State("cm-body", "value"), State("cm-assign", "value"), State("cm-quote", "data"), State("cm-me", "value"),
    State("ws-q", "data"), State("ws-text", "value"),
    prevent_initial_call=True,
)
def post(n, body, assign, quote, who, qd, text):
    if not n:
        raise PreventUpdate
    body = (body or "").strip()
    if not body:
        return (no_update,) * 5 + (html.Span("Write a comment first.", className="error-text"), no_update, no_update)
    from .workspace_page import question_list

    assignee = assign or mentioned(body, team_labels())
    db.add_comment(qd["id"], body, who or me(), quote, assignee)
    note = f"Asked {short(assignee)}. It's on their list on Home." if assignee else ""
    return (threads_view(qd["id"], text), "", None, None, None, html.Span(note, className="ok-text") if note else "",
            tab_label(qd["id"]), question_list(qd["opp"], qd["id"], qd.get("kind", "application")))


@callback(
    Output("cm-threads", "children", allow_duplicate=True), Output("cm-tab", "label", allow_duplicate=True),
    Output("ws-qlist", "children", allow_duplicate=True),
    Input({"type": "cm-reply", "id": ALL}, "n_clicks"), Input({"type": "cm-reply-text", "id": ALL}, "n_submit"),
    Input({"type": "cm-resolve", "id": ALL}, "n_clicks"),
    State({"type": "cm-reply-text", "id": ALL}, "value"), State({"type": "cm-reply-text", "id": ALL}, "id"),
    State("cm-me", "value"), State("ws-q", "data"), State("ws-text", "value"),
    prevent_initial_call=True,
)
def act(_r, _s, _x, replies, ids, who, qd, text):
    trig = ctx.triggered_id
    if not trig or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    from .workspace_page import question_list

    if trig["type"] == "cm-resolve":
        t = next((t for t in db.list_comments(qd["id"]) if t["id"] == trig["id"]), None)
        if not t:
            raise PreventUpdate
        db.set_comment_resolved(t["id"], not t["resolved"])
    else:
        body = next((v for v, i in zip(replies, ids) if i["id"] == trig["id"]), "") or ""
        if not body.strip():
            raise PreventUpdate
        db.add_comment(qd["id"], body.strip(), who or me(), parent_id=trig["id"])
    return threads_view(qd["id"], text), tab_label(qd["id"]), question_list(qd["opp"], qd["id"],
                                                                            qd.get("kind", "application"))

"""Application writing workspace: one funder question at a time, with the
user's own editor in the middle and the AI helpers (sources, Grant Writer,
Grant Coach, Evidence Checker) beside it. The AI never edits the answer
itself: a draft or suggestion only reaches the editor when the user chooses
it. The editor saves itself a moment after the user stops typing."""

from datetime import date, datetime

from dash import ALL, Input, Output, State, callback, clientside_callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from .. import db
from ..errors import friendly
from ..library import DOC_TYPES
from ..answers import classify, matches as answer_matches, word_count
from ..writing import check_evidence, coach, draft, ensure_fix, length_check
from . import comments
from .components import card, copy_action, days_text, deadline_text, empty, label, link, modal
from .writing_components import (
    _find, highlight_view, length_label, render_coach, draft_notes, render_evidence, source_snippets,
)

Q_STATUSES = ["Not started", "Drafting", "Reviewed", "Approved"]
Q_STATUS_CLASS = {"Not started": "muted", "Drafting": "attn", "Reviewed": "attn", "Approved": "ok"}
APPROVED_TYPE = DOC_TYPES[DOC_TYPES.index("Approved organisational language")]


BASE = {"application": "/application", "report": "/report"}


def question_list(opp_id: int, active_id: int | None, kind: str = "application"):
    items = []
    talk = db.open_comment_counts(opp_id)
    for i, q in enumerate(db.list_questions(opp_id, kind=kind), 1):
        length = length_check(q["response"], q["limit_type"], q["limit_value"])
        items.append(dcc.Link(
            [
                html.Div([html.Span(f"Q{i}", className="q-num"), label(q["status"], Q_STATUS_CLASS[q["status"]])],
                         className="q-head"),
                html.Div(q["prompt"][:90] + ("…" if len(q["prompt"]) > 90 else ""), className="q-prompt"),
                html.Div([html.Span(length["label"], className="small " + ("muted" if length["ok"] else "error-text")),
                          html.Span(f"💬 {talk[q['id']]}", className="q-talk",
                                    title=f"{talk[q['id']]} open comment(s)") if talk.get(q["id"]) else None],
                         className="q-foot"),
            ],
            href=f"{BASE[kind]}/{opp_id}/{q['id']}",
            className="q-item" + (" active" if q["id"] == active_id else ""),
        ))
    return items or [empty("No report sections yet. Upload the funder's reporting requirements above, or add "
                           "sections below." if kind == "report" else
                           "No questions yet. Add the funder's questions below.")]


def add_question_form():
    return html.Details(
        [
            html.Summary("+ Add a question", className="toggle"),
            dcc.Textarea(id="ws-new-prompt", className="textarea short", placeholder="Paste the funder's question"),
            html.Div([
                dcc.Input(id="ws-new-limit", type="number", min=1, placeholder="Limit", className="input"),
                dcc.Dropdown(["words", "characters"], "words", id="ws-new-unit", clearable=False,
                             className="dropdown small-dd"),
            ], className="input-row"),
            html.Button("Add question", id="ws-new-add", className="btn btn-quiet btn-block"),
            html.Div(id="ws-new-msg", className="form-msg"),
        ],
        className="add-q",
    )


def history(q_id: int):
    versions = db.list_versions(q_id)
    if not versions:
        return empty("No saved versions yet.")
    return [html.Div([html.Span(f"{v['created'][:16].replace('T', ' ')} · {v['origin']} · "
                                f"{len(v['text'].split())} words", className="small"),
                      html.Button("Load into editor", id={"type": "ws-restore", "id": v["id"]}, className="btn-link")],
                     className="version") for v in versions[:10]]


def layout(opp_id: int, q_id: int | None = None, kind: str = "application"):
    """The writing workspace. kind='report' is the same editor for a report owed to a funder after a win."""
    opp = db.get_opportunity(opp_id)
    if not opp:
        return html.Div([html.H1("Not found"), link("← Applications", "/applications")])
    questions = db.list_questions(opp_id, kind=kind)
    q = next((x for x in questions if x["id"] == q_id), questions[0] if questions else None)
    days = (date.fromisoformat(opp["deadline"]) - date.today()).days if opp["deadline"] else None
    answered = sum(bool(x["response"].strip()) for x in questions)
    approved = sum(x["status"] == "Approved" for x in questions)

    if kind == "report":
        from .reports_page import report_header  # the report's due date, requirements, programme reports, exports
        header = report_header(opp, questions)
    else:
        header = html.Div([
            link("← All applications", "/applications", "back-link"),
            html.Div(opp["funder"], className="eyebrow"),
            html.H1(opp["program_name"], className="ws-title"),
            html.Div([html.Span(f"Due {deadline_text(opp)} · {days_text(days)}"), html.Span(" · "),
                      html.Span(f"{answered}/{len(questions)} answered · {approved} approved"), html.Span(" · "),
                      html.Button("Opportunity details", id="ws-opp-open", className="inline-link")],
                     className="muted small"),
        ], className="ws-header")

    left = card([html.H3("Report sections" if kind == "report" else "Questions", className="side-h"),
                 html.Div(question_list(opp_id, q and q["id"], kind), id="ws-qlist"), add_question_form()],
                className="ws-left")
    if not q:
        return html.Div([header, html.Div([left, card(empty("Add the funder's first question to start writing."))],
                                          className="ws-grid two"),
                         dcc.Store(id="ws-opp", data=opp_id), modal("ws")])

    pos = [x["id"] for x in questions].index(q["id"]) + 1
    length = length_check(q["response"], q["limit_type"], q["limit_value"])
    editor = card([
        html.Div([html.Span(f"{'Section' if kind == 'report' else 'Question'} {pos} of {len(questions)}", className="eyebrow"),
                  html.Div([html.Span(_limit_tag(q), id="ws-qlimit", className="tag"),
                            html.Button("✎ Edit question", id="ws-qedit-toggle", className="btn-link small-btn",
                                        title="Change the wording or the word / character limit")],
                           className="editor-top-r")], className="editor-top"),
        html.Div(q["prompt"], id="ws-qtext", className="q-full"),
        html.Div([
            html.Label("Question", className="k"),
            dcc.Textarea(id="ws-qedit-prompt", value=q["prompt"], className="textarea short"),
            html.Label("Length limit", className="k"),
            html.Div([
                dcc.Input(id="ws-qedit-limit", type="number", min=1, value=q["limit_value"],
                          placeholder="No limit", className="input"),
                dcc.Dropdown(["words", "characters"], q["limit_type"] or "words", id="ws-qedit-unit",
                             clearable=False, className="dropdown small-dd"),
            ], className="input-row"),
            html.Div("Leave the limit empty if the funder doesn't set one. Your answer isn't changed.",
                     className="hint"),
            html.Div([html.Button("Save changes", id="ws-qedit-save", n_clicks=0, className="btn btn-primary"),
                      html.Button("Cancel", id="ws-qedit-cancel", className="btn btn-quiet")], className="btn-row"),
        ], id="ws-qedit", className="q-edit"),
        html.Div([
            dcc.RadioItems([{"label": "Edit", "value": "edit"}, {"label": "Review suggestions", "value": "review"}],
                           "edit", id="ws-mode", inline=True, className="segmented mode-switch"),
            html.Div([comments.start_button(),
                      html.Button("✦ Draft with AI", id="ws-gen-draft", n_clicks=0, className="btn btn-quiet gen-draft",
                                  title="The Grant Writer drafts an answer from your Profile and source documents "
                                        "only")], className="mode-actions"),
        ], className="mode-row"),
        html.Div([
            dcc.Textarea(id="ws-text", value=q["response"], className="textarea editor",
                         placeholder="Write your answer here, or click ✦ Draft with AI for a first draft from your Profile and documents."),
            html.Div(id="ws-review", className="review-pane"),
        ], id="ws-editor-wrap", className="mode-edit"),
        html.Div([html.Div(length_label(length), id="ws-count"),
                  html.Div([html.Button([html.Span(className="undo-icon"), html.Span("Undo")], id="ws-undo-btn", n_clicks=0, disabled=True, className="btn-link undo-btn",
                                        title="Undo your last change (typing, AI draft or Coach suggestion)"),
                            html.Button([html.Span(className="undo-icon redo"), html.Span("Redo")], id="ws-redo-btn", n_clicks=0, disabled=True, className="btn-link undo-btn",
                                        title="Redo")], className="undo-row"),
                  html.Div(id="ws-dirty")], className="editor-meta"),
        html.Div([
            dcc.Dropdown(Q_STATUSES, q["status"], id="ws-status", clearable=False, className="dropdown small-dd"),
            html.Button("★ Add to Answer Library", id="ws-approve-lang", className="btn btn-quiet",
                        title="Save this answer as approved wording you can reuse in other applications"),
            dcc.ConfirmDialogProvider(html.Button("Delete question", className="btn-link btn-danger"),
                                      id="ws-delete", message="Delete this question and its answer?"),
        ], className="btn-row wrap"),
        html.Div(id="ws-msg", className="form-msg"),
        html.Div(id="ws-draft-notes"),
        html.Details([html.Summary("Version history", className="toggle"), html.Div(history(q["id"]), id="ws-history")],
                     className="block"),
    ], className="ws-editor")

    def tab_body(kind, render, button, hint):
        review = db.latest_review(q["id"], kind)
        return html.Div([
            html.Div([*button, html.Span(hint, className="hint")], className="btn-row tight"),
            dcc.Loading(html.Div(render(review, q["response"]), id=f"ws-{kind}-out"), type="dot", color="#2f5d50"),
        ], className="tab-body")

    suggested = answer_matches(q["prompt"], exclude_question_id=q["id"])
    assistant = card(dcc.Tabs(
        [
            dcc.Tab(label=f"Library{f' ({len(suggested)})' if suggested else ''}", value="answers",
                    className="tab", selected_className="tab-on",
                    children=html.Div(saved_answers(suggested), className="tab-body")),
            dcc.Tab(label="Sources", value="sources", className="tab", selected_className="tab-on",
                    children=html.Div([html.P("Passages from your library that relate to this question. "
                                              "Approved language first.", className="hint"),
                                       *source_snippets(q["prompt"])], className="tab-body")),
            dcc.Tab(label="Coach", value="coach", className="tab", selected_className="tab-on", children=tab_body(
                "coach", lambda review, text: render_coach(review, text, None, editable=True), [],
                "The Coach reviews your answer by itself whenever you open Review suggestions.")),
            dcc.Tab(label=comments.tab_label(q["id"]), value="comments", id="cm-tab", className="tab",
                    selected_className="tab-on", children=comments.panel(q)),
            dcc.Tab(label="Evidence", value="evidence", className="tab", selected_className="tab-on", children=tab_body(
                "evidence", render_evidence,
                [html.Button("Check evidence", id="ws-evidence-run", className="btn btn-primary")],
                "Saves your text first.")),
        ],
        id="ws-tabs", value="answers" if suggested else "sources", className="tabs",
    ), className="ws-assistant")

    return html.Div([
        header,
        html.Div([left, editor, assistant], className="ws-grid"),
        dcc.Store(id="ws-q", data={"id": q["id"], "opp": opp_id, "kind": kind}),
        dcc.Store(id="ws-origin", data="you"),
        dcc.Store(id="ws-autosave"),  # set once typing pauses; the server then saves
        dcc.Store(id="ws-issues", data={}),  # which coach suggestions were accepted, rejected or clicked
        dcc.Store(id="ws-undo", data=[]),  # snapshots before each accept/reject, newest last
        dcc.Store(id="ws-redo", data=[]),
        dcc.Store(id="ws-coach-done"),  # set when a background Coach review finishes, to redraw the highlights
        dcc.Store(id="ws-opp", data=opp_id),
        modal("ws"),  # Opportunity details open here, without leaving the editor
    ])


# --- Helpers ----------------------------------------------------------------------------
def saved_answers(items: list[dict]):
    """Answer Library entries that fit this question, each one click from the editor."""
    if not items:
        return [html.P("No saved answers fit this question yet.", className="hint"),
                html.P(["When an answer is ready, click ★ Add to Answer Library under the editor. Next time a funder "
                        "asks something similar, it shows up in this tab. ", link("Open the library →", "/answers",
                                                                           "small-link")], className="hint")]
    return [html.P("Approved answers from your library that fit this question. Use one as your starting point, "
                   "then adapt it to this funder. Undo brings your text back.", className="hint"),
            *[html.Div([
                html.Div([html.Span(a["reason"], className="ans-reason"),
                          html.Span(f"{a['funder'] or 'Added by hand'} · {word_count(a['text'])} words",
                                    className="ans-meta")], className="ans-top"),
                html.Div(a["question"], className="ans-q small"),
                html.Div(a["text"], className="ans-text"),
                html.Div([html.Button("Use this answer", id={"type": "ws-use-ans", "id": a["id"]}, n_clicks=0,
                                      className="btn btn-primary btn-small"),
                          html.Button("Show full answer", className="btn-link ans-more"),
                          copy_action(a["text"])], className="ans-actions"),
            ], className="ans-card compact") for a in items]]


def _limit_tag(q: dict) -> str:
    return f"Limit: {q['limit_value']:,} {q['limit_type']}" if q["limit_value"] else "No limit"


def _save_if_changed(q_id: int, text: str, origin: str) -> bool:
    return db.save_response(q_id, text or "", origin)


def _saved_label(when: str | None = None):
    return html.Span(f"Saved{' ' + when[11:16] if when else ''}", className="saved-note", title="Changes save automatically")


AUTOSAVE_DELAY_MS = 1000


# --- Callbacks ----------------------------------------------------------------------------
@callback(
    Output("ws-count", "children"),
    Output("ws-dirty", "children"),
    Input("ws-text", "value"),
    State("ws-q", "data"),
)
def live_count(text, qd):
    q = db.get_question(qd["id"])
    dirty = (text or "") != (q["response"] if q else "")
    return (length_label(length_check(text or "", q["limit_type"], q["limit_value"])),
            html.Span("Saving…", className="unsaved") if dirty else _saved_label())


# Debounce in the browser: wait until typing has paused, then hand the text to the server once.
clientside_callback(
    f"""async function(value) {{
        await new Promise(r => setTimeout(r, {AUTOSAVE_DELAY_MS}));
        const el = document.getElementById('ws-text');
        if (el && el.value !== value) return window.dash_clientside.no_update;  // still typing
        return {{text: value, t: Date.now()}};
    }}""",
    Output("ws-autosave", "data"),
    Input("ws-text", "value"),
    prevent_initial_call=True,
)


@callback(
    Output("ws-dirty", "children", allow_duplicate=True),
    Output("ws-qlist", "children"),
    Output("ws-history", "children"),
    Output("ws-origin", "data"),
    Output("ws-status", "value", allow_duplicate=True),
    Output("ws-undo", "data", allow_duplicate=True),
    Output("ws-redo", "data", allow_duplicate=True),
    Output("ws-undo-btn", "disabled", allow_duplicate=True),
    Output("ws-redo-btn", "disabled", allow_duplicate=True),
    Input("ws-autosave", "data"),
    Input("ws-text", "n_blur"),  # leaving the editor saves straight away
    State("ws-text", "value"),
    State("ws-q", "data"),
    State("ws-origin", "data"),
    State("ws-issues", "data"),
    State("ws-undo", "data"),
    prevent_initial_call=True,
)
def autosave(_tick, _blur, text, qd, origin, state, undo):
    """Save, and make each pause in typing one Undo step. Drafts, Coach accepts and Undo/Redo themselves
    record their own steps (their origin isn't plain "you"), so they aren't recorded twice."""
    before = (db.get_question(qd["id"]) or {}).get("response", "")
    if not db.save_response(qd["id"], text or "", origin, autosave=True):
        q = db.get_question(qd["id"])
        if q and q["response"] == (text or ""):
            return _saved_label(), *[no_update] * 8
        raise PreventUpdate
    q = db.get_question(qd["id"])
    steps = no_update
    if origin == "you":
        undo = (list(undo or []) + [{"text": before, "state": state or {}, "label": "your edit"}])[-30:]
        steps = (undo, [], False, True)
    return (_saved_label(q["updated"]), question_list(qd["opp"], qd["id"], qd.get("kind", "application")), history(qd["id"]), "you", q["status"],
            *(steps if steps is not no_update else [no_update] * 4))


@callback(
    Output("ws-qtext", "children"),
    Output("ws-qlimit", "children"),
    Output("ws-count", "children", allow_duplicate=True),
    Output("ws-qlist", "children", allow_duplicate=True),
    Output("ws-qedit", "className"),
    Output("ws-msg", "children", allow_duplicate=True),
    Input("ws-qedit-save", "n_clicks"),
    State("ws-qedit-prompt", "value"),
    State("ws-qedit-limit", "value"),
    State("ws-qedit-unit", "value"),
    State("ws-text", "value"),
    State("ws-q", "data"),
    prevent_initial_call=True,
)
def edit_question(n, prompt, limit, unit, text, qd):
    if not n:
        raise PreventUpdate
    if not (prompt or "").strip():
        return (*[no_update] * 5, html.Span("The question can't be empty.", className="error-text"))
    limit = int(limit) if limit and int(limit) > 0 else None
    db.update_question(qd["id"], prompt.strip(), unit, limit)
    q = db.get_question(qd["id"])
    return (q["prompt"], _limit_tag(q), length_label(length_check(text or "", q["limit_type"], q["limit_value"])),
            # a className different from the last one, so the browser drops the "open" class menu.js added
            question_list(qd["opp"], qd["id"], qd.get("kind", "application")), f"q-edit saved-{n % 2}",
            html.Span("Question updated.", className="ok-text small"))


@callback(
    Output("ws-qlist", "children", allow_duplicate=True),
    Input("ws-status", "value"),
    State("ws-q", "data"),
    prevent_initial_call=True,
)
def set_status(status, qd):
    q = db.get_question(qd["id"])
    if not q or q["status"] == status:
        return no_update
    db.set_question_status(qd["id"], status)
    return question_list(qd["opp"], qd["id"], qd.get("kind", "application"))


@callback(
    Output("ws-msg", "children", allow_duplicate=True),
    Input("ws-approve-lang", "n_clicks"),
    State("ws-text", "value"),
    State("ws-q", "data"),
    prevent_initial_call=True,
)
def save_approved_language(_n, text, qd):
    if not (text or "").strip():
        return html.Span("Write an answer first.", className="error-text")
    if "[MISSING:" in text:
        return html.Span("Fill in the [MISSING: …] items first, so the saved answer is complete.", className="error-text")
    q, opp = db.get_question(qd["id"]), db.get_opportunity(qd["opp"])
    _, created = db.save_answer(q["prompt"], text.strip(), classify(q["prompt"]), opp["funder"], q["id"])
    return html.Span([("Added to" if created else "Updated in") + " your Answer Library. ",
                      link("View library →", "/answers", "small-link")], className="ok-text small")


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Output("ws-new-msg", "children"),
    Input("ws-new-add", "n_clicks"),
    State("ws-new-prompt", "value"),
    State("ws-new-limit", "value"),
    State("ws-new-unit", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def add_question(_n, prompt, limit, unit, path):
    if not (prompt or "").strip():
        return no_update, html.Span("Paste the question first.", className="error-text")
    kind = "report" if path.startswith("/report/") else "application"
    opp_id = int(path.split("/")[2])
    q_id = db.add_question(opp_id, prompt.strip(), unit if limit else None, int(limit) if limit else None, kind=kind)
    return f"{BASE[kind]}/{opp_id}/{q_id}", ""


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("ws-delete", "submit_n_clicks"),
    State("ws-q", "data"),
    prevent_initial_call=True,
)
def delete(n, qd):
    if not n:
        return no_update
    db.delete_question(qd["id"])
    return f"{BASE[qd.get('kind', 'application')]}/{qd['opp']}"


@callback(
    Output("ws-text", "value", allow_duplicate=True),
    Output("ws-origin", "data", allow_duplicate=True),
    Output("ws-msg", "children", allow_duplicate=True),
    Output("ws-undo", "data", allow_duplicate=True),
    Output("ws-redo", "data", allow_duplicate=True),
    Output("ws-undo-btn", "disabled", allow_duplicate=True),
    Output("ws-redo-btn", "disabled", allow_duplicate=True),
    Input({"type": "ws-restore", "id": ALL}, "n_clicks"),
    State("ws-q", "data"),
    State("ws-text", "value"),
    State("ws-issues", "data"),
    State("ws-undo", "data"),
    prevent_initial_call=True,
)
def restore(clicks, qd, text, state, undo):
    """Load an earlier version into the editor; like every other change, one Undo reverses it."""
    if not ctx.triggered_id or not any(clicks):
        raise PreventUpdate
    v = next((v for v in db.list_versions(qd["id"]) if v["id"] == ctx.triggered_id["id"]), None)
    if not v:
        raise PreventUpdate
    undo = (list(undo or []) + [{"text": text or "", "state": state or {}, "label": "loading an earlier version"}])[-30:]
    return (v["text"], "you (restored version)",
            html.Span("Earlier version loaded and saved. Undo brings back the text you had.", className="small"),
            undo, [], False, True)


@callback(
    Output("ws-text", "value", allow_duplicate=True),
    Output("ws-origin", "data", allow_duplicate=True),
    Output("ws-msg", "children", allow_duplicate=True),
    Output("ws-draft-notes", "children"),
    Output("ws-mode", "value", allow_duplicate=True),
    Output("ws-undo", "data", allow_duplicate=True),
    Output("ws-redo", "data", allow_duplicate=True),
    Output("ws-undo-btn", "disabled", allow_duplicate=True),
    Output("ws-redo-btn", "disabled", allow_duplicate=True),
    Input("ws-gen-draft", "n_clicks"),
    State("ws-text", "value"),
    State("ws-q", "data"),
    State("ws-issues", "data"),
    State("ws-undo", "data"),
    running=[(Output("ws-gen-draft", "disabled"), True, False),
             (Output("ws-gen-draft", "children"), "Drafting from your documents…", "✦ Draft with AI")],
    prevent_initial_call=True,
)
def generate_draft(n, text, qd, state, undo):
    """The Grant Writer writes (or improves) the answer from the Profile and source documents only, straight
    into the editor. The previous text stays in Version history and one click on Undo brings it back."""
    if not n:
        raise PreventUpdate
    text = text or ""
    q = {**db.get_question(qd["id"]), "response": text}
    try:
        res = draft(q, db.get_opportunity(qd["opp"]))
    except Exception as exc:
        msg = friendly(exc)
        return (no_update, no_update, html.Span(msg, className="error-text"), *[no_update] * 6)
    db.save_review(qd["id"], "draft", res["result"], res["usage"], text)
    if text.strip():
        db.save_response(qd["id"], text, "you")  # keep the writer's own text in history first
    undo = (list(undo or []) + [{"text": text, "state": state or {}, "label": "AI draft"}])[-30:]
    msg = html.Span("Draft written from your Profile and source documents. Edit it freely"
                    + (", or click Undo to get your previous text back." if text.strip() else "."), className="small")
    return (res["result"]["draft"], "AI draft (accepted by you)", msg,
            draft_notes(db.latest_review(qd["id"], "draft")), "edit", undo, [], False, True)


@callback(
    Output("ws-text", "value", allow_duplicate=True),
    Output("ws-origin", "data", allow_duplicate=True),
    Output("ws-msg", "children", allow_duplicate=True),
    Output("ws-mode", "value", allow_duplicate=True),
    Output("ws-undo", "data", allow_duplicate=True),
    Output("ws-redo", "data", allow_duplicate=True),
    Output("ws-undo-btn", "disabled", allow_duplicate=True),
    Output("ws-redo-btn", "disabled", allow_duplicate=True),
    Input({"type": "ws-use-ans", "id": ALL}, "n_clicks"),
    State("ws-text", "value"),
    State("ws-issues", "data"),
    State("ws-undo", "data"),
    prevent_initial_call=True,
)
def use_saved_answer(clicks, text, state, undo):
    """Put a library answer in the editor; the writer's own text is one Undo away."""
    if not ctx.triggered_id or not any(clicks):
        raise PreventUpdate
    a = db.get_answer(ctx.triggered_id["id"])
    if not a:
        raise PreventUpdate
    db.mark_answer_used(a["id"])
    undo = (list(undo or []) + [{"text": text or "", "state": state or {}, "label": "saved answer"}])[-30:]
    return (a["text"], "you, from the Answer Library",
            html.Span("Saved answer placed in the editor. Adapt it to this funder; Undo brings back your text.",
                      className="small"), "edit", undo, [], False, True)


def _review(kind: str, fn, text: str, qd: dict):
    if not (text or "").strip():
        return html.Div("Write or paste an answer first.", className="error-text")
    _save_if_changed(qd["id"], text, "you")
    q, opp = db.get_question(qd["id"]), db.get_opportunity(qd["opp"])
    try:
        res = fn(q, opp, text) if kind == "coach" else fn(text, qd["id"])
    except Exception as exc:
        msg = friendly(exc)
        return html.Div(msg, className="error-text")
    db.save_review(qd["id"], kind, res["result"], res["usage"], text)
    if q["status"] in ("Not started", "Drafting"):
        db.set_question_status(qd["id"], "Reviewed")
    if kind == "coach":
        return render_coach(db.latest_review(qd["id"], kind), text, None, editable=True)
    return render_evidence(db.latest_review(qd["id"], kind), text)


def _coach_stale(review: dict | None, text: str) -> bool:
    """True when the Coach hasn't seen this exact text yet (so opening Review should run it)."""
    return bool((text or "").strip()) and (not review or review.get("response_text") != text)


@callback(
    Output("ws-coach-done", "data"),
    Output("ws-coach-out", "children"),
    Output("ws-qlist", "children", allow_duplicate=True),
    Output("ws-status", "value", allow_duplicate=True),
    Output("ws-issues", "data"),
    Output("ws-undo", "data"),
    Output("ws-redo", "data"),
    Input("ws-mode", "value"),
    State("ws-text", "value"),
    State("ws-q", "data"),
    prevent_initial_call=True,
)
def auto_coach(mode, text, qd):
    """The Grant Coach runs in the background as soon as Review suggestions opens, but only if the answer
    has changed since its last review, so switching back and forth costs nothing."""
    if mode != "review" or not _coach_stale(db.latest_review(qd["id"], "coach"), text):
        raise PreventUpdate
    out = _review("coach", coach, text, qd)
    return (datetime.now().isoformat(), out, question_list(qd["opp"], qd["id"], qd.get("kind", "application")),
            db.get_question(qd["id"])["status"], {}, [], [])


@callback(
    Output("ws-editor-wrap", "className"),
    Output("ws-review", "children"),
    Output("ws-coach-out", "children", allow_duplicate=True),
    Output("ws-text", "value", allow_duplicate=True),
    Output("ws-origin", "data", allow_duplicate=True),
    Output("ws-issues", "data", allow_duplicate=True),
    Output("ws-msg", "children", allow_duplicate=True),
    Output("ws-tabs", "value"),
    Output("ws-undo", "data", allow_duplicate=True),
    Output("ws-redo", "data", allow_duplicate=True),
    Output("ws-undo-btn", "disabled"),
    Output("ws-redo-btn", "disabled"),
    Input("ws-mode", "value"),
    Input({"type": "ws-apply", "i": ALL}, "n_clicks"),
    Input({"type": "ws-dismiss", "i": ALL}, "n_clicks"),
    Input({"type": "ws-apply-pop", "i": ALL}, "n_clicks"),
    Input({"type": "ws-dismiss-pop", "i": ALL}, "n_clicks"),
    Input("ws-undo-btn", "n_clicks"),
    Input("ws-redo-btn", "n_clicks"),
    Input("ws-coach-done", "data"),
    State("ws-text", "value"),
    State("ws-q", "data"),
    State("ws-issues", "data"),
    State("ws-origin", "data"),
    State("ws-undo", "data"),
    State("ws-redo", "data"),
    prevent_initial_call=True,
)
def review_ui(mode, _apply, _dismiss, _apply_pop, _dismiss_pop, _undo, _redo, _coached, text, qd, state, origin, undo,
              redo):
    """Grammarly-style review: click a highlight to find its suggestion; Apply puts the suggested wording into
    the editor (saved automatically; Undo reverses it); Dismiss hides it."""
    # Several inputs can change at once (e.g. the mode switches while new buttons appear). Act on a real
    # click if there is one, otherwise on the mode change; ignore buttons merely being re-rendered.
    import json as _json

    trig = None
    for t in ctx.triggered:
        prop_id = t["prop_id"].rsplit(".", 1)[0]
        if prop_id.startswith("{") and t["value"]:
            trig = _json.loads(prop_id)
            break
    if trig is None:
        for name in ("ws-undo-btn", "ws-redo-btn"):
            if any(t["prop_id"] == f"{name}.n_clicks" and t["value"] for t in ctx.triggered):
                trig = name
    if trig is None:
        if any(t["prop_id"] == "ws-mode.value" for t in ctx.triggered):
            trig = "ws-mode"
        elif any(t["prop_id"] == "ws-coach-done.data" for t in ctx.triggered):
            trig = "ws-coach-done"
        else:
            raise PreventUpdate
    state = dict(state or {})
    text = text or ""
    review = db.latest_review(qd["id"], "coach")
    issues = {it["id"]: (ensure_fix(it) if it.get("quote") else it)
              for it in (review or {}).get("result", {}).get("issues", [])}
    msg, new_text, new_origin, tab = no_update, no_update, no_update, no_update
    undo, redo = list(undo or []), list(redo or [])
    before = {"text": text, "state": dict(state)}
    if trig in ("ws-undo-btn", "ws-redo-btn"):
        src, dst = (undo, redo) if trig == "ws-undo-btn" else (redo, undo)
        if src:
            snap = src.pop()
            dst.append({**before, "label": snap.get("label", "")})
            text, state = snap["text"], dict(snap["state"])
            new_text, new_origin = text, "you (undo/redo)"
            verb = "Undid" if trig == "ws-undo-btn" else "Redid"
            msg = html.Span(f"{verb}: {snap.get('label', 'last change')}.", className="small")
    elif isinstance(trig, dict):
        i = trig["i"]
        trig = {**trig, "type": trig["type"].replace("-pop", "")}  # the pinned card's buttons = the panel's buttons
        title = issues.get(i, {}).get("title", "suggestion")
        if trig["type"] == "ws-dismiss":
            undo.append({**before, "label": f"rejected “{title}”"})
            redo.clear()
            state["dismissed"] = sorted(set(state.get("dismissed", [])) | {i})
        elif trig["type"] == "ws-apply" and i in issues:
            it = issues[i]
            at = _find(text, it["quote"])
            if at >= 0 and (it.get("replacement") or it.get("action") == "remove"):
                new = "" if it.get("action") == "remove" else it["replacement"]
                end = at + len(it["quote"])
                if not new and end < len(text) and text[end] == " ":  # removing a sentence: drop one space too
                    end += 1
                undo.append({**before, "label": f"accepted “{title}”"})
                redo.clear()
                text = text[:at] + new + text[end:]
                new_text, new_origin = text, "you, with Coach suggestions"
                state["applied"] = sorted(set(state.get("applied", [])) | {i})
                msg = html.Span("Suggestion applied and saved. Click Undo to reverse it.",
                                className="small")
    undo = undo[-30:]
    if trig in ("ws-mode", "ws-coach-done") and mode == "review" and _coach_stale(review, text):
        if trig == "ws-mode":  # auto_coach is reading it now
            note = html.Div([html.Div([html.Span(), html.Span(), html.Span()], className="typing"),
                             html.Span("The Coach is reading your answer…", className="hint")], className="coach-reading")
        else:  # it finished without saving a review: say so rather than wait forever
            note = html.Div("The Coach couldn't review this just now. Switch to Edit and back to try again.",
                            className="error-text")
        return (f"mode-{mode}", note, no_update if trig == "ws-coach-done" else note, new_text, new_origin, state,
                msg, tab, undo, redo, not undo, not redo)
    return (f"mode-{mode or 'edit'}", highlight_view(text, review, state, editable=True),
            render_coach(review, text, state, editable=True), new_text, new_origin, state, msg, tab,
            undo, redo, not undo, not redo)


@callback(
    Output("ws-evidence-out", "children"),
    Output("ws-qlist", "children", allow_duplicate=True),
    Output("ws-status", "value", allow_duplicate=True),
    Input("ws-evidence-run", "n_clicks"),
    State("ws-text", "value"),
    State("ws-q", "data"),
    prevent_initial_call=True,
)
def run_evidence(_n, text, qd):
    return (_review("evidence", check_evidence, text, qd), question_list(qd["opp"], qd["id"], qd.get("kind", "application")),
            db.get_question(qd["id"])["status"])


@callback(
    Output("ws-modal", "className"),
    Output("ws-modal-body", "children"),
    Input("ws-opp-open", "n_clicks"),
    State("ws-opp", "data"),
    prevent_initial_call=True,
)
def open_details(n, opp_id):
    from .opportunity_page import layout as opportunity_view  # local import: opportunity_page imports this module's peers

    if not n:
        return no_update, no_update
    return "modal open", opportunity_view(opp_id, in_modal=True)


@callback(
    Output("ws-modal", "className", allow_duplicate=True),
    Output("ws-modal-body", "children", allow_duplicate=True),
    Input("ws-modal-close", "n_clicks"),
    Input("ws-modal-backdrop", "n_clicks"),
    prevent_initial_call=True,
)
def close_details(_a, _b):
    return "modal", None

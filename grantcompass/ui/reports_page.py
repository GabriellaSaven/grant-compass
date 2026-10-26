"""Reports: what you owe funders after a win, and what to tell your board.

- Funder reports: each won grant has its reporting requirements, report sections (written in the same editor
  as applications, with Draft with AI, Coach and Evidence), programme reports in the source documents, and a
  Word report and PowerPoint deck to send.
- Board update: the last six months of fundraising as a Word document and PowerPoint deck."""

from datetime import date

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from .. import db
from ..board import facts, summarize
from ..errors import friendly
from ..exports import board_docx, board_pptx, funder_report_docx, funder_report_pptx
from ..library import decode_upload
from .components import card, days_text, empty, label, link, money, page_header, section_title, stat
from ..dates import dfmt

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text).strip("-")[:40]


def _due(opp: dict):
    if not opp.get("report_due"):
        return html.Span("No report date", className="muted small")
    days = (date.fromisoformat(opp["report_due"]) - date.today()).days
    kind = "crit" if days < 0 else "risk" if days <= 14 else "attn" if days <= 30 else "ok"
    return label(f"Report due {dfmt(date.fromisoformat(opp['report_due']), '%-d %b')} · {days_text(days)}", kind)


def _progress(opp_id: int) -> tuple[int, int]:
    qs = db.list_questions(opp_id, kind="report")
    return sum(bool(q["response"].strip()) for q in qs), len(qs)


def export_buttons(opp_id: int, prefix: str = "rep"):
    return html.Div([
        html.Button("⬇ Word report", id={"type": f"{prefix}-docx", "id": opp_id}, n_clicks=0, className="btn btn-quiet btn-small"),
        html.Button("⬇ PowerPoint", id={"type": f"{prefix}-pptx", "id": opp_id}, n_clicks=0, className="btn btn-quiet btn-small"),
    ], className="btn-row tight")


# --- The Reports page -----------------------------------------------------------------------------
def funder_reports():
    won = sorted((o for o in db.list_opportunities() if o["status"] == "Won"),
                 key=lambda o: o.get("report_due") or "9999")
    if not won:
        return empty("No won grants yet. When a grant is won, mark it Won in the Pipeline and its report appears here.")
    rows = []
    for o in won:
        done, total = _progress(o["id"])
        rows.append(html.Div([
            html.Div([html.Div(o["funder"], className="eyebrow"),
                      link(o["program_name"], f"/report/{o['id']}", "rep-title"),
                      html.Div(f"{money(o.get('awarded_amount'))} awarded · {o.get('grant_period') or ''}",
                               className="small muted")], className="rep-main"),
            html.Div([_due(o), html.Div(f"{done} of {total} sections written", className="small muted")],
                     className="rep-status"),
            html.Div([link("Open report →", f"/report/{o['id']}", "btn btn-primary btn-small"), export_buttons(o["id"])],
                     className="rep-actions"),
        ], className="rep-row"))
    return rows


def board_card():
    f = facts()
    return card([
        section_title("Board update", html.Span(f["period_label"], className="muted small")),
        html.P("Where fundraising stands for your next board meeting: what you've won and lost in the last six "
               "months, what's awaiting a decision, what the team is working on, and what's coming up.",
               className="hint"),
        html.Div([stat(money(f["won_total"]), f"won ({len(f['won'])} grants)", "ok"),
                  stat(f["win_rate_label"].split(" ")[0], "win rate"),
                  stat(money(f["awaiting_total"]), f"awaiting decision ({len(f['awaiting'])})"),
                  stat(str(len(f["reports_due"])), "reports due to funders")], className="stats compact"),
        html.Div([
            html.Button("✦ Write summary with AI", id="board-ai", n_clicks=0, className="btn btn-quiet"),
            html.Button("⬇ Word document", id="board-docx", n_clicks=0, className="btn btn-primary"),
            html.Button("⬇ PowerPoint deck", id="board-pptx", n_clicks=0, className="btn btn-primary"),
        ], className="btn-row wrap"),
        dcc.Loading(html.Div(id="board-summary-view"), type="dot", color="#2f5d50"),
        html.P("The documents are built from your records. The optional summary is written by the Executive "
               "Director agent; any sentence with a number that isn't in your records is removed before you see it.",
               className="hint"),
    ], className="board-card")


def decisions():
    out = [o for o in db.list_opportunities() if o["status"] in ("Won", "Lost") and o.get("result_date")]
    out.sort(key=lambda o: o["result_date"], reverse=True)
    if not out:
        return empty("No decisions recorded yet.")
    return html.Ul([html.Li([
        label(o["status"], "ok" if o["status"] == "Won" else "crit"),
        html.Div([html.Strong(f"{o['funder']} — {o['program_name']}"),
                  html.Div(f"{money(o.get('awarded_amount') or o.get('award_max'))} "
                           f"{'awarded' if o['status'] == 'Won' else 'requested'} · "
                           f"{dfmt(date.fromisoformat(o['result_date']), '%-d %b %Y')}", className="small muted"),
                  html.Div(f"Feedback: {o['lost_reason']}", className="small") if o.get("lost_reason") else None]),
    ], className="decision") for o in out], className="decisions")


def layout():
    return html.Div([
        page_header("Reports", "Progress reports due to your funders, and fundraising updates for your board."),
        card([section_title("Reports owed to funders"),
              html.P("Each won grant's reporting requirements become sections you write in the same editor as "
                     "your applications, drafting from your programme reports. Export a Word report and a "
                     "PowerPoint deck to send.", className="hint"),
              html.Div(funder_reports(), className="rep-list")]),
        board_card(),
        card([section_title("Recent decisions"), decisions()]),
        dcc.Store(id="board-summary"),
        dcc.Download(id="rep-dl"),
    ])


# --- Header of a report in the editor --------------------------------------------------------------
def report_header(opp: dict, sections: list[dict]):
    done = sum(bool(q["response"].strip()) for q in sections)
    progs = [d for d in db.list_documents() if d["doc_type"] == "Programme report"]
    req = opp.get("reporting_requirements")
    return html.Div([
        link("← All reports", "/reports", "back-link"),
        html.Div(opp["funder"], className="eyebrow"),
        html.H1(f"Report: {opp['program_name']}", className="ws-title"),
        html.Div([_due(opp), html.Span(f"{money(opp.get('awarded_amount'))} awarded · "
                                       f"{opp.get('grant_period') or ''} · {done}/{len(sections)} sections written",
                                       className="muted small")], className="rep-sub"),
        html.Div([
            html.Div([
                html.Div("Funder's reporting requirements", className="k"),
                html.Details([html.Summary("Read them", className="toggle small"),
                              html.Pre(req, className="doc-content")]) if req else
                html.P("Not uploaded yet.", className="small muted"),
                dcc.Upload(html.Div(["Upload new requirements (PDF, Word, text)"], className="upload-mini"),
                           id="rep-req-upload", multiple=False),
                html.Div(id="rep-req-msg", className="form-msg small"),
            ], className="rep-panel"),
            html.Div([
                html.Div("Programme reports in your source documents", className="k"),
                html.Ul([html.Li(d["title"]) for d in progs[:4]], className="small rep-docs") if progs else
                html.P("None yet. Upload one so Draft with AI can report real results.", className="small muted"),
                dcc.Upload(html.Div(["Upload a programme report"], className="upload-mini"), id="rep-prog-upload",
                           multiple=False),
                html.Div(id="rep-prog-msg", className="form-msg small"),
            ], className="rep-panel"),
            html.Div([html.Div("Send to the funder", className="k"),
                      html.P("Built from the sections below, as you've written them.", className="small muted"),
                      export_buttons(opp["id"], "rep-h")], className="rep-panel"),
        ], className="rep-panels"),
        dcc.Store(id="rep-opp", data=opp["id"]),
        dcc.Download(id="rep-h-dl"),
    ], className="ws-header")


# --- Callbacks ------------------------------------------------------------------------------------
def _send(kind: str, opp_id: int):
    opp = db.get_opportunity(opp_id)
    name = f"{_slug(opp['funder'])}-report"
    if kind == "docx":
        return dcc.send_bytes(funder_report_docx(opp_id), f"{name}.docx", type=DOCX)
    return dcc.send_bytes(funder_report_pptx(opp_id), f"{name}.pptx", type=PPTX)


@callback(Output("rep-dl", "data"), Input({"type": "rep-docx", "id": ALL}, "n_clicks"),
          Input({"type": "rep-pptx", "id": ALL}, "n_clicks"), prevent_initial_call=True)
def download_from_list(_d, _p):
    if not ctx.triggered_id or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    return _send(ctx.triggered_id["type"].split("-")[1], ctx.triggered_id["id"])


@callback(Output("rep-h-dl", "data"), Input({"type": "rep-h-docx", "id": ALL}, "n_clicks"),
          Input({"type": "rep-h-pptx", "id": ALL}, "n_clicks"), prevent_initial_call=True)
def download_from_editor(_d, _p):
    if not ctx.triggered_id or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    return _send(ctx.triggered_id["type"].split("-")[2], ctx.triggered_id["id"])


@callback(Output("url", "pathname", allow_duplicate=True), Output("rep-req-msg", "children"),
          Input("rep-req-upload", "contents"), State("rep-req-upload", "filename"), State("rep-opp", "data"),
          prevent_initial_call=True)
def read_requirements(contents, filename, opp_id):
    """New requirements: the Research Agent pulls out the sections the funder asks for (kept only if they
    appear word for word), and each becomes a report section."""
    if not contents:
        raise PreventUpdate
    from ..research import extract_opportunity

    try:
        text = decode_upload(contents, filename)
        found = extract_opportunity(text)["opportunity"]["questions"]
    except Exception as exc:
        return no_update, html.Span(friendly(exc), className="error-text")
    have = {q["prompt"].strip().lower() for q in db.list_questions(opp_id, kind="report")}
    added = 0
    for q in found:
        if q["prompt"].strip().lower() not in have:
            db.add_question(opp_id, q["prompt"], q.get("limit_type") if q.get("limit_value") else None,
                            q.get("limit_value"), kind="report")
            added += 1
    db.update_opportunity(opp_id, reporting_requirements=text)
    if not found:
        return no_update, html.Span("Saved. No report sections were found in it; add them below.", className="small")
    return f"/report/{opp_id}", ""


@callback(Output("rep-prog-msg", "children"), Input("rep-prog-upload", "contents"),
          State("rep-prog-upload", "filename"), prevent_initial_call=True)
def add_programme_report(contents, filename):
    if not contents:
        raise PreventUpdate
    try:
        text = decode_upload(contents, filename)
    except Exception as exc:
        return html.Span(friendly(exc), className="error-text")
    title = filename.rsplit(".", 1)[0].replace("_", " ").strip()
    db.add_document(title, "Programme report", text)
    return html.Span(f"Added “{title}” to your source documents. Draft with AI will use it.", className="ok-text")


@callback(Output("board-summary", "data"), Output("board-summary-view", "children"),
          Input("board-ai", "n_clicks"), prevent_initial_call=True,
          running=[(Output("board-ai", "disabled"), True, False),
                   (Output("board-ai", "children"), "Writing…", "✦ Write summary with AI")])
def write_summary(n):
    if not n:
        raise PreventUpdate
    try:
        s = summarize(facts())["summary"]
    except Exception as exc:
        return no_update, html.P(friendly(exc), className="error-text")
    removed = s.get("numbers_removed")
    return s, html.Div([
        html.Div(s["headline"], className="board-headline"),
        html.P(s["summary"]),
        html.Ul([html.Li(h) for h in s["highlights"]]),
        html.Div([html.Strong("Asks: "), "; ".join(s["asks"])], className="small") if s["asks"] else None,
        html.P(f"{removed} sentence(s) removed because a number couldn't be found in your records."
               if removed else "Every number checked against your records.", className="hint"),
        html.P("Included in the Word document and PowerPoint deck.", className="hint"),
    ], className="board-summary")


@callback(Output("rep-dl", "data", allow_duplicate=True), Input("board-docx", "n_clicks"),
          Input("board-pptx", "n_clicks"), State("board-summary", "data"), prevent_initial_call=True)
def download_board(_d, _p, summary):
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    f = facts()
    stamp = date.today().isoformat()
    if ctx.triggered_id == "board-docx":
        return dcc.send_bytes(board_docx(f, summary), f"board-update-{stamp}.docx", type=DOCX)
    return dcc.send_bytes(board_pptx(f, summary), f"board-update-{stamp}.pptx", type=PPTX)

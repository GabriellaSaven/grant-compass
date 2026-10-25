"""Answer Library: the team's approved answers, searchable by topic, ready to reuse."""

from datetime import datetime

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from .. import db
from ..answers import OTHER, TOPICS, classify, search, word_count
from .components import card, copy_action, page_header, section_title

TOPIC_LIST = ["All", *TOPICS, OTHER]


def _date(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%-d %b %Y")


def answer_card(a: dict):
    meta = [a["funder"] or "Added by hand", _date(a["created"]), f"{word_count(a['text'])} words",
            f"reused {a['uses']}×" if a["uses"] else "not reused yet"]
    return html.Div([
        html.Div([html.Span(a["topic"], className="ans-topic"), html.Span(" · ".join(meta), className="ans-meta")],
                 className="ans-top"),
        html.Div(a["question"], className="ans-q"),
        html.Div(a["text"], className="ans-text"),
        html.Div([
            html.Button("Show full answer", className="btn-link ans-more"),
            copy_action(a["text"]),
            dcc.ConfirmDialogProvider(html.Button([html.Span(className="ans-trash"), html.Span("Remove")],
                                                  className="ans-act", title="Remove from the library"),
                                      id={"type": "ans-del", "id": a["id"]},
                                      message="Remove this answer from your Answer Library? "
                                              "Applications that used it keep their text."),
        ], className="ans-actions"),
    ], className="ans-card")


def empty_library():
    steps = [("1", "Write and polish an answer", "in any application, with the Coach's help."),
             ("2", "Click ★ Add to Answer Library", "under the editor, once it's ready to reuse."),
             ("3", "Reuse it next time", "the editor's Library tab suggests it for similar questions.")]
    return html.Div([
        html.Div("☆", className="ans-empty-mark"),
        html.H3("Your best answers will live here"),
        html.P("Most funders ask the same ten questions in different words. Save an answer once, then reuse and "
               "adapt it instead of starting from a blank page.", className="lede"),
        html.Div([html.Div([html.Span(n, className="ans-step-n"),
                            html.Div([html.Strong(t), html.Span(" " + d)])], className="ans-step")
                  for n, t, d in steps], className="ans-steps"),
        html.P("Have answers from past applications? Paste them in on the left.", className="hint"),
    ], className="ans-empty")


def results(query: str = "", topic: str = "All"):
    if not db.list_answers():
        return empty_library()
    items = search(query, topic)
    if not items:
        return html.P("No saved answers match. Try another topic or fewer words.", className="empty-note")
    return [html.P(f"{len(items)} answer{'s' if len(items) != 1 else ''}", className="ans-count"),
            *[answer_card(a) for a in items]]


def topic_options():
    counts = {t: 0 for t in TOPIC_LIST}
    for a in db.list_answers():
        counts["All"] += 1
        counts[a["topic"]] = counts.get(a["topic"], 0) + 1
    return [{"label": f"{t} {counts[t]}" if counts[t] else t, "value": t} for t in TOPIC_LIST
            if t == "All" or counts[t]]


def add_form():
    return html.Div([
        html.Label("Funder's question", className="field-label"),
        dcc.Textarea(id="ans-new-q", className="textarea short full",
                     placeholder="e.g. Describe the need your program addresses."),
        html.Label("Your approved answer", className="field-label"),
        dcc.Textarea(id="ans-new-text", className="textarea full", placeholder="Paste the final wording."),
        html.Label("Funder (optional)", className="field-label"),
        dcc.Input(id="ans-new-funder", type="text", className="input full", placeholder="e.g. Ohio Arts Council"),
        html.Button("Add to library", id="ans-new-add", n_clicks=0, className="btn btn-primary btn-block"),
        html.Div(id="ans-new-msg", className="form-msg"),
    ], className="stack-form")


def layout():
    return html.Div([
        page_header("Answer Library", "Your approved answers, ready to reuse. Search by topic, copy one, or open "
                                      "an application and pick one from its Library tab."),
        html.Div([
            card([section_title("Add a past answer"), add_form(),
                  html.P("The topic is worked out from the question, so similar questions find it later.",
                         className="hint")], className="side-card"),
            html.Div([
                html.Div([
                    dcc.Input(id="ans-search", type="search", debounce=0.3, className="input ans-search",
                              placeholder="Search answers, questions or funders"),
                    dcc.RadioItems(topic_options(), "All", id="ans-topic", className="ans-topics", inline=True),
                ], className="ans-tools"),
                html.Div(results(), id="ans-list"),
            ]),
        ], className="two-col narrow-left"),
    ])


@callback(Output("ans-list", "children"), Input("ans-search", "value"), Input("ans-topic", "value"),
          prevent_initial_call=True)
def filter_answers(query, topic):
    return results(query, topic)


@callback(
    Output("ans-list", "children", allow_duplicate=True),
    Output("ans-topic", "options"),
    Output("ans-new-msg", "children"),
    Output("ans-new-q", "value"),
    Output("ans-new-text", "value"),
    Output("ans-new-funder", "value"),
    Input("ans-new-add", "n_clicks"),
    State("ans-new-q", "value"),
    State("ans-new-text", "value"),
    State("ans-new-funder", "value"),
    State("ans-search", "value"),
    State("ans-topic", "value"),
    prevent_initial_call=True,
)
def add_answer(n, question, text, funder, query, topic):
    if not n:
        raise PreventUpdate
    if not (question or "").strip() or not (text or "").strip():
        return (no_update, no_update, html.Span("Add both the question and your answer.", className="error-text"),
                no_update, no_update, no_update)
    t = classify(question)
    db.save_answer(question.strip(), text.strip(), t, (funder or "").strip() or None)
    return (results(query, topic), topic_options(), html.Span(f"Added under {t}.", className="ok-text small"),
            "", "", "")


@callback(
    Output("ans-list", "children", allow_duplicate=True),
    Output("ans-topic", "options", allow_duplicate=True),
    Input({"type": "ans-del", "id": ALL}, "submit_n_clicks"),
    State("ans-search", "value"),
    State("ans-topic", "value"),
    prevent_initial_call=True,
)
def remove_answer(clicks, query, topic):
    if not ctx.triggered_id or not any(clicks):
        raise PreventUpdate
    db.delete_answer(ctx.triggered_id["id"])
    return results(query, topic), topic_options()

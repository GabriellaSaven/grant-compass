"""Organisation Library: the documents every agent treats as the source of truth."""

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from .. import db
from ..library import DOC_TYPES, decode_upload
from .components import card, empty, page_header, profile_tabs, section_title


def doc_list():
    docs = db.list_documents()
    if not docs:
        return empty("No documents yet. Upload your mission, programme descriptions, budget and impact data.")
    rows = []
    for d in docs:
        rows.append(
            html.Details(
                [
                    html.Summary(
                        [
                            html.Div(
                                [
                                    html.Span(d["title"], className="doc-title"),
                                    html.Span(d["doc_type"], className="doc-type"),
                                ]
                            ),
                            html.Div(
                                [
                                    html.Span("Approved language", className="tag tag-approved") if d["approved"] else None,
                                    html.Span("Sample", className="tag") if d["sample"] else None,
                                    html.Span(f"{len(d['content'].split()):,} words", className="doc-meta"),
                                ],
                                className="doc-aside",
                            ),
                        ],
                    ),
                    html.Div(
                        [
                            html.Pre(d["content"], className="doc-content"),
                            html.Div(
                                [
                                    html.Button(
                                        "Remove approval" if d["approved"] else "Mark as approved language",
                                        id={"type": "doc-approve", "id": d["id"]},
                                        className="btn btn-quiet",
                                    ),
                                    dcc.ConfirmDialogProvider(
                                        html.Button("Delete", className="btn btn-quiet btn-danger"),
                                        id={"type": "doc-delete", "id": d["id"]},
                                        message=f"Delete “{d['title']}”? The AI will no longer use it. "
                                                "This can't be undone."),
                                ],
                                className="btn-row",
                            ),
                        ],
                        className="doc-body",
                    ),
                ],
                className="doc",
            )
        )
    return rows


def layout():
    return html.Div(
        [
            profile_tabs("/profile/documents"),
            page_header(
                "Source documents",
                "Reports, budgets, past applications and approved language that the AI writes from. Together with "
                "your Profile they are the source of truth: if a fact is not here, Grant Compass reports it as "
                "missing rather than inventing it.",
            ),
            html.Div(
                [
                    card(
                        [
                            section_title("Add a document"),
                            html.Label("Document type", className="field-label"),
                            dcc.Dropdown(DOC_TYPES, "Other", id="lib-type", clearable=False, className="dropdown"),
                            dcc.Checklist(
                                [{"label": " Approved organisational language", "value": "approved"}],
                                [], id="lib-approved", className="checkbox",
                            ),
                            dcc.Upload(
                                html.Div(["Drop files here or ", html.Span("browse", className="link-text")]),
                                id="lib-upload", multiple=True, className="upload",
                            ),
                            html.P("PDF, Word, text or Markdown. Text is extracted and stored locally.",
                                   className="hint"),
                            html.Div(id="lib-msg", className="form-msg"),
                        ],
                        className="side-card",
                    ),
                    card([section_title("Documents"), html.Div(doc_list(), id="lib-list")]),
                ],
                className="two-col narrow-left",
            ),
        ]
    )


@callback(
    Output("lib-list", "children"),
    Output("lib-msg", "children"),
    Input("lib-upload", "contents"),
    State("lib-upload", "filename"),
    State("lib-type", "value"),
    State("lib-approved", "value"),
    prevent_initial_call=True,
)
def upload(contents, filenames, doc_type, approved):
    if not contents:
        return no_update, no_update
    added, errors = [], []
    for c, name in zip(contents, filenames):
        try:
            text = decode_upload(c, name)
            title = name.rsplit(".", 1)[0].replace("_", " ").strip()
            db.add_document(title, doc_type, text, approved="approved" in (approved or []))
            added.append(name)
        except ValueError as exc:  # our own plain-English reasons (empty file, unsupported type…)
            errors.append(f"{name}: {exc}")
        except Exception:  # a damaged or protected file: report it, keep the good ones
            errors.append(f"{name} couldn't be read. The file may be damaged or password-protected; "
                          "try saving it again as PDF, Word or plain text.")
    msg = []
    if added:
        msg.append(html.Div(f"Added {', '.join(added)}.", className="ok-text"))
    msg += [html.Div(e, className="error-text") for e in errors]
    return doc_list(), msg


@callback(
    Output("lib-list", "children", allow_duplicate=True),
    Input({"type": "doc-approve", "id": ALL}, "n_clicks"),
    Input({"type": "doc-delete", "id": ALL}, "submit_n_clicks"),
    prevent_initial_call=True,
)
def doc_action(_approve, _delete):
    trig = ctx.triggered_id
    if not trig or not ctx.triggered[0]["value"]:
        return no_update
    if trig["type"] == "doc-delete":
        db.delete_document(trig["id"])
    else:
        doc = next((d for d in db.list_documents() if d["id"] == trig["id"]), None)
        if doc:
            db.set_document_approved(doc["id"], not doc["approved"])
    return doc_list()

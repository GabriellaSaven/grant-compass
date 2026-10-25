"""Discover: search every source that applies to this organisation, see
ranked matches with reasons, and save the good ones to the pipeline."""

from datetime import date

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from .. import db
from ..errors import friendly
from ..config import SAMPLE_DIR
from ..discover import assess_leads, run, state_source
from ..fit import assess
from ..funder_history import history as funder_history, summary as funder_summary
from ..importer import import_and_assess
from ..pipeline import workback_plan
from ..triage import lead_to_opportunity, search_keywords
from ..watchlist import add as add_watch
from .components import (
    FIT_LEGEND, REC_CLASS, award_full, award_range, card, deadline_full, deadline_text, empty, fit_class, label,
    fit_visual, page_header, section_title, usage_line,
)
from .fit_explain import fit_explainer
from .icons import field_icon

BAND_CLASS = {"Strong": "ok", "Possible": "attn", "Weak": "muted"}


# --- Pieces ------------------------------------------------------------------------
def source_options(prof: dict):
    st = state_source(prof)
    n = len(db.list_watchlist())
    opts = [{"label": " Federal (Grants.gov)", "value": "federal"},
            {"label": f" Major foundations ({len(db.list_directory())})", "value": "directory"}]
    if st:
        opts.append({"label": f" {st[0]}", "value": "state"})
    opts.append({"label": f" Foundations you follow ({n})", "value": "watchlist", "disabled": n == 0})
    return opts, [o["value"] for o in opts if not o.get("disabled")]


def state_note(prof: dict):
    state = prof.get("state")
    if not state:
        return "Add your state to your Profile to include a state grant portal where one exists."
    if state_source(prof):
        return f"Including the open {state} state grant portal."
    return (f"{state} doesn't publish an open grants feed we can search yet. "
            "You can follow your state agencies' grant pages under Foundations you follow.")


def watch_list():
    rows = db.list_watchlist()
    if not rows:
        return html.Div([
            html.Div("You're not following any funders yet.", className="small strong"),
            html.Div("Good places to start: your community foundation, family foundations that have funded you "
                     "before, and local corporate giving programmes.", className="small muted"),
        ], className="watch-empty")
    return [
        html.Div(
            [
                html.Div([
                    html.Div(w["name"] or w["url"].split("/")[2], className="row-title"),
                    html.A(w["url"], href=w["url"], target="_blank", className="small muted watch-url"),
                    html.Div(f"Last checked {w['last_checked'][:16].replace('T', ' ')}" if w["last_checked"]
                             else "Not checked yet", className="small muted"),
                ]),
                html.Button("Unfollow", id={"type": "watch-remove", "id": w["id"]}, className="btn-link btn-danger"),
            ],
            className="watch-row",
        )
        for w in rows
    ]


def in_pipeline() -> dict[tuple[str, str], int]:
    """(funder, title) -> opportunity id, for results already saved."""
    return {(o["funder"].lower(), o["program_name"].lower()): o["id"] for o in db.list_opportunities()}


def saved_id(lead: dict, saved: dict) -> int | None:
    return saved.get((lead["funder"].lower(), lead["title"].lower()))


def fit_badge(sid: str, pending: bool = False):
    """The Fit Agent's score for a result. Never the triage score."""
    a = db.get_lead_assessment(sid)
    if not a and pending:
        return html.Div([html.Div("Fit", className="fit-k"), html.Div("…", className="fit-num muted pulse"),
                         html.Div("Assessing", className="fit-cap muted")], className="fit-box")
    if not a or a["result"].get("fit_score") is None:
        return html.Div([html.Div("Fit", className="fit-k"), html.Div("—", className="fit-num muted"),
                         html.Div("Not assessed", className="fit-cap muted")], className="fit-box")
    r = a["result"]
    band = fit_class(r["fit_score"])  # colour follows the fit %, not the recommendation
    return html.Div([html.Div("Fit", className="fit-k"),
                     html.Div([html.Span(str(r["fit_score"]), className="count-up", **{"data-to": str(r["fit_score"])}),
                               "%"], className=f"fit-num rec-{band}"),
                     html.Div(r["recommendation"], className="fit-cap")], className=f"fit-box band-{band}")


def describe(lead: dict, limit: int = 240) -> str:
    """The grant in the funder's own words, cut at a sentence or word boundary."""
    text = " ".join((lead.get("summary") or lead.get("focus_area") or "").split())
    if not text:
        return "No description in the listing. Open it for the details."
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind(". ")
    return cut[:end + 1] if end > limit * 0.6 else cut.rsplit(" ", 1)[0] + "…"


def _past(lead: dict, opp_id: int | None) -> list[dict]:
    """This funder's history with you, leaving out this very grant if it's already in the pipeline."""
    return [h for h in funder_history(lead.get("funder") or "") if h["id"] != opp_id]


def history_chip(lead: dict, opp_id: int | None):
    s = funder_summary(_past(lead, opp_id))
    if not s:
        return None
    return html.Div([html.Span("↺", className="hist-mark"), s[0]], className=f"hist-chip hist-{s[1]}",
                    title="Your history with this funder. Open the grant for details.")


def history_block(lead: dict, opp_id: int | None):
    past = _past(lead, opp_id)
    if not past:
        return html.Div([html.Div("Your history with this funder", className="k"),
                         html.Div("You haven't applied to this funder before.", className="small muted")],
                        className="ov-block")
    def row(h):
        when = f" · {date.fromisoformat(h['when']):%-d %b %Y}" if h.get("when") else ""
        amount = f" · ${h['amount']:,}" if h.get("amount") else ""
        name = dcc.Link(h["programme"], href=f"/opportunity/{h['id']}") if h["id"] else html.Span(h["programme"])
        return html.Li([label(h["status"], {"Won": "ok", "Lost": "crit", "Funded you": "ok"}.get(h["status"], "attn")),
                        html.Div([name, html.Span(f"{h['funder']}{when}{amount}", className="small muted"),
                                  html.Div(f"Their feedback: {h['feedback']}", className="small")
                                  if h.get("feedback") else None], className="hist-body")], className="hist-item")
    return html.Div([html.Div("Your history with this funder", className="k"),
                     html.Ul([row(h) for h in past], className="hist-list")], className="ov-block hist-block")


def in_pipeline_link(opp_id: int | None):
    return [html.Span("✓ In pipeline", className="in-pipe"),
            dcc.Link("See in pipeline →", href=f"/opportunity/{opp_id}", className="side-link")] if opp_id else None


def result_card(lead: dict, saved: dict, pending: bool = False):
    t = lead["triage"]
    opp_id = saved_id(lead, saved)
    deadline = deadline_text(lead)  # "13 Nov 2026", "Rolling"…, the same short form as the Pipeline
    return html.Div(
        [
            html.Div(
                [
                    html.Div([html.Span(lead["source"], className="tag"), label(t["band"], BAND_CLASS[t["band"]])],
                             className="result-tags"),
                    html.Div([field_icon(lead), html.Span(lead["funder"])], className="eyebrow funder-line"),
                    history_chip(lead, opp_id),
                    html.Div(lead["title"], className="result-title"),
                    html.Div([html.Span(f"Deadline {deadline}", title=deadline_full(lead)), html.Span(" · "),
                              html.Span(award_range(lead), title=award_full(lead))], className="small muted"),
                    # What the grant is for; why it matched is shown when you open it.
                    html.P(describe(lead), className="result-desc"),
                    html.Div([html.Strong("Ignored instructions found on this page: "), "; ".join(lead["suspicious"])],
                             className="alert alert-crit") if lead.get("suspicious") else None,
                ],
                id={"type": "lead-open", "sid": lead["source_id"]},
                n_clicks=0,
                className="result-main clickable",
            ),
            html.Div(
                [
                    html.Div(
                        [html.Div(fit_badge(lead["source_id"], pending), id={"type": "lead-fit", "sid": lead["source_id"]}),
                         ],
                        id={"type": "lead-open-side", "sid": lead["source_id"]},
                        n_clicks=0,
                        className="side-click",
                    ),
                    # Outside the clickable area, so following it never starts an assessment.
                    html.Div(in_pipeline_link(opp_id), id={"type": "lead-pipe", "sid": lead["source_id"]}),
                ],
                className="result-actions",
            ),
        ],
        className="result",
    )


def fit_overview(a: dict):
    """The Go / No-Go summary in the format a development director scans first, then the dimensions behind it."""
    r = a["result"]
    rec = r["recommendation"]

    def block(title, body):
        return html.Div([html.Div(title, className="k"), body], className="ov-block")

    def bullets(items):
        return html.Ul([html.Li(i) for i in items]) if items else html.Div("None noted", className="muted small")

    alerts = []
    if r.get("suspicious_content"):
        alerts.append(html.Div([html.Strong("Instructions found in the funder text were ignored."),
                                html.Ul([html.Li(x) for x in r["suspicious_content"]])], className="alert alert-crit"))
    if r.get("gate"):
        alerts.append(html.Div(r["gate"], className="alert alert-attn"))
    if r.get("quote_warnings"):
        alerts.append(html.Div([html.Strong("Unverified quotes, shown as Inferred:"),
                                html.Ul([html.Li(w) for w in r["quote_warnings"]])], className="alert alert-attn"))
    fit = r["fit_score"]
    return html.Div([
        fit_visual(r, "md"),
        html.Div([block("Recommendation", label(rec, REC_CLASS[rec]))], className="ov-top"),
        html.Details([html.Summary(f"Why {fit}%? See the points behind it", className="toggle small"),
                      fit_explainer(r)], className="block fx-details") if fit is not None else None,
        html.P(r["headline"], className="headline small-headline"),
        *alerts,
        block("Why", bullets(r["why"])),
        block("Concerns", bullets(r["concerns"])),
        html.Div([block("Likely application effort", html.Div(r["application_effort"], className="ov-val")),
                  block("Expected value", html.Div(r["expected_value"], className="ov-val"))], className="ov-pair"),
        block("Missing information", bullets(r["missing_information"])) if r["missing_information"] else None,
        block("Suggested next steps", bullets(r["next_steps"])) if r["next_steps"] else None,
        usage_line(a["usage"]),
    ])


def filtered_overview(lead: dict):
    """What a filtered-out result is, and why it was skipped. No AI is run unless the user asks."""
    def block(title, body):
        return html.Div([html.Div(title, className="k"), body], className="ov-block")

    elig = [e for e in lead.get("eligibility") or [] if e]
    return html.Div([
        html.Div([html.Strong("Filtered out by the free rules: "), lead["triage"]["excluded"]],
                 className="alert alert-attn"),
        block("About this opportunity", html.P(lead.get("summary") or "No description provided.", className="small")),
        block("Who can apply", html.Ul([html.Li(e) for e in elig]) if elig else
              html.Div("Not stated", className="muted small")),
        html.Div([block("Focus", html.Div(lead.get("categories") or "Not stated", className="small")),
                  block("Match required", html.Div(lead.get("match_required") or "Not stated", className="small"))],
                 className="ov-pair"),
        html.Div([
            html.Button("Assess fit anyway", id="drawer-assess-anyway", className="btn btn-quiet"),
            html.Span("Runs the full Fit Agent on this one (uses AI tokens).", className="hint"),
        ], className="btn-row"),
    ])


def drawer_header(lead: dict, saved: dict, just_added: bool = False):
    opp_id = saved_id(lead, saved)
    deadline = deadline_text(lead)  # "13 Nov 2026", "Rolling"…, the same short form as the Pipeline
    t = lead.get("triage") or {}
    band = (label(t["band"], BAND_CLASS[t["band"]]) if t.get("band") else
            label("Filtered out", "muted") if t.get("excluded") else None)
    opp = lead.get("opportunity") or {}
    questions = opp.get("questions") or []
    q_block = None
    if "questions" in opp and not questions:
        q_block = html.Div("No application questions in this text. You can add them later in the application "
                           "editor.", className="hint")
    elif "questions" in opp:
        q_block = html.Details(
            [html.Summary(f"{len(questions)} application question{'s' if len(questions) != 1 else ''} found"
                          + (" — they'll be ready in the application editor" if questions else ""),
                          className="toggle"),
             html.Ol([html.Li([q["prompt"], html.Span(f" ({q['limit_value']:,} {q['limit_type']})", className="muted")
                               if q.get("limit_value") else None]) for q in questions], className="q-found")
             if questions else html.P("None listed in this document. You can add them in the editor.", className="hint"),
             html.P(f"{opp['questions_dropped']} suggested question(s) were left out because they don't appear word "
                    "for word in the document.", className="hint") if opp.get("questions_dropped") else None],
            open=bool(questions), className="block")
    notes = []
    if lead.get("truncated"):
        notes.append(html.Div("Long document: only the first part was read.", className="alert alert-attn small"))
    if lead.get("suspicious"):
        notes.append(html.Div([html.Strong("Instructions found in this document were ignored: "),
                               "; ".join(lead["suspicious"])], className="alert alert-crit small"))
    return html.Div([
        html.Div([html.Span(lead["source"], className="tag"), band], className="result-tags"),
        html.Div([field_icon(lead), html.Span(lead["funder"])], className="eyebrow funder-line"),
        html.H2(lead["title"], className="drawer-title"),
        html.Div([html.Span(f"Deadline {deadline}", title=deadline_full(lead)), html.Span(" · "),
                  html.Span(award_range(lead), title=award_full(lead))],
                 className="small muted"),
        html.P(describe(lead, 600), className="drawer-desc"),
        history_block(lead, opp_id),
        html.Div([html.Div("Why it matched your profile", className="k"),
                  html.Ul([html.Li(r, className="why-ok") for r in t.get("reasons") or []]
                          + [html.Li(w, className="why-warn") for w in t.get("warnings") or []], className="why")],
                 className="ov-block") if t.get("reasons") or t.get("warnings") else None,
        *notes,
        q_block,
        html.Div([
            html.Span("Added! ✓", className="btn btn-added") if just_added else
            dcc.Link("See in pipeline →", href=f"/opportunity/{opp_id}", className="btn btn-primary") if opp_id else
            html.Button("Add to pipeline", id="drawer-save", className="btn btn-primary"),
            dcc.Link("See in pipeline →", href="/pipeline", className="btn btn-quiet") if just_added else None,
            None if opp_id else html.Button("Add & start application", id="drawer-start", className="btn btn-quiet"),
            html.A("View source ↗", href=lead["url"], target="_blank", className="btn btn-quiet") if lead.get("url")
            else None,
        ], className="btn-row wrap"),
        html.Div(id="drawer-msg", className="form-msg"),
        usage_line(lead["extract_usage"]) if lead.get("extract_usage") else None,
    ], className="drawer-head")


def _fit_of(lead: dict) -> int:
    a = db.get_lead_assessment(lead["source_id"])
    return a["result"]["fit_score"] if a and a["result"].get("fit_score") is not None else -1


def results_view(res: dict, pending: bool = False):
    saved = in_pipeline()
    ranked, filtered = list(res["ranked"]), res["filtered"]
    if not pending:  # once assessed, best fit first; unassessed last
        ranked.sort(key=lambda lead: (-_fit_of(lead), -lead["triage"]["score"]))
    head = html.Div(
        [
            html.Div(f"{len(ranked)} match{'es' if len(ranked) != 1 else ''}", className="big-num small-big"),
            html.Div(
                [html.Div("Searched for: " + ", ".join(res["keywords"]), className="small"),
                 html.Div(" · ".join(res["notes"]) + f" · {len(filtered)} filtered out", className="small muted")],
            ),
        ],
        className="results-head",
    )
    errors = [html.Div(e, className="alert alert-attn") for e in res["errors"]]
    body = [result_card(lead, saved, pending) for lead in ranked] or [
        empty("No matches. Try other keywords, follow some foundations, or check your Profile's focus areas.")]
    filt = html.Details(
        [html.Summary(f"Filtered out ({len(filtered)}) — why each was skipped", className="filtered-summary"),
         html.P("Click any of these to see what it is. You can still assess one if you think the rules got it wrong.",
                className="hint"),
         html.Ul([html.Li([html.Span(lead["title"], className="filtered-title"),
                           html.Span(f" — {lead['triage']['excluded']}", className="small muted"),
                           html.Span(" View →", className="small-link")],
                          id={"type": "lead-open", "sid": lead["source_id"]}, n_clicks=0,
                          className="filtered-item clickable") for lead in filtered],
                 className="filtered")],
        className="block",
    ) if filtered else None
    note = html.P(FIT_LEGEND + " Every match gets a full fit assessment from the Fit Agent, then the list is sorted by fit. "
                  "Results filtered out by the free rules above (wrong eligibility, deadline passed, award too small, "
                  "off-topic) are not assessed, which keeps cost down. Assessments are saved, so searching again is free.",
                  className="hint")
    return [head, *errors, *body, filt, note, usage_line(res["usage"]) if res["usage"] else None]


def assess_status(summary: dict | None, n: int):
    if summary is None:
        return html.Div([html.Span(className="spinner-dot"), f"Assessing fit for {n} result{'s' if n != 1 else ''}…"],
                        className="assess-status")
    bits = [f"Fit assessed for {summary['new'] + summary['cached']} results"]
    if summary["cached"]:
        bits.append(f"{summary['cached']} from earlier searches (no cost)")
    parts = [html.Div(" · ".join(bits), className="assess-status done")]
    if summary["failed"]:
        parts.append(html.Div("Couldn't assess: " + "; ".join(summary["failed"]) + ". Click one to try again.",
                              className="alert alert-attn small"))
    if summary["usage"]:
        parts.append(usage_line(summary["usage"]))
    return parts


def layout():
    prof = (db.get_profile() or {"data": {}})["data"]
    opts, selected = source_options(prof)
    default_kw = ", ".join(search_keywords(prof, None))
    return html.Div(
        [
            page_header("Discover", "Search open grants that fit your organisation, from federal listings, your "
                                    "state's portal where available, and the funders you follow."),
            card(
                [
                    html.Div(
                        [
                            dcc.Input(id="disc-query", type="text", className="input",
                                      placeholder=f"Keywords, comma-separated (blank = your focus areas: {default_kw})"),
                            html.Button("Search", id="disc-search", className="btn btn-primary"),
                        ],
                        className="input-row",
                    ),
                    dcc.Checklist(opts, selected, id="disc-sources", inline=True, className="chips sources-row"),
                    html.P(state_note(prof), className="hint"),
                ],
                className="search-card",
            ),
            html.Div(
                [
                    card([dcc.Loading(html.Div(id="disc-status"), type="dot", color="#2f5d50"),
                          html.Div(id="disc-assess-status"),
                          html.Div(empty("Search to see ranked matches."), id="disc-results")]),
                    html.Div(
                        [
                            card([
                                section_title("Assess one you found",
                                              html.Button("Sample", id="imp-sample", className="btn-link")),
                                html.P("An application form, RFP or guidelines you found elsewhere. Grant Compass "
                                       "pulls out the facts and the application questions, then assesses the fit.",
                                       className="hint"),
                                dcc.Upload(
                                    html.Div(id="imp-file-label",
                                             children=["Drop a PDF or Word file, or ",
                                                       html.Span("browse", className="link-text")]),
                                    id="imp-file", accept=".pdf,.docx,.txt,.md", max_size=10_000_000,
                                    className="upload compact",
                                ),
                                dcc.Input(id="imp-url", type="url", placeholder="…or paste a link to the opportunity",
                                          className="input full"),
                                html.Details([html.Summary("…or paste the text", className="toggle"),
                                              dcc.Textarea(id="imp-text", className="textarea short")],
                                             id="imp-text-box", className="block"),
                                html.Button("Assess opportunity", id="imp-run", className="btn btn-primary btn-block"),
                                dcc.Loading(html.Div(id="imp-msg", className="form-msg"), type="dot", color="#2f5d50"),
                            ]),
                            card([
                                section_title("Foundations you follow"),
                                html.P("Federal listings don't include private foundations. Add the grants page of "
                                       "any foundation you want to keep an eye on, and every search will check it "
                                       "for open opportunities and score them alongside the federal results.",
                                       className="watch-intro"),
                                html.Ol([
                                    html.Li("Paste the funder's grants or “how to apply” page."),
                                    html.Li("Search as usual. Open calls appear tagged “Watchlist”."),
                                    html.Li("Pages are only re-read by the AI when they change, so following "
                                            "costs almost nothing."),
                                ], className="watch-steps"),
                                html.Label("Funder's grants page", className="field-label"),
                                dcc.Input(id="watch-url", type="url",
                                          placeholder="e.g. https://www.yourcommunityfoundation.org/grants",
                                          className="input full"),
                                html.Label("Funder name (optional)", className="field-label"),
                                dcc.Input(id="watch-name", type="text", placeholder="e.g. Dayton Foundation",
                                          className="input full"),
                                html.Button("Follow this funder", id="watch-add", className="btn btn-quiet btn-block"),
                                html.Div(id="watch-msg", className="form-msg"),
                                html.Div(watch_list(), id="watch-list"),
                            ]),
                        ],
                        className="stack",
                    ),
                ],
                className="two-col wide-left",
            ),
            dcc.Store(id="disc-leads"),
            dcc.Store(id="disc-res"),
            dcc.Store(id="disc-assess"),
            dcc.Store(id="drawer-sid"),
            html.Div(
                [
                    html.Div(id="drawer-backdrop", className="drawer-backdrop", n_clicks=0),
                    html.Aside(
                        [
                            html.Button("×", id="drawer-close", className="drawer-close", title="Close"),
                            html.Div(id="drawer-header"),
                            dcc.Loading(html.Div(id="drawer-fit", className="drawer-fit"), type="dot",
                                        color="#2f5d50"),
                        ],
                        className="drawer-panel",
                    ),
                ],
                id="drawer",
                className="drawer",
            ),
        ]
    )


# --- Callbacks ------------------------------------------------------------------------
@callback(
    Output("disc-results", "children"),
    Output("disc-leads", "data"),
    Output("disc-res", "data"),
    Output("disc-assess", "data"),
    Output("disc-status", "children"),
    Output("disc-assess-status", "children"),
    Input("disc-search", "n_clicks"),
    Input("disc-query", "n_submit"),
    State("disc-query", "value"),
    State("disc-sources", "value"),
    State("disc-leads", "data"),
    prevent_initial_call=True,
)
def search(n, s, query, sources, leads):
    """Step 1: search and show results at once. Step 2 (below) fills in every fit score."""
    sources = sources or []
    if not sources:
        return (html.Div("Choose at least one source.", className="error-text"), no_update, no_update, no_update,
                "", "")
    res = run(query, "federal" in sources, "state" in sources, "watchlist" in sources, "directory" in sources)
    imported = {k: v for k, v in (leads or {}).items() if k.startswith("import:")}  # keep imports open in the panel
    leads = {**imported, **{lead["source_id"]: lead for lead in res["ranked"] + res["filtered"]}}
    todo = sum(1 for lead in res["ranked"] if not db.get_lead_assessment(lead["source_id"]))
    status = assess_status(None, todo) if todo else assess_status({"new": 0, "cached": len(res["ranked"]),
                                                                   "failed": [], "usage": None}, 0)
    return (results_view(res, pending=bool(todo)), leads, res,
            {"n": (n or 0) + (s or 0)} if todo else no_update, "", status)


@callback(
    Output("disc-results", "children", allow_duplicate=True),
    Output("disc-assess-status", "children", allow_duplicate=True),
    Input("disc-assess", "data"),
    State("disc-res", "data"),
    prevent_initial_call=True,
)
def assess_results(_trigger, res):
    if not res:
        return no_update, no_update
    summary = assess_leads(res["ranked"])
    return results_view(res), assess_status(summary, len(res["ranked"]))


@callback(
    Output("drawer", "className"),
    Output("drawer-header", "children"),
    Output("drawer-fit", "children", allow_duplicate=True),
    Output("drawer-sid", "data"),
    Input({"type": "lead-open", "sid": ALL}, "n_clicks"),
    Input({"type": "lead-open-side", "sid": ALL}, "n_clicks"),
    State("disc-leads", "data"),
    prevent_initial_call=True,
)
def open_drawer(main_clicks, side_clicks, leads):
    clicks = (main_clicks or []) + (side_clicks or [])
    if not ctx.triggered_id or not any(clicks) or not ctx.triggered[0]["value"] or not leads:
        return no_update, no_update, no_update, no_update
    lead = leads.get(ctx.triggered_id["sid"])
    if not lead:
        return no_update, no_update, no_update, no_update
    cached = db.get_lead_assessment(lead["source_id"])
    if cached:  # already assessed: show it at once, no AI call ("manual" stops a second assessment)
        return ("drawer open", drawer_header(lead, in_pipeline()), fit_overview(cached),
                {"sid": lead["source_id"], "n": sum(clicks), "manual": True})
    if (lead.get("triage") or {}).get("excluded"):  # filtered out: show what it is; assess only on request
        return ("drawer open", drawer_header(lead, in_pipeline()), filtered_overview(lead),
                {"sid": lead["source_id"], "n": sum(clicks), "manual": True})
    waiting = html.P("Assessing fit against your Profile and library… (about 20 seconds)", className="hint")
    return "drawer open", drawer_header(lead, in_pipeline()), waiting, {"sid": lead["source_id"], "n": sum(clicks)}


@callback(
    Output("drawer-fit", "children"),
    Output({"type": "lead-fit", "sid": ALL}, "children"),
    Input("drawer-sid", "data"),
    State("disc-leads", "data"),
    State({"type": "lead-fit", "sid": ALL}, "id"),
    prevent_initial_call=True,
)
def drawer_fit(data, leads, badge_ids):
    """Assess one search result with the Fit Agent. Cached, so reopening it is free."""
    sid = (data or {}).get("sid")
    if not sid or not leads or sid not in leads or (data or {}).get("manual"):
        return no_update, [no_update] * len(badge_ids)
    cached = db.get_lead_assessment(sid)
    if not cached:
        try:
            res = assess(lead_to_opportunity(leads[sid]))
        except Exception as exc:
            msg = friendly(exc)
            return html.Div(msg, className="error-text"), [no_update] * len(badge_ids)
        db.save_lead_assessment(sid, res["result"], res["usage"])
        cached = db.get_lead_assessment(sid)
    badges = [fit_badge(i["sid"]) if i["sid"] == sid else no_update for i in badge_ids]
    return fit_overview(cached), badges


@callback(
    Output("drawer", "className", allow_duplicate=True),
    Input("drawer-close", "n_clicks"),
    Input("drawer-backdrop", "n_clicks"),
    prevent_initial_call=True,
)
def close_drawer(_a, _b):
    return "drawer"


@callback(
    Output("drawer-fit", "children", allow_duplicate=True),
    Input("drawer-assess-anyway", "n_clicks"),
    State("drawer-sid", "data"),
    State("disc-leads", "data"),
    prevent_initial_call=True,
)
def assess_anyway(n, data, leads):
    sid = (data or {}).get("sid")
    if not n or not sid or not leads or sid not in leads:
        return no_update
    try:
        res = assess(lead_to_opportunity(leads[sid]))
    except Exception as exc:
        msg = friendly(exc)
        return html.Div(msg, className="error-text")
    db.save_lead_assessment(sid, res["result"], res["usage"])
    return [html.Div([html.Strong("Filtered out by the free rules: "), leads[sid]["triage"]["excluded"]],
                     className="alert alert-attn small"),
            fit_overview(db.get_lead_assessment(sid))]


def _create(lead: dict, start: bool) -> int:
    """Save a result to the pipeline with its assessment and any questions found.
    Starting the application records the user's Go and builds the workback plan."""
    a = db.get_lead_assessment(lead["source_id"])
    status = "Drafting" if start else ("Go / No-Go" if a else "Researching")
    opp = lead_to_opportunity(lead)
    opp_id = db.add_opportunity(opp, status=status)
    if a:
        db.save_assessment(opp_id, a["result"], a["usage"])
    for q in (lead.get("opportunity") or {}).get("questions") or []:
        db.add_question(opp_id, q["prompt"], q.get("limit_type") if q.get("limit_value") else None, q.get("limit_value"))
    if start:
        db.update_opportunity(opp_id, decision="Go", decision_reason="Started an application from Discover")
        if opp.get("deadline"):
            db.add_tasks(opp_id, [(t, d, False) for t, d in workback_plan(date.fromisoformat(opp["deadline"]))])
    return opp_id


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Output("drawer-header", "children", allow_duplicate=True),
    Output({"type": "lead-pipe", "sid": ALL}, "children"),
    Input("drawer-save", "n_clicks"),
    Input("drawer-start", "n_clicks"),
    State("drawer-sid", "data"),
    State("disc-leads", "data"),
    prevent_initial_call=True,
)
def drawer_save(n_save, n_start, data, leads):
    """Add to pipeline: save and stay on Discover ("Added!"), so you can keep exploring.
    Add & start application: save, record Go, and go straight to the writing workspace."""
    sid = (data or {}).get("sid")
    cards = [no_update] * len(ctx.outputs_list[2])
    if not (n_save or n_start):
        return no_update, no_update, cards
    if not sid or not leads or sid not in leads:
        raise PreventUpdate  # nothing to save; shouldn't happen now that every open records its grant
    start = ctx.triggered_id == "drawer-start"
    opp_id = _create(leads[sid], start)
    if start:
        return f"/application/{opp_id}", no_update, cards
    # Mark the result card too, so it's clear after the panel closes that this grant is already saved.
    cards = [in_pipeline_link(opp_id) if o["id"]["sid"] == sid else no_update for o in ctx.outputs_list[2]]
    return no_update, drawer_header(leads[sid], in_pipeline(), just_added=True), cards


@callback(Output("imp-file-label", "children"), Input("imp-file", "filename"), prevent_initial_call=True)
def show_file(name):
    return [html.Strong(name), " — ready. ", html.Span("Choose another", className="link-text")] if name else no_update


@callback(
    Output("drawer", "className", allow_duplicate=True),
    Output("drawer-header", "children", allow_duplicate=True),
    Output("drawer-fit", "children", allow_duplicate=True),
    Output("drawer-sid", "data", allow_duplicate=True),
    Output("disc-leads", "data", allow_duplicate=True),
    Output("imp-msg", "children"),
    Input("imp-run", "n_clicks"),
    State("imp-file", "contents"),
    State("imp-file", "filename"),
    State("imp-url", "value"),
    State("imp-text", "value"),
    State("disc-leads", "data"),
    prevent_initial_call=True,
)
def import_opportunity(n, contents, filename, url, text, leads):
    """Read → extract (Research Agent) → assess (Fit Agent) → open the fit panel."""
    if not n:
        return (no_update,) * 6
    try:
        lead = import_and_assess(contents, filename, url, text)
    except ValueError as exc:
        return no_update, no_update, no_update, no_update, no_update, html.Span(str(exc), className="error-text")
    except Exception as exc:  # network or model errors: show them, don't crash
        return (no_update,) * 5 + (html.Span(friendly(exc),
                                             className="error-text"),)
    leads = {**(leads or {}), lead["source_id"]: lead}
    return ("drawer open", drawer_header(lead, in_pipeline()), fit_overview(db.get_lead_assessment(lead["source_id"])),
            {"sid": lead["source_id"], "n": n}, leads, html.Span("Assessed. See the panel on the right.",
                                                                  className="ok-text"))


@callback(
    Output("watch-list", "children"),
    Output("watch-msg", "children"),
    Output("disc-sources", "options"),
    Input("watch-add", "n_clicks"),
    Input({"type": "watch-remove", "id": ALL}, "n_clicks"),
    State("watch-url", "value"),
    State("watch-name", "value"),
    prevent_initial_call=True,
)
def manage_watch(_add, removes, url, name):
    trig = ctx.triggered_id
    msg = ""
    if trig == "watch-add":
        try:
            add_watch(url, name)
            msg = html.Span("Following. It will be checked the next time you search.", className="ok-text")
        except ValueError as exc:
            msg = html.Span(str(exc), className="error-text")
    elif isinstance(trig, dict) and any(removes):
        db.remove_watch(trig["id"])
    else:
        return no_update, no_update, no_update
    prof = (db.get_profile() or {"data": {}})["data"]
    return watch_list(), msg, source_options(prof)[0]


@callback(Output("imp-text", "value"), Output("imp-text-box", "open"), Input("imp-sample", "n_clicks"),
          prevent_initial_call=True)
def load_sample(_):
    """A fictional application form with numbered questions and word limits."""
    return (SAMPLE_DIR / "application_form.md").read_text(), True



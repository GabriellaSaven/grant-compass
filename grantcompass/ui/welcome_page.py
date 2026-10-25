"""First steps for a new organisation: the three things the AI needs before it can help."""

from dash import Input, Output, callback, dcc, html
from dash.exceptions import PreventUpdate

from .. import db
from ..errors import friendly
from ..profile import completeness
from .components import card, page_header, progress_bar


def steps():
    prof = db.get_profile()
    pct, _ = completeness(prof["data"] if prof else {})
    docs, team = len(db.list_documents()), len(db.list_team())
    return [
        ("Fill in your profile", f"{pct}% complete", pct >= 60,
         "Mission, programmes, who you serve, budget and grant preferences. Discover ranks grants against it, "
         "and the writers draft from it.", "/profile", "Edit profile", pct),
        ("Upload your source documents", f"{docs} uploaded", docs >= 2,
         "Annual and impact reports, budgets, past applications. The AI only writes from what's here, so more "
         "evidence means stronger drafts.", "/profile/documents", "Upload documents", min(100, docs * 25)),
        ("Add your team", f"{team} {'person' if team == 1 else 'people'}", team >= 2,
         "Anyone who can be responsible for a grant.", "/profile/team", "Add people", min(100, team * 50)),
    ]


def website_panel():
    """While the site is being read: what's happening. Afterwards: what was filled, to check."""
    prof = (db.get_profile() or {"data": {}})["data"]
    site = prof.get("website")
    if prof.get("_import_pending"):
        return html.Div([html.Div(className="typing", children=[html.Span(), html.Span(), html.Span()]),
                         html.Div([html.Strong(f"Reading {site}…"),
                                   html.Div("The Research Agent is reading your homepage and key pages to "
                                            "fill in your profile. About 15 seconds.", className="small muted")])],
                        className="import-panel busy")
    if prof.get("_import_result"):
        r = prof["_import_result"]
        return html.Div([
            html.Strong(r["headline"]),
            html.Div(r["detail"], className="small muted"),
            dcc.Link("Check your profile →", href="/profile", className="small-link"),
        ], className="import-panel " + ("ok" if r.get("ok") else "warn"))
    return None


def layout():
    items = steps()
    done = sum(s[2] for s in items)
    pending = ((db.get_profile() or {"data": {}})["data"]).get("_import_pending")
    return html.Div([
        page_header("Welcome to Grant Compass", "Three steps and the AI is ready to find and write grants for you."),
        html.Div(website_panel(), id="import-panel"),
        dcc.Interval(id="import-go", interval=300, max_intervals=1, disabled=not pending),
        html.Div(id="welcome-steps", children=steps_view(items)),
        html.Div([dcc.Link("Go to Discover →", href="/discover", className="btn btn-primary"),
                  html.Span(f"{done} of 3 done. You can come back here any time from Home.", className="hint")],
                 className="btn-row"),
    ])


def steps_view(items):
    return html.Div([card([
            html.Div([html.Span("✓" if ok else str(i), className="step-n" + (" done" if ok else "")),
                      html.Div([html.Div(title, className="step-title"), html.Div(status, className="step-status")])],
                     className="step-head"),
            html.P(why, className="hint"),
            progress_bar(pct),
            dcc.Link(cta + " →", href=href, className="btn btn-primary" if not ok else "btn btn-quiet"),
        ], className="step-card") for i, (title, status, ok, why, href, cta, pct) in enumerate(items, 1)],
        className="steps")


def run_import() -> dict:
    """Read the website, fill the profile, and remember the result for the Welcome and Profile pages."""
    from ..profile_builder import fill_from_website

    prof = (db.get_profile() or {"data": {}})["data"]
    try:
        r = fill_from_website(prof["website"])
        n = len(r["filled"])
        result = {"ok": n > 0, "headline": f"Filled {n} profile fields from your website" if n else
                  "Your website didn't answer any profile fields we could verify",
                  "detail": (", ".join(r["filled"]) + ". " if n else "")
                  + f"Read {len(r['pages'])} page{'s' if len(r['pages']) != 1 else ''}, now also in your source "
                    "documents." + (f" {r['unverified']} suggestion(s) were dropped because their wording wasn't on "
                                    "the site." if r["unverified"] else "")}
    except Exception as exc:
        result = {"ok": False, "headline": "We couldn't read your website", "detail": friendly(exc)}
    prof = (db.get_profile() or {"data": {}})["data"]
    prof.update(_import_pending=False, _import_result=result)
    db.save_profile(prof)
    return result


@callback(Output("import-panel", "children"), Output("welcome-steps", "children"), Input("import-go", "n_intervals"),
          prevent_initial_call=True)
def import_website(n):
    if not n or not ((db.get_profile() or {"data": {}})["data"]).get("_import_pending"):
        raise PreventUpdate
    run_import()
    return website_panel(), steps_view(steps())

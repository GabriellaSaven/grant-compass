"""Profile: the structured form describing the nonprofit. It feeds grant
matching (Fit Agent) and will feed drafting (Grant Writer)."""

from dash import ALL, Input, Output, State, callback, dcc, html, no_update

from .. import db
from ..profile import FIELDS, SECTIONS, completeness, render
from .components import card, page_header, profile_tabs


def _anchor(section: str) -> str:
    return "sec-" + "".join(c if c.isalnum() else "-" for c in section.lower())


def field(key: str, value, from_site: bool = False):
    label, kind, opts, help_ = FIELDS[key]
    fid = {"type": "pf", "key": key}
    if kind == "textarea":
        control = dcc.Textarea(id=fid, value=value or "", className="textarea profile-ta")
    elif kind == "number":
        control = dcc.Input(id=fid, type="number", value=value, min=0, className="input")
    elif kind == "select":
        control = dcc.Dropdown(opts, value, id=fid, placeholder="Choose…", className="dropdown")
    elif kind == "multi":
        control = dcc.Checklist(opts, value or [], id=fid, className="chips", inline=True)
    else:
        control = dcc.Input(id=fid, type="text", value=value or "", className="input")
    wide = kind in ("textarea", "multi")
    return html.Div(
        [html.Label([label, html.Span("from your website", className="from-site",
                                      title="Filled in from your website. Check it before you rely on it.")
                      if from_site else None], className="field-label"), control,
         html.Div(help_, className="hint") if help_ else None],
        className="pf-field" + (" wide" if wide else ""),
    )


def _clean(values, ids) -> dict:
    return {i["key"]: (v.strip() if isinstance(v, str) else v) for v, i in zip(values, ids)}


def _same(a: dict, b: dict) -> bool:
    """Compare saved and on-screen values, treating blank, None and [] as equal."""
    norm = lambda v: None if v in (None, "", []) else v  # noqa: E731
    return all(norm(a.get(k)) == norm(b.get(k)) for k in FIELDS)


def sidebar(data: dict, updated: str | None, unsaved: bool = False):
    pct, gaps = completeness(data)
    return html.Div(
        [
            html.Div("Profile complete", className="k"),
            html.Div(f"{pct}%", className="big-num"),
            html.Div(className="bar", children=html.Div(className="bar-fill", style={"width": f"{pct}%"})),
            html.Ul(
                [html.Li(html.A([html.Span("○" if s in gaps else "●", className="sec-mark" + (" gap" if s in gaps else "")),
                                 s], href=f"#{_anchor(s)}")) for s, _ in SECTIONS],
                className="sec-nav",
            ),
            html.P("Unsaved changes", className="unsaved") if unsaved else
            html.P(f"Last saved {updated[:16].replace('T', ' ')}" if updated else "Not saved yet", className="hint"),
        ]
    )


def layout():
    prof = db.get_profile()
    data, updated = (prof["data"], prof["updated"]) if prof else ({}, None)
    sections = [
        card(
            [html.H2(name, className="pf-section-title"),
             html.Div([field(k, data.get(k), k in data.get("_from_website", [])) for k, *_ in fields],
                      className="pf-grid")],
            className="pf-section",
        )
        for name, fields in SECTIONS
    ]
    for c, (name, _) in zip(sections, SECTIONS):
        c.id = _anchor(name)
    return html.Div(
        [
            profile_tabs("/profile"),
            page_header(
                "Organisation Profile",
                "Describe your nonprofit once. Grant Compass uses this profile to match opportunities to you "
                "and, when drafting, as source material. Leave a field blank rather than guess: blanks are "
                "reported as missing, never filled in by the AI.",
            ),
            html.Div(
                [
                    html.Div(
                        card([
                            html.Div(sidebar(data, updated), id="pf-sidebar"),
                            html.Button("Save profile", id="pf-save", className="btn btn-primary btn-block"),
                            html.Div(id="pf-msg", className="form-msg"),
                            html.Div([
                                html.Div("Fill from your website", className="field-label"),
                                dcc.Input(id="pf-site", type="url", value=data.get("website") or "",
                                          placeholder="yourorg.org", className="input full"),
                                html.Button("Read website", id="pf-site-go", n_clicks=0,
                                            className="btn btn-quiet btn-block"),
                                html.Div("Fills only blank fields, each backed by words on your site. Save first if "
                                         "you have unsaved changes.", className="hint"),
                                dcc.Loading(html.Div(id="pf-site-msg", className="form-msg"), type="dot",
                                            color="#2f5d50"),
                            ], className="pf-site"),
                        ]),
                        className="side-card",
                    ),
                    html.Div(
                        [
                            *sections,
                            card([
                                html.Details([
                                    html.Summary("What the AI reads", className="pf-preview-summary"),
                                    html.P("This is exactly how your profile is given to the agents, as the first "
                                           "source, alongside your source documents.", className="hint"),
                                    html.Pre(render(data) if data else "Nothing saved yet.", id="pf-preview",
                                             className="doc-content"),
                                ]),
                            ]),
                            html.Button("Save profile", id="pf-save-bottom", className="btn btn-primary"),
                        ],
                        className="stack",
                    ),
                ],
                className="two-col narrow-left",
            ),
        ]
    )


@callback(
    Output("pf-sidebar", "children"),
    Output("pf-msg", "children", allow_duplicate=True),
    Input({"type": "pf", "key": ALL}, "value"),
    State({"type": "pf", "key": ALL}, "id"),
    prevent_initial_call=True,
)
def track(values, ids):
    """Recompute completeness from what is on screen, as the user types."""
    data = _clean(values, ids)
    prof = db.get_profile()
    saved, updated = (prof["data"], prof["updated"]) if prof else ({}, None)
    return sidebar(data, updated, unsaved=not _same(data, saved)), ""


@callback(
    Output("pf-sidebar", "children", allow_duplicate=True),
    Output("pf-msg", "children"),
    Output("pf-preview", "children"),
    Input("pf-save", "n_clicks"),
    Input("pf-save-bottom", "n_clicks"),
    State({"type": "pf", "key": ALL}, "value"),
    State({"type": "pf", "key": ALL}, "id"),
    prevent_initial_call=True,
)
def save(n1, n2, values, ids):
    if not (n1 or n2):
        return no_update, no_update, no_update
    data = _clean(values, ids)
    saved = (db.get_profile() or {"data": {}})["data"]
    # Keep the app's own notes (which fields came from the website) alongside the form's fields.
    db.save_profile({**{k: v for k, v in saved.items() if k.startswith("_")}, **data})
    prof = db.get_profile()
    return sidebar(prof["data"], prof["updated"]), html.Span("Saved. New assessments will use this profile.",
                                                             className="ok-text"), render(data)


@callback(Output("pf-site-msg", "children"), Output("url", "pathname", allow_duplicate=True),
          Input("pf-site-go", "n_clicks"), State("pf-site", "value"), prevent_initial_call=True,
          running=[(Output("pf-site-go", "disabled"), True, False),
                   (Output("pf-site-go", "children"), "Reading your website…", "Read website")])
def fill_from_site(n, site):
    """The Research Agent reads the site and fills blank fields; the page reloads to show them, marked."""
    if not n:
        return no_update, no_update
    if not (site or "").strip():
        return html.Span("Enter your website first.", className="error-text"), no_update
    from ..profile_builder import fill_from_website
    from ..errors import friendly

    try:
        r = fill_from_website(site.strip() if site.startswith("http") else "https://" + site.strip())
    except Exception as exc:
        return html.Span(friendly(exc), className="error-text"), no_update
    if not r["filled"]:
        return html.Span("No blank fields could be filled from the website with words we could verify.",
                         className="small"), no_update
    return "", "/profile/from-website"  # a new address, so the page re-renders with the filled fields

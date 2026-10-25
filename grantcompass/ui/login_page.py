"""The front door: log in, create an organisation, or explore a fictional demo nonprofit."""

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask import session

from .. import orgs
from ..profile import US_STATES

CAUSE_TONE = ["#2f5d50", "#9a5b2e", "#3d5a8a", "#7a4a7e", "#8a6a1f", "#a0473f"]


def demo_card(d: dict, i: int):
    initials = "".join(w[0] for w in d["name"].replace("&", "").split()[:2]).upper()
    return html.Button([
        html.Span(initials, className="demo-mark", style={"background": CAUSE_TONE[i % len(CAUSE_TONE)]}),
        html.Span(d["cause"], className="demo-cause"),
        html.Span(d["name"], className="demo-name"),
        html.Span(d["location"], className="demo-loc"),
        html.Span(d["tagline"], className="demo-tag"),
        html.Span("Explore →", className="demo-go"),
    ], id={"type": "demo-open", "slug": d["slug"]}, n_clicks=0, className="demo-card")


def layout():
    return html.Div([
        html.Div([
            html.Img(src="/assets/logo.svg", className="login-mark", alt="Grant Compass"),
            html.Div("Grant Compass", className="login-brand"),
            html.H1("Find the right grants. Write stronger applications."),
            html.P("An AI workspace for nonprofit grant teams: discovery, Go / No-Go decisions, a pipeline, and a "
                   "writing coach that never invents facts.", className="lede"),
        ], className="login-hero"),

        html.Div([
            html.Div([
                html.Div("Explore a demo organisation", className="login-h"),
                html.P("Six fictional nonprofits with profiles, documents, teams and grants already filled in. Each "
                       "works in a different field and state, so Discover finds different funders for each. No "
                       "password needed; changes stay in that demo.", className="hint"),
                html.Div([demo_card(d, i) for i, d in enumerate(orgs.demos())], className="demo-grid"),
            ], className="login-demos"),

            html.Div([
                html.Div([
                    html.Div("Log in", className="login-h"),
                    dcc.Input(id="login-email", type="email", placeholder="Email", className="input full",
                              autoComplete="username"),
                    dcc.Input(id="login-password", type="password", placeholder="Password", className="input full",
                              autoComplete="current-password", n_submit=0),
                    html.Button("Log in", id="login-go", n_clicks=0, className="btn btn-primary btn-block"),
                    html.Div(id="login-msg", className="form-msg"),
                ], className="login-box"),
                html.Div([
                    html.Div("Start your organisation", className="login-h"),
                    html.P("Create an account, then fill in your profile and upload your documents. Nothing is "
                           "pre-filled.", className="hint"),
                    dcc.Input(id="new-name", placeholder="Your name", className="input full", autoComplete="name"),
                    dcc.Input(id="new-org", placeholder="Organisation name", className="input full",
                              autoComplete="organization"),
                    dcc.Dropdown(US_STATES, None, id="new-state", placeholder="State", className="dropdown"),
                    dcc.Input(id="new-website", type="url", placeholder="Website (optional), e.g. yourorg.org",
                              className="input full", autoComplete="url"),
                    html.Div("Add your website and the AI reads it to fill in as much of your profile as it can. "
                             "You check everything before it's used.", className="hint"),
                    dcc.Input(id="new-email", type="email", placeholder="Email", className="input full",
                              autoComplete="email"),
                    dcc.Input(id="new-password", type="password", placeholder="Password (8+ characters)",
                              className="input full", autoComplete="new-password"),
                    html.Button("Create account", id="new-go", n_clicks=0, className="btn btn-quiet btn-block"),
                    html.Div(["By creating an account you agree to how we handle data in our ",
                              dcc.Link("privacy policy", href="/privacy"), "."], className="hint"),
                    html.Div(id="new-msg", className="form-msg"),
                ], className="login-box"),
            ], className="login-side"),
        ], className="login-grid"),
        html.P(["Accounts are stored only on this computer; passwords are kept as salted hashes, never as text. ",
                dcc.Link("Privacy policy", href="/privacy")], className="login-foot"),
    ], className="login")


def _enter(slug: str, user: str | None = None):
    session.clear()
    session["org"], session["user"] = slug, user
    session.permanent = True
    orgs.activate(slug)


# Every way in also clears the chat, so one organisation's conversation never shows in another.
CHAT = Output("chat-history", "data", allow_duplicate=True)


@callback(Output("url", "pathname", allow_duplicate=True), CHAT,
          Input({"type": "demo-open", "slug": ALL}, "n_clicks"), prevent_initial_call=True)
def open_demo(clicks):
    if not ctx.triggered_id or not any(clicks):
        raise PreventUpdate
    _enter(ctx.triggered_id["slug"])
    return "/", []


@callback(Output("url", "pathname", allow_duplicate=True), Output("login-msg", "children"), CHAT,
          Input("login-go", "n_clicks"), Input("login-password", "n_submit"),
          State("login-email", "value"), State("login-password", "value"), prevent_initial_call=True)
def log_in(n, n_submit, email, password):
    if not (n or n_submit):
        raise PreventUpdate
    try:
        user = orgs.login(email, password)
    except ValueError as exc:
        return no_update, html.Span(str(exc), className="error-text"), no_update
    _enter(user["slug"], user["email"])
    return "/", "", []


@callback(Output("url", "pathname", allow_duplicate=True), Output("new-msg", "children"), CHAT,
          Input("new-go", "n_clicks"),
          State("new-name", "value"), State("new-org", "value"), State("new-state", "value"),
          State("new-website", "value"),
          State("new-email", "value"), State("new-password", "value"), prevent_initial_call=True)
def sign_up(n, name, org, state, website, email, password):
    if not n:
        raise PreventUpdate
    try:
        user = orgs.create_account(name, email, password, org, state, website)
    except ValueError as exc:
        return no_update, html.Span(str(exc), className="error-text"), no_update
    _enter(user["slug"], user["email"])
    return "/welcome", "", []

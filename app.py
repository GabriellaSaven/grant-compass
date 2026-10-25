"""Grant Compass: an AI grant research and writing workspace for nonprofit teams.

Run:  python app.py   then open http://127.0.0.1:8050"""

import os
import secrets
import sys
import time

if sys.version_info < (3, 10):  # fail with a clear message rather than a confusing syntax error deeper in
    sys.exit(f"Grant Compass needs Python 3.10 or newer; this is {sys.version.split()[0]}. See README, Run it locally.")
from datetime import timedelta

from dash import Dash, Input, Output, dcc, html
from flask import session

from grantcompass import db, orgs
from grantcompass.config import MAX_REQUEST_BYTES, ROOT
from grantcompass.ui import (
    answers_page, applications_page, discover_page, health_page, home_page, library_page, login_page,
    opportunity_page, pipeline_page, privacy_page, profile_page, reports_page, team_page, welcome_page,
    workspace_page,
)
from grantcompass.ui.chat_widget import widget as chat_widget

app = Dash(__name__, title="Grant Compass", suppress_callback_exceptions=True)
# The compass mark is the browser-tab icon too.
app.index_string = app.index_string.replace(
    "{%favicon%}", '<link rel="icon" type="image/svg+xml" href="/assets/logo.svg">')

# Sessions: which organisation is open. The signing key is made once and kept on this computer.
KEY_FILE = ROOT / "data" / ".secret_key"
if not KEY_FILE.exists():
    KEY_FILE.parent.mkdir(exist_ok=True)
    KEY_FILE.write_text(secrets.token_hex(32))
app.server.secret_key = KEY_FILE.read_text().strip()
app.server.permanent_session_lifetime = timedelta(days=14)
app.server.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",  # no script or cross-site use
                         MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES)  # oversized uploads are refused before they're read


@app.server.before_request
def open_organisation():
    """Point the database and logs at the signed-in organisation for this request."""
    if session.get("org"):
        orgs.activate(session["org"])

# Each server start gets an id. An open tab checks it (assets/menu.js) and reloads itself after a restart,
# because a tab from before a restart still calls the old callbacks, and those requests fail.
BUILD_ID = str(int(time.time()))
app.server.add_url_rule("/__build", "build_id", lambda: BUILD_ID)

NAV = [("Home", "/"), ("Discover", "/discover"), ("Pipeline", "/pipeline"), ("Applications", "/applications"),
       ("Reports", "/reports"), ("Answer Library", "/answers")]
PROFILE_MENU = [("Edit profile", "/profile", "Mission, programmes, finances, preferences"),
                ("Source documents", "/profile/documents", "Upload reports, budgets and past applications"),
                ("Team", "/profile/team", "People who can be responsible for a grant"),
                ("Agent health", "/profile/health", "How the AI agents are working, and what they cost"),
                ("Privacy & your data", "/privacy", "Download your data, delete your account")]

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh="callback-nav"),
        html.Header(
            html.Div(
                [
                    dcc.Link([html.Img(src="/assets/logo.svg", className="brand-mark", alt=""),
                              html.Span("Grant", className="brand-a"), html.Span("Compass", className="brand-b")],
                             href="/", className="brand"),
                    html.Nav(id="nav", className="nav"),
                    html.Div(id="profile-link"),
                ],
                className="topbar-inner",
            ),
            className="topbar",
        ),
        html.Main(id="page", className="container"),
        html.Footer([html.Span("Grant Compass"), html.Span("·"),
                     dcc.Link("Privacy policy", href="/privacy", className="foot-link")], className="site-foot"),
        chat_widget(),  # Compass Assistant, bottom right on every page
        html.Div(id="build-id", hidden=True, **{"data-build": BUILD_ID}),
    ],
    id="shell",
)


def profile_menu(path: str):
    """Top-right organisation menu: edit the profile, or manage the documents the AI writes from.
    Re-rendered on every page change, so it closes after you pick an item."""
    prof = db.get_profile()
    name = (prof["data"].get("legal_name") if prof else None) or "Set up profile"
    initials = "".join(w[0] for w in name.replace(",", "").replace("&", "").split()[:2]).upper()
    active = path.startswith("/profile") or path == "/library"
    demo = orgs.is_demo(session.get("org", ""))
    session_links = [("Switch organisation", "/logout", "Pick another demo, or log in" if demo else "Log out")]
    if demo:
        session_links.insert(0, ("Reset this demo", "/reset-demo", "Undo your changes and start fresh"))
    return html.Details(
        [
            html.Summary(
                [html.Span(initials, className="avatar"),
                 html.Span([html.Span(name, className="profile-name"),
                            html.Span("Demo organisation" if demo else "Profile", className="profile-sub")],
                           className="profile-text"),
                 html.Span("▾", className="caret")],
                className="profile-link" + (" active" if active else ""),
            ),
            html.Div(
                [dcc.Link([html.Div(label, className="menu-label"), html.Div(hint, className="menu-hint")],
                          href=href, className="menu-item" + (" current" if path == href else ""))
                 for label, href, hint in PROFILE_MENU]
                + [html.Div(className="menu-sep")]
                + [dcc.Link([html.Div(label, className="menu-label"), html.Div(hint, className="menu-hint")],
                            href=href, className="menu-item quiet") for label, href, hint in session_links],
                className="profile-menu",
            ),
        ],
        className="profile-dd",
    )


@app.callback(Output("page", "children"), Output("nav", "children"), Output("profile-link", "children"),
              Output("shell", "className"), Input("url", "pathname"))
def route(path):
    path = path or "/"
    if path == "/logout":
        session.clear()
    if path == "/privacy":  # readable before signing in, as privacy law expects
        signed_in = bool(session.get("org"))
        nav = [dcc.Link(name, href=href, className="nav-link") for name, href in NAV] if signed_in else []
        return (privacy_page.layout(), nav, profile_menu(path) if signed_in else None,
                "logged-in" if signed_in else "logged-out")
    if not session.get("org") or path in ("/login", "/logout"):
        return login_page.layout(), [], None, "logged-out"
    if path == "/reset-demo":
        orgs.reset_demo(session["org"])
        orgs.activate(session["org"])
        path = "/"
    if path == "/welcome":
        page, section = welcome_page.layout(), "/"
    elif path.startswith("/report/"):
        parts = path.strip("/").split("/")
        try:
            page = workspace_page.layout(int(parts[1]), int(parts[2]) if len(parts) > 2 else None, kind="report")
        except ValueError:
            page = reports_page.layout()
        section = "/reports"
    elif path.startswith("/application/"):
        parts = path.strip("/").split("/")
        try:
            page = workspace_page.layout(int(parts[1]), int(parts[2]) if len(parts) > 2 else None)
        except ValueError:
            page = applications_page.layout()
        section = "/applications"
    elif path.startswith("/opportunity/"):
        try:
            page = opportunity_page.layout(int(path.rsplit("/", 1)[1]))
        except ValueError:
            page = home_page.layout()
        section = "/pipeline"
    else:
        pages = {"/discover": discover_page.layout, "/pipeline": pipeline_page.layout,
                 "/library": library_page.layout, "/profile/documents": library_page.layout,
                 "/profile": profile_page.layout, "/profile/team": team_page.layout,
                 "/profile/health": health_page.layout, "/profile/from-website": profile_page.layout,
                 "/applications": applications_page.layout, "/answers": answers_page.layout,
                 "/reports": reports_page.layout,
                 "/coach": applications_page.layout}  # old Grant Coach tab: coaching now lives in each question
        page = pages.get(path, home_page.layout)()
        section = path if path in pages else "/"
    nav = [dcc.Link(name, href=href, className="nav-link" + (" active" if href == section else ""))
           for name, href in NAV]
    return page, nav, profile_menu(path), "logged-in"


if __name__ == "__main__":
    # debug off so one edit doesn't spawn a second server via the reloader
    app.run(debug=False, port=int(os.environ.get("PORT", 8050)))

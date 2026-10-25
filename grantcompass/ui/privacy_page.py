"""Privacy policy, and the controls it promises (download your data, delete your account).

Every statement here describes what the code actually does; if the app changes, this page must change with
it. It is not legal advice: an organisation deploying Grant Compass should have counsel review it."""

import json
from datetime import date

from dash import Input, Output, callback, dcc, html
from dash.exceptions import PreventUpdate
from flask import session

from .. import orgs
from .components import card

EFFECTIVE = "October 23, 2026"
CONTACT = "privacy@grantcompass.example"  # replace with a real, monitored address before deploying


def _s(title: str, *body):
    return html.Section([html.H2(title), *body], className="pp-section")


def _p(text: str):
    return html.P(text)


def _ul(*items):
    return html.Ul([html.Li(i) for i in items])


LAWS = [
    ("FTC Act, Section 5 (unfair or deceptive practices)", "Applies to what we say about data.",
     "This policy describes only what the app actually does. We don't use data in ways this page doesn't "
     "disclose, and we update the page whenever that changes."),
    ("California Online Privacy Protection Act (CalOPPA)", "Applies to any online service used by California "
     "residents.", "This policy is linked from every page, lists the information collected and who it is shared "
     "with, explains how Do Not Track signals are handled, and shows its effective date."),
    ("State comprehensive privacy laws: California (CCPA/CPRA), Colorado, Oregon, Virginia, Connecticut, Texas, "
     "Delaware, New Jersey, Minnesota, Maryland and others", "Some exempt nonprofits (California's CCPA covers "
     "for-profit businesses); others, such as Colorado, Oregon, Delaware, New Jersey, Minnesota and Maryland, "
     "can apply to nonprofits above their thresholds.",
     "We provide the rights these laws share: access and portability (Download my data), correction (edit any "
     "record), and deletion (Delete my account). We do not sell personal information, share it for targeted "
     "advertising, or use it for profiling that produces legal or similarly significant effects."),
    ("Children's Online Privacy Protection Act (COPPA)", "Applies to services directed to children under 13.",
     "Grant Compass is for nonprofit staff and is not directed to children. We don't knowingly collect personal "
     "information from children. Organisations should describe the children they serve in aggregate, never by "
     "name."),
    ("Family Educational Rights and Privacy Act (FERPA)", "Governs student education records held by schools.",
     "Grant Compass is not an education records system. Don't upload identifiable student records; use "
     "aggregate results (for example, “68% reached benchmark”)."),
    ("HIPAA", "Applies to health plans, providers and their business associates handling protected health "
     "information.", "Grant Compass is not a covered entity or business associate and isn't designed for "
     "protected health information. Don't upload patient-level data; use aggregate figures."),
    ("Gramm-Leach-Bliley Act (GLBA)", "Applies to financial institutions.", "Grant Compass is not a financial "
     "institution and doesn't collect bank, card or donor payment details. Don't upload them."),
    ("CAN-SPAM Act", "Applies to commercial email.", "Grant Compass doesn't send email of any kind."),
    ("State data-breach notification laws (all 50 states, DC and territories)", "Apply to breaches of certain "
     "personal information.", "We store very little personal information (names, work emails, team roles) and "
     "passwords only as salted hashes. If a breach affecting your information occurs, we'll notify you and any "
     "authorities as the applicable state law requires, without unreasonable delay."),
]


def controls():
    slug = session.get("org")
    if not slug:
        return None
    demo = orgs.is_demo(slug)
    return card([
        html.H2("Your data", className="pp-h"),
        html.P(f"You're signed in to {orgs.org_name(slug)}"
               + (" (a demo organisation)." if demo else "."), className="hint"),
        html.Div([
            html.Button("⬇ Download my data", id="pp-export", n_clicks=0, className="btn btn-primary"),
            dcc.Link("Reset this demo", href="/reset-demo", className="btn btn-quiet") if demo else
            dcc.ConfirmDialogProvider(html.Button("Delete my account", className="btn btn-quiet btn-danger"),
                                      id="pp-delete", message="Permanently delete your account and everything "
                                      "stored for your organisation (profile, documents, grants, answers, comments "
                                      "and usage logs)? This can't be undone."),
        ], className="btn-row"),
        html.P("Download gives you everything stored for your organisation as one JSON file." + (
            "" if demo else " Deleting removes your account, your organisation's database and its usage logs from "
                            "this computer immediately."), className="hint"),
        dcc.Download(id="pp-dl"),
    ], className="pp-controls")


def layout():
    return html.Div([
        html.Div([
            html.Div("Privacy policy", className="eyebrow"),
            html.H1("How Grant Compass handles your data"),
            html.P(f"Effective {EFFECTIVE}", className="muted small"),
        ], className="pp-head"),
        html.Div([
            html.Div("In short", className="pp-k"),
            _ul("Your data stays in a database on the computer that runs Grant Compass, one per organisation.",
                "To draft, review and assess, the app sends the relevant text to an AI model (OpenAI's gpt-6-luna "
                "through Portkey). Otherwise only search keywords, requests for public web pages, and a request for the "
                "app's fonts leave it.",
                "No advertising, no analytics, no tracking, no selling or sharing of personal information.",
                "One cookie, to keep you signed in. Passwords are stored only as salted hashes.",
                "You can download all your data or delete your account at any time, below."),
        ], className="pp-summary"),
        controls(),
        _s("1. Who we are and what this covers",
           _p("Grant Compass is a grant research and writing application for nonprofit teams. It runs on your "
              "organisation's own computer or server. This policy covers the data the application stores and the "
              "services it contacts. If your organisation hosts Grant Compass for others, it is responsible for that "
              "deployment and should adapt this policy.")),
        _s("2. Information we collect",
           _ul("Account: your name, work email, organisation name, and a salted hash of your password (never the "
               "password itself).",
               "Organisation profile: mission, programmes, populations served, finances, preferences and other fields "
               "you fill in, or that are filled from your public website when you ask.",
               "Source documents you upload (reports, budgets, past applications) and pages read from your website.",
               "Grant work: opportunities, decisions, application and report answers, versions, comments and "
               "replies, team members' names and roles.",
               "AI usage logs: for each AI run, the agent, model, token counts, cost and duration. These logs do not "
               "contain your text.",
               "A session cookie (see section 6). We don't collect device fingerprints, location or browsing "
               "history.")),
        _s("3. How we use it",
           _p("Only to provide Grant Compass's features: finding and assessing grants, drafting and reviewing "
              "applications and reports, tracking your pipeline, and showing usage and costs. We don't use your "
              "information for advertising, we don't sell or rent it, and we don't use it to train AI models.")),
        _s("4. AI processing",
           _p("When you use an AI feature, the app sends the text that feature needs (for example, a funder's call, "
              "your profile and documents, or your draft answer) to OpenAI's gpt-6-luna model through Portkey, an AI "
              "gateway. Requests may be served by OpenAI or by Microsoft Azure OpenAI. Each provider handles that "
              "data under its own terms; according to their published policies, data sent through their business "
              "APIs is not used to train their models by default. Portkey may cache identical requests to save cost."),
           _p("We limit what's sent: each request carries only the material for that task, inputs over a size limit "
              "are refused, and every run is capped in AI calls and tokens. Funder pages and documents are treated "
              "as data, never as instructions, and the AI cannot change your records except through actions you "
              "take.")),
        _s("5. Other services the app contacts",
           _ul("Grants.gov and the California Grants Portal (public government APIs): only search keywords, such "
               "as “literacy”, are sent.",
               "Funder websites and your organisation's website, when Discover checks them or you ask the app to read "
               "a page. The app respects each site's robots.txt rules.",
               "Google Fonts, which supplies the app's typefaces; your browser's request shares your IP address with "
               "Google.",
               "No other third parties: no analytics, advertising, social media or tracking services.")),
        _s("6. Cookies and tracking",
           _p("Grant Compass sets one cookie, a signed session cookie that keeps you signed in for up to 14 days. "
              "There are no analytics, advertising or tracking cookies. Because we don't track you, there is nothing "
              "to opt out of: Do Not Track and Global Privacy Control signals are respected by default.")),
        _s("7. Where your data is stored, and how it's protected",
           _ul("Each organisation has its own database file; organisations never share one, and the app keeps every "
               "request scoped to the signed-in organisation.",
               "Passwords are stored as salted scrypt hashes. Sessions are signed with a key generated on your "
               "computer.",
               "Data is stored on the computer running the app. Protect it as you would other organisational "
               "records: keep it updated, use disk encryption, and if you host the app on a network, serve it over "
               "HTTPS.",
               "No system is perfectly secure, but we keep personal information to a minimum so there is little to "
               "expose.")),
        _s("8. How long we keep it",
           _p("Until you delete it. You can delete individual documents, grants, questions and comments at any time; "
              "deleting your account (above) removes everything stored for your organisation. Demo organisations "
              "can be reset to their original sample data.")),
        _s("9. Your rights and choices",
           _ul("Access and portability: Download my data gives you everything in a machine-readable JSON file.",
               "Correction: you can edit your profile, documents, grants, answers and team at any time.",
               "Deletion: Delete my account removes your account and your organisation's data.",
               "No sale, no targeted advertising, no profiling: there is nothing to opt out of.",
               f"Questions or requests: email {CONTACT}. We respond within 45 days, as most state privacy laws "
               "require, and won't treat you differently for exercising your rights.")),
        _s("10. Information you shouldn't upload",
           _p("Grant Compass is built for organisational information, not sensitive personal data. Please don't upload "
              "Social Security numbers, bank or card details, donors' payment information, patients' health "
              "information, identifiable student records, or personal details about the children or clients you "
              "serve. Use aggregate figures instead (for example, “612 students, 88% low-income”).")),
        _s("11. How this policy meets US privacy law",
           _p("The United States has no single federal privacy law; obligations come from federal laws for specific "
              "kinds of data and from state laws. Here is how each relevant law applies to Grant Compass, and how we "
              "meet it."),
           html.Table([html.Thead(html.Tr([html.Th("Law"), html.Th("When it applies"), html.Th("How Grant Compass "
                                                                                                  "meets it")])),
                       html.Tbody([html.Tr([html.Td(a), html.Td(b), html.Td(c)]) for a, b, c in LAWS])],
                      className="pp-table")),
        _s("12. Changes to this policy",
           _p("If we change how data is handled, we'll update this page and its effective date before the change "
              "takes effect.")),
        _s("13. Contact", _p(f"Privacy questions and requests: {CONTACT}.")),
        html.P("This policy describes how Grant Compass handles data. It is not legal advice; an organisation deploying "
               "Grant Compass should have its counsel review it against its own obligations.",
               className="pp-note"),
    ], className="privacy")


@callback(Output("pp-dl", "data"), Input("pp-export", "n_clicks"), prevent_initial_call=True)
def download_data(n):
    if not n or not session.get("org"):
        raise PreventUpdate
    data = orgs.export_data(session["org"])
    return dcc.send_string(json.dumps(data, indent=2, default=str),
                           f"grant-compass-data-{session['org']}-{date.today()}.json", type="application/json")


@callback(Output("url", "pathname", allow_duplicate=True), Input("pp-delete", "submit_n_clicks"),
          prevent_initial_call=True)
def delete_my_account(n):
    if not n or not session.get("org"):
        raise PreventUpdate
    orgs.delete_account(session["org"])
    session.clear()
    return "/login"

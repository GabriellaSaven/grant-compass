"""Small building blocks shared by every page."""

import re
from datetime import date

from dash import dcc, html

HEALTH_CLASS = {"On Track": "ok", "Needs Attention": "attn", "At Risk": "risk", "Critical": "crit"}
REC_CLASS = {"Go": "ok", "Research further": "attn", "No-Go": "crit"}
EVIDENCE_CLASS = {"supported": "ok", "inferred": "attn", "missing": "crit"}
EVIDENCE_LABEL = {"supported": "Supported", "inferred": "Inferred", "missing": "Missing"}


FIT_BANDS = ((70, "ok", "Good fit"), (40, "attn", "Medium fit"), (0, "crit", "Poor fit"))
FIT_LEGEND = "Fit colours: green 70% and up, yellow 40–69%, red under 40%."


def fit_class(score: int | None) -> str:
    """Colour a fit % by how good the fit is: green (70+), yellow (40-69), red (under 40)."""
    if score is None:
        return "muted"
    return next(cls for floor, cls, _ in FIT_BANDS if score >= floor)


SHORT_DIMENSION = {"mission_alignment": "Mission", "geographic_eligibility": "Geography",
                   "population_fit": "Population", "funding_amount": "Funding size",
                   "strategic_alignment": "Strategy", "evidence_readiness": "Evidence", "application_effort": "Effort"}
FIT_COLOUR = {"ok": "#3f7d5a", "attn": "#c4952f", "crit": "#b4473c", "muted": "#b9b9b0"}


def fit_visual(r: dict, size: str = "lg"):
    """The fit % as a dial that fills, plus one small bar per dimension (green 4-5, yellow 3, red 1-2)."""
    fit = r.get("fit_score")
    band = fit_class(fit)
    dial = html.Div([
        html.Div([html.Span(str(fit) if fit is not None else "—", className="count-up dial-num",
                            **({"data-to": str(fit)} if fit is not None else {})),
                  html.Span("%" if fit is not None else "", className="dial-pct")], className="dial-inner"),
    ], className=f"dial dial-{size}", title=FIT_LEGEND,
        style={"--target": fit or 0, "--colour": FIT_COLOUR[band]})

    weights = r.get("weights") or {}

    def bar(d):
        """One dimension: a bar you can open for the reasoning, the quotes and how much it counts."""
        score = d.get("score")
        tone = "muted" if not score else "ok" if score >= 4 else "attn" if score == 3 else "crit"
        quotes = []
        if d.get("funder_quote"):
            quotes.append(html.Div([html.Span("Funder: ", className="quote-who"), f"“{d['funder_quote']}”"],
                                   className="quote"))
        if d.get("org_quote"):
            quotes.append(html.Div([html.Span(f"{d.get('org_source') or 'Your documents'}: ", className="quote-who"),
                                    f"“{d['org_quote']}”"], className="quote"))
        weight = weights.get(d["key"])
        ev = d.get("evidence")
        return html.Details([
            html.Summary([
                html.Span(SHORT_DIMENSION.get(d["key"], d["key"]), className="db-name"),
                html.Div(html.Div(className=f"db-fill db-{tone}", style={"width": f"{(score or 0) * 20}%"}),
                         className="db-track"),
                html.Span(f"{score}/5" if score else "?", className="db-score"),
            ], className="db-row"),
            html.Div([
                html.Div([label(EVIDENCE_LABEL[ev], EVIDENCE_CLASS[ev]) if ev in EVIDENCE_LABEL else None,
                          html.Span(f"counts {weight}% of fit" if weight else "shown, not counted in fit",
                                    className="db-weight")], className="db-meta"),
                html.P(d.get("rationale") or ""), *quotes,
            ], className="db-body"),
        ], className="db-item")
    return html.Div([
        html.Div([dial, html.Div("Fit", className="dial-cap")], className="dial-wrap"),
        html.Div([*[bar(d) for d in r.get("dimensions") or []],
                  html.Div("Each bar is scored 1–5 from the evidence; fit is their weighted average, with unknowns "
                           "left out. Click a bar for the reasoning and quotes.", className="db-hint")],
                 className="dim-bars"),
    ], className=f"fit-visual fv-{size}")


def modal(prefix: str):
    """A centred pop-up: {prefix}-modal (add class 'open' to show), -body for content, -close and -backdrop to shut."""
    return html.Div(
        [
            html.Div(id=f"{prefix}-modal-backdrop", className="modal-backdrop", n_clicks=0),
            html.Div([html.Button("×", id=f"{prefix}-modal-close", className="modal-close", title="Close (Esc)"),
                      html.Div(id=f"{prefix}-modal-body")], className="modal-panel", role="dialog"),
        ],
        id=f"{prefix}-modal", className="modal",
    )


def profile_tabs(active: str):
    """Switch between the two halves of the organisation's profile."""
    return html.Div(
        [dcc.Link(label, href=href, className="ptab" + (" on" if href == active else ""))
         for label, href in (("Edit profile", "/profile"), ("Source documents", "/profile/documents"),
                             ("Team", "/profile/team"), ("Agent health", "/profile/health"))],
        className="ptabs",
    )


def page_header(title: str, subtitle: str = "", actions=None):
    return html.Div(
        [html.Div([html.H1(title), html.P(subtitle, className="lede") if subtitle else None]), actions],
        className="page-header",
    )


def label(text: str, kind: str):
    """A quiet status label: coloured dot + text."""
    return html.Span([html.Span(className="dot"), text], className=f"label label-{kind}")


def health_label(h: str):
    return label(h, HEALTH_CLASS.get(h, "muted"))


def money(n: int | None) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"${n / 1_000_000:,.2f}".rstrip("0").rstrip(".") + "M"
    return f"${n / 1000:,.0f}k" if n >= 10_000 else f"${n:,}"


def award_range(opp: dict) -> str:
    lo, hi = opp.get("award_min"), opp.get("award_max")
    lo = lo if lo and lo >= 100 else None  # Grants.gov often lists a $1 "floor", which only means "no minimum"
    if lo and hi:
        return money(hi) if lo == hi else f"{money(lo)}–{money(hi)}"
    if hi:
        return f"Up to {money(hi)}"
    text = (opp.get("award_text") or "").strip()
    if not text or text.lower().startswith("not stated"):
        return "Not stated"
    return text if len(text) <= 22 else "See details"  # a funder's sentence won't fit a table cell


def award_full(opp: dict) -> str:
    """The funder's own words about the award, for a hover."""
    return opp.get("award_text") or award_range(opp)


def days_text(days: int | None) -> str:
    if days is None:
        return "No fixed date"
    if days < 0:
        return f"{-days} days ago"
    if days == 0:
        return "Due today"
    return f"{days} day{'s' if days != 1 else ''}"


_MONTH_DAY = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b")


def deadline_text(opp: dict) -> str:
    """A short deadline label that fits a table cell. Funders without a fixed date often describe their
    timing in a whole sentence; that becomes 'Rolling', 'Closed', 'Feb 1 & Aug 1' or 'See details'."""
    if opp.get("deadline"):
        return date.fromisoformat(opp["deadline"]).strftime("%-d %b %Y")
    text = (opp.get("deadline_text") or "").strip()
    low = text.lower()
    if not text or low.startswith("not stated"):
        return "Not stated"
    if re.search(r"currently closed|applications? (?:are )?closed|not (?:currently )?accepting", low):
        return "Closed"
    if re.search(r"rolling|throughout the year|year[- ]round|ongoing|any ?time|always open|no (?:fixed )?deadline", low):
        return "Rolling"
    dates = [f"{m} {d}" for m, d in _MONTH_DAY.findall(text)]
    if dates:
        return " & ".join(dict.fromkeys(dates[:2]))
    return text if len(text) <= 24 else "See details"


def deadline_full(opp: dict) -> str:
    """The funder's own words about the deadline, for a hover or details view."""
    return opp.get("deadline_text") or deadline_text(opp)


def progress_bar(pct: int):
    return html.Div(
        [html.Div(className="bar", children=html.Div(className="bar-fill", style={"width": f"{pct}%"})),
         html.Span(f"{pct}%", className="bar-num")],
        className="progress",
    )


def stat(value, caption: str, kind: str = ""):
    return html.Div([html.Div(value, className="stat-value"), html.Div(caption, className="stat-caption")],
                    className=f"stat {kind}")


def copy_action(text: str, label: str = "Copy"):
    """Icon + word; a click on either copies (assets/menu.js passes a click on the word to the icon)."""
    return html.Span([dcc.Clipboard(content=text, className="ans-copy-icon"), html.Span(label)],
                     className="ans-act ans-copy", title="Copy to clipboard", role="button", tabIndex="0")


def card(children, className: str = ""):
    return html.Div(children, className=f"card {className}".strip())


def section_title(text: str, aside=None):
    return html.Div([html.H2(text), aside], className="section-title")


def empty(text: str):
    return html.P(text, className="empty-note")


def link(text: str, href: str, className: str = ""):
    return dcc.Link(text, href=href, className=className)


def usage_line(usage: dict):
    cost = f"${usage['cost_usd']:.4f}" if usage.get("cost_usd") is not None else "cost not recorded"
    return html.Div(
        [
            html.Span("AI usage", className="usage-title"),
            html.Span(f"{usage['input_tokens']:,} input tokens"),
            html.Span(f"{usage['cached_input_tokens']:,} cached"),
            html.Span(f"{usage['output_tokens']:,} output"),
            html.Span(cost),
        ],
        className="usage",
    )

"""'Why this fit %?': the arithmetic behind a fit score, so a user can see why it is 75% and not 82%."""

from dash import html

from ..fit import fit_breakdown


def _1(x: float) -> str:
    """One decimal, halves rounded up (11.25 -> 11.3), so the rows visibly add up to the total."""
    return f"{x + 1e-9:.1f}"


def fit_summary_text(result: dict) -> str:
    """One line for hover tooltips."""
    b = fit_breakdown(result)
    if b["total"] is None:
        return "Not enough information to score fit."
    gaps = "; ".join(f"{g['label']} {g['score']}/5 (−{_1(g['lost'])})" for g in b["biggest_gaps"])
    return f"Fit {b['total']}%. Points lost mostly on: {gaps}." if gaps else f"Fit {b['total']}%: full marks."


def fit_explainer(result: dict):
    """Table of points per dimension, the biggest gaps, and how the number is computed."""
    b = fit_breakdown(result)
    if b["total"] is None:
        return html.Div("No dimensions could be scored, so there is no fit %.", className="small muted")
    rows = [
        html.Div([
            html.Span(r["label"], className="fx-name"),
            html.Span(f"{r['score']}/5", className="fx-score"),
            html.Div(className="fx-bar", children=html.Div(className="fx-fill",
                                                           style={"width": f"{100 * r['points'] / r['max']:.0f}%"})),
            html.Span(f"{_1(r['points'])} of {_1(r['max'])}", className="fx-pts"),
        ], className="fx-row")
        for r in b["rows"]
    ]
    gaps = b["biggest_gaps"]
    return html.Div([
        html.Div(f"Why {b['total']}%", className="fx-h"),
        html.Div([html.Span("Name", className="fx-name k"), html.Span("Score", className="fx-score k"),
                  html.Span("", className="fx-bar-h"), html.Span("Points", className="fx-pts k")],
                 className="fx-row fx-head"),
        *rows,
        html.Div([html.Span("Total", className="fx-name strong"), html.Span(""), html.Span(""),
                  html.Span(f"{b['total']} of 100", className="fx-pts strong")], className="fx-row fx-total"),
        html.Div(["Points lost mostly on ",
                  ", ".join(f"{g['label'].lower()} ({g['score']}/5, −{_1(g['lost'])})" for g in gaps), "."],
                 className="fx-gaps") if gaps else html.Div("Full marks on every scored dimension.", className="fx-gaps"),
        html.Div(f"Left out because there was no information to judge: {', '.join(b['unknown'])}. Their weight is "
                 "shared across the scored dimensions instead of being guessed.", className="fx-note")
        if b["unknown"] else None,
        html.Div("Application effort is shown separately and is not part of fit.", className="fx-note"),
        html.Div("How it's calculated: each dimension's share of 100 is its weight divided by the total weight "
                 "scored; a dimension earns (score − 1) ÷ 4 of its share, so 5/5 earns all of it and 1/5 earns none.",
                 className="fx-note"),
    ], className="fx")

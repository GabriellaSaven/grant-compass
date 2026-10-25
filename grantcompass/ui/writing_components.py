"""Display pieces for the writing tools in the application workspace."""

import re

from dash import html

from .. import db
from .components import empty, label, usage_line

CLAIM_CLASS = {"Supported": "ok", "Weakly supported": "attn", "Needs evidence": "risk", "Contradicted": "crit"}
PART_CLASS = {"Yes": "ok", "Partly": "attn", "No": "crit"}
STOP = set("the a an and or of to in on for with your you our we is are be how what why who which this that "
           "does do will would describe explain please provide any their it as by at from".split())


def q(text: str) -> str:
    """Wrap in curly quotes once, even if the stored text already has them."""
    return "“" + (text or "").strip().strip('"\u201c\u201d').strip() + "”"


def length_label(length: dict):
    return label(length["label"], "ok" if length["ok"] else "crit")


def with_placeholders(text: str):
    """Render text with [MISSING: …] placeholders highlighted."""
    parts = re.split(r"(\[MISSING:[^\]]*\])", text or "")
    return [html.Mark(p, className="missing-mark") if p.startswith("[MISSING:") else p for p in parts]


def source_snippets(prompt: str, limit: int = 6):
    """Library passages that share words with the question. Plain keyword overlap, no AI."""
    words = {w for w in re.findall(r"[a-z][a-z\-]+", prompt.lower()) if w not in STOP and len(w) > 3}
    scored = []
    for d in db.list_documents():
        for para in [p.strip() for p in re.split(r"\n\s*\n|\n(?=[-#])", d["content"]) if len(p.strip()) > 40]:
            hits = sum(1 for w in words if w[:6] in para.lower())
            if hits:
                scored.append((hits + (2 if d["approved"] else 0), d, para))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return empty("No library passages share words with this question.")
    return [
        html.Div([html.Div([html.Span(d["title"], className="snip-title"),
                            html.Span("Approved language", className="tag tag-approved") if d["approved"] else None],
                           className="snip-head"),
                  html.Div(para[:420] + ("…" if len(para) > 420 else ""), className="snip-text")],
                 className="snip")
        for _, d, para in scored[:limit]
    ]


def stale_note(review: dict, current: str):
    if review and review.get("response_text", "").strip() != (current or "").strip():
        return html.Div("Based on an earlier version of your answer. Run again to review the current text.",
                        className="alert alert-attn small")
    return None


def draft_notes(review: dict | None):
    """Shown under the editor after Draft with AI: what is still missing and where each fact came from."""
    if not review:
        return None
    r = review["result"]
    sources = [
        html.Li([
            html.Span(s["claim"]), html.Span(" — "),
            html.Details([html.Summary(s["source_title"] or "No source", className="src-link"),
                          html.Div(s.get("context") or s["source_quote"], className="src-context")],
                         className="src-inline"),
            html.Span(" ✓" if s["verified"] else " (quote not found)",
                      className="ok-text" if s["verified"] else "error-text"),
        ])
        for s in r["sources"]
    ]
    n = len(r["placeholders"])
    return html.Div([
        html.Div([html.Span("AI draft", className="draft-notes-h"), length_label(r["length"]),
                  label(f"{n} missing fact{'s' if n != 1 else ''}" + (" — fill the [MISSING: …] items" if n else ""),
                        "attn" if n else "ok")], className="pill-row"),
        html.Details([html.Summary(f"Where each fact comes from ({len(sources)})", className="toggle"),
                      html.Ul(sources, className="src-list") if sources else empty("No factual claims.")],
                     className="block"),
        html.Details([html.Summary("Missing from your Profile and documents", className="toggle"),
                      html.Ul([html.Li(m) for m in r["missing"]])], className="block") if r["missing"] else None,
        usage_line(review["usage"]),
    ], className="draft-notes")


def _find(text: str, quote: str) -> int:
    """Where a coach quote sits in the current text (exact, then ignoring case); -1 if it's gone."""
    if not quote:
        return -1
    i = text.find(quote)
    return i if i >= 0 else text.lower().find(quote.lower())


def _active(issues: list[dict], state: dict | None) -> list[dict]:
    from ..writing import ensure_fix

    issues = [ensure_fix(it) if it.get("quote") else it for it in issues]
    state = state or {}
    done = set(state.get("dismissed", [])) | set(state.get("applied", []))
    return [it for it in issues if it["id"] not in done]


def _suggestion(it: dict):
    """What accepting would do: the new wording, or 'Remove' with the words struck through."""
    if it.get("action") == "remove":
        return html.Span([html.Span("Suggested: remove ", className="muted"),
                          html.Span(it["quote"], className="ba-before")], className="ba")
    return html.Span([html.Span("Suggested: ", className="muted"),
                      html.Span(with_placeholders(it["replacement"]), className="ba-after")], className="ba")


def _acceptable(it: dict) -> bool:
    return bool(it.get("quote")) and (it.get("action") == "remove" or bool(it.get("replacement")))


TYPE_HELP = {
    "answer": "Answer the question: part of what the funder asked isn't answered directly.",
    "evidence": "Evidence: a claim needs proof, such as a number, result or source.",
    "specificity": "Be specific: vague wording that a concrete detail would make stronger.",
    "outcomes": "Outcomes: say what changes for people, not only what you do.",
    "funder": "Funder fit: connect this to what this funder says it cares about.",
    "clarity": "Clarity: hard to follow; a simpler sentence would read better.",
    "repetition": "Repetition: says something already said elsewhere in the answer.",
    "jargon": "Plain language: insider terms a reviewer may not know.",
    "missing": "Missing information: a fact the answer needs that isn't in your documents yet.",
}
SEVERITY_HELP = {
    "high": "High: likely to cost points with reviewers. Fix before you submit.",
    "medium": "Medium: worth improving if you have time.",
    "low": "Low: polish. Optional.",
}


def _chips(it: dict):
    """The kind of problem and how much it matters, each with a plain explanation on hover."""
    from ..models import ISSUE_TYPES

    return [html.Span(ISSUE_TYPES.get(it["type"], it["type"]), className=f"type-chip t-{it['type']}",
                      title=TYPE_HELP.get(it["type"], "")),
            html.Span(it["severity"].capitalize(), className=f"sev-chip sev-{it['severity']}",
                      title=SEVERITY_HELP.get(it["severity"], ""))]


def _hover_card(it: dict, editable: bool):
    """The Grammarly-style card that appears when you hover a highlight."""
    from ..models import ISSUE_TYPES

    return html.Span([
        html.Button("×", className="hl-close", title="Close"),
        html.Span(_chips(it), className="issue-top"),
        html.Span(it["title"], className="issue-title"),
        html.Span(it["explanation"], className="issue-why"),
        _suggestion(it) if _acceptable(it) else None,
        html.Span([
            html.Button("✓ Accept", id={"type": "ws-apply-pop", "i": it["id"]}, n_clicks=0,
                        className="btn btn-primary btn-small") if _acceptable(it) else None,
            html.Button("✕ Reject", id={"type": "ws-dismiss-pop", "i": it["id"]}, n_clicks=0,
                        className="btn btn-quiet btn-small"),
        ], className="btn-row tight") if editable else None,
    ], className=f"hl-card t-{it['type']}")


def highlight_view(text: str, review: dict | None, state: dict | None = None, editable: bool = False):
    """The answer with each open issue underlined in its type's colour, like Grammarly. Click a highlight to
    open its suggestion card on the spot (opening and closing is handled in the browser, see assets/menu.js)."""
    text = text or ""
    if not text.strip():
        return empty("Nothing to review yet.")
    issues = _active((review or {}).get("result", {}).get("issues", []), state) if review else []
    focus = (state or {}).get("focus")
    spans = []
    for it in issues:
        i = _find(text, it["quote"])
        if i >= 0:
            spans.append((i, i + len(it["quote"]), it))
    spans.sort(key=lambda s: s[0])
    out, pos = [], 0

    def plain(chunk):
        parts = chunk.split("\n")
        for k, p in enumerate(parts):
            if k:
                out.append(html.Br())
            if p:
                out.append(p)

    for a, b, it in spans:
        if a < pos:  # overlapping highlight: keep the first
            continue
        plain(text[pos:a])
        out.append(html.Span([
            html.Mark(text[a:b], className=f"hl hl-{it['type']} sev-{it['severity']}",
                      style={"--i": len(out)}),  # highlights appear one after another
            _hover_card(it, editable),
        ], className="hl-wrap"))
        pos = b
    plain(text[pos:])
    return html.Div(out, className="review-text")


SCORE_BANDS = ((80, "Strong", "ok"), (60, "Getting there", "attn"), (0, "Needs work", "crit"))
TYPE_ORDER = {"high": 0, "medium": 1, "low": 2}


def _band(score: int):
    return next((label_, cls) for floor, label_, cls in SCORE_BANDS if score >= floor)


def _score_ring(score: int):
    label_, cls = _band(score)
    color = {"ok": "var(--ok)", "attn": "var(--attn)", "crit": "var(--crit)"}[cls]
    return html.Div([
        html.Div(html.Div([html.Div(str(score), className="ring-num count-up", **{"data-to": str(score)}),
                           html.Div("/100", className="ring-of")], className="ring-inner"),
                 className="ring", style={"--target": score, "--colour": color}),
        html.Div([html.Div(label_, className=f"ring-label rec-{cls}"),
                  html.Div("Overall score from ten weighted categories", className="small muted")]),
    ], className="ring-row")


def _issue_card(it: dict, text: str, focus, editable: bool):
    from ..models import ISSUE_TYPES

    found = not it["quote"] or _find(text, it["quote"]) >= 0
    before_after = None
    if it["quote"]:
        before_after = html.Div([
            html.Span(it["quote"], className="ba-before"),
            html.Span(" → ", className="muted"),
            html.Span(with_placeholders(it["replacement"]), className="ba-after") if it.get("action") != "remove"
            else html.Span("(remove)", className="muted"),
        ], className="ba")
    actions = []
    if editable and found:
        if _acceptable(it):
            actions.append(html.Button("✓ Accept", id={"type": "ws-apply", "i": it["id"]}, n_clicks=0,
                                       className="btn btn-primary btn-small"))
        actions.append(html.Button("✕ Reject", id={"type": "ws-dismiss", "i": it["id"]}, n_clicks=0,
                                   className="btn btn-quiet btn-small"))
    return html.Div([
        html.Div(_chips(it), className="issue-top"),
        html.Div(it["title"], className="issue-title"),
        before_after,
        html.Div(it["explanation"], className="issue-why"),
        html.Div("The text this refers to has changed.", className="small muted") if not found else None,
        html.Div(actions, className="btn-row tight") if actions else None,
    ], id={"type": "ws-card", "i": it["id"]},
        className=f"issue t-{it['type']}" + (" focus" if it["id"] == focus else "") + ("" if found else " stale"))


def render_coach(review: dict | None, current: str, state: dict | None = None, editable: bool = False):
    """VMock-style score card + Grammarly-style suggestion cards."""
    if not review:
        return empty("Open Review suggestions above your answer and the Coach reviews it by itself: whether you "
                     "answered every part of the question, scores for ten areas, and specific words to improve. "
                     "Nothing changes unless you accept it.")
    r = review["result"]
    current = current or ""
    issues = sorted(_active(r.get("issues", []), state), key=lambda it: TYPE_ORDER[it["severity"]])
    applied, dismissed = len((state or {}).get("applied", [])), len((state or {}).get("dismissed", []))
    part_icon = {"Yes": ("✓", "ok"), "Partly": ("◐", "attn"), "No": ("✕", "crit")}

    def cat_chip(c):
        sc = c["score"] or 0
        cls = "ok" if sc >= 8 else "attn" if sc >= 5 else "crit"
        return html.Div([html.Span(c["label"], className="cat-chip-name"), html.Span(f"{sc}/10", className="cat-chip-score")],
                        className=f"cat-chip c-{cls}", title=c["comment"])

    return html.Div([
        stale_note(review, current),
        _score_ring(r["overall"]),
        html.Div([length_label(r["length"]),
                  html.Span(f"{len(issues)} suggestion{'s' if len(issues) != 1 else ''} to review"
                            + (f" · {applied} accepted" if applied else "") + (f" · {dismissed} rejected" if dismissed else ""),
                            className="small muted")], className="pill-row"),
        html.Div([html.Strong("Start here: "), r["top_priority"]], className="priority"),
        html.H4("Does it answer the question?"),
        html.Div([
            html.Div([html.Span(part_icon[p["addressed"]][0], className=f"part-icon rec-{part_icon[p['addressed']][1]}"),
                      html.Div([html.Div(p["part"], className="part-name"),
                                html.Div(p["note"], className="small muted") if p["note"] and p["addressed"] != "Yes" else None])],
                     className="check-row")
            for p in r["question_parts"]
        ], className="checklist"),
        html.H4(f"Suggestions ({len(issues)})"),
        html.P("Highlighted in your answer: click a highlight to see its suggestion there. Accept puts the wording "
               "into the editor (Undo reverses it); Reject hides it. Each card names the kind of problem and how much it "
               "matters: High = fix before you submit, Medium = worth improving, Low = polish. Hover a label for "
               "more.", className="hint") if editable else None,
        *([_issue_card(it, current, (state or {}).get("focus"), editable) for it in issues]
          or [html.Div("No open suggestions. Run the review again after editing.", className="small muted")]),
        html.Details([html.Summary("Scores by area", className="toggle"),
                      html.Div([cat_chip(c) for c in r["categories"]], className="cat-grid"),
                      html.P("Hover a score for the reason. Overall is the weighted average, minus 10 if over the "
                             "limit.", className="hint")], className="block", open=True),
        html.Details([html.Summary("What's working", className="toggle"),
                      html.Ul([html.Li(s["point"]) for s in r["strengths"]] or [html.Li("Nothing yet.")])],
                     className="block"),
        usage_line(review["usage"]),
    ], className="coach-v2")


def render_evidence(review: dict | None, current: str):
    if not review:
        return empty("The Evidence Checker lists every claim in your answer and checks it against your Organisation "
                     "Library: Supported, Weakly supported, Needs evidence or Contradicted.")
    r = review["result"]
    counts = html.Div([label(f"{n} {s}", CLAIM_CLASS[s]) for s, n in r["counts"].items() if n], className="pill-row")
    claims = [
        html.Div([
            html.Div([label(c["status"], CLAIM_CLASS[c["status"]])]),
            html.Div(q(c["claim"]), className="claim-text"),
            html.Div(c["note"], className="small muted"),
            html.Details([html.Summary(f"Source: {c['source_title']}", className="src-link"),
                          html.Div(c["context"], className="src-context")], className="block")
            if c.get("context") else None,
        ], className="claim")
        for c in r["claims"]
    ]
    return html.Div([stale_note(review, current), counts, *(claims or [empty("No factual claims found.")]),
                     usage_line(review["usage"])])

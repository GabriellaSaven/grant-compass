"""Fit Agent: assesses one opportunity against the Organisation Library and
recommends Go / Research further / No-Go.

The model scores seven dimensions with evidence; the app, not the model,
turns those into the fit percentage using the weights below, so the number is
always explainable. Code then applies two guards the model cannot override:
an eligibility gate, and a word-for-word check of every quote (unverified
"supported" evidence is downgraded to "inferred")."""

import json
import re
from datetime import date

from .config import MAX_INPUT_CHARS, PROMPTS_DIR
from .library import library_context
from .llm import log_run, run_agent, usage_dict
from .models import DIMENSIONS, GO_NO_GO_QUESTIONS, FitAssessment

INSTRUCTIONS = (PROMPTS_DIR / "fit_agent.md").read_text(encoding="utf-8")

# How much each dimension counts toward fit. Application effort is reported
# separately (it is a cost, not a measure of fit).
WEIGHTS = {
    "mission_alignment": 25,
    "geographic_eligibility": 15,
    "population_fit": 15,
    "strategic_alignment": 15,
    "evidence_readiness": 15,
    "funding_amount": 15,
}


# --- Quote checking ---------------------------------------------------------------
def _normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip(" .\"'")


def quote_found(quote: str, source: str) -> bool:
    """True if the quote (ignoring case, whitespace and curly quotes) appears in the source.
    Quotes the model trimmed with '...', or built from separate lines (e.g. three fields of the profile form),
    pass if every piece appears word for word."""
    if not quote.strip():
        return True
    src = _normalize(source)
    return all(_normalize(p) in src for p in re.split(r"\.\.\.|…|\n", quote) if _normalize(p))


# --- Scoring ------------------------------------------------------------------------
def fit_score(dimensions: list[dict]) -> int | None:
    """Weighted average of the scored dimensions, as 0-100. Unknown dimensions are left out."""
    known = [(WEIGHTS[d["key"]], d["score"]) for d in dimensions if d["key"] in WEIGHTS and d["score"]]
    if not known:
        return None
    total = sum(w for w, _ in known)
    return round(sum(w * (s - 1) / 4 for w, s in known) / total * 100)


def rescore(result: dict) -> dict:
    """Bring a stored assessment up to the current dimensions, questions and weights
    (e.g. after a dimension is retired). No AI call: the fit % is recomputed in code."""
    result["dimensions"] = [d for d in result["dimensions"] if d["key"] in DIMENSIONS]
    result["checks"] = [c for c in result["checks"] if c["question"] in GO_NO_GO_QUESTIONS]
    result["fit_score"] = fit_score(result["dimensions"])
    result["weights"] = WEIGHTS
    return result


def refresh_stored() -> int:
    """Rescore every saved assessment. Safe to run on every start."""
    from . import db

    changed = 0
    with db.connect() as conn:
        for table, key in (("assessments", "id"), ("lead_assessments", "source_id")):
            for row in conn.execute(f"SELECT {key}, result FROM {table}").fetchall():
                old = json.loads(row["result"])
                new = rescore(json.loads(row["result"]))
                if new != old:
                    conn.execute(f"UPDATE {table} SET result = ? WHERE {key} = ?", (json.dumps(new), row[key]))
                    changed += 1
    return changed


def reverify_stored() -> int:
    """Re-check quotes in assessments saved before the current check, wherever the funder text is still
    stored: saved grants, and results from the foundation directory. (Grants.gov search results don't keep
    their full text, so they keep their old check and are left out of the Agent health quote figure.)
    Evidence levels aren't raised: a dimension downgraded to Inferred stays that way until re-assessed."""
    from . import db
    from .watchlist import to_lead
    from .library import library_context
    from .triage import lead_to_opportunity

    try:
        _, docs = library_context()
    except ValueError:
        return 0  # nothing in the library yet, so nothing was assessed
    directory = {f"dir:{r['n']}": r for r in db.list_directory() if r.get("result")}
    changed = 0
    with db.connect() as conn:
        for table, key in (("assessments", "opportunity_id"), ("lead_assessments", "source_id")):
            id_col = "id" if table == "assessments" else "source_id"
            for row in conn.execute(f"SELECT {id_col} AS rid, {key} AS ref, result FROM {table}").fetchall():
                result = json.loads(row["result"])
                if result.get("quote_check") == QUOTE_CHECK:
                    continue
                if table == "assessments":
                    opp = db.get_opportunity(row["ref"])
                elif row["ref"] in directory:
                    d = directory[row["ref"]]
                    opp = lead_to_opportunity(to_lead(d, d["result"], "Foundation directory", row["ref"]))
                else:
                    continue
                if not opp:
                    continue
                result["quote_warnings"] = _check_quotes(result, _funder_material(opp), docs)
                conn.execute(f"UPDATE {table} SET result = ? WHERE {id_col} = ?", (json.dumps(result), row["rid"]))
                changed += 1
    return changed


def fit_breakdown(result: dict) -> dict:
    """How the fit % adds up: each scored dimension's points out of its maximum share.
    Matches fit_score(): points = weight * (score - 1) / 4, as a share of the total weight scored."""
    dims = result["dimensions"]
    weights = result.get("weights") or WEIGHTS
    known = [d for d in dims if d["key"] in weights and d["score"]]
    total_w = sum(weights[d["key"]] for d in known)
    rows = []
    for d in known:
        share = 100 * weights[d["key"]] / total_w
        pts = share * (d["score"] - 1) / 4
        rows.append({"key": d["key"], "label": DIMENSIONS[d["key"]], "score": d["score"], "weight": weights[d["key"]],
                     "points": pts, "max": share, "lost": share - pts})
    unknown = [DIMENSIONS[d["key"]] for d in dims if d["key"] in weights and not d["score"]]
    effort = next((d for d in dims if d["key"] == "application_effort"), None)
    return {"rows": rows, "total": round(sum(r["points"] for r in rows)) if rows else None, "unknown": unknown,
            "effort": effort["score"] if effort else None,
            "biggest_gaps": sorted([r for r in rows if r["lost"] >= 0.5], key=lambda r: -r["lost"])[:3]}


def _complete(result: FitAssessment) -> dict:
    """Exactly one entry per dimension and per question, in a fixed order."""
    out = result.model_dump()
    dims = {d["key"]: d for d in out["dimensions"]}
    out["dimensions"] = [
        dims.get(k) or {"key": k, "score": None, "rationale": "Not assessed.", "evidence": "missing",
                        "funder_quote": "", "org_source": "", "org_quote": ""}
        for k in DIMENSIONS
    ]
    checks = {c["question"].strip().lower(): c for c in out["checks"]}
    out["checks"] = [
        checks.get(q.lower()) or {"question": q, "answer": "Unknown", "explanation": "Not assessed."}
        for q in GO_NO_GO_QUESTIONS
    ]
    return out


# A "quote" that only says the text is silent ("Award amounts are not stated…") is a note, not a quote.
NO_QUOTE = re.compile(r"\bnot (?:stated|specified|mentioned|given|provided|listed)\b", re.I)

# Version of the quote check. 3 = also accepts quotes made of separate verbatim lines, and treats "not stated"
# notes as no quote. 2 = funder quotes checked against everything the agent was shown (the extracted
# facts and the full text). Version 1 checked the full text only and wrongly flagged quotes taken from the facts.
QUOTE_CHECK = 3


def _check_quotes(out: dict, funder_text: str, docs: dict[str, str]) -> list[str]:
    """Mark each dimension's quotes as verified or not; return the warnings."""
    warnings = []
    for d in out["dimensions"]:
        label = DIMENSIONS[d["key"]]
        d["quote_verified"] = True
        if d.get("funder_quote") and NO_QUOTE.search(d["funder_quote"]) and not quote_found(d["funder_quote"], funder_text):
            d["funder_quote"] = ""  # the agent described a gap rather than quoting; nothing to verify
        if d.get("funder_quote") and not quote_found(d["funder_quote"], funder_text):
            warnings.append(f"{label}: the funder quote is not in the funder text.")
            d["quote_verified"] = False
        if d.get("org_quote"):
            source = docs.get(d.get("org_source")) or "\n".join(docs.values())
            if not quote_found(d["org_quote"], source):
                warnings.append(f"{label}: the quoted evidence is not in “{d.get('org_source') or 'the library'}”.")
                d["quote_verified"] = False
    out["quote_check"] = QUOTE_CHECK
    return warnings


def _guards(out: dict, raw_text: str, docs: dict[str, str]) -> dict:
    warnings = _check_quotes(out, raw_text, docs)
    for d in out["dimensions"]:
        if d["evidence"] == "supported" and (not d["org_quote"] or not d["quote_verified"]):
            d["evidence"] = "inferred"  # never show unverified evidence as supported

    out["model_recommendation"] = out["recommendation"]
    out["gate"] = None
    eligible = next(c for c in out["checks"] if c["question"] == GO_NO_GO_QUESTIONS[0])
    geo = next(d for d in out["dimensions"] if d["key"] == "geographic_eligibility")
    if eligible["answer"] == "No" or geo["score"] == 1:
        out["recommendation"] = "No-Go"
        out["gate"] = "Eligibility gate: a hard eligibility rule is not met, so the recommendation is No-Go."

    out["fit_score"] = fit_score(out["dimensions"])
    out["weights"] = WEIGHTS
    out["quote_warnings"] = warnings
    return out


# --- Run ------------------------------------------------------------------------------
def _facts(opp: dict) -> str:
    return json.dumps({k: opp.get(k) for k in ("funder", "program_name", "deadline", "geography", "focus_area",
                                               "award_text", "eligibility", "restrictions", "requirements",
                                               "matched_funding", "reporting")}, indent=1)


def _funder_material(opp: dict) -> str:
    """Everything the agent is shown about the funder: the extracted facts and the full text.
    Funder quotes are checked against this, so a quote taken from the facts isn't wrongly flagged."""
    return f"{_facts(opp)}\n{opp.get('raw_text') or ''}"


def _opportunity_prompt(opp: dict) -> str:
    questions = "\n".join(f"- {q}" for q in GO_NO_GO_QUESTIONS)
    return (
        f"Today's date: {date.today().isoformat()}\n\n"
        f"Standard Go / No-Go questions:\n{questions}\n\n"
        f"Extracted facts (for convenience; quote from the full text below):\n{_facts(opp)}\n\n"
        f'<funder_opportunity untrusted="true">\n{opp.get("raw_text") or ""}\n</funder_opportunity>'
    )


def assess(opp: dict) -> dict:
    """Run the Fit Agent on a saved opportunity. Returns {result, usage}."""
    raw = opp.get("raw_text") or ""
    if len(raw) > MAX_INPUT_CHARS:
        raise ValueError("The funder text is too long to assess.")
    library_text, docs = library_context()
    # Static instructions + library first: a stable prefix the provider caches.
    run = run_agent(FitAssessment,
                    f"{INSTRUCTIONS}\n\n<organisation_library>\n{library_text}\n</organisation_library>",
                    _opportunity_prompt(opp), agent="fit_agent")
    usage = usage_dict(run.usage)
    result = _guards(_complete(run.output), _funder_material(opp), docs)
    log_run(
        "fit_agent", usage,
        {"opportunity_id": opp.get("id"), "recommendation": result["recommendation"],
         "fit_score": result["fit_score"], "quote_warnings": len(result["quote_warnings"])},
    )
    return {"result": result, "usage": usage}

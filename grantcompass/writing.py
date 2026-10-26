"""Writing agents for one application question.

- Grant Writer drafts from the Organisation Library only, citing a source for
  every fact and leaving [MISSING: …] placeholders instead of guessing.
- Grant Coach critiques an answer (VMock-style): what the question really
  asks, ten category scores, strengths, weaknesses, suggestions. Never rewrites.
- Evidence Checker classifies every claim against the library.

Code, not the model, counts words, checks the length limit, computes the
overall coach score from visible weights, and verifies every quote. A claim
whose source can't be found word for word is never shown as Supported."""

import re

from .config import PROMPTS_DIR
from .fit import quote_found
from .library import library_context
from .llm import log_run, run_agent, usage_dict
from .models import COACH_CATEGORIES, CoachReview, EvidenceReport, WriterDraft

PROMPTS = {name: (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8") for name in ("grant_writer", "grant_coach", "evidence_checker")}
FUNDER_TEXT_LIMIT = 8_000  # characters of the funder's text given to the writer and coach


def _unquote(text: str) -> str:
    """Models sometimes wrap quotes in quotation marks; the UI adds its own."""
    return (text or "").strip().strip('"\u201c\u201d\u2018\u2019\'').strip()


# --- Counting and limits -------------------------------------------------------------
def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def length_check(text: str, limit_type: str | None, limit_value: int | None) -> dict:
    """{count, unit, limit, ok, label}: computed by code, never by the model."""
    unit = limit_type or "words"
    count = len(text or "") if unit == "characters" else word_count(text)
    if not limit_value:
        return {"count": count, "unit": unit, "limit": None, "ok": True, "label": f"{count:,} {unit}"}
    ok = count <= limit_value
    label = f"{count:,} / {limit_value:,} {unit}" + ("" if ok else f" — over by {count - limit_value:,}")
    return {"count": count, "unit": unit, "limit": limit_value, "ok": ok, "label": label}


def limit_text(q: dict) -> str:
    return f"{q['limit_value']} {q['limit_type']}" if q.get("limit_value") else "no stated limit"


def source_context(quote: str, doc: str, width: int = 220) -> str:
    """The quote with some surrounding text, so the user can see it in place."""
    i = (doc or "").lower().find((quote or "").lower().strip(" .\"'")[:60])
    if i < 0:
        return quote
    start, end = max(0, i - width), min(len(doc), i + len(quote) + width)
    return ("…" if start else "") + doc[start:end].strip() + ("…" if end < len(doc) else "")


# --- Agent runner ---------------------------------------------------------------------
def _call(name: str, output_type, instructions: str, prompt: str, detail: dict):
    run = run_agent(output_type, instructions, prompt, agent=name)
    usage = usage_dict(run.usage)
    log_run(name, usage, detail)
    return run.output, usage


def _question_block(q: dict, opp: dict | None) -> str:
    funder = ""
    if opp:
        funder = (f"Funder: {opp['funder']} — {opp['program_name']}\n"
                  f'<funder_text untrusted="true">\n{(opp.get("raw_text") or "")[:FUNDER_TEXT_LIMIT]}\n</funder_text>\n\n')
    if q.get("kind") == "report" and opp:  # a report owed to a funder that already gave money, not an application
        awarded = f"${opp['awarded_amount']:,}" if opp.get("awarded_amount") else "a grant"
        funder += (f"This is a REPORT to a funder that awarded {awarded} for {opp.get('grant_period') or 'this grant'}"
                   ". Describe what was actually delivered and achieved, using the organisation's programme reports "
                   "and documents; never describe plans as results.\n"
                   f'<reporting_requirements untrusted="true">\n{(opp.get("reporting_requirements") or "")[:4000]}'
                   "\n</reporting_requirements>\n\n")
        return f"{funder}Report section:\n{q['prompt']}\n\nLength limit: {limit_text(q)}\n"
    return f"{funder}Funder question:\n{q['prompt']}\n\nLength limit: {limit_text(q)}\n"


# --- Grant Writer -----------------------------------------------------------------------
def draft(q: dict, opp: dict | None, instructions: str = "") -> dict:
    library_text, docs = library_context()
    prompt = _question_block(q, opp)
    if q.get("response", "").strip():
        prompt += f"\nThe writer's current answer (improve on it, keep what is good):\n<answer>\n{q['response']}\n</answer>\n"
    if instructions.strip():
        prompt += f"\nThe writer asks: {instructions.strip()}\n"
    out, usage = _call(
        "grant_writer", WriterDraft,
        f"{PROMPTS['grant_writer']}\n\n<organisation_library>\n{library_text}\n</organisation_library>",
        prompt, {"question_id": q["id"]},
    )
    result = out.model_dump()
    for s in result["sources"]:
        s["source_quote"] = _unquote(s["source_quote"])
        doc = docs.get(s["source_title"]) or "\n".join(docs.values())
        s["verified"] = bool(s["source_quote"]) and quote_found(s["source_quote"], doc)
        s["context"] = source_context(s["source_quote"], docs.get(s["source_title"], ""))
    result["unverified"] = sum(not s["verified"] for s in result["sources"])
    result["placeholders"] = re.findall(r"\[MISSING:[^\]]*\]", result["draft"])
    result["length"] = length_check(result["draft"], q.get("limit_type"), q.get("limit_value"))
    return {"result": result, "usage": usage}


# --- Grant Coach --------------------------------------------------------------------------
def coach(q: dict, opp: dict | None, answer: str) -> dict:
    if not answer.strip():
        raise ValueError("Write or paste an answer first.")
    prompt = _question_block(q, opp) + f"\n<answer>\n{answer}\n</answer>"
    out, usage = _call("grant_coach", CoachReview, PROMPTS["grant_coach"], prompt, {"question_id": q.get("id")})
    r = out.model_dump()

    # One score per category, in a fixed order; overall is computed here from visible weights.
    by_key = {c["key"]: c for c in r["categories"]}
    r["categories"] = [
        {**(by_key.get(k) or {"key": k, "score": None, "comment": "Not scored."}), "label": label, "weight": w}
        for k, (label, w) in COACH_CATEGORIES.items()
    ]
    scored = [(c["weight"], c["score"]) for c in r["categories"] if c["score"]]
    overall = round(sum(w * s for w, s in scored) / sum(w for w, _ in scored) * 10) if scored else 0
    length = length_check(answer, q.get("limit_type"), q.get("limit_value"))
    if not length["ok"]:
        overall = max(0, overall - 10)  # over the funder's limit is a compliance failure
    r["overall"], r["length"] = overall, length

    # Quotes must really be in the answer.
    for item in r["question_parts"]:
        item["where"] = _unquote(item["where"])
    for item in r["strengths"] + r["weaknesses"]:
        item["quote"] = _unquote(item["quote"])
    for part in r["question_parts"]:
        part["verified"] = quote_found(part["where"], answer) if part["where"] else False  # unverified quotes are hidden
    for fb in r["strengths"] + r["weaknesses"]:
        fb["verified"] = quote_found(fb["quote"], answer) if fb["quote"] else True

    # Issues must point at words that really are in the answer; each gets a stable id for highlighting.
    issues = []
    for n, it in enumerate(r.get("issues") or []):
        it["quote"] = _unquote(it["quote"])
        if it["quote"] and quote_found(it["quote"], answer):
            issues.append(ensure_fix({**it, "id": n}))
    if not length["ok"]:
        issues.insert(0, {"id": 99, "quote": "", "type": "answer", "severity": "high", "title": "Over the word limit",
                          "explanation": f"This answer is {length['label']}. Funders often stop reading at the limit "
                                         "or mark it non-compliant.", "replacement": ""})
    r["issues"] = issues
    return {"result": r, "usage": usage}


def ensure_fix(it: dict) -> dict:
    """Every suggestion must be acceptable: a replacement or a removal. Fill a safe default if the model
    left it out (also used for reviews saved before this rule existed)."""
    it = dict(it)
    if it.get("action") == "remove" or (it.get("replacement") or "").strip():
        it["action"] = it.get("action") or "replace"
        return it
    if it.get("type") in ("evidence", "repetition", "jargon"):  # unsupported, repeated or filler words: cut them
        it["action"], it["replacement"] = "remove", ""
    else:  # keep the sentence's place, mark exactly what the writer needs to add
        it["action"], it["replacement"] = "replace", f"[MISSING: {it.get('title', 'detail needed').lower()}]"
    return it


# --- Evidence Checker ---------------------------------------------------------------------
def check_evidence(answer: str, q_id: int | None = None) -> dict:
    if not answer.strip():
        raise ValueError("Write or paste an answer first.")
    library_text, docs = library_context()
    out, usage = _call(
        "evidence_checker", EvidenceReport,
        f"{PROMPTS['evidence_checker']}\n\n<organisation_library>\n{library_text}\n</organisation_library>",
        f"<answer>\n{answer}\n</answer>", {"question_id": q_id},
    )
    claims = []
    for c in out.model_dump()["claims"]:
        c["claim"], c["source_quote"] = _unquote(c["claim"]), _unquote(c["source_quote"])
        if not quote_found(c["claim"], answer):
            continue  # not actually in the answer: drop rather than show a phantom claim
        doc = docs.get(c["source_title"], "")
        c["verified"] = bool(c["source_quote"]) and quote_found(c["source_quote"], doc or "\n".join(docs.values()))
        if c["status"] == "Supported" and not c["verified"]:
            c["status"] = "Needs evidence"
            c["note"] = "The cited source could not be found word for word in your library. " + c["note"]
        c["context"] = source_context(c["source_quote"], doc) if c["verified"] else ""
        claims.append(c)
    order = {"Contradicted": 0, "Needs evidence": 1, "Weakly supported": 2, "Supported": 3}
    claims.sort(key=lambda c: order[c["status"]])
    counts = {s: sum(c["status"] == s for c in claims) for s in order}
    return {"result": {"claims": claims, "counts": counts}, "usage": usage}


def placeholder_free(text: str) -> bool:
    return "[MISSING:" not in (text or "")


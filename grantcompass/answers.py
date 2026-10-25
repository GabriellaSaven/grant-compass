"""Answer Library: approved answers the team can reuse across applications.

Topics and matching are plain keyword rules (no AI), so they are instant, free and
predictable: an answer is suggested for a new question when it covers the same topic
or its original question used similar words."""

import re

from . import db

# Topic -> words that signal it in a funder's question. Order matters only for ties.
TOPICS = {
    "Mission & organisation": ["mission", "vision", "history", "overview", "about your organi", "who you are",
                               "background", "founded"],
    "Need & community": ["need", "problem", "community", "population", "serve", "demographic", "challenge",
                         "why does this", "issue"],
    "Programme design": ["program", "programme", "activit", "design", "approach", "deliver", "model", "how will",
                         "how often", "curriculum", "services"],
    "Outcomes & evaluation": ["outcome", "evaluat", "measure", "impact", "result", "success", "metric", "data",
                              "goal", "track"],
    "Capacity & partners": ["capacity", "positioned", "qualif", "staff", "partner", "collaborat", "experience",
                            "leadership", "board", "expertise", "volunteer"],
    "Budget & sustainability": ["budget", "cost", "sustain", "funding", "financ", "revenue", "match", "other funders",
                                "expense", "dollar"],
    "Equity & inclusion": ["equity", "inclusi", "diversity", "dei", "underserved", "access", "barrier"],
}
OTHER = "Other"
STOP = set("""a an and are as at be by can describe do does for from has have how in is it its of on or our
please the this to what when where which who why will with you your work organization organisation""".split())


def classify(question: str) -> str:
    """The topic whose signal words appear most in the question; Other if none do."""
    q = (question or "").lower()
    scores = {t: sum(q.count(w) for w in words) for t, words in TOPICS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else OTHER


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOP}


def matches(question: str, exclude_question_id: int | None = None, limit: int = 5) -> list[dict]:
    """Saved answers worth reusing for this question, best first, each with a plain reason."""
    topic, want = classify(question), _words(question)
    out = []
    for a in db.list_answers():
        if exclude_question_id and a["question_id"] == exclude_question_id:
            continue
        have = _words(a["question"])
        overlap = len(want & have) / max(1, len(want | have))
        same = a["topic"] == topic and topic != OTHER
        score = (3 if same else 0) + overlap * 10
        if score >= 1.5:
            reason = "Same topic, similar question" if same and overlap >= 0.2 else \
                "Same topic" if same else "Similar question"
            out.append({**a, "score": score, "reason": reason})
    return sorted(out, key=lambda a: -a["score"])[:limit]


def search(query: str = "", topic: str | None = None) -> list[dict]:
    words = (query or "").lower().split()
    items = db.list_answers()
    if topic and topic != "All":
        items = [a for a in items if a["topic"] == topic]
    if words:
        items = [a for a in items
                 if all(w in f"{a['topic']} {a['question']} {a['text']} {a['funder'] or ''}".lower() for w in words)]
    return items


def word_count(text: str) -> int:
    return len((text or "").split())

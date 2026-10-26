"""Build report/report.html: a single self-contained file (screenshots embedded) for the MGT409 final report.

Every number comes from the app's own records: the usage logs (logs/**/usage.jsonl), the safety test results
(tests/safety_results.md) and the cost experiment (report/cost_experiment.json). Rebuild after any of them changes:
    .venv/bin/python report/build_report.py
Text the author still has to supply is marked with a yellow "TO ADD" box."""

import base64
import glob
import html
import io
import json
import re
import statistics as st
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
REPORT = Path(__file__).parent
SHOTS = REPORT / "shots"
OUT = REPORT / "report.html"

# --- Author details (fill these in) ---------------------------------------------------------------
AUTHOR = "Gabriella Saven"
REPO_URL = "https://github.com/GabriellaSaven/grant-compass"
USER_TEST = None  # path to the Markdown copied from user_test_kit.html, once the session has been run


esc = html.escape


def todo(text: str) -> str:
    return f'<div class="todo"><b>TO ADD</b> {text}</div>'


def img(name: str, caption: str, width: int = 1600, cls: str = "", crop=None) -> str:
    """crop = (left, top, right, bottom) as fractions of the screenshot."""
    path = SHOTS / name
    if not path.exists():
        return todo(f"screenshot {esc(name)}")
    im = Image.open(path).convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((round(crop[0] * w), round(crop[1] * h), round(crop[2] * w), round(crop[3] * h)))
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80, optimize=True, progressive=True)
    data = base64.b64encode(buf.getvalue()).decode()
    return (f'<figure class="{cls}"><img src="data:image/jpeg;base64,{data}" alt="{esc(caption)}">'
            f'<figcaption>{caption}</figcaption></figure>')


def money(x: float, digits: int = 4) -> str:
    return f"${x:,.{digits}f}"


# --- Usage logs ------------------------------------------------------------------------------------
rows = []
for f in sorted(set(glob.glob(str(ROOT / "logs" / "**" / "usage.jsonl"), recursive=True))):
    for line in open(f):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
priced = [r for r in rows if r.get("cost_usd") is not None and not r["agent"].startswith("exp_")]
AGENT_ORDER = ["research_agent", "fit_agent", "grant_writer", "grant_coach", "evidence_checker", "assistant",
               "executive_director"]
NAMES = {"research_agent": "Research Agent", "fit_agent": "Fit Agent", "grant_writer": "Grant Writer",
         "grant_coach": "Grant Coach", "evidence_checker": "Evidence Checker", "assistant": "Compass Assistant",
         "executive_director": "Executive Director"}


def med(rs, k):
    return st.median([r.get(k) or 0 for r in rs])


per_agent = {}
for a in AGENT_ORDER:
    rs = [r for r in priced if r["agent"] == a]
    if not rs:
        continue
    tin = sum(r["input_tokens"] for r in rs)
    per_agent[a] = {
        "n": len(rs), "input": med(rs, "input_tokens"), "cached": med(rs, "cached_input_tokens"),
        "output": med(rs, "output_tokens"), "cost": med(rs, "cost_usd"), "mean_cost": st.mean(r["cost_usd"] for r in rs),
        "cache_share": sum(r.get("cached_input_tokens") or 0 for r in rs) / max(tin, 1),
        "seconds": med([r for r in rs if r.get("seconds")], "seconds") if any(r.get("seconds") for r in rs) else None,
    }
total_runs = len([r for r in rows if not r["agent"].startswith("exp_")])
total_cost = sum(r["cost_usd"] for r in priced)
first_day = min(r["time"] for r in rows)[:10]
last_day = max(r["time"] for r in rows)[:10]

# The traced run (Cedar Ridge, San Antonio Area Foundation, 25 Oct 2026)
cedar = [json.loads(line) for line in open(ROOT / "logs" / "cedar-ridge-veterans" / "usage.jsonl")]
TRACE_FIT = next(r for r in cedar if r["agent"] == "fit_agent" and r.get("time", "").startswith("2026-10-25T21:25"))
TRACE = {r["agent"]: r for r in cedar if r["time"] >= "2026-10-25T21:26" and r["time"] < "2026-10-25T21:36:00"}
TRACE["fit_agent"] = TRACE_FIT
TRACE_STEPS = ["research_agent", "fit_agent", "grant_writer", "grant_coach", "evidence_checker"]
trace_cost = sum(TRACE[a]["cost_usd"] for a in TRACE_STEPS)
trace_in = sum(TRACE[a]["input_tokens"] for a in TRACE_STEPS)
trace_out = sum(TRACE[a]["output_tokens"] for a in TRACE_STEPS)

# Monthly usage for one development director (assumptions shown in the report)
MONTH = [  # (what, agent, runs per month)
    ("Fit checks on new search results and links", "fit_agent", 80),
    ("Funder pages read (only when they change)", "research_agent", 40),
    ("Answers drafted (4 applications x 4 questions)", "grant_writer", 16),
    ("Coach reviews (about 2 per answer)", "grant_coach", 32),
    ("Evidence checks (about 1.5 per answer)", "evidence_checker", 24),
    ("Chat questions", "assistant", 60),
    ("Board updates and team reviews", "executive_director", 6),
]
month_rows = [(w, a, n, n * per_agent[a]["mean_cost"]) for w, a, n in MONTH if a in per_agent]
per_user_month = sum(c for *_, c in month_rows)

# Cost experiment
exp = json.loads((REPORT / "cost_experiment.json").read_text()) if (REPORT / "cost_experiment.json").exists() else None

# Safety results
safety_md = (ROOT / "tests" / "safety_results.md").read_text()
safety = []
for block in re.split(r"\n## ", safety_md)[1:]:
    title = block.splitlines()[0]
    m = {k: (re.search(rf"- \*\*{k}:\*\* (.*)", block) or [None, ""])[1] for k in ("Risk", "Attack", "Defense", "Observed")}
    safety.append({"title": re.sub(r"^\d+\. [✅❌] ", "", title), "passed": "✅" in title, **m})
safety_header = re.search(r"Run (.*?) with", safety_md)[1]

# --- Diagram (HTML/SVG, no image generation) ----------------------------------------------------------
DIAGRAM = """
<svg viewBox="0 0 920 430" class="diagram" role="img" aria-label="How the Grant Compass agents hand work to each other">
<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="#7aa892"/></marker>
<marker id="arr2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="#b9b2a4"/></marker></defs>
<g font-family="Inter, -apple-system, Segoe UI, sans-serif">
<!-- sources -->
<rect x="10" y="150" width="120" height="118" rx="12" fill="#f3f0ea" stroke="#d9d3c7"/>
<text x="70" y="176" text-anchor="middle" font-size="12" font-weight="600" fill="#5b5a55">FUNDER SOURCES</text>
<text x="70" y="198" text-anchor="middle" font-size="12" fill="#5b5a55">Grants.gov</text>
<text x="70" y="216" text-anchor="middle" font-size="12" fill="#5b5a55">74 foundation sites</text>
<text x="70" y="234" text-anchor="middle" font-size="12" fill="#5b5a55">Links, PDFs, Word</text>
<text x="70" y="252" text-anchor="middle" font-size="12" fill="#5b5a55">State portals</text>
<!-- library -->
<rect x="330" y="350" width="260" height="62" rx="12" fill="#f3f0ea" stroke="#d9d3c7"/>
<text x="460" y="375" text-anchor="middle" font-size="12" font-weight="600" fill="#5b5a55">YOUR PROFILE + SOURCE DOCUMENTS</text>
<text x="460" y="395" text-anchor="middle" font-size="12" fill="#5b5a55">the only facts agents may use</text>
<!-- flow arrows -->
<line x1="130" y1="209" x2="168" y2="209" stroke="#7aa892" stroke-width="2.5" marker-end="url(#arr)"/>
<line x1="262" y1="209" x2="300" y2="209" stroke="#7aa892" stroke-width="2.5" marker-end="url(#arr)"/>
<line x1="394" y1="209" x2="432" y2="209" stroke="#7aa892" stroke-width="2.5" marker-end="url(#arr)"/>
<line x1="526" y1="209" x2="564" y2="209" stroke="#7aa892" stroke-width="2.5" marker-end="url(#arr)"/>
<line x1="656" y1="196" x2="712" y2="150" stroke="#7aa892" stroke-width="2.5" marker-end="url(#arr)"/>
<line x1="656" y1="222" x2="712" y2="270" stroke="#7aa892" stroke-width="2.5" marker-end="url(#arr)"/>
<line x1="760" y1="168" x2="760" y2="186" stroke="#7aa892" stroke-width="0"/>
<path d="M806 130 C 860 130, 880 170, 880 200" fill="none" stroke="#7aa892" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#arr)"/>
<path d="M806 290 C 860 290, 880 250, 880 220" fill="none" stroke="#7aa892" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#arr)"/>
<!-- library to agents -->
<line x1="400" y1="350" x2="350" y2="258" stroke="#b9b2a4" stroke-width="1.5" stroke-dasharray="4 4" marker-end="url(#arr2)"/>
<line x1="460" y1="350" x2="480" y2="258" stroke="#b9b2a4" stroke-width="1.5" stroke-dasharray="4 4" marker-end="url(#arr2)"/>
<line x1="560" y1="350" x2="610" y2="258" stroke="#b9b2a4" stroke-width="1.5" stroke-dasharray="4 4" marker-end="url(#arr2)"/>
<line x1="590" y1="372" x2="740" y2="318" stroke="#b9b2a4" stroke-width="1.5" stroke-dasharray="4 4" marker-end="url(#arr2)"/>
<!-- nodes -->
<g>
<circle cx="215" cy="209" r="46" fill="#fff" stroke="#2f5d50" stroke-width="3"/><text x="215" y="204" text-anchor="middle" font-size="13" font-weight="700" fill="#1f2a26">Research</text><text x="215" y="222" text-anchor="middle" font-size="12" fill="#5b5a55">extracts facts</text>
<circle cx="347" cy="209" r="46" fill="#fff" stroke="#2f5d50" stroke-width="3"/><text x="347" y="204" text-anchor="middle" font-size="13" font-weight="700" fill="#1f2a26">Fit</text><text x="347" y="222" text-anchor="middle" font-size="12" fill="#5b5a55">scores 1–5 x7</text>
<circle cx="479" cy="209" r="46" fill="#2f5d50"/><text x="479" y="204" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">You</text><text x="479" y="222" text-anchor="middle" font-size="12" fill="#e4efe9">Go / No-Go</text>
<circle cx="610" cy="209" r="46" fill="#fff" stroke="#2f5d50" stroke-width="3"/><text x="610" y="204" text-anchor="middle" font-size="13" font-weight="700" fill="#1f2a26">Writer</text><text x="610" y="222" text-anchor="middle" font-size="12" fill="#5b5a55">drafts, cites</text>
<circle cx="760" cy="125" r="46" fill="#fff" stroke="#2f5d50" stroke-width="3"/><text x="760" y="120" text-anchor="middle" font-size="13" font-weight="700" fill="#1f2a26">Coach</text><text x="760" y="138" text-anchor="middle" font-size="12" fill="#5b5a55">critiques only</text>
<circle cx="760" cy="295" r="46" fill="#fff" stroke="#2f5d50" stroke-width="3"/><text x="760" y="290" text-anchor="middle" font-size="13" font-weight="700" fill="#1f2a26">Evidence</text><text x="760" y="308" text-anchor="middle" font-size="12" fill="#5b5a55">tests claims</text>
<circle cx="880" cy="210" r="30" fill="#2f5d50"/><text x="880" y="206" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">You</text><text x="880" y="221" text-anchor="middle" font-size="10" fill="#e4efe9">approve</text>
</g>
<!-- supervisor + assistant -->
<rect x="300" y="18" width="340" height="56" rx="28" fill="#1f2a26"/>
<text x="470" y="42" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">Executive Director</text>
<text x="470" y="60" text-anchor="middle" font-size="12" fill="#cfd8d3">reads every agent's metrics · briefs you · board update</text>
<line x1="380" y1="74" x2="250" y2="165" stroke="#b9b2a4" stroke-width="1.3" stroke-dasharray="3 4"/>
<line x1="420" y1="74" x2="360" y2="163" stroke="#b9b2a4" stroke-width="1.3" stroke-dasharray="3 4"/>
<line x1="530" y1="74" x2="600" y2="163" stroke="#b9b2a4" stroke-width="1.3" stroke-dasharray="3 4"/>
<line x1="580" y1="74" x2="720" y2="105" stroke="#b9b2a4" stroke-width="1.3" stroke-dasharray="3 4"/>
<rect x="20" y="20" width="230" height="56" rx="12" fill="#fff" stroke="#d9d3c7"/>
<text x="135" y="43" text-anchor="middle" font-size="13" font-weight="700" fill="#1f2a26">Compass Assistant (chat)</text>
<text x="135" y="61" text-anchor="middle" font-size="12" fill="#5b5a55">11 read-only tools + open a page</text>
</g></svg>
<div class="legend"><span><i class="sw solid"></i>work handed on</span><span><i class="sw dash"></i>facts read from your library</span><span><i class="sw dot"></i>supervision (metrics only)</span><span><i class="sw dark"></i>a human decision</span></div>
"""

# --- Sections ----------------------------------------------------------------------------------------
def table(head, body, cls=""):
    th = "".join(f"<th>{h}</th>" for h in head)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in body)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


agent_rows = [
    ("Research Agent", "Reads a funder's web page, PDF or Word file and extracts deadline, award, eligibility, "
     "restrictions and the application questions word for word.",
     "Safe web fetch (public sites only, robots.txt respected), PDF/Word text extraction, Grants.gov and state "
     "portal APIs; 74-site foundation directory re-read only when a page's text changes.",
     "Lists any instruction-like text it finds; it is shown to you in red and never acted on."),
    ("Fit Agent", "Scores 7 dimensions 1–5 (mission, geography, population, funding size, strategy, evidence, "
     "effort), each with a funder quote and a quote from your documents.",
     "Your Profile + source documents, your history with this funder (wins, losses, feedback).",
     "Fit % and the eligibility gate are computed in code; every quote is matched word for word, unverified "
     "evidence is downgraded to Inferred."),
    ("Grant Writer", "Drafts one answer at a time within the word limit, using only your documents and approved "
     "Answer Library language.",
     "Your library, Answer Library, the funder's question and priorities.",
     "Missing facts become [MISSING: …] gaps rather than invented numbers; you load the draft yourself."),
    ("Grant Coach", "Reviews an answer like a program officer: what the question asks (✓/◐/✕), ten weighted "
     "category scores, and 3–8 anchored suggestions you accept or reject.",
     "The question, your answer, the funder's text.",
     "Never rewrites your text; score is a weighted average computed in code; injection inside the answer "
     "is treated as data."),
    ("Evidence Checker", "Splits the answer into claims and labels each Supported, Weakly supported, Needs "
     "evidence or Contradicted, with the source passage.",
     "Your Profile + source documents.",
     "Each cited source passage must exist word for word."),
    ("Compass Assistant", "Chat on every page: answers questions about deadlines, pipeline, reports, spending "
     "and takes you to a page.",
     "11 read-only tools (pipeline, grant details, discovery matches, federal search, profile, team, funder "
     "reports, answer library, open asks, agent health, AI spending) + open_page.",
     "No tool can change data; navigation only accepts the app's own pages."),
    ("Executive Director", "Supervisor: reads every agent's health metrics and briefs you on what to watch; "
     "also writes the board fundraising update.",
     "Computed metrics only (never raw documents).",
     "Every claim must cite an existing metric with its exact value or it is removed; its rating can't be "
     "rosier than the code's rule-based status."),
]

trace_steps = [
    ("1 · Paste a real funder link", "research_agent",
     "On Discover, the Cedar Ridge Veterans Collaborative (a San Antonio demo organisation) pastes the San Antonio "
     "Area Foundation's real grants page. The Research Agent reads the live page and extracts the open programme "
     "(Special and Urgent Needs, rolling deadline). No application questions were on the page, and it says so.",
     "05a_import_link.jpg", None),
    ("2 · Fit assessment", "fit_agent",
     "The Fit Agent scores 59%: Geography 5/5 (the foundation funds Bexar County, where Cedar Ridge works), Funding "
     "size and Effort unknown because the page doesn't state them, and recommends <b>Research further</b> rather "
     "than Go. The code marks it 'Filtered out' too, because the page also says several 2026 programmes are "
     "closed: the app is honest that this is not a sure thing.", "05_import_fit.jpg", (0.61, 0.0, 1.0, 1.0)),
    ("3 · You decide, add a question, Draft with AI", "grant_writer",
     "The user clicks Add &amp; start application, pastes the funder's question (250-word limit) and clicks Draft "
     "with AI. In 6 seconds the Grant Writer returns 174 words built only from Cedar Ridge's documents: 318 of 412 "
     "households housed in 2025-26, the Homeward Navigation programme, the family make-up of the current cohort.",
     "07_draft.jpg", (0.275, 0.28, 0.605, 1.0)),
    ("4 · Review suggestions (Grant Coach)", "grant_coach",
     "Switching to Review suggestions runs the Coach in the background. It scores the draft 65/100 ('Getting "
     "there'), checks each part of the question (all three only partly answered), and underlines six passages. "
     "Clicking one opens a suggestion card: <i>Urgency lacks evidence</i>, with why it matters and Accept / Reject.",
     "08b_coach_card.jpg", (0.275, 0.28, 0.91, 1.0)),
    ("5 · Check evidence", "evidence_checker",
     "The Evidence Checker tests 12 claims against the documents: 7 Supported, 2 Weakly supported, 1 Needs "
     "evidence and <b>2 Contradicted</b>. The writer had labelled first-quarter 2026 cohort figures (41% families "
     "with children, 38% with a disability rating) as 2025-26 results; the checker caught it and shows the source "
     "passage. This is the team working as designed: one agent's mistake is caught by another before a funder "
     "sees it.", "09_evidence.jpg", (0.61, 0.28, 0.91, 1.0)),
]

trace_html = []
for title, agent, text, shot, crop in trace_steps:
    r = TRACE[agent]
    tok = (f'{NAMES[agent]} · {r["input_tokens"]:,} input ({r.get("cached_input_tokens") or 0:,} cached) · '
           f'{r["output_tokens"]:,} output · {money(r["cost_usd"])} · {r.get("seconds") or "–"} s')
    trace_html.append(f'<div class="step"><div><h4>{title}</h4><p>{text}</p><p class="tok">{tok}</p></div>'
                      f'{img(shot, "", width=1100, crop=crop)}</div>')

per_agent_rows = [(NAMES[a], f'{v["n"]:,}', f'{v["input"]:,.0f}', f'{v["cached"]:,.0f}', f'{v["output"]:,.0f}',
                   money(v["cost"]), f'{v["cache_share"]:.0%}') for a, v in per_agent.items()]

month_table = table(["Work in a typical month", "Agent", "Runs", "Cost"],
                    [(w, NAMES[a], n, money(c, 3)) for w, a, n, c in month_rows] +
                    [("<b>Total per active user</b>", "", "", f"<b>{money(per_user_month, 2)}</b>")])
scale = [(n, per_user_month * n) for n in (1, 100, 10_000)]

if exp:
    S = exp["summary"]
    A, B, C = S["A_shipped"], S["B_no_cache_order"], S["C_medium_reasoning"]
    exp_table = table(
        ["Setting (same 6 grants)", "Avg input", "Cached", "Avg output", "Avg cost", "Avg time",
         "Same Go/No-Go as shipped", "Avg fit gap vs shipped", "Quote warnings"],
        [("<b>A · Shipped</b>: low reasoning, library first (cacheable)", f'{A["mean_input"]:,}', f'{A["cached_share"]:.0%}',
          f'{A["mean_output"]:,}', money(A["mean_cost"]), f'{A["mean_seconds"]} s', f'{A["same_recommendation_as_A"]}/{A["runs"]}', "—", A["quote_warnings"]),
         ("B · Library after the grant (no shared prefix)", f'{B["mean_input"]:,}', f'{B["cached_share"]:.0%}',
          f'{B["mean_output"]:,}', money(B["mean_cost"]), f'{B["mean_seconds"]} s', f'{B["same_recommendation_as_A"]}/{B["runs"]}',
          f'{B["mean_abs_fit_diff_vs_A"]} pts', B["quote_warnings"]),
         ("C · Medium reasoning effort", f'{C["mean_input"]:,}', f'{C["cached_share"]:.0%}', f'{C["mean_output"]:,}',
          money(C["mean_cost"]), f'{C["mean_seconds"]} s', f'{C["same_recommendation_as_A"]}/{C["runs"]}',
          f'{C["mean_abs_fit_diff_vs_A"]} pts', C["quote_warnings"])], "small")
    cache_saving = 1 - A["mean_cost"] / B["mean_cost"] if B["mean_cost"] else 0
    reasoning_extra = C["mean_cost"] / A["mean_cost"] - 1 if A["mean_cost"] else 0
    exp_text = (f"<p><b>Caching works and costs nothing in quality.</b> With the instructions and library first, "
                f"<b>{A['cached_share']:.0%}</b> of input tokens came from cache (versus {B['cached_share']:.0%}), "
                f"cutting the cost per assessment by <b>{cache_saving:.0%}</b>. The prompt content is identical, so "
                f"any difference in answers is the model's own run-to-run variation.</p>"
                f"<p><b>More reasoning cost {reasoning_extra:+.0%} and was {C['mean_seconds'] - A['mean_seconds']:.0f} s "
                f"slower, without better decisions.</b> Fit scores moved by {C['mean_abs_fit_diff_vs_A']} points on "
                f"average. Recommendations matched the shipped setting on {C['same_recommendation_as_A']} of "
                f"{C['runs']} grants, but setting B, which reasons exactly like A, matched on only "
                f"{B['same_recommendation_as_A']} of {B['runs']}: on borderline grants the model flips between "
                f"<i>Research further</i> and <i>No-Go</i> whatever the setting. (High fit with No-Go is expected "
                f"here: those grants are due in 1–4 days or already submitted.) So low reasoning stays, and the "
                f"variability is listed as a limit in section 7. Six grants is a small sample: evidence, not proof.</p>")
else:
    exp_table, exp_text = todo("cost experiment results (run report/cost_experiment.py)"), ""

def short(t: str, n: int = 150) -> str:
    return esc(t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…")


safety_rows = [(f'{"✅" if s["passed"] else "❌"} <b>{esc(s["title"])}</b><br><span class="src">{short(s["Attack"], 110)}</span>',
                short(s["Defense"], 170), short(s["Observed"], 130)) for s in safety]


# A typical one-grant run: the five steps of the trace, using each agent's median from all logged runs
TYPICAL = {k: sum(per_agent[a][k] for a in TRACE_STEPS) for k in ("input", "cached", "output", "cost")}

SAFETY_GROUPS = [  # (category, requirement wording, test numbers 1-based)
    ("Attacks", "Prompt injection", [1, 2, 3, 4]),
    ("Attacks", "Data leaks and break-ins", [10, 13, 12]),
    ("Agent malfunction", "Invented facts", [8, 9]),
    ("Agent malfunction", "Wrong action", [5]),
    ("Agent malfunction", "Infinite loops", [6]),
    ("Overspending", "Budget guards", [7, 11]),
]
safety_group_rows = []
for cat, kind, nums in SAFETY_GROUPS:
    for i, n in enumerate(nums):
        s = safety[n - 1]
        safety_group_rows.append((
            f"<b>{cat}</b><br><span class='src'>{kind}</span>" if i == 0 else "",
            f'{"✅" if s["passed"] else "❌"} {esc(s["title"])}', short(s["Defense"], 120), short(s["Observed"], 85)))

def quote(text: str, cls: str = "") -> str:
    return f'<blockquote class="{cls}">“{text}”</blockquote>'


user_block = f"""<p>A friend with grant-fundraising experience tried the app on their own in October 2026 and sent me an
honest review (full text in <code>report/user_review.md</code>).</p>
<div class="quotes">
{quote("It gets to the part that takes so much time in fundraising, which is working out whether something is "
       "actually worth pursuing before you sink hours into an application.")}
{quote("I could genuinely see this saving a lot of time for a small fundraising team, especially where one person "
       "is juggling research, deadlines and writing at the same time.")}
{quote("It actually feels like something I would use in real life, which I wasn’t expecting from a student project.")}
{quote("The pipeline is probably my favourite bit. Being able to see deadlines, risk, funding amount, where each "
       "application is at and what the next action is all in one place is genuinely helpful.")}
</div>
<p class="src">What they'd improve: “keep pushing the organisation knowledge/evidence side because that is where I think it
becomes especially valuable.” It is now one of the next steps on page 15.</p>""" + (Path(USER_TEST).read_text() if USER_TEST else "")

repo = (f'<a href="{REPO_URL}">{REPO_URL}</a>' if REPO_URL else
        '<span class="todo-inline">TO ADD: GitHub link (same as on Canvas)</span>')

def bars(items, fmt, note=""):
    """Horizontal HTML bar chart: items = [(label, value)]."""
    top = max(v for _, v in items) or 1
    rows_ = "".join(f'<div class="bar"><span class="bl">{l}</span><span class="bt"><i style="width:{100 * v / top:.1f}%"></i></span>'
                    f'<span class="bv">{fmt(v)}</span></div>' for l, v in items)
    return f'<div class="bars">{rows_}</div>' + (f'<p class="src">{note}</p>' if note else "")


spend = sorted(((NAMES[a], sum(r["cost_usd"] for r in priced if r["agent"] == a)) for a in per_agent),
               key=lambda x: -x[1])
SPEND_CHART = bars(spend, lambda v: f"{money(v, 3)} · {v / total_cost:.0%}",
                   "Total spend by agent across all logged runs. The Fit Agent dominates because it runs on every search result worth a look.")
EXP_CHART = bars([("A · Shipped", exp["summary"]["A_shipped"]["mean_cost"] * 1000),
                  ("B · No cache-friendly order", exp["summary"]["B_no_cache_order"]["mean_cost"] * 1000),
                  ("C · Medium reasoning", exp["summary"]["C_medium_reasoning"]["mean_cost"] * 1000)],
                 lambda v: f"${v:.2f} per 1,000 assessments") if exp else ""

# --- Pages ----------------------------------------------------------------------------------------------
PAGES = []  # (short label for the navigation, html)


def page(label: str, html_: str):
    PAGES.append((label, html_))


page("Title", f"""
<div class="cover">
<p class="eyebrow">MGT409 AI Foundations · Final project · Fall 2026</p>
<h1>Grant <em>Compass</em></h1>
<p class="lede">Grant Compass is an AI development team for small nonprofits: it finds grants that fit, tells
you honestly whether to apply, and helps you write answers that are true to your own records.</p>
<div class="meta"><b>Author</b><span>{AUTHOR}</span>
<b>GitHub</b><span>{repo} (public repository)<br><code>git clone {REPO_URL}.git</code></span>
<b>App</b><span>Runs locally from the README (not hosted online): Python 3.10+, one <code>PORTKEY_API_KEY</code>, six demo organisations with no password</span>
<b>Model</b><span>gpt-6-luna via Portkey, for every AI call</span></div>
<div class="kpis">
<div class="kpi"><b>7</b><span>AI agents, each checked by code</span></div>
<div class="kpi"><b>{money(trace_cost, 3)}</b><span>AI cost to find, assess, draft, coach and check one grant answer</span></div>
<div class="kpi"><b>{money(per_user_month, 2)}</b><span>AI cost per active user per month</span></div>
<div class="kpi"><b>{sum(s['passed'] for s in safety)}/{len(safety)}</b><span>attack and failure tests passed</span></div></div>
<h3>Contents</h3>
<ol class="toc">
<li><a href="#p2">Motivation</a><span>2–3</span></li><li><a href="#p4">What is new here</a><span>4</span></li>
<li><a href="#p5">The agents</a><span>5–8</span></li><li><a href="#p9">Tokenomics</a><span>9–11</span></li>
<li><a href="#p12">Safety</a><span>12–13</span></li><li><a href="#p14">Impact</a><span>14</span></li>
<li><a href="#p15">Limits and next steps</a><span>15</span></li></ol>
</div>""")

page("Motivation", f"""
<h2><span class="n">1 · MOTIVATION</span>I was the person this is for</h2>
<p class="big">Before business school, I was a fundraiser. I joined to help a mission I believed in, and found
that most of my week went to paperwork instead.</p>
<p>Grant season meant scrolling through foundation websites to work out whether we were even eligible, then
rebuilding the same answers from last year's applications for a new funder's word limits. Before anything went
out, I had to hunt through program reports to confirm that every number I had written was actually true, because
one wrong statistic in front of a funder costs more than one lost grant. After an award came the reports, and
after that the board update. Every deadline landed in the same weeks as program work, so the applications that
got submitted were the ones I had time for, not always the ones we were best placed to win.</p>
<p>None of that work is what a funder pays for or what a community needs from us. It is the cost of being heard.
Grant Compass is the tool I wanted in that job.</p>
<h3>Who has this problem</h3>
<p>About <b>1.9 million</b> registered nonprofits in the US, most of them running on under $1 million a year. In
those organisations, grant work falls on one or two people (a development director, an executive director, a
program manager writing at night) who also run the programmes the grants pay for.</p>
<h3>How they handle it today</h3>
<ul>
<li>A spreadsheet of deadlines, and funder websites searched one by one, or a paid database for those who can afford one.</li>
<li>Copying and editing paragraphs from old applications.</li>
<li>Increasingly, pasting questions into ChatGPT, which writes fluently but can state numbers that aren't in the
organisation's records.</li>
<li>For those with budget, a freelance grant writer for each important proposal.</li>
</ul>
{img("02_home.jpg", crop=(0.08, 0.06, 0.92, 0.62), width=1300, cls="home", caption="Grant Compass's home screen: what is due, what is at risk, and what each grant is worth, in one place.")}""")

page("Motivation", f"""
<h3 class="first">What it costs: money, time and frustration</h3>
<div class="statgrid">
<div><b>68%</b><span>of organisations name <i>time</i> as their biggest grant-seeking challenge (GrantStation, 2023)</span></div>
<div><b>2 days–4 weeks</b><span>to prepare a single proposal (SSIR, on grant-writing workloads)</span></div>
<div><b>~48 hours</b><span>median time per application to a philanthropic funder (SmartyGrants)</span></div>
<div><b>$1,500–$5,000</b><span>a freelance writer's flat fee for one full foundation proposal; hourly rates are $30–150 (Grantable, 2026)</span></div>
<div><b>22% vs 72%</b><span>of very small vs other nonprofits received even one foundation grant (Candid)</span></div>
<div><b>$299+/month</b><span>for a grant-search database like Instrumentl, out of reach for most small groups</span></div>
</div>
<p><b>Time:</b> dozens of hours per application, mostly searching, re-formatting and fact-checking rather than
thinking. <b>Money:</b> either staff hours taken from programmes, or fees a small budget can't carry.
<b>Frustration:</b> the work is repetitive, deadlines collide, and the people doing it know the hours came out of
the mission. Candid's data shows the result: the smallest organisations, often closest to their communities, are
the least likely to win foundation money at all.</p>
<div class="why"><h3>Why care</h3>
<p>Because every hour belongs to the community. A fundraiser's time is one of the scarcest resources a small
nonprofit has, and right now too much of it goes to searching, re-typing and double-checking. Grant Compass is
about <b>optimising our time for the communities we serve</b>: software does the searching, the first draft and the
fact-check; people spend their hours on the work only they can do, building relationships with funders and showing
up for the families, veterans and students who rely on them.</p>
<p>Better-targeted applications also mean the money is more likely to arrive. When a two-person team can apply to
the right five funders instead of the nearest two, that is more meals, more tutoring hours, more veterans housed.</p></div>
{quote("It feels like it was designed by someone who actually understands how grant fundraising works rather than "
       "just adding AI onto a generic CRM.", "side")}
<p class="cite">A friend with grant-fundraising experience, after trying the app (page 14)</p>
""")

page("What is new", f"""
<h2><span class="n">2 · WHAT IS NEW HERE</span>Not a grant database, and not a chatbot</h2>
<h3>What already exists</h3>
{table(["", "Finds grants", "Judges fit against <i>your</i> documents", "Drafts answers", "Checks claims against your records", "After the award", "Price"], [
 ("<b>Instrumentl</b>", "✓ large database", "Keyword match", "AI assist (higher tiers)", "—", "Tracking (top tier)", "$299–$999/mo"),
 ("<b>Candid Foundation Directory</b>", "✓ reference database", "—", "—", "—", "—", "≈$1,200–$2,200/yr"),
 ("<b>Grantable</b> (startup)", "Basic", "—", "✓ AI drafting", "—", "—", "$0–$150/mo"),
 ("<b>ChatGPT</b>", "—", "Only what you paste", "✓", "— can invent numbers", "—", "$0–$20/mo"),
 ("<b>Freelance writer</b>", "Sometimes", "✓ (human)", "✓", "✓ (human)", "Extra fee", "$1,500–$5,000 flat fee per proposal (≈$75/h)"),
 ("<b>Grant Compass</b>", "✓ Grants.gov, state portals, 74 foundations, any link", "✓ 7 dimensions, quotes verified", "✓ from your documents only", "✓ Evidence Checker + Coach", "✓ reports, board update", f"≈{money(per_user_month, 2)}/mo in AI"),
], "small")}
<h3>What is different, honestly</h3>
<p>Instrumentl and Candid are better <i>databases</i>, and a good freelance writer is better at prose. What is new
is the combination, built around one rule: <b>the AI may only say what your own records support, and code, not
the AI, checks that it did.</b></p>
<ul>
<li><b>A team that checks itself.</b> Seven agents with narrow jobs; two exist only to check the others (the
Evidence Checker and the Executive Director). In the traced run, the checker caught the writer's mistake.</li>
<li><b>Verification in code.</b> Fit % and eligibility are computed, not asked for; quotes must match the source
word for word; the Director's claims must match real metrics. Generic AI tools trust the model.</li>
<li><b>Honest go / no-go.</b> The Fit Agent will say <i>Research further</i> or <i>No-Go</i>, uses your history with the
funder, and explains every score with quotes.</li>
<li><b>The whole life cycle</b>, from search to funder report to board update, in one place.</li></ul>
{quote("The Grant Coach feels much more useful than just asking ChatGPT to rewrite something because it actually "
       "tells you what is missing, whether you’ve answered the question properly and where the evidence is weak.", "side")}
<p class="cite">A friend with grant-fundraising experience, after trying the app</p>
<h3>Why the difference matters</h3>
<p>For a small nonprofit, a wrong number in an application can cost a funder relationship that took years to
build, so speed without verification is a bad trade. And at under 20 cents a month in AI costs, this can be
offered to the organisations that can't justify $300 a month, the ones Candid's data shows are left out.</p>""")

page("Agents", f"""
<h2><span class="n">3 · THE AGENTS</span>Seven colleagues with narrow jobs</h2>
<h3>How they are organised, and who hands work to whom</h3>
{DIAGRAM}
<p>Work moves left to right like a real development team. <b>Research</b> reads a funder and hands the extracted
facts to <b>Fit</b>, which scores them against your library. <b>You</b> decide Go / No-Go. The <b>Writer</b> drafts
each answer, then the <b>Coach</b> and <b>Evidence Checker</b> review it in parallel, and <b>you</b> approve what is
sent. A person sits at the two decisions that matter: whether to apply, and what to send.</p>
<p>The <b>Executive Director</b> supervises from above. It sees only metrics (failure rates, quote-warning rates,
costs), never documents, so it can't be manipulated by them. The <b>Compass Assistant</b> is a read-only chat
layer over everything. Agents don't call each other: the app passes each one exactly the inputs it needs, and each
returns a typed result (a Pydantic model), so code can check it.</p>
<h3>Models used, and why</h3>
<p>Every call uses <b>gpt-6-luna</b> through Portkey (the course key), with low reasoning effort, a 6,000-token
output cap, and at most 6 model calls and 120,000 tokens per run. A small, cheap model is enough because the hard
parts (scores, eligibility, quote matching, totals) are done in code; the model only reads and writes. Section 4
tests whether more reasoning would help: it cost 58% more and did not.</p>""")

page("Agents", f"""
<h3 class="first">Each agent, what it does, and its tools</h3>
{table(["Agent", "What it does", "Tools and inputs", "What keeps it honest"], agent_rows, "small")}
<p class="src">Built with pydantic-ai. Each agent has its own instructions file in <code>grantcompass/prompts/</code>
and a typed output in <code>grantcompass/models.py</code>.</p>
<h3>Example output: the Executive Director's board update</h3>
{img("12b_board_summary.jpg", width=1300, crop=(0, 0, 1, 0.8), caption="Reports page, Cedar Ridge. Generated in under 10 seconds; Every number is checked against the records before it is shown.")}""")

page("Agents", f"""
<h3 class="first">One real run, traced step by step</h3>
<p>Sunday 25 October 2026, on the Cedar Ridge Veterans Collaborative (a demo organisation in San Antonio). All
screenshots are from this run; token counts are from the app's usage log.</p>
{img("03_discover.jpg", crop=(0.08, 0.44, 0.92, 0.93), width=1300, caption="Discover: one search across Grants.gov and 74 foundation sites ranks 18 matches by fit. Results assessed earlier are reused at no cost.")}
{trace_html[0]}
{trace_html[1]}""")

page("Agents", f"""
{trace_html[2]}
{trace_html[3]}
{trace_html[4]}
<div class="callout">Whole run: {trace_in:,} input and {trace_out:,} output tokens across five agents,
<b>{money(trace_cost, 4)}</b>, about 40 seconds of AI time. One step was wrong (the Writer's dates) and another agent
caught it before a human had to.</div>""")

page("Tokenomics", f"""
<h2><span class="n">4 · TOKENOMICS</span>Under a cent per grant, measured</h2>
<p>All figures come from the app's usage log: <b>{total_runs:,}</b> AI runs between {first_day} and {last_day}
across six demo organisations, <b>{money(total_cost, 2)}</b> spent in total.</p>
<h3>Tokens per run, by agent (medians)</h3>
{table(["Agent", "Runs", "Input tokens", "Cached input", "Output tokens", "Cost per run", "Share of input cached"], per_agent_rows, "small")}
<h3>A typical run: one grant answer, start to finish</h3>
{table(["", "Input tokens", "Cached input", "Output tokens", "Cost"], [
 ("Typical (sum of the five agents' medians)", f'{TYPICAL["input"]:,.0f}', f'{TYPICAL["cached"]:,.0f}', f'{TYPICAL["output"]:,.0f}', money(TYPICAL["cost"])),
 ("The traced run above (first run, cache empty)", f"{trace_in:,}", "0", f"{trace_out:,}", money(trace_cost)),
], "small")}
<p class="src">Prices: input $0.10 per million tokens, cached input $0.01, cache write $0.125, output $0.50 (gpt-6-luna via
Portkey). {len(rows) - len(priced)} early test runs logged before prices were recorded are left out. Output tokens
include the model's reasoning tokens.</p>
<h3>Where the money goes</h3>
{SPEND_CHART}""")

page("Tokenomics", f"""
<h3 class="first">Cost per user per month</h3>
<p>A busy development director: four applications a month with four questions each, plus discovery and chat.
Each line uses that agent's measured average cost.</p>
{month_table}
<h3>At 100 and 10,000 users</h3>
{table(["Users", "AI cost per month", "AI cost per year"], [(f"{n:,}", money(c, 2), money(c * 12, 2)) for n, c in scale], "small")}
<p>Even at five times the heavy-user assumption, 10,000 users would cost about
{money(per_user_month * 5 * 10_000, 0)} a month in AI. At that scale hosting, support and data costs dominate; the AI
itself stays small, which is what makes a low price for very small nonprofits plausible.</p>
<h3>What we did to cut cost</h3>
<ul>
<li><b>Code before AI.</b> Keyword and rule-based triage filters search results first (115 of the traced search's
results were filtered out at no cost); only the rest get a Fit assessment.</li>
<li><b>Never pay twice.</b> Foundation pages are hashed and re-read by the AI only when their text changes; earlier
assessments are reused ("18 from earlier searches (no cost)").</li>
<li><b>Cache-friendly prompts.</b> Instructions and the organisation's library come first, in a stable order, so
the provider serves them from cache at a tenth of the price.</li>
<li><b>Small model, low reasoning, hard caps</b> on output tokens, requests and total tokens per run.</li></ul>""")

page("Tokenomics", f"""
<h3 class="first">Did the cuts hurt performance? An experiment</h3>
<p>The Fit Agent assessed the same six Cedar Ridge grants three ways: 18 real runs, logged separately so the app's
own health figures were untouched (<code>report/cost_experiment.py</code>).</p>
{exp_table}
{EXP_CHART}
{exp_text}
<div class="callout"><b>Conclusion.</b> Caching is a free saving. Low reasoning effort is enough for this
task; spending more did not make the agent's decisions better or more consistent. The real quality risk is
run-to-run variation on borderline grants, which is now listed as a limit with a planned fix.</div>""")

page("Safety", f"""
<h2><span class="n">5 · SAFETY</span>Thirteen attacks, thirteen defenses that held</h2>
<p><code>tests/safety_tests.py</code> attacks the app on a throwaway copy of the data and records what happened
(last run {safety_header}; full details in <code>tests/safety_results.md</code>).</p>
{table(["Risk", "Test", "Defense", "What happened"], safety_group_rows, "small")}""")

page("Safety", f"""
<h3 class="first">Defenses working in the app</h3>
<div class="two">
{img("14_injection_flagged.jpg", crop=(0.61, 0.0, 1.0, 0.72), width=1000, caption="<b>Prompt injection.</b> A pasted 'fellowship' tells grant-matching tools to record it as a Go. The instruction is shown in red as ignored; fit is 0% and eligibility fails in code.")}
{img("09_evidence.jpg", crop=(0.61, 0.28, 0.91, 1.0), width=1000, caption="<b>Invented facts.</b> The Evidence Checker marks two of the Writer's claims Contradicted and shows the source passage.")}
</div>
<h3>Overspending guards</h3>
<p>Every run is capped at 6 model calls, 120,000 tokens and 6,000 output tokens. Messages over 2,000 characters
and libraries over 120,000 characters are refused before any AI call, and uploads over 10 MB before they are read.
Agent health shows each agent's runs, cost and failures, and the Executive Director flags anything unusual.</p>
{img("11_health.jpg", crop=(0.08, 0.06, 0.92, 0.6), width=1300, caption="Agent health: every agent's runs, cost and checks.")}""")

page("Impact", f"""
<h2><span class="n">6 · IMPACT</span>Hours back for the communities we serve</h2>
<h3>A real user</h3>
{user_block}
<h3>Measured in the app</h3>
{table(["Task", "Today (typical)", "With Grant Compass (measured)", "Source"], [
 ("Judge whether one funder is worth applying to", "30–60 min reading guidelines", "19 s to read and score the San Antonio page", "Traced run"),
 ("First draft of one 250-word answer from your records", "1–2 hours", "6 s draft, plus editing", "Traced run"),
 ("Check every claim in an answer against your documents", "Often skipped", "6 s; caught 2 contradicted figures", "Traced run"),
 ("Board fundraising update", "1–2 hours compiling", "Under 10 s, every number checked", "Reports page"),
 ("Hiring a writer for one full foundation proposal", "$1,500–$5,000 flat fee (writers charge $30–150/h)", "Under $0.02 in AI per application", "Usage log; rate guides"),
], "small")}
<h3>What it adds up to</h3>
<p>A careful estimate, to be tested by the user session: if a development director saves even <b>5 hours per
application</b> on research, first drafts and fact-checking, four applications a month returns about <b>20 hours a
month</b>, half a work week, to programmes and funder relationships. <b>Newly possible:</b> a two-person nonprofit
can screen dozens of funders a month and fact-check every answer, which today only organisations with a paid
database and a dedicated grants team can do.</p>
""")

page("Limits", f"""
<h2><span class="n">7 · LIMITS AND NEXT STEPS</span>What doesn't work yet</h2>
<ul>
<li><b>Coverage.</b> 74 foundation websites can be read automatically; many funders publish only through
JavaScript portals or PDFs behind logins, and Texas and many other states have no open grants feed.</li>
<li><b>The writer still makes mistakes</b>, as the trace shows. The checker catches them, but a person must read
the result. The app never submits anything.</li>
<li><b>Borderline recommendations vary.</b> Asked twice about the same grant, the Fit Agent sometimes says
<i>Research further</i> once and <i>No-Go</i> the next. Fit scores are stable to a few points; the label isn't.</li>
<li><b>Quote checks are strict.</b> About a third of Fit assessments carry a quote that doesn't match word for word
(often a profile that changed since). The app shows these as warnings rather than hiding them.</li>
<li><b>Local only.</b> No hosting or shared team logins, and the login lockout is kept in memory. A real
deployment needs hosting, backups and a legal review of the privacy policy.</li>
<li><b>Fictional demo data.</b> The six organisations are realistic but invented.</li></ul>
<h3>With another month</h3>
<ul>
<li>Pilot with two or three real nonprofits and measure hours saved and win rate over a full grant cycle.</li>
<li>Run the Fit Agent twice on borderline grants and show "uncertain" when the runs disagree.</li>
<li>Read funder portals and PDFs behind links; add more state feeds and community foundations.</li>
<li><b>Deepen the organisation-knowledge side</b>, as the user review suggested: guided prompts to fill evidence
gaps the Evidence Checker finds, and outcome data that updates the library after every report.</li>
<li>Learn from outcomes: feed funders' feedback on losses back into Fit scores and the Coach.</li>
<li>Host it, with shared team accounts, roles, and a record of who approved each answer.</li></ul>
<h3>Sources</h3>
<ol class="src links">
<li><a href="https://candid.org/explore-issues/us-social-sector/money" target="_blank" rel="noopener">Candid, "Money in the US social sector"</a>: 1.9 million registered nonprofits, most under $1M.</li>
<li><a href="https://candid.org/blogs/data-insights-very-small-nonprofits-make-up-majority-us-nonprofits/" target="_blank" rel="noopener">Candid, "Very small nonprofits make up the majority of US nonprofits"</a> (May 2025): 22% vs 72%.</li>
<li><a href="https://ssir.org/articles/entry/grant-writing-infrastructure" target="_blank" rel="noopener">Stanford Social Innovation Review, "Grant-writing infrastructure"</a>, citing GrantStation's 2023 State of Grantseeking report: 68%; 2 days to 4 weeks per proposal.</li>
<li><a href="https://smartygrants.com.au/articles/smartystats-reveal-how-applicants-are-lodging-forms" target="_blank" rel="noopener">SmartyGrants, "SmartyStats"</a>: median about 48 hours per application to philanthropic funders (Australia).</li>
<li><a href="https://grantable.co/how-much-does-a-grant-writer-cost" target="_blank" rel="noopener">Grantable, "How much does a grant writer cost? (2026)"</a>: freelance writers charge $30–150 an hour (about $75 mid-level), or flat fees of $1,500–$5,000 per foundation proposal. Grantable sells AI grant-writing software, so treat its figures as an upper-middle estimate.</li>
<li>Pricing: Instrumentl (<a href="https://aitoolsbakery.com/blog/instrumentl-pricing/" target="_blank" rel="noopener">AI Tools Bakery</a>, <a href="https://grantsights.com/blog/instrumentl-pricing" target="_blank" rel="noopener">Grantsights</a>); Candid Foundation Directory (<a href="https://grantsights.com/blog/candid-foundation-directory-pricing" target="_blank" rel="noopener">Grantsights</a>); Grantable (<a href="https://grantable.co/docs/billing/plans" target="_blank" rel="noopener">Grantable plans</a>).</li>
<li>Grant Compass evidence in the repository: <a href="https://github.com/GabriellaSaven/grant-compass/blob/master/tests/safety_results.md" target="_blank" rel="noopener">safety test results</a>, <a href="https://github.com/GabriellaSaven/grant-compass/blob/master/report/cost_experiment.json" target="_blank" rel="noopener">cost experiment</a>, <a href="https://github.com/GabriellaSaven/grant-compass/blob/master/report/user_review.md" target="_blank" rel="noopener">user review</a>. Token counts come from the app's usage logs, which stay on the computer running the app (they are excluded from git) and are summarised in section 4.</li></ol>""")

assert len(PAGES) == 15, len(PAGES)

CSS = """
:root{--ink:#1f2a26;--muted:#5b5a55;--line:#e3ded4;--paper:#fffefb;--green:#2f5d50;--soft:#eef4f0}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-snap-type:y proximity}
body{margin:0;background:#e9e5dd;color:var(--ink);font:10.5pt/1.5 Inter,-apple-system,"Segoe UI",Roboto,sans-serif}
.page{width:8.5in;height:11in;margin:28px auto;background:var(--paper);padding:.6in .7in .75in;position:relative;
 box-shadow:0 8px 30px rgba(0,0,0,.08);border-radius:6px;overflow:hidden;scroll-snap-align:start;scroll-margin-top:20px}
.pfoot{position:absolute;left:.7in;right:.7in;bottom:.35in;display:flex;justify-content:space-between;font-size:8pt;color:#9a978f;border-top:1px solid var(--line);padding-top:6px}
h1,h2,h3,h4{font-family:"Iowan Old Style","Palatino Linotype",Georgia,serif;font-weight:600;line-height:1.2;margin:0}
h1{font-size:46pt;margin:8px 0 10px} h1 em{color:var(--green)}
h2{font-size:20pt;margin:0 0 12px} h2 .n{display:block;font:600 9pt Inter,sans-serif;letter-spacing:.1em;color:var(--green);margin-bottom:5px}
h3{font-size:13.5pt;margin:16px 0 6px} h3.first{margin-top:0} h4{font-size:11.5pt;margin:0 0 4px}
p{margin:0 0 8px} ul,ol{margin:4px 0 8px;padding-left:20px} li{margin:2px 0} a{color:var(--green)}
.big{font-family:"Iowan Old Style",Georgia,serif;font-size:14.5pt;line-height:1.4;color:var(--ink)}
.eyebrow{font-size:9pt;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-top:1in}
.lede{font-size:14pt;line-height:1.45;color:#3d3c38;font-family:"Iowan Old Style",Georgia,serif;max-width:6in}
.meta{display:grid;grid-template-columns:90px 1fr;gap:5px 14px;margin:26px 0 18px;padding:14px 18px;background:#fff;border:1px solid var(--line);border-radius:10px}
.meta b{color:var(--muted);font-weight:500}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0 26px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-family:"Iowan Old Style",Georgia,serif;font-size:21pt;color:var(--green);line-height:1.1;margin-bottom:4px}
.kpi span{font-size:8.5pt;color:var(--muted);line-height:1.3;display:block}
.toc{list-style:none;padding:0;columns:1;max-width:4.6in} .toc li{display:flex;justify-content:space-between;border-bottom:1px dotted #cfc9bd;padding:5px 0}
.toc a{text-decoration:none;color:var(--ink)} .toc span{color:var(--muted)}
.statgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:8px 0 14px}
.statgrid div{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.statgrid b{display:block;font-family:"Iowan Old Style",Georgia,serif;font-size:16pt;color:var(--green);margin-bottom:3px}
.statgrid span{font-size:8.5pt;color:var(--muted);line-height:1.35;display:block}
.why{background:var(--soft);border-left:4px solid var(--green);padding:12px 16px;border-radius:8px;margin-top:12px}
.why h3{margin-top:0}
table{width:100%;border-collapse:collapse;margin:6px 0 10px;font-size:9pt;background:#fff;border:1px solid var(--line)}
table.small{font-size:8.3pt}
th{background:#f6f3ee;text-align:left;font-weight:600;color:var(--muted);font-size:8pt}
th,td{padding:4px 6px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.35}
figure{margin:6px 0 10px} figure img{width:100%;border:1px solid var(--line);border-radius:8px;display:block}
figcaption{font-size:8.3pt;color:var(--muted);margin-top:4px;line-height:1.35}
.step{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;margin:4px 0 12px}
.step p{font-size:9.3pt} .step figure{margin:0} .step img{max-height:2.8in;object-fit:cover;object-position:top}
.tok{font-size:8pt;color:var(--green);background:var(--soft);display:inline-block;padding:3px 9px;border-radius:999px}
.diagram{width:100%;height:auto;background:#fff;border:1px solid var(--line);border-radius:10px;padding:4px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:8pt;color:var(--muted);margin:4px 0 10px}
.sw{display:inline-block;width:20px;height:0;border-top:3px solid #7aa892;vertical-align:middle;margin-right:5px}
.sw.dash{border-top:2px dashed #b9b2a4} .sw.dot{border-top:2px dotted #b9b2a4}
.sw.dark{height:9px;width:9px;border:0;border-radius:50%;background:var(--green)}
.callout{background:var(--soft);border-left:4px solid var(--green);padding:9px 14px;border-radius:8px;margin:10px 0}
.todo{background:#fff7d6;border:1px dashed #d8b63a;padding:8px 12px;border-radius:8px;margin:8px 0;font-size:9.5pt}
.todo-inline{background:#fff7d6;border:1px dashed #d8b63a;padding:1px 6px;border-radius:6px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px} .home img{max-height:2.7in;object-fit:cover;object-position:top} .two img{max-height:4.1in;object-fit:cover;object-position:top}
.bars{margin:6px 0 4px}.bar{display:grid;grid-template-columns:1.9in 1fr 1.6in;gap:10px;align-items:center;margin:4px 0;font-size:9pt}
.bt{background:#efebe4;border-radius:999px;height:10px;overflow:hidden}.bt i{display:block;height:100%;background:var(--green);border-radius:999px}
.bv{color:var(--muted);font-size:8.5pt}
blockquote{margin:6px 0;padding:8px 12px;background:#fff;border:1px solid var(--line);border-left:4px solid var(--green);
 border-radius:8px;font-family:"Iowan Old Style",Georgia,serif;font-size:10.5pt;line-height:1.4}
blockquote.side{background:var(--soft);border-color:transparent;border-left-color:var(--green);font-size:11pt}
.quotes{display:grid;grid-template-columns:1fr 1fr;gap:8px} .quotes blockquote{margin:0}
.cite{font-size:8pt;color:var(--muted);margin:-2px 0 8px 16px}
.links a{color:var(--green);text-decoration:underline;text-underline-offset:2px}
.src{font-size:8pt;color:var(--muted)} code{background:#f1eee8;padding:1px 4px;border-radius:4px;font-size:8.5pt}
/* navigation */
.nav{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);display:flex;align-items:center;gap:6px;background:#1f2a26;color:#fff;
 padding:6px 8px;border-radius:999px;box-shadow:0 8px 24px rgba(0,0,0,.2);font:500 13px Inter,sans-serif;z-index:10}
.nav button{all:unset;cursor:pointer;padding:6px 12px;border-radius:999px} .nav button:hover{background:rgba(255,255,255,.12)}
.nav button[disabled]{opacity:.35;cursor:default}
.nav .where{min-width:170px;text-align:center} .nav select{font:inherit;background:transparent;color:#fff;border:0;cursor:pointer}
.nav select option{color:#1f2a26}
@media (max-width:900px){.page{transform-origin:top center}}
@media print{body{background:#fff} .nav{display:none} .page{margin:0;box-shadow:none;border-radius:0;break-after:page}
 .todo{display:none} html{scroll-snap-type:none}}
@page{size:letter;margin:0}
"""

JS = """
const pages=[...document.querySelectorAll('.page')], sel=document.getElementById('go'), where=document.getElementById('where');
const prev=document.getElementById('prev'), next=document.getElementById('next');
let cur=0;
function show(i){i=Math.max(0,Math.min(pages.length-1,i));pages[i].scrollIntoView({behavior:'smooth',block:'start'});}
function mark(i){cur=i;sel.value=i;where.textContent=`Page ${i+1} of ${pages.length}`;prev.disabled=i===0;next.disabled=i===pages.length-1;
 history.replaceState(null,'','#p'+(i+1));}
const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting)mark(pages.indexOf(e.target))})},{threshold:.5});
pages.forEach(p=>io.observe(p));
prev.onclick=()=>show(cur-1); next.onclick=()=>show(cur+1); sel.onchange=()=>show(+sel.value);
document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;
 if(['ArrowRight','ArrowDown','PageDown',' '].includes(e.key)){e.preventDefault();show(cur+1)}
 if(['ArrowLeft','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();show(cur-1)}
 if(e.key==='Home'){e.preventDefault();show(0)} if(e.key==='End'){e.preventDefault();show(pages.length-1)}});
document.querySelectorAll('a[href^="#p"]').forEach(a=>a.onclick=e=>{e.preventDefault();show(+a.getAttribute('href').slice(2)-1)});
window.addEventListener('load',()=>{const m=location.hash.match(/^#p(\\d+)/); if(m&&pages[+m[1]-1]) pages[+m[1]-1].scrollIntoView({block:'start'});});
"""

sections = []
for i, (label, h) in enumerate(PAGES, 1):
    sections.append(f'<section class="page" id="p{i}">{h}<div class="pfoot"><span>Grant Compass · {AUTHOR}</span>'
                    f'<span>{label} · {i} / {len(PAGES)}</span></div></section>')
options = "".join(f'<option value="{i}">{i + 1}. {label}</option>' for i, (label, _) in enumerate(PAGES))
nav = (f'<nav class="nav" aria-label="Pages"><button id="prev" title="Previous page (←)">← Prev</button>'
       f'<span class="where" id="where">Page 1 of {len(PAGES)}</span>'
       f'<select id="go" aria-label="Jump to page">{options}</select>'
       f'<button id="next" title="Next page (→)">Next →</button></nav>')

OUT.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Grant Compass · Final report · {AUTHOR}</title><style>{CSS}</style></head>
<body>{''.join(sections)}{nav}<script>{JS}</script></body></html>""")
print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB) · {len(PAGES)} pages · runs {total_runs} · "
      f"per user/month {money(per_user_month, 3)} · trace {money(trace_cost, 4)}")

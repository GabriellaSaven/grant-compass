"""Build report/slides.html: a 10-slide reveal.js deck (reveal.js 5.2.1 from a CDN; screenshots and diagram embedded).

Reuses the report's numbers and diagram, so the two always agree (and rebuilds the report). The demo slides use
16:9 screenshots from report/slide_shots.py and step through them with reveal.js fragments: each click brings in
the next screen or callout. Press S for speaker notes, F for full screen, Esc for an overview.
    .venv/bin/python report/build_slides.py"""

import base64
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import build_report as R  # noqa: E402  (builds the report and exposes its figures)

OUT = R.REPORT / "slides.html"
SLIDE_SHOTS = R.SHOTS / "slide"
REVEAL = "https://cdn.jsdelivr.net/npm/reveal.js@5.2.1"


def data_uri(path: Path, width: int = 1800) -> str:
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def screen(name: str, markers, frag: int | None = None, label: str = "") -> str:
    """A 16:9 app screenshot with numbered markers. markers = [(number, x%, y%, fragment index)]."""
    dots = "".join(f'<span class="mk fragment" data-fragment-index="{i}" style="left:{x}%;top:{y}%">{n}</span>'
                   for n, x, y, i in markers)
    cls = "screen" + (" fragment" if frag is not None else "")
    attr = f' data-fragment-index="{frag}"' if frag is not None else ""
    tag = f'<span class="screen-label">{label}</span>' if label else ""
    return (f'<div class="{cls}"{attr}><img src="{data_uri(SLIDE_SHOTS / f"{name}.jpg")}" alt="{R.esc(label)}">'
            f'{tag}{dots}</div>')


def steps(items) -> str:
    """Callouts beside a screen. items = [(number, html, fragment index)]; the current one is bright."""
    lis = "".join(f'<li class="fragment fade-in-then-semi-out" data-fragment-index="{i}"><b>{n}</b><span>{t}</span></li>'
                  for n, t, i in items)
    return f'<ol class="steps">{lis}</ol>'


def notes(text: str) -> str:
    return f'<aside class="notes">{text}</aside>'


S = R.exp["summary"]
cache_saving = 1 - S["A_shipped"]["mean_cost"] / S["B_no_cache_order"]["mean_cost"]
reasoning_extra = S["C_medium_reasoning"]["mean_cost"] / S["A_shipped"]["mean_cost"] - 1
ten_k = R.per_user_month * 10_000
passed, total = sum(s["passed"] for s in R.safety), len(R.safety)
T = R.TRACE

slides = []

# 1 · Title
slides.append(f"""
<section class="title" data-background-color="#1f2a26">
<p class="kicker">MGT409 AI Foundations · Final project</p>
<h1>Grant <em>Compass</em></h1>
<p class="pitch">An AI development team for small nonprofits: it finds grants that fit, tells you honestly
whether to apply, and helps you write answers that are true to your own records.</p>
<p class="by">{R.AUTHOR}</p>
<p class="repo">Public repo: <a href="{R.REPO_URL}">{R.REPO_URL}</a><br><code>git clone {R.REPO_URL}.git</code></p>
{notes("Before business school I was a fundraiser. Grant Compass is the tool I wanted in that job.")}
</section>""")

# 2 · Problem
slides.append(f"""
<section>
<p class="kicker">The problem</p>
<h2>I was a fundraiser. Most of my week went to paperwork.</h2>
<div class="cols">
<div class="lead">
<p>Searching funder sites to check eligibility. Rebuilding last year's answers for new word limits.
Checking every number before it went out. Then reports, then the board update.</p>
<p class="em">Small nonprofits don't lose grants because of bad programmes. They lose them because one or two people
can't find the time.</p>
</div>
<div class="stats">
<div><b>1.9M</b><span>US nonprofits, most under $1M a year</span></div>
<div><b>68%</b><span>say time is their biggest grant-seeking challenge</span></div>
<div><b>~48 h</b><span>median time per foundation application</span></div>
<div><b>22% vs 72%</b><span>of very small vs other nonprofits win even one foundation grant</span></div>
</div></div>
<p class="source">Sources: Candid; GrantStation 2023 via SSIR; SmartyGrants</p>
{notes("Who has it: the one or two people in a small nonprofit who do the grants and the programmes. Today: "
       "spreadsheets, funder sites one by one, last year's answers, ChatGPT that can invent numbers. Why care: every "
       "hour on paperwork is an hour not spent on the community.")}
</section>""")

# 3 · What is new
slides.append(f"""
<section>
<p class="kicker">What is new</p>
<h2>Not a database, not a chatbot: a team that checks itself</h2>
<table class="cmp">
<thead><tr><th></th><th>Finds grants</th><th>Judges fit vs your documents</th><th>Drafts</th><th>Checks claims vs your records</th><th>Price</th></tr></thead>
<tbody>
<tr><td>Instrumentl</td><td>✓</td><td>keywords</td><td>✓</td><td>—</td><td>$299–999/mo</td></tr>
<tr><td>Candid FDO</td><td>✓</td><td>—</td><td>—</td><td>—</td><td>≈$1,200+/yr</td></tr>
<tr><td>Grantable</td><td>basic</td><td>—</td><td>✓</td><td>—</td><td>$0–150/mo</td></tr>
<tr><td>ChatGPT</td><td>—</td><td>what you paste</td><td>✓</td><td>can invent numbers</td><td>$0–20/mo</td></tr>
<tr class="us"><td>Grant Compass</td><td>✓</td><td>✓ quotes verified</td><td>✓ your docs only</td><td>✓</td><td>≈{R.money(R.per_user_month, 2)}/mo AI</td></tr>
</tbody></table>
<p class="rule">The AI may only say what your records support, <b>and code, not the AI, checks that it did.</b></p>
{notes("Honest: Instrumentl and Candid are better databases; a freelance writer writes better prose. What's new "
       "is the combination and the verification.")}
</section>""")

# 4 · Agents
slides.append(f"""
<section>
<p class="kicker">How the agents work</p>
<h2>Seven colleagues with narrow jobs. You decide at the two moments that matter.</h2>
<div class="diagram-wrap">{R.DIAGRAM}</div>
<p class="small">gpt-6-luna via Portkey for every call, low reasoning effort. Fit %, eligibility and quote checks are
computed in code. The Executive Director sees only metrics, never documents.</p>
{notes("Research reads a funder and hands facts to Fit, which scores them against the library. You decide Go/No-Go. "
       "The Writer drafts; the Coach and Evidence Checker review in parallel; you approve. The Executive Director "
       "supervises from metrics; the Assistant is a read-only chat layer.")}
</section>""")

# 5 · Demo 1: find and judge
slides.append(f"""
<section class="demo">
<p class="kicker">Live demo 1 of 2 · Cedar Ridge Veterans Collaborative, San Antonio</p>
<h2>Find a funder, and get an honest answer on whether to apply</h2>
<div class="demo-grid">
<div class="r-stack stage">
{screen("discover", [(1, 8.5, 26, 0), (2, 57.5, 46, 1)], label="Discover")}
{screen("fit", [(3, 10, 33, 3), (4, 20, 23, 4), (5, 8.5, 80, 5)], frag=2, label="Go / No-Go · San Antonio Area Foundation")}
{screen("pipeline", [(6, 60, 63, 7), (7, 72, 79.5, 8)], frag=6, label="Pipeline")}
</div>
{steps([
    (1, "<b>One search</b> across Grants.gov and 74 foundation sites: 18 matches", 0),
    (2, "Ranked by fit; 114 filtered out by code first, at no AI cost", 1),
    (3, "A real funder link read and scored in 19 s: <b>59%</b>, computed in code", 3),
    (4, "Every score is explained, with the funder's words and yours, checked word for word", 4),
    (5, "An honest call: <b>Research further</b>, not Go", 5),
    (6, "Into the pipeline: deadline, risk and progress update themselves", 7),
    (7, "The next action for every grant, in one place", 8),
])}
</div>
{notes("Click through: Discover, then the Go/No-Go card for the real San Antonio Area Foundation page, then the "
       f"pipeline. Research + Fit for this grant: {R.money(T['research_agent']['cost_usd'] + T['fit_agent']['cost_usd'], 4)}. "
       "The friend who tested it said the pipeline was their favourite part.")}
</section>""")

# 6 · Demo 2: write and check
slides.append(f"""
<section class="demo">
<p class="kicker">Live demo 2 of 2 · same application</p>
<h2>Draft, coach and fact-check an answer, and catch the AI's mistake</h2>
<div class="demo-grid">
<div class="r-stack stage">
{screen("draft", [(1, 27, 55, 0), (2, 69, 17.5, 1)], label="Draft with AI")}
{screen("coach", [(3, 61.5, 23, 3), (4, 61.5, 53.5, 4), (5, 34.5, 60, 5)], frag=2, label="Review suggestions · Grant Coach")}
{screen("evidence", [(6, 61.5, 34, 7), (7, 61.5, 46.5, 8)], frag=6, label="Evidence Checker")}
</div>
{steps([
    (1, "<b>Draft with AI</b>: 174 of 250 words from Cedar Ridge's own documents, in 6 s", 0),
    (2, "The library passages it drew on, approved language first", 1),
    (3, "The Coach scores it <b>65/100</b> from ten weighted categories", 3),
    (4, "Does it answer each part of the question? ✓ ◐ ✕", 4),
    (5, "Suggestions tied to exact words. You accept or reject; it never rewrites for you", 5),
    (6, "Evidence Checker: 7 supported, 2 weak, 1 needs evidence, <b>2 contradicted</b>", 7),
    (7, "It caught the Writer labelling Q1 2026 figures as 2025-26, and shows the source", 8),
])}
</div>
{notes(f"Whole run, five agents: {R.money(R.trace_cost, 4)} and about 40 seconds of AI time. One agent made a mistake "
       "and another caught it before a funder could. That is the design.")}
</section>""")

# 7 · Cost
A_, B_, C_ = S["A_shipped"], S["B_no_cache_order"], S["C_medium_reasoning"]


def cost_bar(label, sub, cost, top, verdict, ours=False):
    return (f'<div class="cbar{" ours" if ours else ""}"><div class="cl"><b>{label}</b><span>{sub}</span></div>'
            f'<div class="ct"><i style="width:{100 * cost / top:.0f}%"></i></div>'
            f'<div class="cv"><b>${cost * 1000:.2f}</b><span>{verdict}</span></div></div>')


top = max(A_["mean_cost"], B_["mean_cost"], C_["mean_cost"])
slides.append(f"""
<section class="cost">
<p class="kicker">Cost to run</p>
<h2>Running Grant Compass costs less than a cent per grant answer</h2>
<div class="big4">
<div><b>{R.money(R.trace_cost, 3)}</b><span><strong>One grant answer:</strong> find the funder, judge the fit, draft, coach and fact-check (5 AI agents)</span></div>
<div><b>{R.money(R.per_user_month, 2)}</b><span><strong>One busy fundraiser for a month</strong> (4 applications, plus search and chat)</span></div>
<div><b>{R.money(R.per_user_month * 100, 0)}</b><span><strong>100 users</strong> a month</span></div>
<div><b>{R.money(ten_k, 0)}</b><span><strong>10,000 users</strong> a month</span></div>
</div>
<p class="compare">For comparison: a freelance grant writer charges about <b>$75 an hour</b>, or a <b>$1,500–5,000 flat fee</b> for one full foundation proposal; a grant database like Instrumentl costs <b>$299+ a month</b>.
All figures measured from {R.total_runs} real AI runs.</p>
<div class="cols cost-cols">
<div><h3>How we keep it cheap</h3>
<ul class="plain">
<li><b>Free checks first.</b> Simple code rules drop poor matches before any AI is used.</li>
<li><b>Never pay twice.</b> A funder's page is re-read only if it has changed.</li>
<li><b>Reuse what repeats.</b> The instructions and your documents are sent the same way every time, so the AI provider
bills {A_["cached_share"]:.0%} of it at a tenth of the price.</li>
<li><b>A small, fast model</b> with spending caps on every run.</li></ul></div>
<div><h3>Did saving money make it worse? We tested it.</h3>
<p class="small test-sub">Same 6 grants, assessed 3 ways · AI cost per 1,000 assessments</p>
{cost_bar("Our setup", "cheap model + reuse", A_["mean_cost"], top, "the baseline", ours=True)}
{cost_bar("Without reuse", "same instructions, no caching", B_["mean_cost"], top, f"{B_['mean_cost'] / A_['mean_cost'] - 1:.0%} more, no better")}
{cost_bar("More AI 'thinking'", "medium reasoning effort", C_["mean_cost"], top, f"{C_['mean_cost'] / A_['mean_cost'] - 1:.0%} more, no better")}
<p class="verdict">Verdict: the cheap setup loses nothing, so we kept it.</p></div>
</div>
{notes("Reuse (caching) sends the identical prompt, so the answers can't get worse; it just costs 35% less. Extra "
       f"reasoning cost {reasoning_extra:.0%} more and took about 4 seconds longer, but on borderline grants the "
       "recommendation flips between 'Research further' and 'No-Go' whatever the setting (even running our own setting "
       "twice), so the extra spend bought nothing. We list that variation as a limit.")}
</section>""")

# 8 · Safety
def crop_uri(name, box, width=1100):
    im = Image.open(SLIDE_SHOTS / f"{name}.jpg").convert("RGB")
    w, h = im.size
    im = im.crop((round(box[0] * w), round(box[1] * h), round(box[2] * w), round(box[3] * h)))
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def risk(name, defense, proof):
    return f'<div class="risk"><b>{name}</b><span>{defense}</span><em>✓ {proof}</em></div>'


slides.append(f"""
<section class="safety2">
<p class="kicker">Safety · every risk in the brief, with a defense and a test that proves it</p>
<h2>{passed} of {total} attack and failure tests pass</h2>
<div class="sgrid">
<div class="scol"><h3>Attacks</h3>
{risk("Prompt injection", "Funder pages, documents and answers are treated as data. Planted instructions are flagged in red; scores and eligibility are computed in code.", "Tests 1–4: blocked or ignored; Coach still scored a 'give me 100' answer 20/100")}
{risk("Data leaks", "One database per organisation. Links can't reach this computer or a private network.", "Tests 10, 13: 0 leaks in 160 reads; 6 of 6 internal addresses refused")}
{risk("Misbehaviour", "Password guessing locks the account; oversized uploads are refused unread.", "Tests 11, 12: locked after 5 wrong passwords; 10 MB+ files refused")}
</div>
<div class="scol"><h3>Agent malfunction</h3>
{risk("Invented facts", "Every quote must match the source word for word. The Evidence Checker tests each claim; the Executive Director's numbers must match real metrics.", "Tests 8, 9: invented quote rejected; 2 made-up figures removed")}
{risk("Wrong action", "The chat assistant's tools are read-only, and it can only open the app's own pages. Nothing is submitted without you.", "Test 5: no tool can change data")}
{risk("Infinite loops", "Every run stops after 6 AI calls.", "Test 6: a runaway agent was stopped")}
</div>
<div class="scol"><h3>Overspending</h3>
{risk("Budget guards", "Per run: 6 calls, 120,000 tokens, 6,000 output tokens. Messages over 2,000 characters and libraries over 120,000 are refused before any AI call. Agent health shows each agent's cost.", "Tests 6, 7: stopped and refused with 0 AI calls")}
<div class="suite"><b>{passed}/{total} passed</b><span>The whole suite attacks a throwaway copy of the data and costs about $0.002:</span>
<code>python tests/safety_tests.py</code></div>
</div>
</div>
<div class="proofs">
<figure><img src="{crop_uri('injection', (0.6, 0.33, 1.0, 0.5))}" alt="Injection flagged">
<figcaption><b>Shown working:</b> a pasted 'grant' told the AI to score it a Go. The instruction is shown as ignored, and the fit is 0%.</figcaption></figure>
<figure><img src="{crop_uri('evidence', (0.6, 0.355, 0.9, 0.6))}" alt="Contradicted claims">
<figcaption><b>Shown working:</b> the Evidence Checker caught two figures the Writer got wrong, with the source.</figcaption></figure>
</div>
{notes("This slide follows the project brief's three groups. Attacks: injection, data leaks, misbehaviour. Agent "
       "malfunction: invented facts, wrong action, infinite loops. Overspending: budget guards. Every defense has an "
       "automated test, and two are shown working in the app on the bottom row.")}
</section>""")

# 9 · Impact
slides.append(f"""
<section>
<p class="kicker">Impact</p>
<h2>Hours back for the communities we serve</h2>
<div class="cols impact-cols">
<div class="quotes">
<blockquote>“It gets to the part that takes so much time in fundraising, which is working out whether something is
actually worth pursuing before you sink hours into an application.”</blockquote>
<blockquote>“I could genuinely see this saving a lot of time for a small fundraising team, especially where one person
is juggling research, deadlines and writing at the same time.”</blockquote>
<p class="small">A friend with grant-fundraising experience, after trying the app</p>
</div>
<div><table class="impact">
<thead><tr><th>Task</th><th>Today</th><th>With Grant Compass</th></tr></thead>
<tbody>
<tr><td>Judge one funder</td><td>30–60 min</td><td><b>19 s</b></td></tr>
<tr><td>First draft of an answer</td><td>1–2 h</td><td><b>6 s</b> + editing</td></tr>
<tr><td>Fact-check every claim</td><td>often skipped</td><td><b>6 s</b></td></tr>
<tr><td>Board update</td><td>1–2 h</td><td><b>under 10 s</b></td></tr>
<tr><td>Hiring a writer for one full proposal</td><td>$1,500–5,000 flat fee (≈$75/h)</td><td><b>under $0.02</b> of AI</td></tr>
</tbody></table>
<p class="em small">≈5 hours saved per application → about <b>20 hours a month</b> back for programmes.</p></div>
</div>
<div class="newly"><b>Newly possible:</b> a two-person nonprofit can screen dozens of funders a month and fact-check every
answer, work that today needs a paid database and a dedicated grants team.</div>
{notes("Times on the right were measured in the traced run; 'today' figures are typical ranges. The 5-hours-per-"
       "application figure is an estimate to test with real users.")}
</section>""")

# 10 · Next
slides.append(f"""
<section class="next">
<p class="kicker">What's next</p>
<h2>What it can't do yet, and what I'd build next</h2>
<div class="cols next-cols">
<div><h3>Where it falls short today</h3>
<ul class="plain">
<li><b>It can't read every funder.</b> Many post their guidelines behind logins or in scanned PDFs, so some still have
to be pasted in by hand.</li>
<li><b>The AI writer still makes mistakes.</b> In the demo it put the wrong year on two figures. The Evidence Checker
caught them, but a person should always read the final answer.</li>
<li><b>It can change its mind on close calls.</b> Asked twice about a borderline grant, it may say "Research further"
once and "No-Go" the next.</li>
<li><b>It hasn't met a real nonprofit's files yet.</b> It runs on one computer, with six realistic but invented
organisations.</li></ul></div>
<div><h3>With another month</h3>
<ul class="plain">
<li><b>Try it with 2–3 real nonprofits</b> for a full grant cycle, and measure the hours saved and grants won.</li>
<li><b>Say "uncertain" honestly</b> when the AI gives two different answers on the same grant, instead of picking one.</li>
<li><b>Help teams build their evidence</b> (my tester's top request): prompt for missing numbers, and update the
library after every funder report.</li>
<li><b>Put it online</b> so a whole development team can share one workspace.</li></ul></div>
</div>
<div class="closing">
<p class="close">Less time on paperwork. More time with the people we serve.</p>
<p class="close-sub">The tool I wish I'd had as a fundraiser.</p>
</div>
<p class="repo-end">Public repo: <a href="{R.REPO_URL}">{R.REPO_URL}</a> · <code>git clone {R.REPO_URL}.git</code></p>
{notes("Close on the person: this is the tool I wanted when I was the one doing the grants.")}
</section>""")

assert len(slides) <= 10, len(slides)

CSS = """
.reveal{color:#1f2a26;font-family:Inter,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:26px}
.reveal .slides{text-align:left}
.reveal .slides section{height:100%;padding:6px 0}
.reveal h1,.reveal h2,.reveal h3{font-family:"Iowan Old Style","Palatino Linotype",Georgia,serif;font-weight:600;text-transform:none;letter-spacing:0;color:#1f2a26}
.reveal h1{font-size:96px;margin:0 0 18px;color:#fff} .reveal h1 em{color:#a7d1bf}
.reveal h2{font-size:42px;line-height:1.15;margin:0 0 20px} .reveal h3{font-size:26px;margin:0 0 8px;color:#2f5d50}
.reveal p,.reveal li{line-height:1.4} .reveal ul{margin:0 0 0 1em} .reveal li{margin:6px 0} .reveal ul li{font-size:24px}
.reveal a{color:#2f5d50} .reveal code{font-size:.85em;background:#f1eee8;padding:2px 8px;border-radius:6px}
.kicker{font:600 15px Inter,sans-serif!important;letter-spacing:.12em;text-transform:uppercase;color:#2f5d50;margin:0 0 6px!important}
section.title{display:flex!important;flex-direction:column;justify-content:center;padding-left:40px!important;color:#fff}
.title .kicker{color:#a7d1bf}
.title .pitch{font-family:"Iowan Old Style",Georgia,serif;font-size:34px;line-height:1.35;color:#e8efe9;max-width:1000px}
.title .by{font-size:22px;color:#cfd8d3;margin-top:36px}
.title .repo{font-size:22px;color:#e8efe9;margin-top:10px;line-height:1.7} .title .repo a{color:#a7d1bf}
.title .repo code{background:rgba(255,255,255,.1);color:#fff}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:start}
.lead p{font-size:26px} .em{font-family:"Iowan Old Style",Georgia,serif;font-size:28px;color:#2f5d50}
.stats,.big4{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.big4{grid-template-columns:repeat(4,1fr);margin-bottom:24px}
.stats div,.big4 div{background:#fff;border:1px solid #e3ded4;border-radius:14px;padding:16px 18px}
.stats b,.big4 b{display:block;font-family:"Iowan Old Style",Georgia,serif;font-size:44px;color:#2f5d50;line-height:1.05}
.big4 b{font-size:40px} .stats span,.big4 span{font-size:17px;color:#5b5a55;display:block;line-height:1.3;margin-top:4px}
.source,.small{font-size:16px!important;color:#5b5a55} .small{margin-top:12px}
.reveal table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e3ded4}
.reveal table th,.reveal table td{padding:10px 14px;border-bottom:1px solid #e3ded4;text-align:left;font-size:23px}
.reveal table th{font-size:16px;color:#5b5a55;background:#f6f3ee;font-weight:600;letter-spacing:.02em;text-transform:uppercase}
tr.us td{background:#eef4f0;font-weight:600;color:#2f5d50}
.rule{font-family:"Iowan Old Style",Georgia,serif;font-size:34px;margin-top:32px}
.diagram-wrap svg{width:100%;height:auto;max-height:440px;background:#fff;border:1px solid #e3ded4;border-radius:14px}
.legend{display:flex;gap:22px;flex-wrap:wrap;font-size:15px;color:#5b5a55;margin:8px 0 0}
.sw{display:inline-block;width:24px;height:0;border-top:3px solid #7aa892;vertical-align:middle;margin-right:6px}
.sw.dash{border-top:2px dashed #b9b2a4} .sw.dot{border-top:2px dotted #b9b2a4}
.sw.dark{height:11px;width:11px;border:0;border-radius:50%;background:#2f5d50}
/* demo screens */
.demo h2{font-size:36px;margin-bottom:14px}
.demo-grid{display:grid;grid-template-columns:880px 1fr;gap:24px;align-items:start}
.stage{width:880px;height:495px}
.screen{position:relative;width:880px;height:495px;border-radius:12px;overflow:hidden;
 box-shadow:0 14px 40px rgba(31,42,38,.18),0 0 0 1px #d9d3c7;background:#fff}
.screen img{width:100%;height:100%;margin:0;display:block;object-fit:cover}
.screen-label{position:absolute;left:12px;bottom:12px;background:rgba(31,42,38,.88);color:#fff;font-size:14px;font-weight:600;
 padding:5px 12px;border-radius:999px;letter-spacing:.02em}
.mk{position:absolute;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;background:#c4472c;color:#fff;
 font:700 18px/34px Inter,sans-serif;text-align:center;box-shadow:0 0 0 4px rgba(196,71,44,.25),0 4px 10px rgba(0,0,0,.25)}
ol.steps{list-style:none;margin:0;padding:0}
ol.steps li{display:grid;grid-template-columns:34px 1fr;gap:12px;align-items:start;font-size:19px;line-height:1.35;margin:0 0 12px}
ol.steps li > b{width:30px;height:30px;border-radius:50%;background:#c4472c;color:#fff;font:700 16px/30px Inter,sans-serif;text-align:center}
.safety-list ul.tight{margin-top:10px} .safety-list ul.tight li{font-size:19px;margin:6px 0}
/* impact */
.quotes blockquote{margin:0 0 16px;width:auto;padding:16px 20px;background:#eef4f0;border-left:5px solid #2f5d50;border-radius:10px;
 box-shadow:none;font-family:"Iowan Old Style",Georgia,serif;font-size:24px;font-style:normal;line-height:1.35;text-align:left}
.impact-cols{grid-template-columns:1fr 1.05fr}
.cost h2{font-size:38px;margin-bottom:14px}
.cost .big4{margin-bottom:10px} .cost .big4 b{font-size:36px} .cost .big4 span{font-size:15.5px} .big4 strong{color:#1f2a26}
.compare{font-size:17px!important;color:#5b5a55;margin:0 0 14px}
.cost-cols{grid-template-columns:.85fr 1.15fr;gap:30px} .cost h3{font-size:24px;margin-bottom:6px}
ul.plain{list-style:none;margin:0;padding:0} ul.plain li{font-size:20px;margin:0 0 12px;line-height:1.35}
.test-sub{margin:0 0 8px!important}
.cbar{display:grid;grid-template-columns:150px 1fr 150px;gap:12px;align-items:center;margin:0 0 9px}
.cl b{display:block;font-size:17px} .cl span{display:block;font-size:13px;color:#5b5a55;line-height:1.2}
.ct{background:#efebe4;border-radius:999px;height:16px;overflow:hidden} .ct i{display:block;height:100%;background:#b9b2a4;border-radius:999px}
.cbar.ours .ct i{background:#2f5d50}
.cv b{display:block;font-size:19px;color:#1f2a26} .cv span{display:block;font-size:13px;color:#5b5a55;line-height:1.2}
.verdict{margin-top:10px!important;padding:9px 14px;background:#eef4f0;border-left:4px solid #2f5d50;border-radius:8px;font-size:18px;font-weight:600;color:#2f5d50}
.safety2 h2{font-size:36px;margin-bottom:12px}
.sgrid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.scol h3{font-size:21px;margin:0 0 6px;padding-bottom:4px;border-bottom:2px solid #2f5d50}
.risk{margin:0 0 9px} .risk b{display:block;font-size:17px;color:#1f2a26}
.risk span{display:block;font-size:14.5px;line-height:1.32;color:#3d3c38}
.risk em{display:block;font-style:normal;font-size:13.5px;line-height:1.3;color:#2f5d50;font-weight:600;margin-top:2px}
.suite{background:#1f2a26;color:#e8efe9;border-radius:10px;padding:10px 12px;margin-top:6px}
.suite b{display:block;font-size:22px;color:#a7d1bf} .suite span{display:block;font-size:12.5px;line-height:1.3;margin:2px 0 6px}
.suite code{background:rgba(255,255,255,.12);color:#fff;font-size:12.5px}
.proofs{display:grid;grid-template-columns:1.15fr 1fr;gap:16px;margin-top:6px}
.proofs img{width:100%;height:150px;object-fit:cover;object-position:top left;border:1px solid #e3ded4;border-radius:8px;margin:0;display:block}
.proofs figcaption{font-size:13px;line-height:1.3;color:#5b5a55;margin-top:4px}
.next h2{margin-bottom:14px} .next-cols{gap:40px} .next ul.plain li{font-size:18.5px;margin:0 0 11px}
.closing{margin-top:14px;padding:16px 24px;background:#1f2a26;border-radius:14px;text-align:center}
.closing .close{color:#fff;margin:0;font-size:32px} .closing .close-sub{color:#a7d1bf;margin:4px 0 0;font-size:20px;font-family:"Iowan Old Style",Georgia,serif;font-style:italic}
.newly{margin-top:22px;padding:16px 22px;background:#1f2a26;color:#e8efe9;border-radius:12px;font-size:23px;line-height:1.4}
.newly b{color:#a7d1bf}
.close{font-family:"Iowan Old Style",Georgia,serif;font-size:30px;color:#2f5d50;margin-top:30px;text-align:center}
.repo-end{text-align:center;font-size:19px!important;color:#5b5a55;margin-top:20px}
.reveal .progress{color:#2f5d50} .reveal .controls{color:#2f5d50}
.reveal .slide-number{background:transparent;color:#5b5a55;font-size:14px;right:70px;bottom:14px}
.deck-foot{position:fixed;left:24px;bottom:14px;font:500 13px Inter,sans-serif;color:#8d8a82;z-index:5}
.deck-foot a{color:#8d8a82}
#no-reveal{display:none;position:fixed;top:0;left:0;right:0;background:#c4472c;color:#fff;font:600 15px Inter,sans-serif;
 padding:10px 16px;z-index:99;text-align:center}
"""

OUT.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Grant Compass · Slides · {R.AUTHOR}</title>
<link rel="stylesheet" href="{REVEAL}/dist/reveal.css">
<style>{CSS}</style></head>
<body>
<div id="no-reveal">The slide engine (reveal.js) couldn't load from the internet, so the slides are shown as one page.
Connect to the internet and reload.</div>
<div class="reveal"><div class="slides">{''.join(slides)}</div></div>
<div class="deck-foot">Grant Compass · {R.AUTHOR} · <a href="{R.REPO_URL}">{R.REPO_URL.replace('https://', '')}</a></div>
<script src="{REVEAL}/dist/reveal.js"></script>
<script src="{REVEAL}/plugin/notes/notes.js"></script>
<script>
if (!window.Reveal) {{ document.getElementById('no-reveal').style.display = 'block'; }}
else Reveal.initialize({{width:1280,height:720,margin:0.04,hash:true,slideNumber:'c/t',transition:'slide',
  controls:true,progress:true,center:false,plugins:window.RevealNotes ? [RevealNotes] : []}});
</script>
</body></html>""")
print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB) · {len(slides)} slides")

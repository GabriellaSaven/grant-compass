"""Build report/slides.html: a 10-slide reveal.js deck (reveal.js from a CDN; screenshots and diagram embedded).

Reuses the report's numbers, screenshots and diagram, so the two always agree. Rebuilds the report too.
    .venv/bin/python report/build_slides.py
Arrow keys move between slides, F goes full screen, Esc shows an overview."""

import base64
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import build_report as R  # noqa: E402  (builds the report and exposes its figures)

OUT = R.REPORT / "slides.html"
REVEAL = "https://cdn.jsdelivr.net/npm/reveal.js@5.2.1/dist"


def src(name: str, crop=None, width: int = 1400) -> str:
    im = Image.open(R.SHOTS / name).convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((round(crop[0] * w), round(crop[1] * h), round(crop[2] * w), round(crop[3] * h)))
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def shot(name, crop=None, cap="", width=1400, cls=""):
    return (f'<figure class="{cls}"><img src="{src(name, crop, width)}" alt="{R.esc(cap)}">'
            + (f"<figcaption>{cap}</figcaption>" if cap else "") + "</figure>")


S = R.exp["summary"]
cache_saving = 1 - S["A_shipped"]["mean_cost"] / S["B_no_cache_order"]["mean_cost"]
reasoning_extra = S["C_medium_reasoning"]["mean_cost"] / S["A_shipped"]["mean_cost"] - 1
ten_k = R.per_user_month * 10_000
passed, total = sum(s["passed"] for s in R.safety), len(R.safety)

slides = []

slides.append(f"""
<section class="title" data-background-color="#1f2a26">
<p class="kicker">MGT409 AI Foundations · Final project</p>
<h1>Grant <em>Compass</em></h1>
<p class="pitch">An AI development team for small nonprofits: it finds grants that fit, tells you honestly
whether to apply, and helps you write answers that are true to your own records.</p>
<p class="by">{R.AUTHOR}</p>
<p class="repo">Public repo: <a href="{R.REPO_URL}">{R.REPO_URL}</a><br><code>git clone {R.REPO_URL}.git</code></p>
</section>""")

slides.append("""
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
<p class="source">Candid; GrantStation 2023 via SSIR; SmartyGrants</p>
</section>""")

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
</section>""")

slides.append(f"""
<section>
<p class="kicker">How the agents work</p>
<h2>Seven colleagues with narrow jobs; you decide at the two moments that matter</h2>
<div class="diagram-wrap">{R.DIAGRAM}</div>
<p class="small">gpt-6-luna via Portkey for every call, low reasoning effort. Fit %, eligibility and quote checks are
computed in code; the Executive Director sees only metrics, never documents.</p>
</section>""")

T = R.TRACE
slides.append(f"""
<section>
<p class="kicker">Demo · one real run</p>
<h2>A real funder page to a fit score in 19 seconds</h2>
<div class="cols demo">
{shot("03_discover.jpg", (0.1, 0.46, 0.58, 0.93), "Discover: Grants.gov + 74 foundations, ranked by fit", cls="tall")}
{shot("05_import_fit.jpg", (0.61, 0.5, 1.0, 0.98), "San Antonio Area Foundation: 59%, Research further, every bar explained", cls="tall")}
</div>
<p class="small">Cedar Ridge Veterans Collaborative (demo, San Antonio) · Research Agent + Fit Agent:
{T["research_agent"]["input_tokens"] + T["fit_agent"]["input_tokens"]:,} input / {T["research_agent"]["output_tokens"] + T["fit_agent"]["output_tokens"]:,} output tokens ·
{R.money(T["research_agent"]["cost_usd"] + T["fit_agent"]["cost_usd"], 4)}</p>
</section>""")

slides.append(f"""
<section>
<p class="kicker">Demo · draft, coach, check</p>
<h2>The Evidence Checker caught the Writer's mistake</h2>
<div class="cols three">
{shot("07_draft.jpg", (0.275, 0.28, 0.605, 1.0), "Draft with AI: 174 words from Cedar Ridge's own documents, 6 s", 900, "tall")}
{shot("08b_coach_card.jpg", (0.61, 0.28, 0.91, 1.0), "Grant Coach: 65/100, what the question asks, 6 suggestions", 900, "tall")}
{shot("09_evidence.jpg", (0.61, 0.28, 0.91, 1.0), "Evidence Checker: 7 supported, 2 contradicted, with the source", 900, "tall")}
</div>
<p class="small">The Writer labelled Q1 2026 figures as 2025-26 results; the checker flagged both before a funder could.
Whole run, five agents: <b>{R.money(R.trace_cost, 4)}</b>.</p>
</section>""")

slides.append(f"""
<section>
<p class="kicker">Cost to run</p>
<h2>Under a cent per grant, measured from {R.total_runs} real runs</h2>
<div class="big4">
<div><b>{R.money(R.trace_cost, 3)}</b><span>find, assess, draft, coach and check one answer</span></div>
<div><b>{R.money(R.per_user_month, 2)}</b><span>per active user per month</span></div>
<div><b>{R.money(R.per_user_month * 100, 0)}</b><span>per month for 100 users</span></div>
<div><b>{R.money(ten_k, 0)}</b><span>per month for 10,000 users</span></div>
</div>
<div class="cols">
<div><h3>Cost cuts</h3><ul>
<li>Code filters results before any AI call</li>
<li>Pages re-read only when they change</li>
<li>Cache-friendly prompts: <b>{S["A_shipped"]["cached_share"]:.0%}</b> of input cached</li>
<li>Small model, low reasoning, hard caps</li></ul></div>
<div><h3>Did they hurt quality? (18-run test)</h3><ul>
<li>Caching: <b>{cache_saving:.0%} cheaper</b>, same prompt, no quality cost</li>
<li>Medium reasoning: <b>{reasoning_extra:+.0%} cost</b>, slower, decisions no more consistent</li>
<li>So: keep it small, and flag borderline calls</li></ul></div>
</div>
</section>""")

slides.append(f"""
<section>
<p class="kicker">Safety</p>
<h2>{passed} of {total} attack and failure tests passed</h2>
<div class="cols safety">
<div><ul class="tight">
<li><b>Prompt injection</b> in funder pages, documents and answers: ignored, flagged in red, scores computed in code</li>
<li><b>Invented facts</b>: quotes must match word for word; the Director's numbers must match real metrics</li>
<li><b>Wrong actions</b>: the chat assistant's tools are read-only</li>
<li><b>Data leaks</b>: one database per organisation; links can't reach private networks</li>
<li><b>Overspending and loops</b>: 6 calls, 120k tokens per run; size limits before any AI call</li></ul>
<p class="small">Reproduce: <code>python tests/safety_tests.py</code> (about $0.002)</p></div>
{shot("14_injection_flagged.jpg", (0.61, 0.0, 1.0, 0.62), "A planted instruction, shown as ignored. Fit 0%.", 900, "tall")}
</div>
</section>""")

slides.append(f"""
<section>
<p class="kicker">Impact</p>
<h2>Hours back for the communities we serve</h2>
<div class="cols">
<div class="quotes">
<blockquote>“It gets to the part that takes so much time in fundraising, which is working out whether something is
actually worth pursuing before you sink hours into an application.”</blockquote>
<blockquote>“The Grant Coach feels much more useful than just asking ChatGPT to rewrite something because it actually
tells you what is missing.”</blockquote>
<p class="small">A friend with grant-fundraising experience, after trying the app</p>
</div>
<div><table class="impact"><tbody>
<tr><td>Judge one funder</td><td>30–60 min</td><td><b>19 s</b></td></tr>
<tr><td>First draft of an answer</td><td>1–2 h</td><td><b>6 s</b> + editing</td></tr>
<tr><td>Fact-check every claim</td><td>often skipped</td><td><b>6 s</b></td></tr>
<tr><td>Board update</td><td>1–2 h</td><td><b>&lt; 10 s</b></td></tr>
<tr><td>Writer per proposal</td><td>$1,500–5,000</td><td><b>&lt; $0.02</b> AI</td></tr>
</tbody></table>
<p class="em small">≈5 hours saved per application → about <b>20 hours a month</b> back for programmes.</p></div>
</div>
</section>""")

slides.append(f"""
<section>
<p class="kicker">What's next</p>
<h2>Honest limits, and the next month</h2>
<div class="cols">
<div><h3>Doesn't work yet</h3><ul>
<li>Many funders hide behind portals and PDFs</li>
<li>The writer still makes mistakes (the checker catches them)</li>
<li>Borderline Go / No-Go calls vary between runs</li>
<li>Runs locally; demo data is fictional</li></ul></div>
<div><h3>With another month</h3><ul>
<li>Pilot with 2–3 real nonprofits over a grant cycle</li>
<li>Run twice on borderline grants; show "uncertain"</li>
<li>Deepen the organisation-knowledge side</li>
<li>Host it, with shared team accounts</li></ul></div>
</div>
<p class="close">Software does the searching, drafting and checking.<br>People spend their hours on the communities they serve.</p>
<p class="repo-end">Public repo: <a href="{R.REPO_URL}">{R.REPO_URL}</a> · <code>git clone {R.REPO_URL}.git</code></p>
</section>""")

assert len(slides) <= 10, len(slides)

CSS = """
:root{--r-background-color:#fbfaf7;--r-main-color:#1f2a26;--r-heading-color:#1f2a26;--r-link-color:#2f5d50;
 --r-main-font:Inter,-apple-system,"Segoe UI",Roboto,sans-serif;--r-heading-font:"Iowan Old Style","Palatino Linotype",Georgia,serif;
 --r-main-font-size:26px;--r-heading-text-transform:none;--r-heading-font-weight:600;--r-heading-letter-spacing:0}
.reveal{color:#1f2a26;font-family:Inter,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:26px}
.reveal .slides{text-align:left}
.reveal h1,.reveal h2,.reveal h3{font-family:"Iowan Old Style","Palatino Linotype",Georgia,serif;font-weight:600;text-transform:none;letter-spacing:0}
.reveal section.title{display:flex!important;flex-direction:column;justify-content:center;padding-left:40px}
.legend{display:flex;gap:22px;flex-wrap:wrap;font-size:15px;color:#5b5a55;margin:8px 0 0}
.sw{display:inline-block;width:24px;height:0;border-top:3px solid #7aa892;vertical-align:middle;margin-right:6px}
.sw.dash{border-top:2px dashed #b9b2a4} .sw.dot{border-top:2px dotted #b9b2a4}
.sw.dark{height:11px;width:11px;border:0;border-radius:50%;background:#2f5d50}
.reveal ul li{font-size:24px}
.reveal .slides section{height:100%;padding:8px 0}
.reveal h1{font-size:96px;margin:0 0 18px;color:#fff} .reveal h1 em{color:#a7d1bf}
.reveal h2{font-size:44px;line-height:1.15;margin:0 0 22px} .reveal h3{font-size:26px;margin:0 0 8px;color:#2f5d50}
.reveal p,.reveal li{line-height:1.4} .reveal ul{margin:0 0 0 1em} .reveal li{margin:6px 0}
.kicker{font:600 16px Inter,sans-serif!important;letter-spacing:.12em;text-transform:uppercase;color:#2f5d50;margin:0 0 6px!important}
.title .kicker{color:#a7d1bf} .title{color:#fff}
.title .pitch{font-family:"Iowan Old Style",Georgia,serif;font-size:34px;line-height:1.35;color:#e8efe9;max-width:1000px}
.title .by{font-size:22px;color:#cfd8d3;margin-top:40px} .title .by a{color:#a7d1bf}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:start}
.cols.three{grid-template-columns:1fr 1fr 1fr;gap:20px}
.lead p{font-size:26px} .em{font-family:"Iowan Old Style",Georgia,serif;font-size:28px;color:#2f5d50}
.stats,.big4{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.big4{grid-template-columns:repeat(4,1fr);margin-bottom:24px}
.stats div,.big4 div{background:#fff;border:1px solid #e3ded4;border-radius:14px;padding:16px 18px}
.stats b,.big4 b{display:block;font-family:"Iowan Old Style",Georgia,serif;font-size:44px;color:#2f5d50;line-height:1.05}
.big4 b{font-size:40px} .stats span,.big4 span{font-size:17px;color:#5b5a55;display:block;line-height:1.3;margin-top:4px}
.source,.small{font-size:16px!important;color:#5b5a55} .small{margin-top:14px}
table.cmp,table.impact{width:100%;border-collapse:collapse;font-size:24px;background:#fff;border:1px solid #e3ded4}
.reveal table th,.reveal table td{padding:9px 12px;border-bottom:1px solid #e3ded4;text-align:left}
.reveal table th{font-size:17px;color:#5b5a55;background:#f6f3ee;font-weight:600}
tr.us td{background:#eef4f0;font-weight:600;color:#2f5d50}
.rule{font-family:"Iowan Old Style",Georgia,serif;font-size:34px;margin-top:34px}
.diagram-wrap svg{width:100%;height:auto;max-height:440px;background:#fff;border:1px solid #e3ded4;border-radius:14px}
.reveal figure{margin:0} .reveal figure img{width:100%;margin:0;border:1px solid #e3ded4;border-radius:10px;display:block;object-fit:cover;object-position:top}
.reveal figure.tall img{max-height:470px} .demo figure img{max-height:470px}
.reveal figcaption{font-size:16px;color:#5b5a55;margin-top:6px;line-height:1.3}
.safety{grid-template-columns:1.25fr 1fr} ul.tight li{font-size:22px;margin:9px 0}
.quotes blockquote{margin:0 0 16px;width:auto;padding:16px 20px;background:#eef4f0;border-left:5px solid #2f5d50;border-radius:10px;
 box-shadow:none;font-family:"Iowan Old Style",Georgia,serif;font-size:25px;font-style:normal;line-height:1.35;text-align:left}
table.impact td{font-size:24px;padding:12px 12px}
.title .repo{font-size:22px;color:#e8efe9;margin-top:14px;line-height:1.6} .title .repo a{color:#a7d1bf}
.title .repo code{background:rgba(255,255,255,.1);color:#fff;padding:3px 10px;border-radius:6px;font-size:20px}
.repo-end{text-align:center;font-size:20px!important;color:#5b5a55;margin-top:24px} .repo-end code{font-size:18px} .repo-end a{color:#2f5d50}
.close{font-family:"Iowan Old Style",Georgia,serif;font-size:30px;color:#2f5d50;margin-top:34px;text-align:center}
.reveal .progress{color:#2f5d50} .reveal .controls{color:#2f5d50} .reveal .slide-number{background:transparent;color:#5b5a55;font-size:14px}
"""

OUT.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Grant Compass · Slides · {R.AUTHOR}</title>
<link rel="stylesheet" href="{REVEAL}/reveal.css">
<style>{CSS}</style></head>
<body><div class="reveal"><div class="slides">{''.join(slides)}</div></div>
<script src="{REVEAL}/reveal.js"></script>
<script>Reveal.initialize({{width:1280,height:720,margin:0.05,hash:true,slideNumber:'c/t',transition:'slide',
 controls:true,progress:true,center:false}});</script>
</body></html>""")
print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB) · {len(slides)} slides")

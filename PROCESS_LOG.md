# Process Log — Grant Compass

A running record of how I built this project with an AI coding assistant
(Claude Code): what I asked for, what came back, and what I decided. Prompts
are summarized, not quoted word for word.

---

## 2026-10-17 — Setup and requirements

**1. Project folder.** I asked the assistant to create a folder for my final
project. It found an empty `Final Project` folder already in the course
directory, used that, and created a Python virtual environment inside it
(following my course rule that every project folder gets its own `.venv`).

**2. Reading the requirements.** I shared the link to the final project
requirements. The assistant read the page and summarized the deliverables
(GitHub repo, `report.html`, `slides.html`, optional demo video), the
deadline (Oct 26, 6 PM), the grading rubric, and the rules that shape the
build. The key rules: the app must find `.env` in its own folder or the one
above it, it may only use `gpt-6-luna` on the course key, and every report
section needs real evidence (measured token counts, a safety defense shown
working, a real user).

## 2026-10-17 — Choosing the idea

**3. Describing the problem.** I explained a problem I have seen repeatedly
in nonprofit fundraising: grant teams lose time finding opportunities,
deciding which ones are worth pursuing, pulling information together from
many places, and rewriting similar material. Existing AI tools mostly
generate text. They don't help decide whether a grant is a good fit, whether
the organization is ready, or whether claims in a draft are supported.

The assistant agreed the idea avoids the course's "overdone ideas" list as
long as the **Go/No-Go decision and evidence-grounded writing** are the
centre of the app, not just drafting. It flagged that the full workflow is too
much to build well in 9 days and suggested building the whole flow for one
opportunity at a time: **Find → Decide → Plan → Draft → Check**. It proposed
five agents (Scout, Fit & Eligibility Analyst, Readiness Planner, Writer,
Reviewer) and asked me about a real test user, data sources and app format.

**4. My decisions.**
- **Competitors:** Candid is paid; Grantable and Grantboost focus on writing;
  Submittable and Fluxx focus on tracking. None covers the whole process.
  *The assistant noted that some tools (e.g. Instrumentl, Grantable) may do
  partial matching or tailoring, so I should verify each comparison before
  writing the report.*
- **Real user:** I have one who can test the app.
- **Data sources:** I will provide them.
- **Format:** a Dash web app that runs locally from a fresh clone.

## 2026-10-17 — First working version (Decide step)

The assistant built the first piece of the app:
- **Repo setup:** git repo, `.gitignore` (keeps `.env` and `.venv` out),
  `.env.example`, `requirements.txt`, README.
- **Model connection:** `gpt-6-luna` through Portkey, loading `.env` from the
  project folder first and then the parent folder.
- **Fit & Eligibility Analyst:** compares an organization profile against a
  funder opportunity and returns a structured scorecard: Go / Go with
  conditions / No-Go, a fit score, rule-by-rule eligibility, scored funder
  priorities, conditions, missing information and risks.
- **Safety built in from the start:**
  - Funder text is treated as untrusted; injected instructions are flagged
    and ignored.
  - Every quote the AI cites is checked word for word against the source
    document; invented quotes are flagged.
  - Per-run limits on requests and tokens to prevent overspending.
- **Tokenomics:** each run's input, cached and output tokens are shown in
  the app and saved to `logs/usage.jsonl`.
- **Test data:** a fictional organization (Riverbend Reads) and two
  fictional opportunities, a good fit and a poor fit. The poor fit includes a
  planted prompt injection.

**Results:** The good-fit sample came back Go (94/100). The poor-fit sample
came back No-Go (2/100), and the app caught and ignored the planted
injection. All quotes checked out. On the second run, 1,245 of 1,545 input
tokens were served from cache.

**Open items:** add gpt-6-luna prices so the app shows dollar costs; build
the Find step once I share data sources; get real documents from my test
user; verify competitor claims.

## 2026-10-17 — Keeping this log

**5.** I asked for a process log that describes my process rather than
recording prompts verbatim. The assistant created this file and will add an
entry for each new step.

## 2026-10-17 — Full product concept

**6. Writing up the full vision.** I wrote a detailed product concept: an AI
grant research and writing workspace with 12 features (Discover, Go/No-Go,
pipeline tracker, application planner, organisation knowledge base, writing
workspace, Grantwriting Coach, "does this answer the question?" checker,
evidence checker, approved answer library, budget/narrative consistency
checker, compliance checker), six agents with distinct jobs (Research, Fit,
Application Planner, Grant Writer, Grant Coach, Compliance), human-in-the-loop
rules, and a calm, editorial design direction. My project question: *can an
AI grant workspace reduce the time fundraisers spend finding and preparing
applications while maintaining or improving quality?* I asked the assistant to
review the concept before building anything.

**Review takeaways:**
- **Strengths:** the evidence discipline (Supported / Inferred / Missing), a
  fit score explained by its dimensions, the Coach as an editor rather than a
  ghostwriter, and human override at every step make the concept clearly
  different from generic AI writing tools.
- **Main risk is scope:** 12 features in about 9 days, with the report and
  slides worth 49 of 100 points. The assistant recommended a phased plan with
  a working core loop first.
- **Design suggestions:**
  - Compute the fit score from visible dimension scores and weights, not as
    a number the model invents.
  - Mark dimensions "Unknown" when there is no data.
  - Handle deadlines and pipeline statuses with plain date logic, not AI.
  - Merge the overlapping checkers into the Coach and Compliance agents.
  - Keep the whole organisation library in a cached prompt prefix instead of
    building a search index.
- **Measuring the project question:** time a real task with and without the
  app, and have the test user (not the AI) judge quality, so the AI is not
  grading its own work.

## 2026-10-17 — Phase 1 build

**7. Go-ahead for Phase 1.** I approved the phased plan. The assistant built
the core loop:

- **Organisation Library:** upload PDF, Word, text or Markdown files; mark
  documents as *approved organisational language*. The whole library is the
  agents' source of truth and sits in a cached prompt prefix.
- **Discover + Research Agent:** import a funder page from an approved site
  (allowlist in config; other sites are refused) or paste text. The agent
  extracts funder, programme, deadline, geography, eligibility, award,
  restrictions, requirements and source. The user reviews the result, then
  saves it to the pipeline.
- **Fit Agent (rebuilt):** scores eight dimensions (mission, geography,
  population, funding amount, strategy, evidence readiness, relationship,
  effort). Each score comes with a rationale, quotes and a
  Supported / Inferred / Missing label. It answers the nine Go / No-Go
  questions and recommends Go / Research further / No-Go, with why, concerns,
  risks, missing information and next steps.
  - **The app, not the AI, calculates the fit %.** It uses visible weights
    and leaves unknowns out.
  - **Code-level guards:** an eligibility gate forces No-Go, and quotes that
    can't be verified are downgraded from Supported to Inferred.
- **Human decision + override:** the user records Go / Research further /
  No-Go. Overriding the AI requires a reason and is shown as an override.
  Go creates a workback plan and moves the grant to Drafting.
- **Pipeline:**
  - Statuses Researching → Go / No-Go → Drafting → Internal Review → Ready to
    Submit → Submitted → Won / Lost, plus Declined.
  - Days remaining, progress, risk label (On Track / Needs Attention / At
    Risk / Critical) with reasons, outstanding tasks and responsible person.
  - All plain date logic, recalculated from today's date.
- **Homepage:** active opportunities, due this month, at risk, total
  potential funding, needs attention today, next 30 days, counts by stage.
- **Design:** restyled to a calm, editorial look with warm paper background,
  serif headings, deep green accent, and quiet dot-and-text status labels.
- **Sample data:** fictional nonprofit (Riverbend Reads) and six fictional
  funders, with deadlines relative to the day the app first runs.

**Tested (live gpt-6-luna runs and browser checks):**

| Test | Result |
|---|---|
| Buckeye Family Literacy Trust | Research further, 78% fit. The 25% match and missing information on reporting capacity and funder relationship were flagged; relationship scored Unknown, not guessed. |
| Great Lakes STEM (planted prompt injection) | No-Go, 7% fit. The injection was flagged and ignored; the eligibility gate fired. |
| Overriding the AI without a reason | Rejected. |
| Overriding with a reason | Saved and labelled as an override, a workback plan was created, and status moved to Drafting. |
| Ticking a task | Progress updated. |
| Discover sample import | Extracted correctly and saved to the pipeline. |
| Non-approved URL | Refused. |
| Word document upload | Parsed. |

**Findings to remember for the report:**
- **Repeated requests seem to be cached by Portkey.** Identical requests
  return byte-identical results and token counts. Tokenomics should be
  measured on distinct inputs, and checked against the Portkey dashboard.
- **Grants.gov search pages need JavaScript,** so real search will need its
  API or the data sources I provide.

**Open items:** gpt-6-luna prices for dollar costs; my data sources for real
search in Discover; real documents from my test user.

## 2026-10-17 — Organisation Profile

**8. Profile tab.** I asked for a Profile tab in the top right, where a
user builds the nonprofit's profile with a form. The profile is used to match
grants to the organisation and to help write applications.

The assistant built:
- **A structured form with nine sections:**
  - Basics
  - Mission & programmes
  - Who and where
  - Finances
  - Capacity
  - Outcomes & evidence
  - Funder relationships
  - Grant preferences (smallest award worth applying for, largest match,
    preparation time, areas to avoid)
  - Writing voice (tone, key messages, language to use or avoid)
- **Page features:** a completeness meter, section navigation, and a "What
  the AI reads" preview.
- **Top-right profile link:** shows the organisation's name and initials.
- **How the agents use it:** the profile is the first document in the
  agents' source of truth. Blank fields are passed as "Not provided" so they
  are reported as missing, never guessed. The Fit Agent's instructions now
  use grant preferences and funder relationships when scoring. The future
  Grant Writer will use the writing voice and key messages.
- **Sample data:** a profile for the fictional Riverbend Reads.

**Tested:**
- **Profile edit changes the assessment.** I added a board-chair connection
  to Buckeye Family Literacy Trust in the profile, then re-ran its
  assessment.
  - Existing relationship moved from Unknown to 5/5 Supported, quoting the
    profile word for word.
  - Fit rose from 78% to 82%.
  - The headline flagged that the funder's 25% match exceeds the "up to 10%"
    limit in our grant preferences.
- **Caching:** cached tokens were 0 on that run because the profile edit
  changed the cached prefix. The next unchanged run will hit the cache again.

**9. Fix: profile tracker out of sync.** I noticed the completeness
tracker said "Mission & programmes" was complete while those fields were
empty on screen.

- **Cause:** the tracker only recalculated when the profile was saved, so it
  showed the last saved version, not what was in the form.
- **Fix:**
  - The tracker now recalculates live from the form as you type or tick
    boxes.
  - It shows "Unsaved changes" until you save.
  - Text fields now report every keystroke.
  - The focus-area chips were restyled as clean pills with a tick.
- **Verified in the browser:** ticking a focus area moved the meter from 85%
  to 88% and showed "Unsaved changes". Unticking it returned to 85% and
  "Last saved".
- The "What the AI reads" preview still shows the saved version on purpose,
  because that is what the agents actually use.

## 2026-10-17 — Choosing the next step

**10. What to build next.** I asked whether Discover should be next and
offered to provide grant websites. The assistant agreed. Discover is the
biggest gap in the core loop: today it can only import one page or pasted
text.

**Proposed design:**
- **One adapter per source:** a public API where one exists (e.g. the
  Grants.gov search API), otherwise the source's listing pages.
- **Cheap triage first:** filter by deadline, geography, award size and
  focus area using the Profile. This is free and instant. Only the top
  matches go to the Research and Fit agents, which keeps costs down and gives
  a clear tokenomics story.
- **Ranked results:** a quick match reason for each, with "Assess" and
  "Save to pipeline" buttons.

**Suggested order:** Discover search next, then Phase 2 (writing workspace,
Grant Coach, evidence checker), which carries most of the "what is new"
value. Waiting on my list of source websites.

## 2026-10-17 — Checking grant sources for Discover

**11. Source websites.** I suggested five sites. The assistant checked each
one's robots.txt, whether pages load without a login, any public API, and
whether automated access is blocked:

| Site | Verdict | Why |
|---|---|---|
| simpler.grants.gov | **Use (via the Grants.gov API)** | Simpler's own API needs a key the graders won't have (401). The public Grants.gov search and fetchOpportunity APIs return the same federal data with no key, including deadline, award floor and ceiling, eligibility and description. |
| instrumentl.com | Don't use | Paid competitor. robots.txt specifically blocks AI agents (ClaudeBot, ChatGPT-User, etc.) from grant and foundation pages. |
| grantforward.com | Don't use | Search needs a login or institutional subscription; robots.txt disallows /grant*. |
| thegrantportal.com | Don't use | Listing pages are public, but the funder's website and application link need a paid subscription, and listings often show "Open / Ongoing" instead of amounts and dates, so Go/No-Go can't be grounded in evidence. |
| grantwatch.com | Don't use | Blocks automated tools with a bot check (HTTP 403 "Just a moment"). Bypassing that is off-limits. Also a paid service. |

**Competitor finding (important for the report):** Instrumentl calls itself
a "Full Cycle Grant Platform" with prospecting matches, writing tools and
award management. GrantWatch advertises profile-based "Best Fit" matching,
an AI grant writing tool, and grant pipelines. So "no one offers the full
package" is not accurate. Grant Compass's honest difference:
- explainable Go/No-Go with visible weights
- evidence labels with every quote checked against the source
- an eligibility gate the AI can't override
- a rule that missing facts are never invented
- (coming) a coach that critiques rather than rewrites

**Foundation grants gap:** none of the free, usable sources cover private
foundations. Options: keep single-page import for specific funders the team
already tracks, with those funders' domains added to the approved list.

**12. Why not GrantForward?** I asked why grantforward.com/search doesn't
work. The assistant re-checked the page with a "literacy" search. Three
reasons:
- **No grants in the page itself.** It loads (HTTP 200), but the HTML only
  holds the search form, filters and pop-ups. "Deadline" and "Amount" appear
  only as sort labels. The results are filled in afterwards by JavaScript.
- **The site's rules forbid automated access** to grant pages (/grant*) and
  to its data service (/api*).
- **Built for university researchers.** It is a subscription service: the
  page offers recommendations for "a researcher in my institution", a free
  trial and a login, and its AI assistant is for members only. Its listings
  lean toward research funding, not community nonprofit grants.

**13. Looking for other open grant lists.** I asked what other sources
could work. The assistant tested more candidates:

| Source | Verdict | Notes |
|---|---|---|
| California Grants Portal (data.ca.gov) | **Usable if the org is in California** | Official open data, no key, updated daily. Structured fields include status, agency, applicant type, categories, purpose and description; 34 matches for "literacy". State grants only. |
| ProPublica Nonprofit Explorer API | **Useful for funder research** | Free, no key. Gives 990 data on foundations (size, giving), not open calls. Could add a "funder snapshot" to Go/No-Go. |
| USAspending API | **Useful for context** | Free, no key. Past federal awards by place and keyword, showing who already wins this money locally. Not open calls. |
| Federal Register API | Skip | Free, but notices are noisy and mostly duplicate Grants.gov. |
| Philanthropy News Digest RFPs (Candid) | Gone | The old free RFP list now redirects to Candid's premium funding search. |
| fundsforNGOs | Don't use | Bot check (403). |

**Conclusion:** no free, open, allowed list of private foundation grants
exists. Paid databases (Candid, Instrumentl, GrantWatch) are the business
model for that data. The honest design:
1. Grants.gov API (federal)
2. A state open-data portal where one exists (e.g. California)
3. A funder watchlist: the team's own list of foundation and community
   foundation pages, re-checked by the Research Agent
4. Optional ProPublica funder snapshots

This limit belongs in the report's "Limits + next steps".

## 2026-10-17 — Discover search for any state

**14. Requirement: any nonprofit, any state.** I said the app must work for
a nonprofit in any state, not just one. The assistant built Discover around
sources that work everywhere, plus state plug-ins:

- **Federal: Grants.gov API.** Free, no key. Searches with the Profile's
  focus areas (or typed keywords), then pulls full details (deadline, award
  floor and ceiling, eligibility, cost sharing, description) for up to 60
  results in parallel. **No AI is needed**, because the data is already
  structured.
- **State portals as plug-ins.** California Grants Portal open data is
  included automatically when the Profile's state is California. For other
  states the page explains that there's no open feed yet and suggests adding
  state agency pages to the watchlist. A **State** field was added to the
  Profile.
- **Funder watchlist.** Any foundation or community-foundation page, in any
  state.
  - Adding a page approves that site for reading.
  - Each check hashes the page text. Unchanged pages reuse the last result,
    so **no AI is used**; only new or changed pages go to the Research Agent.
  - The app now also checks each site's robots.txt before fetching.
- **No-AI triage.** Every result is ranked against the Profile with plain,
  explainable rules, and every filtered result says why. Filters:
  - not open to nonprofits
  - international programme
  - research grant (unless Research is a chosen grant type)
  - deadline passed
  - award below your minimum
  - only a passing link to your focus areas

  The score (Strong / Possible / Weak) weighs: title/summary matches over
  body mentions, populations, deadline vs. preparation time, award size vs.
  budget, and eligibility. Watchlist funders are never hidden, only warned
  about.
- **Save to pipeline** works straight from a result. Federal and state
  saves use no AI.

**Tuning from live tests** (each found by checking real results):
1. Title X Family Planning ranked first because its description mentioned
   "literacy" once. Fix: title/summary matches now count much more than
   body mentions.
2. A US Embassy programme in Angola scored "Strong". Fix: international
   programmes (embassy, State Department, USAID) are filtered out.
3. An NIH R01 research grant ranked "Possible". Fix: research grants are
   filtered unless Research is one of the Profile's grant types.
4. With no focus areas in my Profile, everything scored the same. Fix: typed
   keywords now drive relevance on their own.
5. The population bonus let Title X back in through a "families" mention.
   Fix: the bonus only applies when the title or summary really matches.

**Results:**
- **Search speed:** 60 federal results plus one watchlist page in about
  5 seconds.
- **Change detection:** the Cleveland Foundation page cost 1,323 input
  tokens on the first check and 0 on the second (unchanged page).
- **Filtering:** "literacy, early childhood" gave 4 ranked matches, with
  47 filtered out, each with a reason.
- **Saving:** a federal result saved straight to the pipeline with no AI.
- **Cleanup:** test items were removed afterwards.

**Takeaway for the report:** this shows a layered cost design. Free rules
screen everything, the AI only reads pages that changed, and the expensive
Go/No-Go assessment only runs on what the team saves.

## 2026-10-18 — Status check

**15. Where are we?** I asked for a status update. Summary:
- **Built and tested:** Home, Discover, Pipeline, the Go/No-Go page with
  override, the Organisation Library, and the Profile.
- **Not committed:** nothing is in git yet, and there's no GitHub repo.
- **Still to do:**
  - Phase 2: writing workspace, Grant Coach, evidence checker
  - gpt-6-luna prices for dollar costs
  - a session with my real test user
  - `report.html` and `slides.html`
  - a fresh-clone dry run

8 days remain until the Oct 26 deadline.

**16. No commits.** I told the assistant not to commit anything until I say so. It saved this as a standing rule.

## 2026-10-18 — Phase 2: writing workspace, Grant Coach, evidence checker

**17. Phase 2.** I asked to start Phase 2 and come back to Discover later,
since finding grants from open sources is limited. The assistant built:

- **Three new agents with separate jobs:**
  - **Grant Writer** drafts one answer from the Organisation Library only.
    It follows the Profile's writing voice and key messages and prefers
    approved language. Every fact needs a cited source; gaps become
    [MISSING: …] placeholders.
  - **Grant Coach** works like a résumé reviewer. It breaks the question into
    the parts it really asks (the "does this answer the question?" check),
    scores ten categories 1–10, lists strengths and weaknesses with quotes,
    and gives specific suggestions and a top priority. It never rewrites.
  - **Evidence Checker** marks each claim as Supported / Weakly supported /
    Needs evidence / Contradicted, with the source quote.
- **Code-level guards:**
  - Word and character counts and limit checks are done in code.
  - The Coach's overall score is a weighted average using visible weights,
    minus 10 if over the limit.
  - Every quote is verified against the answer or the library. An
    unverifiable "Supported" becomes "Needs evidence", and a coach "Yes"
    without a real quote becomes "Partly".
- **Applications page:** progress per grant (answered, approved, average
  coach score, claims to fix).
- **Writing workspace:**
  - question list with status and word count
  - your own editor with a live count and "Unsaved changes"
  - version history labelled "you" or "AI draft (accepted by you)"
  - **Save as approved language**, which feeds the library
  - assistant tabs: Sources (no AI), Draft, Coach and Evidence
- **Standalone Grant Coach page** for any question and answer.
- **Human-in-the-loop:** AI drafts only reach the editor when the user
  chooses them, with a word-level diff of what would change. Nothing is
  saved until the user clicks Save, and only the user can mark an answer
  Approved.
- **Sample application:** four questions on the fictional Miami Valley
  grant. One sample answer is deliberately weak, with repetition, vague
  outcomes, an inflated "over 700 students" and an unsupported "leading
  provider" claim.

**Tested live:**

| Test | Result |
|---|---|
| Coach on the weak answer | 40/100. All four parts of the question only partly answered or missed; evidence 2/10, plain language 10/10. Top priority: add local evidence of need. |
| Evidence Checker on the weak answer | "Over 700 students" Contradicted (library says 612). "Leading literacy provider in Ohio" Needs evidence. "Transforms lives" Weakly supported. |
| Grant Writer on the outcomes question | 226/250 words, all sources verified, 3 [MISSING] placeholders (grant-specific targets, data sharing) instead of invented numbers. |
| Use this draft → Save | Draft entered the editor unsaved, then was saved as "AI draft (accepted by you)". |
| Coach on a strong, evidence-based answer | 72/100, against 40 for the weak one. Useful calibration evidence. |

**Fix found in testing:** the model sometimes wrapped quotes in its own
quotation marks, so they showed doubled. Quotes are now normalised.

## 2026-10-18 — Planning the last 8 days

**18. What's next?** The assistant proposed an order based on the rubric
(the report and slides are worth 49 points, and each report section needs
real evidence):
1. **User test kit.** A short script for my test user: a timed task done the
   usual way vs. with the app, plus a feedback form. Book this early; it is
   the strongest evidence for Impact and the top tier.
2. **Tokenomics.** A usage page in the app that turns `logs/usage.jsonl`
   into tokens per run, cost per run, per user per month, and at 100 and
   10,000 users. Needs gpt-6-luna prices. Measure on varied inputs because
   of Portkey's response caching.
3. **Safety tests.** Automated tests showing each defense working:
   - prompt injection ignored
   - eligibility gate
   - invented quotes downgraded
   - per-run token cap
4. **Optional Phase 3:** Application Planner and a pre-submission
   Compliance check, only if time allows.
5. **Report and slides** (`report.html`, `slides.html`) with embedded
   screenshots, then a fresh-clone dry run and GitHub (commit only when I
   say so).

**19. Where is the HTML file?** I asked why I could not see an HTML link in my folder. Answer: the app is not an HTML file. Dash builds its pages live while `python app.py` is running, at http://127.0.0.1:8050. The deliverable HTML files (`report.html`, `slides.html`) have not been created yet.

## 2026-10-18 — Discover: fit panel for each result

**20. Click a result to see its fit.** I asked that clicking a Discover
result open a panel on the right with a fit overview, in the format of my
example: Fit %, Why, Concerns, likely application effort, expected value,
recommendation. The score must be explained by its dimensions. From the
panel I should be able to add it to the pipeline or view the source.

**What changed:**
- **Results:** each result card is now clickable ("View fit →") and shows a
  "Fit %" tag once assessed.
- **Panel:** a right-side panel slides in with:
  - the facts and the free triage reasons
  - a Fit Agent assessment of that one result, without saving it first
  - the overview in my format, then "How the fit score is built" with all
    eight dimensions (score, weight, Supported / Inferred / Missing label;
    click a row for reasoning and quotes)
  - any injection, eligibility-gate or unverified-quote warnings, plus
    missing information and next steps
  - **Add to pipeline** and **View source**
- **Cost:** assessments are cached per result, so reopening is instant and
  uses no tokens. Adding to the pipeline carries the assessment over, so it
  is never paid for twice. The AI only runs when I click a result.

**Tested live:**
- **National Leadership Grants for Libraries:** Fit 36%, Research further.
  The Fit Agent noted it's a library-services grant while Riverbend works
  through schools, the cost share may exceed our 10% match limit, and the
  deadline is close to our 21-day preparation time.
- **Tribal Home Visiting:** Fit 18%, No-Go. Reopening was instant from the
  cache. Add to pipeline opened the opportunity page with the assessment
  already there (status Go / No-Go).
- **Cleanup:** the test opportunity was removed afterwards.

**21. Fit score on each card.** I asked for the fit score above "View fit →"
on each Discover result.
- **Assessed results** show the Fit Agent's score (e.g. "8%") coloured by
  its recommendation, with "Fit · No-Go" underneath.
- **Not yet assessed** results show "— Fit not assessed". The free triage
  score is deliberately not shown as "fit", so there's never a number
  without its explanation.
- **Live update:** the card's score updates as soon as an assessment
  finishes in the panel, without re-searching. Tested: Maternal, Infant and
  Early Childhood Home Visiting went from "not assessed" to "8% · No-Go".

**22. Tidier score boxes + "See in pipeline".** I said the fit scores were
not uniform or attractive, and asked for a "See in pipeline" link on results
already saved.
- **Uniform score box:** every result now has an identical bordered box
  (132 × 96 px) with a small "FIT" label, a large serif score coloured by
  recommendation, and the recommendation underneath. Unassessed results show
  "—" / "Not assessed" in the same box. Below it: "View fit →", or "Assess
  fit →" when not yet assessed.
- **See in pipeline:** saved results get a "See in pipeline →" link to their
  opportunity page. The link sits outside the clickable area, so following
  it never starts a paid assessment. In the side panel, "Add to pipeline"
  becomes "See in pipeline →" for saved items.
- **Verified in the browser:** all five boxes measured 132 × 96. The link
  went straight to /opportunity/7 without opening the panel.

**23. Dropped "existing relationship".** I asked to remove the existing
relationship dimension, because I won't be able to supply relationship data
for every organisation that uses the tool.
- **Fit Agent:** now scores seven dimensions. New weights: mission 25, and
  geography, population, strategy, evidence readiness and funding amount 15
  each. Application effort is still shown but not counted in fit.
- **Go/No-Go questions:** "Do we have an existing relationship with the
  funder?" was removed, leaving eight.
- **Profile:** "Funder relationships" became an optional "Funding history"
  section (current and past funders, used as evidence when drafting, not in
  scoring). The funder-contacts field was removed.
- **Saved assessments:** all 8 were re-scored in code with no new AI calls;
  this runs automatically on start and changes nothing on a second run. For
  example, Buckeye went from 82% to 81% because its 5/5 relationship score
  no longer counts.
- **Verified:** a fresh live assessment returned seven dimensions and eight
  questions, and the opportunity, Discover and Profile pages render without
  errors.

## 2026-10-18 — Import an opportunity found elsewhere

**24. Upload, link or paste → assess → pipeline or application.** I asked to
upload a grant application document (PDF or Word) I found offline, or give a
link, and have it assessed, added to the pipeline and sent to the
application editor, all from the Discover page.

**What was built:**
- **"Assess one you found" card on Discover:** drop a PDF or Word file,
  paste a link, or paste the text, then **Assess opportunity**. A **Sample**
  button loads a fictional application form with five numbered questions
  and limits.
- **Links:** a link I paste myself counts as my approval, so any site works
  (robots.txt is still respected). Links pointing directly to a PDF or Word
  file are read as documents.
- **Research Agent:** now also extracts the application's narrative
  questions, word for word, with word or character limits (page limits go
  to requirements). Code keeps only questions found word for word in the
  document.
- **Assessment:** the Fit Agent runs right away. The same right-side panel
  opens with the extraction cost, the questions found, the fit overview and
  dimensions, and these buttons:
  - **Add to pipeline:** saves the opportunity, its assessment and its
    questions.
  - **Add & start application:** also records my Go, builds the workback
    plan and opens the writing workspace with every question ready.
  - **View source** (for links).
- **Cost:** importing the same document twice reuses the saved assessment.
- **Reliability fix:** all agents now share one runner that closes its AI
  connection, which removed the "Event loop is closed" warnings.

**Tested live:**

| Test | Result |
|---|---|
| Word file (Python test) | 14 s. Extracted funder, deadline 15 Jan 2027, award $20k–$60k, and all 5 questions with limits (200/300/400/250 words, 1,000 characters). Fit 96%, Go. |
| Link not on the watchlist (Cleveland Foundation) | Worked. 0 questions found; 39%, No-Go (Cleveland-only funder). |
| Browser: Sample → Assess → panel | 92%, Go, 5 questions listed. |
| Add & start application | Opened the workspace with Q1–Q5 ready; due 15 Jan 2027, 89 days. |
| Browser: real Word file upload | Name shown, 96%, Go, 5 questions. The panel showed "See in pipeline" because the grant had just been added. |
| Cleanup | Test application removed afterwards. |

**25. Profile menu replaces the Library tab.** I asked for the top-right
profile button to become a dropdown with two choices: edit the profile, or
upload documents to use as sources for writing. I also asked to remove
"Organisation Library" from the header.
- **Profile button:** now a menu with **Edit profile** (mission, programmes,
  finances, preferences) and **Source documents** (upload reports, budgets
  and past applications). It closes when you pick an item or click outside.
- **Header:** now Home, Discover, Pipeline, Applications, Grant Coach.
- **Pages:** the library page is renamed **Source documents**
  (/profile/documents). Both profile pages have an "Edit profile | Source
  documents" switch at the top.
- **Wording:** in-app text now says "your Profile and source documents"
  instead of "Organisation Library".
- **Small fix:** large amounts now read "$1.56M" instead of "$1,560k".
- **Verified in the browser:** menu opens; Source documents shows all 6
  documents; the menu closes after choosing and on outside clicks; the
  header no longer lists the library.

**26. Team list.** I asked to be able to add people to the "Responsible"
list, and for that list to live in the top-right profile menu.
- **Storage:** the team is now stored in the database instead of being
  fixed in code. The three sample people are added on first run.
- **Team page:** a new third item in the profile menu and switch
  (/profile/team). It lists each person with the active grants they're
  responsible for, an Add form (name + optional role, duplicates refused),
  and Remove. Removing someone keeps their name on grants already assigned
  to them, so nothing is lost.
- **Responsible field:** each opportunity has **+ Add a person** under the
  field, which adds them to the Team and assigns them in one step. The
  dropdown always lists the current Team.
- **Verified in the browser:**
  - Added "Jordan Lee (Grant Writer)" from Buckeye's Responsible field. They
    became responsible immediately and showed on the Team page with
    Buckeye.
  - On the Team page, added "Alex Kim"; adding them again was refused as a
    duplicate.
  - Removed both test people and restored Buckeye to Maya Chen.

**27. Fix: Team page layout and Responsible on the Pipeline.** I said the
Team page looked broken, and that I couldn't choose who is responsible from
the Pipeline page.
- **Cause of the broken look:** my open browser tab was still using the
  stylesheet from before the restart (a refresh fixes that). The page was
  still redesigned so it holds up:
  - the Add form is stacked (Name, Role, full-width "Add to team")
  - each person has an initials avatar, name and role
  - their grants appear as "Responsible for" chips linking to each grant
  - a tidy Remove button
- **Pipeline:** the Responsible column is now a dropdown on every active
  row. It lists the Team, saves immediately and confirms ("Saved — Gem City
  Community Fund: Priya Nair"). A hint points to Profile → Team to manage
  the list.
- **Verified in the browser:** the Team page renders cleanly. Changing Gem
  City's Responsible person in the Pipeline saved to the database, and it
  was then restored to Maya Chen.

## 2026-10-18 — Fit scores appear automatically after a search

**28. No separate "assess" step.** I asked why some Discover results had no
fit score; assessments should be there as soon as results appear.
- **Why they were missing:** the Fit Agent only ran when I clicked a result,
  to save cost.
- **New behaviour:**
  1. The search shows results immediately, each score box reading
     "Assessing".
  2. A second step runs the Fit Agent on every match in parallel, 6 at a
     time.
  3. The list re-sorts by fit, best first, with a status line ("Fit assessed
     for N results · M from earlier searches (no cost)") and the total token
     usage.
  4. If one assessment fails, the others still finish, and the failure is
     listed.
- **Cost controls:**
  - Results filtered out by the free rules are never assessed.
  - Assessments are cached, so repeating a search is free.
  - The research-grant filter was widened (clinical or translational
    research, early investigator, research network, diagnostics), so medical
    research grants are screened out for free instead of costing an AI call.
- **Also fixed:** HTML entities in Grants.gov titles ("Parkinson&rsquo;s")
  are now decoded.

**Measured live:**

| Run | What happened |
|---|---|
| First search | Results shown in 2.5 s. 12 new assessments done in parallel in about 24 s; 7 came from the cache. 46,695 input tokens, of which 30,300 were cached (the shared Profile and documents), and 19,767 output tokens for 12 assessments. |
| Repeat search | 3 s, all 15 scores present, no AI cost. 4 medical research grants were now filtered out for free. |

**29. What is the funder watchlist?** I asked what the watchlist card is. Answer: a list of specific foundation or community-foundation grant pages the team already follows. Each search re-reads them, extracts any open opportunity, and ranks and assesses it alongside the federal results. It is the main way to bring private foundation grants into Discover, since no free open feed exists for them. My question suggests the card's wording is unclear.

**30. Watchlist card rewritten.** I asked for the card to be rewritten so
it's clear what it does.
- **New title:** "Foundations you follow". The source chip above the search
  bar is renamed to match.
- **Explanation:** a one-line why (federal listings don't include private
  foundations) and three numbered steps: paste the funder's grants page,
  search as usual (open calls appear tagged "Watchlist"), and pages are only
  re-read by the AI when they change.
- **Form:** labelled fields ("Funder's grants page", "Funder name") with
  example placeholders, and a full-width "Follow this funder" button.
- **Wording:** "Remove" is now "Unfollow".
- **Empty state:** suggests where to start (your community foundation,
  family foundations that funded you before, local corporate giving).

**31. Filtered results are clickable.** I asked to be able to click
filtered-out results so a fundraiser can double-check what they are.
- **Clickable list:** every item in "Filtered out" now opens the same
  right-side panel, tagged "Filtered out". The panel shows:
  - the reason it was skipped
  - what the grant is about
  - who can apply
  - focus and match requirement
  - Add to pipeline, Add & start application, and View source
- **No automatic AI:** filtered results are not assessed automatically, to
  keep the cost saving. An **Assess fit anyway** button runs the full Fit
  Agent on request, for when the rules may have got it wrong. A result
  assessed in an earlier search shows its saved fit straight away.
- **Tested live:** the Genome Sequencing Center (NIH research grant) opened
  with its description and eligibility; "Assess fit anyway" returned
  18% / No-Go, confirming the filter was right. Childhood Asthma, assessed in
  an earlier search, showed its saved 22% / No-Go instantly.

**32. "robots.txt does not allow…" explained.** I tried a Rockefeller
Foundation grants search link and got the robots.txt message. What it
means:
- **The block:** robots.txt is the file where a website says which pages
  automated tools may read. Rockefeller's says `Disallow: */?*`, meaning no
  URL with a "?" in it, which covers every search-results page. Grant
  Compass respects that. Its main /grants/ page is allowed.
- **The page itself:** it isn't a list of open opportunities. It searches
  grants Rockefeller has already made ("active and past grants within the
  past five years"), and Rockefeller's grants page says it does not accept
  unsolicited proposals. Useful for researching who they fund, but not
  something to apply to.
- **Change:** the error message now explains this in plain words and
  suggests trying the funder's main grants page or pasting the text.

**33. Is Zeffy's Grant Finder usable as a source?** The assistant checked
zeffy.com/grant-finder.
- **Good signs:** free with no paywall. robots.txt allows the grant-finder
  pages (only addresses ending in "=" are blocked), and it publishes a
  sitemap of 341 category pages.
- **The problem:** the grants themselves are not in the pages. The pages hold
  search filters and written guides ("How to find grants for youth
  development…"). The actual results are loaded afterwards by JavaScript
  from Zeffy's private, undocumented service. Grant Compass would only see
  the guide text.
- **Why not call that service directly:** it means reverse-engineering
  another company's internal system without permission. It could break or
  be blocked at any time, and Zeffy is a direct competitor. Not appropriate
  for a built-in source.
- **What does work:** use Zeffy by hand to spot grants, then paste the
  funder's own page link (or the text) into "Assess one you found".
  Partnering with Zeffy for official access is a "next steps" idea.
- **Competitor finding for the report:** Zeffy advertises a free grant
  finder with AI grant matching, application support tools and funder 990
  insights, and says post-award management is "not yet" available. It is a
  strong, free competitor to name honestly in "What is new". Grant Compass's
  difference is the explainable, evidence-checked Go/No-Go, the pipeline
  and the writing coach and evidence checker.

**34. Ford Foundation grant opportunities page.** The assistant checked
fordfoundation.org/work/our-grants/grant-opportunities/.
- **Access:** robots.txt allows everything, and the content is in the page
  itself (no JavaScript loading), so Grant Compass can read it.
- **What it lists:** Ford doesn't accept unsolicited proposals. The page
  links to only two limited opportunities: JustFilms (documentary film
  funding) and the New York City Good Neighbor Committee (NYC
  nonprofits).
- **Live test with "Assess one you found":**

  | Page | Time | Result |
  |---|---|---|
  | Good Neighbor Committee | 12 s | Applications currently closed; NYC organisations only. 43%, No-Go for the Ohio sample organisation. |
  | Main opportunities page | 11 s | Both programmes recognised and both closed. 14%, No-Go. |

- **Best use:** follow the main opportunities page under "Foundations you
  follow". It is only re-read by the AI when it changes, so a new Ford call
  for proposals will show up in Discover automatically, at almost no cost
  while nothing changes. This makes a good demo of the watchlist idea.

**35. Following Ford.** At my request, Ford Foundation's grant opportunities page was added to "Foundations you follow". The first check read it with the AI (both programmes currently closed). A second check found the page unchanged and used no AI, which confirms the change detection works on a real foundation page.

## 2026-10-18 — 100 grantmakers checked; 74 built into Discover

**36. Assess a list of 100 grantmakers.** I gave a list of 100 foundation,
corporate and community-foundation grants pages and asked which could be
added to Discover. Then (37) I asked for all usable ones to show up in
results automatically.

**Access check (no AI, all 100 in parallel):** each page was tested for
robots.txt permission, bot walls, HTTP errors and readable text.

| Result | Count |
|---|---|
| Readable as listed | 55 |
| Dead links (404) | 29 |
| Behind a bot check (HTTP 403) | 8 |
| Content only appears with JavaScript | 5 |
| robots.txt says no (e.g. Hewlett, MacArthur) | 3 |

- **Dead links:** many of the links in the list were outdated or wrong. An
  automatic page-finder read each funder's homepage and found the current
  grants page for 19 of the 29.
- **Total: 74 of 100 usable.** `FUNDER_SOURCES.md` lists every funder, its
  page and status, and why the 26 others are excluded.
- **Closed calls:** 20 usable pages say they don't take unsolicited
  proposals or are invitation-only. They're kept, because their pages
  change when a call opens. The free rules now send closed or
  invitation-only opportunities to "Filtered out" (still clickable), so
  they cost no assessment.

**Built in:**
- **"Major foundations (74)" source:** a built-in directory in Discover, on
  by default (`data/funder_directory.json`).
- **Shared code:** it uses the same change detection as the watchlist.
  Watchlist checks now also run in parallel.

**One-time read (performance lesson):**
- **Result:** 73 of 74 pages read by the Research Agent (PNC timed out):
  138,555 input and 22,724 output tokens.
- **Problem:** it took about 2 hours, because the AI service slowed down
  under that many requests.
- **Fixes:**
  - Results ship in `data/funder_directory_cache.json`, so a fresh clone
    starts with them.
  - Each foundation page is refreshed at most once a day; otherwise the
    stored result is used.
  - A page that failed is skipped until the next day.
- **After the fix:** loading all 73 foundations takes about 0 seconds with
  no AI.

**Live search after restart** (blank keywords, using my focus areas):

| Step | Result |
|---|---|
| Results shown | 3.5 s; 35 matches, 20 of them from the foundation directory; 99 filtered out |
| 20 new fit assessments | About 1.5 minutes. 84,184 input tokens (47,975 cached) and 29,695 output tokens. |
| Top foundation fits | AEP Foundation 75% (Research further; AEP serves Ohio), Entergy 65%, Mott 60%, PPL 57%, RWJF 45%, Kauffman 41% |

- **Reason they weren't showing before:** the browser was still running the
  previous version of the app, before this source was added. Restarting
  fixed it.

## 2026-10-19 — Cost so far (tokenomics)

**38. How are we doing on cost?**
- **Prices found:** the course's Lecture 11 (Tokenomics) slides give
  gpt-6-luna at $0.10 input, $0.01 cached input, $0.125 cache write and
  $0.50 output, per 1M tokens.
- **Prices in the app:** now in `config.py`, so every run shows its dollar
  cost and logs it.
- **Cache writes:** following the course's rule that input_tokens include
  cache reads and writes, cache-write tokens are now tracked and billed
  separately. They weren't logged before this, so earlier figures treat
  them as zero.

**Real usage, from `logs/usage.jsonl`** (153 AI runs during development,
including the one-time read of 74 foundation pages):

| Agent | Runs | Total | Per run |
|---|---|---|---|
| Fit Agent | 56 | $0.055 | $0.00098 |
| Research Agent | 84 | $0.028 | $0.00034 |
| Grant Coach | 4 | $0.002 | $0.00058 |
| Grant Writer | 2 | $0.0015 | $0.00076 |
| Evidence Checker | 2 | $0.0009 | $0.00044 |
| **All runs** | **153** | **$0.090** | |

All development so far cost about **9 cents**.

**Typical active user per month (estimate; the assumptions need checking
with my test user):**
- 4 searches with 20 new fit assessments each: $0.079
- 8 imported opportunities: $0.011
- writing 3 applications × 6 questions (2 drafts, 3 coach reviews, 2
  evidence checks each): $0.074
- **Total ≈ $0.16 per user per month.**

**At scale:** about **$16/month for 100 users** and **$1,635/month for
10,000 users**. Add the foundation directory's worst case (every one of the
74 pages changes daily): about $0.75/month, shared by everyone if hosted
centrally.

**What keeps it low:**
- free rule-based triage before any AI
- cached shared prompt prefix (about 55% of Fit Agent input tokens were
  cached)
- page-change detection and once-a-day refresh
- cached assessments, so repeat searches cost $0

**Caveat:** Portkey sometimes returned cached responses for identical
requests, so the actual bill may be lower than these logged figures. Check
it against the Portkey dashboard.

**39. Fix: "Unknown" unreadable in the fit panel.** I pointed out that an
"Unknown" dimension score overlapped the weight column in the right-hand
panel.
- **Cause:** the score column was only 44 px, wide enough for "4/5" but not
  for "Unknown".
- **Fix:**
  - The score column now has room for "Unknown" (62 px in the panel, 72 px
    on the opportunity page). Unknown is shown smaller and muted, and
    nothing wraps.
  - The name and bar columns flex to fill the remaining space.
  - On narrow screens the bar is hidden, so score, weight and evidence
    label always fit.
- **Verified:** on AEP Foundation (Funding amount = Unknown), all seven rows
  fit inside the panel with no overlap, at both laptop width and a narrow
  screen.

**40. Fit colours follow the fit %.** I asked that the score colours
reflect the fit: green best, yellow medium, red poor.
- **Before:** colours followed the recommendation, so a 65% "No-Go" was red
  and a 36% "Research further" was yellow.
- **Now:** colour is set by the fit % alone: **green 70% and up, yellow
  40–69%, red under 40%**. The whole score box is lightly tinted to match,
  and the recommendation underneath is shown in neutral text.
- **Applied everywhere:** Discover cards, the fit panel and the opportunity
  page. A legend line explains the bands.
- **Verified:** 75% green (AEP); 65%, 60%, 57%, 45%, 41% yellow; 37% and
  below red.

## 2026-10-19 — Pipeline: grants open in a centred pop-up

**41. Pop-up instead of a new page.** I asked that clicking a grant in the
Pipeline open a pop-up in the middle of the screen, with everything the
opportunity page shows, instead of going to a new page.
- **Pop-up:** clicking a grant's name opens a centred pop-up over the dimmed
  Pipeline. It reuses the full opportunity view, so all controls work
  inside it:
  - status and responsible person (+ Add a person)
  - health strip
  - Go / No-Go with fit % and the seven-dimension breakdown
  - your decision and override
  - workback plan checkboxes
  - opportunity details
- **Links at the top:** "Open as full page ↗" and "Open application
  workspace →".
- **Closing:** the ×, Esc, or a click on the background. The Pipeline table
  then refreshes, so changes made in the pop-up show immediately. The page
  behind doesn't scroll while the pop-up is open.
- **Verified in the browser:** opened Riverside's Summer Reading Grants;
  ticking "Submit" in the pop-up moved progress from 83% to 100%; Esc
  closed it and the row showed 100%. The test was undone (back to 83%),
  closing via the background.

**42. Fix: names cut off in the Pipeline's Responsible column.** I pointed
out that names like "Kyle Yeh (Senior Grant W…" were truncated.
- **Fix:** the dropdown now shows just the person's name once chosen (e.g.
  "Kyle Yeh"). The open list still shows name and role (e.g. "Kyle Yeh ·
  Senior Grant Writer") and opens wide enough to read. The stored value is
  unchanged, so nothing else is affected.
- **Verified:** none of the names in the column are truncated, and the
  list shows all four people with their roles.

## 2026-10-19 — Pipeline redesign

**43. Making the Pipeline answer "is this worth it, and what's next?"** I
asked for a list of changes, then added a few more mid-way.

**New and changed columns:**
- **Fit:** e.g. "75% · Review" or "8% · No-Go", coloured by fit band;
  "Not assessed" if there's no assessment yet.
- **Funding:** e.g. "$50k–$100k" or "Up to $20k".
- **Stage & progress:** the separate Status column was removed (it repeated
  the progress bar). The stage name now sits above the bar ("Drafting ·
  17%").
- **Origin tag** under each grant name: "Found via Grants.gov", "Found via
  foundation directory", "Found via a funder you follow", "Uploaded PDF",
  "Uploaded Word document", "Added from URL", "Pasted text" or "Sample
  data". New grants are stamped when they're saved; existing ones were
  backfilled through a small database migration.

**Next action (replaces Outstanding):** worked out from each grant's real
state and clickable. Priority order:
1. still deciding → "Run Go / No-Go assessment", then "Make Go / No-Go
   decision"
2. any overdue step → "Overdue: …" (shown in red)
3. no questions yet → "Add the application questions"
4. the first unanswered question → "Draft Q3"
5. an answer over its limit → "Cut Q2 to the limit"
6. an unapproved answer → "Review & approve Q1"
7. otherwise the next workback step

Drafting actions open the application workspace at that question; the
others open the grant pop-up.

**Rows:** clicking anywhere on a row opens the full record pop-up, except
the Responsible dropdown, Risk and Next action, which do their own thing.

**Explainable risk:** hover over a risk label to see the facts, or click it
for a panel with the facts and the exact rule that set the label (same
thresholds as the code). For example, Miami Valley shows: 5 days remaining;
17% complete; 2 of 4 answers drafted; overdue: complete first draft,
programme review; 5 workback steps outstanding. Rule: "At Risk: 7 days or
fewer remain with under 60% done, or 2 or more steps are overdue."

**Filters:** responsible person (with Unassigned), deadline (overdue / next
7, 30 or 90 days / none), status, risk, and a funder or programme area
search that updates as you type. Plus Clear, the Active/All switch, and a
"Showing N of M" count.

**Verified in the browser:**
- the new column headings
- the risk panel opens without opening the grant pop-up
- "literacy" → 2 of 7 grants
- owner "Maya Chen" → 2 grants; Clear → back to 6
- a row click opens the pop-up for Buckeye
- the Responsible dropdown doesn't open the pop-up
- "Add the application questions →" opened Gem City's workspace

**Fixes found while testing:**
- Miami Valley first showed "Run Go / No-Go assessment" although it was
  already a Go. The assessment step now only appears while still deciding.
- The area search waited for Enter; it now updates after typing.

## 2026-10-19 — Explainable fit and risk, fewer clicks

**44. "Why 75%, not 82%?"** I asked for the fit score to be explained on
hover or click.
- **Points per dimension:** a new breakdown shows how many points each
  dimension earns out of its maximum. It uses the same formula as the
  score: a dimension's share is its weight ÷ the total weight scored, and it
  earns (score − 1) ÷ 4 of that share. Rows add up to the total, with halves
  rounded up.
- **Pipeline:** hovering the Fit cell gives a one-line reason ("Fit 75%.
  Points lost mostly on: Funding amount 3/5 (−7.5); Mission alignment 4/5
  (−6.3)…"). Clicking ⓘ opens the full table: points per dimension, the
  total, the biggest gaps, any unknowns left out, a note that effort isn't
  counted, and the formula.
- **Elsewhere:** the same "Why 75%?" breakdown is on the opportunity page
  and in the Discover fit panel.

**45. Risk says exactly why.** Clicking the risk ⓘ now leads with the
specific rule that fired, then the details and the rule text. Example
(Miami Valley): "5 days left and only 17% done (under 60%)" and "2 steps
are overdue". Hover shows the same "At Risk because…" line. Only one
explanation is open at a time, and none of them opens the grant pop-up.

**46. Prominent back button.** "← Applications" in the workspace is now a
clear green "← All applications" button. "← Pipeline" on grant pages became
"← Back to Pipeline" in the same style.

**47. Opportunity details as a pop-up.** In the application workspace,
"Opportunity details" now opens the full grant record (Go / No-Go, decision,
workback plan, details) in a centred pop-up instead of a new page. Esc, ×
or a click outside closes it, and Esc now closes any pop-up in the app.

**48. Why 4 applications but 7 in the Pipeline?** By design, Applications
only shows grants we've decided to apply for (Drafting, Internal Review,
Ready to Submit, or any with questions). The other 3 are Great Lakes STEM
and Buckeye (still awaiting a Go / No-Go decision) and Harbor Bank (already
submitted). The page now says so, names them, and links to the Pipeline.

**Verified in the browser:** fit hover and panel (75% = 18.8 + 15.0 + 11.3
+ 7.5 + 11.3 + 11.3, no wrapping); risk panel; back button style; the
workspace pop-up opens and Esc closes it without leaving the page; the
Applications note.

**49. Fix: "Add to pipeline" and "Add & start application" did nothing.** I
reported that the buttons in the Discover panel had no effect.
- **Cause:** once results were assessed automatically, every result opened
  from the cache, and that path never recorded which grant the panel was
  showing. The buttons had nothing to save, so they silently did nothing.
- **Fix:** the panel now always records the grant it shows, without
  triggering a second assessment.
- **Verified in the browser:**
  - "Add to pipeline" on AEP Foundation saved it with its 75% assessment
    (status Go / No-Go).
  - "Add & start application" on Entergy opened its application workspace.
  - Both test grants were then removed.

**50. "Add to pipeline" keeps you on Discover.** I asked that adding a grant
not navigate away, but show "Added!" in place of the button, so I can keep
exploring.
- **Add to pipeline:** saves the grant (with its assessment and any
  questions), stays on Discover with the panel open, and replaces the
  button with "Added! ✓" plus a "See in pipeline →" link.
- **Add & start application:** still goes straight to the writing
  workspace, since that's the point of that button.
- **Verified:** on Mott Foundation the button became "Added! ✓", the page
  stayed on /discover and all 35 results remained. My test entry was then
  removed. AEP Foundation, which I'd added myself, was kept.

**51. No "View fit" link; the whole card opens the panel.** I asked to
remove "View fit →" under the scores, so that clicking anywhere on a grant
card opens the panel on the right.
- **Removed:** "View fit →" and "Assess fit →".
- **Click target:** the whole card, including the empty space under the
  score box, now opens the fit panel, and the card highlights on hover.
- **Kept:** "See in pipeline →" for grants already added.
- **Verified:** 0 cards still show the link. Clicking below Entergy's score
  and clicking its title both opened the panel.

**52. Fix: Pipeline table stretched off the page.** After two foundation
grants were added (AEP and Entergy), the table spilled far past its card,
with a big gap after the Deadline column and squashed names.
- **Cause:** grants with no fixed date had a whole sentence as their
  "deadline" (up to 179 characters, e.g. "Requests are accepted throughout
  the year; nonprofit 501(c)(3) organizations must secure an
  invitation…"), in a column that didn't wrap.
- **Fix:**
  - Deadline labels are now short everywhere (Pipeline, Applications,
    Home, workspace, opportunity page): Rolling, Closed, Not stated, the
    dates found in the text ("Feb 1 & Aug 1"), or "See details".
  - The funder's full wording appears on hover. On the opportunity page it
    shows under the short label.
  - Dates stay on one line, the second line says "No fixed date" when
    there isn't one, and long text in Pipeline cells now wraps, so one
    entry can never stretch the table again.
- **Verified:** the table is now as wide as its card (1,174 px inside
  1,176 px), with no sideways scrolling. AEP shows "Rolling", Entergy shows
  "Feb 1 & Aug 1", and both show the full text on hover.

**53. ⓘ explanations open on hover.** I asked for the Fit and Risk ⓘ to
show their explanation on hover, not on click.
- **Change:** the Pipeline's Fit and Risk explanations now appear as soon
  as you hover over the score or label. They close when you move away,
  with a small gap bridge so moving onto the panel keeps it open. They also
  open on keyboard focus (Tab), for accessibility.
- **Removed:** the separate browser tooltips, so there's no duplicate pop-up.
- **Verified:** both panels are hidden by default, appear on focus, and
  close when focus moves on, without opening the grant pop-up. The hover
  rule is loaded; a real mouse hover can't be simulated in the test tool.

**54. Delete a grant from the Pipeline.** I asked for a trash can on the
right of each row.
- **Trash icon:** every row now ends with one. Clicking it asks for
  confirmation, naming the grant and warning that its answers, drafts,
  coach reviews and tasks are removed too and that this can't be undone.
  Cancel does nothing.
- **On confirm:** the grant and all its data are deleted. The table and the
  risk counts refresh, and a "Deleted …" message appears. Its Discover
  assessment is kept, so re-adding it from Discover costs nothing.
- **Isolation:** the trash icon doesn't open the grant pop-up.
- **Layout:** the Responsible column was narrowed slightly so the extra
  column still fits inside the card.
- **Verified with a throwaway test grant** (not one of mine): cancel left it
  alone (10 grants); confirm removed it (9 grants) along with its test
  question; the table and trash icon fit inside the card; no names are cut
  off.

## 2026-10-20 — Pipeline layout made robust

**55. Fix: Pipeline table stretched again (Funding column).** After I added
Mott Foundation, a huge gap opened after the Funding column.
- **Cause:** the same kind of problem as before, in another column. Mott's
  "award" was a 104-character sentence ("Not stated. The page displays
  individual past grant amounts…") in a column that didn't wrap.
- **Fix, at the source:**
  - **Funding labels** are now short: "$50k–$100k", "Up to $20k", "Not
    stated", or "See details", with the funder's full wording on hover.
  - **Fixed column widths:** the Pipeline table now uses a fixed layout with
    set widths per column, so no text in any cell can stretch the table
    again; long text wraps inside its cell. Headings no longer break
    mid-word.
- **Verified:** the table fits its card at 1440 px and 1024 px, with no
  sideways scrolling, the trash icon inside the card, and no names cut off.
  Mott shows "Not stated" with the full text on hover.

## 2026-10-20 — Coach redesigned like VMock + Grammarly

**56. A friendlier Coach, with Grammarly-style review.** I asked for the
Coach to be more user-friendly and for the review to work like
VMock/Grammarly.

- **Anchored issues:** the Coach now returns 3–8 issues, each tied to the
  exact words it's about, with:
  - a type (answer the question, evidence, be specific, outcomes, funder
    fit, clarity, repetition, plain language, missing information)
  - a severity
  - a short title and a plain explanation
  - an optional replacement

  Replacements may only rephrase, restructure or cut what's already there;
  where a fact is needed they insert [MISSING: …], never an invented
  number. Code keeps only issues whose words really are in the answer. Going
  over the length limit is added as a high-severity issue by code.
- **Score card (VMock-style):**
  - a score ring with a plain verdict (Strong 80+ / Getting there 60+ /
    Needs work)
  - a "Start here" top priority
  - a ✓ / ◐ / ✕ checklist of what the question asks
  - colour-coded chips for the ten scored areas (hover for the reason)
  - "What's working" (collapsible)
  - The confusing "(Couldn't find the quoted passage.)" notes were removed.
- **Review mode (Grammarly-style):**
  - The editor has an Edit / Review suggestions switch, and running the
    review switches to Review automatically.
  - The answer is shown with each issue underlined in its type's colour
    (dashed for low severity).
  - Clicking a highlight jumps to its card. Each card shows the problem, a
    before → after preview (struck-through red → green), and Apply /
    Dismiss.
- **Human in control:** Apply puts the wording into the editor as unsaved
  changes; nothing is kept until I click Save. Saved versions are labelled
  "you, with Coach suggestions".
- **Grant Coach page:** the standalone page also shows the marked-up answer
  and the new score card.

**Tested live** on the deliberately weak sample answer:
- **Result:** 39/100 ("Needs work") with 5 anchored issues: the
  unsupported "leading literacy provider" claim, vague population, vague
  income share, no local evidence, and an ending that misses the prompt.
  Cost about $0.0009.
- **In the browser:**
  - highlights appeared straight after the review
  - clicking "Children who cannot read well…" focused the "No local
    evidence" card
  - Apply changed the editor text (adding a [MISSING] placeholder) and
    showed "Unsaved changes"
  - Dismiss removed a card ("3 suggestions to review · 1 applied · 1
    dismissed")
- **Cleanup:** the test edit was discarded by reloading; the saved answer
  was confirmed unchanged.

**Bug found and fixed while testing:** the highlights first didn't appear,
because the mode switch and the new suggestion buttons changed at the same
moment and the code only looked at the first change. It now acts on the
real click or the mode change.

**57. Hover a highlight to see its suggestion.** I said nothing happened
when hovering over the underlined text.
- **Hover card:** each highlight now opens a Grammarly-style card on hover,
  showing the type and severity, the title, a plain explanation, the
  suggested wording (or "Only you can fix this one…" when the writer must
  add a fact), and **Apply** / **Dismiss** buttons that work like the ones
  in the side panel.
- **Behaviour:** a small hover bridge keeps the card open while moving onto
  its buttons. Clicking a highlight still jumps to its card in the Coach
  panel.
- **Verified:** Apply from a hover card updated the editor ("Unsaved
  changes") and removed that highlight (5 → 4). A real mouse hover can't be
  simulated in the test tool, so the card was forced open once to
  screenshot it. The test edit was discarded and the saved answer
  confirmed unchanged.

**58. Hover to preview, click to accept or reject on the right.** I said
the hover was good, but clicking a highlight should open it on the right,
where I can accept or reject it.
- **Hover:** a read-only summary card (type, severity, title, why, the
  suggested wording) with "Click to accept or reject →".
- **Click:** switches the right-hand panel to the Coach tab, focuses that
  suggestion's card (with a brief highlight) and scrolls it into view. The
  card has **✓ Accept** (puts the wording into the editor, still unsaved)
  and **✕ Reject**. Suggestions that only the writer can fix say "Edit this
  yourself in Edit mode." The summary reads "· N accepted · N rejected".
- **Layout:** the right-hand panel is now sticky and scrolls on its own, so
  the marked-up answer and the selected card stay visible side by side.
- **Bugs found while testing:**
  - The first scroll attempt never ran; it was moved into the page script.
  - Smooth scrolling was cancelled while the panel redrew, so it is now an
    instant jump within the panel.
- **Verified:** starting on the Sources tab, clicking three different
  highlights each opened the Coach tab with the matching card focused, and
  both the highlight and its card were on screen. The saved answer was
  unchanged.

**59. Click to pin the suggestion card in place.** I changed my mind: no
side-panel jump. Clicking a highlight should pop up the card right there
(as on hover before), and it should stay until I accept, reject or close it
(× or a click outside).
- **Click:** the highlight now opens its card in place, and it stays
  pinned. Nothing appears on hover, and the right-hand panel is not
  changed.
- **The card:** × in the top right, type and severity, title, explanation,
  the suggested wording, and **✓ Accept** / **✕ Reject**.
- **Closing:** ×, a click anywhere outside, or Esc. Opening another
  highlight closes the previous one.
- **How it works:** opening and closing happen in the browser (no server
  round trip), so the card isn't redrawn away. Accept and Reject still run
  through the app, so nothing is kept until Save.
- **Verified:**
  - hidden until clicked, and still open after waiting
  - the right panel tab is unchanged
  - × closes it, and a click outside closes it
  - Accept changed the editor ("Unsaved changes"); Reject removed the
    highlight
  - the test edits were discarded and the saved answer confirmed unchanged

**60. Every suggestion can be accepted.** I pointed out that some cards
said "Only you can fix this one" with just Reject; every suggestion should
have a fix I can accept or reject.
- **Coach rule:** each issue must now come with a concrete fix:
  - **replace:** new wording for just those words, rewritten around
    [MISSING: …] placeholders where a fact is needed, e.g. "We serve over
    700 [MISSING: grade range] students…"
  - **remove:** delete them, for unsupported superlatives, filler or
    repetition.

  The no-invented-facts rule is unchanged.
- **Safety net in code:** if the model ever leaves a fix out, evidence,
  repetition and jargon issues default to "remove", and others to a
  [MISSING: …] placeholder. The same applies to reviews saved before this
  change.
- **Cards:** both the pinned card and the side card always show
  "Suggested: …" (or "Suggested: remove …" with the words struck through)
  and ✓ Accept / ✕ Reject. Accepting a removal deletes the words and the
  extra space.
- **Verified on a fresh Coach run:** all 6 suggestions had a fix and an
  Accept button, e.g. "Leading literacy provider in Ohio" → "Riverbend
  Reads provides literacy support in Ohio." Accepting "remove: Reading is
  very important for children." deleted it cleanly. The test edit was
  discarded and the saved answer confirmed unchanged.

## 2026-10-20 — Undo and redo for Coach edits

- **Prompt (summarised):** let the user undo edits made from Coach
  suggestions.
- **What was built:** ↶ Undo and ↷ Redo buttons above the review view.
  Each Accept or Reject saves a snapshot of the answer and the open
  suggestions, so Undo puts back both the text and the highlight; Redo
  re-applies it. A note says what was undone ("Undid: accepted
  'Unsupported comparative claim'"). History resets on a new Coach run and
  keeps the last 30 steps. Nothing is saved until the user clicks Save.
- **Verified in the browser:** accepted one suggestion and rejected
  another (6 → 4 highlights), undid both (back to 6, text identical to the
  original, Undo greyed out), then redid one (5 highlights). The test
  edits were discarded and the saved answer confirmed unchanged.

## 2026-10-20 — Undo/Redo buttons restyled

- **Prompt (summarised):** the small text arrows (↶ Undo / ↷ Redo) looked
  odd; make them look like the familiar Word-style buttons.
- **Change:** each button is now a bold curved-arrow icon with the label
  underneath, in the accent green. Redo is the same arrow mirrored. The
  icon is drawn in the button's own colour, so it greys out together with
  the label when there is nothing to undo or redo.
- **Checked in the browser:** the arrows render with Undo active and Redo
  greyed out after one accepted suggestion. The test edit was discarded
  and the saved answer confirmed unchanged.

## 2026-10-20 — "Add a question" form fixed

- **Prompt (summarised):** the Add a question form in the application
  editor looked broken: the words/characters dropdown stuck out of the
  Questions card and the Limit box was a different height.
- **Change:** the Limit box and the unit dropdown now share one row
  inside the card (equal height, even gap), with spacing above the Add
  question button and the message underneath.
- **Checked in the browser:** both fields sit inside the card's edges at
  40 px high, including with the "Paste the question first." message
  showing.

## 2026-10-20 — Autosave, whole-row clicks, Draft with AI in the editor

- **Prompts (summarised):** (1) answers should save automatically while
  typing; (2) a Pipeline row should open no matter where you click; (3) the
  two buttons at the top of the grant pop-up should match; (4) unticked
  Workback steps stayed struck out; (5) the "Add a question" form still
  looked broken; (6) add a "Draft with AI" button in the editor itself,
  not a separate Draft tab, drafting from the Profile and documents.
- **What changed:**
  - **Autosave:** the Save button is gone. The editor saves a second after
    typing pauses (debounced in the browser, so one save per pause) and
    when you click away. "Saving…" turns into "✓ Saved 22:31". Autosaves
    within 10 minutes fold into one Version history entry instead of one
    per pause.
  - **Pipeline rows:** a click anywhere in the row opens the grant,
    including the Fit and Risk labels and cell padding. The row's own
    controls (Next action, Responsible, delete) still do their own job.
  - **Pop-up header:** "Open application workspace →" now uses the same
    pill style as "Open as full page ↗".
  - **Workback plan:** the line-through follows the tickbox itself, so it
    clears the moment a step is unticked, even if the server is slow or
    restarting.
  - **Draft with AI:** the Draft tab is removed. "✦ Draft with AI" sits
    above the editor, shows "Drafting from your documents…" while it runs,
    and writes the draft into the editor. Undo restores the previous text,
    which also stays in Version history. A small panel under the editor
    lists missing facts and where each fact came from.
- **What was lacking before:** the user's screenshots of the old Undo
  arrows, the form overflow and the stuck "Saving…" came from a browser
  tab opened before a server restart. Dash only loads new CSS and new
  browser-side callbacks on a full page reload. The fixes were already in.
  The real lesson: tell the user to reload (⌘R) after each restart.
- **Verified in the browser:**
  - Autosave: "Saving…" while typing, "Saved" after the pause; two edits
    made one history entry.
  - Rows: every part of a row opened the pop-up; the Responsible dropdown
    did not.
  - Header buttons: identical style.
  - Workback: the line-through cleared instantly when unticked.
  - Add a question form: inside the card on all 9 applications.
  - Draft with AI on a temporary empty question: 130/150 words, 0 missing
    facts, 9 sourced facts, gpt-6-luna, 2,190 input + 734 output tokens,
    $0.0006. Undo returned the empty answer; Redo restored the draft.
  - Test data was rolled back from a backup.

## 2026-10-20 — Compass Assistant (chatbot)

- **Prompt (summarised):** add a chatbot in the bottom left that answers
  questions about discovery, the pipeline, targets, drafting, deadlines and
  anything else a fundraiser or grant writer would ask. Its icon should be
  about fundraising and maybe animated on hover. The chat should open with
  something like "let us help you, help others".
- **Built:**
  - **Agent:** a sixth agent, `grantcompass/assistant.py` plus
    `prompts/assistant.md`, on gpt-6-luna through Portkey.
  - **Tools (7, all read-only):** pipeline overview (stage, days left,
    risk with reasons, progress, owner, fit, next action), grant details
    (assessment, workback steps, every question's status, length, Coach
    score and evidence counts), Discover matches, a live Grants.gov search
    (no AI cost), profile and documents, team workload, and AI spending.
  - **No invented numbers:** code computes every number; the model only
    explains them.
  - **Limits:** at most 8 model calls and 80k tokens per question,
    messages capped at 2,000 characters, and only the last 8 turns sent
    back as context.
  - **Safety:** the agent can't change anything. Funder and document text
    is treated as data, and off-topic requests are declined.
  - **Widget:** an animated hand-offering-a-heart button. On hover, "Ask
    Compass" slides out, the heart beats and a gold coin drops into the
    hand.
  - **Panel:** opens with "Let us help you, help others." and six starter
    questions. It also has typing dots, Enter to send (Shift+Enter for a
    new line), a sun icon by the composer, Send disabled while answering,
    Esc to close, and a conversation kept for the browser session.
- **Verified in the browser:**
  - "What should I work on this week?" put Miami Valley first: Critical,
    due 23 Oct, 67% done, Coach score 38, placeholders in Q2 and Q3, Q4
    not started. It then named the pending Go / No-Go decisions. Cost:
    3 model calls, 7,448 input tokens (2,340 cached), 420 output, $0.00085.
  - Asked to "delete the Great Lakes one", it declined and pointed to the
    Pipeline (a safety defense shown working).
  - The follow-up "Who is that one assigned to?" resolved "that one" from
    context: unassigned. Cost: $0.00037.
  - The "new opportunities" starter ranked AEP 75%, Mott 60% and Kauffman
    41%, and noted that Entergy is already in the pipeline.
  - Fixed during testing: the reply sometimes stopped short of the bottom
    of the chat. The chat now scrolls whenever its content grows.
- **Note for the report:** the 153 earliest logged runs predate the price
  settings, so they have token counts but no cost. The AI-spending tool
  says so rather than under-reporting.

## 2026-10-20 — Coach runs by itself; Undo covers typing

- **Prompts (summarised):** (1) opening Review suggestions should show
  suggestions straight away; the Coach should be a background agent, not
  something you have to ask. (2) The Undo and Redo buttons did nothing.
- **What was lacking before:**
  - Suggestions only appeared after clicking "Review my answer" in the
    Coach tab.
  - Undo and Redo only covered Coach accepts and rejects (and AI drafts).
    After ordinary typing they stayed greyed out, so they looked broken.
- **Changes:**
  - **Background Coach:** the "Review my answer" button is gone. Opening
    Review suggestions starts the Coach as a background callback. The
    pane shows "The Coach is reading your answer…" and fills in the
    highlights when it finishes.
  - **Cost control:** it reruns only when the text differs from what it
    last reviewed (compared with the saved `response_text`). Switching
    back and forth is free. If a run fails, it says so instead of
    loading forever.
  - **Undo for typing:** autosave records each typing pause as one Undo
    step. Drafts, Coach accepts and Undo/Redo record their own steps, so
    nothing is counted twice.
- **Verified in the browser** on the user's mission question:
  - Opening Review with an already-reviewed answer: no new AI run (log
    unchanged).
  - After typing a sentence: Undo enabled; Undo restored the text exactly
    ("Undid: your edit."); Redo put it back.
  - Opening Review after that edit: the Coach ran by itself (1,631 input
    + 986 output tokens, $0.00056) and showed 3 new highlights on the new
    text.
  - The test edit was rolled back from a backup.

## 2026-10-20 — Edit a question; the assistant can navigate

- **Prompts (summarised):**
  - (1) There should be a way to edit a question, e.g. to change its word
    limit.
  - (2) "Why can't the chatbot navigate the app for me?" It had replied
    that it couldn't, and wrongly pointed to a "sidebar".
- **What was lacking before:**
  - Questions could only be added or deleted, so fixing a typo or a limit
    meant deleting and losing the answer.
  - The assistant had no navigation tool, and its prompt didn't describe
    where the menus are.
- **Changes:**
  - **Edit question:** a "✎ Edit question" link next to the limit tag
    opens an inline form (wording, limit, words/characters). Saving
    updates the question, the limit tag, the live count and the question
    list. An empty limit means no limit, and the answer is never touched.
  - **Navigation tool:** the assistant gained `open_page(page, grant_id,
    question_number)`. It can open Home, Discover, Pipeline, Applications,
    Grant Coach, Profile, Source documents, Team, any grant's record, or
    any application question.
  - **How navigation runs:** code (not the model) builds and checks the
    address. The chat callback then sends the browser there, with the
    chat still open.
  - **Prompt:** now says the main menu is along the top and Profile,
    Source documents and Team are in the organisation menu.
- **Verified in the browser:**
  - Setting a 50-word limit showed "Limit: 50 words" and "22 / 50 words".
    The edit form closes after saving (first try: it stayed open, now
    fixed). The test edit was rolled back.
  - "take me to discover" → /discover.
  - "open question 2 of the Miami Valley application" →
    /application/1/2, showing the programme-design question.

## 2026-10-20 — Stale tabs reload themselves; suggestion labels explained

- **Prompts (summarised):**
  - (1) "When I clicked Review suggestions it didn't automatically give me
    a review" (Miami Valley Q4, right after Draft with AI).
  - (2) What do "Funder fit" and "High" on a suggestion mean?
- **Diagnosis (1):** not a logic bug. The server log showed a
  `KeyError: Callback function not found` for the old "Review my answer"
  callback. The user's tab was loaded before the server restart that
  replaced it. Requests from that tab hit callbacks that no longer
  existed and failed silently. This was the third bug report caused by a
  stale tab (after the Undo icons and the Add-question layout).
- **What was lacking before:** nothing told an open tab that the server
  now had new code.
- **Fix (1):** each server start gets a build id, served at `/__build`
  and also written into the page. `assets/menu.js` checks it every 5
  seconds. When it changes, the tab reloads itself, waiting until you're
  not typing (autosave means nothing is lost).
- **Fix (2):** "Funder fit" is the kind of problem; "High / Medium / Low"
  is how much it matters. Both labels now explain themselves on hover
  (e.g. "High: likely to cost points with reviewers. Fix before you
  submit."), and the Coach panel's intro has a one-line legend.
- **Verified in the browser:**
  - Q4 → Review suggestions showed 5 highlights straight away.
  - Hover text is present on the type and severity labels.
  - Simulating a new build id made the open tab reload itself within 5
    seconds.

## 2026-10-20 — Chat wording tidied

- **Prompts (summarised):**
  - The chat box placeholder ("Ask about a grant, a deadline, a draft…")
    was cut off.
  - The header subtitle ("Reads your grants and takes you anywhere ·
    never edits") felt odd and "AI-ish".
- **Changes:**
  - The placeholder is now "Ask me anything…": 123 px of text in a 258 px
    box, so it fits with room to spare.
  - The subtitle is removed; the header just reads "Compass Assistant".
  - The welcome line is plainer: "Ask about deadlines, your pipeline, new
    funders or a draft. I can also take you to any page."
- **Verified in the browser** with a screenshot of the open panel.
- **Follow-up prompt (summarised):** clicking outside Compass Assistant
  should minimise the chat. Added in `assets/menu.js`: a click anywhere
  outside the chat closes it. Clicks inside it (text, input, starter
  questions) keep it open, and the round button still toggles it. Tested
  each case in the browser. The conversation is kept when the panel
  closes.

## 2026-10-20 — Answer Library redesigned as its own feature

- **Prompts (summarised):**
  - "Where is the reusable approved answer library?"
  - Then: "This isn't at all clear — find a new way to do this that
    improves UX and UI."
- **What was lacking before:** approved answers were source documents
  with an "Approved language" tag. Saving was a vague "Save as approved
  language" button. Finding them meant the Profile menu → Source
  documents, mixed in with reports and budgets. Reusing them was implicit:
  the passages were ranked first in Sources. There was no page, search,
  topics, reuse button or usage count.
- **New design:**
  - **Answer Library** in the top menu (`/answers`):
    - search box and topic chips with counts
    - cards: topic, funder · date · words · "reused N×", the original
      question in serif, a 3-line preview with "Show full answer", Copy
      and Remove
    - an "Add a past answer" form for wording from old applications
    - an empty state that explains the 3-step loop (write → ★ add →
      reuse)
  - **Editor:** the button is now "★ Add to Answer Library". It blocks
    answers with [MISSING: …] gaps, and re-saving the same question
    updates its entry rather than duplicating it.
  - **Library tab in the editor:** it opens first when saved answers fit
    the question. Each fit has a plain reason ("Same topic, similar
    question"), **Use this answer** (an Undo step, and it counts a reuse)
    and Copy.
  - **Under the hood:** a new `answers` table. `answers.py` classifies
    topics and matches answers with keyword rules (no AI cost). Saved
    answers join the writers' library context as approved wording.
  - **Assistant:** Compass Assistant gained an `answer_library` tool and
    can open the page.
- **Verified in the browser:**
  - Empty state.
  - Saving Miami Valley Q4 → "Added to your Answer Library. View library
    →".
  - Q2 and Q3 refused because of [MISSING: …] gaps.
  - A pasted past answer was filed under Outcomes & evaluation.
  - A new outcomes question on another application opened on the
    Library (1) tab with that answer marked "Same topic, similar
    question". Use put it in the editor and Undo emptied it again; the
    library then showed "reused 1×".
  - Search and topic filters work.
  - Fixed during testing: the "Saved answers (1)" tab label wrapped and
    made the tabs taller, so it was renamed "Library (1)".
  - All test entries (including a made-up sample answer) were rolled back.

## 2026-10-20 — Harsh self-audit against the rubric; Copy/Remove polish

- **Prompts (summarised):**
  - (1) "Is everything working perfectly now? I want 100%, be a harsh
    grader."
  - (2) In the Answer Library, both the Copy icon and the word should
    copy, and Remove should look exactly like Copy, with a trash icon.
- **Audit done:**
  - Re-read the full rubric (100 pts: idea 21, app 30, report 41, slides
    8).
  - **Fresh-clone dry run:** copied exactly the files git would publish,
    put `.env` one folder up as the staff do, and followed the README.
    Python 3.14 venv plus install took 18 s. First start took 1.4 s: it
    seeded the sample data, found the key in the parent folder, rendered
    all 11 pages, and a real assistant call answered correctly ($0.0003).
    Total 35 s, well inside the 10-minute rule.
  - 73 of the 74 foundations load from the shipped cache, so a grader's
    first Discover search doesn't call the AI 74 times.
  - **Secrets:** the scan found no secrets; `.env`, `logs/` and the
    database are git-ignored.
  - **README:** fixed stale claims ("(soon) produce stronger
    applications", "It is not a chatbot", the sample-data counts).
- **Gaps found (not yet fixed):** the repo has no commits and no GitHub
  remote; `report.html` and `slides.html` don't exist; there is no real
  user session; no prompt-injection test yet; tokenomics need
  re-measuring now that the assistant and the auto-Coach exist; Discover
  search and the PDF/link import haven't been regression-tested since the
  recent changes.
- **Copy / Remove:** a shared `copy_action` helper; a click on the word
  passes through to the clipboard icon. Remove uses the same `.ans-act`
  style with a trash icon drawn in the same green. Verified: the word and
  the icon both copied (clipboard calls recorded), and Copy and Remove
  have identical colour, size and weight. The temporary answer was
  removed; the user's own saved Q1 answer was kept.

## 2026-10-20 — Full regression sweep and prompt-injection safety tests

- **Prompt (summarised):** do a full regression sweep of every feature, fix
  anything broken, and add a prompt-injection safety test.
- **Method:**
  - Swept a fresh copy of exactly what git would publish (new sample
    data, `.env` one folder up), served on port 8051 so the user's own
    app and data were never touched.
  - Drove every feature in the browser, with real AI calls where the
    feature uses them.
  - Ended with no console errors and no server errors.
- **Bugs found and fixed:**
  1. **Source documents:** Delete removed a document instantly. It now
     asks for confirmation.
  2. **Source documents:** a damaged PDF showed "Stream has ended
     unexpectedly". It now gives a plain explanation.
  3. **Team:** the same person could be added twice (the check compared
     name + role). It now blocks by name.
  4. **Discover:** after "Add to pipeline", the result card gave no sign
     it was saved. It now shows "✓ In pipeline" immediately.
  5. **Discover:** deadlines showed as raw "2026-12-09". They now use the
     app-wide "9 Dec 2026".
  6. **Award formats:** "$1–$460k" (Grants.gov's $1 floor) now reads "Up
     to $460k", and "$2M–$2M" reads "$2M".
  7. **Errors everywhere:** link import and other failures showed raw
     exceptions (HTTPError 404, NameResolutionError…). A new `errors.py`
     gives one plain sentence (404, blocked site, no connection, bad API
     key, provider content filter, spending limit) and logs the details
     for developers.
  8. **Go/No-Go:** choosing Go against the AI's "Research further"
     without a reason silently reset the choice to the AI's pick. It now
     keeps the user's choice, outlines the reason box in red, and says
     "You chose Go but the AI recommends Research further. Add a short
     reason, then save again." The rule itself is intended: a human
     override must be explained.
  9. **Version history:** loading an earlier version wasn't an Undo step.
     It is now.
  10. **Assistant:** it said there were no saved answers for "programme
      design" when one was filed under that topic (search ignored
      topics). Search now includes topics, and an empty search falls back
      to the whole library instead of a false "none".
  11. **Discover import:** "0 application questions found" now says "No
      application questions in this text…".
  12. **Sample data:** Riverside was "Ready to Submit" and Gem City "In
      Internal Review" with zero questions. Riverside now has 2 approved
      answers and Gem City 2 answers in review, all from facts in the
      sample profile. One approved answer is seeded in the Answer
      Library, so Miami Valley Q4 opens on "Library (1)" with a "Same
      topic, similar question" suggestion.
- **Verified working:**
  - **Home:** stats; attention links open the right grant.
  - **Profile:** save persists; menu works.
  - **Source documents:** upload, approve/unapprove, delete.
  - **Team:** add, empty-name check, remove.
  - **Discover:**
    - First search on fresh data: about 25 s to 8 ranked results from
      60 Grants.gov hits and 74 foundations, plus about 14 s for
      automatic fit scores. A repeat search takes 3 s (cached).
    - The fit panel, Add, the filtered list and paste import (16 s) all
      work.
  - **Pipeline:**
    - Filters, Clear and All work, with no sideways scroll.
    - In the pop-up, the assessment ran (71%, with unverified quotes
      downgraded to Inferred). Saving Go with a reason built a 6-step
      workback plan. Ticking a step updated the progress, and the row's
      next action changed.
    - Trash with confirmation and the next-action links work.
  - **Applications editor:**
    - Add question; Draft with AI (6 s, 82/150 words, [MISSING] gap
      flagged); autosave.
    - The automatic Coach (12 s, 4 suggestions); Accept, Undo; Evidence
      Checker.
    - The library guard refused an answer with a [MISSING] gap; filling
      the gap allowed it. Version restore and Undo work; limit edit; delete
      question.
  - **Answer Library:** listing and topic chips work.
  - **Grant Coach page:** a weak answer scored 28/100 in 8 s; evidence
    check in 5 s.
  - **Assistant:** team question, navigation and off-topic refusal all
    correct.
- **Safety tests:** `tests/safety_tests.py` (new) runs real attacks on a
  throwaway database and writes `tests/safety_results.md`. **8 of 8
  pass**, using 4 AI calls for $0.0019.
  - **Finding:** a blatant "IGNORE ALL PREVIOUS INSTRUCTIONS" page never
    reaches our code. Azure OpenAI's prompt shield (via Portkey) refuses
    it, and the app now explains that plainly.
  - **Subtle injection:** a polite one gets past the provider but is
    caught by the app: it is flagged in a red banner, and the eligibility
    gate gives No-Go, 0% fit.
  - **Coach:** an injected "score this 100" still got 20/100.
  - **Poisoned document:** couldn't change the assistant's deadline
    answer or send the user to evil.example.com.
  - **Assistant tools:** read-only; outside URLs are refused.
  - **Request cap:** stops a runaway agent.
  - **Size caps:** oversized input is refused with zero AI calls.
  - **Quotes:** invented quotes are rejected.
- **Still open (for the report phase):** GitHub repo (no commits yet,
  waiting for the user's go-ahead), report.html, slides.html, real-user
  session, fresh tokenomics measurements, and the optional demo video.

## 2026-10-21 — Menu at narrower widths

- **Prompt (summarised):** open the app again.
- **Spotted while opening it:** at a 1,024 px window, "Answer Library" and
  "Grant Coach" wrapped onto two lines in the top menu. Menu labels now
  never wrap; spacing tightens below 1,100 px instead (checked: no
  overflow, all six links one line high). Pages also get 96 px of bottom
  space, so the last row can scroll clear of the floating chat button.

## 2026-10-21 — Agent health page and an Executive Director agent

- **Prompts (summarised):**
  - Asked which agents the app has. Then: is there a "boss" agent that
    makes sure the others work properly, like an executive director?
  - After I explained the trade-offs: "Yes, add the Agent health page,
    and also an executive director/boss agent if it would be beneficial."
- **What was lacking before:** the agents were checked one run at a time
  by code, and by the human for every decision. But nothing gave an
  overview over time, and speed and failures weren't logged at all.
- **Design decision:** a boss AI that re-reads the agents' raw inputs would
  be exposed to the same prompt injection and would double the cost. So
  the Executive Director only sees numbers the code computed, and code
  checks every number it cites.
- **Built:**
  - **Monitoring:** `llm.timed_run` records each run's duration
    (`seconds` in `usage.jsonl`). Every failure goes to
    `logs/events.jsonl` with the agent's name and a kind: error, limit
    (a per-run cap stopped it) or provider_block (the prompt shield
    refused it).
  - **`health.py` (no AI):** per-agent runs, cost per run, speed,
    failures, and agent-specific safety checks:
    - Fit Agent: quotes that failed verification, eligibility-gate
      overrides, injection flags, how often the human overruled it.
    - Grant Writer: unverified cited facts, drafts that marked a gap
      instead of guessing.
    - Evidence Checker: weak and contradicted claims.
    - Assistant: look-ups per question, zero write tools.
  - **Status rules:** each agent is Healthy / Watch / Attention by rules
    shown on the page. Every number has an id.
  - **Executive Director (7th agent):** `director.py` plus
    `prompts/executive_director.md`. On request it reviews the six
    agents and returns an overall Healthy / Watch / Act, 3–7 findings
    each tied to ONE metric, and a top action. Code then:
    - removes any finding whose metric doesn't exist or whose value
      doesn't match;
    - raises the rating if it is rosier than the app's own rules.
    Reports are saved in a `director_reports` table.
  - **Agent health page** (`/profile/health`, organisation menu and
    profile tabs): the Director's briefing (evidence lines in plain
    words, and a note when it's stricter than the rules), totals, six
    agent cards, and "How statuses are decided".
  - **Assistant:** a new `agent_health` tool, and it can open the page.
  - **Safety tests:** test 9 checks that the Director can't invent
    numbers or sugar-coat.
- **Prompt tuning from real runs:**
  - The first review said "a rate of 1.0", reviewed itself, and called
    "1 of 1" overrides "high". Now numbers read as people say them, it
    doesn't review itself, and it says when there is too little data.
  - It also treated the Coach's average answer score of 54 as the Coach
    failing. The label and the instructions now say that score measures
    the answers, not the Coach.
- **Bug caught:** the safety tests' deliberate limit hit and provider
  block were logged into the user's real health data (the Assistant
  showed "Watch: 1 run stopped by a limit"). Tests now log to a throwaway
  folder; the two test events were removed.
- **Verified:**
  - **Review:** 6–8 s, about $0.0005 a review, 0 claims removed. Its
    top action was "Review Fit assessments with quote warnings": 23 of
    55 assessments had a quote fail verification.
  - **Page:** all six cards Healthy, 206 runs, $0.028 spent on priced
    runs, $0.0005 per run, 0 failures.
  - **Assistant:** "How are the AI agents doing?" answered from the new
    tool, including the Director's top action.
  - **Safety suite:** 9 of 9 pass ($0.0018).

## 2026-10-21 — Agent health redesigned for at-a-glance reading

- **Prompt (summarised):** the Agent health page was long, cumbersome and
  hard to understand. Make it easy to glance at.
- **What was lacking before:** it opened with explanatory paragraphs.
  Every Director finding took three lines, including a technical
  "Based on…" line. Each agent card listed every metric, so the page ran
  to about four screens.
- **New layout:**
  1. **Status banner** in one sentence ("All six agents are healthy", or
     which agents need attention), with runs, cost, cost per run and
     failures on one line.
  2. **Director's briefing:** rating, one-line headline, a highlighted
     "Do next", then "To watch (n)" as one-liners. Hovering any line
     shows the number it rests on. "Working well" is folded away.
  3. **Six compact tiles,** each with a coloured edge for its status and
     ONE key fact (e.g. "23 of 55 assessments had an unverified quote").
     Cost, speed and failures go on one small line, the rest under
     "Details".
  4. **"How this works"** (status rules, how the Director is checked) is
     folded at the bottom.
- **Checked in the browser:** the page is about 1.3 screens instead of
  about 4, and the Run review button still refreshes everything.

## 2026-10-21 — Front door with demo organisations; design pass

- **Prompts (summarised):**
  1. Add a login page with three options: log in, start a new
     organisation and enter its profile, or test with 5–6 fabricated
     organisations (documents, profiles, teams filled in). They should be
     very different, so Discover gives different results for each.
  2. Mid-task, chose five design upgrades:
     - a compass logomark everywhere
     - a "mission control" Home
     - a fit dial with dimension bars (keeping the %)
     - a live agent diagram, with nonprofit job titles and archetype
       personalities for each agent
     - purposeful motion
- **What was lacking before:** the app had one organisation in one
  database, with no way in except straight to Riverbend's data. Graders
  could only test one profile, so Discover always searched the same
  literacy keywords.
- **Multi-organisation design:** `orgs.py` gives each organisation its
  own SQLite database (`data/orgs/<slug>.db`; Riverbend keeps
  `data/grantcompass.db`, so existing work carried over) and its own log
  folder, so grants, documents, answers and Agent health never mix. A
  signed Flask session cookie names the open organisation, and
  `before_request` points the database and logs at it.
- **Accounts:** stored in `data/accounts.db` with werkzeug scrypt hashes
  (checked: the hash is stored, never the password). Email,
  8-character-minimum, duplicate-email and wrong-password checks.
- **Demo organisations:** five new ones were written in parallel by
  helper agents to a shared spec (`data/demo_orgs/SPEC.md`), then
  validated in code (every profile value in the app's option lists, doc
  types, stage order, team references, "FICTIONAL SAMPLE" labels):
  - **Bright Orbit STEM Lab:** Detroit, STEM for girls.
  - **Cedar Ridge Veterans Collaborative:** San Antonio, veteran housing
    and jobs.
  - **Harbor Light Health Collective:** Oakland, street medicine.
  - **Prairie Roots Food Alliance:** Nebraska, rural food security.
  - **Tidewater Arts & Heritage Center:** Charleston, Gullah Geechee
    heritage.

  Each has 6 documents, 6 grants at every pipeline stage, 8 questions,
  a 3-person team and a library answer. The first application has a
  deliberately weak answer, so the Coach and Evidence Checker have
  something to catch.
- **Discover keywords:** they now add one distinctive population
  (veteran, rural, refugee, LGBTQ) after the top two focus areas, so
  Cedar Ridge searches "veteran" and Prairie Roots "rural". The first try
  put "disability" ahead of "health" for Harbor Light, so the population
  now supplements rather than leads, and "disability" was dropped as too
  general.
- **Front door and setup:**
  - The login page has six demo cards (monogram, cause, place,
    one-liner), Log in, and Start your organisation. The menu and chat
    are hidden until you're in.
  - A new account lands on a Welcome page with three steps (profile %,
    documents, team), and Home shows "Finish setting up" until they're
    done.
  - Organisation menu: "Reset this demo" and "Switch organisation".
- **Bug prevented:** the chat conversation would have carried over
  between organisations. Every login, demo or switch now clears it.
- **Design pass:**
  - **Compass logomark** (`assets/logo.svg`): its needle swings into
    place on load. It's used in the header, browser tab, login page and
    chat header.
  - **Mission-control Home:** a 60-day deadline strip (one dot per
    grant, coloured by risk, click to open). Labels sit in lanes so close
    deadlines never collide; the first version overlapped and was fixed,
    then measured at 0 overlaps. Funding by stage is one animated bar
    with amounts and counts; empty links displayed "/pipeline" text,
    which was fixed.
  - **Fit dial:** a CSS conic-gradient ring fills to the fit %, which
    counts up and is still shown. Seven dimension bars are coloured
    green 4–5, yellow 3, red 1–2. Used in the Discover panel and on every
    grant.
  - **Meet the team** on Agent health: seven personas with nonprofit
    titles and archetypes, arrows for the flow of work, dashed lines for
    the Director's oversight, health-coloured rings. Click a person for
    their job, sources and guardrails. Personas also appear on the agent
    tiles.
  - **Motion:** Discover results fade in one after another, fit badges
    and the Coach score count up, the score ring fills, and Coach
    highlights appear one by one. All of it is off for people with
    reduced motion turned on.
- **Verified:**
  - **Browser:** the login page; opening Harbor Light (its own grants)
    and switching to Riverbend (the user's own data intact).
  - **Account flow:** created a test account (validation messages,
    Welcome page, empty Home with the setup banner), logged out, a wrong
    password was refused, the right one accepted. The test account was
    then deleted.
  - **Discover per org:** Harbor Light got 45 matches, including 52 from
    the California portal (health, housing). Prairie Roots got 32
    (agriculture and food research, conservation, rural).
  - **Visuals:** the fit dial at 92% with its bars; the team diagram
    with a persona card.
  - **Fresh clone:** boots in 1 s, and all six demos build with 6
    grants, 8 questions and 1 library answer each.
  - **Safety suite:** still 9 of 9.
- **Known limit:** utility-company foundations from the shared 74-funder
  list (AEP, Entergy) appear for demos outside their service states. The
  Fit Agent marks them down on geography, but the free first-pass filter
  doesn't screen foundations by state yet.

## 2026-10-23 — Funder reporting, board updates, Discover clean-up, chat on the right

- **Prompts (summarised):**
  1. Every organisation should have grants it has won and lost. For won
     grants: upload the funder's reporting requirements, upload programme
     reports to source materials so the AI can draft and review, and
     generate a Word document and a PowerPoint deck for the funder.
  2. Move the chatbot to the right.
  3. Generate a Word document and PowerPoint deck for the board: where we
     are, what's coming, what we've won in the past six months, what
     we're working on.
  4. Icons next to funder names on Discover showing what they mainly fund.
  5. Discover cards should describe the grant under the deadline, not the
     fit; the match details belong in the opened panel. There, "How the
     score is built" should merge into the top fit bars, each opening
     like the old dimension rows.
- **What was lacking before:** the app stopped at submission. There were
  no outcomes, no reporting, and nothing for the board. Discover cards
  were crowded with match reasons and didn't say what the grant was for,
  and the fit panel showed the dimensions twice.
- **Built:**
  - **Grant history:** helper agents added it to the five demo files, and
    Riverbend's is in `data/sample/riverbend_outcomes.json`. Each
    organisation has:
    - two won grants within six months, one with a report due in about
      18 days, each with realistic funder reporting requirements, 4
      report sections that match them word for word, and a programme
      report in the source documents;
    - one lost grant with funder feedback.

    Validated in code. Added to existing demo databases automatically
    (and to Riverbend's, after a backup).
  - **Database:** new outcome columns (awarded amount, result date, grant
    period, report due, reporting requirements, lost reason). Questions
    gained a `kind`, so report sections never count as application
    questions. Marking a grant Won or Lost records the date.
  - **Reporting workspace** (`/report/<id>`): the application editor,
    reused. The Grant Writer is told it is writing a report on delivered
    results and is given the requirements. The header has the
    requirements, uploads for new requirements (the Research Agent turns
    them into sections, kept only if word for word) and programme reports,
    and Word / PowerPoint export.
  - **Reports page** (new top-menu item): funder reports with due-date
    badges and progress, the board update, and recent decisions with
    feedback.
  - **Exports** (`exports.py`): python-docx and python-pptx, styled like
    the app: compass logo drawn as a PNG, green accent, serif headings, a
    facts table, unwritten sections flagged. The board deck has stat
    cards and a native, editable bar chart.
  - **Board summary** (`board.py`): facts computed in code. The Executive
    Director writes an optional summary, and every number in it must
    appear in the facts or that sentence is removed.
  - **Discover:**
    - an icon set (tree, heart, book, cap, sprout, briefcase, wheat,
      house, palette, coin, landmark, globe, people, scale), chosen from
      the funder's own words;
    - the funder's description on cards;
    - "Why it matched your profile" moved into the panel;
    - the fit bars now expand (evidence level, weight, reasoning,
      quotes), and the duplicate "How the fit score is built" list was
      removed (also on grant pages).
  - **Chat:** moved to the bottom right; the button grows leftwards.
- **Verified:**
  - **Harbor Light in the browser:**
    - Reports showed 2 won grants (report due in 18 days), $205k won and a
      67% win rate. The menu fits with 7 items.
    - Draft with AI wrote a report section from the programme report in
      10 s (760 patients, 1,190 visits; 0 missing facts; $0.0008).
    - The Word download returned a real .docx.
    - The board AI summary took 4 s with every number verified.
    - Uploading new requirements added 2 sections word for word; a
      programme-report upload landed in the source documents.
    - Discover cards show icon and description, and the panel has the
      match reasons plus 7 expandable bars.
  - **Rendered output:** the Word report and board deck were previewed
    with Quick Look (clean, on-brand). Word's default blue title rule was
    recoloured green.
  - **Fresh copy:** all six organisations build won/lost history, 4
    report sections each, and all four exports. Safety tests 9 of 9.
- **Known limits:**
  - Every demo has the same win rate (2 of 3), because of the spec.
  - The deck turns report text into bullet points by sentence, without
    AI, so very long sentences make long bullets.
  - Only the first slide of each deck was visually checked (Quick Look
    previews one page).

## 2026-10-23 — Website-to-profile, "applied before?", and a data-isolation fix

- **Prompts (summarised):**
  1. Ideas for internal messaging between teammates (discussion only).
  2. When building a new profile, accept a public website and have the
     agents fill in as much of the profile as possible.
  3. Discover should say whether you've applied to a funder before.
- **What was lacking before:** new organisations started from a blank
  form, and Discover couldn't tell you about past dealings with a funder.
- **Built:**
  - **`profile_builder.py`:**
    - The Research Agent reads the homepage plus up to five key pages
      (about, mission, programmes, impact, team, financials), skipping
      blogs, news and files, and respecting robots.txt.
    - It returns field, value and an exact quote. Code drops any field
      whose quote isn't on the site, checks answer choices and numbers,
      and only fills blank fields.
    - It records which fields came from the site, and saves the pages as
      source documents.
  - **Sign-up and profile:** sign-up has a Website field. The Welcome page
    reads the site with a live "Reading…" panel, then lists what was
    filled. Edit profile shows "from your website" badges and a "Fill from
    your website" tool. Saving the form now keeps the app's notes about
    sources.
  - **`funder_history.py`:**
    - It matches funder names by their distinctive words (generic words
      like Foundation, Community, Fund are ignored) against every pipeline
      grant and the profile's funding history.
    - Discover cards get a chip ("Applied before: won $75k · Aug 2026",
      "not funded", "awaiting decision", "already in your pipeline",
      "you decided not to apply").
    - The opened panel lists "Your history with this funder", with links
      and the funder's feedback.
- **Serious bug found in testing, and fixed:**
  - **What happened:** the open organisation was a process-wide global.
    During the 15-second website import, another browser tab signed in
    as Riverbend (polling for updates) switched it mid-request. The
    import wrote Reading Partners' mission, programmes, theory of change,
    website and 5 web pages into **Riverbend's** data.
  - **The fix:** the database and log locations are now per-request
    context variables (`db.use`, `llm.use_logs`). A `ContextPool` carries
    them into Discover's worker threads (searches, directory checks,
    assessments).
  - **Proof:** two threads working as Harbor Light and Prairie Roots at
    the same time, each also using pool workers, made 1,200 reads with 0
    crossing over.
  - **Repair:** Riverbend's profile was restored exactly from the backup
    taken before the session's work, and the 5 stray pages were removed;
    both were verified.
- **Verified in the browser:**
  - **Sign-up with readingpartners.org (a real public site):** 13 fields
    filled from 5 pages, all quote-checked, about 15 s and about $0.001.
    The Welcome page showed the account's own numbers (45%, 5 documents,
    1 person), with 13 "from your website" badges. Riverbend's profile
    was confirmed unchanged afterwards.
  - **"Applied before?":** pasting a new call from Dayton Readers' Circle
    in Riverbend showed "Your history with this funder: Won, Early
    Reading Success Grants, 22 Aug 2026, $75,000". A Riverbend search
    flagged the Mott Foundation ("Already in your pipeline: Go / No-Go").
  - **Clean-up:** test accounts deleted; safety tests 9 of 9.
- **Known limits:**
  - Name matching is word-based, so "Ford Foundation" and "Ford Family
    Foundation" would count as a possible match (the panel names the
    exact past funder so you can judge).
  - Sites that need JavaScript to show text can't be read.

## 2026-10-23 — Teammate comments on the text (messaging idea #1)

- **Prompt (summarised):** build idea 1 from the messaging brainstorm:
  comments anchored to the words of an answer, Google Docs-style, with
  @mentions that become asks.
- **What was lacking before:** teammates had no way to discuss a draft
  inside the app; feedback had to happen in email or Slack, away from
  the words it was about.
- **Built:**
  - **Storage:** a `comments` table (threads and replies, the quoted
    words, author, assignee, resolved). It is cleaned up when a question
    or grant is deleted. `open_asks()` and `open_comment_counts()` feed
    Home and the question list.
  - **Editor:** select words in the answer and **💬 Comment** becomes
    available (`assets/menu.js` passes the selection to a hidden input).
    It opens the new Comments tab with the quote ready.
  - **Comments tab:** "Commenting as" (remembered for the session), a
    composer with "Ask someone" and @mention detection, and threads:
    - the quote, which jumps to and selects those words in the answer
    - author, time, the person asked, replies
    - Resolve / Reopen (a reply reopens a resolved thread)
    - "these words have since changed" if the text was edited away
    - resolved threads folded
  - **Elsewhere:** "💬 n" badges in the question list; a **Waiting on
    people** card on Home (who, the quoted words, who asked and what,
    linking straight to the question). Compass Assistant gained an
    `open_asks` tool (read-only), so "What's waiting on Sam?" works. The
    safety test's read-only list was updated.
  - **Demo data:** two sample threads per demo: an ask to check the
    weak first sentence against the impact report, with a reply, and a
    resolved suggestion.
- **Verified in the browser** (Riverbend):
  - Home listed the open ask, and its link opened Q1 with "💬 1" and
    "Comments (1)".
  - Selecting "612 students…" enabled Comment. Posting "…@Sam please
    confirm…" gave "Asked Sam Ortiz. It's on their list on Home", and the
    counts went to 2.
  - Reply added; Resolve moved the thread to Resolved; clicking a quote
    selected exactly those words in the answer.
  - Fixed during testing: five editor tabs made "Comments (1)" wrap onto
    two lines; tabs now size to their labels on one line (checked at
    1,440 and 1,100 px).
  - The test comment was removed (sample threads kept); safety tests
    9 of 9.
- **Not built (other ideas from the list):** handoffs, a grant-level
  conversation, agents in threads, daily digest, funder relationship
  notes, board asks.

## 2026-10-23 — Page subtitles made plain

- **Prompt (summarised):** the Reports subtitle ("What you owe the funders
  who said yes, and what to tell your board.") is terrible.
- **What was lacking before:** the line was cute rather than clear.
  Agent health had the same tone ("Is the AI team working properly, and
  is there anything to do?").
- **Change:** both now say plainly what the page is:
  - Reports: "Progress reports due to your funders, and fundraising
    updates for your board."
  - Agent health: "How each AI agent is performing, what it costs, and
    anything that needs attention."
- **Checked in the browser.**

## 2026-10-23 — Privacy policy, data download and account deletion

- **Prompt (summarised):** add a data privacy policy that explains how
  we comply with US law.
- **Approach:**
  - A policy can't certify legal compliance, and overstating it is itself
    a deceptive practice under the FTC Act. So the policy describes
    exactly what the app does, and for each relevant law explains when it
    applies and how the app meets it (or why it doesn't apply).
  - Every claim was checked against the code first: an audit of every
    outbound connection found the AI provider (Portkey → OpenAI / Azure
    OpenAI), Grants.gov and the California portal (keywords only),
    funder and organisation websites, and Google Fonts (IP address).
- **Gap found and fixed:** the rights a privacy policy promises didn't
  exist. Added `orgs.export_data` (every table plus the usage log and
  account details, never the password hash) and `orgs.delete_account`
  (removes the account, the organisation's database and its logs; demos
  are reset instead).
- **Policy page** (`/privacy`, readable without signing in):
  - an "In short" box and a "Your data" card (Download my data; Delete
    my account with confirmation, or Reset this demo);
  - 13 sections: scope, what's collected, use, AI processing, other
    services, cookies (one signed session cookie; DNT/GPC respected
    because nothing tracks), storage and security, retention, rights (45
    days to respond), what not to upload (SSNs, payment data, PHI,
    student records, children's details);
  - a 9-row table of US laws: FTC Act §5, CalOPPA, state comprehensive
    privacy laws (CCPA/CPRA and the states whose laws can cover
    nonprofits), COPPA, FERPA, HIPAA, GLBA, CAN-SPAM, state
    breach-notification laws;
  - changes, contact (a placeholder address to replace), and a
    not-legal-advice note.
- **Linked from:** a footer on every page, the login page, the sign-up
  form ("By creating an account you agree…"), and the organisation menu
  ("Privacy & your data").
- **Verified in the browser:**
  - Signed out: the policy loads (13 sections, 9 laws), with no data
    controls.
  - Signed in with a throwaway account: Download returned the JSON (no
    password hash). Delete account sent me to the login page, and the
    account, its database and its logs were confirmed gone.
  - Fixed during testing: the summary's "nothing else leaves" left out
    the font request; it now matches section 5.
- **For a real deployment:** replace `privacy@grantcompass.example`, and
  consider self-hosting the fonts to remove the Google request. Have
  counsel review the policy.

## 2026-10-25 — Pre-submission audit; two real bugs fixed; team diagram by job title

- **Prompts (summarised):**
  1. Re-read the requirements and list what's missing, apart from the
     slides and the report.
  2. Explain the "1 agent needs attention: Fit Agent" banner on Agent
     health.
  3. Team diagram: show the job title instead of a person's name, and
     where the job title was, the agent and where it works in the app.
- **Audit (requirements unchanged, due 26 Oct, 6 PM):**
  - A fresh copy of the publishable files, with `.env` one folder up,
    installs and runs in 31 s.
  - All six demos load; an AI call works; no secrets in tracked files.
  - Every file parses with Python 3.9's grammar (no newest-Python-only
    syntax); the code needs Python 3.10+ at runtime.
  - The repo still has no commits and no GitHub remote.
- **Bug 1, the assistant couldn't see funder reports:** asked "Which
  report is due soonest?", it named an application due in 3 days (no
  tool exposed reports). Added a read-only `funder_reports` tool (won
  grants' report due dates and sections written, plus losses with
  feedback), and "reports" and "privacy" pages for navigation. Now it
  answers correctly (Edisto, 12 Nov, 18 days, 0 of 4 sections); the
  application question still gets the application. Safety test list
  updated.
- **Bug 2, the Fit Agent's quote check used the wrong text:** the banner
  came from "12 of 21 assessments had an unverified quote". Every failure
  was a funder quote. The agent is shown extracted facts plus the full
  text, but quotes were checked only against the full text, so quotes
  correctly taken from the facts were flagged (e.g. "See the full
  announcement at the source link"). Funder quotes are now checked
  against exactly what the agent was shown. A fresh assessment had 0
  warnings. Old warnings in existing local demo databases stay until
  re-assessed; graders' fresh copies start clean.
- **Diagram:** nodes, persona cards and tiles now lead with the job title
  (e.g. "Prospect Research Manager"), then the agent and page ("Research
  Agent · Discover page"). People's names were removed (also from the
  Welcome page and README). Avoided "Executive Director · Executive
  Director", and made room so the bottom label no longer touches the
  legend. Checked in the browser.

## Real-user test kit, and re-checking saved Fit quotes

**Prompts:** "Prepare a short real-user test kit (15-minute script, 3 tasks,
timing sheet, quote capture) I can run today." Then, with a screenshot of
Agent health still showing "1 agent needs attention: Fit Agent": "it still
says this, why?"

**What was lacking before:** no structured way to run and record a real-user
session (the rubric's Impact evidence). And the earlier Fit quote fix only
applied to new assessments: saved ones kept warnings from the old faulty
check, so the banner didn't change.

- **Test kit:** `user_test/user_test_kit.html`, self-contained. It includes:
  - setup and consent script, and "today" time estimates
  - 3 timed tasks: Discover and decide; draft and review with AI; board update
  - wrap-up questions (NPS, trust, would pay) and quote capture
  - an automatic before/after timing sheet with a yearly-hours estimate
  - browser autosave, Markdown export and Print/PDF

  Checked in the browser: timer, autosave and Markdown export work, with no
  console errors. Test entries were cleared.
- **Saved Fit assessments re-checked:**
  - Each assessment now records which quote check produced it
    (`quote_check = 2`).
  - On startup, saved assessments for pipeline grants and foundation-
    directory results are re-checked against the funder text the agent saw.
    Evidence levels are never raised.
  - Grants.gov search results don't keep their full text, so they can't be
    re-checked. Agent health leaves them out of the quote figure and shows
    their count as a separate info line, instead of hiding the problem.
  - "Watch" now needs at least 3 checked assessments.
- **Result:** every demo organisation's Fit Agent is Healthy (e.g.
  Riverbend: 9 of 30 still fail). The remaining failures are real: quotes
  of an older profile layout ("Headquarters (city, state)") and spellings
  that differ from the funder text. The banner now reads "All six agents
  are healthy". Data was backed up to the scratchpad first.

## Grant Coach tab folded into Applications

**Prompt:** "I don't like the grantcoach tab, shouldnt that just be in the
applications page as part of the review per question?"

**What was lacking before:** the top menu had a separate Grant Coach page
where you pasted a question and an answer by hand. Every application question
already has the same Coach and Evidence Checker under Review suggestions, with
highlights and Accept/Reject, so the tab repeated it with fewer features and
crowded the menu.

- Removed the Grant Coach tab and its page (`ui/coach_page.py`). The old
  `/coach` address now opens Applications.
- The Applications subtitle now says where the review lives: in any
  question, Review suggestions runs the Grant Coach and the Evidence Checker.
- Updated the Compass Assistant's page list and prompt, the "where it works"
  labels on Agent health ("Applications, per question") and the README.
- The Grant Coach agent itself is unchanged.
- Checked in the browser: the menu, the Applications page, the `/coach`
  redirect and the Agent health labels, with no console errors. Safety
  tests 9/9.

## Safety review, and four web-app gaps closed

**Prompts:** "how am i doing in terms of safety of the app?" Then: "Yes, fix
all four gaps, add them to the safety tests, and log it."

**What was lacking before:** the AI side was well defended: 9 attack tests,
prompt injection, read-only tools, checking done in code. The ordinary
web-app side had four gaps:
- Pasted links, and links inside funder pages, could reach localhost, the
  office network or the cloud metadata address (server-side request
  forgery), including through a redirect.
- Uploads had no size limit.
- Logins could be retried without limit.
- Nothing proved that two organisations' data stay apart when requests
  overlap.

- **Links:** new `grantcompass/netsafe.py`.
  - Each host is resolved and must be a public address.
  - Redirects are followed one hop at a time, and every hop is re-checked
    (and must stay on an approved site for automatic watchlist checks).
  - Used by the Research Agent, robots.txt checks, the watchlist and
    directory, and Profile-from-website.
  - Public sites still load (checked on MacArthur and Kresge, including an
    http→https redirect).
- **Uploads:** each file is capped at 10 MB, checked from its encoded size
  before decoding or parsing, with a plain message. The server refuses any
  request over 64 MB. Session cookie is HttpOnly and SameSite=Lax.
- **Logins:** after 5 wrong passwords in 15 minutes, that email is locked for
  the rest of the window, even with the right password. Unknown emails take
  as long to check as real ones, so response time doesn't reveal which
  accounts exist.
- **Tests:** four new tests: internal links and a redirect to the metadata
  address; an oversized upload; password guessing; 8 simultaneous requests
  across two organisations, including background workers (160 reads, 0
  leaks). **13/13 pass** for $0.0019. `tests/safety_results.md` is
  regenerated, and the README is updated.
- **Browser check:** pasting the metadata address in Discover shows "Grant
  Compass only reads public websites…".
- **Known limit:** the lockout is kept in memory, so restarting the server
  resets it. That's fine for a local, single-process app; a hosted version
  would store it, and limit by IP address too.

## Quick app fixes before the report

**Prompt:** "Yes, do the quick app fixes now: Python 3.10+ README note,
out-of-state utility grants in demos, varied win rates per demo org, and the
Discover import button layout."

**What was lacking before:**
- The README didn't say which Python was needed. On a Mac's default 3.9
  the app crashed with a confusing error.
- Utility and community foundations showed up for organisations outside
  their service area (e.g. Entergy for a California demo), because their web
  pages don't name states.
- Every demo had the same 67% win rate (2 won, 1 lost), which looked
  fabricated.
- On Discover, the "Assess opportunity" button sat about 1,300px down,
  below the long "Foundations you follow" card.

- **Python:** the README now says "Needs Python 3.10 or newer", with what to
  do on 3.9. `app.py` exits with a one-line message on older Pythons. Tested
  with the system Python 3.9.6.
- **Service areas:** the 20 regional funders in `data/funder_directory.json`
  (Duke Energy, Entergy, AEP, PPL and 16 community foundations) now list the
  states they give in. These come from the directory, not the AI.
  - Discover excludes them outside those states, with the reason ("Only
    funds in Arkansas, Louisiana, Mississippi and Texas").
  - The chat assistant's matches are filtered the same way.
  - Ohio and Texas demos still see AEP/Entergy correctly; California,
    Nebraska and South Carolina don't.
- **Win rates:** added fictional past outcomes so demos differ:
  - Riverbend 67%, Bright Orbit 40%, Cedar Ridge 75%
  - Harbor Light 60%, Prairie Roots 50%, Tidewater 33%

  Each loss has funder feedback. The added outcomes were applied to the local
  demo databases and confirmed on a fresh copy. SPEC.md was updated.
- **Discover layout:** "Assess one you found" now comes first in the right
  column; its button is on the first screen at 1280×800.
- **Checks:** Reports shows the new win rate (Cedar Ridge 75%), with no
  console errors. Safety tests 13/13.
- **Note:** Riverbend's local pipeline still has AEP and Entergy entries added
  during testing on Oct 18. They're local-only (databases aren't in the repo),
  so graders' fresh copies don't have them.

## Report draft (report/report.html)

**Prompt:** "Yes, start the report, what do you need from me?"

**What was lacking before:** no report. The evidence it needs (a traced run with
screenshots, measured costs, proof that the cost cuts don't hurt quality,
named competitors) wasn't collected in one place.

- **Asked of the user:**
  - a real-user session (required for full Impact marks)
  - an optional "start with a person" story
  - how their name should appear
  - the GitHub link, which needs their go-ahead to commit
- **Traced run** (`report/trace.py`, Playwright with installed Chrome, in its
  own `report/.venv`), on the Cedar Ridge demo:
  - a real San Antonio Area Foundation link → Research → Fit 59%,
    "Research further"
  - → Draft (174/250 words) → Coach 65/100, 6 suggestions
  - → Evidence: 7 Supported, **2 Contradicted**. The Writer had labelled Q1
    2026 figures as 2025-26, and the checker caught it.
  - Whole run: $0.0058.
  - Also captured: Discover, Pipeline, Agent health, Reports (board
    update), chat, and an injection flagged in red.
- **Real bug found by the trace:** the Fit Agent built a quote from three
  separate profile lines, and wrote "Award amounts are not stated" as if it
  were a quote. `quote_found` now accepts line-split verbatim quotes, and
  "not stated" notes count as no quote. `QUOTE_CHECK` is now 3; stored
  assessments are re-checked automatically.
- **Cost experiment** (`report/cost_experiment.py`): 18 Fit runs on 6 grants,
  logged to a temp folder.
  - Cache-friendly order: 88% of input cached, 35% cheaper.
  - Medium reasoning: +58% cost, 4 s slower, no more consistent.
  - Borderline recommendations flip between "Research further" and
    "No-Go" even with identical settings. Added as a limit.
- **Sources:** competitor pricing (Instrumentl, Candid FDO, Grantable),
  sector data (Candid, GrantStation via SSIR, SmartyGrants) and freelance
  rates were found by web search and cited in the report.
- **Builder:** `report/build_report.py` pulls every number from the logs,
  safety results and experiment JSON, and embeds cropped screenshots. Output
  is a 1.6 MB self-contained HTML file, **14 printed letter pages**, with
  print CSS. "TO ADD" boxes (hidden when printed) mark what the user must
  supply.

## Report: 15 click-through pages, personal motivation, requirements check

**Prompt:** "Break this into 15 pages that you can scroll or click through. In
motivation, explain how I was a fundraiser and faced these issues. Make the
challenge personal to me. under why care, this is bad, make it about
optimizing our time for the communities we serve. also, make sure that the
report answers all the questions in the requirements"

**What was lacking before:**
- The report was one long scroll, so page breaks fell wherever the browser
  put them.
- Motivation opened with sector data instead of the author's own experience.
- "Why care" was generic.
- Several requirement questions were answered, but not under headings a
  grader could find. Missing were "why the difference matters", an explicit
  "typical run" token breakdown, and safety risks grouped as the brief lists
  them.

- **Layout:** 15 fixed letter-size pages (8.5×11 in, identical on screen and
  in print; the PDF prints exactly 15 sheets).
  - Navigation: a bottom bar with Prev / Next, "Page n of 15", and a jump
    menu; arrow keys, Page Up/Down, Home/End and Space work too.
  - Each page has a footer, there's a contents list with links on the
    title page, and `#p8`-style links open a given page.
  - `report/fitcheck.py` verifies no page overflows.
- **Motivation (pages 2–3), in first person:** "Before business school, I was
  a fundraiser…": eligibility searching, rebuilding old answers, checking
  every number, reports and board updates, and deadlines colliding with
  programme work. No invented specifics: no organisation name, dates or
  figures.
  - "Why care" is rewritten around optimising our time for the communities
    we serve.
- **Requirements mapped to headings:**
  - Who has the problem / How they handle it today / What it costs (money,
    time, frustration) / Why care
  - What already exists / What is different, honestly / Why the difference
    matters
  - How they're organised and who hands work to whom / Each agent and its
    tools / Models and why / One real run traced
  - Tokens per run (input, cached, output) / A typical run / Cost per user
    per month / At 100 and 10,000 users / Cost cuts / Did the cuts hurt
    performance
  - Safety risks grouped as Attacks (injection, data leaks), Agent
    malfunction (invented facts, wrong action, infinite loops) and
    Overspending
  - Impact: a real user, measured numbers with sources, what's newly
    possible
  - Limits / With another month
- **Added visuals:** the home screen on page 2, plus HTML bar charts of
  spend by agent (page 9) and experiment cost per setting (page 11).

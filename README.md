# Grant Compass

An AI grant research and writing workspace for nonprofit teams. It helps a
Development Director find grants and decide which are worth pursuing,
organise the work required to apply, and write stronger applications from
evidence the organisation already has.

Each AI agent has one job, every AI judgement shows its evidence, and the
human makes every decision. Seven agents: Research, Fit, Grant Writer, Grant
Coach, Evidence Checker, Compass Assistant (a chat helper that can look
things up and navigate, but never edit), and an Executive Director that
reviews how the other six are working.

## Run it locally

**Needs Python 3.10 or newer.** Check with `python3 --version`. Many Macs
come with 3.9; if yours does, install a newer Python (python.org or
`brew install python@3.12`) and use `python3.12` in step 2.

1. Clone the repo and enter the folder:
   ```bash
   git clone https://github.com/GabriellaSaven/grant-compass.git
   cd grant-compass
   ```
2. Create a virtual environment and install the requirements:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Provide the API key. The app looks for a `.env` file **in this folder
   first, then in the folder above it**. It needs one key (see
   `.env.example`):
   ```
   PORTKEY_API_KEY=your-key
   ```
4. Start the app and open http://127.0.0.1:8050
   ```bash
   python app.py
   ```

## Getting in: three ways

The app opens on a front door with three choices:

1. **Explore a demo organisation** (fastest for graders, no password). Six
   fictional nonprofits, each with a full profile, six source documents, a
   three-person team, six grants at every pipeline stage, eight application
   questions (from empty to approved) and one approved answer in the Answer
   Library. They work in different fields and states, so **Discover finds
   different funders for each**:

   | Demo | Where | Field | Discover searches |
   |---|---|---|---|
   | Riverbend Reads | Dayton, Ohio | Early literacy | literacy, K-12, early childhood |
   | Bright Orbit STEM Lab | Detroit, Michigan | STEM for girls | K-12, women, youth |
   | Cedar Ridge Veterans Collaborative | San Antonio, Texas | Veteran housing & jobs | housing, workforce, veteran |
   | Harbor Light Health Collective | Oakland, California | Community health | health, mental health, housing + California Grants Portal |
   | Prairie Roots Food Alliance | Grand Island, Nebraska | Rural food security | food, environment, rural |
   | Tidewater Arts & Heritage Center | Charleston, South Carolina | Arts & heritage | arts, civic, racial equity |

   Each demo's first application has a deliberately weak first answer (an
   unsupported "leading provider" claim, a number that contradicts the
   documents), so the Coach and Evidence Checker have something real to
   catch. **Reset this demo** (organisation menu) undoes your changes.
2. **Start your organisation:** create an account (stored only on this
   computer; passwords are salted hashes), then a three-step welcome page
   walks you through your profile, documents and team. **Add your public
   website** and the Research Agent reads your homepage and up to five key
   pages (respecting robots.txt) to fill in as much of the profile as it
   can. Each field must be backed by words found on the site, it only fills
   blank fields, every one is marked "from your website" for you to check,
   and the pages are saved as source documents. **Fill from your website**
   on Edit profile does the same at any time.
3. **Log in** to an account you created earlier.

Each organisation has its own database (`data/orgs/<org>.db`; Riverbend uses
`data/grantcompass.db`) and its own usage logs, so nothing mixes between
organisations, including Agent health. Deadlines are set relative to today, so
the demos always look current. Demo content lives in `data/demo_orgs/*.json`
(format in `data/demo_orgs/SPEC.md`); every name, funder and figure is invented.

## A two-minute tour

1. **Home** is a mission-control view: the key numbers, a 60-day deadline
   timeline (one dot per grant, coloured by risk, click to open), funding by
   stage as one bar, and what needs attention today.
2. **Pipeline** lists every grant with:
   - **Fit:** fit % and recommendation (Go / Review / No-Go).
   - **Funding** amount.
   - **Deadline**, and **stage & progress**.
   - **Risk** (On Track / Needs Attention / At Risk / Critical). Hover or
     click it to see the facts and the rule behind it.
   - **Next action:** a clickable step (e.g. "Draft Q3", "Make Go / No-Go
     decision", "Overdue: Complete first draft").
   - **Responsible** person.
   - **Origin tag** on each grant (e.g. "Found via Grants.gov", "Uploaded
     PDF", "Added from URL").

   You can filter by responsible person, deadline, status, risk and funder
   or programme area. Click a row to open the full record in a pop-up.
3. Open **Buckeye Family Literacy Trust** and click **Run Go / No-Go
   assessment**. The Fit Agent scores seven dimensions with quotes from the
   funder and from your documents, answers eight Go / No-Go questions, and
   recommends Go, Research further or No-Go.
4. Under **Your decision**, accept or override the recommendation (an
   override needs a reason). Choosing **Go** builds a workback plan from the
   deadline and moves the grant to Drafting.
5. Open **Great Lakes STEM Futures Initiative** and run the assessment. Its
   page contains a planted prompt injection. The app flags it and ignores it,
   and the eligibility gate forces No-Go.
6. **Discover** searches open grants for a nonprofit in any state. Each
   result shows an icon for what the funder mainly supports (tree for
   environment, heart for health, book for literacy…) and the grant's own
   description; click it for why it matched your profile and the fit dial,
   whose seven bars open for the reasoning and quotes. **Applied before?**
   A chip on each result (and a "Your history with this funder" list when
   opened) shows if you've won, lost, submitted, declined or are already
   working on a grant from the same funder, with the funder's feedback.
   Sources:
   - **Federal:** every open federal grant, from the free Grants.gov API.
   - **Major foundations:** a built-in directory of 74 large private,
     corporate and community foundations. 100 were checked; the other 26 are
     excluded with reasons. See `FUNDER_SOURCES.md`.
     - Pages are checked in parallel, and only pages that changed are read
       by the AI.
     - A pre-read cache ships in `data/funder_directory_cache.json`, so a
       fresh install doesn't re-read them all.
     - Opportunities that are closed or invitation-only go to "Filtered
       out" for free.
   - **State portal:** added automatically when the Profile's state has an
     open one (currently California).
   - **Funder watchlist:** the foundation and community-foundation pages
     your team follows, anywhere. Adding a page approves that site.
     Unchanged pages are not re-read by the AI.
   - **No-AI triage:** results are ranked by plain rules on your Profile
     (focus areas or typed keywords, populations, deadline vs. preparation
     time, award size, eligibility, grant types). Every ranking shows its
     reasons, and every filtered-out result says why.
   - **Automatic fit scores:** results appear immediately. Every match is
     then assessed by the Fit Agent in parallel (6 at a time) and the list
     re-sorts by fit. Assessments are saved, so a repeat search is instant
     and free. Results the free rules filter out are not assessed.
   - **Fit panel:** click any result to open a panel on the right. It shows
     Fit %, Recommendation, Why, Concerns, likely application effort and
     expected value, then the seven dimensions that build the score.
     Assessments are cached, so reopening a result is instant and free.
   - **Saving:** **Add to pipeline** in the panel saves the opportunity
     with its assessment attached, so it isn't paid for twice. **Add & start
     application** also records your Go, builds the workback plan and opens
     the writing workspace. **View source** opens the funder's page.
   - **Assess one you found:** upload a PDF or Word application form, paste
     a link (any site; robots.txt is respected), or paste the text. Click
     **Sample** to try a fictional application form.
     - The Research Agent extracts the facts and the application's
       questions with their word or character limits. Only questions that
       appear word for word in the document are kept.
     - The Fit Agent assesses it in the same panel.
     - Starting the application puts every question in the editor, ready
       to draft. **Add one opportunity** still imports a
     single page or pasted text.
7. **Profile menu** (top right, under your organisation's name) has two
   parts:
   - **Edit profile:** the structured form (see below).
   - **Source documents:** upload PDF, Word, text or Markdown files
     (reports, budgets, past applications) and mark strong text as
     *approved organisational language*. The AI writes only from your
     Profile and these documents.
   - **Team:** the people who can be responsible for a grant, with the
     active grants each one owns. You can also add someone straight from
     the **Responsible** field on any opportunity (**+ Add a person**).
8. **Edit profile** is a structured form covering basics, mission and
   programmes, who and where, finances, capacity, outcomes, funding
   history, grant preferences and writing voice.
   - **Matching:** the profile is the first document every agent reads. The
     Fit Agent uses grant preferences (smallest award, largest match,
     preparation time, areas to avoid) when scoring.
   - **Missing fields:** blank fields are passed to the agents as "Not
     provided", so they are reported as missing, never guessed.

9. **Applications** lists every grant being written, with answers done,
   answers approved, average coach score and claims still to fix. Open
   **Miami Valley Early Learning Fund** to try the writing workspace:
   - **Editor:** your own text, with a live word or character count against
     the funder's limit and version history. It **saves automatically** a
     second after you stop typing (and when you click away); edits within
     10 minutes share one history entry. You set each question's status;
     only you can mark it Approved. **✎ Edit question** (top right of the
     editor) changes the question's wording or its word / character limit
     without touching your answer.
   - **✦ Draft with AI** (above the editor): the Grant Writer drafts from your
     Profile and source documents only, cites a source for every fact, and
     writes [MISSING: …] instead of guessing. The draft goes into the editor;
     **Undo** brings back your previous text, which also stays in Version
     history. Under the editor you see the missing facts and where each fact
     came from.
   - **Sources:** library passages related to the question, with approved
     language first. Plain keyword matching, no AI.
   - **Coach:** works like VMock and Grammarly.
     - **Score card:** a score ring with a plain verdict (Strong / Getting
       there / Needs work), a "Start here" priority, a ✓ / ◐ / ✕ checklist
       of what the question asks, and colour-coded scores for ten areas
       (hover for the reason).
     - **Review suggestions:** the editor switches to a marked-up view of
       your answer. The Coach runs on its own in the background the moment
       you open it (only if the answer changed since its last review, so
       switching back and forth costs nothing); there is no button to press. Each issue is underlined in its type's colour (evidence,
       be specific, outcomes, answer the question, clarity…). Click a
       highlight to pin its suggestion card right there: the problem, why
       it matters, the suggested wording, and ✓ Accept / ✕ Reject. Close it
       with × or a click outside. The same suggestions are also listed in
       the Coach panel on the right.
     - **Undo / Redo:** every change can be undone and redone: each pause
       in your typing, an AI draft, or an Accept or Reject (which restores
       the highlights too).
     - **Your control:** nothing changes unless you click Accept, and Undo
       reverses it. Suggestions never add facts; where a fact is needed they
       insert [MISSING: …].
   - **Evidence:** every claim is marked Supported / Weakly supported /
     Needs evidence / Contradicted. Click a claim to see the source passage
     in context.
   - **Comments, Google Docs-style:** select words in an answer and click
     **💬 Comment**. Type @ and a teammate's name (or pick "Ask someone") to
     turn it into an ask for them. The **Comments** tab holds the threads:
     click a quote to jump to those words, reply, resolve or reopen; a
     comment whose words were later edited away says so. Questions with open
     comments show 💬 in the list, **Home** shows everything "Waiting on
     people", and Compass Assistant can tell you what's waiting on whom.
     Each demo starts with two sample threads.
   - **★ Add to Answer Library:** saves a finished answer (no [MISSING: …]
     gaps allowed) as approved wording to reuse. Saving the same question
     again updates its entry.
   - **Library tab:** approved answers that fit the current question (same
     topic or similar wording), each with **Use this answer** (Undo brings
     your text back) and Copy.
10. **Reports** (top menu) covers what happens after a grant is decided:
    - **Reports owed to funders:** every won grant, its next report due date
      and progress. Open one to write the report in the same editor as
      applications (Draft with AI, Coach, Evidence, Undo, autosave). The
      header holds the funder's reporting requirements; **upload new
      requirements** and the Research Agent turns them into report sections
      (kept only if they appear word for word). **Upload programme reports**
      to your source documents so Draft with AI reports real results, not
      plans. **Download a Word report and a PowerPoint deck** to send.
    - **Board update:** won and lost in the last six months (with funder
      feedback), win rate, what's awaiting decisions, what's in progress,
      deadlines and reports coming up, and potential funding by stage, as a
      **Word document and a PowerPoint deck** (with a native chart).
      Optionally, the Executive Director writes a summary for the board;
      any sentence with a number that isn't in your records is removed.
    - **Recent decisions:** wins and losses, with what funders said.

    Every demo organisation has two won grants (one report due within
    about three weeks) and one lost grant. Marking a grant Won or Lost
    yourself records the date, so it appears here too.
11. **Answer Library** (top menu): every approved answer with its topic,
    original question, funder, length and how often it has been reused.
    Search, filter by topic (Mission, Need, Programme design, Outcomes &
    evaluation, Capacity & partners, Budget & sustainability, Equity), copy,
    or remove. **Add a past answer** pastes in wording from old
    applications. Topics and matching are keyword rules, not AI, so they are
    instant and free. The Grant Writer may adapt these answers too.
12. **Agent health** (organisation menu, top right) opens with **Meet the
    team**: a diagram of the seven agents as colleagues on a development team,
    each shown by its nonprofit job title, the agent, and where it works in the
    app: Prospect Research Manager (Research Agent, Discover page); Director
    of Grant Strategy (Fit Agent, Discover & Pipeline); Senior Grant Writer
    (Grant Writer, Applications & Reports); Grant Readiness Coach (Grant Coach, Applications per question);
    Evaluation & Impact Manager (Evidence Checker, Applications per question); Development Associate
    (Compass Assistant, chat on every page); Executive Director (Agent health
    & Reports). Arrows show how work flows; ring colours show
    health; click anyone for their job, sources and guardrails. Below it, it shows each agent's
    runs, cost per run, speed, failures and safety checks: quotes that failed
    verification, unverified cited facts, injection attempts flagged, how often
    you overruled the Fit Agent. All of it is computed from the logs, without
    AI. **Run review** asks the **Executive Director** agent for a short
    briefing: what's healthy, what to watch, and what to do next. It sees only
    those numbers, never funder pages. The app deletes any finding whose
    number doesn't match its data, and never lets its rating be rosier than
    the app's own rules.
13. **Compass Assistant** (the hand-and-heart button, bottom right on every
    page) answers questions in plain English: "What should I work on this
    week?", "Which deadlines are coming up?", "Which grants are at risk, and
    why?", "Which new opportunities fit us best?", "What's still missing
    from our Miami Valley application?", "Who is responsible for what?".
    It can also take you anywhere: "take me to Discover", "open question 2
    of the Miami Valley application". It looks everything up with read-only
    tools and can navigate, but it can't change your data, and it treats
    funder text and documents as data, not instructions. Enter sends;
    Shift+Enter adds a new line.

## How it works

| Agent | Job | Output |
|---|---|---|
| Research Agent | Reads a watchlist page, a link you give it (respecting robots.txt), an uploaded PDF/Word file or pasted text, and extracts the facts and the application questions | Funder, programme, deadline, geography, eligibility, award, restrictions, requirements, source URL |
| Fit Agent | Judges the opportunity against your Profile and source documents | Seven scored dimensions with evidence, eight Go / No-Go answers, recommendation, risks, missing information, next steps |
| Grant Writer | Drafts one answer from the library only | Draft with [MISSING: …] placeholders, a source for every claim, list of missing facts |
| Grant Coach | Critiques one answer; never rewrites | Question broken into parts (addressed or not), ten category scores, strengths, weaknesses, suggestions, top priority |
| Evidence Checker | Tests every claim against the library | Supported / Weakly supported / Needs evidence / Contradicted, with the source quote |
| Executive Director | Reviews the other six agents' reliability, safety checks, human overrides and cost; briefs the human | Overall Healthy / Watch / Act, findings each tied to one verified metric, top action |
| Compass Assistant | Answers a fundraiser's questions in chat using 7 read-only tools (pipeline overview, grant details, Discover matches, live Grants.gov search, profile and documents, team workload, AI spending) and one navigation tool (open any page, grant or application question) | A short answer built only from tool results; opens the page when asked |

Pipeline status, days remaining, progress, risk labels and workback plans are
plain date logic, not AI, so they are instant, free and always correct.

**Evidence and safety:**

- **One model.** Every AI call uses `gpt-6-luna` through Portkey.
- **Fit score is calculated by the app.** It is the weighted average of the
  dimension scores, using the weights shown in the interface. Unknown
  dimensions are left out rather than guessed.
- **Evidence labels.** Every dimension is marked **Supported** (quoted from
  an org document), **Inferred**, or **Missing**.
- **Quote checking.** Every quote is checked word for word against its source
  document. An unverified quote cannot show as Supported.
- **Untrusted funder text.** Funder text is fenced off as untrusted. Any
  instructions inside it are flagged and never followed.
- **Eligibility gate.** If a hard eligibility rule fails, the recommendation
  is forced to No-Go, whatever the model says.
- **Approved sources.** Discover only fetches sites on the approved list in
  `grantcompass/config.py`.
- **Per-run limits.** Each run has a cap on model requests and tokens.
- **Writing guards (all in code, not the model):**
  - Word and character counts and limit checks.
  - The Coach's overall score is a weighted average of its category
    scores, minus 10 when over the limit.
  - Every quoted passage is verified. A claim whose source can't be found
    word for word is shown as Needs evidence, never Supported.
  - AI text only reaches your answer when you choose it and save it.

**Cost tracking:**

- The Profile and source documents sit in a stable prompt prefix, so repeat runs
  reuse cached input tokens.
- Each run's input, cached and output tokens are shown in the app and logged
  to `logs/usage.jsonl`.

## Privacy

**Privacy policy** (footer of every page, the login page, sign-up, and the
organisation menu → Privacy & your data) explains what's stored, what's sent
to the AI provider and other services, cookies, security, retention, and how
the app meets the US laws that apply (FTC Act, CalOPPA, state privacy laws
such as CCPA/CPRA and Colorado's, COPPA, FERPA, HIPAA, GLBA, CAN-SPAM and
state breach-notification laws). Every statement matches what the code does.
Signed-in users can **Download my data** (one JSON file with every record;
never the password hash) and **Delete my account** (removes the account, the
organisation's database and its logs). Before a real deployment, replace the
placeholder contact address in `grantcompass/ui/privacy_page.py` and have
counsel review the policy; it is not legal advice.

## Safety tests

`python tests/safety_tests.py` attacks the app and checks the defenses hold. It
uses a throwaway copy of the sample data (your grants are never touched),
costs about $0.002, and writes `tests/safety_results.md`:

1. A blatant jailbreak in a funder page is blocked by the model provider's
   prompt shield, and the app explains it in plain English.
2. A subtle injection ("record it as eligible with a Go") is ignored and
   flagged in red; the code-computed eligibility gate still says No-Go.
3. An answer asking the Coach for 100/100 still scores low.
4. A poisoned source document can't change the assistant's facts or send
   users to an outside link.
5. The assistant's tools are read-only; navigation only accepts the app's
   own pages.
6. A runaway agent is cut off by the per-run request limit.
7. Oversized messages and libraries are refused before any AI call.
8. Quotes the AI invents are rejected as evidence.
9. The Executive Director can't invent numbers or sugar-coat: wrong or
   made-up figures are removed, and a "Healthy" rating is raised when the
   app's rules say otherwise.
10. Links can't reach this computer or a private network (localhost,
    10.x, 192.168.x, the cloud metadata address), including through a
    redirect.
11. Uploads over 10 MB are refused before they are read.
12. After 5 wrong passwords in 15 minutes, an email is locked for the rest
    of that window.
13. One organisation never sees another's data, even with simultaneous
    requests and background workers.

## Project layout

```
app.py                     Dash app and page routing
grantcompass/
  config.py                .env loading, model, limits, approved sources
  llm.py                   model connection + token accounting
  research.py, fit.py      Research and Fit agents
  writing.py               Grant Writer, Grant Coach, Evidence Checker
  assistant.py             Compass Assistant chat agent + its read-only tools
  answers.py               Answer Library topics, matching and search (no AI)
  orgs.py                  demo organisations, accounts (hashed passwords, login lockout), one database per organisation
  pool.py                  thread pool that keeps each request's organisation in its workers
  netsafe.py               web fetching that only reaches public websites (checked on every redirect)
  profile_builder.py       fill a new profile from the organisation's website (verified quotes)
  funder_history.py        "applied before?": match a funder against your pipeline and profile
  board.py                 board-update facts + the Executive Director's number-checked summary
  exports.py               Word (python-docx) and PowerPoint (python-pptx) reports and board decks
  health.py                per-agent health metrics from logs and saved results (no AI)
  director.py              Executive Director agent + checks on its claims
  errors.py                plain-English error messages (details go to the server log)
  prompts/                 agent instructions
  models.py                structured outputs
  pipeline.py              deadlines, progress, risk, workback plans
  sources/                 Grants.gov and California Grants Portal adapters
  discover.py, triage.py   multi-source search + no-AI ranking against the Profile
  watchlist.py             funder pages, re-read only when they change
  directory.py             built-in foundation directory (data/funder_directory*.json)
  importer.py              assess one opportunity from an upload, link or pasted text
  library.py               document upload + library context
  profile.py               profile form fields, completeness, text for agents
  db.py, seed.py           SQLite storage + fictional sample data
  ui/                      one module per page
assets/style.css           design
tests/safety_tests.py      prompt-injection, malfunction and overspending tests
data/sample/               sample library and opportunities
```

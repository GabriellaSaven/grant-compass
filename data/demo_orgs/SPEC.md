# Demo organisation file format

Each demo organisation is one JSON file in `data/demo_orgs/<slug>.json`. Graders pick one on the login
page and get a fully populated, fictional nonprofit to test Grant Compass with. Everything is FICTIONAL:
invent names, funders and numbers, but keep them realistic and internally consistent (the same facts,
numbers and names must match across the profile, the documents, the application answers and the
library answer). The app's AI agents check answers against the documents word for word, so any fact used
in an answer must appear in a document or the profile.

## Top level

```json
{
  "slug": "kebab-case id, same as the file name",
  "name": "Organisation name as it appears on the login card",
  "tagline": "One sentence (max 14 words) on what they do, for the login card",
  "location": "City, State",
  "cause": "2-4 word label, e.g. 'Community health'",
  "profile": { ... },
  "team": [["Full Name", "Role"], ["Full Name", "Role"], ["Full Name", "Role"]],
  "documents": [ ... 6 items ... ],
  "opportunities": [ ... 6 items ... ],
  "library_answers": [ ... 1 item ... ]
}
```

## profile (every key required; use the allowed values EXACTLY)

- legal_name (str), legal_status: one of "501(c)(3) public charity", "Fiscally sponsored project"
- year_founded (int), headquarters (city), state (full state name, e.g. "California"), website ("" is fine)
- mission (1-2 sentences), theory_of_change (2-3 sentences, "If … then …")
- programmes: one per line, "Name — what it is, how often, where" (3 lines, separated by \n)
- focus_areas: list from: "Early childhood", "K-12 education", "Literacy", "Youth development",
  "Higher education & workforce", "Health", "Mental health", "Food security", "Housing & homelessness",
  "Arts & culture", "Environment", "Economic mobility", "Civic engagement", "Immigrant & refugee services",
  "Disability services", "Racial equity", "Women & girls", "Older adults"
- populations: list from: "Children (0-5)", "Children (5-12)", "Youth (13-18)", "Young adults (18-24)",
  "Adults", "Older adults", "Families / caregivers", "Low-income households", "Communities of colour",
  "English learners", "Immigrants & refugees", "People with disabilities", "LGBTQ+ people", "Veterans",
  "Rural communities"
- population_details (evidence-style percentages), geography (counties/cities), people_served (int)
- annual_budget (int USD), fiscal_year_end (e.g. "June 30"), revenue_mix (e.g. "Foundations 40%, …" = 100%)
- audit: one of "Independent audit, clean opinion", "Independent audit, with findings", "Financial review"
- staff (e.g. "14 full-time, 3 part-time"), volunteers (str), grant_capacity (1 sentence)
- federal_experience: one of "Yes, we manage federal grants directly", "Only as a subrecipient", "No"
- outcomes: 3 lines with numbers and the year (e.g. "2025-26: …"), separated by \n
- evaluation (1-2 sentences), current_funders: 2-3 lines "Funder — amount — years" (fictional names)
- grant_types: list from "General operating", "Programme / project", "Capacity building", "Capital",
  "Research", "Event"
- min_award (int), max_match (str), lead_time_days (int), avoid (1 sentence)
- voice: one of "Warm and plain-spoken", "Formal and academic", "Data-led and concise",
  "Community-centred and story-led"
- key_messages: 3 lines separated by \n; language_preferences (1 sentence)

## documents (exactly 6, markdown, 100-200 words each, start with "# Title")

Use these titles/types (replace the year where natural):
1. "Mission and Theory of Change" — doc_type "Mission & theory of change"
2. "Programme Descriptions" — "Programme description"
3. "2025-26 Impact Report" — "Impact report" (concrete numbers: participants, outcomes, a quote)
4. "FY2026 Budget Summary" — "Budget" (expense lines and revenue mix that sum correctly)
5. "Governance and Capacity" — "Governance" (board size, staff, audit, policies, key leaders = the team)
6. "Organisation Overview" — "Approved organisational language", approved: true (a polished 100-word paragraph)

Each item: {"title": "...", "doc_type": "...", "approved": false|true, "content": "# ...\n\n..."}

## opportunities (exactly 6, fictional funders that fit THIS organisation's field and state)

Each item:
```json
{
  "funder": "Fictional Foundation name", "program_name": "Programme name",
  "deadline_days": 9,              // days from today (negative = past)
  "geography": "...", "focus_area": "...",
  "award_min": 25000 or null, "award_max": 75000, "award_text": "$25,000 to $75,000 for one year",
  "eligibility": ["...", "..."], "restrictions": ["..."], "requirements": ["...", "..."],
  "matched_funding": "Not required" | "25% match required" | ..., "reporting": "...",
  "summary": "One sentence.",
  "raw_text": "Funder — Programme (FICTIONAL SAMPLE)\n...the funder's call text, 80-180 words, with eligibility, award, deadline wording, priorities, restrictions...",
  "status": "...", "owner_index": 0|1|2|null, "decision": "Go"|"Research further"|"No-Go"|null,
  "tasks_done": 0-6,
  "questions": [ {"prompt": "...", "limit_type": "words"|"characters", "limit_value": 250, "answer": "...", "status": "Not started"|"Drafting"|"Reviewed"|"Approved"} ]
}
```

Cover these six stages, one each, in this order:
1. status "Drafting", decision "Go", deadline_days 5-8, tasks_done 1 — a strong-fit funder. 4 questions:
   Q1 has a WEAK first-draft answer (60-90 words: vague, an unsupported superlative like "the leading
   provider", a wrong or rounded number that contradicts the documents, filler) so the Coach and Evidence
   Checker have something to catch; Q2-Q4 answer "" status "Not started". Q1 status "Drafting".
2. status "Internal Review", decision "Go", deadline_days 10-14, tasks_done 3 — 2 questions, both
   answered well (80-150 words, every fact from the documents), statuses "Reviewed" and "Drafting".
3. status "Ready to Submit", decision "Go", deadline_days 2-4, tasks_done 5 — 2 questions, both answered
   well, both "Approved".
4. status "Go / No-Go", decision null, deadline_days 20-30, tasks_done 0, questions [] — a plausible but
   uncertain fit (e.g. requires a match, or a slightly different population). raw_text 120-180 words so the
   Fit Agent has real material.
5. status "Researching", decision null, deadline_days 12-18, tasks_done 0, questions [] — a POOR fit
   (wrong state or wrong population or requires something they lack), clearly stated in raw_text.
6. status "Submitted", decision "Go", deadline_days -15 to -25, tasks_done 6, questions [].

owner_index points into team (null allowed only for stage 5). Prompts must be realistic funder questions.

## library_answers (exactly 1)

{"question": "a common funder question (e.g. 'Why is your organisation well positioned to do this work?')",
 "answer": "120-180 words, every fact from the documents", "funder": "one of the stage-2/3 funders"}
Use a question topic that matches one of the stage-1 Q2-Q4 prompts, so the editor's Library tab can
suggest it.

## Quality bar

- Realistic, specific, professional. No real organisations or real people. Plain English.
- JSON must parse (no comments, no trailing commas). Validate with: python3 -c "import json;json.load(open('PATH'))"

## outcomes (at least 3, with at least one won and one lost; vary the mix so demos have different win rates) — grant history for reporting

Add a top-level key `"outcomes"` (a list) to the JSON. These are grants the organisation already applied
for. Funders are fictional, fit this organisation's field and state, and must NOT reuse any funder name
already in `opportunities`. Every fact must match the existing profile and documents.

Won grant (two of these):
```json
{
  "result": "Won",
  "funder": "...", "program_name": "...", "geography": "...", "focus_area": "...",
  "summary": "One sentence on what the grant funds.",
  "raw_text": "Funder — Programme (FICTIONAL SAMPLE)\n40-90 words: what the funder supports.",
  "amount_awarded": 60000,
  "decided_days_ago": 75,               // first won: 30-90; second won: 100-170 (both within 6 months)
  "grant_period": "July 1, 2026 – June 30, 2027",
  "report_due_days": 18,                // days from today the next report is due: first won 10-25, second won 45-90
  "owner_index": 0,
  "reporting_requirements": "The funder's reporting guidelines as they would send them, 120-200 words: report type (interim/final), due date wording, required narrative sections with word limits, required metrics, financial report, format and how to submit. Start with 'Funder — Interim Report Requirements (FICTIONAL SAMPLE)'.",
  "report_sections": [ {"prompt": "...", "limit_type": "words", "limit_value": 300} ],   // 4 sections that match the requirements word for word
  "program_report": {"title": "Programme Progress Report: <period>", "content": "# ...\n\nMarkdown, 150-250 words: what was delivered so far under THIS grant, with concrete numbers (people served, sessions, outcomes to date, a short participant quote, spending to date), consistent with the profile and documents."}
}
```

Lost grant (one):
```json
{
  "result": "Lost",
  "funder": "...", "program_name": "...", "geography": "...", "focus_area": "...",
  "summary": "...", "raw_text": "Funder — Programme (FICTIONAL SAMPLE)\n40-90 words.",
  "amount_requested": 50000, "decided_days_ago": 40, "owner_index": 1,
  "lost_reason": "One or two sentences of plausible funder feedback (e.g. 'Strong programme, but this cycle prioritised rural counties.')."
}
```

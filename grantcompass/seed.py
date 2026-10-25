"""Fictional sample data so a fresh clone opens on a populated workspace.

Deadlines are set relative to the day the database is created, so the
pipeline always looks current. Every funder and figure here is invented."""

from datetime import date, timedelta

from . import db
from .config import SAMPLE_DIR
from .pipeline import workback_plan

SAMPLE_TEAM = [("Maya Chen", "Development Director"), ("Sam Ortiz", "Grants Manager"),
               ("Priya Nair", "Programme Director")]
TEAM = [db.member_label(n, r) for n, r in SAMPLE_TEAM]

LIBRARY = [
    ("mission.md", "Mission and Theory of Change", "Mission & theory of change", False),
    ("programmes.md", "Programme Descriptions", "Programme description", False),
    ("impact_report.md", "2025-26 Impact Report", "Impact report", False),
    ("budget.md", "FY2026 Budget Summary", "Budget", False),
    ("governance.md", "Governance and Capacity", "Governance", False),
    ("approved_overview.md", "Organisation Overview", "Approved organisational language", True),
]


def _text(*lines: str) -> str:
    return "\n".join(lines)


def _opportunities(today: date) -> list[dict]:
    d = lambda n: (today + timedelta(days=n)).isoformat()  # noqa: E731
    return [
        {
            "funder": "Miami Valley Early Learning Fund",
            "program_name": "2027 Community Grants",
            "deadline": d(6),
            "geography": "Montgomery, Greene and Miami counties, Ohio",
            "focus_area": "Early literacy (K-3)",
            "award_min": 50_000, "award_max": 100_000,
            "award_text": "$50,000 to $100,000 per year for up to two years",
            "eligibility": [
                "501(c)(3) public charity",
                "Serves residents of Montgomery, Greene or Miami County",
                "Operating budget between $250,000 and $5 million",
                "Independent audit or financial review within the last two years",
            ],
            "restrictions": ["Data must be shared with the Fund"],
            "requirements": [
                "Narrative (max 8 pages)", "Program budget and justification", "Most recent audit",
                "Board list with affiliations", "Two letters of support",
            ],
            "matched_funding": "Not required",
            "reporting": "Annual outcome report",
            "summary": "Early literacy grants for K-3 programmes in the Miami Valley.",
            "source_url": None,
            "raw_text": (SAMPLE_DIR / "opportunity_good_fit.md").read_text(),
            "_status": "Drafting", "_owner": TEAM[1], "_decision": "Go", "_done": 1,
        },
        {
            "funder": "Gem City Community Fund",
            "program_name": "Neighbourhood Learning Grants",
            "deadline": d(11),
            "geography": "City of Dayton, Ohio",
            "focus_area": "Out-of-school learning and family engagement",
            "award_min": 25_000, "award_max": 40_000,
            "award_text": "Up to $40,000 for one year",
            "eligibility": ["Nonprofit serving Dayton residents"],
            "restrictions": ["No capital expenses"],
            "requirements": ["Online application (5 questions)", "Budget", "Board list"],
            "matched_funding": "Not required",
            "reporting": "Six-month and final report",
            "summary": "One-year grants for neighbourhood learning and family engagement in Dayton.",
            "source_url": None,
            "raw_text": _text(
                "Gem City Community Fund — Neighbourhood Learning Grants (FICTIONAL SAMPLE)",
                "Grants of up to $40,000 for one year to nonprofits serving Dayton residents.",
                "Priority: family engagement and out-of-school learning. No capital expenses.",
            ),
            "_status": "Internal Review", "_owner": TEAM[0], "_decision": "Go", "_done": 3,
        },
        {
            "funder": "Buckeye Family Literacy Trust",
            "program_name": "Family Literacy Partnerships",
            "deadline": d(26),
            "geography": "Ohio",
            "focus_area": "Family literacy",
            "award_min": 75_000, "award_max": 150_000,
            "award_text": "$75,000 to $150,000 over two years",
            "eligibility": ["Ohio 501(c)(3)", "Programme must include a parent component"],
            "restrictions": ["Indirect costs capped at 10%"],
            "requirements": ["Letter of inquiry", "Logic model", "Two-year budget"],
            "matched_funding": "25% match required",
            "reporting": "Quarterly data reports",
            "summary": "Two-year grants for programmes that build literacy across whole families.",
            "source_url": None,
            "raw_text": _text(
                "Buckeye Family Literacy Trust — Family Literacy Partnerships (FICTIONAL SAMPLE)",
                "Two-year grants of $75,000 to $150,000 for Ohio 501(c)(3) organisations whose programmes",
                "build literacy across whole families and include a parent component.",
                "A 25% match is required. Indirect costs are capped at 10%. Quarterly data reports required.",
                "Submit a letter of inquiry, logic model and two-year budget.",
            ),
            "_status": "Go / No-Go", "_owner": TEAM[0], "_decision": None, "_done": 0,
        },
        {
            "funder": "Great Lakes STEM Futures Initiative",
            "program_name": "High School STEM Pathways",
            "deadline": d(13),
            "geography": "Michigan and Wisconsin",
            "focus_area": "High school STEM",
            "award_min": None, "award_max": 250_000,
            "award_text": "Up to $250,000 over three years",
            "eligibility": ["501(c)(3) located in Michigan or Wisconsin", "Serves high school students"],
            "restrictions": [],
            "requirements": [],
            "matched_funding": "1:1 cash match",
            "reporting": "Not stated",
            "summary": "High school STEM career programmes in Michigan and Wisconsin.",
            "source_url": None,
            "raw_text": (SAMPLE_DIR / "opportunity_poor_fit.md").read_text(),
            "_status": "Researching", "_owner": None, "_decision": None, "_done": 0,
        },
        {
            "funder": "Riverside Children's Fund",
            "program_name": "Summer Reading Grants",
            "deadline": d(3),
            "geography": "Montgomery County, Ohio",
            "focus_area": "Summer learning",
            "award_min": None, "award_max": 20_000,
            "award_text": "Up to $20,000",
            "eligibility": ["Montgomery County nonprofit"],
            "restrictions": ["Books and materials only"],
            "requirements": ["Short application", "Budget"],
            "matched_funding": "Not required",
            "reporting": "Final report",
            "summary": "Small grants for summer reading materials.",
            "source_url": None,
            "raw_text": _text(
                "Riverside Children's Fund — Summer Reading Grants (FICTIONAL SAMPLE)",
                "Up to $20,000 for books and materials for summer reading in Montgomery County.",
            ),
            "_status": "Ready to Submit", "_owner": TEAM[1], "_decision": "Go", "_done": 5,
        },
        {
            "funder": "Harbor Bank Foundation",
            "program_name": "Community Education Grants",
            "deadline": d(-20),
            "geography": "Southwest Ohio",
            "focus_area": "Education",
            "award_min": None, "award_max": 35_000,
            "award_text": "Up to $35,000",
            "eligibility": ["Nonprofit in the bank's service area"],
            "restrictions": [], "requirements": [],
            "matched_funding": "Not required", "reporting": "Final report",
            "summary": "Education grants in the bank's service area.",
            "source_url": None,
            "raw_text": "Harbor Bank Foundation — Community Education Grants (FICTIONAL SAMPLE)",
            "_status": "Submitted", "_owner": TEAM[0], "_decision": "Go", "_done": 6,
        },
    ]


def seed() -> None:
    lib = SAMPLE_DIR / "library"
    for filename, title, doc_type, approved in LIBRARY:
        db.add_document(title, doc_type, (lib / filename).read_text(), approved=approved, sample=True)

    today = date.today()
    for opp in _opportunities(today):
        meta = {k: opp.pop(k) for k in list(opp) if k.startswith("_")}
        opp["deadline_text"] = date.fromisoformat(opp["deadline"]).strftime("%B %-d, %Y")
        opp_id = db.add_opportunity({**opp, "origin": "Sample data"}, status=meta["_status"], owner=meta["_owner"],
                                    sample=True)
        if meta["_decision"]:
            db.update_opportunity(opp_id, decision=meta["_decision"], decision_reason="Sample data")
            # Sample plans start 14 days before the deadline, as if made on time.
            deadline = date.fromisoformat(opp["deadline"])
            plan = workback_plan(deadline, today=deadline - timedelta(days=14))
            db.add_tasks(opp_id, [(t, due, i < meta["_done"]) for i, (t, due) in enumerate(plan)])


SAMPLE_PROFILE = {
    "legal_name": "Riverbend Reads, Inc.",
    "legal_status": "501(c)(3) public charity",
    "year_founded": 2014,
    "headquarters": "Dayton",
    "state": "Ohio",
    "website": "",
    "mission": "Riverbend Reads helps children in grades K-3 from low-income families read at grade level "
               "by the end of third grade.",
    "theory_of_change": "If children who are behind in reading receive consistent one-on-one tutoring from a "
                        "trained adult, and their families have simple routines for reading at home, then they "
                        "will reach grade-level reading by the end of third grade.",
    "programmes": "One-on-One Tutoring — trained volunteer tutors, twice a week for 30 minutes, at 9 partner "
                  "elementary schools in Dayton Public Schools\n"
                  "Family Reading Nights — monthly evening events teaching at-home reading routines\n"
                  "Summer Book Bags — 10 free books per enrolled student each summer",
    "focus_areas": ["Literacy", "K-12 education", "Early childhood"],
    "populations": ["Children (5-12)", "Families / caregivers", "Low-income households", "English learners"],
    "population_details": "88% qualify for free or reduced-price lunch; 71% Black, 14% Hispanic/Latino, "
                          "11% white, 4% multiracial; 19% English learners.",
    "geography": "Montgomery County, Ohio (Dayton Public Schools)",
    "people_served": 612,
    "annual_budget": 1_200_000,
    "fiscal_year_end": "June 30",
    "revenue_mix": "Foundations 46%, individual donors 27%, corporate gifts 12%, government 10%, events 5%",
    "audit": "Independent audit, clean opinion",
    "staff": "11 full-time, 6 part-time",
    "volunteers": "About 140 active volunteer tutors",
    "grant_capacity": "One full-time grants manager; the development director spends about 30% of time on grants.",
    "federal_experience": "Only as a subrecipient",
    "outcomes": "2025-26: 68% of tutored students who started below benchmark on DIBELS 8 reached benchmark by "
                "spring, vs 41% of similar non-tutored students\n"
                "2025-26: average gain of 1.4 grade levels in oral reading fluency\n"
                "2025-26: 93% of parents surveyed said their child reads more at home",
    "evaluation": "DIBELS 8 assessments in fall, winter and spring, tracked in a shared database; annual parent survey.",
    "current_funders": "Ohio Department of Education — subgrant — 2024 to present",
    "funder_contacts": "",
    "grant_types": ["General operating", "Programme / project", "Capacity building"],
    "min_award": 15_000,
    "max_match": "Up to 10% of the award, in cash",
    "lead_time_days": 21,
    "avoid": "Funding restricted to high school or adult programmes; capital campaigns.",
    "voice": "Warm and plain-spoken",
    "key_messages": "Reading by third grade changes a child's path\n"
                    "Tutoring works: our students outpace similar peers\n"
                    "Families are partners, not bystanders",
    "language_preferences": "Say 'students' and 'families'; avoid 'at-risk' and 'disadvantaged'.",
}


def seed_profile() -> None:
    db.save_profile(SAMPLE_PROFILE)


SAMPLE_QUESTIONS = [
    ("Describe the need your program addresses and the population you serve. Why does this need matter "
     "in your community, and what evidence shows it?", "words", 300,
     "Riverbend Reads is the leading literacy provider in Ohio. We serve over 700 students in Dayton who "
     "struggle with reading. Many of our students come from low-income families and need help with reading.\n\n"
     "Reading is very important for children. Children who cannot read well struggle in school. Our program "
     "transforms lives by helping children who struggle with reading become better readers.\n\n"
     "We hope to help even more children read better in the future and make a big difference in the community."),
    ("Describe your program design: the activities, who delivers them, how often, and where.", "words", 400, ""),
    ("What outcomes do you expect from this grant, and how will you measure them?", "words", 250, ""),
    ("Why is your organization well positioned to do this work?", "characters", 1500, ""),
]


RIVERSIDE_CAPACITY = (
    "Riverbend Reads has focused on one goal since 2014: helping children in grades K-3 from low-income families "
    "read at grade level by the end of third grade. About 140 trained volunteer tutors work one-on-one with students "
    "twice a week at nine partner elementary schools in Dayton Public Schools. We measure results with DIBELS 8 three "
    "times a year: in 2025-26, 68% of tutored students who started below benchmark reached it by spring, compared "
    "with 41% of similar students who were not tutored. An independent audit with a clean opinion and a full-time "
    "grants manager mean funders can rely on how we manage their money.")

# Later-stage sample applications, so every stage in the pipeline looks like real work.
# (funder, [(question, unit, limit, answer, status)]). Every fact comes from the sample profile.
MORE_SAMPLE_QUESTIONS = [
    ("Riverside Children's Fund", [
        ("Describe your summer reading activities and who they reach.", "words", 200,
         "Each summer, every student enrolled in Riverbend Reads takes home a Summer Book Bag of 10 free books, so "
         "reading continues while tutoring pauses. In 2025-26 we served 612 students in grades K-3 at nine partner "
         "elementary schools in Dayton Public Schools; 88% qualify for free or reduced-price lunch and 19% are "
         "English learners. During the school year, monthly Family Reading Nights teach the simple at-home "
         "routines families use over the summer, and 93% of parents surveyed said their child reads more at home.",
         "Approved"),
        ("Why is your organization well positioned to do this work?", "characters", 1000, RIVERSIDE_CAPACITY,
         "Approved"),
    ]),
    ("Gem City Community Fund", [
        ("Describe the learning need in the neighbourhoods you serve.", "words", 250,
         "Riverbend Reads works in Dayton Public Schools, where most of the children we serve are behind in "
         "reading when they start with us. Of our 612 students in 2025-26, 88% qualify for free or reduced-price "
         "lunch and 19% are English learners. Children who are not reading at grade level by the end of third grade "
         "find it much harder to keep up in later grades, so we focus on kindergarten through third grade, when "
         "one-on-one help makes the biggest difference.",
         "Reviewed"),
        ("How will you measure success?", "words", 150,
         "We assess every student with DIBELS 8 in fall, winter and spring and track the results in a shared "
         "database. Our main measure is the share of students who start below benchmark and reach it by spring "
         "(68% in 2025-26, compared with 41% of similar students who were not tutored). We also run an annual "
         "parent survey on reading at home.",
         "Drafting"),
    ]),
]


def seed_questions() -> None:
    """Add sample applications to the sample opportunities that exist, and one approved answer to the
    Answer Library so reuse can be tried straight away."""
    opps = {o["funder"]: o for o in db.list_opportunities() if o["sample"]}
    opp = opps.get("Miami Valley Early Learning Fund")
    if opp:
        for prompt, unit, limit, answer in SAMPLE_QUESTIONS:
            db.add_question(opp["id"], prompt, unit, limit, answer)
    for funder, questions in MORE_SAMPLE_QUESTIONS:
        if funder not in opps:
            continue
        for prompt, unit, limit, answer, status in questions:
            q_id = db.add_question(opps[funder]["id"], prompt, unit, limit, answer)
            db.set_question_status(q_id, status)
            if answer is RIVERSIDE_CAPACITY and not db.list_answers():
                from .answers import classify
                db.save_answer(prompt, answer, classify(prompt), funder, q_id)


def seed_team() -> None:
    for name, role in SAMPLE_TEAM:
        db.add_member(name, role)

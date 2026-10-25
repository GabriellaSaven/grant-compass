"""First-pass triage: rank search results against the profile with plain
rules, no AI. It is free and instant, so it can screen every result; only the
opportunities the team saves go on to the (paid) Fit Agent.

Every point comes with a reason the user can read, and anything filtered out
says why."""

import re
from datetime import date

# Words that signal each focus area / population in a funder's text.
FOCUS_TERMS = {
    "Early childhood": ["early childhood", "early learning", "preschool", "pre-k", "kindergarten", "infant", "toddler"],
    "K-12 education": ["k-12", "elementary", "middle school", "high school", "students", "school district"],
    "Literacy": ["literacy", "reading", "readers", "books", "library", "libraries"],
    "Youth development": ["youth", "mentoring", "after school", "afterschool", "out-of-school", "adolescent"],
    "Higher education & workforce": ["workforce", "job training", "apprentice", "college", "postsecondary", "career"],
    "Health": ["health", "clinic", "medical", "disease", "wellness"],
    "Mental health": ["mental health", "behavioral health", "suicide", "counseling", "trauma"],
    "Food security": ["food", "nutrition", "hunger", "meals"],
    "Housing & homelessness": ["housing", "homeless", "shelter", "eviction"],
    "Arts & culture": ["arts", "culture", "museum", "humanities", "music", "theater"],
    "Environment": ["environment", "climate", "conservation", "watershed", "energy"],
    "Economic mobility": ["economic mobility", "poverty", "financial", "income", "asset building"],
    "Civic engagement": ["civic", "voter", "democracy", "community engagement"],
    "Immigrant & refugee services": ["immigrant", "refugee", "newcomer", "asylum"],
    "Disability services": ["disability", "disabilities", "accessib"],
    "Racial equity": ["racial equity", "equity", "underserved", "minority"],
    "Women & girls": ["women", "girls", "gender"],
    "Older adults": ["older adults", "seniors", "aging", "elderly"],
}
POPULATION_TERMS = {
    "Children (0-5)": ["infant", "toddler", "early childhood", "preschool"],
    "Children (5-12)": ["children", "elementary", "child"],
    "Youth (13-18)": ["youth", "adolescent", "teen", "high school"],
    "Young adults (18-24)": ["young adult", "opportunity youth"],
    "Families / caregivers": ["families", "family", "parent", "caregiver"],
    "Low-income households": ["low-income", "low income", "poverty", "economically disadvantaged", "title i"],
    "Communities of colour": ["communities of color", "minority", "underserved"],
    "English learners": ["english learner", "english language", "multilingual"],
    "Immigrants & refugees": ["immigrant", "refugee"],
    "People with disabilities": ["disabilit"],
    "Rural communities": ["rural"],
    "Veterans": ["veteran"],
}
# Grants.gov / state funding categories that fit each focus area.
FOCUS_CATEGORIES = {
    "Early childhood": "education", "K-12 education": "education", "Literacy": "education|humanities|librar",
    "Youth development": "education|community|youth|social services",
    "Higher education & workforce": "education|employment|labor|workforce",
    "Health": "health", "Mental health": "health", "Food security": "food|nutrition|agricultur",
    "Housing & homelessness": "housing|community development", "Arts & culture": "arts|humanities",
    "Environment": "environment|natural resources|energy|conservation",
    "Economic mobility": "income security|community development|employment",
    "Civic engagement": "community", "Immigrant & refugee services": "community|social services",
    "Disability services": "health|social services|disabilit", "Racial equity": "community",
    "Women & girls": "social services|community", "Older adults": "health|social services|income",
}
# NIH-style research mechanisms (R01, K99, U01…) and clinical-trial announcements.
RESEARCH = re.compile(r"\((?:R|K|U|P|F|T)\d{2}\b|clinical trial|clinical research|translational research|"
                      r"research project grant|early investigator|research network|diagnostic", re.I)
# Wording that means the opportunity isn't open to applications right now.
NOT_OPEN = re.compile(r"currently closed|applications? (?:are |is )?closed|not (?:currently )?accepting|"
                      r"(?:do|does) not accept unsolicited|by invitation only|invitation[- ]only|"
                      r"no (?:current|open) (?:calls|opportunities|funding opportunities)", re.I)
INTERNATIONAL = re.compile(r"\bembassy\b|public diplomacy|u\.s\. mission to|consulate", re.I)

# Populations specific enough to search for directly.
DISTINCT_POPULATION = {"Veterans": "veteran", "Rural communities": "rural", "Immigrants & refugees": "refugee",
                       "LGBTQ+ people": "LGBTQ"}

# The single best search keyword for each focus area.
SEARCH_KEYWORD = {k: v[0] for k, v in FOCUS_TERMS.items()}


def search_keywords(profile: dict, query: str | None) -> list[str]:
    if query and query.strip():
        return [q.strip() for q in query.split(",") if q.strip()][:4]
    areas = [a for a in profile.get("focus_areas") or [] if a in SEARCH_KEYWORD]
    # A distinctive population (veterans, rural…) says more about who funds you than a third focus area.
    people = [DISTINCT_POPULATION[p] for p in profile.get("populations") or [] if p in DISTINCT_POPULATION][:1]
    focus = [SEARCH_KEYWORD[a] for a in areas]
    return (focus[:2] + people + focus[2:])[:3] or ["nonprofit"]


def _hits(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if re.search(r"\b" + re.escape(t), text)]


def _count(text: str, terms: list[str]) -> int:
    return sum(len(re.findall(r"\b" + re.escape(t), text)) for t in terms)


def _list_states(states: list[str]) -> str:
    return states[0] if len(states) == 1 else ", ".join(states[:-1]) + " and " + states[-1]


def triage(lead: dict, profile: dict, today: date | None = None, keywords: list[str] | None = None) -> dict:
    """Return {score, band, reasons, warnings, excluded}. Reasons are short and plain."""
    today = today or date.today()
    head = f"{lead['title']} {lead.get('summary', '')}".lower()  # title + first lines of the description
    body = (lead.get("raw_text") or "").lower()
    categories = (lead.get("categories") or "").lower()
    reasons, warnings = [], []

    # Hard filters
    if lead.get("states") and profile.get("state") and profile["state"] not in lead["states"]:
        # utilities and community foundations give only where they operate (from the directory, not the AI)
        return {"excluded": f"Only funds in {_list_states(lead['states'])}"}
    if lead.get("nonprofit_eligible") is False:
        return {"excluded": "Nonprofits are not eligible"}
    if INTERNATIONAL.search(f"{lead['title']} {lead.get('funder', '')}") or \
            lead.get("agency_code", "").upper().startswith(("DOS-", "USAID")):
        return {"excluded": "International programme"}
    status_text = f"{lead.get('deadline_text', '')} {lead.get('title', '')} {lead.get('summary', '')}"
    if lead.get("source") in ("Watchlist", "Foundation directory", "Link") and NOT_OPEN.search(status_text):
        return {"excluded": "Not open to applications right now (closed or invitation only)"}
    if RESEARCH.search(lead["title"]) and "Research" not in (profile.get("grant_types") or []):
        return {"excluded": "Research grant (Research is not among your Profile's grant types)"}
    days = (date.fromisoformat(lead["deadline"]) - today).days if lead.get("deadline") else None
    if days is not None and days < 0:
        return {"excluded": "Deadline has passed"}
    min_award = profile.get("min_award")
    if min_award and lead.get("award_max") and lead["award_max"] < min_award:
        return {"excluded": f"Largest award (${lead['award_max']:,}) is below your minimum (${int(min_award):,})"}

    # Relevance (0-50): the title and summary count most; a passing mention in the body counts little.
    areas = [a for a in profile.get("focus_areas") or [] if a in FOCUS_TERMS]
    # Typed keywords count as extra focus terms (and are all we have if the Profile has no focus areas).
    groups = {a: FOCUS_TERMS[a] for a in areas}
    for kw in keywords or []:
        if kw.lower() not in (t for terms in groups.values() for t in terms):
            groups[f"“{kw}”"] = [kw.lower()]
    if not groups:
        relevance = 20
        warnings.append("Add focus areas to your Profile to rank by relevance")
    else:
        if not areas:
            warnings.append("Ranked on your keywords only: add focus areas to your Profile")
        relevance, matched, head_match = 0, [], False
        for a, terms in groups.items():
            in_head = _hits(head, terms)
            if in_head:
                relevance += 20
                head_match = True
                matched.append(a.lower() if a.startswith("“") else f"{a.lower()} (“{in_head[0]}”)")
            elif _count(body, terms) >= 3:
                relevance += 6
                matched.append(f"{a.lower()} (in the details)")
        if areas and categories and not any(re.search(FOCUS_CATEGORIES.get(a, "$^"), categories) for a in areas):
            relevance -= 15
            warnings.append(f"Funding category is {lead['categories']}")
        pops = [p for p in profile.get("populations") or [] if p in POPULATION_TERMS
                and _count(f"{head} {body}", POPULATION_TERMS[p]) >= 2]
        if pops and head_match:  # populations only add weight to an otherwise real match
            relevance += 10
        relevance = min(relevance, 50)
        if relevance < 12:
            if lead.get("source") != "Watchlist":
                return {"excluded": "Only a passing link to your focus areas"}
            relevance = max(relevance, 5)  # a funder the team chose to follow is never hidden
            warnings.append("No specific match to your focus areas: check whether general grants fit")
        if matched:
            reasons.append("Matches " + ", ".join(matched))
        if pops and head_match:
            reasons.append("Mentions your populations: " + ", ".join(p.lower() for p in pops))

    # Deadline (0-20)
    lead_time = int(profile.get("lead_time_days") or 21)
    if days is None:
        deadline_pts = 8
        warnings.append("No deadline set yet" if lead.get("status") == "forecasted" else "Deadline not stated")
    elif days >= 2 * lead_time:
        deadline_pts = 20
        reasons.append(f"{days} days to the deadline (you need about {lead_time})")
    elif days >= lead_time:
        deadline_pts = 12
        reasons.append(f"{days} days to the deadline: enough, but plan now")
    else:
        deadline_pts = 0
        warnings.append(f"Only {days} days left; you usually need {lead_time}")

    # Award size (0-20)
    budget = profile.get("annual_budget")
    if not lead.get("award_max") and not lead.get("award_min"):
        award_pts = 10
        warnings.append("Award amount not stated")
    elif budget and lead.get("award_min") and lead["award_min"] > 0.5 * budget:
        award_pts = 5
        warnings.append(f"Smallest award is {100 * lead['award_min'] // budget}% of your budget: may be too big a lift")
    else:
        award_pts = 20
        reasons.append(f"Award size fits ({lead['award_text']})")

    # Eligibility (0-10)
    if lead.get("nonprofit_eligible"):
        elig_pts = 10
        reasons.append("Open to nonprofits")
    else:
        elig_pts = 4
        warnings.append("Eligibility unclear: check the full announcement")
    if lead.get("match_required") not in (None, "", "Not required", "Not stated", "No", "0%", "None"):
        warnings.append(f"Match: {lead['match_required']}")

    score = relevance + deadline_pts + award_pts + elig_pts
    band = "Strong" if score >= 75 else "Possible" if score >= 50 else "Weak"
    return {"score": score, "band": band, "reasons": reasons, "warnings": warnings, "excluded": None}


def origin_label(source: str | None) -> str:
    """Where an opportunity came from, in words a fundraiser recognises."""
    source = source or ""
    if source.startswith("Uploaded:"):
        name = source.lower()
        kind = "PDF" if name.endswith(".pdf") else "Word document" if name.endswith(".docx") else "document"
        return f"Uploaded {kind}"
    return {
        "Grants.gov": "Found via Grants.gov",
        "California Grants Portal": "Found via California Grants Portal",
        "Foundation directory": "Found via foundation directory",
        "Watchlist": "Found via a funder you follow",
        "Link": "Added from URL",
        "Pasted text": "Pasted text",
    }.get(source, "Added manually")


def lead_to_opportunity(lead: dict) -> dict:
    """Turn a search result into a pipeline opportunity (no AI needed for structured sources)."""
    if lead.get("opportunity"):  # watchlist results were already extracted by the Research Agent
        return {**lead["opportunity"], "origin": origin_label(lead.get("source"))}
    return {
        "funder": lead["funder"],
        "program_name": lead["title"],
        "deadline": lead.get("deadline"),
        "deadline_text": lead.get("deadline_text"),
        "geography": lead.get("geography"),
        "focus_area": lead.get("categories"),
        "award_min": lead.get("award_min"),
        "award_max": lead.get("award_max"),
        "award_text": lead.get("award_text"),
        "eligibility": [e for e in lead.get("eligibility") or [] if e],
        "restrictions": [],
        "requirements": ["See the full announcement at the source link"],
        "matched_funding": lead.get("match_required"),
        "reporting": "Not stated",
        "summary": lead.get("summary"),
        "source_url": lead.get("url"),
        "raw_text": lead.get("raw_text"),
        "origin": origin_label(lead.get("source")),
    }

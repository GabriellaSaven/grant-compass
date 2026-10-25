"""The nonprofit profile: a structured form the team fills in once.

The form definition lives here so the page, the completeness meter and the
text the agents read are all generated from one list. The saved profile is
rendered as the first document in the Organisation Library, so the Fit Agent
uses it to judge matches and the writing agents will use it as source material."""

FOCUS_AREAS = [
    "Early childhood", "K-12 education", "Literacy", "Youth development", "Higher education & workforce",
    "Health", "Mental health", "Food security", "Housing & homelessness", "Arts & culture", "Environment",
    "Economic mobility", "Civic engagement", "Immigrant & refugee services", "Disability services",
    "Racial equity", "Women & girls", "Older adults", "Other",
]
POPULATIONS = [
    "Children (0-5)", "Children (5-12)", "Youth (13-18)", "Young adults (18-24)", "Adults", "Older adults",
    "Families / caregivers", "Low-income households", "Communities of colour", "English learners",
    "Immigrants & refugees", "People with disabilities", "LGBTQ+ people", "Veterans", "Rural communities",
]
US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas",
    "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Puerto Rico",
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
    "Washington", "West Virginia", "Wisconsin", "Wyoming",
]
GRANT_TYPES = ["General operating", "Programme / project", "Capacity building", "Capital", "Research", "Event"]

# (section, [(key, label, kind, options_or_None, help)])
# kinds: text, textarea, number, select, multi
SECTIONS = [
    ("Basics", [
        ("legal_name", "Legal name", "text", None, ""),
        ("legal_status", "Legal status", "select",
         ["501(c)(3) public charity", "501(c)(3) private foundation", "Fiscally sponsored project",
          "Government entity", "School / university", "Other"], ""),
        ("year_founded", "Year founded", "number", None, ""),
        ("headquarters", "Headquarters (city)", "text", None, ""),
        ("state", "State", "select", US_STATES, "Used to include your state's open grant portal, where one exists."),
        ("website", "Website", "text", None, ""),
    ]),
    ("Mission & programmes", [
        ("mission", "Mission statement", "textarea", None, "One or two sentences, as you would write it in an application."),
        ("theory_of_change", "Theory of change", "textarea", None, "If we do X for Y, then Z will change, because…"),
        ("programmes", "Programmes", "textarea", None, "One per line: name — what it is, how often, where."),
        ("focus_areas", "Focus areas", "multi", FOCUS_AREAS, ""),
    ]),
    ("Who and where", [
        ("populations", "Populations served", "multi", POPULATIONS, ""),
        ("population_details", "Population details", "textarea", None,
         "Demographics you can evidence, e.g. % low-income, % English learners."),
        ("geography", "Service area", "text", None, "Counties, cities or neighbourhoods where programmes run."),
        ("people_served", "People served per year", "number", None, ""),
    ]),
    ("Finances", [
        ("annual_budget", "Annual operating budget (USD)", "number", None, ""),
        ("fiscal_year_end", "Fiscal year end", "text", None, "e.g. June 30"),
        ("revenue_mix", "Revenue mix", "textarea", None, "e.g. Foundations 46%, individuals 27%…"),
        ("audit", "Most recent audit", "select",
         ["Independent audit, clean opinion", "Independent audit, with findings", "Financial review",
          "Compilation only", "None yet"], ""),
    ]),
    ("Capacity", [
        ("staff", "Staff", "text", None, "e.g. 11 full-time, 6 part-time"),
        ("volunteers", "Volunteers", "text", None, ""),
        ("grant_capacity", "Grant team capacity", "textarea", None, "Who writes grants and how much time they have."),
        ("federal_experience", "Federal grant experience", "select",
         ["Yes, we manage federal grants directly", "Only as a subrecipient", "No"], ""),
    ]),
    ("Outcomes & evidence", [
        ("outcomes", "Key outcomes", "textarea", None, "One per line, with numbers and the year. Only results you can evidence."),
        ("evaluation", "How you measure results", "textarea", None, "Tools, assessments, data systems, how often."),
    ]),
    ("Funding history", [
        ("current_funders", "Current and past funders", "textarea", None,
         "Optional. One per line: funder — amount — years. Used as evidence when drafting, not in fit scoring."),
    ]),
    ("Grant preferences", [
        ("grant_types", "Grant types you pursue", "multi", GRANT_TYPES, ""),
        ("min_award", "Smallest award worth applying for (USD)", "number", None, ""),
        ("max_match", "Largest cash match you can provide", "text", None, "e.g. 10% of the award, or none"),
        ("lead_time_days", "Days needed to prepare a full application", "number", None, ""),
        ("avoid", "Funders or areas to avoid", "textarea", None, "Mission conflicts, restricted funding you won't take."),
    ]),
    ("Writing voice", [
        ("voice", "Tone", "select", ["Warm and plain-spoken", "Formal and academic", "Data-led and concise",
                                     "Community-centred and story-led"], ""),
        ("key_messages", "Key messages", "textarea", None, "Three or four points every application should land."),
        ("language_preferences", "Language to use or avoid", "textarea", None,
         "e.g. say 'students', not 'kids'; avoid 'at-risk'."),
    ]),
]

FIELDS = {key: (label, kind, opts, help_) for _, fields in SECTIONS for key, label, kind, opts, help_ in fields}
PROFILE_DOC_TITLE = "Organisation Profile"


def _filled(value) -> bool:
    return value not in (None, "", [])


def completeness(data: dict) -> tuple[int, list[str]]:
    """Return (% of fields filled, sections with gaps)."""
    filled = sum(_filled(data.get(k)) for k in FIELDS)
    gaps = [name for name, fields in SECTIONS if not all(_filled(data.get(f[0])) for f in fields)]
    return round(100 * filled / len(FIELDS)), gaps


def _fmt(key: str, value) -> str:
    _, kind, _, _ = FIELDS[key]
    if kind == "multi":
        return ", ".join(value)
    if kind == "number" and key in ("annual_budget", "min_award"):
        return f"${int(value):,}"
    if kind == "number":
        return f"{int(value):,}" if key != "year_founded" else str(int(value))
    return str(value).strip()


def render(data: dict) -> str:
    """The profile as plain text for the agents. Blank fields are listed as not provided,
    so the agents know the information is missing rather than assuming it."""
    lines = [f"# {PROFILE_DOC_TITLE}", "Entered by the organisation's grant team in the profile form.", ""]
    missing = []
    for section, fields in SECTIONS:
        body = []
        for key, label, *_ in fields:
            v = data.get(key)
            if not _filled(v):
                missing.append(label)
                continue
            text = _fmt(key, v)
            body.append(f"{label}:\n{text}" if "\n" in text else f"{label}: {text}")
        if body:
            lines += [f"## {section}", *body, ""]
    if missing:
        lines += ["## Not provided", ", ".join(missing)]
    return "\n".join(lines).strip()

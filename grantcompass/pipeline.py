"""Pipeline logic: statuses, workback plans, progress and risk labels.

All plain date arithmetic, no AI: it is instant, free, and always agrees with
the calendar. Everything is computed from today's date at render time, so the
pipeline updates itself as time passes."""

from datetime import date, timedelta

STATUSES = [
    "Researching",
    "Go / No-Go",
    "Drafting",
    "Internal Review",
    "Ready to Submit",
    "Submitted",
    "Won",
    "Lost",
    "Declined",  # the team decided not to apply
]
CLOSED = {"Submitted", "Won", "Lost", "Declined"}

# Progress when an opportunity has no tasks yet.
STATUS_PROGRESS = {
    "Researching": 5, "Go / No-Go": 10, "Drafting": 30, "Internal Review": 70,
    "Ready to Submit": 90, "Submitted": 100, "Won": 100, "Lost": 100, "Declined": 0,
}

# Days before the deadline, for a standard 14-day workback.
WORKBACK = [
    (14, "Collect missing information"),
    (10, "Complete first draft"),
    (7, "Programme review"),
    (4, "Leadership review"),
    (2, "Final compliance check"),
    (0, "Submit"),
]

HEALTH_ORDER = ["Critical", "At Risk", "Needs Attention", "On Track"]


def workback_plan(deadline: date, today: date | None = None) -> list[tuple[str, date]]:
    """Tasks counted back from the deadline. If there are fewer than 14 days
    left, the plan is compressed proportionally so every step still fits."""
    today = today or date.today()
    days_left = (deadline - today).days
    scale = 1.0 if days_left >= 14 else max(days_left, 0) / 14
    return [(title, deadline - timedelta(days=round(offset * scale))) for offset, title in WORKBACK]


def days_remaining(opp: dict, today: date | None = None) -> int | None:
    if not opp.get("deadline"):
        return None
    return (date.fromisoformat(opp["deadline"]) - (today or date.today())).days


def progress(opp: dict, tasks: list[dict]) -> int:
    if opp["status"] in CLOSED:
        return STATUS_PROGRESS[opp["status"]]
    if tasks:
        return round(100 * sum(t["done"] for t in tasks) / len(tasks))
    return STATUS_PROGRESS.get(opp["status"], 0)


def overdue_tasks(tasks: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    return [t for t in tasks if not t["done"] and date.fromisoformat(t["due"]) < today]


def health(opp: dict, tasks: list[dict], today: date | None = None) -> tuple[str, list[str]]:
    """Return (label, reasons). Label is one of HEALTH_ORDER; reasons explain it."""
    if opp["status"] in CLOSED:
        return "On Track", []
    today = today or date.today()
    days = days_remaining(opp, today)
    pct = progress(opp, tasks)
    late = overdue_tasks(tasks, today)
    reasons = []
    if days is not None and days < 0:
        reasons.append(f"Deadline passed {-days} day{'s' if days != -1 else ''} ago")
    if late:
        reasons.append(f"{len(late)} overdue: " + ", ".join(t["title"].lower() for t in late))
    needs_decision = opp["status"] in ("Researching", "Go / No-Go") and not opp.get("decision")
    if needs_decision:
        reasons.append("Go / No-Go decision needed")

    if days is None:
        label = "Needs Attention" if (late or needs_decision) else "On Track"
    elif days < 0 or (days <= 3 and pct < 80):
        label = "Critical"
    elif (days <= 7 and pct < 60) or len(late) >= 2:
        label = "At Risk"
    elif late or needs_decision or (days <= 14 and pct < 40):
        label = "Needs Attention"
    else:
        label = "On Track"
    if label != "On Track" and days is not None and days >= 0 and not reasons:
        reasons.append(f"{pct}% complete with {days} days left")
    return label, reasons


def pipeline_rows(opps: list[dict], all_tasks: list[dict], today: date | None = None) -> list[dict]:
    """One summary row per opportunity, with every computed field the UI needs."""
    today = today or date.today()
    by_opp: dict[int, list[dict]] = {}
    for t in all_tasks:
        by_opp.setdefault(t["opportunity_id"], []).append(t)
    rows = []
    for o in opps:
        tasks = by_opp.get(o["id"], [])
        label, reasons = health(o, tasks, today)
        rows.append({
            **o,
            "days_remaining": days_remaining(o, today),
            "progress": progress(o, tasks),
            "health": label,
            "health_reasons": reasons,
            "outstanding": [t for t in tasks if not t["done"]],
            "active": o["status"] not in CLOSED,
        })
    return rows


RISK_RULES = {
    "Critical": "Critical: the deadline has passed, or 3 days or fewer remain with under 80% done.",
    "At Risk": "At Risk: 7 days or fewer remain with under 60% done, or 2 or more steps are overdue.",
    "Needs Attention": "Needs Attention: a step is overdue, a Go / No-Go decision is needed, or 14 days or fewer "
                       "remain with under 40% done.",
    "On Track": "On Track: none of the warning rules apply.",
}


def explain_health(opp: dict, tasks: list[dict], answered: int | None = None, questions: int | None = None,
                   today: date | None = None) -> dict:
    """The facts behind a risk label, plus the rule that produced it. Same thresholds as health()."""
    today = today or date.today()
    label, _ = health(opp, tasks, today)
    days = days_remaining(opp, today)
    pct = progress(opp, tasks)
    late = overdue_tasks(tasks, today)
    open_tasks = [t for t in tasks if not t["done"]]
    facts = []
    if opp["status"] in CLOSED:
        return {"label": label, "facts": [f"{opp['status']}: no longer active"], "rule": ""}
    if days is None:
        facts.append("No deadline set")
    elif days < 0:
        facts.append(f"Deadline passed {-days} day{'s' if days != -1 else ''} ago")
    else:
        facts.append(f"{days} day{'s' if days != 1 else ''} remaining")
    facts.append(f"{pct}% complete")
    if questions:
        facts.append(f"{answered} of {questions} application answers drafted")
    if late:
        facts.append("Overdue: " + ", ".join(t["title"].lower() for t in late))
    if open_tasks:
        facts.append(f"{len(open_tasks)} workback step{'s' if len(open_tasks) != 1 else ''} outstanding")
    needs_decision = opp["status"] in ("Researching", "Go / No-Go") and not opp.get("decision")
    if needs_decision:
        facts.append("Go / No-Go decision not made yet")

    # Exactly which condition put it in this band (same tests, same order as health()).
    because = []
    if label == "Critical":
        if days is not None and days < 0:
            because.append("The deadline has passed")
        if days is not None and 0 <= days <= 3 and pct < 80:
            because.append(f"Only {days} day{'s' if days != 1 else ''} left and {pct}% done (under 80%)")
    elif label == "At Risk":
        if days is not None and days <= 7 and pct < 60:
            because.append(f"{days} day{'s' if days != 1 else ''} left and only {pct}% done (under 60%)")
        if len(late) >= 2:
            because.append(f"{len(late)} steps are overdue")
    elif label == "Needs Attention":
        if late:
            because.append(f"{len(late)} step{'s are' if len(late) != 1 else ' is'} overdue")
        if needs_decision:
            because.append("A Go / No-Go decision is needed")
        if days is not None and days <= 14 and pct < 40:
            because.append(f"{days} days left and only {pct}% done (under 40%)")
    return {"label": label, "facts": facts, "because": because, "rule": RISK_RULES[label]}

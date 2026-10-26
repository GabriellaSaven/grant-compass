"""Executive Director agent: reviews the other agents' health and briefs the human.

It sees only the numbers health.compute() produced (never funder text or documents), so a
poisoned page can't reach it. Code then checks its work: every finding must cite a real metric
with the exact value, or it is removed and counted; its overall rating can never be rosier than
the app's own rules."""

import json

from . import db
from .config import PROMPTS_DIR
from .health import AGENTS, RULES, compute
from .llm import log_run, run_agent, usage_dict
from .models import DirectorReport

INSTRUCTIONS = (PROMPTS_DIR / "executive_director.md").read_text(encoding="utf-8")
FLOOR = {"Healthy": "Healthy", "Not used yet": "Healthy", "Watch": "Watch", "Attention": "Act"}
LEVEL = {"Healthy": 0, "Watch": 1, "Act": 2}


def _matches(claimed, actual) -> bool:
    if isinstance(actual, (int, float)) and not isinstance(actual, bool):
        try:
            return abs(float(claimed) - float(actual)) <= max(0.001, abs(float(actual)) * 0.005)
        except (TypeError, ValueError):
            return False
    return str(claimed).strip().lower() == str(actual).strip().lower()


def verify(report: dict, metrics: dict, code_status: str) -> dict:
    """Keep only findings whose metric exists and whose value matches; never rosier than the code."""
    kept, removed = [], []
    for f in report["findings"]:
        if f["metric"] in metrics and metrics[f["metric"]] is not None and _matches(f["value"], metrics[f["metric"]]):
            kept.append(f)
        else:
            removed.append({**f, "actual": metrics.get(f["metric"], "no such metric")})
    floor = FLOOR[code_status]
    raised = LEVEL[report["overall"]] < LEVEL[floor]
    return {**report, "findings": kept, "removed": removed, "claims_removed": len(removed),
            "model_overall": report["overall"], "overall": floor if raised else report["overall"],
            "raised_by_code": raised, "code_status": code_status}


def _input(health: dict) -> str:
    lines = ["Status rules the app applies:", *[f"- {r}" for r in RULES], "", "Agents:"]
    team = {k: a for k, a in health["agents"].items() if k != "executive_director"}  # it doesn't review itself
    for key, a in team.items():
        lines.append(f"- {key} ({AGENTS[key][0]}): status {a['status']}"
                     + (f" because {'; '.join(a['reasons'])}" if a["reasons"] else ""))
    metrics = {k: v for k, v in health["metrics"].items() if v is not None and not k.startswith("executive_director.")}
    shown = {c["metric"]: c["shown"] for a in team.values() for c in a["checks"]}
    lines += ["", "Metrics (id: value):", json.dumps(metrics, indent=0),
              "", "How each check reads in words (id: shown):", json.dumps(shown, indent=0)]
    return "\n".join(lines)


def review() -> dict:
    """Run one review, verify it, save it. Returns {result, usage}."""
    health = compute()
    run = run_agent(DirectorReport, INSTRUCTIONS, _input(health), agent="executive_director")
    usage = usage_dict(run.usage)
    result = verify(run.output.model_dump(), health["metrics"], health["status"])
    log_run("executive_director", usage, {"overall": result["overall"], "claims_removed": result["claims_removed"]})
    db.save_director_report(result, usage)
    return {"result": result, "usage": usage}

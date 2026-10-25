"""Do the Fit Agent's cost cuts hurt quality? Runs the same grants three ways and compares.

  A. As shipped: low reasoning effort, instructions + organisation library first (a stable prefix the
     provider caches across runs).
  B. No cache-friendly order: the library goes after the grant, so every prompt starts differently.
  C. More reasoning: medium effort instead of low.

Run from the Final Project folder with the app's environment (needs the .env key; about $0.04):
    .venv/bin/python report/cost_experiment.py
Usage goes to a temporary log folder, so Agent health isn't affected. Writes report/cost_experiment.json."""

import json
import statistics as st
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from grantcompass import db, fit, llm, orgs  # noqa: E402
from grantcompass.library import library_context  # noqa: E402
from grantcompass.models import FitAssessment  # noqa: E402

ORG, N = "cedar-ridge-veterans", 6
orgs.activate(ORG)
LOGS = Path(tempfile.mkdtemp())
llm.use_logs(LOGS)

opps = [o for o in db.list_opportunities() if o["status"] not in ("Won", "Lost") and len(o.get("raw_text") or "") > 500][:N]
library_text, docs = library_context()
LIB = f"<organisation_library>\n{library_text}\n</organisation_library>"


def run(cond: str, opp: dict) -> dict:
    if cond == "B_no_cache_order":
        instructions, prompt = fit.INSTRUCTIONS, f"{fit._opportunity_prompt(opp)}\n\n{LIB}"
    else:
        instructions, prompt = f"{fit.INSTRUCTIONS}\n\n{LIB}", fit._opportunity_prompt(opp)
    t0 = time.time()
    r = llm.run_agent(FitAssessment, instructions, prompt, agent=f"exp_{cond}")
    secs = time.time() - t0
    usage = llm.usage_dict(r.usage)
    out = fit._guards(fit._complete(r.output), fit._funder_material(opp), docs)
    llm.log_run(f"exp_{cond}", usage, {})
    cost = json.loads((LOGS / "usage.jsonl").read_text().splitlines()[-1])["cost_usd"]
    return {"opp": opp["id"], "funder": opp["funder"], "fit": out["fit_score"], "rec": out["recommendation"],
            "warnings": len(out["quote_warnings"]), "input": usage["input_tokens"],
            "cached": usage.get("cached_input_tokens", 0), "output": usage["output_tokens"], "cost": cost,
            "seconds": round(secs, 1)}


results = {}
for cond, effort in (("A_shipped", "low"), ("B_no_cache_order", "low"), ("C_medium_reasoning", "medium")):
    llm.MODEL_SETTINGS["openai_reasoning_effort"] = effort
    results[cond] = []
    for o in opps:
        try:
            results[cond].append(run(cond, o))
            print(cond, results[cond][-1])
        except Exception as exc:  # keep going; report the failure
            print(cond, o["funder"], "FAILED", type(exc).__name__, exc)
llm.MODEL_SETTINGS["openai_reasoning_effort"] = "low"

base = {r["opp"]: r for r in results["A_shipped"]}
summary = {}
for cond, rs in results.items():
    summary[cond] = {
        "runs": len(rs),
        "mean_input": round(st.mean(r["input"] for r in rs)),
        "mean_cached": round(st.mean(r["cached"] for r in rs)),
        "cached_share": round(sum(r["cached"] for r in rs) / max(1, sum(r["input"] for r in rs)), 3),
        "mean_output": round(st.mean(r["output"] for r in rs)),
        "mean_cost": round(st.mean(r["cost"] for r in rs), 6),
        "mean_seconds": round(st.mean(r["seconds"] for r in rs), 1),
        "same_recommendation_as_A": sum(r["rec"] == base[r["opp"]]["rec"] for r in rs if r["opp"] in base),
        "mean_abs_fit_diff_vs_A": round(st.mean(abs((r["fit"] or 0) - (base[r["opp"]]["fit"] or 0))
                                             for r in rs if r["opp"] in base), 1),
        "quote_warnings": sum(r["warnings"] for r in rs),
    }
(ROOT / "report" / "cost_experiment.json").write_text(json.dumps({"org": ORG, "results": results, "summary": summary},
                                                               indent=1))
print(json.dumps(summary, indent=1))

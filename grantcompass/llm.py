"""The model connection (gpt-6-luna through Portkey) and token accounting."""

import asyncio
import contextvars
import json
import threading
import time
from datetime import datetime, timezone

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from .config import (
    LOG_DIR,
    MAX_OUTPUT_TOKENS,
    MODEL_NAME,
    PORTKEY_BASE_URL,
    PORTKEY_PROVIDER,
    PRICE_CACHE_WRITE_PER_M,
    PRICE_CACHED_INPUT_PER_M,
    PRICE_INPUT_PER_M,
    PRICE_OUTPUT_PER_M,
    REASONING_EFFORT,
    REQUEST_LIMIT,
    TOTAL_TOKENS_LIMIT,
    portkey_api_key,
)

USAGE_LIMITS = UsageLimits(request_limit=REQUEST_LIMIT, total_tokens_limit=TOTAL_TOKENS_LIMIT)

MODEL_SETTINGS = OpenAIResponsesModelSettings(
    max_tokens=MAX_OUTPUT_TOKENS,
    openai_reasoning_effort=REASONING_EFFORT,
)


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey. The only model used anywhere in this project.

    Built fresh for each run so the async client belongs to that run's event loop."""
    key = portkey_api_key()
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": key, "x-portkey-provider": PORTKEY_PROVIDER},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


async def _run_agent(output_type, instructions: str, prompt: str):
    model = build_model()
    try:
        agent = Agent(model, output_type=output_type, instructions=instructions, model_settings=MODEL_SETTINGS,
                      retries=1)
        return await agent.run(prompt, usage_limits=USAGE_LIMITS)
    finally:
        await model.client.close()  # close inside the loop, so nothing is left for a closed loop to clean up


def run_agent(output_type, instructions: str, prompt: str, agent: str = "agent"):
    """Run one agent to completion with the project's model, limits and settings. Returns the pydantic-ai run."""
    return timed_run(agent, lambda: asyncio.run(_run_agent(output_type, instructions, prompt)))


# --- Monitoring: how long each run took, and every failure, for the Agent health page -----------
_timing = threading.local()  # per thread, because Discover assesses several results at once
# The signed-in organisation's log folder for this request (see db.use for why it's not a global).
_log_dir: contextvars.ContextVar = contextvars.ContextVar("log_dir", default=None)


def log_dir():
    return _log_dir.get() or LOG_DIR


def use_logs(folder) -> None:
    _log_dir.set(folder)


def timed_run(agent: str, fn):
    """Call fn(); remember its duration for the next log_run on this thread, and log any failure."""
    start = time.perf_counter()
    try:
        result = fn()
    except Exception as exc:
        log_event(agent, exc, time.perf_counter() - start)
        raise
    _timing.seconds = round(time.perf_counter() - start, 2)
    return result


def failure_kind(exc: Exception) -> str:
    name = type(exc).__name__
    if name == "UsageLimitExceeded":
        return "limit"  # a per-run cap stopped it
    if name == "ModelHTTPError" and "content_filter" in str(getattr(exc, "body", "") or exc):
        return "provider_block"  # the provider's prompt shield refused it
    return "error"


def log_event(agent: str, exc: Exception, seconds: float | None = None) -> None:
    """Append a failed run to logs/events.jsonl."""
    log_dir().mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "agent": agent,
              "event": failure_kind(exc), "error": type(exc).__name__,
              "seconds": round(seconds, 2) if seconds is not None else None}
    with open(log_dir() / "events.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def usage_dict(usage: RunUsage) -> dict:
    """Token counts for one run, split the way the tokenomics section needs them."""
    # input_tokens includes cache reads and cache writes; only the rest is billed at the full input rate.
    cached = usage.cache_read_tokens or 0
    written = usage.cache_write_tokens or 0
    uncached = usage.input_tokens - cached - written
    out = {
        "requests": usage.requests,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": cached,
        "cache_write_tokens": written,
        "uncached_input_tokens": uncached,
        "output_tokens": usage.output_tokens,
        "cost_usd": None,
    }
    if None not in (PRICE_INPUT_PER_M, PRICE_CACHED_INPUT_PER_M, PRICE_CACHE_WRITE_PER_M, PRICE_OUTPUT_PER_M):
        out["cost_usd"] = cost_usd(uncached, cached, written, usage.output_tokens)
    return out


def cost_usd(uncached: int, cached: int, written: int, output: int) -> float:
    return (uncached * PRICE_INPUT_PER_M + cached * PRICE_CACHED_INPUT_PER_M + written * PRICE_CACHE_WRITE_PER_M
            + output * PRICE_OUTPUT_PER_M) / 1_000_000


def log_run(agent: str, usage: dict, detail: dict | None = None) -> None:
    """Append one line per run to logs/usage.jsonl (real token counts for the report)."""
    log_dir().mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent": agent,
        "model": MODEL_NAME,
        **usage,
        "seconds": getattr(_timing, "seconds", None),
        **(detail or {}),
    }
    _timing.seconds = None
    with open(log_dir() / "usage.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")

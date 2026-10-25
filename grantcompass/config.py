"""Settings for Grant Compass: where the .env lives, the model, and the
limits that keep token use (and cost) in check."""

import os
from pathlib import Path

from dotenv import load_dotenv

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

ROOT = Path(__file__).resolve().parent.parent  # the repo folder
PROMPTS_DIR = ROOT / "grantcompass" / "prompts"
SAMPLE_DIR = ROOT / "data" / "sample"
LOG_DIR = ROOT / "logs"
DB_PATH = ROOT / "data" / "grantcompass.db"  # delete this file to reset to the sample data

# Discover only fetches pages from these sites (and their subdomains).
APPROVED_SOURCES = {
    "grants.gov": "Grants.gov — US federal grant listings",
}
FETCH_TIMEOUT_S = 15
MAX_FETCH_BYTES = 2_000_000
MAX_UPLOAD_BYTES = 10_000_000  # largest file we accept (10 MB); checked before it is decoded or parsed
MAX_REQUEST_BYTES = 64_000_000  # largest request the server accepts at all (several files at once)


# Look for .env in the repo folder first, then one folder up (where the
# teaching staff keep theirs). The first one found wins.
ENV_FILE: Path | None = None
for _candidate in (ROOT / ".env", ROOT.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        ENV_FILE = _candidate
        break

# The ONLY model this project uses, for every agent. Deliberately not
# overridable by an environment variable.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
PORTKEY_PROVIDER = "openai"


def portkey_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is not set. Put it in a .env file in this folder or the folder above it."
        )
    return key


# --- Cost guardrails (per run) ----------------------------------------------
REQUEST_LIMIT = 6  # model calls per run
TOTAL_TOKENS_LIMIT = 120_000  # input + output tokens per run
MAX_OUTPUT_TOKENS = 6_000  # per model response (includes reasoning tokens)
REASONING_EFFORT = "low"
MAX_INPUT_CHARS = 120_000  # largest org library or funder text we accept (~30k tokens)

# --- Pricing, USD per 1M tokens ---------------------------------------------
# gpt-6-luna, from the course's Lecture 11 (Tokenomics) slides.
PRICE_INPUT_PER_M: float | None = 0.10
PRICE_CACHED_INPUT_PER_M: float | None = 0.01
PRICE_CACHE_WRITE_PER_M: float | None = 0.125
PRICE_OUTPUT_PER_M: float | None = 0.50

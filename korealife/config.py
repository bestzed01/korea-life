"""Central configuration: filesystem paths and environment-driven settings.

Secrets (the Anthropic API key) are read from environment variables only and
are never written to disk or hardcoded anywhere in this project.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    # Load a local .env if present. Safe no-op if the file is missing.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge_base.json"
DEMO_PROFILE_PATH = DATA_DIR / "demo_profile.json"
DEMO_QUESTIONS_PATH = DATA_DIR / "demo_questions.json"


def database_path() -> str:
    """Resolve the SQLite database file path.

    Can be overridden with the KOREA_LIFE_DB environment variable (useful for
    tests). Defaults to korea_life.db at the project root.
    """
    override = os.environ.get("KOREA_LIFE_DB", "").strip()
    if override:
        return override
    return str(PROJECT_ROOT / "korea_life.db")


# ---------------------------------------------------------------------------
# Anthropic / Claude settings (secrets come from the environment only)
# ---------------------------------------------------------------------------
def anthropic_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


# Widely-available fallback models tried, in order, if the configured model
# returns a "model not found" (404) error. These are stable, broadly-accessible
# IDs so the live assistant keeps working even if ANTHROPIC_MODEL is set to a
# model the account can't access.
FALLBACK_MODELS = [
    "claude-3-5-sonnet-latest",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-latest",
]


def anthropic_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip() or "claude-sonnet-4-5"


def candidate_models() -> list:
    """The configured model first, then the fallbacks (de-duplicated)."""
    primary = anthropic_model()
    chain = [primary]
    for m in FALLBACK_MODELS:
        if m not in chain:
            chain.append(m)
    return chain


def ai_enabled() -> bool:
    """True when a live Claude API key is configured, else we run in fallback mode."""
    return bool(anthropic_api_key())

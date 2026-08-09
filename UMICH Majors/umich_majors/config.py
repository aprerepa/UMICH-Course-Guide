"""Config for UMICH Majors only.

Loads env from this project's `.env` (next to the package parent), never from the
KOL / Akaike `.env`. Tokenplex vars are intentionally ignored.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
RUNS = ROOT / "runs"
# Per-major program page + hopped requirements page (LLM-ready text).
REQUIREMENTS = ROOT / "requirements"
PLANNER_MAJORS = ROOT.parent / "Planner" / "config" / "majors"

# Only this project's env file — do not load ../.env (Tokenplex lives there).
_ENV_PATH = ROOT / ".env"
load_dotenv(_ENV_PATH, override=False)

MAJORS_LISTING_URL = "https://admissions.umich.edu/academics-majors/majors-degrees"


def llm_config() -> tuple[str, str, str]:
    """Return (base_url, api_key, model). Raises if missing."""
    base = (os.environ.get("UMICH_LLM_BASE_URL") or "").strip()
    key = (os.environ.get("UMICH_LLM_API_KEY") or "").strip()
    model = (os.environ.get("UMICH_LLM_MODEL") or "gpt-4o-mini").strip()
    if not base or not key:
        raise RuntimeError(
            "Set UMICH_LLM_BASE_URL and UMICH_LLM_API_KEY in "
            f"{_ENV_PATH} (see .env.example). "
            "Do not use TOKENPLEX_* — this is not the Akaike pipeline."
        )
    # Hard refuse Tokenplex host so a mistaken copy-paste fails loudly.
    if "tokenplex" in base.lower() or "akaike" in base.lower():
        raise RuntimeError(
            "UMICH_LLM_BASE_URL points at Tokenplex/Akaike. "
            "Use your own OpenAI-compatible endpoint instead."
        )
    return base.rstrip("/"), key, model

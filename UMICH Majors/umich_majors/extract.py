"""LLM extract from a fetched major detail page."""
from __future__ import annotations

from typing import Any

from umich_majors.llm import chat_json
from umich_majors.prompts import extract_system, extract_user


def llm_extract_major(
    major_name: str,
    school_college: str | None,
    page_text: str,
) -> dict[str, Any] | None:
    result = chat_json(
        extract_system(),
        extract_user(major_name, school_college, page_text),
        max_tokens=3000,
    )
    return result if isinstance(result, dict) else None

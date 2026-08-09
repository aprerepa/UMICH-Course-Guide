"""LLM prompts for major-page extraction."""
from __future__ import annotations


def extract_system() -> str:
    return (
        "You extract structured facts from University of Michigan undergraduate "
        "major / program web pages. Use ONLY the provided page text — never invent "
        "requirements, degrees, or contacts from outside knowledge. "
        "If a field is not stated, use null. Return a single JSON object."
    )


def extract_user(major_name: str, school_college: str | None, page_text: str) -> str:
    school = school_college or "(unknown school/college from listing)"
    return f"""This is a program page for the undergraduate major "{major_name}"
(listing school/college: {school}).

Confirm it is about this program, then extract:

Return JSON:
{{
  "is_correct_program": true/false,
  "official_name": string or null,
  "school_college": string or null,
  "degree_types": [string] or [],
  "overview": string or null,
  "what_you_study": string or null,
  "requirements_summary": string or null,
  "careers_or_outcomes": string or null,
  "contact_email": string or null,
  "contact_phone": string or null,
  "department_or_unit": string or null,
  "related_programs": [string] or [],
  "notes": string or null
}}

PAGE TEXT:
{page_text}
"""

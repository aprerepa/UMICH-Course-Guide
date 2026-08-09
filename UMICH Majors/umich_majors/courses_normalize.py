"""Normalize LLM course-extract output into Planner config/majors JSON shape."""
from __future__ import annotations

import re
from typing import Any

# STATS/DATASCI 413  or  EECS/CSE 280
_SLASH_SUBJECTS = re.compile(
    r"\b([A-Z]{2,}(?:/[A-Z]{2,})+)\s+(\d{3}[A-Z]?)\b"
)
# STATS 413 / DATASCI 413  (same number implied or repeated)
_PAIR_CODES = re.compile(
    r"\b([A-Z]{2,})\s+(\d{3}[A-Z]?)\s*/\s*([A-Z]{2,})(?:\s+(\d{3}[A-Z]?))?\b"
)
_SINGLE_CODE = re.compile(r"\b([A-Z]{2,})\s+(\d{3}[A-Z]?)\b")
_CODE_TOKEN = re.compile(r"^[A-Z]{2,}\s+\d{3}[A-Z]?$")

# SOC subject codes that the LLM / dept guides often abbreviate
_SUBJECT_ALIASES = {
    "TC": "TCHNCLCM",
}


def _canonicalize_code(code: str) -> str:
    parts = code.strip().upper().split()
    if len(parts) == 2 and parts[0] in _SUBJECT_ALIASES:
        return f"{_SUBJECT_ALIASES[parts[0]]} {parts[1]}"
    return code


def expand_cross_listed_token(token: str) -> list[str]:
    """Expand one LLM/course token into one or more SUBJ NNN strings."""
    raw = (token or "").strip().upper()
    raw = re.sub(r"\s+", " ", raw)
    if not raw:
        return []

    # Already a clean single code
    if _CODE_TOKEN.match(raw):
        return [_canonicalize_code(raw)]

    out: list[str] = []

    m = _SLASH_SUBJECTS.search(raw)
    if m:
        subjects = m.group(1).split("/")
        num = m.group(2)
        out.extend(_canonicalize_code(f"{s} {num}") for s in subjects)
        return out

    m = _PAIR_CODES.search(raw)
    if m:
        s1, n1, s2, n2 = m.group(1), m.group(2), m.group(3), m.group(4) or m.group(2)
        return [_canonicalize_code(f"{s1} {n1}"), _canonicalize_code(f"{s2} {n2}")]

    # Fall back: pull every SUBJECT NNN in the string
    for s, n in _SINGLE_CODE.findall(raw):
        out.append(_canonicalize_code(f"{s} {n}"))
    return out


def normalize_course_list(codes: Any) -> list[str]:
    """Flatten/expand/dedupe a list of course code strings (order preserved)."""
    if not isinstance(codes, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in codes:
        if not isinstance(item, str):
            continue
        for code in expand_cross_listed_token(item):
            if code not in seen:
                seen.add(code)
                result.append(code)
    return result


def normalize_requirement_groups(groups: Any) -> dict[str, list[str]]:
    if not isinstance(groups, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, codes in groups.items():
        if not isinstance(name, str) or not name.strip():
            continue
        cleaned = normalize_course_list(codes)
        if cleaned:
            out[name.strip()] = cleaned
    return out


def normalize_exclude_list(codes: Any) -> list[str]:
    """Normalize exclusion course codes; expand MCDB/EEB 300-style tokens."""
    return normalize_course_list(codes)


def normalize_open_rule(rule: Any) -> dict[str, Any] | None:
    """Normalize one open-band rule; return None if invalid."""
    if not isinstance(rule, dict):
        return None
    subjects_raw = rule.get("subjects") or rule.get("subject") or []
    if isinstance(subjects_raw, str):
        subjects_raw = [subjects_raw]
    subjects: list[str] = []
    seen_s: set[str] = set()
    for s in subjects_raw:
        if not isinstance(s, str):
            continue
        for part in re.split(r"[/,]| or ", s.upper()):
            part = re.sub(r"[^A-Z0-9]", "", part.strip())
            if len(part) >= 2 and part not in seen_s:
                seen_s.add(part)
                subjects.append(part)
    if not subjects:
        return None
    min_level = rule.get("minLevel", rule.get("min_level", 0))
    try:
        min_level = int(min_level)
    except (TypeError, ValueError):
        min_level = 0
    exclude = normalize_exclude_list(rule.get("exclude") or rule.get("exclusions") or [])
    return {
        "subjects": subjects,
        "minLevel": min_level,
        "exclude": exclude,
    }


def normalize_open_groups(open_groups: Any) -> dict[str, Any]:
    """
    Shape (value is a single rule, or a list when one group has multiple bands):
      {
        "Group D - Biology Elective": {
          "subjects": ["BIOLOGY", "EEB", "MCDB"],
          "minLevel": 200,
          "exclude": ["BIOLOGY 200", "EEB 300", ...]
        },
        "Additional Courses": [
          {"subjects": ["CHEM"], "minLevel": 230},
          {"subjects": ["MATH"], "minLevel": 200}
        ]
      }
    """
    if not isinstance(open_groups, dict):
        return {}
    out: dict[str, Any] = {}
    for name, rule_or_list in open_groups.items():
        if not isinstance(name, str) or not name.strip():
            continue
        raw_rules = (
            rule_or_list if isinstance(rule_or_list, list) else [rule_or_list]
        )
        cleaned: list[dict[str, Any]] = []
        for rule in raw_rules:
            norm = normalize_open_rule(rule)
            if norm:
                cleaned.append(norm)
        if not cleaned:
            continue
        out[name.strip()] = cleaned[0] if len(cleaned) == 1 else cleaned
    return out


def kebab_id(name: str, fallback: str = "major") -> str:
    s = re.sub(r"\(.*?\)", "", name or "")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or fallback


def build_major_config(
    *,
    major_id: str,
    display_name: str,
    llm_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge LLM JSON into the canonical Planner majors schema."""
    groups: dict[str, list[str]] = {}
    open_groups: dict[str, Any] = {}
    out_id = major_id
    out_name = display_name

    if isinstance(llm_result, dict):
        if isinstance(llm_result.get("displayName"), str) and llm_result["displayName"].strip():
            out_name = llm_result["displayName"].strip()
        if not out_id and isinstance(llm_result.get("id"), str):
            out_id = kebab_id(llm_result["id"])
        raw_groups = llm_result.get("requirementGroups")
        if raw_groups is None and isinstance(llm_result.get("groups"), dict):
            raw_groups = llm_result["groups"]
        groups = normalize_requirement_groups(raw_groups)
        open_groups = normalize_open_groups(
            llm_result.get("openGroups") or llm_result.get("open_groups")
        )
        # Ensure every openGroups key exists in requirementGroups (may be empty list)
        for gname in open_groups:
            groups.setdefault(gname, [])

    config: dict[str, Any] = {
        "id": out_id or kebab_id(out_name),
        "displayName": out_name,
        "requirementGroups": groups,
    }
    if open_groups:
        config["openGroups"] = open_groups
    return config

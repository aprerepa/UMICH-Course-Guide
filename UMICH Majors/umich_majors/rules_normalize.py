"""Normalize LLM groupRules extract → Planner/config/rules JSON shape."""
from __future__ import annotations

import re
from typing import Any

_COURSE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,12}\s+\d{2,4}[A-Z]?$", re.I)


def _positive_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value) if value == int(value) else value
    if isinstance(value, str):
        try:
            n = float(value.strip())
        except ValueError:
            return None
        if n > 0:
            return int(n) if n == int(n) else n
    return None


def _normalize_course_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    code = re.sub(r"\s+", " ", value.strip().upper())
    if not code or not _COURSE_RE.match(code):
        return None
    return code


def normalize_clause(clause: Any, *, depth: int = 0) -> Any | None:
    """Normalize a require-tree clause; returns None if unusable."""
    if depth > 12:
        return None

    if isinstance(clause, str):
        return _normalize_course_code(clause)

    if not isinstance(clause, dict):
        return None

    # allow wrapping a bare course as {"course": "BIOLOGY 171"}
    if "course" in clause and len(clause) == 1:
        return _normalize_course_code(clause.get("course"))

    if "anyOf" in clause or "any_of" in clause:
        raw = clause.get("anyOf", clause.get("any_of"))
        if not isinstance(raw, list):
            return None
        opts = [normalize_clause(c, depth=depth + 1) for c in raw]
        opts = [c for c in opts if c is not None]
        if not opts:
            return None
        if len(opts) == 1:
            return opts[0]
        return {"anyOf": opts}

    if "allOf" in clause or "all_of" in clause:
        raw = clause.get("allOf", clause.get("all_of"))
        if not isinstance(raw, list):
            return None
        parts = [normalize_clause(c, depth=depth + 1) for c in raw]
        parts = [c for c in parts if c is not None]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return {"allOf": parts}

    min_of = clause.get("minOf", clause.get("min_of"))
    options = clause.get("options")
    if min_of is not None or options is not None:
        n = _positive_number(min_of)
        if not isinstance(n, int) or n < 1 or not isinstance(options, list):
            return None
        opts = [normalize_clause(c, depth=depth + 1) for c in options]
        opts = [c for c in opts if c is not None]
        if len(opts) < n:
            return None
        return {"minOf": n, "options": opts}

    return None


def normalize_group_rule(rule: Any) -> dict[str, Any] | None:
    if not isinstance(rule, dict):
        return None

    out: dict[str, Any] = {}

    require_raw = rule.get("require")
    if require_raw is not None:
        require = normalize_clause(require_raw)
        if require is not None:
            out["require"] = require

    completion = rule.get("completion")
    if isinstance(completion, str) and completion.strip().lower() == "manual":
        # Prefer require tree when both present
        if "require" not in out:
            out["completion"] = "manual"

    min_courses = _positive_number(
        rule.get("minCourses") if "minCourses" in rule else rule.get("min_courses")
    )
    if isinstance(min_courses, float):
        min_courses = int(min_courses) if min_courses == int(min_courses) else None
    if isinstance(min_courses, int) and min_courses > 0:
        out["minCourses"] = min_courses

    min_credits = _positive_number(
        rule.get("minCredits") if "minCredits" in rule else rule.get("min_credits")
    )
    if min_credits is not None:
        out["minCredits"] = min_credits

    if rule.get("countsTowardMajorTotal") is True or rule.get(
        "counts_toward_major_total"
    ) is True:
        out["countsTowardMajorTotal"] = True

    if not out:
        return None
    if set(out.keys()) == {"countsTowardMajorTotal"}:
        return None
    return out


def normalize_group_rules(
    rules: Any,
    *,
    known_groups: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(rules, dict):
        return {}

    known = set(known_groups or [])
    out: dict[str, dict[str, Any]] = {}
    for name, rule in rules.items():
        if not isinstance(name, str) or not name.strip():
            continue
        key = name.strip()
        if known and key not in known:
            continue
        normalized = normalize_group_rule(rule)
        if normalized:
            out[key] = normalized
    return out


def build_rules_config(
    llm_result: dict[str, Any],
    *,
    major_id: str,
    display_name: str,
    known_groups: list[str] | None = None,
) -> dict[str, Any]:
    group_rules = normalize_group_rules(
        llm_result.get("groupRules") or llm_result.get("group_rules"),
        known_groups=known_groups,
    )
    return {
        "id": major_id,
        "displayName": display_name,
        "groupRules": group_rules,
    }

"""LLM prompts for extracting groupRules (quotas + prerequisite trees)."""
from __future__ import annotations


def rules_extract_system() -> str:
    return (
        "You extract undergraduate major completion rules from University of "
        "Michigan requirements pages — course/credit quotas per named group, and "
        "nested prerequisite combination trees when the page uses choose-one / "
        "all-of sequences. Use ONLY the provided page text. Do not invent course "
        "codes. Return a single JSON object."
    )


def rules_extract_user(
    major_name: str,
    school_college: str | None,
    page_text: str,
    *,
    known_groups: list[str] | None = None,
) -> str:
    school = school_college or "(unknown)"
    groups_hint = ""
    if known_groups:
        listed = "\n".join(f'  - "{g}"' for g in known_groups)
        groups_hint = f"""
Known requirement group names for this major (prefer these exact keys when the
page matches them; you may omit a group if the page gives no rule for it):
{listed}
"""

    return f"""Extract completion rules for "{major_name}"
(school/college: {school}) from the PAGE TEXT below.

Prefer the MOST RECENT requirements version (highest "Effective Fall/Winter YYYY").
Ignore older historical versions of the same major.
{groups_hint}
Return JSON with this exact shape:
{{
  "id": "kebab-case-id",
  "displayName": "{major_name}",
  "groupRules": {{
    "Group A: Gateway Biology Options": {{ "minCourses": 2, "minCredits": 6 }},
    "Lab Requirement": {{ "minCourses": 1 }},
    "Additional Courses": {{ "completion": "manual", "countsTowardMajorTotal": true }},
    "Prerequisites": {{
      "require": {{
        "allOf": [
          {{
            "anyOf": [
              {{
                "allOf": [
                  "BIOLOGY 171",
                  {{ "anyOf": ["BIOLOGY 172", "BIOLOGY 174"] }},
                  {{ "anyOf": ["BIOLOGY 173", "BIOLOGY 196"] }}
                ]
              }},
              {{
                "allOf": [
                  "BIOLOGY 195",
                  {{ "anyOf": ["BIOLOGY 173", "BIOLOGY 196"] }}
                ]
              }}
            ]
          }},
          {{ "allOf": ["CHEM 210", "CHEM 211"] }},
          {{
            "minOf": 3,
            "options": [
              {{ "anyOf": ["MATH 115", "MATH 120"] }},
              {{ "anyOf": ["MATH 116", "MATH 121"] }},
              {{ "anyOf": ["STATS 180", "STATS 250", "STATS 280"] }}
            ]
          }}
        ]
      }}
    }}
  }}
}}

Rules for each groupRules entry (use only fields that apply):
1. minCourses — integer when the page says take N courses / "two (2) courses" / "one course"
   from a pool of electives (student picks any N).
2. minCredits — number when the page requires a credit minimum for that group.
3. Both minCourses and minCredits may appear together when the page states both.
4. require — use whenever completion is a fixed combination of named courses, not only
   for Prerequisites:
   - course code string: that course must be taken
   - {{ "anyOf": [ ... ] }}: at least one clause (choose-one lists)
   - {{ "allOf": [ ... ] }}: every clause (all listed courses are required)
   - {{ "minOf": N, "options": [ ... ] }}: at least N of the option clauses
   Example: "Core: EECS 281, 370, 376" plus "one Probability/Statistics course from …"
   → {{ "require": {{ "allOf": ["EECS 281", "EECS 370", "EECS 376", {{ "anyOf": ["STATS 250", …] }}] }} }}
   Prefer require over minCourses when the page lists specific required courses (not a
   pick-N elective pool). Prefer require over completion:"manual" whenever the page
   spells out the courses or choose-one menus.
5. completion: "manual" — ONLY when the group cannot be encoded as quotas or a require
   tree (residual "enough credits to reach major total", advisor-only with no course
   list anywhere in the page/supplements). Do NOT use manual for "complete all of:
   COURSE A, B, C".
6. countsTowardMajorTotal: true — when courses in this group also fill an overall
   major credit total.
7. Course codes are "SUBJECT CATALOG" with one space (e.g. "EECS 281").
   Do not invent codes; only use codes listed on the page or linked supplements.
8. Do NOT invent groups that are not on the page.
9. If nothing can be determined, return groupRules: {{}}.

PAGE TEXT:
{page_text}
"""

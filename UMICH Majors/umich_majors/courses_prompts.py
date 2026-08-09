"""LLM prompts for extracting requirementGroups (subcategory → course codes)."""
from __future__ import annotations


def courses_extract_system() -> str:
    return (
        "You extract undergraduate course requirement lists from University of "
        "Michigan major requirements pages. Use ONLY the provided page text and "
        "any labeled Supplement sections — never invent courses. Return a single "
        "JSON object."
    )


def courses_extract_user(major_name: str, school_college: str | None, page_text: str) -> str:
    school = school_college or "(unknown)"
    return f"""Extract the undergraduate course requirements for "{major_name}"
(school/college: {school}) from the PAGE TEXT below.

Prefer the MOST RECENT requirements version on the page (highest "Effective Fall/Winter
YYYY"). Ignore older historical versions of the same major.

Sections titled "### Supplement: …" are linked course lists / approved lists for
specific requirement groups. Use them to fill the matching group's explicit course
codes (or openGroups when they describe a band). Do not treat supplements as a
different major.

Return JSON with this exact shape:
{{
  "id": "kebab-case-id",
  "displayName": "{major_name}",
  "requirementGroups": {{
    "Group Name": ["SUBJ 123", "SUBJ 456"]
  }},
  "openGroups": {{
    "Group Name": {{
      "subjects": ["BIOLOGY", "EEB"],
      "minLevel": 200,
      "exclude": ["BIOLOGY 200", "BIOLOGY 212", "EEB 300"]
    }},
    "Additional Courses": [
      {{"subjects": ["CHEM"], "minLevel": 230}},
      {{"subjects": ["MATH"], "minLevel": 200}},
      {{"subjects": ["PHYSICS"], "minLevel": 200}},
      {{"subjects": ["STATS"], "minLevel": 400}}
    ]
  }}
}}

Rules:
1. requirementGroups: named subcategories with EXPLICIT course codes listed on the page.
   Codes are "SUBJECT CATALOG" with one space (e.g. "EECS 280", "BIOLOGY 171").
2. Nesting / prerequisites: if the page has a parent section like "Prerequisites"
   that contains subsections (e.g. Introductory Biology, Chemistry, Quantitative
   Analysis), put ALL of those courses into ONE group named "Prerequisites"
   (or the parent section title). Do NOT invent separate groups for each subsection.
   Use separate groups only for top-level requirement categories (Core, Electives,
   Group A/B/C/D, Lab, etc.).
3. Cross-listed courses: if the page lists multiple subjects for one course
   ("STATS 413 / DATASCI 413", "STATS/DATASCI 413", "WGS / NURS 220"),
   include EVERY subject as its own string (["STATS 413", "DATASCI 413"]).
4. openGroups: use when the page says you may take ANY course in a subject / level
   band, often with exclusions — e.g. "BIOLOGY, EEB, or MCDB 200-, 300-, or 400-level
   (excluding BIOLOGY 200, 212, 241, 299; MCDB/EEB 300, 301, ...)" OR phrasing like
   "CHEM 230 and above", "MATH 200-level or above", "STATS 400-level or above".
   - subjects: subject codes that are allowed
   - minLevel: lowest allowed catalog number (200 for "200-level or above";
     230 for "CHEM 230 and above"; 400 for "400-level or above")
   - exclude: full course codes that are NOT allowed (expand MCDB/EEB 300 →
     both "MCDB 300" and "EEB 300")
   The openGroups key must match the requirementGroups group name. A group may
   have BOTH explicit courses in requirementGroups AND open rules in openGroups.
   If one group has multiple subject/level bands with DIFFERENT minLevels, set
   openGroups[group] to an ARRAY of rule objects (one per band). If all subjects
   share the same minLevel/exclusions, a single rule object is fine.
5. Do NOT try to invent every BIOLOGY 2xx/3xx/4xx / MATH 200+ course yourself —
   use openGroups for those bands; only list explicit codes in requirementGroups.
6. Skip graduate-only sections, admissions fluff, and LSA college distribution rules.
7. If there are no courses, return requirementGroups: {{}} and omit openGroups.

PAGE TEXT:
{page_text}
"""

# ── Imports ───────────────────────────────────────────────────────────────────

import os
import requests
import json
import base64
import time
import re
from pathlib import Path
from collections import defaultdict, deque

# ── Config ────────────────────────────────────────────────────────────────────

def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CLIENT_ID = os.environ.get("UMICH_SOC_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("UMICH_SOC_CLIENT_SECRET", "").strip()
if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit(
        "Missing UMICH_SOC_CLIENT_ID / UMICH_SOC_CLIENT_SECRET. "
        "Copy Planner/.env.example to Planner/.env and fill in your SOC API credentials."
    )

BASE_URL      = "https://gw.api.it.umich.edu/um/Curriculum/SOC"  # base URL for all endpoints
TERM_CODE     = "2610"   # identifies Fall 2026 in UMich's system

# UMich API limit is 500 calls/minute — stay under with headroom
MAX_CALLS_PER_MINUTE = 450

# ── Subject -> School code mapping ────────────────────────────────────────────

SUBJECT_SCHOOL = {
    "EECS":     "EG",
    "CSE":      "EG",
    "ROB":      "EG",
    "IOE":      "EG",
    "MFG":      "EG",
    "ECE":      "EG",
    "AEROSP":   "EG",
    "ENGR":     "EG",
    "MECHENG":  "EG",
    "CEE":      "EG",
    "BIOMEDE":  "EG",
    "CHE":      "EG",
    "MATSCIE":  "EG",
    "NERS":     "EG",
    "NAVARCH":  "EG",
    "CLIMATE":  "EG",
    "DATASCI":  "LS",
    "STATS":    "LS",
    "MATH":     "LS",
    "ECON":     "LS",
    "BIOINF":   "LS",
    "BIOPHYS":  "LS",
    "PHYSICS":  "LS",
    "CMPLXSYS": "LS",
    "COGSCI":   "LS",
    "LING":     "LS",
    "EARTH":    "LS",
    "ENVIRON":  "LS",
    "SPACE":    "LS",
    "ASTRO":    "LS",
    "EEB":      "LS",
    "ANTHRBIO": "LS",
    "POLSCI":   "LS",
    "BIOSTAT":  "PH",
    "SI":       "SI",
    "BIOLOGY":  "LS",
    "CHEM":     "LS",
    "BIOLCHEM": "LS",
    "MCDB":     "LS",
    "MICRBIOL": "LS",
    "ANTHRCUL": "LS",
    "RCSSCI":   "LS",
    "AMCULT":   "LS",
    "HISTORY":  "LS",
    "PHIL":     "LS",
    "PSYCH":    "LS",
    "SOC":      "LS",
    "PUBHLTH":  "PH",
    "PUBPOL":   "LS",
    "MIDEAST":  "LS",
    "STS":      "LS",
    "IHS":      "LS",
    "AAS":      "LS",
    "ALA":      "LS",
    "WGS":      "LS",
    "COMPFOR":  "LS",
    # Ross / IOE technical electives
    "ACC":      "BA",
    "FIN":      "BA",
    "MKT":      "BA",
    "STRATEGY": "BA",
    "BL":       "BA",
    "MO":       "BA",
    "TO":       "BA",
    # Kinesiology / public health bands from IOE TE list
    "MOVESCI":  "PE",
    "KINESLGY": "PE",
    "ANATOMY":  "LS",
    "PHYSIOL":  "LS",
    "EPID":     "PH",
    "EHS":      "PH",
    "HSMP":     "PH",
    "HMP":      "PH",
    "TC":       "EG",
    "TCHNCLCM": "EG",
}

# ── Subject exclusions for open-ended groups ──────────────────────────────────

SUBJECT_EXCLUSIONS = {
    "BIOLOGY": {"200", "212", "241", "299"},
    "EEB":     {"300", "301", "302", "396", "397", "399", "400", "412",
                "460", "461", "494", "499"},
    "MCDB":    {"300", "301", "302", "360", "396", "397", "399", "400",
                "412", "460", "461", "494", "499"},
}

# ── Course lists (one JSON per major) ─────────────────────────────────────────
# Files: Planner/config/majors/<kebab-id>.json
# Shape: { "id", "displayName", "requirementGroups": { "Group": ["SUBJ 123", ...] } }

MAJORS_DIR = Path(__file__).resolve().parents[1] / "config" / "majors"


def load_major_courses(majors_dir: Path = MAJORS_DIR) -> dict:
    """
    Load displayName → requirement groups from config/majors/*.json.

    Supports optional openGroups: expand subject/level bands via SOC catalog,
    applying per-major exclude lists (and SUBJECT_EXCLUSIONS defaults).
    Returns (major_courses, open_group_specs) where open_group_specs is
    displayName → { groupName → rule }.
    """
    major_courses = {}
    open_specs = {}
    for path in sorted(majors_dir.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "requirementGroups" not in data:
            raise ValueError(
                f"{path.name}: expected keys id, displayName, requirementGroups"
            )
        name = data.get("displayName") or data.get("id") or path.stem
        major_courses[name] = {
            k: list(v) for k, v in data["requirementGroups"].items()
        }
        if isinstance(data.get("openGroups"), dict) and data["openGroups"]:
            open_specs[name] = data["openGroups"]
    if not major_courses:
        raise FileNotFoundError(f"No major JSON files found in {majors_dir}")
    return major_courses, open_specs


MAJOR_COURSES, OPEN_GROUP_SPECS = load_major_courses()

# ── Auth ──────────────────────────────────────────────────────────────────────

def get_token():
    credentials = base64.b64encode(
        f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    ).decode()
    resp = requests.post(
        "https://gw.api.it.umich.edu/um/oauth2/token",
        headers={"Authorization": f"Basic {credentials}"},
        data={
            "grant_type": "client_credentials",
            "scope": "umscheduleofclasses"
        }
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

# ── Rate limit (sliding 60s window) ───────────────────────────────────────────

class RateLimiter:
    """Cap API calls under MAX_CALLS_PER_MINUTE over any rolling 60s window."""

    def __init__(self, max_calls=MAX_CALLS_PER_MINUTE, period=60.0):
        self.max_calls = max_calls
        self.period = period
        self._times = deque()

    def wait(self):
        now = time.monotonic()
        while self._times and now - self._times[0] >= self.period:
            self._times.popleft()
        if len(self._times) >= self.max_calls:
            sleep_for = self.period - (now - self._times[0]) + 0.05
            if sleep_for > 0:
                print(f"  Rate limit: waiting {sleep_for:.1f}s "
                      f"({self.max_calls} calls/{int(self.period)}s)…")
                time.sleep(sleep_for)
            now = time.monotonic()
            while self._times and now - self._times[0] >= self.period:
                self._times.popleft()
        self._times.append(time.monotonic())


_rate_limiter = RateLimiter()
# Cache CatalogNbrs responses per subject so openGroups don't re-hit the API
_catalog_nbrs_cache: dict[str, list] = {}

# ── API wrapper ───────────────────────────────────────────────────────────────

def api_get(token, path):
    _rate_limiter.wait()
    resp = requests.get(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_meeting(section):
    meeting = section.get("Meeting", {})
    if isinstance(meeting, list):
        meeting = meeting[0] if meeting else {}
    return meeting

def get_instructor(section):
    ci = section.get("ClassInstructors", {})
    if isinstance(ci, list):
        return ", ".join(i.get("InstrName", "") for i in ci)
    elif isinstance(ci, dict):
        return ci.get("InstrName", "")
    return ""

def fetch_all_courses_for_subject(token, subject, min_level=0, exclusions=None):
    school = SUBJECT_SCHOOL.get(subject, "LS")
    cache_key = f"{school}:{subject}"
    if cache_key not in _catalog_nbrs_cache:
        path = f"/Terms/{TERM_CODE}/Schools/{school}/Subjects/{subject}/CatalogNbrs"
        try:
            data = api_get(token, path)
        except requests.HTTPError as e:
            print(f"  Skipping subject {subject}: {e}")
            _catalog_nbrs_cache[cache_key] = []
            return []
        resp = data.get("getSOCCtlgNbrsResponse", {}) or {}
        # API may return ClassOffered (current) or CatalogNbr (older schema)
        catalog_nbrs = resp.get("ClassOffered") or resp.get("CatalogNbr") or []
        if isinstance(catalog_nbrs, dict):
            catalog_nbrs = [catalog_nbrs]
        _catalog_nbrs_cache[cache_key] = catalog_nbrs
    catalog_nbrs = _catalog_nbrs_cache[cache_key]

    if exclusions is None:
        exclusions = SUBJECT_EXCLUSIONS.get(subject, set())
    else:
        exclusions = set(str(x) for x in exclusions) | SUBJECT_EXCLUSIONS.get(subject, set())

    codes = []
    for entry in catalog_nbrs:
        if not isinstance(entry, dict):
            continue
        nbr = str(entry.get("CatalogNumber", "")).strip()
        if not nbr:
            continue
        # Catalog may be "200" or "200-001" — compare numeric prefix
        try:
            level = int(re.match(r"\d+", nbr).group(0))
        except (AttributeError, ValueError):
            continue
        if nbr in exclusions or str(level) in exclusions:
            continue
        if level < min_level:
            continue
        codes.append(f"{subject} {nbr}")
    return codes


def exclusions_by_subject(exclude_codes):
    """['BIOLOGY 200', 'EEB 300'] → {'BIOLOGY': {'200'}, 'EEB': {'300'}}"""
    out = defaultdict(set)
    for code in exclude_codes or []:
        parts = str(code).strip().upper().split()
        if len(parts) >= 2:
            out[parts[0]].add(parts[1])
    return out


def expand_open_groups(token, major_courses, open_specs):
    """Mutate major_courses in place: append SOC-expanded codes for openGroups.

    Each openGroups value may be a single rule dict or a list of rules
    (multiple subject/level bands under one requirement group).
    """
    for major, specs in open_specs.items():
        groups = major_courses.setdefault(major, {})
        for group_name, rule_or_list in specs.items():
            rules = rule_or_list if isinstance(rule_or_list, list) else [rule_or_list]
            existing = set(groups.get(group_name) or [])
            added = []
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                subjects = rule.get("subjects") or []
                min_level = int(rule.get("minLevel") or 0)
                by_subj = exclusions_by_subject(rule.get("exclude") or [])
                for subject in subjects:
                    excl = by_subj.get(subject.upper(), set())
                    print(f"  Expanding {major} / {group_name}: {subject} {min_level}+ "
                          f"(exclude {sorted(excl)[:8]}{'…' if len(excl)>8 else ''})")
                    for code in fetch_all_courses_for_subject(
                        token, subject, min_level=min_level, exclusions=excl
                    ):
                        if code not in existing:
                            existing.add(code)
                            added.append(code)
            groups[group_name] = list(groups.get(group_name) or []) + added
            print(f"    → +{len(added)} courses")

# ── Course fetcher ────────────────────────────────────────────────────────────

def fetch_course(token, subject, catalog_num):
    school = SUBJECT_SCHOOL.get(subject, "LS")

    desc_path = (
        f"/Terms/{TERM_CODE}/Schools/{school}"
        f"/Subjects/{subject}/CatalogNbrs/{catalog_num}"
    )
    try:
        desc_data = api_get(token, desc_path)
        desc_raw = desc_data.get("getSOCCourseDescrResponse", {}).get("CourseDescr", "")
        title = desc_raw.split(" --- ")[0] if " --- " in desc_raw else desc_raw
    except requests.HTTPError:
        title = ""

    sections_path = (
        f"/Terms/{TERM_CODE}/Schools/{school}"
        f"/Subjects/{subject}/CatalogNbrs/{catalog_num}"
        f"/Sections?IncludeAllSections=Y"
    )
    try:
        data = api_get(token, sections_path)
    except requests.HTTPError as e:
        print(f"    Skipping {subject} {catalog_num}: {e}")
        return None

    sections = data.get("getSOCSectionsResponse", {}).get("Section", [])
    if not sections:
        return None
    if isinstance(sections, dict):
        sections = [sections]

    lectures = [s for s in sections if s.get("SectionType") == "LEC"]
    if not lectures:
        lectures = sections

    first = lectures[0]

    return {
        "code":             f"{subject} {catalog_num}",
        "title":            title,
        "credits":          first.get("CreditHours", 0),
        "semester":         TERM_CODE,
        "sections":         len(lectures),
        "seats":            sum(s.get("AvailableSeats", 0) for s in lectures),
        "enrollmentStatus": first.get("EnrollmentStatus", ""),
        "sectionDetails": [
            {
                "id":         str(s.get("SectionNumber", "")),
                "days":       get_meeting(s).get("Days", ""),
                "time":       get_meeting(s).get("Times", ""),
                "room":       get_meeting(s).get("Location", ""),
                "seats":      s.get("AvailableSeats", 0),
                "instructor": get_instructor(s),
            }
            for s in lectures
        ],
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def _parse_codes_arg(raw):
    """Parse --codes 'TCHNCLCM 380' or --codes TCHNCLCM380."""
    if not raw:
        return None
    out = set()
    for item in raw:
        for chunk in item.split(","):
            chunk = " ".join(chunk.strip().split())
            if not chunk:
                continue
            parts = chunk.upper().split()
            if len(parts) == 2:
                out.add(f"{parts[0]} {parts[1]}")
            elif len(parts) == 1:
                m = re.match(r"^([A-Z]+)(\d{3}[A-Z]?)$", parts[0])
                if m:
                    out.add(f"{m.group(1)} {m.group(2)}")
    return out or None


def _index_courses(output: dict) -> dict:
    """code → course object from any major/group in courses.json."""
    index = {}
    for groups in (output or {}).values():
        for courses in (groups or {}).values():
            for c in courses or []:
                if isinstance(c, dict) and c.get("code"):
                    index[c["code"]] = c
    return index


def _rebuild_majors_from_cache(output: dict, course_cache: dict) -> dict:
    """
    Rebuild every major/group from config, preferring freshly fetched courses,
    then any course already present anywhere in courses.json.

    Also keeps previously stored courses in a group that are not in the explicit
    config list (e.g. openGroups expansions), so a resync does not wipe them.
    """
    global_cache = _index_courses(output)
    global_cache.update(course_cache)
    for major, groups in MAJOR_COURSES.items():
        prev_groups = output.get(major) or {}
        major_out = {}
        for group, codes in groups.items():
            merged = []
            seen = set()
            for code in codes:
                if code in global_cache and code not in seen:
                    merged.append(global_cache[code])
                    seen.add(code)
            for c in prev_groups.get(group) or []:
                if not isinstance(c, dict):
                    continue
                code = c.get("code")
                if code and code not in seen:
                    merged.append(c)
                    seen.add(code)
            if merged:
                major_out[group] = merged
        if major_out:
            output[major] = major_out
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch SOC courses into src/data/courses.json"
    )
    parser.add_argument(
        "--codes",
        nargs="+",
        metavar="CODE",
        help='Only fetch these codes and merge into existing courses.json '
             '(e.g. --codes "TCHNCLCM 380")',
    )
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Only fetch codes listed in config/majors that are not yet in "
             "src/data/courses.json, then rebuild all majors from cache",
    )
    parser.add_argument(
        "--resync",
        action="store_true",
        help="Rebuild courses.json groups from config using already-fetched "
             "courses (no API calls). Use after fixing merge/config.",
    )
    args = parser.parse_args()
    only_codes = _parse_codes_arg(args.codes)
    out_path = Path("src/data/courses.json")

    if args.resync:
        if not out_path.exists():
            raise SystemExit("No src/data/courses.json to resync")
        output = json.loads(out_path.read_text(encoding="utf-8"))
        before = {m: {g: len(cs) for g, cs in gs.items()} for m, gs in output.items()}
        output = _rebuild_majors_from_cache(output, {})
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print("Resynced majors from config + existing course cache:")
        for major, groups in output.items():
            print(f"  {major}")
            for g, cs in groups.items():
                old = before.get(major, {}).get(g)
                note = f" (was {old})" if old is not None and old != len(cs) else ""
                print(f"    {g}: {len(cs)}{note}")
        raise SystemExit(0)

    print("Getting token...")
    token = get_token()

    if args.missing or only_codes is None:
        # Expand openGroups into MAJOR_COURSES so bands are included
        if OPEN_GROUP_SPECS:
            print("\nExpanding openGroups via SOC catalog…")
            expand_open_groups(token, MAJOR_COURSES, OPEN_GROUP_SPECS)

    if args.missing:
        have = set()
        if out_path.exists():
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            have = set(_index_courses(existing))
        needed = set()
        for groups in MAJOR_COURSES.values():
            for codes in groups.values():
                needed.update(codes)
        only_codes = needed - have
        if not only_codes:
            print("No new SOC fetches needed — resyncing groups from cache…")
            output = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
            output = _rebuild_majors_from_cache(output, {})
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)
            print(f"Done — wrote {out_path}")
            raise SystemExit(0)
        print(f"Will fetch {len(only_codes)} missing course(s)")

    if only_codes:
        print(
            f"\nFetching {len(only_codes)} course(s) only "
            f"(≤{MAX_CALLS_PER_MINUTE} API calls/min)..."
        )
        course_cache = {}
        for code in sorted(only_codes):
            parts = code.strip().split()
            if len(parts) != 2:
                print(f"  Skipping malformed code: {code!r}")
                continue
            subject, catalog_num = parts
            print(f"  {code}")
            course = fetch_course(token, subject, catalog_num)
            if course:
                course_cache[code] = course
            else:
                print("    (not found / skipped)")

        output = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
        output = _rebuild_majors_from_cache(output, course_cache)

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"\nDone — merged {len(course_cache)} newly fetched + resynced all majors → {out_path}")
    else:
        all_codes = set()
        for groups in MAJOR_COURSES.values():
            for codes in groups.values():
                all_codes.update(codes)

        print(
            f"\nFetching {len(all_codes)} unique courses "
            f"(≤{MAX_CALLS_PER_MINUTE} API calls/min)..."
        )
        course_cache = {}
        for code in sorted(all_codes):
            subject, catalog_num = code.strip().split()
            print(f"  {code}")
            course = fetch_course(token, subject, catalog_num)
            if course:
                course_cache[code] = course

        output = {}
        for major, groups in MAJOR_COURSES.items():
            output[major] = {}
            for group, codes in groups.items():
                group_courses = [
                    course_cache[code]
                    for code in codes
                    if code in course_cache
                ]
                if group_courses:
                    output[major][group] = group_courses

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        print(f"\nDone — wrote {out_path}")

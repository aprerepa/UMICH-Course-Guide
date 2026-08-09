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

BASE_URL = "https://gw.api.it.umich.edu/um/Curriculum/SOC"

# Live term(s) — re-fetchable as schedules change
CURRENT_TERMS = ["2610"]  # Fall 2026

# Historical Fall/Winter (~2 years) — fetch once; schedules do not change
# WN26, FA25, WN25, FA24
HISTORY_TERMS = ["2570", "2560", "2520", "2510"]

ALL_TERMS = HISTORY_TERMS + CURRENT_TERMS

# Expand openGroups against the live catalog
TERM_CODE = CURRENT_TERMS[0]

TERM_LABELS = {
    "2510": "Fall 2024",
    "2520": "Winter 2025",
    "2560": "Fall 2025",
    "2570": "Winter 2026",
    "2610": "Fall 2026",
}

# UMich API limit is 500 calls/minute — stay under with headroom
MAX_CALLS_PER_MINUTE = 450

FETCH_LOG_PATH = Path(__file__).resolve().parents[1] / "src" / "data" / "soc_term_fetch_log.json"

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

def fetch_all_courses_for_subject(token, subject, min_level=0, exclusions=None, term_code=None):
    term_code = term_code or TERM_CODE
    school = SUBJECT_SCHOOL.get(subject, "LS")
    cache_key = f"{term_code}:{school}:{subject}"
    if cache_key not in _catalog_nbrs_cache:
        path = f"/Terms/{term_code}/Schools/{school}/Subjects/{subject}/CatalogNbrs"
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

def offering_key(code: str, term: str) -> str:
    return f"{code}|{term}"


def load_fetch_log(path: Path = FETCH_LOG_PATH) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def save_fetch_log(log: dict, path: Path = FETCH_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def seed_fetch_log_from_courses(output: dict, log: dict) -> dict:
    """Mark existing offerings as fetched so history is not re-pulled."""
    for groups in (output or {}).values():
        for courses in (groups or {}).values():
            for c in courses or []:
                if not isinstance(c, dict):
                    continue
                code, term = c.get("code"), str(c.get("semester") or "")
                if code and term:
                    log[offering_key(code, term)] = "ok"
    return log


def fetch_course(token, subject, catalog_num, term_code=None):
    term_code = str(term_code or TERM_CODE)
    school = SUBJECT_SCHOOL.get(subject, "LS")

    desc_path = (
        f"/Terms/{term_code}/Schools/{school}"
        f"/Subjects/{subject}/CatalogNbrs/{catalog_num}"
    )
    try:
        desc_data = api_get(token, desc_path)
        desc_raw = desc_data.get("getSOCCourseDescrResponse", {}).get("CourseDescr", "")
        title = desc_raw.split(" --- ")[0] if " --- " in desc_raw else desc_raw
    except requests.HTTPError:
        title = ""

    sections_path = (
        f"/Terms/{term_code}/Schools/{school}"
        f"/Subjects/{subject}/CatalogNbrs/{catalog_num}"
        f"/Sections?IncludeAllSections=Y"
    )
    try:
        data = api_get(token, sections_path)
    except requests.HTTPError as e:
        print(f"    Skipping {subject} {catalog_num} ({term_code}): {e}")
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
        "semester":         term_code,
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
    """(code|semester) → course object from any major/group in courses.json."""
    index = {}
    for groups in (output or {}).values():
        for courses in (groups or {}).values():
            for c in courses or []:
                if not isinstance(c, dict) or not c.get("code"):
                    continue
                term = str(c.get("semester") or "")
                if not term:
                    continue
                index[offering_key(c["code"], term)] = c
    return index


def _courses_by_code(index: dict) -> dict:
    """code → list of course offerings sorted by term."""
    by_code = defaultdict(list)
    for c in index.values():
        by_code[c["code"]].append(c)
    for code, offerings in by_code.items():
        offerings.sort(key=lambda x: str(x.get("semester") or ""))
    return by_code


def _rebuild_majors_from_cache(output: dict, course_cache: dict) -> dict:
    """
    Rebuild every major/group from config, attaching every known semester
    offering for each course code.

    Also keeps previously stored courses in a group that are not in the explicit
    config list (e.g. openGroups expansions), so a resync does not wipe them.
    """
    global_cache = _index_courses(output)
    global_cache.update(course_cache)
    by_code = _courses_by_code(global_cache)

    for major, groups in MAJOR_COURSES.items():
        prev_groups = output.get(major) or {}
        major_out = {}
        for group, codes in groups.items():
            merged = []
            seen = set()
            for code in codes:
                for c in by_code.get(code, []):
                    key = offering_key(c["code"], str(c.get("semester") or ""))
                    if key not in seen:
                        merged.append(c)
                        seen.add(key)
            for c in prev_groups.get(group) or []:
                if not isinstance(c, dict):
                    continue
                code = c.get("code")
                term = str(c.get("semester") or "")
                if not code or not term:
                    continue
                key = offering_key(code, term)
                if key not in seen:
                    merged.append(c)
                    seen.add(key)
            if merged:
                major_out[group] = merged
        if major_out:
            output[major] = major_out
    return output


def _iter_config_codes():
    codes = set()
    for groups in MAJOR_COURSES.values():
        for group_codes in groups.values():
            codes.update(group_codes)
    return codes


def _missing_offerings(codes, terms, fetch_log, force_terms=None):
    """Return sorted list of (code, term) still needing a SOC fetch."""
    force_terms = set(force_terms or [])
    needed = []
    for code in codes:
        for term in terms:
            key = offering_key(code, term)
            if term in force_terms or key not in fetch_log:
                needed.append((code, term))
    needed.sort(key=lambda x: (x[1], x[0]))
    return needed


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
        help="Fetch (code, term) pairs not yet recorded in the fetch log "
             "(history once + any missing current-term rows), then rebuild",
    )
    parser.add_argument(
        "--current-only",
        action="store_true",
        help="Only consider CURRENT_TERMS (skip history backfill)",
    )
    parser.add_argument(
        "--refresh-current",
        action="store_true",
        help="Re-fetch CURRENT_TERMS for all config codes even if already logged",
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
    terms = list(CURRENT_TERMS) if args.current_only else list(ALL_TERMS)
    force_terms = set(CURRENT_TERMS) if args.refresh_current else set()

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

    fetch_log = load_fetch_log()
    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    fetch_log = seed_fetch_log_from_courses(existing, fetch_log)

    if args.missing or only_codes is None or args.refresh_current:
        # Expand openGroups into MAJOR_COURSES so bands are included
        if OPEN_GROUP_SPECS:
            print("\nExpanding openGroups via SOC catalog…")
            expand_open_groups(token, MAJOR_COURSES, OPEN_GROUP_SPECS)

    config_codes = _iter_config_codes()
    if only_codes is not None:
        target_codes = only_codes
    else:
        target_codes = config_codes

    # Default / --missing / --codes / --refresh-current all use the pair queue
    pairs = _missing_offerings(target_codes, terms, fetch_log, force_terms=force_terms)
    if not pairs:
        print("No new SOC fetches needed — resyncing groups from cache…")
        output = _rebuild_majors_from_cache(existing, {})
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        save_fetch_log(fetch_log)
        print(f"Done — wrote {out_path}")
        raise SystemExit(0)

    print(
        f"\nFetching {len(pairs)} offering(s) "
        f"across terms {[TERM_LABELS.get(t, t) for t in terms]} "
        f"(≤{MAX_CALLS_PER_MINUTE} API calls/min)..."
    )
    course_cache = {}
    found = 0
    missing = 0
    for code, term in pairs:
        parts = code.strip().split()
        if len(parts) != 2:
            print(f"  Skipping malformed code: {code!r}")
            continue
        subject, catalog_num = parts
        label = TERM_LABELS.get(term, term)
        print(f"  {code} @ {label} ({term})")
        course = fetch_course(token, subject, catalog_num, term_code=term)
        key = offering_key(code, term)
        if course:
            course_cache[key] = course
            fetch_log[key] = "ok"
            found += 1
        else:
            fetch_log[key] = "missing"
            missing += 1
            print("    (not offered / skipped)")

    output = existing
    output = _rebuild_majors_from_cache(output, course_cache)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    save_fetch_log(fetch_log)
    print(
        f"\nDone — merged {found} offerings "
        f"({missing} not offered), wrote {out_path}"
    )
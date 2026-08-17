"""Parse a UMich unofficial transcript PDF into course rows.

PeopleSoft transcripts are landscape two-column with no drawn table rules, so
pdfplumber extract_tables() is empty. Crop left/right columns, then parse the
aligned course lines (subject, catalog, title, grade, Hours/MSH/CTP/MHP).
"""
from __future__ import annotations

import io
import re
from typing import Any, BinaryIO

import pdfplumber

TERM_RE = re.compile(
    r"^(Fall|Winter|Spring|Summer)\s+(\d{4})\b",
    re.I,
)
COURSE_START_RE = re.compile(
    r"^([A-Z]{2,12})\s+(\d{2,4}[A-Z]?)\b",
)
NUM4_RE = re.compile(
    r"(?P<hours>\d+\.\d{2})\s+(?P<msh>\d+\.\d{2})\s+"
    r"(?P<ctp>\d+\.\d{2})\s+(?P<mhp>\d+\.\d{2})\s*$"
)
GRADE_RE = re.compile(
    r"^(?P<title>.*?)\s+(?P<grade>A\+|A-|B\+|B-|C\+|C-|D\+|D-|A|B|C|D|E|F|T|Y|W|I|P|CR|NR)$"
)

PASSING_GRADES = {
    "A+",
    "A",
    "A-",
    "B+",
    "B",
    "B-",
    "C+",
    "C",
    "C-",
    "D+",
    "D",
    "D-",
    "P",
    "CR",
    "T",
}

SKIP_LINE_RE = re.compile(
    r"^(THE UNIVERSITY|Unofficial Transcript|Not an Official|Page \d|"
    r"UM ID:|Uniqname:|Date:|United States|Term Total|Cumulative Total|"
    r"Transfer Credit Accepted|Academic Statistics|Total to Date|"
    r"Program Action|Plan Change|Matriculation|Honors|Academic Previous|"
    r"High School|End of Unofficial|Elected Term Hours|Lit, Sci|"
    r"LSA Undeclared|Minor -)",
    re.I,
)

ELECTIONS_RE = re.compile(r"^Elections as of:", re.I)


def _status_for(*, grade: str | None, ctp: float, enrolled: bool) -> str:
    if enrolled:
        return "enrolled"
    if grade in PASSING_GRADES and ctp > 0:
        return "completed"
    if grade == "T" and ctp > 0:
        return "completed"
    return "in_progress"


def parse_course_line(line: str) -> dict[str, Any] | None:
    """Parse one PeopleSoft course row, or None if not a course."""
    m = COURSE_START_RE.match(line)
    if not m:
        return None
    subject, catalog = m.group(1), m.group(2)
    rest = line[m.end() :].strip()
    nums = NUM4_RE.search(rest)
    if not nums:
        return None
    hours = float(nums.group("hours"))
    ctp = float(nums.group("ctp"))
    mid = rest[: nums.start()].strip()
    grade = None
    title = mid
    gm = GRADE_RE.match(mid)
    if gm:
        title = gm.group("title").strip()
        grade = gm.group("grade")
    credits = ctp if ctp > 0 else (hours if hours > 0 else None)
    return {
        "course_code": f"{subject} {catalog}",
        "title": title or None,
        "credits": credits,
        "grade": grade,
        "hours": hours,
        "ctp": ctp,
    }


def parse_column_text(text: str) -> list[dict[str, Any]]:
    """Turn one column of transcript text into course dicts."""
    courses: list[dict[str, Any]] = []
    term: str | None = None
    enrolled = False
    for raw in (text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        tm = TERM_RE.match(line)
        if tm:
            term = f"{tm.group(1).title()} {tm.group(2)}"
            enrolled = False
            continue
        if ELECTIONS_RE.match(line):
            enrolled = True
            continue
        if SKIP_LINE_RE.match(line):
            continue
        if line.startswith("Transfer Test Credit") or line.startswith(
            "Transfer Course Credit"
        ):
            continue
        if line in {"Advanced Placement", "Undergraduate LSA"}:
            continue
        parsed = parse_course_line(line)
        if not parsed:
            continue
        status = _status_for(
            grade=parsed.get("grade"),
            ctp=float(parsed.get("ctp") or 0),
            enrolled=enrolled,
        )
        courses.append(
            {
                "course_code": parsed["course_code"],
                "title": parsed["title"],
                "credits": parsed["credits"],
                "term_completed": term,
                "grade": parsed.get("grade"),
                "status": status,
            }
        )
    return courses


def _prefer_status(existing: str, incoming: str) -> str:
    rank = {"completed": 3, "in_progress": 2, "enrolled": 1}
    return existing if rank.get(existing, 0) >= rank.get(incoming, 0) else incoming


def dedupe_courses(courses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per course_code; prefer completed over in-progress/enrolled."""
    by_code: dict[str, dict[str, Any]] = {}
    for row in courses:
        code = row["course_code"]
        prev = by_code.get(code)
        if not prev:
            by_code[code] = dict(row)
            continue
        winner_status = _prefer_status(prev["status"], row["status"])
        if winner_status == row["status"] and row["status"] != prev["status"]:
            by_code[code] = dict(row)
        elif row.get("credits") and not prev.get("credits"):
            prev["credits"] = row["credits"]
    return list(by_code.values())


def extract_column_texts(pdf_bytes: bytes) -> list[str]:
    columns: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            mid = page.width / 2.0
            left = page.crop((0, 0, mid, page.height))
            right = page.crop((mid, 0, page.width, page.height))
            columns.append(left.extract_text() or "")
            columns.append(right.extract_text() or "")
    return columns


def parse_transcript_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """Return { courses, counts } from unofficial transcript PDF bytes."""
    raw: list[dict[str, Any]] = []
    for col in extract_column_texts(pdf_bytes):
        raw.extend(parse_column_text(col))
    courses = dedupe_courses(raw)
    counts = {"completed": 0, "in_progress": 0, "enrolled": 0}
    for c in courses:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    return {"courses": courses, "counts": counts}


def parse_transcript_file(file: BinaryIO) -> dict[str, Any]:
    return parse_transcript_pdf(file.read())

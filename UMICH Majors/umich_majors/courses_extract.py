"""LLM-extract requirementGroups from requirements/<id>/ → Planner config/majors."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from umich_majors.config import PLANNER_MAJORS, REQUIREMENTS
from umich_majors.courses_normalize import build_major_config
from umich_majors.courses_prompts import courses_extract_system, courses_extract_user
from umich_majors.fetch import fetch_page
from umich_majors.llm import chat_json
from umich_majors.pipeline import load_listing
from umich_majors.requirements_fetch import find_major, major_dir
from umich_majors.requirements_supplements import load_supplements_llm_text
import re

# Schools with no reliable public requirements → course extract (skip in batch)
SKIP_SCHOOLS = {
    "School of Kinesiology",
    "School of Music, Theatre & Dance (SMTD)",
}

# Hand-curated majors already in the live guide — never overwrite / re-extract
PROTECTED_MAJOR_IDS = {
    "biology-health-and-society--majors-minors-html-general-biology-maj",
    "computer-science-bse--computer-science-eng",
    "computer-science-lsa",
    # Listing id for LSA CS (hand file is computer-science-lsa.json)
    "computer-science-bs--majors-minors-html-computer-science-maj",
    "data-science",
    "data-science--preview",
    "data-science-bs--majors-minors-html-data-science-maj",
    "industrial-and-operations-engineering--undergrad-research",
}

PROTECTED_DISPLAY_NAMES = {
    "biology, health, and society",
    "computer science (bse)",
    "computer science (lsa)",
    "computer science (bs)",
    "data science",
    "data science (bs)",
    "industrial and operations engineering",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_meta(mid: str) -> dict[str, Any] | None:
    path = major_dir(mid) / "meta.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _prefer_current_requirements(text: str, *, max_chars: int = 20_000) -> str:
    """
    LSA requirements pages often embed many historical Effective-term versions.
    Keep from the first Effective … block, capped so the LLM sees the newest first.
    Long course guides (Slides/PDFs) jump to the Degree Requirements body.
    """
    m = re.search(r"Effective\s+(?:Fall|Winter|Spring|Summer)\s+\d{4}", text, re.I)
    if m:
        start = m.start()
        chunk = text[start:]
        if len(chunk) > max_chars:
            chunk = chunk[:max_chars] + "\n\n[truncated older historical versions]"
        return chunk

    # Skip TOC / welcome / history in long dept course guides
    m2 = re.search(
        r"(?:^|\n)\s*Degree Requirements\b|(?:^|\n)\s*The IOE Curriculum\b|"
        r"(?:^|\n)\s*Core .+ Requirements\b|(?:^|\n)\s*Major Requirements\b",
        text,
        re.I,
    )
    if m2 and m2.start() > 400:
        text = text[m2.start() :]
    if len(text) > 45_000:
        return text[:45_000] + "\n\n[truncated]"
    return text


def _requirements_text(mid: str, meta: dict[str, Any]) -> tuple[str, str]:
    """
    Return (page_text, source_label).
    Prefer already-fetched LLM text; append course-list supplements when present.
    """
    d = major_dir(mid)
    main = ""
    source = ""
    for name in ("requirements_page.llm.txt", "requirements_page.txt"):
        p = d / name
        if p.exists() and p.stat().st_size > 80:
            raw = p.read_text(encoding="utf-8")
            main = _prefer_current_requirements(raw)
            source = str(p)
            break

    if not main:
        url = (
            meta.get("requirements_final_url") or meta.get("requirements_url") or ""
        ).strip()
        if not url:
            raise RuntimeError(
                f"{mid}: no requirements URL in meta.json and no cached page"
            )
        _fetched, llm = fetch_page(url)
        (d / "requirements_page.llm.txt").write_text(llm + "\n", encoding="utf-8")
        main = _prefer_current_requirements(llm)
        source = url

    supplements = load_supplements_llm_text(d)
    if supplements.strip():
        page = (
            main.rstrip()
            + "\n\n---\n"
            + "# Linked course lists (supplements)\n"
            + "Use these to fill requirement groups that point at an approved/"
            + "course list.\n\n"
            + supplements.strip()
        )
        return page, f"{source} + supplements"
    return main, source


def _is_protected(major: dict) -> bool:
    """Hand-curated live-guide majors — never re-extract or overwrite."""
    mid = (major.get("id") or "").strip()
    name = (major.get("name") or "").strip().lower()
    if mid in PROTECTED_MAJOR_IDS:
        return True
    if name in PROTECTED_DISPLAY_NAMES:
        return True
    return False


def extract_courses_one(
    major: dict,
    *,
    force: bool = False,
    max_tokens: int = 8000,
) -> dict[str, Any]:
    mid = major["id"]
    name = major.get("name") or mid
    out_path = PLANNER_MAJORS / f"{mid}.json"

    row: dict[str, Any] = {
        "id": mid,
        "name": name,
        "status": "pending",
        "message": None,
        "output_path": str(out_path),
        "groups": 0,
        "courses": 0,
        "source": None,
        "extracted_at": _now(),
    }

    school = (major.get("school_college") or "").strip()
    if school in SKIP_SCHOOLS:
        row["status"] = "skipped"
        row["message"] = f"school excluded from extract: {school}"
        return row

    if _is_protected(major):
        row["status"] = "skipped"
        row["message"] = "protected hand-curated major (already in live guide)"
        return row

    meta = _load_meta(mid)
    if not meta:
        row["status"] = "needs_requirements"
        row["message"] = (
            "no requirements/<id>/meta.json — run: "
            f'python -m umich_majors.cli requirements --id "{name}"'
        )
        return row

    if meta.get("status") not in ("fetched",):
        row["status"] = "needs_requirements"
        row["message"] = f"requirements status is {meta.get('status')!r}, expected fetched"
        return row

    if out_path.exists() and not force:
        row["status"] = "skipped"
        row["message"] = f"exists (pass --force to overwrite): {out_path}"
        return row

    # Never allow --force to clobber protected majors
    if force and mid in PROTECTED_MAJOR_IDS:
        row["status"] = "skipped"
        row["message"] = "refusing --force on protected major"
        return row

    try:
        page_text, source = _requirements_text(mid, meta)
    except Exception as e:
        row["status"] = "failed"
        row["message"] = f"could not load requirements text: {e}"
        return row

    row["source"] = source

    try:
        llm_result = chat_json(
            courses_extract_system(),
            courses_extract_user(name, major.get("school_college") or meta.get("school_college"), page_text),
            max_tokens=max_tokens,
        )
    except Exception as e:
        row["status"] = "failed"
        row["message"] = f"LLM call failed: {e}"
        return row

    if not isinstance(llm_result, dict):
        row["status"] = "failed"
        row["message"] = "LLM returned no JSON object"
        # Keep raw for debugging if present in artifacts
        return row

    config = build_major_config(
        major_id=mid,
        display_name=name,
        llm_result=llm_result,
    )
    groups = config["requirementGroups"]
    open_groups = config.get("openGroups") or {}
    n_courses = sum(len(v) for v in groups.values())
    n_open = len(open_groups)
    row["groups"] = len(groups)
    row["courses"] = n_courses
    row["open_groups"] = n_open

    if n_courses == 0 and n_open == 0:
        row["status"] = "needs_review"
        row["message"] = "LLM returned zero course codes"
        (major_dir(mid) / "courses_extract.raw.json").write_text(
            json.dumps(llm_result, indent=2) + "\n", encoding="utf-8"
        )
        return row

    PLANNER_MAJORS.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (major_dir(mid) / "courses_extract.raw.json").write_text(
        json.dumps(llm_result, indent=2) + "\n", encoding="utf-8"
    )
    (major_dir(mid) / "courses_extract.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )

    row["status"] = "extracted"
    row["message"] = (
        f"wrote {len(groups)} groups / {n_courses} explicit courses"
        f"{f' / {n_open} openGroups' if n_open else ''} → {out_path.name}"
    )
    return row


def extract_courses_batch(
    *,
    limit: int | None = None,
    offset: int = 0,
    force: bool = False,
    only_fetched: bool = True,
) -> Path:
    majors = load_listing()
    majors = [
        m
        for m in majors
        if (m.get("school_college") or "").strip() not in SKIP_SCHOOLS
        and not _is_protected(m)
    ]
    if only_fetched:
        fetched_ids = set()
        for meta_path in REQUIREMENTS.glob("*/meta.json"):
            try:
                m = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if m.get("status") == "fetched":
                fetched_ids.add(m["id"])
        majors = [m for m in majors if m["id"] in fetched_ids]

    slice_ = majors[offset : (offset + limit) if limit is not None else None]
    REQUIREMENTS.mkdir(parents=True, exist_ok=True)
    index_path = REQUIREMENTS / "courses_extract_index.jsonl"

    with index_path.open("a", encoding="utf-8") as out:
        for i, major in enumerate(slice_, start=1):
            print(f"[{i}/{len(slice_)}] {major['name']} ({major.get('school_college')})")
            row = extract_courses_one(major, force=force)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  → {row['status']}: {row.get('message')}")
            # Pace LLM calls to reduce 429s (skipped rows are instant)
            if row["status"] not in ("skipped",):
                time.sleep(20)

    return index_path
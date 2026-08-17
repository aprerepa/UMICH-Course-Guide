"""LLM-extract groupRules from requirements/<id>/ → Planner/config/rules/<id>.json."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from umich_majors.config import PLANNER_MAJORS, PLANNER_RULES, REQUIREMENTS
from umich_majors.courses_extract import (
    SKIP_MAJOR_IDS,
    SKIP_SCHOOLS,
    _load_meta,
    _requirements_text,
)
from umich_majors.llm import chat_json
from umich_majors.pipeline import load_listing
from umich_majors.requirements_fetch import major_dir
from umich_majors.rules_normalize import build_rules_config
from umich_majors.rules_prompts import rules_extract_system, rules_extract_user


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _known_groups(mid: str) -> list[str]:
    """Prefer group names from existing course config so rules keys align."""
    path = PLANNER_MAJORS / f"{mid}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    names: list[str] = []
    for key in ("requirementGroups", "openGroups"):
        groups = data.get(key) or {}
        if isinstance(groups, dict):
            for name in groups:
                if isinstance(name, str) and name.strip() and name not in names:
                    names.append(name.strip())
    return names


def extract_rules_one(
    major: dict,
    *,
    force: bool = False,
    max_tokens: int = 4000,
) -> dict[str, Any]:
    mid = major["id"]
    name = major.get("name") or mid
    out_path = PLANNER_RULES / f"{mid}.json"

    row: dict[str, Any] = {
        "id": mid,
        "name": name,
        "status": "pending",
        "message": None,
        "output_path": str(out_path),
        "groups": 0,
        "source": None,
        "extracted_at": _now(),
    }

    school = (major.get("school_college") or "").strip()
    if school in SKIP_SCHOOLS:
        row["status"] = "skipped"
        row["message"] = f"school excluded from extract: {school}"
        return row

    if mid in SKIP_MAJOR_IDS:
        row["status"] = "skipped"
        row["message"] = "excluded non-undergrad / graduate listing entry"
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

    try:
        page_text, source = _requirements_text(mid, meta)
    except Exception as e:
        row["status"] = "failed"
        row["message"] = f"could not load requirements text: {e}"
        return row

    row["source"] = source
    known = _known_groups(mid)

    try:
        llm_result = chat_json(
            rules_extract_system(),
            rules_extract_user(
                name,
                school or None,
                page_text,
                known_groups=known or None,
            ),
            max_tokens=max_tokens,
            temperature=0,
        )
    except Exception as e:
        row["status"] = "failed"
        row["message"] = f"LLM call failed: {e}"
        return row

    config = build_rules_config(
        llm_result if isinstance(llm_result, dict) else {},
        major_id=mid,
        display_name=name,
        known_groups=known or None,
    )
    n_groups = len(config.get("groupRules") or {})
    if n_groups == 0:
        row["status"] = "needs_review"
        row["message"] = "LLM returned zero groupRules"
        # still write raw for debugging
        out_dir = major_dir(mid)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "rules_extract.raw.json").write_text(
            json.dumps(llm_result, indent=2) + "\n", encoding="utf-8"
        )
        return row

    PLANNER_RULES.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    out_dir = major_dir(mid)
    (out_dir / "rules_extract.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "rules_extract.raw.json").write_text(
        json.dumps(llm_result, indent=2) + "\n", encoding="utf-8"
    )

    row["status"] = "extracted"
    row["groups"] = n_groups
    row["message"] = f"wrote {n_groups} groupRules → {out_path.name}"
    return row


def extract_rules_batch(
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
        and m.get("id") not in SKIP_MAJOR_IDS
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
    PLANNER_RULES.mkdir(parents=True, exist_ok=True)
    index_path = REQUIREMENTS / "rules_extract_index.jsonl"

    with index_path.open("a", encoding="utf-8") as out:
        for i, major in enumerate(slice_, start=1):
            print(f"[{i}/{len(slice_)}] {major['name']} ({major.get('school_college')})")
            row = extract_rules_one(major, force=force)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"  → {row['status']}: {row.get('message')}")
            if row["status"] not in ("skipped",):
                time.sleep(20)

    return index_path

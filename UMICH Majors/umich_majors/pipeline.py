"""End-to-end: list majors → fetch each program page → optional LLM extract."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from umich_majors.config import MAJORS_LISTING_URL, OUTPUT, RUNS
from umich_majors.extract import llm_extract_major
from umich_majors.fetch import fetch_page, html_to_text
from umich_majors.listing import parse_majors


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_listing(*, force_browser: bool = False) -> tuple[list[dict], dict]:
    """Fetch + parse the Admissions majors table. Writes listing artifacts."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fetched, _ = fetch_page(
        MAJORS_LISTING_URL,
        force_browser=force_browser,
        min_chars=500,
    )
    majors = parse_majors(fetched.html, fetched.final_url)
    # If HTTP missed the JS table, retry browser once.
    if len(majors) < 50 and fetched.mode == "http":
        fetched, _ = fetch_page(MAJORS_LISTING_URL, force_browser=True)
        majors = parse_majors(fetched.html, fetched.final_url)

    meta = {
        "source_url": MAJORS_LISTING_URL,
        "final_url": fetched.final_url,
        "status_code": fetched.status_code,
        "fetch_mode": fetched.mode,
        "fetched_at": _now(),
        "major_count": len(majors),
    }
    (OUTPUT / "page.html").write_text(fetched.html, encoding="utf-8")
    (OUTPUT / "page.txt").write_text(html_to_text(fetched.html) + "\n", encoding="utf-8")
    (OUTPUT / "fetch_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    jsonl_path = OUTPUT / "majors.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as out:
        for m in majors:
            out.write(json.dumps(m, ensure_ascii=False) + "\n")

    with (OUTPUT / "majors.csv").open("w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(
            out,
            fieldnames=["id", "name", "school_college", "url", "is_submajor"],
        )
        w.writeheader()
        w.writerows(majors)

    (OUTPUT / "majors.json").write_text(
        json.dumps({"fetched_at": meta["fetched_at"], "source_url": MAJORS_LISTING_URL, "majors": majors}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return majors, meta


def load_listing() -> list[dict]:
    path = OUTPUT / "majors.jsonl"
    if not path.exists():
        majors, _ = fetch_listing()
        return majors
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def enrich_one(major: dict, *, skip_llm: bool = False) -> dict[str, Any]:
    """Fetch one program URL; optionally LLM-extract. Artifacts under runs/<id>/."""
    mid = major["id"]
    run_dir = RUNS / mid
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "listing.json").write_text(json.dumps(major, indent=2) + "\n", encoding="utf-8")

    row: dict[str, Any] = {
        **major,
        "status": "pending",
        "message": None,
        "source_url": major.get("url"),
        "final_url": None,
        "fetch_mode": None,
        "extracted": None,
        "enriched_at": _now(),
    }

    try:
        fetched, text = fetch_page(major["url"])
    except Exception as e:
        row["status"] = "failed"
        row["message"] = f"fetch failed: {e}"
        (run_dir / "enrich_result.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        return row

    (run_dir / "page.html").write_text(fetched.html, encoding="utf-8")
    (run_dir / "page.txt").write_text(text + "\n", encoding="utf-8")
    row["final_url"] = fetched.final_url
    row["fetch_mode"] = fetched.mode
    row["source_url"] = fetched.final_url

    if skip_llm:
        row["status"] = "fetched"
        row["message"] = "page fetched; LLM skipped"
        (run_dir / "enrich_result.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        return row

    try:
        extracted = llm_extract_major(major["name"], major.get("school_college"), text)
    except Exception as e:
        row["status"] = "needs_review"
        row["message"] = f"LLM extract failed: {e}"
        (run_dir / "enrich_result.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        return row

    (run_dir / "llm_extract.json").write_text(
        json.dumps(extracted, indent=2) + "\n" if extracted else "null\n",
        encoding="utf-8",
    )
    row["extracted"] = extracted

    if not extracted:
        row["status"] = "needs_review"
        row["message"] = "LLM returned unparseable JSON"
    elif extracted.get("is_correct_program") is False:
        row["status"] = "needs_review"
        row["message"] = "LLM says page is not this program"
    else:
        row["status"] = "success"
        row["message"] = "OK"

    (run_dir / "enrich_result.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return row


def enrich_batch(
    *,
    limit: int | None = None,
    offset: int = 0,
    skip_llm: bool = False,
    refresh_listing: bool = False,
) -> Path:
    if refresh_listing or not (OUTPUT / "majors.jsonl").exists():
        majors, _ = fetch_listing()
    else:
        majors = load_listing()

    slice_ = majors[offset : (offset + limit) if limit is not None else None]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT / "enrichment.jsonl"

    # Append-friendly: rewrite full slice results into a batch file + merge later if needed.
    with out_path.open("a", encoding="utf-8") as out:
        for i, major in enumerate(slice_, start=1):
            print(f"[{i}/{len(slice_)}] {major['name']}")
            row = enrich_one(major, skip_llm=skip_llm)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  → {row['status']}: {row.get('message')}")

    return out_path

"""CLI for UMICH Majors (standalone — no hcp_enrichment / Tokenplex)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python -m umich_majors.cli` from "UMICH Majors/" or via this file.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def cmd_list(args: argparse.Namespace) -> int:
    from umich_majors.pipeline import fetch_listing

    majors, meta = fetch_listing(force_browser=args.browser)
    print(json.dumps(meta, indent=2))
    print(f"wrote {len(majors)} majors → output/majors.jsonl")
    if majors:
        print(f"sample: {majors[0]['name']} | {majors[0].get('school_college')}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    from umich_majors.pipeline import enrich_one, load_listing

    majors = load_listing()
    match = next((m for m in majors if m["id"] == args.id or m["name"].lower() == args.id.lower()), None)
    if not match and args.url:
        match = {
            "id": "manual",
            "name": args.name or "Unknown",
            "school_college": None,
            "url": args.url,
            "is_submajor": False,
        }
    if not match:
        print(f"No major matching id/name: {args.id}", file=sys.stderr)
        return 1
    row = enrich_one(match, skip_llm=True)
    print(json.dumps({k: row[k] for k in ("id", "name", "status", "final_url", "fetch_mode", "message")}, indent=2))
    return 0 if row["status"] in ("fetched", "success") else 1


def cmd_enrich(args: argparse.Namespace) -> int:
    from umich_majors.pipeline import enrich_batch, enrich_one, load_listing

    if args.id:
        majors = load_listing()
        match = next(
            (m for m in majors if m["id"] == args.id or m["name"].lower() == args.id.lower()),
            None,
        )
        if not match:
            print(f"No major matching id/name: {args.id}", file=sys.stderr)
            return 1
        row = enrich_one(match, skip_llm=args.skip_llm)
        print(json.dumps(row, indent=2)[:2000])
        return 0 if row["status"] == "success" else 1

    path = enrich_batch(
        limit=args.limit,
        offset=args.offset,
        skip_llm=args.skip_llm,
        refresh_listing=args.refresh_listing,
    )
    print(f"wrote → {path}")
    return 0


def cmd_requirements(args: argparse.Namespace) -> int:
    """Program page → hop to Requirements link → save LLM-ready text under requirements/<id>/."""
    from umich_majors.pipeline import load_listing
    from umich_majors.requirements_fetch import (
        fetch_requirements_batch,
        fetch_requirements_one,
        find_major,
        major_dir,
    )

    if args.id:
        majors = load_listing()
        match = find_major(majors, args.id)
        if not match:
            print(f"No major matching id/name: {args.id}", file=sys.stderr)
            return 1
        row = fetch_requirements_one(match, force_browser=args.browser)
        print(json.dumps(row, indent=2))
        print(f"artifacts → {major_dir(match['id'])}")
        return 0 if row["status"] in ("fetched", "discontinued") else 1

    path = fetch_requirements_batch(
        limit=args.limit,
        offset=args.offset,
        force_browser=args.browser,
    )
    print(f"index → {path}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """LLM: requirements page → requirementGroups → Planner/config/majors/<id>.json."""
    from umich_majors.courses_extract import extract_courses_batch, extract_courses_one
    from umich_majors.pipeline import load_listing
    from umich_majors.requirements_fetch import find_major

    if args.id:
        majors = load_listing()
        match = find_major(majors, args.id)
        if not match:
            print(f"No major matching id/name: {args.id}", file=sys.stderr)
            return 1
        row = extract_courses_one(match, force=args.force)
        print(json.dumps(row, indent=2))
        return 0 if row["status"] in ("extracted", "skipped") else 1

    path = extract_courses_batch(
        limit=args.limit,
        offset=args.offset,
        force=args.force,
    )
    print(f"index → {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="UMich majors fetch / enrich (personal LLM keys)")
    sub = p.add_subparsers(dest="cmd", required=True)

    lst = sub.add_parser("list", help="Fetch Admissions majors table → output/majors.*")
    lst.add_argument("--browser", action="store_true", help="Force Playwright for listing")
    lst.set_defaults(func=cmd_list)

    fet = sub.add_parser("fetch", help="Fetch one major detail page (no LLM)")
    fet.add_argument("--id", default="", help="Major id or exact name from majors.jsonl")
    fet.add_argument("--url", default="", help="Or pass a program URL directly")
    fet.add_argument("--name", default="", help="Display name when using --url")
    fet.set_defaults(func=cmd_fetch)

    en = sub.add_parser("enrich", help="Fetch + LLM extract (needs UMICH_LLM_* in .env)")
    en.add_argument("--id", default="", help="Single major id/name")
    en.add_argument("--limit", type=int, default=None)
    en.add_argument("--offset", type=int, default=0)
    en.add_argument("--skip-llm", action="store_true", help="Fetch only")
    en.add_argument("--refresh-listing", action="store_true")
    en.set_defaults(func=cmd_enrich)

    req = sub.add_parser(
        "requirements",
        help="Hop from program url → Requirements page; save under requirements/<id>/",
    )
    req.add_argument("--id", default="", help="Single major id or exact name")
    req.add_argument("--limit", type=int, default=None, help="Batch: first N majors from listing")
    req.add_argument("--offset", type=int, default=0)
    req.add_argument("--browser", action="store_true", help="Force Playwright for fetches")
    req.set_defaults(func=cmd_requirements)

    ex = sub.add_parser(
        "extract",
        help="LLM extract subcategory→course codes → Planner/config/majors/<id>.json",
    )
    ex.add_argument("--id", default="", help="Single major id or exact name")
    ex.add_argument("--limit", type=int, default=None, help="Batch: first N fetched majors")
    ex.add_argument("--offset", type=int, default=0)
    ex.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Planner/config/majors/<id>.json",
    )
    ex.set_defaults(func=cmd_extract)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

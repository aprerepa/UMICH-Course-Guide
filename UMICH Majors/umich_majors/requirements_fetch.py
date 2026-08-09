"""Fetch program page → hop to requirements → save LLM-ready artifacts per major.

LSA path (from Admissions majors listing):
  A) Listing URL is already the requirements / curriculum page → use it.
  B) Listing URL is lsa majors-minors.html#… → expand row → follow REQUIREMENTS.

Non-LSA: find Requirements links, or hop hubs (Art & Design, teacher ed, CoE, etc.).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from umich_majors.config import REQUIREMENTS
from umich_majors.fetch import fetch_page, html_to_text
from umich_majors.lsa_detail import (
    LSA_MAJORS_MINORS,
    fetch_lsa_program_detail_html,
    is_lsa_majors_minors_url,
    lsa_fragment_id,
)
from umich_majors.lsa_math_requirements import (
    extract_latest_historical_program,
    should_trim_lsa_historical,
)
from umich_majors.pipeline import load_listing
from umich_majors.requirements_links import (
    find_degree_program_links,
    find_requirements_url,
    find_requirements_url_in_detail,
    is_google_docs_or_sheets_url,
    page_looks_like_majors_directory,
    page_looks_like_requirements,
    should_follow_nested_requirements,
)
from umich_majors.requirements_supplements import fetch_supplements_for_major


def _is_lsa_school(major: dict) -> bool:
    school = (major.get("school_college") or "").lower()
    return "literature, science" in school or school.startswith("lsa") or "(lsa)" in school


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def major_dir(major_id: str) -> Path:
    return REQUIREMENTS / major_id


def fetch_requirements_one(major: dict, *, force_browser: bool = False) -> dict[str, Any]:
    """
    1) Fetch majors.json `url` (Admissions program / requirements URL)
    2) Resolve requirements page (LSA expand, self-page, Requirements link, or hub)
    3) Write under requirements/<id>/
    """
    mid = major["id"]
    out = major_dir(mid)
    out.mkdir(parents=True, exist_ok=True)

    (out / "listing.json").write_text(json.dumps(major, indent=2) + "\n", encoding="utf-8")

    row: dict[str, Any] = {
        "id": mid,
        "name": major.get("name"),
        "school_college": major.get("school_college"),
        "program_url": major.get("url"),
        "status": "pending",
        "message": None,
        "program_final_url": None,
        "program_fetch_mode": None,
        "requirements_url": None,
        "requirements_link_text": None,
        "requirements_link_score": None,
        "requirements_link_strategy": None,
        "requirements_final_url": None,
        "requirements_fetch_mode": None,
        "fetched_at": _now(),
    }

    program_url = (major.get("url") or "").strip()
    if not program_url:
        row["status"] = "failed"
        row["message"] = "listing has no url"
        (out / "meta.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        return row

    try:
        program, program_llm = fetch_page(program_url, force_browser=force_browser)
    except Exception as e:
        row["status"] = "failed"
        row["message"] = f"program page fetch failed: {e}"
        (out / "meta.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        return row

    (out / "program_page.html").write_text(program.html, encoding="utf-8")
    (out / "program_page.txt").write_text(html_to_text(program.html) + "\n", encoding="utf-8")
    (out / "program_page.llm.txt").write_text(program_llm + "\n", encoding="utf-8")
    row["program_final_url"] = program.final_url
    row["program_fetch_mode"] = program.mode

    lookup_base = program_url if urlparse(program_url).fragment else program.final_url
    link = None
    major_name = major.get("name") or ""

    def _set_link(info: dict) -> None:
        nonlocal link
        link = info
        row["requirements_url"] = info["url"]
        row["requirements_link_text"] = info["link_text"]
        row["requirements_link_score"] = info["score"]
        row["requirements_link_strategy"] = info["strategy"]
        (out / "requirements_url.txt").write_text(info["url"] + "\n", encoding="utf-8")

    def _save_requirements_artifacts(
        html: str,
        llm: str,
        *,
        final_url: str | None,
        fetch_mode: str | None,
        message: str,
    ) -> dict[str, Any]:
        (out / "requirements_page.html").write_text(html, encoding="utf-8")
        (out / "requirements_page.txt").write_text(html_to_text(html) + "\n", encoding="utf-8")
        (out / "requirements_page.llm.txt").write_text(llm + "\n", encoding="utf-8")
        row["requirements_final_url"] = final_url
        row["requirements_fetch_mode"] = fetch_mode
        row["status"] = "fetched"
        row["message"] = message
        # Discover course-list links from the untrimmed HTML (has real <a href>s).
        source_html_for_supplements = html
        _maybe_trim_shared_lsa_historical_page(html, final_url or "")
        _fetch_course_list_supplements(
            source_html_for_supplements,
            base_url=final_url or row.get("requirements_url") or "",
        )
        (out / "meta.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        return row

    def _fetch_course_list_supplements(html: str, *, base_url: str) -> None:
        """Fetch approved/course-list links; does not change requirements_url."""
        try:
            supp_rows = fetch_supplements_for_major(
                out,
                html,
                base_url=base_url,
                major_name=major_name or None,
                is_submajor=bool(major.get("is_submajor")),
                primary_url=row.get("requirements_url") or base_url,
                force_browser=force_browser,
            )
        except Exception as e:
            row["supplements_count"] = 0
            row["supplements_error"] = str(e)
            return
        ok = [r for r in supp_rows if r.get("status") == "fetched"]
        row["supplements_count"] = len(ok)
        row["supplements"] = [
            {
                "id": r["id"],
                "url": r["url"],
                "link_text": r["link_text"],
                "status": r["status"],
                "chars": r.get("chars"),
            }
            for r in supp_rows
        ]
        if ok:
            labels = ", ".join(r["link_text"] for r in ok[:3])
            extra = f" (+{len(ok)} course-list supplement{'s' if len(ok) != 1 else ''}: {labels})"
            row["message"] = (row.get("message") or "") + extra

    def _maybe_trim_shared_lsa_historical_page(html: str, page_url: str) -> None:
        """
        Shared LSA majors-minors pages embed every term/subplan in accordions
        (math submajors, International Studies subplans, etc.). Keep only the
        latest-term block for this major.
        """
        if not should_trim_lsa_historical(major, page_url):
            return
        extracted = extract_latest_historical_program(
            html,
            major_name=major_name,
            is_submajor=bool(major.get("is_submajor")),
        )
        if not extracted:
            return
        (out / "requirements_page.full.html").write_text(html, encoding="utf-8")
        (out / "requirements_page.html").write_text(extracted["html"] + "\n", encoding="utf-8")
        (out / "requirements_page.txt").write_text(extracted["text"] + "\n", encoding="utf-8")
        (out / "requirements_page.llm.txt").write_text(
            extracted["llm_text"] + "\n", encoding="utf-8"
        )
        row["lsa_requirements_title"] = extracted["title"]
        row["lsa_requirements_term"] = extracted["term_start"]
        # Keep old math_* keys for compatibility
        row["math_requirements_title"] = extracted["title"]
        row["math_requirements_term"] = extracted["term_start"]
        if extracted.get("term_end"):
            row["lsa_requirements_term_end"] = extracted["term_end"]
            row["math_requirements_term_end"] = extracted["term_end"]
        strategy = row.get("requirements_link_strategy") or ""
        row["requirements_link_strategy"] = (
            f"{strategy}+{extracted['strategy']}" if strategy else extracted["strategy"]
        )
        row["message"] = (
            f"requirements page ready for LLM "
            f"({extracted['title']}, {extracted['term_start']}"
            f"{('–' + extracted['term_end']) if extracted.get('term_end') else '+'})"
        )

    def _finish_with_requirements_page(
        url: str,
        *,
        force: bool = force_browser,
        allow_doc_hop: bool = True,
    ) -> dict[str, Any]:
        try:
            req, req_llm = fetch_page(url, force_browser=force)
        except Exception as e:
            row["status"] = "needs_review"
            row["message"] = f"requirements link found but fetch failed: {e}"
            (out / "meta.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
            return row

        # Curriculum landings often link onward (BME Google Doc, Ross Curriculum by Year).
        final = req.final_url or url
        if allow_doc_hop:
            nested = find_requirements_url(
                req.html, final, major_name=major_name
            )
            if nested and should_follow_nested_requirements(
                final, nested, current_html=req.html, major_name=major_name
            ):
                prev_text = row.get("requirements_link_text") or ""
                hop_kind = (
                    "google_doc"
                    if is_google_docs_or_sheets_url(nested["url"])
                    else "nested"
                )
                _set_link(
                    {
                        **nested,
                        "strategy": (
                            f"{row.get('requirements_link_strategy') or 'page'}"
                            f"→{hop_kind}"
                        ),
                        "link_text": (
                            f"{prev_text} → {nested['link_text']}"
                            if prev_text
                            else nested["link_text"]
                        ),
                    }
                )
                # Google Docs / heavy JS curriculum pages need Playwright
                return _finish_with_requirements_page(
                    nested["url"],
                    force=True,
                    allow_doc_hop=False,
                )

        return _save_requirements_artifacts(
            req.html,
            req_llm,
            final_url=req.final_url,
            fetch_mode=req.mode,
            message="requirements page ready for LLM",
        )

    def _try_lsa_detail(
        frag: str | None,
        *,
        required: bool,
        strategy_prefix: str = "lsa_detail",
    ) -> bool:
        """Expand LSA majors-minors row; set REQUIREMENTS link. Return True if fully handled."""
        try:
            row_id, detail_html = fetch_lsa_program_detail_html(
                frag,
                major_name=major_name or None,
            )
        except Exception as e:
            msg = str(e)
            if "no matching majors-minors table row" in msg:
                row["status"] = "discontinued"
                row["message"] = (
                    f"major no longer listed on LSA majors-minors: {msg}"
                )
                (out / "meta.json").write_text(
                    json.dumps(row, indent=2) + "\n", encoding="utf-8"
                )
                return True
            if required:
                row["status"] = "needs_review"
                row["message"] = f"LSA program detail expand failed: {e}"
                (out / "meta.json").write_text(
                    json.dumps(row, indent=2) + "\n", encoding="utf-8"
                )
                return True
            return False

        row["lsa_resolved_row_id"] = row_id
        (out / "program_detail.html").write_text(detail_html, encoding="utf-8")
        (out / "program_detail.txt").write_text(
            html_to_text(detail_html) + "\n", encoding="utf-8"
        )
        found = find_requirements_url_in_detail(detail_html, LSA_MAJORS_MINORS)
        if not found:
            if required:
                row["status"] = "needs_review"
                row["message"] = (
                    "LSA program detail loaded but no REQUIREMENTS link found"
                )
                (out / "meta.json").write_text(
                    json.dumps(row, indent=2) + "\n", encoding="utf-8"
                )
                return True
            return False
        _set_link(
            {
                **found,
                "strategy": f"{strategy_prefix}:{found['strategy']}",
            }
        )
        return False

    # --- LSA majors-minors.html#fragment → REQUIREMENTS ---
    if is_lsa_majors_minors_url(program_url):
        handled = _try_lsa_detail(
            lsa_fragment_id(program_url),
            required=True,
            strategy_prefix="lsa_listing",
        )
        if handled:
            return row

    # --- Admissions already linked the requirements page (e.g. Pure Math / EE major) ---
    if not link and page_looks_like_requirements(program.html, program_url):
        _set_link(
            {
                "url": program.final_url or program_url,
                "link_text": "(program page is requirements)",
                "score": 200,
                "strategy": "program_is_requirements",
            }
        )
        # Still allow one more hop (e.g. EE → Program Guide Google Doc)
        return _finish_with_requirements_page(
            program.final_url or program_url,
            force=force_browser,
            allow_doc_hop=True,
        )

    # --- Requirements / Degree Requirements link on the program page ---
    if not link:
        found = find_requirements_url(
            program.html,
            lookup_base,
            major_name=major_name,
        )
        if found:
            _set_link(found)

    # --- Hub pages (Art & Design / teacher ed / MSE / WGS / CoE Explore) ---
    if not link:
        programs = find_degree_program_links(
            program.html, lookup_base, major_name=major_name
        )
        if programs:
            hop_labels: list[str] = []
            hub = program
            hub_llm = program_llm
            _score, prog_url, prog_text = programs[0]
            hop_labels.append(prog_text)

            for hop_i in range(2):
                (out / f"hub_program_url{'' if hop_i == 0 else hop_i}.txt").write_text(
                    prog_url + "\n", encoding="utf-8"
                )
                try:
                    hub, hub_llm = fetch_page(prog_url, force_browser=force_browser)
                except Exception as e:
                    row["status"] = "needs_review"
                    row["message"] = f"degree program hub hop failed: {e}"
                    (out / "meta.json").write_text(
                        json.dumps(row, indent=2) + "\n", encoding="utf-8"
                    )
                    return row
                (out / f"hub_program_page{'' if hop_i == 0 else hop_i}.html").write_text(
                    hub.html, encoding="utf-8"
                )
                (out / f"hub_program_page{'' if hop_i == 0 else hop_i}.llm.txt").write_text(
                    hub_llm + "\n", encoding="utf-8"
                )

                if page_looks_like_majors_directory(hub.html, hub.final_url or prog_url):
                    nested_progs = find_degree_program_links(
                        hub.html, hub.final_url or prog_url, major_name=major_name
                    )
                    if nested_progs:
                        _score, prog_url, prog_text = nested_progs[0]
                        hop_labels.append(prog_text)
                        continue
                break

            hop_label = " → ".join(hop_labels)
            nested = find_requirements_url(
                hub.html, hub.final_url, major_name=major_name
            )
            hub_is_reqs = page_looks_like_requirements(
                hub.html, hub.final_url or prog_url
            )

            if nested and should_follow_nested_requirements(
                hub.final_url or prog_url,
                nested,
                current_html=hub.html,
                major_name=major_name,
            ):
                _set_link(
                    {
                        **nested,
                        "strategy": f"hub:{hop_label}→{nested['strategy']}",
                        "link_text": f"{hop_label} → {nested['link_text']}",
                    }
                )
            elif hub_is_reqs:
                _set_link(
                    {
                        "url": hub.final_url or prog_url,
                        "link_text": hop_label,
                        "score": _score,
                        "strategy": "hub_program_is_requirements",
                    }
                )
                return _finish_with_requirements_page(
                    hub.final_url or prog_url,
                    force=force_browser,
                    allow_doc_hop=True,
                )
            elif nested:
                _set_link(
                    {
                        **nested,
                        "strategy": f"hub:{hop_label}→{nested['strategy']}",
                        "link_text": f"{hop_label} → {nested['link_text']}",
                    }
                )
            else:
                _set_link(
                    {
                        "url": hub.final_url or prog_url,
                        "link_text": hop_label,
                        "score": _score,
                        "strategy": "hub_program_page",
                    }
                )
                return _save_requirements_artifacts(
                    hub.html,
                    hub_llm,
                    final_url=hub.final_url,
                    fetch_mode=hub.mode,
                    message="degree program page saved (no nested requirements link)",
                )

    # Last resort for LSA dept landings: try majors-minors by name.
    if not link and _is_lsa_school(major):
        handled = _try_lsa_detail(
            None,
            required=False,
            strategy_prefix="lsa_fallback",
        )
        if handled:
            return row

    if not link:
        row["status"] = "needs_review"
        row["message"] = "no requirements link found on program page"
        (out / "meta.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        return row

    return _finish_with_requirements_page(link["url"])


def fetch_requirements_batch(
    *,
    limit: int | None = None,
    offset: int = 0,
    force_browser: bool = False,
) -> Path:
    majors = load_listing()
    slice_ = majors[offset : (offset + limit) if limit is not None else None]
    REQUIREMENTS.mkdir(parents=True, exist_ok=True)
    index_path = REQUIREMENTS / "index.jsonl"

    with index_path.open("a", encoding="utf-8") as out:
        for i, major in enumerate(slice_, start=1):
            print(f"[{i}/{len(slice_)}] {major['name']}")
            row = fetch_requirements_one(major, force_browser=force_browser)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  → {row['status']}: {row.get('message')}")
            if row.get("requirements_url"):
                print(f"     {row['requirements_url']}")

    return index_path


def find_major(majors: list[dict], key: str) -> dict | None:
    key_l = key.lower().strip()
    return next(
        (m for m in majors if m["id"] == key or m["name"].lower() == key_l),
        None,
    )

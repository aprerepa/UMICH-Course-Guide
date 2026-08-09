"""Expand LSA majors-minors.html rows to load AJAX program detail (REQUIREMENTS link)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from umich_majors.fetch import USER_AGENT

LSA_MAJORS_MINORS = "https://lsa.umich.edu/lsa/academics/majors-minors.html"


def is_lsa_majors_minors_url(url: str) -> bool:
    p = urlparse(url)
    return "lsa.umich.edu" in p.netloc.lower() and "majors-minors.html" in p.path


def lsa_fragment_id(url: str) -> str | None:
    frag = urlparse(url).fragment.strip()
    return frag or None


def _normalize_major_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\(.*?\)", "", name)  # drop parentheticals
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    return name


def resolve_lsa_row_id(
    page,
    fragment_id: str | None,
    *,
    major_name: str | None = None,
) -> str:
    """
    Resolve the DOM id of the majors-minors row.

    Admissions listing hashes are sometimes wrong (e.g. Chemistry →
    #chemical_science_bschem-maj). Fall back to matching the major name
    against row link text (prefer '(Major)' rows).
    """
    if fragment_id and page.locator(f"#{fragment_id}").count() > 0:
        return fragment_id

    if not major_name:
        if fragment_id:
            raise RuntimeError(f"LSA row #{fragment_id} not found on majors-minors page")
        raise RuntimeError("No LSA fragment id or major name to resolve row")

    target = _normalize_major_name(major_name)
    rows = page.locator("tr.has-program-detail")
    n = rows.count()
    best: tuple[int, str] | None = None
    for i in range(n):
        row = rows.nth(i)
        rid = row.get_attribute("id") or ""
        text = (row.inner_text() or "").strip()
        norm = _normalize_major_name(text.split("\n")[0] if text else "")
        # Prefer exact / prefix match on the display name
        score = 0
        if norm == target or norm.startswith(target + " "):
            score = 100
        elif target and target in norm:
            score = 60
        else:
            continue
        if re.search(r"\(\s*major\s*\)", text, re.I):
            score += 30
        if re.search(r"\(\s*minor\s*\)", text, re.I):
            score -= 40
        if best is None or score > best[0]:
            best = (score, rid)

    if not best or not best[1]:
        hint = f"#{fragment_id}" if fragment_id else "(no fragment)"
        raise RuntimeError(
            f"LSA row not found for major {major_name!r} (tried {hint}); "
            "no matching majors-minors table row"
        )
    return best[1]


def fetch_lsa_program_detail_html(
    fragment_id: str | None,
    *,
    major_name: str | None = None,
    timeout_ms: int = 60_000,
) -> tuple[str, str]:
    """
    Open majors-minors.html, click the matching row, return
    (resolved_row_id, detail_panel_html).
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            goto = LSA_MAJORS_MINORS
            if fragment_id:
                goto = f"{LSA_MAJORS_MINORS}#{fragment_id}"
            page.goto(goto, wait_until="domcontentloaded", timeout=timeout_ms)

            # Cloudflare interstitial if present
            for _ in range(40):
                if page.locator("tr.has-program-detail").count() > 0 and "Just a moment" not in (
                    page.title() or ""
                ):
                    break
                page.wait_for_timeout(500)

            row_id = resolve_lsa_row_id(page, fragment_id, major_name=major_name)
            row = page.locator(f"#{row_id}")
            row.first.click(timeout=15_000)

            detail_sel = f"tr#{row_id} + tr .lsa-program-body"
            try:
                page.wait_for_selector(f"{detail_sel} a", timeout=20_000)
            except Exception:
                page.wait_for_timeout(2500)

            html = page.locator(detail_sel).inner_html(timeout=10_000)
            return row_id, html
        finally:
            browser.close()

"""Extract the latest LSA historical-program-requirements accordion block.

Shared LSA majors-minors pages (mathematics-major.html, international-studies-major.html,
many *-submajor.html pages, etc.) embed every term version of every related program in
``div.historical-program-requirements``. UI flow: open the most recent semester
accordion for this major/submajor — that block is what we keep for the LLM.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from umich_majors.fetch import html_to_llm_input, html_to_text

_SEASON = {"winter": 1, "spring": 2, "summer": 3, "fall": 4}
_TERM_RE = re.compile(r"(Fall|Winter|Spring|Summer)\s+(\d{4})", re.I)
_HEAD_RE = re.compile(
    r"^(?P<title>.+?)\s*\("
    r"(?P<start>(?:Fall|Winter|Spring|Summer)\s+\d{4})"
    r"(?:\s*-\s*(?P<end>(?:Fall|Winter|Spring|Summer)\s+\d{4})?)?"
    r"\)",
    re.I,
)
# Any LSA majors-minors detail page (not the listing itself)
_LSA_MAJORS_DETAIL = re.compile(r"/majors-minors/[^/]+\.html$", re.I)


def is_lsa_math_requirements_page(url: str) -> bool:
    """Backward-compatible alias — math + other shared LSA accordion pages."""
    return is_lsa_historical_requirements_page(url)


def is_lsa_historical_requirements_page(url: str) -> bool:
    p = urlparse(url)
    if "lsa.umich.edu" not in p.netloc.lower():
        return False
    path = p.path.rstrip("/")
    if path.endswith("/majors-minors.html"):
        return False
    return bool(_LSA_MAJORS_DETAIL.search(path))


def _norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    # Drop filler words so "Norms and Cooperation" ≈ "Norms & Cooperation"
    s = re.sub(r"\b(?:and|or|of|the|a|an)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _core_name(s: str) -> str:
    s = re.sub(
        r"\((?:Sub-)?Major(?:\s+of\s+[^)]+)?\)",
        "",
        s or "",
        flags=re.I,
    )
    s = re.sub(r"Sub-?major of [^(]+", "", s, flags=re.I)
    return _norm(s)


def _names_match(want: str, title: str) -> bool:
    """True when listing name and accordion title refer to the same program."""
    a = _core_name(want)
    b = _core_name(title)
    if not a or not b:
        return False
    if a == b:
        return True
    # Token containment (handles shorter/longer variants)
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    if ta <= tb or tb <= ta:
        return True
    # High overlap for near-matches
    inter = len(ta & tb)
    return inter >= 3 and inter / min(len(ta), len(tb)) >= 0.75


def _term_key(term: str) -> tuple[int, int]:
    m = _TERM_RE.search(term or "")
    if not m:
        return (0, 0)
    return (int(m.group(2)), _SEASON[m.group(1).lower()])


def _parse_heading(heading: str) -> tuple[str, str, str] | None:
    m = _HEAD_RE.match(heading.strip())
    if m:
        return m.group("title").strip(), m.group("start"), (m.group("end") or "").strip()
    # Single-term form: "… (Sub-Major) (Fall 2019)"
    m2 = re.match(
        r"(.+? \(Sub-Major\))\s*\(((?:Fall|Winter|Spring|Summer)\s+\d{4})\)",
        heading.strip(),
        re.I,
    )
    if m2:
        return m2.group(1).strip(), m2.group(2), ""
    return None


def _extract_submajor_body_html(div, title: str) -> str:
    """Drop shared parent-major preamble; keep the target program section."""
    text = div.get_text("\n", strip=True)
    title_plain = re.sub(r"\s*\(Sub-Major\)\s*$", "", title, flags=re.I).strip()
    # Strip trailing acronym "(ISNC)" for a looser body search
    title_no_acro = re.sub(r"\s*\([A-Z]{2,}\)\s*$", "", title_plain).strip()
    patterns = [
        rf"{re.escape(title)}\s*\n\s*Effective\s+(?:Fall|Winter|Spring|Summer)\s+\d{{4}}",
        rf"{re.escape(title_plain)}\s*\(Sub-Major\)\s*\n\s*Effective\s+(?:Fall|Winter|Spring|Summer)\s+\d{{4}}",
        rf"{re.escape(title_no_acro)}\s*\([A-Z]{{2,}}\)\s*\(Sub-Major\)\s*\n\s*Effective\s+(?:Fall|Winter|Spring|Summer)\s+\d{{4}}",
        rf"{re.escape(title_no_acro)}\s*\(Sub-Major\)\s*\n\s*Effective\s+(?:Fall|Winter|Spring|Summer)\s+\d{{4}}",
    ]
    start = None
    for pat in patterns:
        matches = list(re.finditer(pat, text, re.I))
        if matches:
            start = matches[-1].start()
            break
    if start is None:
        return str(div)

    body_text = text[start:]
    return (
        f'<div class="lsa-historical-requirements">\n'
        f"<pre>{_escape(body_text)}</pre>\n</div>"
    )


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def extract_latest_math_program(
    html: str,
    *,
    major_name: str,
    is_submajor: bool = True,
) -> dict | None:
    """Alias kept for callers — same as extract_latest_historical_program."""
    return extract_latest_historical_program(
        html, major_name=major_name, is_submajor=is_submajor
    )


def extract_latest_historical_program(
    html: str,
    *,
    major_name: str,
    is_submajor: bool = True,
) -> dict | None:
    """
    Return the most recent term block for this program from an LSA shared
    majors-minors requirements page.

    Keys: title, term_start, term_end, html, text, llm_text, strategy
    """
    soup = BeautifulSoup(html, "lxml")
    want = _core_name(major_name)
    if not want:
        return None

    # Parent major with a dedicated current panel (e.g. Mathematics)
    if not is_submajor:
        cur = soup.select_one("div.current-program-requirements")
        if cur and _names_match(major_name, cur.get_text(" ", strip=True)[:200]):
            cur_html = str(cur)
            return {
                "title": major_name,
                "term_start": _guess_effective(cur.get_text(" ", strip=True)),
                "term_end": "",
                "html": cur_html,
                "text": html_to_text(cur_html),
                "llm_text": html_to_llm_input(cur_html),
                "strategy": "lsa_historical_current",
            }
        # Mathematics parent special-case by name
        if want == "mathematics":
            cur = soup.select_one("div.current-program-requirements")
            if cur:
                cur_html = str(cur)
                return {
                    "title": "Mathematics (Major)",
                    "term_start": _guess_effective(cur.get_text(" ", strip=True)),
                    "term_end": "",
                    "html": cur_html,
                    "text": html_to_text(cur_html),
                    "llm_text": html_to_llm_input(cur_html),
                    "strategy": "lsa_math_current",
                }

    best: tuple[tuple[int, int], str, str, str, object] | None = None
    for div in soup.select("div.historical-program-requirements"):
        # Prefer the accordion h3 heading when present
        h3 = div.select_one("h3")
        heading = (
            h3.get_text(" ", strip=True)
            if h3
            else div.get_text(" ", strip=True)
        )
        parsed = _parse_heading(heading)
        if not parsed:
            # Fall back to full-div text start (math pages)
            parsed = _parse_heading(div.get_text(" ", strip=True))
        if not parsed:
            continue
        title, start, end = parsed
        if not _names_match(major_name, title):
            continue
        title_l = title.lower()
        if is_submajor and "sub-major" not in title_l and "sub major" not in title_l:
            # Some older blocks say "sub-plan" only inside body — still require Sub-Major in title
            if "sub-plan" not in title_l:
                continue
        if not is_submajor and ("sub-major" in title_l or "sub major" in title_l):
            continue
        key = _term_key(start)
        if best is None or key > best[0]:
            best = (key, title, start, end, div)

    if not best:
        return None

    _key, title, start, end, div = best
    block_html = _extract_submajor_body_html(div, title)
    if 'class="lsa-historical-requirements"' not in block_html:
        # Rebuild from text slice (same as math path)
        text_full = div.get_text("\n", strip=True)
        title_plain = re.sub(r"\s*\(Sub-Major\)\s*$", "", title, flags=re.I).strip()
        body_text = text_full
        for pat in (
            rf"{re.escape(title)}\s*\n\s*Effective\s+(?:Fall|Winter|Spring|Summer)\s+\d{{4}}",
            rf"{re.escape(title_plain)}\s*\(Sub-Major\)\s*\n\s*Effective\s+(?:Fall|Winter|Spring|Summer)\s+\d{{4}}",
        ):
            matches = list(re.finditer(pat, text_full, re.I))
            if matches:
                body_text = text_full[matches[-1].start() :]
                break
        block_html = (
            f'<div class="lsa-historical-requirements" '
            f'data-title="{_escape(title)}" data-term="{_escape(start)}">\n'
            f"<pre>{_escape(body_text)}</pre>\n</div>"
        )

    return {
        "title": title,
        "term_start": start,
        "term_end": end,
        "html": block_html,
        "text": html_to_text(block_html),
        "llm_text": html_to_llm_input(block_html),
        "strategy": "lsa_historical_latest_term",
    }


def _guess_effective(text: str) -> str:
    m = re.search(r"Effective\s+((?:Fall|Winter|Spring|Summer)\s+\d{4})", text, re.I)
    return m.group(1) if m else ""


def is_math_family_major(name: str, *, is_submajor: bool | None = None) -> bool:
    del is_submajor
    core = _core_name(name)
    if core == "mathematics":
        return True
    return bool(
        re.search(
            r"pure mathematics|actuarial mathematics|honors mathematics|"
            r"mathematical sciences|mathematics of finance|"
            r"secondary mathematics teaching",
            name or "",
            re.I,
        )
    )


def should_trim_lsa_historical(major: dict, page_url: str) -> bool:
    """True when this major/page pair should keep only one accordion block."""
    if not is_lsa_historical_requirements_page(page_url):
        return False
    name = major.get("name") or ""
    if is_math_family_major(name):
        return True
    if major.get("is_submajor"):
        return True
    # International Studies parent + subplans share one page
    if re.search(r"international studies|international security|"
                 r"political economy and development|comparative culture|"
                 r"global environment and health",
                 name, re.I):
        return True
    return False

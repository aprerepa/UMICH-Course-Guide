"""Discover & fetch secondary course-list links from a requirements page.

These are supplements (approved lists, elective lists, department course lists).
They do NOT replace requirements_url / requirements_final_url.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from umich_majors.fetch import fetch_page, html_to_text
from umich_majors.lsa_math_requirements import (
    _names_match,
    _parse_heading,
    _term_key,
)

_SKIP_HREF = re.compile(r"^(javascript:|mailto:|tel:|#)$", re.I)
_NOISE = re.compile(
    r"advising|appointment|honors\s+plan|apply|admissions?|declare|"
    r"facebook|twitter|instagram|linkedin|youtube|give\s+online|"
    r"course\s+catalog|lsa\s+course\s+guide|/cg(?:/|$)|"
    r"transfer\s+courses?|override\s+request|career\s+fair|"
    r"course\s+tagging|thesis\s+handout|special\s+topics\s+courses",
    re.I,
)

# Link text / URL signals that this is a course list for a requirement group
_POSITIVE: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\bulcs\b", re.I), 130),
    (re.compile(r"\bexpanded\s+ulcs\b", re.I), 125),
    (re.compile(r"\bcapstone\b", re.I), 120),
    (re.compile(r"\bflexible\s+(?:cs\s+)?technical\s+electives?\b", re.I), 120),
    (re.compile(r"\bapproved\s+list\b", re.I), 120),
    (re.compile(r"\bapproved\s+courses?\b", re.I), 110),
    (re.compile(r"\bprintable\s+.*(?:checklist|plan|subplan)\b", re.I), 120),
    (re.compile(r"\b(?:subplan|sub-?major)\s+checklist\b", re.I), 120),
    (re.compile(r"\bchecklist\b", re.I), 115),
    (re.compile(r"\belective\s+list\b", re.I), 110),
    (re.compile(r"\blist\s+of\s+(?:approved\s+)?courses?\b", re.I), 110),
    (re.compile(r"\bcourse\s+list\b", re.I), 100),
    (re.compile(r"\beligible\s+courses?\b", re.I), 95),
    (re.compile(r"\bcourses?\s+page\b", re.I), 90),
    (re.compile(r"\bpics\s+courses?\b", re.I), 90),
    (re.compile(r"\bcourse\s+options?\b", re.I), 70),
    (re.compile(r"/courses?(?:\.html|/|$)", re.I), 55),
    (re.compile(r"electives?(?:\.html|/|[-_])", re.I), 50),
    (re.compile(r"approved[-_]?list|course[-_]?list", re.I), 80),
    (re.compile(r"spreadsheets/d/", re.I), 60),
    (re.compile(r"drive\.google\.com/file/", re.I), 95),
]

# Hub pages that often link to the real checklist / approved list
_HUB_PAGE = re.compile(
    r"checklist|subplan|sub-?major|major-and-minor-programs|"
    r"/math/undergraduates|/undergraduates/major",
    re.I,
)

_MIN_SCORE = 55
_MAX_SUPPLEMENTS = 8
_MAX_CHARS_EACH = 18_000


def _unwrap_url(url: str) -> str:
    """Unwrap Google Docs redirect wrappers and normalize sheet preview URLs."""
    url = (url or "").strip()
    if "google.com/url" in url:
        q = parse_qs(urlparse(url).query).get("q", [None])[0]
        if q:
            url = unquote(q)
    return url


def _norm_url(url: str) -> str:
    url = _unwrap_url(url)
    p = urlparse(url.split("#")[0] if "#gid=" not in url.lower() else url)
    # Keep sheet tab id so ULCS / Capstone / FTE tabs don't collapse
    gid = None
    frag = urlparse(url).fragment or ""
    gm = re.search(r"gid=(\d+)", frag) or re.search(r"[?&]gid=(\d+)", url)
    if gm:
        gid = gm.group(1)
    base = urlunparse(
        (p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", "", "")
    ).lower()
    return f"{base}#gid={gid}" if gid else base


def _slug(label: str, url: str, index: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    if not base or base in {"download-now", "link", "here", "click-here", "ulcs-list"}:
        path = urlparse(url).path.rsplit("/", 1)[-1]
        base = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or f"supplement-{index}"
    # Distinguish sheet tabs
    gm = re.search(r"gid=(\d+)", url or "")
    if gm:
        base = f"{base}-gid{gm.group(1)}"
    return f"{index:02d}-{base[:70]}"


def _score_supplement(text: str, url: str) -> int:
    blob = f"{text} {url}"
    if _NOISE.search(blob):
        return 0
    if re.search(r"info\s+sheet|senior\s+design\s+info|course\s+descriptions?", blob, re.I):
        return 0
    score = 0
    for pat, pts in _POSITIVE:
        if pat.search(blob):
            score = max(score, pts)
    # PDF / Drive / sheet course lists
    if score and (
        url.lower().endswith(".pdf")
        or "docs.google.com" in url.lower()
        or "drive.google.com/file/" in url.lower()
    ):
        score += 15
    # Prefer a specific sheet tab (gid) over the workbook root
    if score and re.search(r"[#&?]gid=\d+", url):
        score += 25
    elif score and re.search(r"spreadsheets/d/", url) and "gid=" not in url:
        score -= 30
    return score


def _nearby_label(el: Tag) -> str:
    text = " ".join(el.get_text(" ", strip=True).split())
    if text and text.lower() not in {"download now", "here", "link", "click here"}:
        return text
    node: Tag | None = el
    for _ in range(6):
        if node is None:
            break
        heading = node.find(class_=re.compile(r"^h[1-6]$")) or node.find(
            re.compile(r"^h[1-6]$")
        )
        if heading:
            label = " ".join(heading.get_text(" ", strip=True).split())
            if label:
                return label
        node = node.parent if isinstance(node.parent, Tag) else None
    return text or "course list"


def _scope_html_for_major(
    html: str,
    *,
    major_name: str | None,
    is_submajor: bool,
) -> str:
    """Prefer the latest matching historical accordion when present."""
    if not major_name:
        return html
    soup = BeautifulSoup(html, "lxml")
    divs = soup.select("div.historical-program-requirements")
    if not divs:
        return html
    best = None
    best_key = (-1, -1)
    for div in divs:
        h3 = div.select_one("h3")
        heading = h3.get_text(" ", strip=True) if h3 else div.get_text(" ", strip=True)
        parsed = _parse_heading(heading) or _parse_heading(
            div.get_text(" ", strip=True)
        )
        if not parsed:
            continue
        title, start, _end = parsed
        if not _names_match(major_name, title):
            continue
        title_l = title.lower()
        if is_submajor and "sub-major" not in title_l and "sub major" not in title_l:
            if "sub-plan" not in title_l:
                continue
        if not is_submajor and ("sub-major" in title_l or "sub major" in title_l):
            continue
        key = _term_key(start)
        if key > best_key:
            best_key = key
            best = div
    return str(best) if best is not None else html


def find_supplement_links(
    html: str,
    base_url: str,
    *,
    major_name: str | None = None,
    is_submajor: bool = False,
    primary_url: str | None = None,
    limit: int = _MAX_SUPPLEMENTS,
    extra_html: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Return ranked course-list supplement candidates:
    [{url, link_text, score}, ...]

    extra_html: optional [(html, base_url), ...] pages to mine as well
    (e.g. program_page.html, department major pages).
    """
    pages: list[tuple[str, str]] = [(html, base_url or "")]
    for eh, eu in extra_html or []:
        if eh and eh.strip():
            pages.append((eh, eu or base_url or ""))

    primary = _norm_url(primary_url or base_url or "")
    found: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    hub_candidates: list[tuple[int, str, str]] = []
    generic_label = re.compile(
        r"^(?:course\s+lists?|link|here|click\s+here|download(?:\s+now)?|more|read\s+more)$",
        re.I,
    )

    def _consider(text: str, href: str, page_base: str) -> None:
        href = _unwrap_url((href or "").strip())
        if not href or _SKIP_HREF.match(href):
            return
        absolute = _unwrap_url(urljoin((page_base or "").split("#")[0], href))
        key = _norm_url(absolute)
        if not key or key in seen:
            return
        page_key = _norm_url(page_base or "")
        if key == primary or key == page_key:
            return
        label = text.strip()
        if generic_label.match(label or ""):
            if not re.search(
                r"drive\.google\.com/file/|docs\.google\.com/|spreadsheets/d/|"
                r"\.pdf(?:$|\?)|approved|checklist|ulcs|capstone|elective",
                absolute,
                re.I,
            ):
                return
        score = _score_supplement(label, absolute)
        blob = f"{label} {absolute}"
        if score < _MIN_SCORE:
            name_hit = False
            if major_name:
                tokens = [
                    t
                    for t in re.split(r"[^a-z0-9]+", major_name.lower())
                    if len(t) > 3
                    and t
                    not in {
                        "major",
                        "minor",
                        "sub",
                        "plan",
                        "college",
                        "school",
                        "administered",
                    }
                ]
                name_hit = sum(1 for t in tokens if t in blob.lower()) >= min(
                    2, max(1, len(tokens))
                )
            if name_hit or _HUB_PAGE.search(blob):
                if "umich.edu" in absolute.lower() or "drive.google.com" in absolute.lower():
                    hub_candidates.append((40, absolute, label or "program page"))
                    seen.add(key)
            return
        seen.add(key)
        found.append((score, absolute, label or "course list"))

    for page_html, page_base in pages:
        scoped = _scope_html_for_major(
            page_html, major_name=major_name, is_submajor=is_submajor
        )
        soup = BeautifulSoup(scoped, "lxml")
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            data_src = (a.get("data-source") or "").strip()
            if data_src and (_SKIP_HREF.match(href) or not href):
                _consider(_nearby_label(a), data_src, page_base)
            else:
                _consider(_nearby_label(a), href, page_base)
                if data_src:
                    _consider(_nearby_label(a), data_src, page_base)
        for el in soup.find_all(attrs={"data-source": True}):
            if el.name == "a":
                continue
            src = (el.get("data-source") or "").strip()
            if src:
                _consider(_nearby_label(el), src, page_base)

    # One-hop: mine hub pages for checklist / Drive / approved-list links
    for _score, hub_url, _text in hub_candidates[:3]:
        try:
            fetched, _llm = fetch_page(hub_url, force_browser=False)
        except Exception:
            continue
        hub_html = fetched.html or ""
        if len(hub_html) < 200:
            continue
        soup = BeautifulSoup(hub_html, "lxml")
        for a in soup.find_all("a", href=True):
            _consider(_nearby_label(a), a.get("href") or "", hub_url)

    found.sort(key=lambda x: (-x[0], x[1]))
    out: list[dict[str, Any]] = []
    for score, url, text in found[:limit]:
        out.append({"url": url, "link_text": text, "score": score})
    return out


def fetch_supplements_for_major(
    out_dir: Path,
    html: str,
    *,
    base_url: str,
    major_name: str | None = None,
    is_submajor: bool = False,
    primary_url: str | None = None,
    force_browser: bool = False,
    extra_html: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Discover + fetch supplements into out_dir/supplements/.
    Returns list of supplement meta rows (also written to supplements/index.json).
    Does not modify requirements_url.
    """
    # Always also mine the saved program page when present
    extras = list(extra_html or [])
    prog = out_dir / "program_page.html"
    if prog.exists():
        extras.append((prog.read_text(encoding="utf-8", errors="replace"), base_url))

    links = find_supplement_links(
        html,
        base_url,
        major_name=major_name,
        is_submajor=is_submajor,
        primary_url=primary_url or base_url,
        extra_html=extras,
    )
    supp_dir = out_dir / "supplements"
    if supp_dir.exists():
        # Clear previous run artifacts (keep folder)
        for p in supp_dir.iterdir():
            if p.is_file():
                p.unlink()
    else:
        supp_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for i, link in enumerate(links, start=1):
        slug = _slug(link["link_text"], link["url"], i)
        row: dict[str, Any] = {
            "id": slug,
            "url": link["url"],
            "link_text": link["link_text"],
            "score": link["score"],
            "status": "pending",
            "message": None,
            "final_url": None,
            "fetch_mode": None,
            "chars": 0,
        }
        try:
            fetched, llm = fetch_page(link["url"], force_browser=force_browser)
            text = html_to_text(fetched.html)
            if len(llm) > _MAX_CHARS_EACH:
                llm = llm[:_MAX_CHARS_EACH] + "\n\n[truncated supplement]"
            if len(text) > _MAX_CHARS_EACH:
                text = text[:_MAX_CHARS_EACH] + "\n\n[truncated supplement]"
            (supp_dir / f"{slug}.html").write_text(fetched.html, encoding="utf-8")
            (supp_dir / f"{slug}.txt").write_text(text + "\n", encoding="utf-8")
            (supp_dir / f"{slug}.llm.txt").write_text(llm + "\n", encoding="utf-8")
            row["status"] = "fetched"
            row["final_url"] = fetched.final_url
            row["fetch_mode"] = fetched.mode
            row["chars"] = len(text)
            row["message"] = f"ok ({row['chars']} chars)"
        except Exception as e:
            row["status"] = "failed"
            row["message"] = str(e)
        rows.append(row)

    (supp_dir / "index.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    # Combined LLM bundle for extract
    parts: list[str] = []
    for row in rows:
        if row.get("status") != "fetched":
            continue
        path = supp_dir / f"{row['id']}.llm.txt"
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8").strip()
        parts.append(
            f"### Supplement: {row['link_text']}\n"
            f"Source: {row.get('final_url') or row['url']}\n\n"
            f"{body}"
        )
    bundle = "\n\n".join(parts)
    (out_dir / "requirements_supplements.llm.txt").write_text(
        (bundle + "\n") if bundle else "",
        encoding="utf-8",
    )
    return rows


def load_supplements_llm_text(out_dir: Path, *, max_total_chars: int = 40_000) -> str:
    """Load previously fetched supplement bundle for LLM extract."""
    bundle = out_dir / "requirements_supplements.llm.txt"
    if bundle.exists() and bundle.stat().st_size > 40:
        text = bundle.read_text(encoding="utf-8")
        if len(text) > max_total_chars:
            return text[:max_total_chars] + "\n\n[truncated supplements]"
        return text

    # Rebuild from index if bundle missing
    index = out_dir / "supplements" / "index.json"
    if not index.exists():
        return ""
    try:
        rows = json.loads(index.read_text(encoding="utf-8"))
    except Exception:
        return ""
    parts: list[str] = []
    total = 0
    for row in rows:
        if row.get("status") != "fetched":
            continue
        path = out_dir / "supplements" / f"{row['id']}.llm.txt"
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8").strip()
        chunk = (
            f"### Supplement: {row.get('link_text') or row['id']}\n"
            f"Source: {row.get('final_url') or row.get('url')}\n\n"
            f"{body}"
        )
        if total + len(chunk) > max_total_chars:
            parts.append(chunk[: max(0, max_total_chars - total)] + "\n\n[truncated]")
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts)

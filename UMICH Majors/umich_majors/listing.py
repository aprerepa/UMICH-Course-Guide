"""Parse the Admissions Majors & Degrees listing table."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from umich_majors.config import MAJORS_LISTING_URL


def slug_for_major(name: str, url: str) -> str:
    """Stable-ish id for run folders / jsonl keys."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]
    # Disambiguate same name / different schools via path fragment.
    path = re.sub(r"[^a-z0-9]+", "-", url.rstrip("/").split("/")[-1].lower()).strip("-")
    if path and path not in base:
        return f"{base}--{path}"[:120]
    return base or "major"


def parse_majors(html: str, base_url: str = MAJORS_LISTING_URL) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    majors: list[dict] = []
    seen: set[str] = set()

    for row in soup.select("table tbody tr"):
        title_td = row.select_one("td.views-field-title, td.views-field.views-field-title")
        school_td = row.select_one(
            "td.views-field-field-school-college, "
            "td.views-field.views-field-field-school-college"
        )
        link = (title_td or row).find("a", href=True) if (title_td or row) else None
        if not link:
            continue
        name = link.get_text(" ", strip=True)
        href = (link.get("href") or "").strip()
        if not name or href.startswith("javascript:"):
            continue
        url = urljoin(base_url, href)
        key = f"{name}|{url}"
        if key in seen:
            continue
        seen.add(key)
        school = school_td.get_text(" ", strip=True) if school_td else None
        majors.append(
            {
                "id": slug_for_major(name, url),
                "name": name,
                "school_college": school or None,
                "url": url,
                "is_submajor": "sub-major" in name.lower(),
            }
        )

    if not majors:
        for a in soup.select(".views-field-title a[href]"):
            name = a.get_text(" ", strip=True)
            href = (a.get("href") or "").strip()
            if not name or href.startswith("javascript:"):
                continue
            url = urljoin(base_url, href)
            key = f"{name}|{url}"
            if key in seen:
                continue
            seen.add(key)
            majors.append(
                {
                    "id": slug_for_major(name, url),
                    "name": name,
                    "school_college": None,
                    "url": url,
                    "is_submajor": "sub-major" in name.lower(),
                }
            )

    majors.sort(key=lambda m: m["name"].lower())
    return majors

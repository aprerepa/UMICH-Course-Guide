"""Find undergraduate major requirements / curriculum links on a program page."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

_COURSE_CODE = re.compile(r"\b[A-Z]{2,}(?:/[A-Z]{2,})?\s+\d{3}\b")

# Positive text signals (undergraduate curriculum)
_TEXT_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\bdegree\s+requirements?\s+checklist\b", re.I), 155),
    (re.compile(r"\bprogram\s+guide\b", re.I), 140),
    (re.compile(r"\bcurriculum\s+by\s+year\b", re.I), 130),
    (re.compile(r"\boverview\s+of\s+(?:the\s+)?.{0,40}curriculum\b", re.I), 125),
    (re.compile(r"\bundergraduate\s+(?:degree\s+)?requirements?\b", re.I), 120),
    (re.compile(r"\bundergraduate\s+curriculum\b", re.I), 115),
    (re.compile(r"\b(?:ce|ee|ioe|program)\s+program\s+guide\b", re.I), 110),
    # Dept course guides (IOE Course Guide) — not the college-wide LSA Course Guide
    (re.compile(r"\b(?!lsa\b)\w[\w&/.-]{0,20}\s+course\s+guide\b", re.I), 135),
    (re.compile(r"\bsample\s+schedule\b", re.I), 90),
    (re.compile(r"\bdegree\s+requirements?\b", re.I), 100),
    (re.compile(r"\bmajor\s+requirements?\b", re.I), 95),
    (re.compile(r"\bprogram\s+requirements?\b", re.I), 90),
    (re.compile(r"\bcourse\s+requirements?\b", re.I), 85),
    (re.compile(r"^requirements?$", re.I), 100),
    (re.compile(r"\brequirements?\b", re.I), 55),
    (re.compile(r"\bcurriculum\b", re.I), 50),
    (re.compile(r"\bchecklist\b", re.I), 95),
    (re.compile(r"\bbulletin\b", re.I), 35),
]

_HREF_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"degree[-_]?checklist|checklist\.pdf", re.I), 55),
    (re.compile(r"/majors-minors/[^/\s?#]*submajor", re.I), 75),
    (re.compile(r"undergraduate.*/(?:degree[-_]?)?requirements?", re.I), 50),
    (re.compile(r"/undergraduate/.*/curriculum", re.I), 45),
    (re.compile(r"degree[-_]?requirements?", re.I), 35),
    (re.compile(r"major[-_]?requirements?", re.I), 30),
    (re.compile(r"/undergraduate/requirements", re.I), 40),
    (re.compile(r"docs\.google\.com/(?:document|spreadsheets|presentation)", re.I), 25),
    (re.compile(r"\.pdf$", re.I), 20),
    (re.compile(r"requirements?", re.I), 15),
    (re.compile(r"curriculum", re.I), 15),
]

_SKIP_HREF = re.compile(r"^(javascript:|mailto:|tel:|#)$", re.I)
_MIN_ACCEPT_SCORE = 60

# Graduate / admissions noise
_GRAD_RE = re.compile(
    r"(?:^|/)(?:graduate|grad(?:uate)?[-_/]|masters?|mba|phd|doctoral|executive[-_]mba)"
    r"|(?:^|\b)(?:graduate|masters?|mba|phd)\b",
    re.I,
)
_UNDERGRAD_RE = re.compile(
    r"(?:^|/)undergraduate|/bba|/bfa|/bse\b|/bs\b|bachelor|undergrad",
    re.I,
)
_ADMISSIONS_APP_RE = re.compile(
    r"application\s+requirements?|admissions?\s*[-_]?\s*requirements?|how\s+to\s+apply|"
    r"declare\s+.+\s+as\s+your\s+major|"
    r"/apply|/admissions?(?:/|$|[-_])|deadlines?",
    re.I,
)
_GENERIC_LSA_REQ_RE = re.compile(
    r"/lsa-requirements(?:\.html|/|$)|area-distribution|distribution\s+requirement",
    re.I,
)

# Degree program hub cards (Art & Design / Eng / Education / dept landings)
_DEGREE_PROGRAM_TEXT = re.compile(
    r"\b(?:BFA|BA|BS|BSE|BBA|Bachelor)\b|"
    r"\bMajor\s+in\b|"
    r"\bTeacher\s+Education\b|"
    r"\bExplore\b|"
    r"Interarts|Dual\s+Degrees?",
    re.I,
)
_DEGREE_PROGRAM_HREF = re.compile(
    r"/(?:bfa|ba|bse|bba|bachelor|major-in-[^/]+|"
    r"undergraduate/(?:programs/)?(?:major|curriculum|requirements)|"
    r"undergraduate-(?:elementary|secondary)-teacher-education|"
    r"women-s-and-gender-studies-major|"
    r"academics/majors|"
    r"offerings/[^/]+|"
    r"program/[^/]+)"
    r"(?:/|$|\.html)",
    re.I,
)
_CAREER_NOISE_RE = re.compile(
    r"\b(?:positions?|careers?|jobs?|faculty|staff|employment|hiring)\b",
    re.I,
)


def _normalize_name(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _normalize_page_key(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path.rstrip("/"), "", "", "")).lower()


def _is_lsa_majors_minors_listing(url: str) -> bool:
    p = urlparse(url)
    return "lsa.umich.edu" in p.netloc.lower() and p.path.rstrip("/").endswith(
        "/majors-minors.html"
    )


def _blob(text: str, href: str) -> str:
    return f"{text} {href}"


def _score_anchor(text: str, href: str, *, program_url: str) -> int:
    if not href or _SKIP_HREF.match(href.strip()):
        return 0

    absolute_preview = urljoin(program_url.split("#")[0], href)
    blob = _blob(text, absolute_preview)
    score = 0
    signal = False

    for pat, pts in _TEXT_PATTERNS:
        if pat.search(text):
            score = max(score, pts)
            signal = True
    for pat, pts in _HREF_PATTERNS:
        if pat.search(absolute_preview):
            score += pts
            signal = True

    # Must look like requirements/curriculum — not just "Undergraduate" nav.
    if not signal:
        return 0

    host = urlparse(absolute_preview).netloc.lower()
    path = urlparse(absolute_preview).path.lower()

    if "umich.edu" in host or href.startswith("/"):
        score += 10

    # Strong preference for undergraduate paths / wording
    if _UNDERGRAD_RE.search(blob):
        score += 55
    if "/undergraduate/" in path:
        score += 25

    # Hard penalties
    if _GRAD_RE.search(blob) and not _UNDERGRAD_RE.search(blob):
        score -= 200
    if _ADMISSIONS_APP_RE.search(blob):
        score -= 180
    if _GENERIC_LSA_REQ_RE.search(absolute_preview) or re.search(
        r"^lsa\s+requirements?$|^lsa\s+distribution", text, re.I
    ):
        score -= 160
    if "admissions.umich.edu" in host and "apply" in path:
        score -= 100
    if "/news/" in path:
        score -= 80
    if "/course-syllabi/" in path or re.search(r"/educ-\d+", path):
        score -= 120
    # College-wide CoE graduation rules — not major curriculum
    if re.search(r"rules/graduation|requirementsforabachelorsdegree", absolute_preview, re.I):
        score -= 120
    if href.strip().startswith("#"):
        score -= 40
    if path.rstrip("/").endswith("/majors-minors.html"):
        score -= 100

    # Official Google Doc / Sheet / Slides curriculum guides
    if is_google_docs_or_sheets_url(absolute_preview):
        score += 35
        if re.search(
            r"curriculum|program\s+guide|course\s+guide|overview|"
            r"degree\s+requirements?|major\s+requirements?",
            blob,
            re.I,
        ):
            score += 40
        # Research opportunity sheets / intranet noise
        if re.search(r"research\s+opportunit|intranet", blob, re.I):
            score -= 100
        # Prefer course/program guides over bare sample schedules
        if re.search(r"sample\s+schedule", blob, re.I) and not re.search(
            r"course\s+guide|program\s+guide|degree\s+requirements?", blob, re.I
        ):
            score -= 45

    # Generic college course guide — not a major curriculum PDF
    if re.search(r"^lsa\s+course\s+guide$", text.strip(), re.I) or re.search(
        r"lsa\.umich\.edu/cg(?:/|$)", absolute_preview, re.I
    ):
        score -= 160

    # Career sheets / historical archives lose to current program guides
    if re.search(r"career\s+info|career\s+sheet|careers?\s+pdf", blob, re.I):
        score -= 150
    if re.search(r"\bhistorical\b", blob, re.I):
        score -= 130
    # Prefer the newest Fall YYYY mentioned next to a program guide link
    years = [int(y) for y in re.findall(r"Fall\s+(20\d{2})", blob, re.I)]
    if years:
        score += max(years) - 2000  # Fall 2025 → +25

    # Curriculum-section nav that is not the actual course list
    if re.search(
        r"coaching|advising|specialization|global\s+opportunit|real\.?\s*business\s+experiences?",
        blob,
        re.I,
    ):
        score -= 80

    # Prefer degree checklists over sample plans / handbooks / minor flyers
    if re.search(r"student\s+handbook|handbook\.pdf", blob, re.I):
        score -= 100
    if re.search(r"sample\s+degree\s+plan|minor\s+options?|pre-?health\s+plan", blob, re.I):
        score -= 50
    if re.search(r"degree\s+requirements?\s+checklist|degree[-_]?checklist", blob, re.I):
        score += 40

    return score


# Hub/dept words that appear on many sibling majors (biology-assets/, …)
_GENERIC_MAJOR_TOKENS = frozenset(
    {
        "biology",
        "science",
        "sciences",
        "studies",
        "engineering",
        "arts",
        "major",
        "program",
        "health",
        "society",
        "education",
        "literature",
        "college",
        "department",
    }
)


def _major_match_keys(major_name: str) -> tuple[list[str], list[str]]:
    """Return (acronyms, distinctive tokens) for preferring the right Program Guide."""
    raw = (major_name or "").lower().split("(")[0]
    raw = raw.replace("&", " and ")
    words = [
        w
        for w in re.sub(r"[^a-z0-9]+", " ", raw).split()
        if w not in {"and", "or", "of", "the", "a", "an", "in", "for", "at"}
    ]
    acronyms: list[str] = []
    if len(words) >= 2:
        acro = "".join(w[0] for w in words if w)
        if len(acro) >= 3:
            acronyms.append(acro)
    # Common dept short names
    joined = " ".join(words)
    if "computer" in words and "science" in words:
        acronyms.extend(["cs", "cs-eng", "cseng"])
        if "engineering" in words or "bse" in words or "eng" in words:
            acronyms.append("cs-eng")
    # Distinctive long tokens only (not biology / sciences / …)
    tokens = [
        w
        for w in words
        if len(w) >= 6 and w not in _GENERIC_MAJOR_TOKENS
    ]
    # Dedupe acronyms
    seen_a: set[str] = set()
    acro_out: list[str] = []
    for a in acronyms:
        if a not in seen_a:
            seen_a.add(a)
            acro_out.append(a)
    return acro_out, tokens


def major_name_link_boost(major_name: str | None, text: str, url: str) -> int:
    """Score bump when link text/filename clearly refers to this major (e.g. MCDB-MAJOR.pdf)."""
    if not major_name:
        return 0
    # Match text + filename only — full URLs include dept folders like biology-assets/
    filename = urlparse(url).path.rsplit("/", 1)[-1].lower()
    blob = f"{text} {filename}".lower()
    boost = 0
    name_l = major_name.lower().split("(")[0].strip()
    if len(name_l) >= 12 and name_l[:24] in blob:
        boost += 80
    acronyms, tokens = _major_match_keys(major_name)
    # Acronym in filename is strongest (MCDB-MAJOR.pdf vs BBS-MAJOR.pdf on same hub)
    for acro in acronyms:
        if re.search(rf"\b{re.escape(acro)}\b", filename, re.I) or re.search(
            rf"(^|[^a-z0-9]){re.escape(acro)}([^a-z0-9]|$)", filename, re.I
        ):
            boost += 150
            break
        if re.search(rf"\b{re.escape(acro)}\b", text, re.I):
            boost += 120
            break
    if boost < 100:
        for key in tokens:
            if re.search(rf"\b{re.escape(key)}\b", blob, re.I):
                boost += 90
                break
    # Wrong-major program guides on the same biology hub
    if boost == 0 and re.search(r"program\s+guide|major\.pdf|-major\.pdf", blob, re.I):
        boost -= 40
    return boost


def is_google_docs_or_sheets_url(url: str) -> bool:
    """True for Google Docs / Sheets / Slides URLs used as curriculum guides."""
    return bool(
        re.search(
            r"docs\.google\.com/(?:document|spreadsheets|presentation)/",
            url or "",
            re.I,
        )
    )


_DEEP_CURRICULUM_RE = re.compile(
    r"curriculum[-_/]?by[-_/]?year|\bby\s+year\b|course\s+list|"
    r"degree\s+requirements?|program\s+guide|checklist|sample\s+schedule|"
    r"overview\s+of\s+(?:the\s+)?.{0,40}curriculum",
    re.I,
)
_NESTED_SKIP_RE = re.compile(
    r"coaching|advising|specialization|concentration|global\s+opportunit|"
    r"real\.?\s*business|experiences?|research\s+opportunit|intranet|"
    r"women|affording|admissions|apply",
    re.I,
)


def should_follow_nested_requirements(
    current_url: str,
    nested: dict,
    *,
    current_html: str = "",
    major_name: str | None = None,
) -> bool:
    """
    True when a requirements/curriculum landing should hop once more
    (Google Doc/Sheet guide, checklist PDF, dedicated submajor page, etc.).
    """
    nested_url = (nested.get("url") or "").strip()
    if not nested_url:
        return False
    text = nested.get("link_text") or ""
    blob = f"{text} {nested_url}"
    if _NESTED_SKIP_RE.search(blob):
        return False
    if is_google_docs_or_sheets_url(nested_url):
        # Landing page → official Doc/Sheet: hop.
        # Already on a Doc/Sheet: do not hop to another Doc (Dual Major, thesis, …).
        # Course-list Sheets are handled as supplements instead.
        if is_google_docs_or_sheets_url(current_url):
            return False
        return True

    cur = urlparse(current_url.split("#")[0])
    nxt = urlparse(nested_url.split("#")[0])
    if cur.netloc.lower() != nxt.netloc.lower():
        return False

    # Same-host degree checklist / requirements PDFs (e.g. Pharmacy FlipBook embeds)
    if nxt.path.lower().endswith(".pdf") and re.search(
        r"checklist|degree[-_]?requirements?|program[-_]?guide|major[-_]?requirements?",
        blob,
        re.I,
    ):
        codes = len(
            _COURSE_CODE.findall(BeautifulSoup(current_html or "", "lxml").get_text(" "))
        )
        return codes < 12

    # Sibling LSA majors-minors pages: parent major → dedicated submajor page
    # (e.g. film-television-and-media-major.html → screenwriting-submajor.html)
    if (
        major_name
        and "/majors-minors/" in cur.path
        and "/majors-minors/" in nxt.path
        and nxt.path.lower().endswith(".html")
        and cur.path.rstrip("/").lower() != nxt.path.rstrip("/").lower()
        and major_name_link_boost(major_name, text, nested_url) >= 90
    ):
        return True

    cur_path = cur.path.rstrip("/")
    nxt_path = nxt.path.rstrip("/")
    if not (nxt_path.startswith(cur_path + "/") and len(nxt_path) > len(cur_path) + 1):
        return False
    if not _DEEP_CURRICULUM_RE.search(blob):
        return False

    # Only leave a thin marketing/curriculum overview for a deeper page.
    codes = len(_COURSE_CODE.findall(BeautifulSoup(current_html or "", "lxml").get_text(" ")))
    return codes < 12


def _nearby_embed_label(el: Tag) -> str:
    """Heading near a FlipBook / data-source embed (e.g. 'Degree Requirements Checklist')."""
    node: Tag | None = el
    for _ in range(8):
        if node is None:
            break
        heading = node.find(class_=re.compile(r"^h[1-6]$")) or node.find(
            re.compile(r"^h[1-6]$")
        )
        if heading:
            label = heading.get_text(" ", strip=True)
            if label:
                return label
        classes = " ".join(node.get("class") or [])
        if "col-box" in classes or "subsection" in classes:
            break
        node = node.parent if isinstance(node.parent, Tag) else None
    return el.get_text(" ", strip=True) or "embedded document"


def _collect_candidates(
    soup: BeautifulSoup,
    base_url: str,
    *,
    scope: Tag | BeautifulSoup | None = None,
) -> list[tuple[int, str, str]]:
    root = scope or soup
    page_key = _normalize_page_key(base_url.split("#")[0])
    found: list[tuple[int, str, str]] = []
    seen: set[str] = set()

    def _add(text: str, href: str, *, context: str = "") -> None:
        scored_text = f"{text} {context}".strip() if context else text
        score = _score_anchor(scored_text, href, program_url=base_url)
        if score < _MIN_ACCEPT_SCORE:
            return
        absolute = urljoin(base_url.split("#")[0], href)
        key = _normalize_page_key(absolute)
        if key == page_key or key in seen:
            return
        if _is_lsa_majors_minors_listing(absolute) and urlparse(absolute).fragment:
            return
        seen.add(key)
        # Keep short link text for display; scoring already used context
        found.append((score, absolute, text.strip() or scored_text.strip()))

    def _anchor_context(a: Tag) -> str:
        parent = a.find_parent(["p", "li", "td", "div", "span"])
        if not parent:
            return ""
        return " ".join(parent.get_text(" ", strip=True).split())[:240]

    for a in root.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        # FlipBook embeds: real PDF is in data-source while href is "#"
        data_src = (a.get("data-source") or "").strip()
        ctx = _anchor_context(a)
        if data_src and (_SKIP_HREF.match(href) or not href):
            href = data_src
            text = _nearby_embed_label(a)
        else:
            text = a.get_text(" ", strip=True)
            if data_src and not href.lower().endswith(".pdf"):
                # Prefer embedded PDF when both exist
                _add(_nearby_embed_label(a), data_src, context=ctx)
        _add(text, href, context=ctx)

    # Non-anchor embeds with data-source
    for el in root.find_all(attrs={"data-source": True}):
        if el.name == "a":
            continue
        src = (el.get("data-source") or "").strip()
        if src:
            _add(_nearby_embed_label(el), src)

    found.sort(key=lambda x: (-x[0], x[1]))
    return found


def page_looks_like_requirements(html: str, url: str) -> bool:
    """True when the program URL itself is already a requirements / curriculum page."""
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower().rstrip("/")
    # Google Sheets / Docs used as official course lists (e.g. Data Science Eng)
    if "docs.google.com" in host and re.search(
        r"/(?:spreadsheets|document|presentation)/", url, re.I
    ):
        return True
    if re.search(r"(?:^|/)(?:requirements?|curriculum)(?:/|$|\.html)", path):
        return True
    # Eng "programs/major" pages embed the course requirements
    if re.search(r"/undergraduate/programs/major(?:/|$)", path):
        return True
    text = BeautifulSoup(html, "lxml").get_text("\n", strip=True)
    codes = len(_COURSE_CODE.findall(text))
    if re.search(r"(?:-major|-sub-major|-minor)(?:\.html)?$", path):
        return codes >= 8
    # Math department major pages are the requirements checklist
    if "/major-and-minor-programs/" in path and path.count("/") >= 4:
        if codes >= 3 or re.search(
            r"requirements?|checklist|prerequisite|must\s+(?:take|complete)|courses?\s+required",
            text,
            re.I,
        ):
            return True
    if codes >= 15 and re.search(
        r"requirements?|prerequisites?|curriculum|program\s+guide|credit\s+hours",
        text,
        re.I,
    ):
        return True
    # Teacher-ed program pages list the full course sequence without a separate link
    if "teacher-education" in path and codes >= 10:
        return True
    # ME / Eng undergrad handbooks embed program requirements
    if "/handbook/" in path and ("bachelor" in path or "undergrad" in path) and codes >= 10:
        return True
    return False


def page_looks_like_majors_directory(html: str, url: str) -> bool:
    """True for CoE 'all undergraduate majors' catalog pages."""
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    if "majors.engin.umich.edu" in host:
        return True
    if re.search(r"/academics/majors/?$", path):
        return True
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    if text.lower().count("course list / bulletin") >= 3:
        return True
    return False


def find_degree_program_links(
    html: str,
    base_url: str,
    *,
    major_name: str | None = None,
) -> list[tuple[int, str, str]]:
    """
    Hub pages (e.g. Stamps Art & Design, Marsal bachelors, MSE undergrad) list
    degree programs instead of a Requirements link. Return ranked undergrad URLs.
    """
    soup = BeautifulSoup(html, "lxml")
    page_key = _normalize_page_key(base_url.split("#")[0])
    name_norm = _normalize_name(major_name) if major_name else ""
    # Drop parentheticals like "Sub-major of Mathematics" for matching
    name_core = name_norm.split(" sub ")[0].strip() if name_norm else ""
    found: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        text = a.get_text(" ", strip=True)
        if not href or _SKIP_HREF.match(href):
            continue
        absolute = urljoin(base_url.split("#")[0], href)
        key = _normalize_page_key(absolute)
        if key == page_key or key in seen:
            continue
        if _GRAD_RE.search(_blob(text, absolute)) and not _UNDERGRAD_RE.search(
            _blob(text, absolute)
        ):
            continue

        text_norm = _normalize_name(text)
        # Empty alt/logo links must not match via ""-in-name (Python: "" in s is True).
        name_hit = bool(
            name_core
            and len(name_core) >= 6
            and text_norm
            and len(text_norm) >= 6
            and (name_core in text_norm or text_norm in name_core)
        )
        # Skip bare site roots / empty labels even if other patterns fire.
        path_only = urlparse(absolute).path.rstrip("/") or "/"
        if not text.strip() or path_only == "/":
            continue
        # Bare "Major" nav → /undergraduate/programs/major (MSE)
        bare_major = bool(
            re.fullmatch(r"Major", text.strip(), re.I)
            and re.search(r"/programs/major(?:/|$)", absolute, re.I)
        )
        # "{Major Name} Major" dept pages (WGS)
        named_major_page = bool(
            name_hit and re.search(r"\bMajor\b", text) and "minor" not in text.lower()
        )

        if (
            not _DEGREE_PROGRAM_TEXT.search(text)
            and not _DEGREE_PROGRAM_HREF.search(absolute)
            and not bare_major
            and not named_major_page
            and not name_hit
        ):
            continue

        # Prefer same host
        score = 50
        if urlparse(absolute).netloc == urlparse(base_url).netloc:
            score += 20
        host = urlparse(absolute).netloc.lower()
        path = urlparse(absolute).path.lower()
        if name_hit:
            score += 45
        if bare_major:
            score += 40
        if named_major_page:
            score += 35
        # CoE: "Explore Mechanical Engineering" → majors catalog
        if re.search(r"\bExplore\b", text) and name_hit:
            score += 55
        if (
            "majors.engin.umich.edu" in host
            or "/academics/majors" in path
            or "/offerings/" in path
        ):
            score += 30
        if re.search(r"\bBFA\b", text):
            score += 25  # primary studio degree for Art & Design
        if re.search(r"\bMajor\s+in\b", text) or "/major-in-" in absolute.lower():
            score += 30
        if re.search(r"\bBA\b", text) and "interarts" not in text.lower():
            score += 15
        if re.search(r"\bBSE\b|\bBBA\b|\bBS\b", text):
            score += 20
        if re.search(r"teacher\s+education", text, re.I):
            score += 15
        if re.search(
            r"/undergraduate/(?:programs/)?(?:major|curriculum|requirements)",
            absolute,
            re.I,
        ):
            score += 35
        if "minor" in text.lower():
            score -= 40
        if "dual" in text.lower():
            score -= 10
        if "admissions" in text.lower() or "admissions" in absolute.lower():
            score -= 50
        if "considering" in text.lower():
            score -= 25
        if _CAREER_NOISE_RE.search(text) or _CAREER_NOISE_RE.search(path):
            score -= 90
        if re.search(r"course\s+list|bulletin|career\s+info", text, re.I):
            score -= 50
        seen.add(key)
        found.append((score, absolute, text))
    found.sort(key=lambda x: (-x[0], x[1]))
    return found


def find_requirements_url(
    html: str,
    base_url: str,
    *,
    major_name: str | None = None,
) -> dict | None:
    """Return best undergraduate requirements link, or None."""
    soup = BeautifulSoup(html, "lxml")
    page_url = base_url.split("#")[0]
    page_hits = _collect_candidates(soup, page_url)

    if major_name:
        boosted: list[tuple[int, str, str]] = []
        for score, url, text in page_hits:
            score += major_name_link_boost(major_name, text, url)
            boosted.append((score, url, text))
        boosted.sort(key=lambda x: (-x[0], x[1]))
        page_hits = boosted

    if page_hits:
        score, url, text = page_hits[0]
        return {
            "url": url,
            "link_text": text,
            "score": score,
            "strategy": "page",
        }
    return None


def find_requirements_url_in_detail(
    detail_html: str,
    base_url: str,
) -> dict | None:
    """Search an LSA AJAX program-detail fragment for REQUIREMENTS."""
    soup = BeautifulSoup(detail_html, "lxml")
    hits = _collect_candidates(soup, base_url)
    if hits:
        score, url, text = hits[0]
        return {
            "url": url,
            "link_text": text,
            "score": score,
            "strategy": "lsa_detail",
        }
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if re.fullmatch(r"requirements?", text, re.I):
            return {
                "url": urljoin(base_url, a["href"]),
                "link_text": text,
                "score": 100,
                "strategy": "lsa_detail_exact",
            }
    return None

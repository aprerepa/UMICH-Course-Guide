"""Fetch listing / detail pages (HTTP, Playwright fallback) → LLM-ready text."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 45.0
MAX_BYTES = 5_000_000
MIN_PAGE_TEXT_CHARS = 500
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
NOISE_TAGS = {"script", "style", "nav", "footer", "header", "noscript"}


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    html: str
    mode: str  # "http" | "browser"


def fetch_page_http(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> FetchResult:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text
        if len(html.encode("utf-8", errors="replace")) > MAX_BYTES:
            html = html[:MAX_BYTES]
    return FetchResult(
        requested_url=url,
        final_url=str(resp.url),
        status_code=resp.status_code,
        html=html,
        mode="http",
    )


def fetch_page_browser(url: str, *, timeout_ms: int = 45_000) -> FetchResult:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_selector(
                    ".views-field-title a, main, article, h1",
                    timeout=12_000,
                )
            except Exception:
                pass
            page.wait_for_timeout(1500)
            html = page.content()
            final = page.url
        finally:
            browser.close()
    return FetchResult(
        requested_url=url,
        final_url=final,
        status_code=200,
        html=html,
        mode="browser",
    )


def _page_title_and_meta(soup: BeautifulSoup) -> list[str]:
    lines: list[str] = []
    if soup.title and soup.title.string:
        lines.append(f"page title: {soup.title.string.strip()}")
    for attrs in (
        {"property": "og:title"},
        {"name": "og:title"},
        {"property": "og:description"},
        {"name": "description"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if not tag:
            continue
        content = (tag.get("content") or "").strip()
        if content and content not in " ".join(lines):
            key = attrs.get("property") or attrs.get("name") or "meta"
            lines.append(f"{key}: {content}")
    return lines


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def html_to_llm_input(html: str, *, max_chars: int = 80_000) -> str:
    soup = BeautifulSoup(html, "lxml")
    header = _page_title_and_meta(soup)
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    parts: list[str] = []
    if header:
        parts.append("Page header:\n" + "\n".join(header))
    parts.append("Visible page text:\n" + text)
    return "\n\n".join(parts)[:max_chars]


def google_docs_export_url(url: str) -> str | None:
    """True-ish marker: Docs URLs we can export (HTML preferred for link discovery)."""
    m = re.search(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", url or "", re.I)
    if not m:
        return None
    return f"https://docs.google.com/document/d/{m.group(1)}/export?format=html"


def google_docs_txt_export_url(url: str) -> str | None:
    m = re.search(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", url or "", re.I)
    if not m:
        return None
    return f"https://docs.google.com/document/d/{m.group(1)}/export?format=txt"


def google_sheets_export_url(url: str) -> str | None:
    """Turn a Sheets edit/share URL into a plain-text TSV export (LLM-friendly).

    Published links (/d/e/2PACX-…/pubhtml) are not supported here — use browser fetch.
    """
    if re.search(r"spreadsheets/d/e/", url or "", re.I):
        return None
    m = re.search(
        r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]{10,})", url or "", re.I
    )
    if not m:
        return None
    sheet_id = m.group(1)
    gid = None
    frag = urlparse(url).fragment or ""
    gm = re.search(r"gid=(\d+)", frag) or re.search(r"[?&]gid=(\d+)", url or "")
    if gm:
        gid = gm.group(1)
    export = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=tsv"
    if gid:
        export += f"&gid={gid}"
    return export


def google_sheets_xlsx_export_url(url: str) -> str | None:
    if re.search(r"spreadsheets/d/e/", url or "", re.I):
        return None
    m = re.search(
        r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]{10,})", url or "", re.I
    )
    if not m:
        return None
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx"


def is_google_published_sheet_url(url: str) -> bool:
    return bool(
        re.search(r"docs\.google\.com/spreadsheets/d/e/[A-Za-z0-9_-]+", url or "", re.I)
    )


def google_slides_export_url(url: str) -> str | None:
    """Turn a Slides edit/share URL into a plain-text export (LLM-friendly)."""
    m = re.search(
        r"docs\.google\.com/presentation/d/([a-zA-Z0-9_-]+)", url or "", re.I
    )
    if not m:
        return None
    return f"https://docs.google.com/presentation/d/{m.group(1)}/export/txt"


def is_pdf_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return True
    # Google Drive file shares are usually PDFs for checklists / guides
    if re.search(r"drive\.google\.com/file/d/", url, re.I):
        return True
    return False


def google_drive_file_export_url(url: str) -> str | None:
    """Direct-download URL for a Google Drive file share."""
    m = re.search(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)", url or "")
    if not m:
        return None
    return f"https://drive.google.com/uc?export=download&id={m.group(1)}"


def fetch_pdf(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> FetchResult:
    """Download a PDF and extract text for LLM input."""
    import io

    from pypdf import PdfReader

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,*/*",
    }
    download_url = google_drive_file_export_url(url) or url
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(download_url)
        resp.raise_for_status()
        data = resp.content
        final_url = str(resp.url)
        status = resp.status_code
    if not data.startswith(b"%PDF"):
        raise ValueError(
            f"Expected PDF bytes from {download_url}, got "
            f"{resp.headers.get('content-type')!r} ({len(data)} bytes)"
        )
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    body = "\n".join(parts).strip()
    if not body:
        raise ValueError("PDF text extraction returned empty")
    return FetchResult(
        requested_url=url,
        final_url=final_url,
        status_code=status,
        html=_wrap_plain_as_html("PDF extract", body),
        mode="http",
    )


def _wrap_plain_as_html(title: str, body: str) -> str:
    safe = (
        body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body><main><pre>{safe}</pre></main></body></html>"
    )


def fetch_google_docs_txt(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> FetchResult:
    """
    Fetch a Google Doc as HTML (keeps hyperlinks for supplement discovery)
    with plain-text fallback.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,*/*"}
    html_export = google_docs_export_url(url)
    txt_export = google_docs_txt_export_url(url)
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        if html_export:
            try:
                resp = client.get(html_export)
                resp.raise_for_status()
                html = resp.text
                # Unwrap google redirect wrappers so supplement discovery sees real URLs
                html = re.sub(
                    r'href="https://www\.google\.com/url\?q=([^"&]+)[^"]*"',
                    lambda m: f'href="{unquote(m.group(1))}"',
                    html,
                )
                if len(html_to_text(html)) >= 200:
                    return FetchResult(
                        requested_url=url,
                        final_url=url,
                        status_code=resp.status_code,
                        html=html,
                        mode="http",
                    )
            except Exception:
                pass
        export = txt_export or url
        resp = client.get(export)
        resp.raise_for_status()
        body = resp.text
        status = resp.status_code
    return FetchResult(
        requested_url=url,
        final_url=url,
        status_code=status,
        html=_wrap_plain_as_html("Google Docs export", body),
        mode="http",
    )


def is_xlsx_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".xlsx") or path.endswith(".xls")


def fetch_xlsx(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> FetchResult:
    """Download an Excel workbook and extract all sheets as TSV text."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
    }
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.content
        final_url = str(resp.url)
        status = resp.status_code
    if not data.startswith(b"PK"):
        raise ValueError(
            f"Expected xlsx bytes from {url}, got "
            f"{resp.headers.get('content-type')!r} ({len(data)} bytes)"
        )
    body = _xlsx_sheets_as_tsv(data)
    return FetchResult(
        requested_url=url,
        final_url=final_url,
        status_code=status,
        html=_wrap_plain_as_html("Excel workbook export", body),
        mode="http",
    )


def _xlsx_sheets_as_tsv(data: bytes) -> str:
    """Convert an .xlsx workbook into labeled TSV text (all sheets)."""
    import io
    import zipfile
    from xml.etree import ElementTree as ET

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    zf = zipfile.ZipFile(io.BytesIO(data))
    shared: list[str] = []
    if "xl/sharedStrings.xml" in zf.namelist():
        sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in sroot.findall("m:si", ns):
            shared.append(
                "".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
            )

    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rid_to_target: dict[str, str] = {}
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels:
        rid_to_target[rel.attrib.get("Id", "")] = rel.attrib.get("Target", "")

    parts: list[str] = []
    for sh in wb.findall("m:sheets/m:sheet", ns):
        name = sh.attrib.get("name") or "Sheet"
        rid = sh.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        target = rid_to_target.get(rid or "", "")
        if not target:
            continue
        path = "xl/" + target.lstrip("/")
        if path not in zf.namelist():
            continue
        root = ET.fromstring(zf.read(path))
        rows_out: list[str] = []
        for row in root.findall("m:sheetData/m:row", ns):
            cells: list[str] = []
            for c in row.findall("m:c", ns):
                v = c.find("m:v", ns)
                if v is None or v.text is None:
                    cells.append("")
                elif c.attrib.get("t") == "s":
                    try:
                        cells.append(shared[int(v.text)])
                    except (ValueError, IndexError):
                        cells.append(v.text)
                else:
                    cells.append(v.text)
            if any(x.strip() for x in cells):
                rows_out.append("\t".join(cells))
        if not rows_out:
            continue
        parts.append(f"### Sheet: {name}\n" + "\n".join(rows_out))
    if not parts:
        raise ValueError("xlsx export contained no sheet text")
    return "\n\n".join(parts)


def fetch_google_sheets_tsv(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> FetchResult:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    # No gid → pull the whole workbook (BME Depth Guide etc. put courses on later tabs).
    has_gid = bool(
        re.search(r"[#&?]gid=\d+", url or "")
        or re.search(r"gid=\d+", urlparse(url).fragment or "")
    )
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        if not has_gid:
            xlsx_url = google_sheets_xlsx_export_url(url)
            if xlsx_url:
                resp = client.get(xlsx_url)
                resp.raise_for_status()
                body = _xlsx_sheets_as_tsv(resp.content)
                return FetchResult(
                    requested_url=url,
                    final_url=url,
                    status_code=resp.status_code,
                    html=_wrap_plain_as_html("Google Sheet export (all tabs)", body),
                    mode="http",
                )
        export = google_sheets_export_url(url) or url
        resp = client.get(export)
        resp.raise_for_status()
        body = resp.text
        status = resp.status_code
    return FetchResult(
        requested_url=url,
        final_url=url,
        status_code=status,
        html=_wrap_plain_as_html("Google Sheet export", body),
        mode="http",
    )


def fetch_google_slides_txt(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> FetchResult:
    export = google_slides_export_url(url) or url
    headers = {"User-Agent": USER_AGENT, "Accept": "text/plain,*/*"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(export)
        resp.raise_for_status()
        body = resp.text
        status = resp.status_code
    # Keep the stable Slides URL — export redirects to a short-lived googleusercontent link.
    return FetchResult(
        requested_url=url,
        final_url=url,
        status_code=status,
        html=_wrap_plain_as_html("Google Slides export", body),
        mode="http",
    )


def fetch_page(
    url: str,
    *,
    force_browser: bool = False,
    min_chars: int = MIN_PAGE_TEXT_CHARS,
) -> tuple[FetchResult, str]:
    """HTTP first; Playwright if short / empty. Returns (FetchResult, llm_text)."""
    # PDFs / Docs / Sheets / Slides / Excel need specialized extractors (edit UIs are JS chrome).
    if is_pdf_url(url):
        try:
            fetched = fetch_pdf(url)
            return fetched, html_to_llm_input(fetched.html)
        except Exception:
            pass
    if is_xlsx_url(url):
        try:
            fetched = fetch_xlsx(url)
            return fetched, html_to_llm_input(fetched.html)
        except Exception:
            pass
    # Published Google Sheets (/d/e/2PACX-…) need the browser — no private export id.
    if is_google_published_sheet_url(url):
        fetched = fetch_page_browser(url)
        text = html_to_llm_input(fetched.html)
        if len(html_to_text(fetched.html)) < min(min_chars, 200):
            raise ValueError(f"Published Google Sheet too short for {url}")
        return fetched, text
    # Google Docs / Sheets / Slides edit UIs are Playwright chrome — never scrape them.
    # Prefer export endpoints; if those fail, raise instead of returning menu soup.
    if google_docs_export_url(url):
        fetched = fetch_google_docs_txt(url)
        text = html_to_llm_input(fetched.html)
        if len(html_to_text(fetched.html)) < min(min_chars, 200):
            raise ValueError(f"Google Docs export too short for {url}")
        return fetched, text
    if google_sheets_export_url(url):
        fetched = fetch_google_sheets_tsv(url)
        text = html_to_llm_input(fetched.html)
        if len(html_to_text(fetched.html)) < min(min_chars, 200):
            raise ValueError(f"Google Sheets export too short for {url}")
        return fetched, text
    if google_slides_export_url(url):
        fetched = fetch_google_slides_txt(url)
        text = html_to_llm_input(fetched.html)
        if len(html_to_text(fetched.html)) < min(min_chars, 200):
            raise ValueError(f"Google Slides export too short for {url}")
        return fetched, text

    if not force_browser:
        try:
            fetched = fetch_page_http(url)
            text = html_to_llm_input(fetched.html)
            if len(html_to_text(fetched.html)) >= min_chars:
                return fetched, text
        except Exception:
            pass
    fetched = fetch_page_browser(url)
    return fetched, html_to_llm_input(fetched.html)

#!/usr/bin/env python3
"""
Sensory Module — AI agent sensory input layer.
Connects AI tools to: web browsing (Playwright), text extraction (PDF/image/HTML),
web scraping, API calls, RSS feeds, and local file reading.

Registered as MCP tools via tools-mcp-server.py. Accessible via /sensory command.

Architecture:
  Each function is a pure handler: dict in -> dict out.
  Playwright is lazy-loaded (only when browse_* is called).
  All external I/O has configurable timeouts and error wrapping.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lazy-loaded dependencies
# ---------------------------------------------------------------------------

_playwright = None
_playwright_browser = None
_pdfplumber = None
_trafilatura = None
_bs4 = None
_requests = None


def _get_requests():
    global _requests
    if _requests is None:
        import requests as _r

        _requests = _r
    return _requests


def _get_bs4():
    global _bs4
    if _bs4 is None:
        from bs4 import BeautifulSoup as _Soup

        _bs4 = _Soup
    return _bs4


def _get_pdfplumber():
    global _pdfplumber
    if _pdfplumber is None:
        import pdfplumber as _p  # type: ignore

        _pdfplumber = _p
    return _pdfplumber


def _get_trafilatura():
    global _trafilatura
    if _trafilatura is None:
        import trafilatura as _t  # type: ignore

        _trafilatura = _t
    return _trafilatura


def _get_playwright():
    global _playwright, _playwright_browser
    if _playwright is None:
        from playwright.sync_api import sync_playwright

        _playwright = sync_playwright().start()
    return _playwright


def _ensure_playwright_browser():
    pw = _get_playwright()
    global _playwright_browser
    if _playwright_browser is None or not _playwright_browser.is_connected():
        _playwright_browser = pw.firefox.launch(headless=True)
    return _playwright_browser


def _close_playwright():
    global _playwright, _playwright_browser
    if _playwright_browser:
        try:
            _playwright_browser.close()
        except Exception:
            pass
        _playwright_browser = None
    if _playwright:
        try:
            _playwright.stop()
        except Exception:
            pass
        _playwright = None


# ---------------------------------------------------------------------------
# Web Browsing (Playwright)
# ---------------------------------------------------------------------------


def browse_url(url: str, extract_mode: str = "text", timeout_ms: int = 30000) -> dict:
    """
    Navigate to URL and extract content.
    extract_mode: "text" (plain text), "html" (raw HTML), "markdown" (trafilatura clean),
                  "links" (all hyperlinks), "metadata" (title, description, og tags)
    Returns: {url, title, content, extracted_at, content_length}
    """
    # SSRF protection
    safe_url = _validate_url(url)
    if safe_url is None:
        return {
            "status": "error",
            "error": f"URL blocked by security policy: {url[:80]}",
            "url": url,
        }
    url = safe_url
    try:
        browser = _ensure_playwright_browser()
        page = browser.new_page()
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        title = page.title()
        result: dict[str, Any] = {
            "url": page.url,
            "title": title,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
        }

        if extract_mode == "text":
            text = page.inner_text("body")
            result["content"] = text[:50000]
            result["content_length"] = len(text)
        elif extract_mode == "html":
            html = page.content()
            result["content"] = html[:100000]
            result["content_length"] = len(html)
        elif extract_mode == "markdown":
            html = page.content()
            t = _get_trafilatura()
            md = t.extract(html, include_links=True, include_tables=True) or ""
            result["content"] = md[:50000]
            result["content_length"] = len(md)
        elif extract_mode == "links":
            links = page.eval_on_selector_all(
                "a[href]",
                """
                els => els.map(e => ({
                    text: e.innerText.trim().substring(0, 200),
                    href: e.href,
                    title: e.title || ''
                }))
            """,
            )
            result["content"] = links[:500]
            result["content_length"] = len(links)
        elif extract_mode == "metadata":
            meta = page.evaluate("""() => {
                const get = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.getAttribute('content') || el.innerText : '';
                };
                return {
                    description: get('meta[name="description"]'),
                    og_title: get('meta[property="og:title"]'),
                    og_description: get('meta[property="og:description"]'),
                    og_image: get('meta[property="og:image"]'),
                    og_type: get('meta[property="og:type"]'),
                    canonical: get('link[rel="canonical"]') || window.location.href,
                    language: document.documentElement.lang || '',
                    keywords: get('meta[name="keywords"]'),
                };
            }""")
            result["content"] = meta
        else:
            result["status"] = "error"
            result["error"] = f"Unknown extract_mode: {extract_mode}"

        page.close()
        return result

    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


def browse_screenshot(url: str, output_path: str = "", timeout_ms: int = 30000) -> dict:
    """Navigate to URL and capture a screenshot. Returns path to screenshot file."""
    safe_url = _validate_url(url)
    if safe_url is None:
        return {
            "status": "error",
            "error": f"URL blocked by security policy: {url[:80]}",
            "url": url,
        }
    url = safe_url
    try:
        browser = _ensure_playwright_browser()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        if not output_path:
            out_dir = Path(tempfile.gettempdir()) / "sensory_screenshots"
            out_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = re.sub(r"[^a-zA-Z0-9]", "_", url[:60]).strip("_")
            output_path = str(out_dir / f"{ts}_{slug}.png")

        page.screenshot(path=output_path, full_page=False)
        page.close()

        return {
            "status": "ok",
            "url": url,
            "screenshot_path": output_path,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


def browse_interact(url: str, actions: list, timeout_ms: int = 30000) -> dict:
    """
    Navigate to URL and perform a sequence of actions.
    Each action: {"type": "click"|"type"|"wait", "selector": "...", "value": "..."}
    Returns: final page state.
    """
    safe_url = _validate_url(url)
    if safe_url is None:
        return {
            "status": "error",
            "error": f"URL blocked by security policy: {url[:80]}",
            "url": url,
        }
    url = safe_url
    try:
        browser = _ensure_playwright_browser()
        page = browser.new_page()
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        results = []
        for i, action in enumerate(actions):
            act_type = action.get("type", "")
            selector = action.get("selector", "")
            value = action.get("value", "")
            try:
                if act_type == "click":
                    page.click(selector, timeout=10000)
                    results.append(
                        {"step": i, "action": "click", "selector": selector, "ok": True}
                    )
                elif act_type == "type":
                    page.fill(selector, value, timeout=10000)
                    results.append(
                        {"step": i, "action": "type", "selector": selector, "ok": True}
                    )
                elif act_type == "press":
                    page.keyboard.press(value)
                    results.append(
                        {"step": i, "action": "press", "key": value, "ok": True}
                    )
                elif act_type == "wait":
                    page.wait_for_selector(value, timeout=10000)
                    results.append(
                        {"step": i, "action": "wait", "selector": value, "ok": True}
                    )
                else:
                    results.append(
                        {
                            "step": i,
                            "action": act_type,
                            "ok": False,
                            "error": "unknown action",
                        }
                    )
            except Exception as e:
                results.append(
                    {"step": i, "action": act_type, "ok": False, "error": str(e)}
                )

        final_text = page.inner_text("body")[:20000]
        page.close()

        return {
            "status": "ok",
            "url": url,
            "actions_executed": results,
            "final_text": final_text,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------


def extract_from_pdf(file_path: str, max_pages: int = 50) -> dict:
    """Extract text from a PDF file. Returns pages as list of text strings."""
    safe_path = _sanitize_path(file_path)
    if safe_path is None:
        return {
            "status": "error",
            "error": f"Path blocked by security policy (outside project root): {file_path[:120]}",
        }
    file_path = safe_path
    try:
        pdf = _get_pdfplumber()
        pages = []
        with pdf.open(file_path) as doc:
            total = len(doc.pages)
            for i, page in enumerate(doc.pages[:max_pages]):
                text = page.extract_text() or ""
                pages.append({"page": i + 1, "text": text})
        return {
            "status": "ok",
            "file": file_path,
            "total_pages": total,
            "pages_extracted": len(pages),
            "pages": pages,
            "full_text": "\n\n".join(p["text"] for p in pages),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "file": file_path}


def extract_from_html(html_content: str, mode: str = "clean") -> dict:
    """
    Extract text from raw HTML.
    mode: "clean" (trafilatura), "soup" (BeautifulSoup raw), "tables" (HTML tables as list)
    """
    try:
        if mode == "clean":
            t = _get_trafilatura()
            text = (
                t.extract(html_content, include_links=True, include_tables=True) or ""
            )
            return {"status": "ok", "text": text, "length": len(text), "mode": "clean"}

        elif mode == "soup":
            Soup = _get_bs4()
            soup = Soup(html_content, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return {
                "status": "ok",
                "text": text[:50000],
                "length": len(text),
                "mode": "soup",
            }

        elif mode == "tables":
            Soup = _get_bs4()
            soup = Soup(html_content, "html.parser")
            tables = []
            for table in soup.find_all("table"):
                rows = []
                for tr in table.find_all("tr"):
                    cells = [
                        td.get_text(strip=True) for td in tr.find_all(["td", "th"])
                    ]
                    rows.append(cells)
                if rows:
                    tables.append(rows)
            return {
                "status": "ok",
                "tables": tables,
                "table_count": len(tables),
                "mode": "tables",
            }

        else:
            return {"status": "error", "error": f"Unknown mode: {mode}"}
    except Exception as e:
        return {"status": "error", "error": str(e), "mode": mode}


def extract_from_image(file_path: str) -> dict:
    """
    Extract text from image using OCR (pytesseract) if available,
    otherwise return image metadata.
    """
    safe_path = _sanitize_path(file_path)
    if safe_path is None:
        return {
            "status": "error",
            "error": f"Path blocked by security policy (outside project root): {file_path[:120]}",
        }
    file_path = safe_path
    try:
        from PIL import Image

        img = Image.open(file_path)
        meta = {
            "format": img.format,
            "mode": img.mode,
            "size": list(img.size),
            "info": {k: str(v)[:200] for k, v in img.info.items()},
        }

        # Try OCR
        try:
            import pytesseract

            text = pytesseract.image_to_string(img)
            return {
                "status": "ok",
                "file": file_path,
                "text": text.strip(),
                "length": len(text.strip()),
                "image_meta": meta,
                "ocr": True,
            }
        except ImportError:
            return {
                "status": "ok",
                "file": file_path,
                "text": None,
                "ocr": False,
                "image_meta": meta,
                "note": "pytesseract not installed; image metadata only",
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "file": file_path}


# ---------------------------------------------------------------------------
# Web Scraping (lightweight, no browser)
# ---------------------------------------------------------------------------


def scrape_url(url: str, mode: str = "text", headers: dict | None = None) -> dict:
    """
    Fetch URL via requests (no JS) and extract content.
    mode: "text", "html", "links", "tables", "json"
    """
    safe_url = _validate_url(url)
    if safe_url is None:
        return {
            "status": "error",
            "error": f"URL blocked by security policy: {url[:80]}",
            "url": url,
        }
    url = safe_url
    try:
        req = _get_requests()
        h = {"User-Agent": "Mozilla/5.0 (compatible; SensoryModule/1.0)"}
        if headers:
            h.update(headers)
        resp = req.get(url, headers=h, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        result = {
            "status": "ok",
            "url": url,
            "status_code": resp.status_code,
            "content_type": content_type,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        if mode == "json" or "json" in content_type:
            result["data"] = resp.json()
        elif mode == "html":
            result["content"] = resp.text[:100000]
        elif mode == "links":
            Soup = _get_bs4()
            soup = Soup(resp.text, "html.parser")
            links = []
            for a in soup.find_all("a", href=True):
                links.append({"text": a.get_text(strip=True)[:200], "href": a["href"]})
            result["content"] = links[:1000]
            result["link_count"] = len(links)
        elif mode == "tables":
            Soup = _get_bs4()
            soup = Soup(resp.text, "html.parser")
            tables = []
            for table in soup.find_all("table"):
                rows = []
                for tr in table.find_all("tr"):
                    cells = [
                        td.get_text(strip=True) for td in tr.find_all(["td", "th"])
                    ]
                    rows.append(cells)
                if rows:
                    tables.append(rows)
            result["tables"] = tables
            result["table_count"] = len(tables)
        else:  # text
            Soup = _get_bs4()
            soup = Soup(resp.text, "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            result["content"] = text[:50000]
            result["content_length"] = len(text)

        return result
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


def scrape_extract_article(url: str) -> dict:
    """Use trafilatura to extract clean article content from a URL."""
    safe_url = _validate_url(url)
    if safe_url is None:
        return {
            "status": "error",
            "error": f"URL blocked by security policy: {url[:80]}",
            "url": url,
        }
    url = safe_url
    try:
        req = _get_requests()
        resp = req.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        t = _get_trafilatura()
        article = t.extract(
            resp.json if "json" in resp.headers.get("content-type", "") else resp.text,
            include_links=True,
            include_tables=True,
            favor_precision=False,
        )
        meta = t.extract_metadata(resp.text)
        return {
            "status": "ok",
            "url": url,
            "title": meta.title if meta else None,
            "author": meta.author if meta else None,
            "date": meta.date if meta else None,
            "text": article or "",
            "length": len(article or ""),
            "categories": meta.categories if meta else [],
            "tags": meta.tags if meta else [],
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


# ---------------------------------------------------------------------------
# API / Data Pipeline Connectors
# ---------------------------------------------------------------------------


def api_request(
    url: str,
    method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: int = 15,
) -> dict:
    """
    General-purpose HTTP request. Returns structured response.
    method: GET, POST, PUT, DELETE, PATCH
    """
    safe_url = _validate_url(url)
    if safe_url is None:
        return {
            "status": "error",
            "error": f"URL blocked by security policy: {url[:80]}",
            "url": url,
        }
    url = safe_url
    try:
        req = _get_requests()
        h = {"User-Agent": "SensoryModule/1.0"}
        if headers:
            h.update(headers)

        kwargs = {"headers": h, "timeout": timeout}
        if params:
            kwargs["params"] = params
        if data and method in ("POST", "PUT", "PATCH"):
            if h.get("Content-Type", "") == "application/json" or "json" in str(
                headers
            ):
                kwargs["json"] = data
            else:
                kwargs["data"] = data

        resp = req.request(method, url, **kwargs)
        result = {
            "status": "ok",
            "url": url,
            "method": method,
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            result["body"] = resp.json()
        except Exception:
            result["body"] = resp.text[:50000]
        return result
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url, "method": method}


def fetch_rss(feed_url: str, max_items: int = 50) -> dict:
    """Parse an RSS/Atom feed and return structured items."""
    try:
        req = _get_requests()
        resp = req.get(
            feed_url, headers={"User-Agent": "SensoryModule/1.0"}, timeout=15
        )
        resp.raise_for_status()
        Soup = _get_bs4()
        soup = Soup(resp.text, "html.parser")

        items = []
        # RSS 2.0
        for item in soup.find_all("item")[:max_items]:
            entry = {}
            for field in [
                "title",
                "description",
                "link",
                "pubDate",
                "author",
                "category",
            ]:
                tag = item.find(field)
                if tag:
                    entry[field] = tag.get_text(strip=True)
            if entry:
                items.append(entry)

        # Atom fallback
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in soup.find_all("entry")[:max_items]:
                item = {}
                for field in ["title", "summary", "link", "updated", "author"]:
                    tag = entry.find(field) or entry.find(
                        f"atom:{field}", attrs=dict(ns)
                    )
                    if tag:
                        item[field] = tag.get_text(strip=True)
                        if field == "link":
                            item[field] = tag.get("href", item[field])
                if item:
                    items.append(item)

        feed_title = ""
        title_tag = soup.find("title")
        if title_tag:
            feed_title = title_tag.get_text(strip=True)

        return {
            "status": "ok",
            "feed_url": feed_url,
            "feed_title": feed_title,
            "item_count": len(items),
            "items": items,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "feed_url": feed_url}


# ---------------------------------------------------------------------------
# Security: Path sanitization & SSRF protection
# ---------------------------------------------------------------------------

# Allowed base directory for file operations (project root or subdirs)
_ALLOWED_FILE_ROOTS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),  # project root
]

# Blocked IP ranges for SSRF protection (private, loopback, link-local, cloud metadata)
_BLOCKED_SSRF_PREFIXES = [
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
    "169.254.",
    "0.",
    "127.",
    "100.",
]
_BLOCKED_SSRF_HOSTS = {"localhost", "localhost.localdomain", "::1", "0.0.0.0"}
_BLOCKED_SSRF_METADATA = ["169.254.169.254", "100.100.100.200", "fd00:ec2::254"]


def _sanitize_path(file_path: str) -> str | None:
    """Resolve and validate a file path. Returns resolved path or None if blocked."""
    try:
        resolved = os.path.abspath(os.path.normpath(file_path))
        for root in _ALLOWED_FILE_ROOTS:
            norm_root = os.path.normpath(root)
            if resolved.startswith(norm_root):
                return resolved
        return None
    except (ValueError, OSError):
        return None


def _validate_url(url: str) -> str | None:
    """Validate and sanitize a URL. Returns URL string or None if blocked.

    Blocks:
    - Non-http(s) protocols (file://, ftp://, etc.)
    - Private IP ranges (10.x, 172.16-31.x, 192.168.x)
    - Loopback (127.x, localhost, ::1)
    - Link-local (169.254.x)
    - Cloud metadata endpoints
    - DNS rebinding: resolves hostname and checks IP against blocklist
    """
    import urllib.parse

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return None

    # Protocol whitelist
    if parsed.scheme not in ("http", "https"):
        return None

    hostname = parsed.hostname or ""

    # Block by hostname
    if hostname.lower() in _BLOCKED_SSRF_HOSTS:
        return None
    if hostname.lower() in _BLOCKED_SSRF_METADATA:
        return None

    # Block by IP prefix (covers literal IPs like 10.0.0.1)
    for prefix in _BLOCKED_SSRF_PREFIXES:
        if hostname.startswith(prefix):
            return None

    # Resolve DNS to catch rebinding attacks (e.g. nip.io, xip.io)
    try:
        import socket

        # Try IPv4 first, fall back to IPv6
        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                addrs = socket.getaddrinfo(hostname, 80, family=family)
            except socket.gaierror:
                continue
            for addr in addrs:
                ip = addr[4][0]
                # IPv4 private range check
                if "." in ip:
                    for prefix in _BLOCKED_SSRF_PREFIXES:
                        if ip.startswith(prefix):
                            return None
                    if ip in _BLOCKED_SSRF_METADATA:
                        return None
                    octet = int(ip.split(".")[0])
                    if octet in (127, 0):
                        return None
                # IPv6 private/loopback/link-local check
                elif ":" in ip:
                    if ip == "::1":
                        return None
                    first_hex = ip.split(":")[0]
                    # unique-local (fc00::/7 → fc00-fdff)
                    if first_hex.startswith("fd") or first_hex.startswith("fc"):
                        return None
                    # link-local (fe80::/10 → fe80-febf)
                    if (
                        first_hex.startswith("fe8")
                        or first_hex.startswith("fe9")
                        or first_hex.startswith("fea")
                        or first_hex.startswith("feb")
                    ):
                        return None
    except (socket.gaierror, OSError):
        pass  # unresolvable or no network — let caller decide

    return url


# ---------------------------------------------------------------------------
# Local File Reading
# ---------------------------------------------------------------------------


def read_file(file_path: str, max_size_kb: int = 500) -> dict:
    """
    Read a local file and extract content. Handles: .txt, .md, .json, .csv,
    .py, .js, .ts, .ps1, .yaml, .toml, .xml, .html, .css, .log
    Returns: {path, extension, size_bytes, content, content_length}

    Security: Path traversal is blocked — files must reside within the project root.
    """
    safe_path = _sanitize_path(file_path)
    if safe_path is None:
        return {
            "status": "error",
            "error": f"Path blocked by security policy (outside project root): {file_path[:120]}",
        }
    try:
        p = Path(safe_path)

        size = p.stat().st_size
        if size > max_size_kb * 1024:
            return {
                "status": "error",
                "error": f"File too large: {size / 1024:.0f}KB > {max_size_kb}KB limit",
            }

        ext = p.suffix.lower()
        text_exts = {
            ".txt",
            ".md",
            ".py",
            ".js",
            ".ts",
            ".ps1",
            ".yaml",
            ".yml",
            ".toml",
            ".xml",
            ".html",
            ".css",
            ".log",
            ".csv",
            ".json",
            ".sh",
            ".bash",
            ".go",
            ".rs",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".sql",
            ".env",
            ".gitignore",
            ".opencode",
            ".jsonc",
        }

        if ext in text_exts or not ext:
            content = p.read_text(encoding="utf-8", errors="replace")
            return {
                "status": "ok",
                "path": str(p),
                "extension": ext,
                "size_bytes": size,
                "content": content[:200000],
                "content_length": len(content),
            }
        else:
            return {
                "status": "ok",
                "path": str(p),
                "extension": ext,
                "size_bytes": size,
                "content": None,
                "note": f"Binary file ({ext}); use extract_from_pdf or extract_from_image for specific types",
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "file": file_path}


# ---------------------------------------------------------------------------
# Search (web search via requests)
# ---------------------------------------------------------------------------


def web_search(query: str, num_results: int = 8) -> dict:
    """
    Perform a web search using DuckDuckGo HTML (no API key needed).
    Returns structured search results.
    """
    try:
        req = _get_requests()
        resp = req.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()
        Soup = _get_bs4()
        soup = Soup(resp.text, "html.parser")

        results = []
        for result_div in soup.find_all("div", class_="result")[:num_results]:
            title_tag = result_div.find("a", class_="result__a")
            snippet_tag = result_div.find("a", class_="result__snippet")
            if title_tag:
                results.append(
                    {
                        "title": title_tag.get_text(strip=True),
                        "url": title_tag.get("href", ""),
                        "snippet": snippet_tag.get_text(strip=True)
                        if snippet_tag
                        else "",
                    }
                )

        return {
            "status": "ok",
            "query": query,
            "result_count": len(results),
            "results": results,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "query": query}


# ---------------------------------------------------------------------------
# MCP Tool Definitions (for registration in tools-mcp-server.py)
# ---------------------------------------------------------------------------

SENSORY_TOOLS = [
    {
        "name": "sensory_browse",
        "description": "Navigate to a URL using Playwright (headless Firefox) and extract content. Modes: text, html, markdown, links, metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to browse"},
                "extract_mode": {
                    "type": "string",
                    "enum": ["text", "html", "markdown", "links", "metadata"],
                    "default": "text",
                },
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "sensory_screenshot",
        "description": "Take a screenshot of a web page via Playwright",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to screenshot"},
                "output_path": {
                    "type": "string",
                    "description": "Optional output file path",
                },
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "sensory_interact",
        "description": "Navigate to URL and perform actions (click, type, press, wait)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["click", "type", "press", "wait"],
                            },
                            "selector": {"type": "string"},
                            "value": {"type": "string"},
                        },
                    },
                },
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url", "actions"],
        },
    },
    {
        "name": "sensory_extract_pdf",
        "description": "Extract text from a PDF file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to PDF file"},
                "max_pages": {"type": "integer", "default": 50},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "sensory_extract_html",
        "description": "Extract text from raw HTML content. Modes: clean (trafilatura), soup (BeautifulSoup), tables",
        "inputSchema": {
            "type": "object",
            "properties": {
                "html_content": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["clean", "soup", "tables"],
                    "default": "clean",
                },
            },
            "required": ["html_content"],
        },
    },
    {
        "name": "sensory_extract_image",
        "description": "Extract text from an image via OCR (if pytesseract installed) or return image metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to image file"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "sensory_scrape",
        "description": "Fetch a URL via HTTP (no JS) and extract content. Modes: text, html, links, tables, json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["text", "html", "links", "tables", "json"],
                    "default": "text",
                },
                "headers": {"type": "object"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "sensory_extract_article",
        "description": "Extract clean article content from a URL using trafilatura",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "sensory_api_request",
        "description": "Make an HTTP API request (GET/POST/PUT/DELETE/PATCH) with structured response",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "default": "GET",
                },
                "data": {"type": "object"},
                "headers": {"type": "object"},
                "params": {"type": "object"},
                "timeout": {"type": "integer", "default": 15},
            },
            "required": ["url"],
        },
    },
    {
        "name": "sensory_fetch_rss",
        "description": "Parse an RSS/Atom feed and return structured items",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feed_url": {"type": "string"},
                "max_items": {"type": "integer", "default": 50},
            },
            "required": ["feed_url"],
        },
    },
    {
        "name": "sensory_read_file",
        "description": "Read a local text file and return its content",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "max_size_kb": {"type": "integer", "default": 500},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "sensory_search",
        "description": "Web search via DuckDuckGo (no API key needed). Returns title, URL, snippet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


def handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch MCP tool call to the appropriate handler function."""
    dispatch = {
        # MERGED: read_sensory_fetch replaces browse + scrape + extract_article
        "sensory_fetch": lambda a: (
            browse_url(a["url"], a.get("mode", "text"), a.get("timeout_ms", 30000))
            if a.get("method", "browser") == "browser"
            else scrape_url(a["url"], a.get("mode", "text"), a.get("headers"))
            if a.get("method") == "http"
            else scrape_extract_article(a["url"])
        ),
        "sensory_browse": lambda a: browse_url(
            a["url"], a.get("extract_mode", "text"), a.get("timeout_ms", 30000)
        ),
        "sensory_screenshot": lambda a: browse_screenshot(
            a["url"], a.get("output_path", ""), a.get("timeout_ms", 30000)
        ),
        "sensory_interact": lambda a: browse_interact(
            a["url"], a.get("actions", []), a.get("timeout_ms", 30000)
        ),
        "sensory_extract_pdf": lambda a: extract_from_pdf(
            a["file_path"], a.get("max_pages", 50)
        ),
        "sensory_extract_html": lambda a: extract_from_html(
            a["html_content"], a.get("mode", "clean")
        ),
        "sensory_extract_image": lambda a: extract_from_image(a["file_path"]),
        "sensory_scrape": lambda a: scrape_url(
            a["url"], a.get("mode", "text"), a.get("headers")
        ),
        "sensory_extract_article": lambda a: scrape_extract_article(a["url"]),
        "sensory_api_request": lambda a: api_request(
            a["url"],
            a.get("method", "GET"),
            a.get("data"),
            a.get("headers"),
            a.get("params"),
            a.get("timeout", 15),
        ),
        "sensory_fetch_rss": lambda a: fetch_rss(a["feed_url"], a.get("max_items", 50)),
        "sensory_read_file": lambda a: read_file(
            a["file_path"], a.get("max_size_kb", 500)
        ),
        "sensory_search": lambda a: web_search(a["query"], a.get("num_results", 8)),
        "sensory_set_browser_type": lambda a: {
            "status": "acknowledged",
            "browser_type": a.get("browser_type", "firefox"),
            "note": "Only Firefox is currently supported via Playwright",
        },
    }
    # Strip known prefixes before dispatch.
    # Dispatch keys use "sensory_*" form, so only strip "read_" or "write_".
    for prefix in ("read_", "write_"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    handler = dispatch.get(name)
    if handler:
        return handler(args)
    return {"status": "error", "error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# CLI entrypoint (for standalone testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python sensory-module.py <tool_name> <json_args>")
        print("Available tools:", ", ".join(t["name"] for t in SENSORY_TOOLS))
        sys.exit(1)

    tool_name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = handle_tool_call(tool_name, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    _close_playwright()

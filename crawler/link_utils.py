from __future__ import annotations

import posixpath
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import tldextract
from bs4 import BeautifulSoup

SKIP_SCHEMES = ("mailto:", "javascript:", "tel:", "data:")
SKIP_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".css",
    ".js",
    ".json",
    ".xml",
}
SKIP_PATH_HINTS = (
    "/login",
    "/logout",
    "/signin",
    "/sign-in",
    "/signup",
    "/sign-up",
    "/register",
    "/account",
    "/cart",
    "/checkout",
    "/wp-admin",
)


def canonicalize_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    normalized_path = re.sub(r"/+", "/", parsed.path or "/")
    normalized_path = posixpath.normpath(normalized_path)
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    if parsed.path.endswith("/") and not normalized_path.endswith("/"):
        normalized_path = f"{normalized_path}/"

    normalized = parsed._replace(
        params="",
        query="",
        fragment="",
        path=normalized_path,
    )
    return urlunparse(normalized)


def get_registered_domain(url: str) -> str:
    extracted = tldextract.extract(url)
    parts = [part for part in (extracted.domain, extracted.suffix) if part]
    return ".".join(parts)


def is_same_domain(url: str, root_domain: str) -> bool:
    return get_registered_domain(url) == root_domain


def should_skip_url(url: str) -> bool:
    lowered = url.lower()
    if any(lowered.startswith(prefix) for prefix in SKIP_SCHEMES):
        return True

    parsed = urlparse(lowered)
    if any(hint in parsed.path for hint in SKIP_PATH_HINTS):
        return True
    if any(parsed.path.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    return False


def normalize_candidate_link(href: str, base_url: str, root_domain: str) -> str | None:
    if not href or should_skip_url(href):
        return None

    absolute = urljoin(base_url, href)
    canonical = canonicalize_url(absolute)
    if not canonical or should_skip_url(canonical):
        return None
    if not is_same_domain(canonical, root_domain):
        return None
    return canonical


def extract_links_from_html(html: str, base_url: str, root_domain: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        normalized = normalize_candidate_link(anchor["href"], base_url, root_domain)
        if normalized and normalized not in seen:
            seen.add(normalized)
            links.append(normalized)

    return links


def dedupe_urls(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered

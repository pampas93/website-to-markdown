from __future__ import annotations

from dataclasses import dataclass

import trafilatura
from bs4 import BeautifulSoup
from markdownify import markdownify as to_markdown
from readability import Document


@dataclass(slots=True)
class ExtractionResult:
    title: str
    markdown: str
    html_for_links: str
    method: str


def _clean_markdown(markdown: str) -> str:
    lines = [line.rstrip() for line in markdown.splitlines()]
    cleaned: list[str] = []
    blank_count = 0

    for line in lines:
        if line.strip():
            cleaned.append(line)
            blank_count = 0
            continue
        if blank_count < 1:
            cleaned.append("")
        blank_count += 1

    return "\n".join(cleaned).strip()


def _extract_title_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    heading = soup.find(["h1", "h2"])
    if heading:
        return heading.get_text(" ", strip=True)
    return "Untitled"


def extract_main_content(html: str, url: str) -> ExtractionResult | None:
    document_title = _extract_title_from_html(html)
    try:
        trafilatura_html = trafilatura.extract(
            html,
            url=url,
            output_format="html",
            include_links=True,
            include_images=False,
            include_tables=True,
            favor_recall=True,
        )
    except Exception:
        trafilatura_html = None

    if trafilatura_html:
        title = _extract_title_from_html(trafilatura_html)
        if title == "Untitled":
            title = document_title
        markdown = _clean_markdown(to_markdown(trafilatura_html, heading_style="ATX"))
        if markdown:
            return ExtractionResult(
                title=title,
                markdown=markdown,
                html_for_links=trafilatura_html,
                method="trafilatura",
            )

    try:
        document = Document(html)
        summary_html = document.summary(html_partial=True)
        title = document.short_title() or _extract_title_from_html(summary_html) or document_title
        markdown = _clean_markdown(to_markdown(summary_html, heading_style="ATX"))
        if markdown:
            return ExtractionResult(
                title=title.strip() or "Untitled",
                markdown=markdown,
                html_for_links=summary_html,
                method="readability",
            )
    except Exception:
        return None

    return None

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


def domain_to_folder_name(domain: str) -> str:
    return domain.replace(".", "-")


def slugify_filename(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "page"


def build_output_path(base_output: Path, domain: str, url: str, title: str) -> Path:
    domain_dir = base_output / domain_to_folder_name(domain)
    domain_dir.mkdir(parents=True, exist_ok=True)

    parsed = urlparse(url)
    path_bits = [segment for segment in parsed.path.split("/") if segment]
    if not path_bits:
        filename = "index"
    else:
        filename = "-".join(path_bits[-2:]) if len(path_bits) > 1 else path_bits[-1]

    if not filename or filename == "-":
        filename = slugify_filename(title)

    candidate = domain_dir / f"{slugify_filename(filename)}.md"
    suffix = 1
    while candidate.exists():
        stem = slugify_filename(title) or "page"
        candidate = domain_dir / f"{stem}-{suffix}.md"
        suffix += 1

    return candidate


def write_markdown(base_output: Path, domain: str, url: str, title: str, markdown: str) -> Path:
    output_path = build_output_path(base_output, domain, url, title)
    content = f"# {title}\n\nSource: {url}\n\n{markdown.strip()}\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path

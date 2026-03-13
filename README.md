# Website to Markdown RAG Crawler

An open-source Python crawler that starts from one or more URLs, extracts only the main article or page content, follows internal links found inside that content, and writes clean Markdown files for downstream retrieval-augmented generation (RAG) pipelines.

## Features

- Crawls recursively from one or more starting URLs
- Restricts crawling to the same domain
- Ignores query parameters and duplicate URLs
- Respects `robots.txt`
- Supports configurable depth, concurrency, request delay, and page limits
- Extracts main content with `trafilatura`
- Falls back to `readability-lxml` when needed
- Converts clean HTML/text into Markdown
- Skips obvious non-content pages and unsupported links
- Writes one Markdown file per page under a domain-based output folder

## Project Structure

```text
website-to-markdown-rag-crawler/
├── README.md
├── requirements.txt
├── main.py
├── crawler/
│   ├── __init__.py
│   ├── crawler.py
│   ├── extractor.py
│   ├── link_utils.py
│   └── markdown_writer.py
└── output/
```

## Requirements

- Python 3.11+

Validated locally with:

- Python 3.11
- Python 3.14

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you want to use Python 3.14 instead:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Basic usage:

```bash
python main.py https://example.com
```

Multiple starting URLs:

```bash
python main.py https://example.com https://docs.python.org/3/
```

With options:

```bash
python main.py https://example.com \
  --depth 2 \
  --max-pages 50 \
  --output-folder output \
  --concurrency 5 \
  --delay 0.5
```

## CLI Options

- `--depth`: Maximum crawl depth from each starting URL
- `--max-pages`: Maximum number of pages to fetch
- `--output-folder`: Base folder for Markdown output
- `--concurrency`: Number of concurrent fetch workers
- `--delay`: Delay in seconds between requests per worker
- `--timeout`: HTTP timeout in seconds
- `--user-agent`: Override the crawler user agent

## Output Format

Each crawled page is written as Markdown:

```markdown
# Page Title

Source: https://example.com/page

Main page content in Markdown...
```

Files are written to:

```text
output/
└── example-com/
    ├── index.md
    ├── about.md
    └── docs-getting-started.md
```

## How This Helps RAG Systems

RAG systems work better when source documents are:

- Clean and focused on meaningful content
- Free of repeated navigation, banners, and boilerplate
- Split into stable page-level files
- Preserved with source attribution for traceability

This crawler prepares a website as a lightweight Markdown knowledge base. That output is easier to chunk, embed, index, and trace back to original URLs in a retrieval pipeline.

## Notes

- The crawler follows only internal links discovered inside extracted main content
- When multiple starting URLs are provided, each URL is crawled independently within its own domain boundary
- Query strings and fragments are ignored for deduplication
- Links such as `javascript:`, `mailto:`, login/account pages, and common non-HTML assets are skipped
- `requirements.txt` pins `chardet<6` to avoid a known `requests` compatibility warning in Python 3.14 environments where a transitive dependency installs `chardet` 7.x
- Some websites rely heavily on client-side rendering; this project does not run a browser, so such pages may produce limited output

## License

MIT

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import robotparser

import aiohttp
import requests

from .extractor import extract_main_content
from .link_utils import canonicalize_url, dedupe_urls, extract_links_from_html, get_registered_domain
from .markdown_writer import write_markdown


DEFAULT_USER_AGENT = (
    "website-to-markdown-rag-crawler/1.0 "
    "(+https://github.com/pampas93/website-to-markdown)"
)
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(slots=True)
class CrawlConfig:
    start_urls: list[str]
    max_depth: int
    max_pages: int
    output_folder: Path
    concurrency: int
    delay: float
    timeout: float
    user_agent: str


class RobotsCache:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self._cache: dict[str, robotparser.RobotFileParser] = {}
        self._lock = asyncio.Lock()

    async def allowed(self, session: aiohttp.ClientSession, url: str) -> bool:
        parsed_url = aiohttp.client_reqrep.URL(url)
        robots_url = str(parsed_url.origin().with_path("/robots.txt").with_query({}))

        async with self._lock:
            parser = self._cache.get(robots_url)
            if parser is None:
                parser = robotparser.RobotFileParser()
                parser.set_url(robots_url)
                try:
                    async with session.get(robots_url) as response:
                        if response.status == 200:
                            parser.parse((await response.text()).splitlines())
                        else:
                            parser.parse([])
                except Exception:
                    parser.parse([])
                self._cache[robots_url] = parser

        return parser.can_fetch(self.user_agent, url)


class WebsiteCrawler:
    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self.start_urls = [canonicalize_url(url) for url in config.start_urls]
        if not self.start_urls or any(url is None for url in self.start_urls):
            raise ValueError("All start URLs must be valid http/https URLs.")

        self.start_urls = [url for url in self.start_urls if url is not None]
        self.visited: set[str] = set()
        self.enqueued: set[str] = set(self.start_urls)
        self.queue: asyncio.Queue[tuple[str, int, str]] = asyncio.Queue()
        self.robots = RobotsCache(config.user_agent)
        self.pages_written = 0
        self._page_lock = asyncio.Lock()

    async def crawl(self) -> int:
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        headers = {"User-Agent": self.config.user_agent, **DEFAULT_HEADERS}
        connector = aiohttp.TCPConnector(limit_per_host=self.config.concurrency)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector) as session:
            for start_url in self.start_urls:
                await self.queue.put((start_url, 0, get_registered_domain(start_url)))
            workers = [asyncio.create_task(self._worker(session)) for _ in range(self.config.concurrency)]
            await self.queue.join()
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        return self.pages_written

    async def _worker(self, session: aiohttp.ClientSession) -> None:
        while True:
            url, depth, root_domain = await self.queue.get()
            try:
                await self._process_url(session, url, depth, root_domain)
            except Exception:
                pass
            finally:
                self.queue.task_done()

    async def _process_url(
        self,
        session: aiohttp.ClientSession,
        url: str,
        depth: int,
        root_domain: str,
    ) -> None:
        if url in self.visited:
            return

        async with self._page_lock:
            if self.pages_written >= self.config.max_pages:
                return
            self.visited.add(url)

        allowed = await self.robots.allowed(session, url)
        if not allowed:
            return

        html = await self._fetch_html(session, url)
        if not html:
            return

        extracted = extract_main_content(html, url)
        if not extracted:
            return

        write_markdown(
            base_output=self.config.output_folder,
            domain=root_domain,
            url=url,
            title=extracted.title,
            markdown=extracted.markdown,
        )

        async with self._page_lock:
            self.pages_written += 1
            if self.pages_written >= self.config.max_pages:
                return

        if depth >= self.config.max_depth:
            return

        links = extract_links_from_html(extracted.html_for_links, url, root_domain)
        for link in dedupe_urls(links):
            if link in self.visited or link in self.enqueued:
                continue
            self.enqueued.add(link)
            await self.queue.put((link, depth + 1, root_domain))

    async def _fetch_html(self, session: aiohttp.ClientSession, url: str) -> str | None:
        await asyncio.sleep(self.config.delay)
        try:
            async with session.get(url, allow_redirects=True) as response:
                if response.status in {403, 429}:
                    return await self._fetch_html_with_requests(url)
                if response.status >= 400:
                    return None
                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    return None
                return await response.text(errors="ignore")
        except Exception:
            return await self._fetch_html_with_requests(url)

    async def _fetch_html_with_requests(self, url: str) -> str | None:
        def _request() -> str | None:
            try:
                response = requests.get(
                    url,
                    headers={"User-Agent": self.config.user_agent, **DEFAULT_HEADERS},
                    timeout=self.config.timeout,
                    allow_redirects=True,
                )
                if response.status_code >= 400:
                    return None
                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    return None
                response.encoding = response.encoding or response.apparent_encoding
                return response.text
            except Exception:
                return None

        return await asyncio.to_thread(_request)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl a website, extract main content, and write clean Markdown files.",
    )
    parser.add_argument("urls", nargs="+", help="One or more starting URLs to crawl")
    parser.add_argument("--depth", type=int, default=2, help="Maximum crawl depth")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum number of pages to crawl")
    parser.add_argument(
        "--output-folder",
        default="output",
        help="Base output directory for generated Markdown files",
    )
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent workers")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay in seconds between requests")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP user agent")
    return parser


def validate_args(args: argparse.Namespace) -> CrawlConfig:
    if args.depth < 0:
        raise ValueError("--depth must be >= 0")
    if args.max_pages <= 0:
        raise ValueError("--max-pages must be > 0")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be > 0")
    if args.delay < 0:
        raise ValueError("--delay must be >= 0")
    if args.timeout <= 0:
        raise ValueError("--timeout must be > 0")

    return CrawlConfig(
        start_urls=args.urls,
        max_depth=args.depth,
        max_pages=args.max_pages,
        output_folder=Path(args.output_folder),
        concurrency=args.concurrency,
        delay=args.delay,
        timeout=args.timeout,
        user_agent=args.user_agent,
    )


async def run_crawler(config: CrawlConfig) -> int:
    crawler = WebsiteCrawler(config)
    return await crawler.crawl()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = validate_args(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        pages_written = asyncio.run(run_crawler(config))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {pages_written} markdown file(s) to {config.output_folder}")
    return 0

import re
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
)

# Many modern sites render their content client-side (React/Next.js/Vue
# etc.). Crawl4AI's bare defaults can come back with just the empty JS
# shell for those - e.g. 0 visible chars, flagged internally as
# "script_heavy_shell" - which then produces nothing to chunk/embed.
# These options make it wait for the page to actually render before
# grabbing the markdown.
DEFAULT_CRAWL_CONFIG = CrawlerRunConfig(
    magic=True,
    simulate_user=True,
    wait_until="networkidle",
    delay_before_return_html=2.0,
)


class WebsiteCrawlerService:

    @staticmethod
    async def crawl_website(url: str, config: CrawlerRunConfig | None = None):
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=config or DEFAULT_CRAWL_CONFIG)
            return result

    @staticmethod
    def website_slug(url: str) -> str:
        """
        Derive a filesystem/collection-safe name from a URL's domain,
        e.g. "https://www.companiesnext.com/about" -> "companiesnext".

        Uses just the domain's first label (post "www.") rather than the
        full host, so it lines up with the collection names already used
        elsewhere in the app (e.g. the "companiesnext" collection queried
        by KnowledgeAgent) instead of producing "companiesnext_com".
        """
        host = urlparse(url).netloc.lower()

        if host.startswith("www."):
            host = host[4:]

        label = host.split(".")[0] if host else ""
        slug = re.sub(r"[^a-z0-9]+", "_", label).strip("_")

        return slug or "website"

    @staticmethod
    def discover_links(base_url: str, homepage_markdown: str) -> list[str]:
        """
        Find same-domain links inside the homepage's crawled markdown,
        filtering out asset links and the homepage/top-level links.
        """
        domain = urlparse(base_url).netloc

        if not domain:
            return []

        pattern = rf"https?://{re.escape(domain)}[^\s\)\]\"']*"
        links = re.findall(pattern, homepage_markdown or "")

        filtered_links = []

        for link in links:
            link = link.rstrip(".,);]")  # Remove trailing punctuation
            lowered = link.lower()
            path_only = lowered.split("?")[0]

            # Image assets - including ones proxied through a query string,
            # e.g. Next.js's "/_next/image?url=%2F...%2Flogo.png&w=256"
            # (the ".png" lives in the query, not the path).
            if any(ext in lowered for ext in IMAGE_EXTENSIONS):
                continue

            # Framework-internal static asset/image endpoints - never a
            # real content page.
            if "/_next/" in path_only:
                continue

            if len(path_only.rstrip("/").split("/")) <= 3:
                continue

            filtered_links.append(link)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(filtered_links))

    @classmethod
    async def crawl_and_save(
        cls,
        url: str,
        website: str | None = None,
        max_pages: int = 30,
    ) -> list[str]:
        """
        Crawl `url` plus same-domain pages linked from its homepage (up to
        `max_pages` total) and save each page's markdown under
        storage/websites/<website>/<slug>.txt.

        Already-saved pages are skipped, so re-running is cheap/resumable -
        except pages cached as empty/whitespace-only (a prior failed crawl:
        dead link, anti-bot block, etc.), which are retried rather than
        skipped. Pages that still end up empty after crawling are left out
        of the returned list, but still written to disk for inspection, so
        they don't produce empty chunks downstream.

        Returns the list of non-empty file paths written (as strings),
        ready to be passed to VectorService.extract_texts_from_files().
        """
        website = website or cls.website_slug(url)

        folder = Path(f"storage/websites/{website}")
        folder.mkdir(parents=True, exist_ok=True)

        saved_files: list[str] = []

        home_file = folder / f"001_{website}.txt"

        # Crawl homepage only once - unless the cached copy is empty,
        # meaning a prior attempt didn't actually get usable content.
        home_markdown = home_file.read_text(encoding="utf-8") if home_file.exists() else ""

        if not home_markdown.strip():
            home_result = await cls.crawl_website(url)
            home_markdown = home_result.markdown or ""
            home_file.write_text(home_markdown, encoding="utf-8")

        if home_markdown.strip():
            saved_files.append(str(home_file))

        links = cls.discover_links(url, home_markdown)
        remaining = max(max_pages - 1, 0)

        for link in links[:remaining]:
            slug = link.split("?")[0].rstrip("/").split("/")[-1] or website
            slug = re.sub(r"[^A-Za-z0-9_-]", "_", slug) or website
            file_path = folder / f"{slug}.txt"

            markdown = file_path.read_text(encoding="utf-8") if file_path.exists() else ""

            if not markdown.strip():
                result = await cls.crawl_website(link)
                markdown = result.markdown or ""
                file_path.write_text(markdown, encoding="utf-8")

            if markdown.strip():
                saved_files.append(str(file_path))

        return saved_files


async def main():
    website = "companiesnext"

    await WebsiteCrawlerService.crawl_and_save(
        "https://www.companiesnext.com",
        website=website,
    )


if __name__ == "__main__":
    asyncio.run(main())

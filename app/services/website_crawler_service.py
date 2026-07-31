import re
import asyncio
from pathlib import Path
from crawl4ai import AsyncWebCrawler


class WebsiteCrawlerService:

    @staticmethod
    async def crawl_website(url: str):
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return result


async def main():
    website = "companiesnext"

    folder = Path(f"storage/websites/{website}")
    folder.mkdir(parents=True, exist_ok=True)

    home_file = folder / f"001_{website}.txt"

    # Crawl homepage only once
    if not home_file.exists():
        result = await WebsiteCrawlerService.crawl_website(
            "https://www.companiesnext.com"
        )
        home_file.write_text(result.markdown, encoding="utf-8")

    text = home_file.read_text(encoding="utf-8")

    pattern = r"https://www\.companiesnext\.com[^\s\)\]\"']*"
    links = re.findall(pattern, text)

    image_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
    )

    # Filter links
    filtered_links = []
    for link in links:
        link = link.rstrip(".,);]")  # Remove trailing punctuation

        if link.lower().split("?")[0].endswith(image_extensions):
            continue

        if len(link.rstrip("/").split("/")) <= 3:
            continue

        filtered_links.append(link)

    # Remove duplicates while preserving order
    links = list(dict.fromkeys(filtered_links))

    print(f"Found {len(links)} links")

    for link in links:
        slug = link.rstrip("/").split("/")[-1]
        print(link)
        # print(f"Crawling: {slug}")

        file_path = folder / f"{slug}.txt"

        if file_path.exists():
            print(f"Skipping {slug} (already exists)")
            continue

        result = await WebsiteCrawlerService.crawl_website(link)

        file_path.write_text(
            result.markdown,
            encoding="utf-8",
        )
    print(f"\nTotal links: {len(links)}")
    # files = [str(file) for file in folder.iterdir() if file.is_file()]
    # print(f"\nTotal Files: {len(files)}")


if __name__ == "__main__":
    asyncio.run(main())
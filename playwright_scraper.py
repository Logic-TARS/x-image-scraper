"""
X 图片爬取 - Playwright 浏览器自动化模式
适用于需要登录或 Nitter 不可用时使用
依赖: pip install playwright && playwright install chromium
"""

import asyncio
import json
import re
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)


async def scrape_with_playwright(username: str, output_dir: str, max_scrolls: int = 20, headless: bool = True):
    """
    使用 Playwright 控制 Chrome 浏览器自动化爬取 X 媒体页。
    可选登录模式获取私密账号内容。
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("请先安装: pip install playwright && playwright install chromium")
        return []

    images = []
    seen_urls = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )

        # 拦截图片网络请求
        async def handle_response(response):
            url = response.url
            if "pbs.twimg.com/media/" in url and url not in seen_urls:
                # 转为原图 URL
                orig_url = re.sub(r"name=\w+", "name=orig", url)
                orig_url = re.sub(r"format=\w+", "format=jpg", orig_url)
                if "format=" not in orig_url:
                    orig_url += ("&" if "?" in orig_url else "?") + "format=jpg&name=orig"
                seen_urls.add(url)
                images.append({"url": orig_url, "tweet_id": "", "type": "photo"})
                log.info(f"捕获图片: {orig_url[-60:]}")

        page = await context.new_page()
        page.on("response", handle_response)

        # 导航到用户媒体页
        media_url = f"https://x.com/{username}/media"
        log.info(f"正在打开: {media_url}")
        await page.goto(media_url, wait_until="networkidle", timeout=30000)

        # 自动滚动加载更多图片
        for i in range(max_scrolls):
            prev_count = len(images)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            # 如果连续两次没有新图片则停止
            if len(images) == prev_count:
                log.info(f"第 {i+1} 次滚动无新内容，停止滚动")
                break
            log.info(f"滚动 {i+1}/{max_scrolls}，已捕获 {len(images)} 张")

        await browser.close()

    log.info(f"Playwright 模式完成，共捕获 {len(images)} 张图片")
    return images


# ── CLI 入口 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    import sys

    # 将父目录加入路径
    sys.path.insert(0, str(Path(__file__).parent))
    from scraper import ImageDownloader, ensure_dir, sanitize_filename

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Playwright 浏览器自动化爬取 X 图片")
    parser.add_argument("username", help="目标用户名（不含 @）")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    parser.add_argument("-s", "--scrolls", type=int, default=20, help="滚动次数")
    parser.add_argument("-w", "--workers", type=int, default=4, help="下载线程数")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口")
    args = parser.parse_args()

    output_dir = Path(args.output) / sanitize_filename(args.username)
    ensure_dir(str(output_dir))

    images = asyncio.run(
        scrape_with_playwright(
            args.username,
            str(output_dir),
            max_scrolls=args.scrolls,
            headless=not args.show_browser,
        )
    )

    if images:
        dl = ImageDownloader(str(output_dir), workers=args.workers)
        stats = dl.download_all(images)
        print(f"\n✅ 完成！下载: {stats['downloaded']} | 跳过: {stats['skipped']} | 失败: {stats['failed']}")
    else:
        print("⚠️  未捕获到任何图片")

"""CLI entry for logged-in X search scraping."""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from .browser import scrape_x_search
from .downloader import ImageDownloader
from .logging_utils import configure_logging
from .utils import ensure_dir, sanitize_filename

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="使用已登录 X Cookies 搜索并下载图片")
    parser.add_argument("--query", required=True, help="X 搜索查询")
    parser.add_argument("--cookies", default="x_cookies.json", help="由 xscrape-login 保存的 Cookies 文件")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    parser.add_argument("--name", default="x_search", help="输出子目录名")
    parser.add_argument("--top", type=int, default=10, help="按点赞数选取前 N 个媒体")
    parser.add_argument("-s", "--scrolls", type=int, default=20, help="搜索页滚动次数")
    parser.add_argument("-w", "--workers", type=int, default=4, help="下载线程数")
    parser.add_argument("--download-order", choices=["time", "likes"], default="time", help="下载排序")
    parser.add_argument("--tab", choices=["live", "top"], default="live", help="X 搜索 tab")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--proxy", help="代理服务器地址 (例如: http://127.0.0.1:7890)")
    parser.add_argument("--profile-dir", help="可选：直接复用持久化浏览器配置目录")
    parser.add_argument("--channel", default=None, help="浏览器通道: msedge, chrome, 或 chromium（默认使用 Playwright 内置 Chromium）")
    parser.add_argument("--quality-mode", action="store_true", help="按综合质量分排序：点赞、转发、引用、图片尺寸和排除词")
    return parser


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()

    output_dir = Path(args.output) / sanitize_filename(args.name)
    ensure_dir(str(output_dir))

    images = asyncio.run(
        scrape_x_search(
            args.query,
            top=args.top,
            max_scrolls=args.scrolls,
            headless=not args.show_browser,
            proxy=args.proxy,
            cookies_file=args.cookies,
            download_order=args.download_order,
            tab=args.tab,
            profile_dir=args.profile_dir,
            channel=None if args.channel == "chromium" else args.channel,
            quality_mode=args.quality_mode,
        )
    )

    if not images:
        log.warning("未从 X 搜索结果中解析到媒体。")
        return 0

    for index, item in enumerate(images, 1):
        original_tweet_id = item["tweet_id"]
        date = (item.get("created_at") or "unknown")[:10].replace("-", "")
        author = sanitize_filename(item.get("author_username") or "unknown")
        item["original_tweet_id"] = original_tweet_id
        item["tweet_id"] = f"{index:02d}_{date}_likes{item.get('like_count', 0)}_{author}_{original_tweet_id}"

    metadata_file = output_dir / "metadata.json"
    metadata_file.write_text(json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("元数据已保存: %s", metadata_file)

    downloader = ImageDownloader(str(output_dir), workers=args.workers, proxy=args.proxy)
    stats = downloader.download_all(images)
    log.info(
        "X 搜索下载完成！已下载: %s | 跳过: %s | 失败: %s",
        stats["downloaded"],
        stats["skipped"],
        stats["failed"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

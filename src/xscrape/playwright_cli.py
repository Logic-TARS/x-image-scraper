"""CLI entry for Playwright scraping mode."""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from .logging_utils import configure_logging
from .utils import ensure_dir, sanitize_filename

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Playwright 浏览器自动化爬取 X 图片")
    parser.add_argument("username", nargs="?", help="目标用户名（不含 @）")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    parser.add_argument("-s", "--scrolls", type=int, default=20, help="滚动次数")
    parser.add_argument("-w", "--workers", type=int, default=4, help="下载线程数")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--proxy", help="代理服务器地址 (例如: http://127.0.0.1:7890)")
    parser.add_argument("--batch", help="批量模式：包含用户名的文本文件路径（每行一个）")
    parser.add_argument("--cookies", help="包含 Playwright Cookies 的 JSON 文件路径")
    return parser


def process_user(username: str, args: argparse.Namespace) -> int:
    from .browser import scrape_with_playwright
    from .downloader import ImageDownloader

    output_dir = Path(args.output) / sanitize_filename(username)
    ensure_dir(str(output_dir))

    images = asyncio.run(
        scrape_with_playwright(
            username,
            max_scrolls=args.scrolls,
            headless=not args.show_browser,
            proxy=args.proxy,
            cookies_file=args.cookies,
        )
    )

    if not images:
        log.warning("用户 @%s 未捕获到任何图片/视频", username)
        return 0

    metadata_file = output_dir / "metadata.json"
    metadata_file.write_text(json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("元数据已保存: %s", metadata_file)

    downloader = ImageDownloader(str(output_dir), workers=args.workers, proxy=args.proxy)
    stats = downloader.download_all(images)
    print(f"\n用户 @{username} 完成！下载: {stats['downloaded']} | 跳过: {stats['skipped']} | 失败: {stats['failed']}")
    return 0

def run(args: argparse.Namespace) -> int:
    usernames = []
    if args.batch:
        batch_file = Path(args.batch)
        if not batch_file.exists():
            log.error("批量文件不存在: %s", args.batch)
            return 1
        with open(batch_file, "r", encoding="utf-8") as f:
            usernames = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    elif args.username:
        usernames = [args.username]
    else:
        log.error("必须提供 username 或 --batch")
        return 1

    for uname in usernames:
        process_user(uname, args)
        
    return 0


def main() -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI entry for saving X login cookies."""

import argparse
import asyncio
import logging

from .browser import save_x_cookies
from .logging_utils import configure_logging

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="登录 X 并保存 Playwright Cookies")
    parser.add_argument("--cookies", default="x_cookies.json", help="Cookies 保存路径")
    parser.add_argument("--timeout", type=int, default=180, help="等待手动登录的秒数")
    parser.add_argument("--proxy", help="代理服务器地址 (例如: http://127.0.0.1:7890)")
    parser.add_argument("--channel", default=None, help="浏览器通道: msedge, chrome, 或 chromium（默认使用 Playwright 内置 Chromium）")
    parser.add_argument("--profile-dir", default=".xscrape-browser-profile", help="持久化浏览器配置目录")
    return parser


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()
    log.info("浏览器会打开 X 登录页。登录成功后 cookies 会保存到: %s", args.cookies)
    channel = None if args.channel == "chromium" else args.channel
    logged_in = asyncio.run(
        save_x_cookies(
            args.cookies,
            timeout=args.timeout,
            proxy=args.proxy,
            channel=channel,
            profile_dir=args.profile_dir,
        )
    )
    if logged_in:
        log.info("已检测到登录态并保存 cookies。")
        return 0

    log.warning("未检测到 auth_token，但仍已保存当前 cookies。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI entry for API and Nitter scraping modes."""

import argparse
import json
import logging
import time
from pathlib import Path

from .logging_utils import configure_logging
from .utils import ensure_dir, sanitize_filename

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="X (Twitter) 图片爬取工具",
        epilog="Special commands: interactive, config",
    )
    parser.add_argument("username", nargs="?", help="目标用户名（不含 @）")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    parser.add_argument("-n", "--count", type=int, default=200, help="最多爬取推文数")
    parser.add_argument("-w", "--workers", type=int, default=4, help="并发下载线程数")
    parser.add_argument("--bearer-token", help="Twitter Bearer Token（可选，使用官方API）")
    parser.add_argument("--nitter", help="Nitter 实例 URL（免API模式）")
    parser.add_argument("--pages", type=int, default=5, help="免API模式页数")
    parser.add_argument("--proxy", help="代理服务器地址 (例如: http://127.0.0.1:7890)")
    parser.add_argument("--batch", help="批量模式：包含用户名的文本文件路径（每行一个）")
    parser.add_argument("--config", help="配置文件路径 (默认尝试读取 config.json)")
    parser.add_argument("--since", help="API模式：过滤开始时间 (ISO 8601, 如 2023-01-01T00:00:00Z)")
    parser.add_argument("--until", help="API模式：过滤结束时间 (ISO 8601)")
    parser.add_argument("--keyword", help="仅下载推文中包含该关键词的图片 (API模式支持)")
    parser.add_argument("--search-query", help="官方 API 最近搜索查询，例如: (Blue Archive) has:images -is:retweet")
    parser.add_argument("--search-name", help="搜索模式输出目录名，默认根据查询词生成")
    parser.add_argument("--top", type=int, default=10, help="搜索模式：按点赞数选取前 N 个媒体")
    parser.add_argument("--download-order", choices=["time", "likes"], default="time", help="搜索模式：下载排序，time=按时间从新到旧，likes=按点赞数从高到低")
    return parser


def select_search_results(images: list[dict], top: int, download_order: str = "time") -> list[dict]:
    ranked = sorted(
        images,
        key=lambda item: (item.get("like_count", 0), item.get("created_at", "")),
        reverse=True,
    )[:top]

    if download_order == "time":
        return sorted(ranked, key=lambda item: item.get("created_at", ""), reverse=True)
    return ranked


def process_search(args: argparse.Namespace) -> int:
    import requests
    from .clients import TwitterAPIClient
    from .downloader import ImageDownloader

    if not args.bearer_token:
        log.error("搜索模式必须提供 --bearer-token")
        return 1

    output_name = args.search_name or f"search_{sanitize_filename(args.search_query)[:80]}"
    output_dir = Path(args.output) / sanitize_filename(output_name)
    ensure_dir(str(output_dir))

    log.info("使用官方 API 最近搜索模式")
    log.info("搜索查询: %s", args.search_query)
    log.info("输出目录: %s", output_dir.resolve())

    client = TwitterAPIClient(args.bearer_token, proxy=args.proxy)
    images = []
    remaining = args.count
    next_token = None

    try:
        while remaining > 0:
            data = client.search_recent_tweets(
                args.search_query,
                min(remaining, 100),
                next_token,
                since=args.since,
                until=args.until,
            )
            batch = client.extract_image_urls(data, keyword=args.keyword)
            images.extend(batch)
            log.info("本批获取媒体: %s", len(batch))

            next_token = data.get("meta", {}).get("next_token")
            remaining -= 100
            if not next_token:
                break
            time.sleep(1)
    except requests.HTTPError as exc:
        log.error("搜索 API 请求失败: %s", exc)
        return 1

    selected = select_search_results(images, args.top, args.download_order)
    log.info("共找到 %s 个媒体，选取 %s 个下载", len(images), len(selected))
    if not selected:
        log.warning("未找到任何媒体，程序退出。")
        return 0

    metadata_file = output_dir / "metadata.json"
    metadata_file.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("元数据已保存: %s", metadata_file)

    downloader = ImageDownloader(str(output_dir), workers=args.workers, proxy=args.proxy)
    stats = downloader.download_all(selected)

    log.info(
        "搜索下载完成！已下载: %s | 跳过: %s | 失败: %s",
        stats["downloaded"],
        stats["skipped"],
        stats["failed"],
    )
    return 0


def process_user(username: str, args: argparse.Namespace) -> int:
    import requests
    from .clients import NoAPIClient, TwitterAPIClient
    from .downloader import ImageDownloader

    output_dir = Path(args.output) / sanitize_filename(username)
    ensure_dir(str(output_dir))

    log.info("目标用户: @%s", username)
    log.info("输出目录: %s", output_dir.resolve())

    images = []
    pending_file = output_dir / "pending_downloads.json"
    
    if pending_file.exists() and not args.batch:
        try:
            import questionary
            resume = questionary.confirm(f"检测到 {username} 的未完成下载，是否跳过扫描直接继续?").ask()
            if resume:
                with open(pending_file, "r", encoding="utf-8") as f:
                    images = json.load(f)
                log.info("已从 pending_downloads.json 加载 %s 个待下载文件。", len(images))
        except Exception:
            pass

    if not images:
        if args.bearer_token:
            log.info("使用官方 API 模式")
            client = TwitterAPIClient(args.bearer_token, proxy=args.proxy)
            try:
                user_id = client.get_user_id(username)
                log.info("用户 ID: %s", user_id)

                remaining = args.count
                next_token = None
                while remaining > 0:
                    data = client.get_user_tweets(user_id, min(remaining, 100), next_token, since=args.since, until=args.until)
                    batch = client.extract_image_urls(data, keyword=args.keyword)
                    images.extend(batch)
                    log.info("本批获取图片: %s", len(batch))

                    next_token = data.get("meta", {}).get("next_token")
                    remaining -= 100
                    if not next_token:
                        break
                    time.sleep(1)
            except requests.HTTPError as exc:
                log.error("API 请求失败: %s", exc)
                return 1
        else:
            log.info("使用 Nitter 免 API 模式")
            client = NoAPIClient(args.nitter, proxy=args.proxy)
            images = client.get_images_from_profile(username, pages=args.pages)

    log.info("共找到 %s 张图片/视频", len(images))
    if not images:
        log.warning("未找到任何图片/视频，程序退出。")
        return 0

    metadata_file = output_dir / "metadata.json"
    metadata_file.write_text(json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("元数据已保存: %s", metadata_file)

    downloader = ImageDownloader(str(output_dir), workers=args.workers, proxy=args.proxy)
    stats = downloader.download_all(images)

    log.info("=" * 40)
    log.info(
        "用户 @%s 下载完成！已下载: %s | 跳过: %s | 失败: %s",
        username,
        stats["downloaded"],
        stats["skipped"],
        stats["failed"],
    )
    return 0

def run(args: argparse.Namespace) -> int:
    if args.search_query:
        return process_search(args)

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

    exit_code = 0
    for uname in usernames:
        result = process_user(uname, args)
        if result != 0:
            exit_code = result
        
    return exit_code


def main() -> int:
    configure_logging()
    parser = build_parser()
    
    # 预解析参数以获取 --config 路径
    temp_args, remaining = parser.parse_known_args()
    
    if temp_args.username == "interactive":
        from .tui import run_interactive
        run_interactive()
        return 0
    elif temp_args.username == "config":
        from .config import load_config
        import json
        conf = load_config()
        print(json.dumps(conf, indent=2, ensure_ascii=False))
        return 0
        
    config_path = temp_args.config

    if config_path and Path(config_path).exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                parser.set_defaults(**config_data)
                log.info("已加载 JSON 配置文件: %s", config_path)
        except Exception as e:
            log.warning("配置文件加载失败 %s: %s", config_path, e)
    else:
        # 默认从 ~/.xscrape/config.toml 加载
        from .config import load_config, CONFIG_FILE
        cfg = load_config()
        defaults = {}
        if bearer := cfg.get("auth", {}).get("bearer_token"):
            defaults["bearer_token"] = bearer
        if output_dir := cfg.get("defaults", {}).get("output_dir"):
            defaults["output"] = output_dir
        if workers := cfg.get("defaults", {}).get("workers"):
            defaults["workers"] = workers
        if nitter := cfg.get("defaults", {}).get("nitter_instance"):
            defaults["nitter"] = nitter
        if scrolls := cfg.get("browser", {}).get("scrolls"):
            defaults["pages"] = scrolls
        if defaults:
            parser.set_defaults(**defaults)
            log.info("已加载 TOML 配置: %s", CONFIG_FILE)
            
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

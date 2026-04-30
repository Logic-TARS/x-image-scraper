"""
X (Twitter) Image Scraper
使用 Twitter/X API v2 或 无需 API 的网页爬取两种模式
"""

import os
import re
import time
import json
import hashlib
import logging
import argparse
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 日志配置 ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/scraper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── 工具函数 ──────────────────────────────────────────────────────────────────
def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)


# ── API 模式 (需要 Bearer Token) ──────────────────────────────────────────────
class TwitterAPIClient:
    BASE = "https://api.twitter.com/2"

    def __init__(self, bearer_token: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {bearer_token}"})

    def get_user_id(self, username: str) -> str:
        url = f"{self.BASE}/users/by/username/{username}"
        r = self.session.get(url, params={"user.fields": "id,name"})
        r.raise_for_status()
        return r.json()["data"]["id"]

    def get_user_tweets(self, user_id: str, max_results: int = 100, next_token: str = None):
        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "attachments,created_at,text",
            "expansions": "attachments.media_keys",
            "media.fields": "url,preview_image_url,type,width,height,variants",
        }
        if next_token:
            params["pagination_token"] = next_token

        url = f"{self.BASE}/users/{user_id}/tweets"
        r = self.session.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def extract_image_urls(self, response_data: dict) -> list[dict]:
        images = []
        media_map = {}

        # 建立 media_key -> media 映射
        includes = response_data.get("includes", {})
        for media in includes.get("media", []):
            media_map[media["media_key"]] = media

        tweets = response_data.get("data", [])
        for tweet in tweets:
            tweet_id = tweet["id"]
            created_at = tweet.get("created_at", "")
            attachments = tweet.get("attachments", {})
            for mk in attachments.get("media_keys", []):
                media = media_map.get(mk, {})
                mtype = media.get("type", "")

                if mtype == "photo":
                    url = media.get("url", "")
                    if url:
                        images.append({
                            "tweet_id": tweet_id,
                            "created_at": created_at,
                            "url": url + "?format=jpg&name=orig",  # 获取原图
                            "type": "photo",
                        })

                elif mtype in ("video", "animated_gif"):
                    # 取最高码率视频的缩略图
                    preview = media.get("preview_image_url", "")
                    if preview:
                        images.append({
                            "tweet_id": tweet_id,
                            "created_at": created_at,
                            "url": preview,
                            "type": mtype,
                        })

        return images


# ── 免 API 模式（抓取公开推文页面） ──────────────────────────────────────────
class NoAPIClient:
    """
    通过 Nitter 实例（X 的开源镜像）爬取图片，无需 API Key。
    Nitter 实例列表: https://github.com/zedeus/nitter/wiki/Instances
    """
    DEFAULT_INSTANCES = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.1d4.us",
    ]

    def __init__(self, instance: str = None):
        self.instance = instance or self.DEFAULT_INSTANCES[0]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def get_images_from_profile(self, username: str, pages: int = 3) -> list[dict]:
        images = []
        cursor = None

        for page in range(pages):
            url = f"{self.instance}/{username}/media"
            params = {}
            if cursor:
                params["cursor"] = cursor

            try:
                r = self.session.get(url, params=params, timeout=15)
                r.raise_for_status()
            except requests.RequestException as e:
                log.warning(f"第 {page+1} 页请求失败: {e}")
                break

            # 解析图片 URL（Nitter 返回 HTML）
            found = re.findall(r'href="(/pic/[^"]+)"', r.text)
            for path in found:
                img_url = f"{self.instance}{path}"
                # 转换成原始 pbs.twimg.com 链接
                img_url = img_url.replace("/pic/", "https://pbs.twimg.com/")
                images.append({"url": img_url, "type": "photo", "tweet_id": ""})

            # 下一页 cursor
            next_cur = re.search(r'cursor=([^&"]+)', r.text)
            cursor = next_cur.group(1) if next_cur else None
            if not cursor:
                break

            time.sleep(1.5)  # 礼貌性延迟

        return images


# ── 下载引擎 ──────────────────────────────────────────────────────────────────
class ImageDownloader:
    def __init__(self, output_dir: str, workers: int = 4, skip_existing: bool = True):
        self.output_dir = ensure_dir(output_dir)
        self.workers = workers
        self.skip_existing = skip_existing
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://twitter.com/",
        })
        self.stats = {"downloaded": 0, "skipped": 0, "failed": 0}

    def _download_one(self, item: dict) -> bool:
        url = item["url"]
        tweet_id = item.get("tweet_id", "unknown")

        # 生成文件名
        parsed = urlparse(url.split("?")[0])
        ext = Path(parsed.path).suffix or ".jpg"
        filename = f"{tweet_id}_{Path(parsed.path).name}{'' if ext in Path(parsed.path).name else ext}"
        filename = sanitize_filename(filename)
        dest = self.output_dir / filename

        if self.skip_existing and dest.exists():
            self.stats["skipped"] += 1
            return True

        try:
            r = self.session.get(url, timeout=20, stream=True)
            r.raise_for_status()
            content = r.content

            # 去重检查
            h = file_hash(content)
            dup_marker = self.output_dir / f".hash_{h}"
            if dup_marker.exists():
                log.debug(f"重复图片跳过: {url}")
                self.stats["skipped"] += 1
                return True
            dup_marker.touch()

            dest.write_bytes(content)
            self.stats["downloaded"] += 1
            log.info(f"✓ 已下载: {filename}")
            return True

        except Exception as e:
            log.warning(f"✗ 下载失败 {url}: {e}")
            self.stats["failed"] += 1
            return False

    def download_all(self, items: list[dict]) -> dict:
        log.info(f"开始下载 {len(items)} 张图片，并发数: {self.workers}")
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self._download_one, item): item for item in items}
            for fut in as_completed(futures):
                fut.result()  # 触发异常日志
        return self.stats


# ── 主入口 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="X (Twitter) 图片爬取工具")
    parser.add_argument("username", help="目标用户名（不含 @）")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    parser.add_argument("-n", "--count", type=int, default=200, help="最多爬取推文数")
    parser.add_argument("-w", "--workers", type=int, default=4, help="并发下载线程数")
    parser.add_argument("--bearer-token", help="Twitter Bearer Token（可选，使用官方API）")
    parser.add_argument("--nitter", help="Nitter 实例 URL（免API模式）")
    parser.add_argument("--pages", type=int, default=5, help="免API模式页数")
    args = parser.parse_args()

    output_dir = Path(args.output) / sanitize_filename(args.username)
    ensure_dir(str(output_dir))

    log.info(f"目标用户: @{args.username}")
    log.info(f"输出目录: {output_dir.resolve()}")

    images = []

    if args.bearer_token:
        # ── 官方 API 模式 ──
        log.info("使用官方 API 模式")
        client = TwitterAPIClient(args.bearer_token)
        try:
            user_id = client.get_user_id(args.username)
            log.info(f"用户 ID: {user_id}")

            remaining = args.count
            next_token = None
            while remaining > 0:
                data = client.get_user_tweets(user_id, min(remaining, 100), next_token)
                batch = client.extract_image_urls(data)
                images.extend(batch)
                log.info(f"本批获取图片: {len(batch)}")

                next_token = data.get("meta", {}).get("next_token")
                remaining -= 100
                if not next_token:
                    break
                time.sleep(1)

        except requests.HTTPError as e:
            log.error(f"API 请求失败: {e}")
            return
    else:
        # ── 免 API 模式（Nitter）──
        log.info("使用 Nitter 免 API 模式")
        client = NoAPIClient(args.nitter)
        images = client.get_images_from_profile(args.username, pages=args.pages)

    log.info(f"共找到 {len(images)} 张图片")

    if not images:
        log.warning("未找到任何图片，程序退出。")
        return

    # 保存元数据
    meta_file = output_dir / "metadata.json"
    meta_file.write_text(
        json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"元数据已保存: {meta_file}")

    # 下载
    downloader = ImageDownloader(str(output_dir), workers=args.workers)
    stats = downloader.download_all(images)

    log.info("=" * 40)
    log.info(f"下载完成！已下载: {stats['downloaded']} | 跳过: {stats['skipped']} | 失败: {stats['failed']}")
    log.info(f"图片保存位置: {output_dir.resolve()}")


if __name__ == "__main__":
    main()

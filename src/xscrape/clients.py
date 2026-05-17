"""HTTP clients for the supported scraping modes."""

import logging
import re
import time
from html import unescape
from urllib.parse import unquote

import requests

log = logging.getLogger(__name__)


class TwitterAPIClient:
    """Client for the official Twitter/X API v2."""

    BASE = "https://api.x.com/2"

    def __init__(self, bearer_token: str, proxy: str | None = None):
        self.session = requests.Session()
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})
        self.session.headers.update({"Authorization": f"Bearer {bearer_token}"})

    def get_user_id(self, username: str) -> str:
        url = f"{self.BASE}/users/by/username/{username}"
        response = self.session.get(url, params={"user.fields": "id,name"})
        response.raise_for_status()
        return response.json()["data"]["id"]

    def get_user_tweets(self, user_id: str, max_results: int = 100, next_token: str | None = None, since: str | None = None, until: str | None = None) -> dict:
        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "attachments,created_at,text",
            "expansions": "attachments.media_keys",
            "media.fields": "url,preview_image_url,type,width,height,variants",
        }
        if next_token:
            params["pagination_token"] = next_token
        if since:
            params["start_time"] = since
        if until:
            params["end_time"] = until

        url = f"{self.BASE}/users/{user_id}/tweets"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def search_recent_tweets(
        self,
        query: str,
        max_results: int = 100,
        next_token: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> dict:
        params = {
            "query": query,
            "max_results": max(10, min(max_results, 100)),
            "tweet.fields": "attachments,author_id,created_at,lang,public_metrics,text",
            "expansions": "attachments.media_keys,author_id",
            "media.fields": "url,preview_image_url,type,width,height,variants",
            "user.fields": "name,username",
        }
        if next_token:
            params["next_token"] = next_token
        if since:
            params["start_time"] = since
        if until:
            params["end_time"] = until

        url = f"{self.BASE}/tweets/search/recent"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def extract_image_urls(self, response_data: dict, keyword: str | None = None) -> list[dict]:
        images = []
        media_map = {}
        user_map = {}

        includes = response_data.get("includes", {})
        for media in includes.get("media", []):
            media_map[media["media_key"]] = media
        for user in includes.get("users", []):
            user_map[user["id"]] = user

        tweets = response_data.get("data", [])
        for tweet in tweets:
            text = tweet.get("text", "")
            if keyword and keyword.lower() not in text.lower():
                continue

            tweet_id = tweet["id"]
            created_at = tweet.get("created_at", "")
            metrics = tweet.get("public_metrics", {})
            author = user_map.get(tweet.get("author_id"), {})
            attachments = tweet.get("attachments", {})
            for media_key in attachments.get("media_keys", []):
                media = media_map.get(media_key, {})
                media_type = media.get("type", "")
                base_item = {
                    "tweet_id": tweet_id,
                    "created_at": created_at,
                    "author_id": tweet.get("author_id", ""),
                    "author_username": author.get("username", ""),
                    "author_name": author.get("name", ""),
                    "like_count": metrics.get("like_count", 0),
                    "retweet_count": metrics.get("retweet_count", 0),
                    "reply_count": metrics.get("reply_count", 0),
                    "quote_count": metrics.get("quote_count", 0),
                    "text": text,
                }

                if media_type == "photo":
                    url = media.get("url", "")
                    if url:
                        item = base_item.copy()
                        item.update({"url": url + "?format=jpg&name=orig", "type": "photo"})
                        images.append(item)
                elif media_type in ("video", "animated_gif"):
                    variants = media.get("variants", [])
                    if variants:
                        mp4_variants = [v for v in variants if v.get("content_type") == "video/mp4"]
                        if mp4_variants:
                            mp4_variants.sort(key=lambda x: x.get("bit_rate", 0), reverse=True)
                            best_video = mp4_variants[0]["url"]
                            item = base_item.copy()
                            item.update({"url": best_video, "type": media_type})
                            images.append(item)
                            continue

                    preview = media.get("preview_image_url", "")
                    if preview:
                        item = base_item.copy()
                        item.update({"url": preview, "type": media_type})
                        images.append(item)

        return images


class NoAPIClient:
    """Scrape public media pages via Nitter without API credentials."""

    DEFAULT_INSTANCES = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.1d4.us",
    ]

    def __init__(self, instance: str | None = None, proxy: str | None = None):
        self._custom_instance = instance is not None
        self.instance = instance or self.DEFAULT_INSTANCES[0]
        self.session = requests.Session()
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )

    @staticmethod
    def _normalize_pic_url(path: str) -> str:
        decoded = unquote(unescape(path.removeprefix("/pic/")))
        if decoded.startswith("http://") or decoded.startswith("https://"):
            return decoded
        return f"https://pbs.twimg.com/{decoded.lstrip('/')}"

    def get_images_from_profile(self, username: str, pages: int = 3) -> list[dict]:
        instances = [self.instance] if self._custom_instance else self.DEFAULT_INSTANCES

        for instance in instances:
            images = []
            seen_urls = set()
            cursor = None
            failed = False

            for page in range(pages):
                url = f"{instance}/{username}/media"
                params = {}
                if cursor:
                    params["cursor"] = cursor

                try:
                    response = self.session.get(url, params=params, timeout=15)
                    response.raise_for_status()
                except requests.RequestException as exc:
                    log.warning("Nitter 实例 %s 第 %s 页请求失败: %s", instance, page + 1, exc)
                    failed = True
                    break

                found = re.findall(r'href="(/pic/[^"]+)"', response.text)
                for path in found:
                    img_url = self._normalize_pic_url(path)
                    if img_url in seen_urls:
                        continue
                    seen_urls.add(img_url)
                    images.append({"url": img_url, "type": "photo", "tweet_id": ""})

                # 抓取 Nitter 的视频 (通常是在 source 标签的 src 中，如 /video/...)
                found_vids = re.findall(r'(?:src|href)="(/video/[^"]+)"', response.text)
                for path in found_vids:
                    vid_url = f"{instance}{path}"
                    if vid_url in seen_urls:
                        continue
                    seen_urls.add(vid_url)
                    images.append({"url": vid_url, "type": "video", "tweet_id": ""})

                next_cur = re.search(r'cursor=([^&"]+)', response.text)
                cursor = next_cur.group(1) if next_cur else None
                if not cursor:
                    break

                time.sleep(1.5)

            if not failed:
                self.instance = instance
                return images

        return []

"""Image download engine."""

import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests

from .utils import ensure_dir, sanitize_filename

log = logging.getLogger(__name__)


class ImageDownloader:
    """Download image assets with duplicate detection and resumable skips."""

    def __init__(self, output_dir: str, workers: int = 4, skip_existing: bool = True, proxy: str | None = None):
        self.output_dir = ensure_dir(output_dir)
        self.workers = workers
        self.skip_existing = skip_existing
        self.proxy = proxy
        self.stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        self._stats_lock = threading.Lock()
        self._hash_lock = threading.Lock()
        self.pending_file = self.output_dir / "pending_downloads.json"

        # Load pending items if exists
        self.pending_items = []
        if self.pending_file.exists():
            import json
            try:
                with open(self.pending_file, "r", encoding="utf-8") as f:
                    self.pending_items = json.load(f)
            except Exception:
                pass

        self._stop_event = threading.Event()

    def _make_session(self) -> requests.Session:
        session = requests.Session()
        if self.proxy:
            session.proxies.update({"http": self.proxy, "https": self.proxy})
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://twitter.com/",
            }
        )
        return session

    def _increment_stat(self, key: str) -> None:
        with self._stats_lock:
            self.stats[key] += 1

    def _download_one(self, item: dict) -> bool:
        if self._stop_event.is_set():
            return False

        url = item["url"]
        tweet_id = item.get("tweet_id", "unknown")

        parsed = urlparse(url.split("?")[0])
        ext = Path(parsed.path).suffix or ".jpg"
        if item.get("type") == "video" and not ext.endswith(".mp4"):
            ext = ".mp4"

        filename = f"{tweet_id}_{Path(parsed.path).name}{'' if ext in Path(parsed.path).name else ext}"
        filename = sanitize_filename(filename)
        destination = self.output_dir / filename

        if self.skip_existing and destination.exists():
            self._increment_stat("skipped")
            return True

        import time

        session = self._make_session()
        for attempt in range(3):
            try:
                response = session.get(url, timeout=20, stream=True)
                response.raise_for_status()

                # Stream to temp file with incremental hash
                tmp = destination.with_suffix(destination.suffix + ".tmp")
                hasher = hashlib.md5()
                with open(tmp, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            hasher.update(chunk)

                image_hash = hasher.hexdigest()
                duplicate_marker = self.output_dir / f".hash_{image_hash}"
                with self._hash_lock:
                    if duplicate_marker.exists():
                        tmp.unlink()
                        log.debug("重复内容跳过: %s", url)
                        self._increment_stat("skipped")
                        return True
                    tmp.rename(destination)
                    duplicate_marker.touch()

                self._increment_stat("downloaded")
                log.debug("✓ 已下载: %s", filename)
                return True
            except requests.RequestException as exc:
                # Clean up temp file on failure
                tmp = destination.with_suffix(destination.suffix + ".tmp")
                if tmp.exists():
                    tmp.unlink()
                if attempt < 2:
                    log.debug("下载失败，准备重试 (%s/3) %s: %s", attempt + 1, url, exc)
                    time.sleep(2 ** attempt)
                else:
                    log.warning("✗ 下载失败 %s: %s", url, exc)
                    self._increment_stat("failed")
                    return False
            except Exception as exc:
                tmp = destination.with_suffix(destination.suffix + ".tmp")
                if tmp.exists():
                    tmp.unlink()
                log.warning("✗ 未知错误 %s: %s", url, exc)
                self._increment_stat("failed")
                return False

    def download_all(
        self,
        items: list[dict],
        on_progress: Callable[[int, int, dict], None] | None = None,
        show_progress: bool = True,
    ) -> dict:
        import json

        download_items = list(items)
        
        # Combine items with pending items
        existing_urls = {item["url"] for item in download_items}
        for p in self.pending_items:
            if p["url"] not in existing_urls:
                download_items.append(p)
                
        # Save all items to pending_downloads.json initially
        with open(self.pending_file, "w", encoding="utf-8") as f:
            json.dump(download_items, f, ensure_ascii=False, indent=2)

        log.info("开始下载 %s 个文件，并发数: %s", len(download_items), self.workers)
        
        pbar = None
        if show_progress:
            try:
                from tqdm import tqdm
                pbar = tqdm(total=len(download_items), desc="Downloading", unit="file")
            except ImportError:
                pbar = None

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self._download_one, item): item for item in download_items}
            completed = 0
            try:
                for future in as_completed(futures):
                    future.result()
                    completed += 1
                    if pbar:
                        pbar.update(1)
                    if on_progress:
                        on_progress(completed, len(download_items), self.stats.copy())
            except KeyboardInterrupt:
                log.warning("检测到中断，正在停止下载...")
                self._stop_event.set()
                # 提前结束不会清空 pending_downloads.json
                if pbar:
                    pbar.close()
                return self.stats

        if pbar:
            pbar.close()
            
        # Clear pending_downloads.json if all successful or skipped
        if self.stats["failed"] == 0 and not self._stop_event.is_set():
            if self.pending_file.exists():
                self.pending_file.unlink()

        return self.stats

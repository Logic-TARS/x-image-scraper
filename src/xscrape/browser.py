"""Playwright-powered scraping mode."""

import asyncio
import json
import logging
import re
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger(__name__)


def normalize_x_media_url(url: str) -> str:
    """Return the original-quality pbs.twimg.com media URL."""
    url = re.sub(r"name=[^&]+", "name=orig", url)
    url = re.sub(r"format=[^&]+", "format=jpg", url)
    if "format=" not in url:
        suffix = "&" if "?" in url else "?"
        url += f"{suffix}format=jpg&name=orig"
    if "name=" not in url:
        suffix = "&" if "?" in url else "?"
        url += f"{suffix}name=orig"
    return url


def parse_compact_count(value: str) -> int:
    """Parse compact counts such as 1.2K, 3万, 4천, or plain numbers."""
    if not value:
        return 0

    text = value.strip().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([KkMm万萬千]?)", text)
    if not match:
        return 0

    number = float(match.group(1))
    suffix = match.group(2)
    multiplier = {
        "K": 1_000,
        "k": 1_000,
        "M": 1_000_000,
        "m": 1_000_000,
        "万": 10_000,
        "萬": 10_000,
        "千": 1_000,
    }.get(suffix, 1)
    return int(number * multiplier)


def parse_like_count(labels: list[str], visible_text: str = "") -> int:
    """Extract a like count from X button aria-labels or article text."""
    for label in labels:
        if not label:
            continue
        if re.search(r"(like|likes|いいね|좋아요)", label, re.IGNORECASE):
            count = parse_compact_count(label)
            if count:
                return count

    lines = [line.strip() for line in visible_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if re.search(r"^(like|likes|いいね|좋아요)$", line, re.IGNORECASE) and index > 0:
            return parse_compact_count(lines[index - 1])
    return 0


def select_search_media(items: list[dict], top: int, download_order: str = "time") -> list[dict]:
    """Pick high-like media first, then order the selected set for downloading."""
    ranked = sorted(
        items,
        key=lambda item: (item.get("like_count", 0), item.get("created_at", "")),
        reverse=True,
    )[:top]
    if download_order == "likes":
        return ranked
    return sorted(ranked, key=lambda item: item.get("created_at", ""), reverse=True)


QUALITY_PENALTY_PATTERNS = [
    r"\bsketch\b",
    r"\bwip\b",
    r"\bmeme\b",
    r"\bcomic\b",
    r"\bscreenshot\b",
    r"\bai\b",
    r"漫画",
    r"落書き",
    r"らくがき",
    r"ラクガキ",
    r"rkgk",
]


def calculate_quality_score(item: dict) -> float:
    """Rank likely finished illustrations above merely viral image posts."""
    likes = item.get("like_count", 0) or 0
    retweets = item.get("retweet_count", 0) or 0
    quotes = item.get("quote_count", 0) or 0
    replies = item.get("reply_count", 0) or 0
    width = item.get("width", 0) or 0
    height = item.get("height", 0) or 0
    text = item.get("text", "") or ""

    megapixels = (width * height) / 1_000_000 if width and height else 0
    score = likes + retweets * 3 + quotes * 2 - replies * 0.5 + min(megapixels, 6) * 500

    if width and height and min(width, height) < 900:
        score -= 1500
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in QUALITY_PENALTY_PATTERNS):
        score -= 3000

    return score


def select_quality_media(items: list[dict], top: int, download_order: str = "time") -> list[dict]:
    ranked = sorted(
        items,
        key=lambda item: (item.get("quality_score", calculate_quality_score(item)), item.get("like_count", 0), item.get("created_at", "")),
        reverse=True,
    )[:top]
    if download_order == "likes":
        return ranked
    return sorted(ranked, key=lambda item: item.get("created_at", ""), reverse=True)


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def extract_media_from_search_json(data: dict) -> list[dict]:
    """Extract media records from X SearchTimeline GraphQL JSON."""
    items = []
    seen = set()

    for node in _walk_json(data):
        legacy = node.get("legacy")
        if not isinstance(legacy, dict) or "favorite_count" not in legacy:
            continue

        tweet_id = legacy.get("id_str") or legacy.get("conversation_id_str")
        if not tweet_id:
            continue

        media_entries = legacy.get("extended_entities", {}).get("media", [])
        if not media_entries:
            media_entries = legacy.get("entities", {}).get("media", [])
        if not media_entries:
            continue

        user_legacy = node.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
        author = user_legacy.get("screen_name", "")

        created_at = legacy.get("created_at", "")
        try:
            created_at = parsedate_to_datetime(created_at).isoformat().replace("+00:00", "Z")
        except Exception:
            pass

        for media in media_entries:
            if media.get("type") != "photo":
                continue
            url = media.get("media_url_https") or media.get("media_url")
            if not url:
                continue
            normalized = normalize_x_media_url(url)
            key = (tweet_id, normalized)
            if key in seen:
                continue
            seen.add(key)
            width = media.get("original_info", {}).get("width") or media.get("sizes", {}).get("large", {}).get("w") or 0
            height = media.get("original_info", {}).get("height") or media.get("sizes", {}).get("large", {}).get("h") or 0
            item = {
                "tweet_id": tweet_id,
                "author_username": author,
                "created_at": created_at,
                "like_count": legacy.get("favorite_count", 0),
                "retweet_count": legacy.get("retweet_count", 0),
                "reply_count": legacy.get("reply_count", 0),
                "quote_count": legacy.get("quote_count", 0),
                "width": width,
                "height": height,
                "url": normalized,
                "type": "photo",
                "tweet_url": f"https://x.com/{author}/status/{tweet_id}" if author else "",
                "text": legacy.get("full_text", ""),
            }
            item["quality_score"] = calculate_quality_score(item)
            items.append(
                item
            )

    return items


async def _load_cookies(context, cookies_file: str | None) -> None:
    if not cookies_file:
        return

    c_path = Path(cookies_file)
    if not c_path.exists():
        log.warning("Cookies 文件不存在: %s", cookies_file)
        return

    try:
        cookies = json.loads(c_path.read_text(encoding="utf-8"))
        await context.add_cookies(cookies)
        log.info("已加载 Cookies 文件: %s", cookies_file)
    except Exception as exc:
        log.warning("加载 Cookies 文件失败: %s", exc)


async def save_x_cookies(
    cookies_file: str,
    timeout: int = 180,
    proxy: str | None = None,
    channel: str | None = None,
    profile_dir: str = ".xscrape-browser-profile",
) -> bool:
    """Open a visible browser for manual X login and save cookies."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("请先安装: pip install playwright && playwright install chromium")
        return False

    async with async_playwright() as playwright:
        proxy_settings = {"server": proxy} if proxy else None
        launch_options = {
            "headless": False,
            "proxy": proxy_settings,
            "viewport": {"width": 1280, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
            "ignore_default_args": ["--enable-automation"],
        }
        if channel:
            launch_options["channel"] = channel

        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            **launch_options,
        )
        logged_in = False
        cookies = []
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=60000)

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                cookies = await context.cookies(["https://x.com", "https://twitter.com"])
                if any(cookie.get("name") == "auth_token" for cookie in cookies):
                    logged_in = True
                    break
                await asyncio.sleep(2)
        except Exception as exc:
            log.warning("登录窗口已关闭或读取 cookies 失败: %s", exc)
            try:
                cookies = await context.cookies(["https://x.com", "https://twitter.com"])
            except Exception:
                cookies = []
        finally:
            if cookies:
                Path(cookies_file).write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
            await context.close()

    return logged_in


async def save_x_cookies_ephemeral(cookies_file: str, timeout: int = 180, proxy: str | None = None) -> bool:
    """Open a temporary visible browser for manual X login and save cookies."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("请先安装: pip install playwright && playwright install chromium")
        return False

    async with async_playwright() as playwright:
        proxy_settings = {"server": proxy} if proxy else None
        browser = await playwright.chromium.launch(headless=False, proxy=proxy_settings)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=60000)

        deadline = time.monotonic() + timeout
        logged_in = False
        while time.monotonic() < deadline:
            cookies = await context.cookies(["https://x.com", "https://twitter.com"])
            if any(cookie.get("name") == "auth_token" for cookie in cookies):
                logged_in = True
                break
            await asyncio.sleep(2)

        cookies = await context.cookies(["https://x.com", "https://twitter.com"])
        Path(cookies_file).write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        await browser.close()

    return logged_in


async def scrape_x_search(
    query: str,
    top: int = 10,
    max_scrolls: int = 20,
    headless: bool = True,
    proxy: str | None = None,
    cookies_file: str | None = None,
    download_order: str = "time",
    tab: str = "live",
    profile_dir: str | None = None,
    channel: str | None = None,
    quality_mode: bool = False,
    return_candidates: bool = False,
) -> list[dict]:
    """Search X with a logged-in browser session and return media.

    By default this returns the selected Top N set. GUI callers can pass
    return_candidates=True to apply their own filters before final selection.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("请先安装: pip install playwright && playwright install chromium")
        return []

    results_by_key: dict[tuple[str, str], dict] = {}

    async with async_playwright() as playwright:
        proxy_settings = {"server": proxy} if proxy else None
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        if profile_dir:
            launch_options = {
                "headless": headless,
                "proxy": proxy_settings,
                "viewport": {"width": 1280, "height": 900},
                "user_agent": user_agent,
                "args": ["--disable-blink-features=AutomationControlled"],
            }
            if channel:
                launch_options["channel"] = channel
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                **launch_options,
            )
            browser = None
        else:
            browser = await playwright.chromium.launch(headless=headless, proxy=proxy_settings)
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1280, "height": 900},
            )
        await _load_cookies(context, cookies_file)

        page = await context.new_page()
        async def handle_search_response(response):
            if "SearchTimeline" not in response.url:
                return
            try:
                data = await response.json()
            except Exception:
                return
            for item in extract_media_from_search_json(data):
                key = (item["tweet_id"], item["url"])
                results_by_key.setdefault(key, item)

        page.on("response", handle_search_response)

        search_url = f"https://x.com/search?q={quote(query)}&src=typed_query"
        if tab:
            search_url += f"&f={quote(tab)}"

        log.info("正在打开 X 搜索页: %s", search_url)
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        if "/i/flow/login" in page.url:
            log.warning("X 跳转到登录页，请先运行 xscrape-login 保存 cookies。")
            await context.close()
            if browser:
                await browser.close()
            return []

        for index in range(max_scrolls):
            raw_items = await page.evaluate(
                """
                () => Array.from(document.querySelectorAll('article[data-testid="tweet"]')).flatMap((article) => {
                  const links = Array.from(article.querySelectorAll('a[href*="/status/"]'));
                  const statusLink = links.find((link) => /\\/status\\/\\d+/.test(link.href));
                  if (!statusLink) return [];
                  const match = statusLink.href.match(/\\/([^/]+)\\/status\\/(\\d+)/);
                  if (!match) return [];
                  const author = match[1];
                  const tweetId = match[2];
                  const time = article.querySelector('time')?.getAttribute('datetime') || '';
                  const labels = Array.from(article.querySelectorAll('[aria-label]')).map((node) => node.getAttribute('aria-label') || '');
                  const text = article.innerText || '';
                  const media = Array.from(article.querySelectorAll('img[src*="pbs.twimg.com/media/"]')).map((img) => img.src);
                  return media.map((url) => ({tweet_id: tweetId, author_username: author, created_at: time, labels, text, url}));
                })
                """
            )

            for raw in raw_items:
                url = normalize_x_media_url(raw["url"])
                key = (raw["tweet_id"], url)
                if key in results_by_key:
                    continue
                results_by_key[key] = {
                    "tweet_id": raw["tweet_id"],
                    "author_username": raw.get("author_username", ""),
                    "created_at": raw.get("created_at", ""),
                    "like_count": parse_like_count(raw.get("labels", []), raw.get("text", "")),
                    "url": url,
                    "type": "photo",
                    "tweet_url": f"https://x.com/{raw.get('author_username', '')}/status/{raw['tweet_id']}",
                }

            log.info("滚动 %s/%s，已解析 %s 个媒体", index + 1, max_scrolls, len(results_by_key))
            previous_count = len(results_by_key)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2.5)
            if len(results_by_key) == previous_count and index >= 2:
                break

        await context.close()
        if browser:
            await browser.close()

    items = list(results_by_key.values())
    if return_candidates:
        return items
    if quality_mode:
        return select_quality_media(items, top=top, download_order=download_order)
    return select_search_media(items, top=top, download_order=download_order)


async def scrape_with_playwright(username: str, max_scrolls: int = 20, headless: bool = True, proxy: str | None = None, cookies_file: str | None = None) -> list[dict]:
    """Open the X media page and collect media responses from the browser."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("请先安装: pip install playwright && playwright install chromium")
        return []

    images = []
    seen_urls = set()

    async with async_playwright() as playwright:
        proxy_settings = {"server": proxy} if proxy else None
        browser = await playwright.chromium.launch(headless=headless, proxy=proxy_settings)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        
        await _load_cookies(context, cookies_file)

        async def handle_response(response):
            url = response.url
            if url in seen_urls:
                return

            if "pbs.twimg.com/media/" in url:
                orig_url = normalize_x_media_url(url)

                seen_urls.add(url)
                images.append({"url": orig_url, "tweet_id": "", "type": "photo"})
                log.info("捕获图片: %s", orig_url[-60:])
            elif "video.twimg.com/" in url and (".mp4" in url or ".m3u8" in url):
                if ".mp4" in url:
                    seen_urls.add(url)
                    images.append({"url": url, "tweet_id": "", "type": "video"})
                    log.info("捕获视频: %s", url[-60:])

        page = await context.new_page()
        page.on("response", handle_response)

        media_url = f"https://x.com/{username}/media"
        log.info("正在打开: %s", media_url)
        await page.goto(media_url, wait_until="networkidle", timeout=30000)

        for index in range(max_scrolls):
            previous_count = len(images)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            if len(images) == previous_count:
                log.info("第 %s 次滚动无新内容，停止滚动", index + 1)
                break

            log.info("滚动 %s/%s，已捕获 %s 张", index + 1, max_scrolls, len(images))

        await browser.close()

    log.info("Playwright 模式完成，共捕获 %s 张图片", len(images))
    return images

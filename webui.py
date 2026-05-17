"""Streamlit Web UI for XScraper — logged-in search, login, API, Nitter, Playwright, and results review."""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# Playwright launches browser subprocesses. Streamlit may run scripts on a
# Selector event loop on Windows, which cannot create subprocess transports.
if sys.platform == "win32" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Ensure src/ is on sys.path so xscrape modules are importable
_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from xscrape.clients import NoAPIClient, TwitterAPIClient
from xscrape.downloader import ImageDownloader
from xscrape.utils import sanitize_filename, ensure_dir
from xscrape.browser import (
    scrape_x_search,
    save_x_cookies,
    scrape_with_playwright,
    select_quality_media,
    select_search_media,
)

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit command)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="XScraper Web GUI",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# i18n — translations
# ---------------------------------------------------------------------------

LANG = {
    "en": {
        # Page
        "page_title": "XScraper Web GUI",
        "header_title": "🐦 XScraper Web GUI",
        "header_desc": "Search, rank, preview, and download X/Twitter media — powered by Streamlit & Playwright",
        "footer": "XScraper © 2026 — All credentials and cookies stay local. No data is uploaded to external services.",

        # Language
        "lang_label": "Language",
        "lang_en": "English",
        "lang_zh": "中文",

        # Sidebar
        "sidebar_title": "⚙️ Global Settings",
        "output_dir": "Output root directory",
        "workers": "Download workers",
        "proxy_optional": "Proxy (optional)",
        "proxy_placeholder": "http://127.0.0.1:7890",
        "cookies_path": "Cookies file path",
        "profile_dir": "Browser profile directory (optional)",
        "profile_placeholder": ".xscrape-browser-profile",
        "browser_channel": "Browser channel",

        # Mode tabs
        "mode_search": "🔍 X Logged-In Search",
        "mode_login": "🔑 X Login / Cookies",
        "mode_api": "📡 Official X API Search",
        "mode_nitter": "🌐 Nitter User Media",
        "mode_playwright": "🎭 Playwright User Media",
        "mode_existing": "📂 Existing Results",

        # Login tab
        "login_title": "🔑 X Login — Save Browser Cookies",
        "login_desc": "Opens a visible browser window for you to log into X manually. Cookies are saved locally and reused by other modes.",
        "login_cookies_path": "Cookies save path",
        "login_timeout": "Login timeout (seconds)",
        "login_profile": "Profile directory (optional)",
        "login_channel": "Browser channel",
        "login_status_auth": "✅ Cookies file exists with auth_token ({count} cookies)",
        "login_status_noauth": "⚠️  Cookies file exists but no auth_token found ({count} cookies)",
        "login_status_bad": "⚠️  Cookies file exists but could not be parsed",
        "login_status_none": "ℹ️  No cookies file yet — run login to create one",
        "login_btn": "🚀 Open Login Browser",
        "login_status_start": "Opening browser for login…",
        "login_success": "✅ Login successful — cookies saved",
        "login_auth_detected": "auth_token detected and saved!",
        "login_warn_auth_missing": "⚠️  Login completed but auth_token not found",
        "login_warn_body": "Browser closed but no auth_token was found. Cookies were still saved.",
        "login_failed": "❌ Login failed",
        "login_error": "Login error: {err}",

        # Search tab
        "search_title": "🔍 X Logged-In Search",
        "search_desc": "Search X with an authenticated browser session. Captures GraphQL search results, ranks by quality or likes, and downloads selected media.",
        "search_preset": "Query preset",
        "preset_ba_quality": "Blue Archive Quality",
        "preset_ba_broad": "Blue Archive Broad",
        "preset_custom": "Custom",
        "search_query": "Search query",
        "search_outname": "Output name (subdirectory)",
        "search_top": "Top N media",
        "search_scrolls": "Scroll count",
        "search_tab": "Search tab",
        "search_tab_live": "Live",
        "search_tab_top": "Top",
        "search_quality": "Quality mode",
        "search_quality_help": "Use composite quality score (likes, retweets, image resolution, content penalties)",
        "search_order": "Download order",
        "search_order_time": "Time",
        "search_order_likes": "Likes",
        "search_advanced": "Advanced filters",
        "search_min_likes": "Minimum likes",
        "search_min_rts": "Minimum retweets",
        "search_btn": "🔍 Start Search",
        "search_no_cookies": "⚠️  Cookies file not found — run X Login first",
        "search_empty_query": "Search query cannot be empty",
        "search_starting": "Starting search…",
        "search_loading_cookies": "Starting browser and loading cookies…",
        "search_captured": "Captured {count} candidates, filtering...",
        "search_no_results": "No results found",
        "search_no_results_body": "No media found. Try broadening the query or increasing scroll count.",
        "search_filtered_out": "No items passed filters",
        "search_filtered_out_body": "All candidates were filtered out. Try lowering minimum requirements.",
        "search_downloading": "Downloading {count} files…",
        "search_done": "✅ Search & download complete",
        "search_failed": "❌ Search failed",
        "search_error": "Search error: {err}",

        # API Search tab
        "api_title": "📡 Official X API Search",
        "api_desc": "Uses the Twitter API v2 recent search endpoint. Requires a Bearer Token.",
        "api_bearer": "Bearer Token",
        "api_query": "Search query",
        "api_query_help": "Example: (Blue Archive OR ブルアカ) has:images -is:retweet",
        "api_outname": "Output name",
        "api_count": "Tweets to scan",
        "api_top": "Top N media",
        "api_order": "Download order",
        "api_keyword": "Keyword filter (optional)",
        "api_keyword_placeholder": "Only tweets containing…",
        "api_since": "Since (ISO 8601, optional)",
        "api_since_placeholder": "2026-01-01T00:00:00Z",
        "api_until": "Until (ISO 8601, optional)",
        "api_until_placeholder": "2026-05-17T00:00:00Z",
        "api_btn": "📡 Start API Search",
        "api_no_bearer": "Bearer Token is required",
        "api_no_query": "Search query is required",
        "api_fetching": "Fetching tweets from API…",
        "api_selecting": "Found {count} media items, selecting…",
        "api_no_results": "No results",
        "api_no_results_body": "No media found. Try a different query.",
        "api_downloading": "Downloading {count} files…",
        "api_done": "✅ API search complete",
        "api_failed": "❌ API search failed",
        "api_error": "API search error: {err}",

        # Nitter tab
        "nitter_title": "🌐 Nitter User Media",
        "nitter_desc": "Scrape a user's media tab via a public Nitter instance. No authentication required.",
        "nitter_user": "Username (without @)",
        "nitter_user_placeholder": "elonmusk",
        "nitter_instance": "Nitter instance",
        "nitter_pages": "Pages to scrape",
        "nitter_btn": "🌐 Start Nitter Scrape",
        "nitter_no_user": "Username is required",
        "nitter_fetching": "Fetching media from Nitter…",
        "nitter_no_results": "No media found",
        "nitter_no_results_body": "No media found for @{user}. The Nitter instance may be down.",
        "nitter_downloading": "Downloading {count} files…",
        "nitter_done": "✅ Nitter scrape complete",
        "nitter_failed": "❌ Nitter scrape failed",
        "nitter_error": "Nitter error: {err}",

        # Playwright tab
        "pw_title": "🎭 Playwright User Media",
        "pw_desc": "Opens `x.com/{{username}}/media` in a headless browser and captures media URLs from network responses.",
        "pw_user": "Username (without @)",
        "pw_user_placeholder": "elonmusk",
        "pw_scrolls": "Scroll count",
        "pw_show": "Show browser window",
        "pw_btn": "🎭 Start Playwright Scrape",
        "pw_no_user": "Username is required",
        "pw_capturing": "Opening browser and capturing media…",
        "pw_no_results": "No media captured",
        "pw_no_results_body": "No media captured for @{user}. X may require login.",
        "pw_downloading": "Downloading {count} files…",
        "pw_done": "✅ Playwright scrape complete",
        "pw_failed": "❌ Playwright scrape failed",
        "pw_error": "Playwright error: {err}",

        # Existing results tab
        "existing_title": "📂 Existing Results",
        "existing_desc": "Browse previously completed runs and inspect their metadata and downloads.",
        "existing_none": "No output directories with metadata.json found under `{dir}/`",
        "existing_select": "Select a run to review",
        "existing_media_count": "📂 **{name}** — {count} media files",
        "existing_tab_summary": "Summary",
        "existing_tab_metadata": "Metadata Table",
        "existing_tab_preview": "Preview",
        "existing_tab_logs": "Logs",
        "existing_metric_mode": "Mode",
        "existing_metric_candidates": "Candidates",
        "existing_metric_selected": "Selected",
        "existing_metric_downloaded": "Downloaded",
        "existing_metric_skipped": "Skipped",
        "existing_no_summary": "No run_summary.json found",
        "existing_output_dir": "**Output directory:** `{path}`",
        "existing_files_on_disk": "**Files on disk:** {count}",
        "existing_dl_summary": "📥 Download run_summary.json",
        "existing_no_meta": "No metadata items",
        "existing_no_files": "No downloaded media files found",
        "existing_no_logs": "No log file found",
        "existing_logs_label": "Last 200 log lines",
        "existing_cannot_read": "Cannot read {path}",

        # Results section
        "results_title": "✅ Results — {mode}",
        "results_candidates": "Candidates",
        "results_selected": "Selected",
        "results_downloaded": "Downloaded",
        "results_skipped": "Skipped",
        "results_failed": "Failed",
        "results_output": "**Output:** `{dir}`",
        "results_meta_table": "📋 Metadata Table",
        "results_preview": "🖼️ Preview",
        "results_no_images": "No image files found yet (may still be downloading)",

        # Table headers
        "table_num": "#",
        "table_tweet_id": "Tweet ID",
        "table_author": "Author",
        "table_created": "Created",
        "table_likes": "Likes",
        "table_rts": "RTs",
        "table_type": "Type",
        "table_quality": "Quality",
        "table_width": "W",
        "table_height": "H",
    },
    "zh": {
        "page_title": "XScraper 网页控制台",
        "header_title": "🐦 XScraper 网页控制台",
        "header_desc": "搜索、排序、预览和下载 X/Twitter 媒体文件 — 基于 Streamlit 与 Playwright",
        "footer": "XScraper © 2026 — 所有凭证和 Cookies 仅存储在本地，不会上传到外部服务。",

        "lang_label": "语言",
        "lang_en": "English",
        "lang_zh": "中文",

        "sidebar_title": "⚙️ 全局设置",
        "output_dir": "输出根目录",
        "workers": "下载并发数",
        "proxy_optional": "代理地址（可选）",
        "proxy_placeholder": "http://127.0.0.1:7890",
        "cookies_path": "Cookies 文件路径",
        "profile_dir": "浏览器配置目录（可选）",
        "profile_placeholder": ".xscrape-browser-profile",
        "browser_channel": "浏览器通道",

        "mode_search": "🔍 X 登录搜索",
        "mode_login": "🔑 X 登录 / Cookies",
        "mode_api": "📡 官方 API 搜索",
        "mode_nitter": "🌐 Nitter 用户媒体",
        "mode_playwright": "🎭 Playwright 用户媒体",
        "mode_existing": "📂 查看历史结果",

        "login_title": "🔑 X 登录 — 保存浏览器 Cookies",
        "login_desc": "打开一个可见的浏览器窗口，供你手动登录 X。Cookies 将保存到本地，供其他模式复用。",
        "login_cookies_path": "Cookies 保存路径",
        "login_timeout": "登录超时（秒）",
        "login_profile": "浏览器配置目录（可选）",
        "login_channel": "浏览器通道",
        "login_status_auth": "✅ Cookies 文件已存在，包含 auth_token（{count} 个 cookies）",
        "login_status_noauth": "⚠️  Cookies 文件存在但未找到 auth_token（{count} 个 cookies）",
        "login_status_bad": "⚠️  Cookies 文件存在但无法解析",
        "login_status_none": "ℹ️  Cookies 文件不存在 — 请先运行登录",
        "login_btn": "🚀 打开登录浏览器",
        "login_status_start": "正在打开浏览器进行登录…",
        "login_success": "✅ 登录成功 — Cookies 已保存",
        "login_auth_detected": "已检测到 auth_token 并已保存！",
        "login_warn_auth_missing": "⚠️  登录完成但未检测到 auth_token",
        "login_warn_body": "浏览器已关闭，但未找到 auth_token。Cookies 仍已保存。",
        "login_failed": "❌ 登录失败",
        "login_error": "登录错误：{err}",

        "search_title": "🔍 X 登录搜索",
        "search_desc": "使用已认证的浏览器会话搜索 X。捕获 GraphQL 搜索结果，按质量分或点赞数排序，并下载选中的媒体。",
        "search_preset": "查询预设",
        "preset_ba_quality": "Blue Archive 精选",
        "preset_ba_broad": "Blue Archive 宽泛",
        "preset_custom": "自定义",
        "search_query": "搜索查询",
        "search_outname": "输出目录名",
        "search_top": "选取前 N 个媒体",
        "search_scrolls": "滚动次数",
        "search_tab": "搜索标签",
        "search_tab_live": "最新",
        "search_tab_top": "热门",
        "search_quality": "质量模式",
        "search_quality_help": "使用综合质量评分（点赞、转发、图片分辨率、内容惩罚词）",
        "search_order": "下载排序",
        "search_order_time": "按时间",
        "search_order_likes": "按点赞数",
        "search_advanced": "高级筛选",
        "search_min_likes": "最低点赞数",
        "search_min_rts": "最低转发数",
        "search_btn": "🔍 开始搜索",
        "search_no_cookies": "⚠️  未找到 Cookies 文件 — 请先运行 X 登录",
        "search_empty_query": "搜索查询不能为空",
        "search_starting": "正在开始搜索…",
        "search_loading_cookies": "正在启动浏览器并加载 Cookies…",
        "search_captured": "已捕获 {count} 个候选，正在筛选…",
        "search_no_results": "未找到结果",
        "search_no_results_body": "未找到媒体。请尝试放宽查询条件或增加滚动次数。",
        "search_filtered_out": "没有通过筛选的项目",
        "search_filtered_out_body": "所有候选均被筛除。请尝试降低最低要求。",
        "search_downloading": "正在下载 {count} 个文件…",
        "search_done": "✅ 搜索下载完成",
        "search_failed": "❌ 搜索失败",
        "search_error": "搜索错误：{err}",

        "api_title": "📡 官方 API 搜索",
        "api_desc": "使用 Twitter API v2 最近搜索接口。需要 Bearer Token。",
        "api_bearer": "Bearer Token",
        "api_query": "搜索查询",
        "api_query_help": "例如：(Blue Archive OR ブルアカ) has:images -is:retweet",
        "api_outname": "输出目录名",
        "api_count": "扫描推文数",
        "api_top": "选取前 N 个媒体",
        "api_order": "下载排序",
        "api_keyword": "关键词过滤（可选）",
        "api_keyword_placeholder": "仅下载包含该词的推文…",
        "api_since": "起始时间（ISO 8601，可选）",
        "api_since_placeholder": "2026-01-01T00:00:00Z",
        "api_until": "截止时间（ISO 8601，可选）",
        "api_until_placeholder": "2026-05-17T00:00:00Z",
        "api_btn": "📡 开始 API 搜索",
        "api_no_bearer": "必须提供 Bearer Token",
        "api_no_query": "搜索查询不能为空",
        "api_fetching": "正在从 API 获取推文…",
        "api_selecting": "已找到 {count} 个媒体，正在筛选…",
        "api_no_results": "无结果",
        "api_no_results_body": "未找到媒体。请尝试不同的查询。",
        "api_downloading": "正在下载 {count} 个文件…",
        "api_done": "✅ API 搜索完成",
        "api_failed": "❌ API 搜索失败",
        "api_error": "API 搜索错误：{err}",

        "nitter_title": "🌐 Nitter 用户媒体",
        "nitter_desc": "通过公共 Nitter 实例抓取用户的媒体标签页。无需认证。",
        "nitter_user": "用户名（不含 @）",
        "nitter_user_placeholder": "elonmusk",
        "nitter_instance": "Nitter 实例",
        "nitter_pages": "抓取页数",
        "nitter_btn": "🌐 开始 Nitter 抓取",
        "nitter_no_user": "必须填写用户名",
        "nitter_fetching": "正在从 Nitter 获取媒体…",
        "nitter_no_results": "未找到媒体",
        "nitter_no_results_body": "未找到 @{user} 的媒体。Nitter 实例可能已失效。",
        "nitter_downloading": "正在下载 {count} 个文件…",
        "nitter_done": "✅ Nitter 抓取完成",
        "nitter_failed": "❌ Nitter 抓取失败",
        "nitter_error": "Nitter 错误：{err}",

        "pw_title": "🎭 Playwright 用户媒体",
        "pw_desc": "在无头浏览器中打开 `x.com/{{username}}/media`，通过网络响应捕获媒体 URL。",
        "pw_user": "用户名（不含 @）",
        "pw_user_placeholder": "elonmusk",
        "pw_scrolls": "滚动次数",
        "pw_show": "显示浏览器窗口",
        "pw_btn": "🎭 开始 Playwright 抓取",
        "pw_no_user": "必须填写用户名",
        "pw_capturing": "正在打开浏览器并捕获媒体…",
        "pw_no_results": "未捕获到媒体",
        "pw_no_results_body": "未捕获到 @{user} 的媒体。X 可能需要登录。",
        "pw_downloading": "正在下载 {count} 个文件…",
        "pw_done": "✅ Playwright 抓取完成",
        "pw_failed": "❌ Playwright 抓取失败",
        "pw_error": "Playwright 错误：{err}",

        "existing_title": "📂 查看历史结果",
        "existing_desc": "浏览之前完成的运行，查看元数据和下载文件。",
        "existing_none": "在 `{dir}/` 下未找到包含 metadata.json 的输出目录",
        "existing_select": "选择要查看的运行",
        "existing_media_count": "📂 **{name}** — {count} 个媒体文件",
        "existing_tab_summary": "概要",
        "existing_tab_metadata": "元数据表",
        "existing_tab_preview": "预览",
        "existing_tab_logs": "日志",
        "existing_metric_mode": "模式",
        "existing_metric_candidates": "候选数",
        "existing_metric_selected": "选中数",
        "existing_metric_downloaded": "已下载",
        "existing_metric_skipped": "已跳过",
        "existing_no_summary": "未找到 run_summary.json",
        "existing_output_dir": "**输出目录：**`{path}`",
        "existing_files_on_disk": "**磁盘文件数：**{count}",
        "existing_dl_summary": "📥 下载 run_summary.json",
        "existing_no_meta": "没有元数据项",
        "existing_no_files": "未找到已下载的媒体文件",
        "existing_no_logs": "未找到日志文件",
        "existing_logs_label": "最近 200 行日志",
        "existing_cannot_read": "无法读取 {path}",

        "results_title": "✅ 结果 — {mode}",
        "results_candidates": "候选数",
        "results_selected": "选中数",
        "results_downloaded": "已下载",
        "results_skipped": "已跳过",
        "results_failed": "失败",
        "results_output": "**输出目录：**`{dir}`",
        "results_meta_table": "📋 元数据表",
        "results_preview": "🖼️ 预览",
        "results_no_images": "暂未找到图片文件（可能仍在下载中）",

        "table_num": "#",
        "table_tweet_id": "推文 ID",
        "table_author": "作者",
        "table_created": "创建时间",
        "table_likes": "点赞",
        "table_rts": "转发",
        "table_type": "类型",
        "table_quality": "质量分",
        "table_width": "宽",
        "table_height": "高",
    },
}


# ---------------------------------------------------------------------------
# i18n helper
# ---------------------------------------------------------------------------

def _(key: str, **kwargs) -> str:
    """Translate *key* into the current session language, interpolating *kwargs*."""
    lang = st.session_state.get("lang", "en")
    text = LANG.get(lang, LANG["en"]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODES = [
    _("mode_search"),
    _("mode_login"),
    _("mode_api"),
    _("mode_nitter"),
    _("mode_playwright"),
    _("mode_existing"),
]

BA_PRESETS = {
    _("preset_ba_quality"): (
        '(Blue Archive OR ブルアカ OR 블루아카) filter:images min_faves:5000 '
        'min_retweets:500 -filter:retweets -filter:quote '
        '-sketch -wip -meme -comic -漫画 -落書き -らくがき -rkgk -screenshot -AI'
    ),
    _("preset_ba_broad"): (
        '(Blue Archive OR ブルアカ OR 블루아카) filter:images '
        'min_faves:1000 -filter:retweets'
    ),
    _("preset_custom"): "",
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _read_file_safe(path: Path) -> str:
    """Read a text file, returning empty string on any error."""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _format_dt(dt_str: str) -> str:
    """Shorten an ISO datetime to a readable form."""
    if not dt_str:
        return "-"
    try:
        d = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return d.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str[:19]


def _discover_output_dirs(root: str) -> list[Path]:
    """Return subdirectories under *root* that contain metadata.json."""
    base = Path(root)
    if not base.exists():
        return []
    dirs = sorted(
        (d for d in base.iterdir() if d.is_dir() and (d / "metadata.json").exists()),
        key=lambda p: (p / "metadata.json").stat().st_mtime,
        reverse=True,
    )
    return dirs


def _prepare_download_items(items: list[dict]) -> list[dict]:
    """Copy selected items and set stable filename-oriented tweet_id values."""
    prepared = []
    for idx, source in enumerate(items, 1):
        item = dict(source)
        orig_tid = item.get("original_tweet_id") or item["tweet_id"]
        date = (item.get("created_at") or "unknown")[:10].replace("-", "")
        author = sanitize_filename(item.get("author_username") or "unknown")
        item["original_tweet_id"] = orig_tid
        item["tweet_id"] = f"{idx:02d}_{date}_likes{item.get('like_count', 0)}_{author}_{orig_tid}"
        prepared.append(item)

    return prepared


def _apply_search_filters(items: list[dict], min_likes: int, min_retweets: int) -> list[dict]:
    """Filter media list by minimum metrics."""
    result = items
    if min_likes > 0:
        result = [i for i in result if (i.get("like_count") or 0) >= min_likes]
    if min_retweets > 0:
        result = [i for i in result if (i.get("retweet_count") or 0) >= min_retweets]
    return result


def _write_run_summary(
    output_dir: Path,
    mode: str,
    query: str | None,
    candidate_count: int,
    selected_count: int,
    stats: dict,
) -> None:
    """Write run_summary.json into *output_dir*."""
    summary = {
        "mode": mode,
        "query": query or "",
        "started_at": st.session_state.get("_run_started", ""),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": candidate_count,
        "selected_count": selected_count,
        "stats": stats,
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _init_session_state() -> None:
    """Ensure Streamlit session state keys exist."""
    keys = {
        "lang": "zh",
        "run_started": False,
        "run_finished": False,
        "run_mode": None,
        "run_results": None,
        "run_stats": None,
        "run_output_dir": None,
        "run_candidates": 0,
        "run_selected": 0,
        "login_status": None,
        "search_results": None,
        "existing_selected_dir": None,
    }
    for k, default in keys.items():
        if k not in st.session_state:
            st.session_state[k] = default


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------


def _render_sidebar() -> dict:
    """Render sidebar global settings, return a config dict."""
    with st.sidebar:
        st.header(_("sidebar_title"))

        # Language toggle
        lang_opts = {"en": _("lang_en"), "zh": _("lang_zh")}
        current_lang = st.session_state.get("lang", "zh")
        selected_lang_label = st.selectbox(
            _("lang_label"),
            options=list(lang_opts.values()),
            index=0 if current_lang == "en" else 1,
            key="sidebar_lang_selector",
        )
        new_lang = "en" if selected_lang_label == lang_opts["en"] else "zh"
        if new_lang != current_lang:
            st.session_state["lang"] = new_lang
            st.rerun()

        st.divider()

        output_dir = st.text_input(_("output_dir"), value="output", key="sidebar_output")
        workers = st.slider(_("workers"), min_value=1, max_value=20, value=4, key="sidebar_workers")
        proxy = st.text_input(
            _("proxy_optional"), placeholder=_("proxy_placeholder"), key="sidebar_proxy"
        )
        if proxy and proxy.strip():
            proxy = proxy.strip()
        else:
            proxy = None

        st.divider()
        cookies_file = st.text_input(
            _("cookies_path"), value="x_cookies.json", key="sidebar_cookies"
        )
        profile_dir = st.text_input(
            _("profile_dir"),
            placeholder=_("profile_placeholder"),
            key="sidebar_profile",
        )
        if profile_dir and profile_dir.strip():
            profile_dir = profile_dir.strip()
        else:
            profile_dir = None

        channel = st.selectbox(
            _("browser_channel"),
            options=["msedge", "chrome", "chromium"],
            index=0,
            key="sidebar_channel",
        )
        if channel == "chromium":
            channel_val = None
        else:
            channel_val = channel

    return {
        "output_dir": output_dir,
        "workers": workers,
        "proxy": proxy,
        "cookies_file": cookies_file,
        "profile_dir": profile_dir,
        "channel": channel_val,
        "channel_display": channel,
    }


def _render_login_tab(cfg: dict) -> None:
    """X Login / Cookies mode."""
    st.subheader(_("login_title"))
    st.markdown(_("login_desc"))

    col1, col2 = st.columns(2)
    with col1:
        cookies_path = st.text_input(
            _("login_cookies_path"), value=cfg["cookies_file"], key="login_cookies_path"
        )
    with col2:
        timeout_s = st.number_input(
            _("login_timeout"), min_value=30, max_value=600, value=180, key="login_timeout"
        )

    col1, col2 = st.columns(2)
    with col1:
        login_profile = st.text_input(
            _("login_profile"),
            value=cfg.get("profile_dir") or "",
            placeholder=_("profile_placeholder"),
            key="login_profile",
        )
    with col2:
        login_channel = st.selectbox(
            _("login_channel"),
            options=["msedge", "chrome", "chromium"],
            index=["msedge", "chrome", "chromium"].index(cfg.get("channel_display", "msedge")),
            key="login_channel",
        )

    # Current login status
    cookies_file = Path(cookies_path)
    if cookies_file.exists():
        try:
            ck = json.loads(cookies_file.read_text(encoding="utf-8"))
            has_auth = any(c.get("name") == "auth_token" for c in ck)
            if has_auth:
                st.success(_("login_status_auth", count=len(ck)))
            else:
                st.warning(_("login_status_noauth", count=len(ck)))
        except Exception:
            st.warning(_("login_status_bad"))
    else:
        st.info(_("login_status_none"))

    if st.button(_("login_btn"), type="primary", width="stretch"):
        with st.status(_("login_status_start"), expanded=True) as status:
            try:
                chan = None if login_channel == "chromium" else login_channel
                result = asyncio.run(
                    save_x_cookies(
                        cookies_file=str(cookies_path),
                        timeout=timeout_s,
                        proxy=cfg["proxy"],
                        channel=chan,
                        profile_dir=login_profile or ".xscrape-browser-profile",
                    )
                )
                if result:
                    status.update(label=_("login_success"), state="complete")
                    st.success(_("login_auth_detected"))
                else:
                    status.update(label=_("login_warn_auth_missing"), state="complete")
                    st.warning(_("login_warn_body"))
            except Exception as exc:
                status.update(label=_("login_failed"), state="error")
                st.error(_("login_error", err=exc))


def _render_search_tab(cfg: dict) -> None:
    """X Logged-In Search mode."""
    st.subheader(_("search_title"))
    st.markdown(_("search_desc"))

    # Preset
    preset = st.selectbox(_("search_preset"), list(BA_PRESETS.keys()), key="search_preset")

    query = st.text_area(
        _("search_query"),
        value=BA_PRESETS.get(preset, ""),
        height=80,
        key="search_query_area",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        output_name = st.text_input(_("search_outname"), value="x_search", key="search_name")
    with col2:
        top_n = st.number_input(_("search_top"), min_value=1, max_value=500, value=10, key="search_top")
    with col3:
        scrolls = st.number_input(_("search_scrolls"), min_value=1, max_value=200, value=20, key="search_scrolls")

    col1, col2, col3 = st.columns(3)
    with col1:
        search_tab = st.selectbox(
            _("search_tab"), options=[_("search_tab_live"), _("search_tab_top")], index=0, key="search_tab"
        )
    with col2:
        quality_mode = st.checkbox(
            _("search_quality"), value=True, key="search_quality", help=_("search_quality_help")
        )
    with col3:
        download_order = st.selectbox(
            _("search_order"),
            options=[_("search_order_time"), _("search_order_likes")],
            index=0,
            key="search_order",
        )

    with st.expander(_("search_advanced")):
        col1, col2 = st.columns(2)
        with col1:
            st.number_input(_("search_min_likes"), min_value=0, value=0, key="search_min_likes")
        with col2:
            st.number_input(_("search_min_rts"), min_value=0, value=0, key="search_min_rts")

    # Build order string for backend
    order_map = {_("search_order_time"): "time", _("search_order_likes"): "likes"}
    download_order_val = order_map.get(download_order, "time")

    # Validate cookies
    cookies_path = Path(cfg["cookies_file"])
    cookies_ok = cookies_path.exists()
    if not cookies_ok:
        st.warning(_("search_no_cookies"))

    if st.button(_("search_btn"), type="primary", width="stretch", disabled=not cookies_ok):
        if not query.strip():
            st.error(_("search_empty_query"))
            return

        st.session_state["_run_started"] = datetime.now(timezone.utc).isoformat()

        # Phase 1: Capture
        with st.status(_("search_starting"), expanded=True) as status:
            try:
                status.update(label=_("search_loading_cookies"))
                tab_val = "live" if search_tab == _("search_tab_live") else "top"

                raw_items = asyncio.run(
                    scrape_x_search(
                        query=query.strip(),
                        top=top_n,
                        max_scrolls=scrolls,
                        headless=True,
                        proxy=cfg["proxy"],
                        cookies_file=str(cookies_path),
                        download_order=download_order_val,
                        tab=tab_val,
                        profile_dir=cfg.get("profile_dir"),
                        channel=cfg.get("channel"),
                        quality_mode=quality_mode,
                        return_candidates=True,
                    )
                )

                candidate_count = len(raw_items) if raw_items else 0
                status.update(label=_("search_captured", count=candidate_count))

                if not raw_items:
                    status.update(label=_("search_no_results"), state="complete")
                    st.warning(_("search_no_results_body"))
                    return

                # Apply additional filters
                min_likes_val = st.session_state.get("search_min_likes", 0)
                min_rts_val = st.session_state.get("search_min_rts", 0)
                filtered = _apply_search_filters(raw_items, min_likes_val, min_rts_val)
                if not filtered:
                    status.update(label=_("search_filtered_out"), state="complete")
                    st.warning(_("search_filtered_out_body"))
                    return

                # Rank against the full filtered pool, then rename for stable filenames.
                if quality_mode:
                    ranked = select_quality_media(filtered, top_n, download_order_val)
                else:
                    ranked = select_search_media(filtered, top_n, download_order_val)
                selected = _prepare_download_items(ranked)

                st.session_state["run_candidates"] = candidate_count
                st.session_state["run_selected"] = len(selected)

                # Phase 2: Download
                output_dir = Path(cfg["output_dir"]) / sanitize_filename(output_name)
                ensure_dir(str(output_dir))

                # Save metadata before download
                meta_file = output_dir / "metadata.json"
                meta_file.write_text(
                    json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                status.update(label=_("search_downloading", count=len(selected)))
                downloader = ImageDownloader(
                    str(output_dir), workers=cfg["workers"], proxy=cfg["proxy"]
                )

                progress_bar = st.progress(0.0)

                def _progress(done, actual_total, current_stats):
                    progress_bar.progress(done / actual_total)

                stats = downloader.download_all(
                    selected, on_progress=_progress, show_progress=False
                )

                _write_run_summary(
                    output_dir, "x_logged_in_search", query.strip(),
                    candidate_count, len(selected), stats,
                )

                st.session_state["run_finished"] = True
                st.session_state["run_results"] = selected
                st.session_state["run_stats"] = stats
                st.session_state["run_output_dir"] = str(output_dir.resolve())
                st.session_state["run_mode"] = _("mode_search")

                status.update(label=_("search_done"), state="complete")

            except Exception as exc:
                status.update(label=_("search_failed"), state="error")
                st.error(_("search_error", err=exc))
                return

def _render_api_search_tab(cfg: dict) -> None:
    """Official X API Search mode (recent search)."""
    st.subheader(_("api_title"))
    st.markdown(_("api_desc"))

    bearer = st.text_input(_("api_bearer"), type="password", key="api_bearer")
    query = st.text_area(
        _("api_query"), height=80, key="api_query", help=_("api_query_help")
    )

    col1, col2 = st.columns(2)
    with col1:
        output_name = st.text_input(_("api_outname"), value="api_search", key="api_name")
    with col2:
        count = st.number_input(
            _("api_count"), min_value=10, max_value=3200, value=100, step=10, key="api_count"
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        top_n = st.number_input(_("api_top"), min_value=1, max_value=500, value=10, key="api_top")
    with col2:
        download_order = st.selectbox(
            _("api_order"), options=[_("search_order_time"), _("search_order_likes")], index=0, key="api_order"
        )
    with col3:
        keyword = st.text_input(
            _("api_keyword"), placeholder=_("api_keyword_placeholder"), key="api_keyword"
        )

    col1, col2 = st.columns(2)
    with col1:
        since = st.text_input(
            _("api_since"), placeholder=_("api_since_placeholder"), key="api_since"
        )
    with col2:
        until = st.text_input(
            _("api_until"), placeholder=_("api_until_placeholder"), key="api_until"
        )

    if st.button(_("api_btn"), type="primary", width="stretch"):
        if not bearer.strip():
            st.error(_("api_no_bearer"))
            return
        if not query.strip():
            st.error(_("api_no_query"))
            return

        st.session_state["_run_started"] = datetime.now(timezone.utc).isoformat()

        with st.status(_("api_fetching"), expanded=True) as status:
            try:
                client = TwitterAPIClient(bearer.strip(), proxy=cfg["proxy"])

                all_images = []
                remaining = count
                next_token = None

                status.update(label=_("api_fetching"))
                while remaining > 0 and not st.session_state.get("_stop_requested"):
                    data = client.search_recent_tweets(
                        query.strip(),
                        min(remaining, 100),
                        next_token,
                        since=since.strip() or None,
                        until=until.strip() or None,
                    )
                    batch = client.extract_image_urls(data, keyword=keyword.strip() or None)
                    all_images.extend(batch)
                    next_token = data.get("meta", {}).get("next_token")
                    remaining -= 100
                    if not next_token:
                        break
                    time.sleep(1)

                candidate_count = len(all_images)
                status.update(label=_("api_selecting", count=candidate_count))

                if not all_images:
                    status.update(label=_("api_no_results"), state="complete")
                    st.warning(_("api_no_results_body"))
                    return

                order_val = "likes" if download_order == _("search_order_likes") else "time"
                ranked = select_search_media(all_images, top_n, order_val)
                selected = _prepare_download_items(ranked)

                st.session_state["run_candidates"] = candidate_count
                st.session_state["run_selected"] = len(selected)

                output_dir = Path(cfg["output_dir"]) / sanitize_filename(output_name)
                ensure_dir(str(output_dir))

                meta_file = output_dir / "metadata.json"
                meta_file.write_text(
                    json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                status.update(label=_("api_downloading", count=len(selected)))
                downloader = ImageDownloader(
                    str(output_dir), workers=cfg["workers"], proxy=cfg["proxy"]
                )

                progress_bar = st.progress(0.0)
                total_dl = len(selected)

                def _progress(done, _total, current_stats):
                    progress_bar.progress(done / total_dl)

                stats = downloader.download_all(
                    selected, on_progress=_progress, show_progress=False
                )

                _write_run_summary(
                    output_dir, "api_search", query.strip(),
                    candidate_count, len(selected), stats,
                )

                st.session_state["run_finished"] = True
                st.session_state["run_results"] = selected
                st.session_state["run_stats"] = stats
                st.session_state["run_output_dir"] = str(output_dir.resolve())
                st.session_state["run_mode"] = _("mode_api")

                status.update(label=_("api_done"), state="complete")

            except Exception as exc:
                status.update(label=_("api_failed"), state="error")
                st.error(_("api_error", err=exc))

def _render_nitter_tab(cfg: dict) -> None:
    """Nitter User Media mode."""
    st.subheader(_("nitter_title"))
    st.markdown(_("nitter_desc"))

    username = st.text_input(
        _("nitter_user"), key="nitter_user", placeholder=_("nitter_user_placeholder")
    )
    col1, col2 = st.columns(2)
    with col1:
        nitter_url = st.text_input(
            _("nitter_instance"), value="https://nitter.privacydev.net", key="nitter_url"
        )
    with col2:
        pages = st.number_input(
            _("nitter_pages"), min_value=1, max_value=50, value=5, key="nitter_pages"
        )

    if st.button(_("nitter_btn"), type="primary", width="stretch"):
        if not username.strip():
            st.error(_("nitter_no_user"))
            return

        st.session_state["_run_started"] = datetime.now(timezone.utc).isoformat()
        username = username.strip()

        with st.status(_("nitter_fetching"), expanded=True) as status:
            try:
                status.update(label=_("nitter_fetching"))
                client = NoAPIClient(nitter_url, proxy=cfg["proxy"])
                images = client.get_images_from_profile(username, pages=pages)

                if not images:
                    status.update(label=_("nitter_no_results"), state="complete")
                    st.warning(_("nitter_no_results_body", user=username))
                    return

                candidate_count = len(images)
                st.session_state["run_candidates"] = candidate_count
                st.session_state["run_selected"] = candidate_count

                output_dir = Path(cfg["output_dir"]) / sanitize_filename(username)
                ensure_dir(str(output_dir))

                meta_file = output_dir / "metadata.json"
                meta_file.write_text(
                    json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                status.update(label=_("nitter_downloading", count=candidate_count))
                downloader = ImageDownloader(
                    str(output_dir), workers=cfg["workers"], proxy=cfg["proxy"]
                )

                progress_bar = st.progress(0.0)

                def _progress(done, _total, current_stats):
                    progress_bar.progress(done / candidate_count)

                stats = downloader.download_all(
                    images, on_progress=_progress, show_progress=False
                )

                _write_run_summary(
                    output_dir, "nitter", username,
                    candidate_count, candidate_count, stats,
                )

                st.session_state["run_finished"] = True
                st.session_state["run_results"] = images
                st.session_state["run_stats"] = stats
                st.session_state["run_output_dir"] = str(output_dir.resolve())
                st.session_state["run_mode"] = _("mode_nitter")

                status.update(label=_("nitter_done"), state="complete")

            except Exception as exc:
                status.update(label=_("nitter_failed"), state="error")
                st.error(_("nitter_error", err=exc))

def _render_playwright_tab(cfg: dict) -> None:
    """Playwright User Media mode."""
    st.subheader(_("pw_title"))
    st.markdown(_("pw_desc"))

    username = st.text_input(
        _("pw_user"), key="pw_user", placeholder=_("pw_user_placeholder")
    )
    col1, col2 = st.columns(2)
    with col1:
        scrolls = st.number_input(_("pw_scrolls"), min_value=1, max_value=200, value=20, key="pw_scrolls")
    with col2:
        show_browser = st.checkbox(_("pw_show"), value=False, key="pw_show")

    if st.button(_("pw_btn"), type="primary", width="stretch"):
        if not username.strip():
            st.error(_("pw_no_user"))
            return

        st.session_state["_run_started"] = datetime.now(timezone.utc).isoformat()
        username = username.strip()

        with st.status(_("pw_capturing"), expanded=True) as status:
            try:
                status.update(label=_("pw_capturing"))
                cookies_path = Path(cfg["cookies_file"])
                cookies_arg = str(cookies_path) if cookies_path.exists() else None

                images = asyncio.run(
                    scrape_with_playwright(
                        username,
                        max_scrolls=scrolls,
                        headless=not show_browser,
                        proxy=cfg["proxy"],
                        cookies_file=cookies_arg,
                    )
                )

                if not images:
                    status.update(label=_("pw_no_results"), state="complete")
                    st.warning(_("pw_no_results_body", user=username))
                    return

                candidate_count = len(images)
                st.session_state["run_candidates"] = candidate_count
                st.session_state["run_selected"] = candidate_count

                output_dir = Path(cfg["output_dir"]) / sanitize_filename(username)
                ensure_dir(str(output_dir))

                meta_file = output_dir / "metadata.json"
                meta_file.write_text(
                    json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                status.update(label=_("pw_downloading", count=candidate_count))
                downloader = ImageDownloader(
                    str(output_dir), workers=cfg["workers"], proxy=cfg["proxy"]
                )

                progress_bar = st.progress(0.0)

                def _progress(done, _total, current_stats):
                    progress_bar.progress(done / candidate_count)

                stats = downloader.download_all(
                    images, on_progress=_progress, show_progress=False
                )

                _write_run_summary(
                    output_dir, "playwright", username,
                    candidate_count, candidate_count, stats,
                )

                st.session_state["run_finished"] = True
                st.session_state["run_results"] = images
                st.session_state["run_stats"] = stats
                st.session_state["run_output_dir"] = str(output_dir.resolve())
                st.session_state["run_mode"] = _("mode_playwright")

                status.update(label=_("pw_done"), state="complete")

            except Exception as exc:
                status.update(label=_("pw_failed"), state="error")
                st.error(_("pw_error", err=exc))

def _render_existing_tab(cfg: dict) -> None:
    """Browse and review existing output directories."""
    st.subheader(_("existing_title"))
    st.markdown(_("existing_desc"))

    dirs = _discover_output_dirs(cfg["output_dir"])
    if not dirs:
        st.info(_("existing_none", dir=cfg["output_dir"]))
        return

    dir_labels = [d.name for d in dirs]
    selected_name = st.selectbox(_("existing_select"), dir_labels, key="existing_select")

    selected_dir = None
    for d in dirs:
        if d.name == selected_name:
            selected_dir = d
            break

    if not selected_dir:
        return

    # Read metadata
    meta_path = selected_dir / "metadata.json"
    summary_path = selected_dir / "run_summary.json"

    try:
        items = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        st.error(_("existing_cannot_read", path=meta_path))
        return

    summary = {}
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    st.success(_("existing_media_count", name=selected_dir.name, count=len(items)))

    if summary:
        cols = st.columns(5)
        cols[0].metric(_("existing_metric_mode"), summary.get("mode", "-"))
        cols[1].metric(_("existing_metric_candidates"), summary.get("candidate_count", "-"))
        cols[2].metric(_("existing_metric_selected"), summary.get("selected_count", "-"))
        cols[3].metric(_("existing_metric_downloaded"), summary.get("stats", {}).get("downloaded", "-"))
        cols[4].metric(_("existing_metric_skipped"), summary.get("stats", {}).get("skipped", "-"))

    # Downloaded files
    downloaded_files = sorted(
        [f for f in selected_dir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".mp4", ".webp")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    tabs = st.tabs([
        _("existing_tab_summary"),
        _("existing_tab_metadata"),
        _("existing_tab_preview"),
        _("existing_tab_logs"),
    ])

    with tabs[0]:
        st.subheader(_("existing_tab_summary"))
        if summary:
            st.json(summary)
        else:
            st.info(_("existing_no_summary"))

        st.markdown(_("existing_output_dir", path=selected_dir.resolve()))
        st.markdown(_("existing_files_on_disk", count=len(downloaded_files)))

        if downloaded_files:
            st.download_button(
                _("existing_dl_summary"),
                data=json.dumps(summary, indent=2) if summary else "{}",
                file_name="run_summary.json",
                mime="application/json",
            )

    with tabs[1]:
        st.subheader(_("existing_tab_metadata"))
        if items:
            table_data = []
            for idx, item in enumerate(items, 1):
                table_data.append({
                    _("table_num"): idx,
                    _("table_tweet_id"): str(item.get("tweet_id", ""))[:20],
                    _("table_author"): item.get("author_username", "-"),
                    _("table_created"): _format_dt(item.get("created_at", "")),
                    _("table_likes"): item.get("like_count", 0),
                    _("table_rts"): item.get("retweet_count", 0),
                    _("table_type"): item.get("type", "photo"),
                    _("table_quality"): round(item.get("quality_score", 0), 0) if item.get("quality_score") else "-",
                    _("table_width"): item.get("width", "-"),
                    _("table_height"): item.get("height", "-"),
                })
            st.data_editor(table_data, width="stretch", hide_index=True, key="existing_metadata_table")
        else:
            st.info(_("existing_no_meta"))

    with tabs[2]:
        st.subheader(_("existing_tab_preview"))
        if not downloaded_files:
            st.info(_("existing_no_files"))
        else:
            cols = st.columns(4)
            for idx, fpath in enumerate(downloaded_files):
                col = cols[idx % 4]
                with col:
                    if fpath.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                        st.image(str(fpath), width="stretch")
                    st.caption(f"{fpath.name}")
                    st.caption(f"{fpath.stat().st_size / 1024:.0f} KB")

    with tabs[3]:
        st.subheader(_("existing_tab_logs"))
        log_path = Path("logs/scraper.log")
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            # Redact sensitive info
            log_text = _redact_sensitive(log_text)
            st.text_area(_("existing_logs_label"), log_text[-10000:], height=400)
        else:
            st.info(_("existing_no_logs"))


def _redact_sensitive(text: str) -> str:
    """Remove bearer tokens, cookie values, and auth headers from log text."""
    import re

    text = re.sub(r"Bearer\s+\S+", "Bearer ***REDACTED***", text)
    text = re.sub(r"auth_token[=:]\s*\S+", "auth_token=***REDACTED***", text)
    text = re.sub(r'"Authorization":\s*"[^"]+"', '"Authorization": "***REDACTED***"', text)
    return text


def _render_results_if_available() -> None:
    """If a run just finished, show results below the form."""
    if not st.session_state.get("run_finished"):
        return

    results = st.session_state["run_results"]
    stats = st.session_state["run_stats"]
    output_dir = st.session_state["run_output_dir"]
    mode = st.session_state["run_mode"]

    st.divider()
    st.subheader(_("results_title", mode=mode))

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(_("results_candidates"), st.session_state["run_candidates"])
    col2.metric(_("results_selected"), st.session_state["run_selected"])
    col3.metric(_("results_downloaded"), stats.get("downloaded", 0))
    col4.metric(_("results_skipped"), stats.get("skipped", 0))
    col5.metric(_("results_failed"), stats.get("failed", 0))

    st.markdown(_("results_output", dir=output_dir))

    if results:
        with st.expander(_("results_meta_table"), expanded=True):
            table_data = []
            for idx, item in enumerate(results, 1):
                table_data.append({
                    _("table_num"): idx,
                    _("table_author"): item.get("author_username", "-"),
                    _("table_created"): _format_dt(item.get("created_at", "")),
                    _("table_likes"): item.get("like_count", 0),
                    _("table_rts"): item.get("retweet_count", 0),
                    _("table_type"): item.get("type", "photo"),
                    _("table_quality"): round(item.get("quality_score", 0), 0) if item.get("quality_score") else "-",
                    _("table_width"): item.get("width", "-"),
                    _("table_height"): item.get("height", "-"),
                })
            st.data_editor(table_data, width="stretch", hide_index=True, key="run_results_metadata_table")

        with st.expander(_("results_preview")):
            output_path = Path(output_dir)
            image_files = sorted(
                [f for f in output_path.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp")],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:20]
            if image_files:
                cols = st.columns(4)
                for idx, fpath in enumerate(image_files):
                    with cols[idx % 4]:
                        try:
                            st.image(str(fpath), width="stretch")
                        except Exception:
                            st.warning(f"无法预览文件: {fpath.name}")
                        st.caption(fpath.name)
            else:
                st.info(_("results_no_images"))


def _render_mode_tabs(cfg: dict) -> None:
    """Render mode selector tabs and delegate to the matching render function."""
    tabs = st.tabs(MODES)
    with tabs[0]:
        _render_search_tab(cfg)
    with tabs[1]:
        _render_login_tab(cfg)
    with tabs[2]:
        _render_api_search_tab(cfg)
    with tabs[3]:
        _render_nitter_tab(cfg)
    with tabs[4]:
        _render_playwright_tab(cfg)
    with tabs[5]:
        _render_existing_tab(cfg)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def main() -> None:
    _init_session_state()

    # Header
    st.title(_("header_title"))
    st.markdown(_("header_desc"))

    # Sidebar
    cfg = _render_sidebar()

    # Mode tabs
    _render_mode_tabs(cfg)
    _render_results_if_available()

    # Footer
    st.divider()
    st.caption(_("footer"))


if __name__ == "__main__":
    main()

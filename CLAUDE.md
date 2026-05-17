# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable, with all extras)
python -m pip install -e .
python -m pip install -e .[browser]   # includes Playwright
python -m pip install -e .[tui]       # includes rich + questionary
python -m pip install -e .[all]       # both browser + tui
playwright install chromium           # only if using browser mode

# Run tests (4 test files: test_clients, test_cli, test_downloader, test_browser, test_utils)
python -m unittest discover tests -v
python -m unittest tests.test_clients -v
python -m unittest tests.test_cli -v
python -m unittest tests.test_downloader -v
python -m unittest tests.test_browser -v
python -m unittest tests.test_utils -v

# Profile scraping via Nitter (no auth needed)
xscrape <username> --nitter https://nitter.privacydev.net --pages 10

# Profile scraping via official API (needs Bearer Token)
xscrape <username> --bearer-token TOKEN --count 500

# API search mode: recent tweets by keyword, pick top N by likes
xscrape --bearer-token TOKEN \
  --search-query "(Blue Archive) has:images -is:retweet" \
  --count 100 --top 10 --download-order time

# Playwright browser mode (opens x.com/{user}/media)
xscrape-browser <username> --scrolls 30

# Interactive TUI wizard (questionary + rich)
xscrape interactive

# Save X login cookies via browser (opens login page, waits manually)
xscrape-login --cookies x_cookies.json --timeout 180 --channel msedge

# Logged-in X search with cookie auth + quality scoring
xscrape-x-search \
  --cookies x_cookies.json \
  --query "(Blue Archive) filter:images min_faves:1000" \
  --top 10 --download-order time --quality-mode

# Streamlit Web UI
streamlit run webui.py

# Legacy entry points (sys.path stubs)
python scraper.py <username> --nitter https://nitter.privacydev.net --pages 10
python playwright_scraper.py <username> --scrolls 30
```

## Architecture

Five CLI entry points share a common download pipeline:

```
CLI entry (cli.py / playwright_cli.py / x_login_cli.py / x_search_cli.py / tui.py)
  → Client (clients.py / browser.py)  →  Downloader (downloader.py)  →  output/
```

### Module map (`src/xscrape/`)

| Module | Purpose |
|--------|---------|
| `cli.py` | Argparse CLI for API/Nitter modes. Subcommands: `interactive`, `config`. Routes to profile scrape or search scrape. |
| `playwright_cli.py` | Argparse CLI for browser mode. Opens `x.com/{user}/media` via Playwright. |
| `x_login_cli.py` | Opens a visible browser to `x.com/login`, waits for manual login, saves cookies to JSON. |
| `x_search_cli.py` | Logged-in X search via Playwright. Uses cookie auth, scrolls search results, extracts GraphQL JSON, applies quality scoring. |
| `tui.py` | Interactive TUI wizard using `questionary` + `rich`. Wraps all three scraping modes with guided prompts. |
| `clients.py` | `TwitterAPIClient` (official v2 API) and `NoAPIClient` (Nitter scraping via regex). Both return `list[dict]` with url/tweet_id/type. |
| `browser.py` | Playwright async scraper. Three functions: `scrape_with_playwright` (profile media), `scrape_x_search` (search results), `save_x_cookies` (login). Includes quality scoring (`calculate_quality_score`), GraphQL JSON extractor (`extract_media_from_search_json`), and compact count parsing for CJK/KR. |
| `downloader.py` | `ImageDownloader` with thread pool, MD5 content dedup, skip-existing by filename, retry with exponential backoff (3 attempts), and `pending_downloads.json` resume on interrupt. |
| `config.py` | Load/save `~/.xscrape/config.toml`. Sections: `[defaults]`, `[auth]`, `[browser]`. |
| `console.py` | Rich `Console` singleton with custom theme (info/warning/error/success/highlight styles) and splash ASCII art. |
| `logging_utils.py` | One-time log config: `RichHandler` for console (colored), `RotatingFileHandler` for `logs/scraper.log`. |
| `utils.py` | `ensure_dir`, `sanitize_filename`, `file_hash` (MD5). |

### Entry points (from `pyproject.toml`)

| Command | Module |
|---------|--------|
| `xscrape` | `xscrape.cli:main` |
| `xscrape-browser` | `xscrape.playwright_cli:main` |
| `xscrape-login` | `xscrape.x_login_cli:main` |
| `xscrape-x-search` | `xscrape.x_search_cli:main` |

### Data flow

1. CLI parses args, creates `output/<username>/` directory
2. Client extracts images (API pagination / Nitter scrolling / Playwright network capture)
3. Metadata saved as `output/<username>/metadata.json`
4. `ImageDownloader` downloads all images concurrently
5. Stats logged: downloaded / skipped / failed

### Output structure

```
output/<username>/
├── metadata.json           # array of {url, tweet_id, type, ...}
├── pending_downloads.json  # temp file, cleared on success, persists on interrupt
├── 1234567890_image.jpg
└── ...
```

### Search & quality features

- **API search mode** (`--search-query`): Uses Twitter API v2 `/tweets/search/recent`. Selects top N by likes, then orders by time or likes for download.
- **X Search mode** (`xscrape-x-search`): Playwright-driven logged-in search. Parses X's GraphQL `SearchTimeline` JSON. Optional `--quality-mode` scores items by likes, retweets, quotes, image resolution, and penalizes sketches/WIP/AI/low-res.
- **`pending_downloads.json`**: If a download is interrupted (Ctrl+C), the pending list persists. On re-run, the user is prompted to resume without re-scanning.

## Important notes

- `.gitignore` excludes `logs/`, `output/`, `__pycache__/`, `.venv/`, `build/`, `dist/`
- Output directory structure: `output/<username>/{metadata.json, <tweet_id>_<filename>.jpg}`
- Nitter instances can be unreliable — fallback instances listed in `NoAPIClient.DEFAULT_INSTANCES`
- Playwright mode scrapes live `x.com` and may trigger login walls / requires cookies for search
- API mode requires a Twitter Developer Account with v2 access
- Config stored at `~/.xscrape/config.toml` (not in repo)
- Playwright login flow (`xscrape-login`) can use persistent profiles (`.xscrape-browser-profile/`) to avoid re-login
- No linters or formatters configured; tests are stdlib `unittest`

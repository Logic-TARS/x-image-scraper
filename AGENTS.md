# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable, with all extras)
python -m pip install -e .
python -m pip install -e .[browser]  # includes Playwright
playwright install chromium            # only if using browser mode

# Run (API/Nitter mode)
xscrape <username> --bearer-token TOKEN --count 500 --output output
xscrape <username> --nitter https://nitter.privacydev.net --pages 10
python -m xscrape <username> --nitter https://nitter.privacydev.net --pages 10

# Run (Playwright mode)
xscrape-browser <username> --scrolls 30 --output output

# Legacy entry points (compatibility stubs)
python scraper.py <username> --nitter https://nitter.privacydev.net --pages 10
python playwright_scraper.py <username> --scrolls 30
```

Tests use stdlib unittest (python -m unittest discover tests -v). CI is configured in .github/.

## Architecture

Three scraping modes share a common download pipeline:

```
CLI entry (cli.py / playwright_cli.py)
  → Client (clients.py / browser.py)  →  Downloader (downloader.py)  →  output/
```

- **`clients.py`** — `TwitterAPIClient` (official v2 API, requires Bearer Token) and `NoAPIClient` (Nitter instance scraping, no auth). Both return `list[dict]` with url/tweet_id/type.
- **`browser.py`** — Playwright async scraper that opens `x.com/{user}/media`, listens for `pbs.twimg.com/media/` network responses, and collects image URLs. Returns same format.
- **`downloader.py`** — `ImageDownloader` with thread pool, dedup by content hash, and skip-existing by filename. Shared across all three modes.
- **`cli.py`** — Argparse CLI for API/Nitter modes. Orchestrates client → metadata.json → downloader.
- **`playwright_cli.py`** — Argparse CLI for Playwright mode. Same pattern but calls `browser.py`.
- **`utils.py`** — `ensure_dir`, `sanitize_filename`, `file_hash` (MD5).
- **`logging_utils.py`** — One-time log config to console + file.

Root `scraper.py` / `playwright_scraper.py` are backward-compat stubs that inject `src/` into `sys.path`.

## Data flow

1. CLI parses args, creates output dir
2. Client extracts images (pagination/scroll loop)
3. Metadata saved as `output/<username>/metadata.json`
4. `ImageDownloader` downloads all images concurrently to `output/<username>/`
5. Stats logged: downloaded / skipped / failed

## Important notes

- `.gitignore` excludes `logs/`, `output/`, `__pycache__/`, `.venv/`, `build/`, `dist/`
- Output directory structure: `output/<username>/{metadata.json, <tweet_id>_<filename>.jpg}`
- Nitter instances can be unreliable — fallback instances listed in `NoAPIClient.DEFAULT_INSTANCES`
- Playwright mode scrapes live `x.com` and may trigger login walls in some sessions
- API mode requires a Twitter Developer Account with v2 access

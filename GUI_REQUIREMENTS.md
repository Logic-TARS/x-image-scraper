# XScraper Web GUI Requirements

## 1. Overview

XScraper Web GUI is a browser-based control console for searching, ranking, previewing, and downloading X/Twitter media with a focus on illustration discovery workflows. It extends the current command-line scraper into an operator-friendly web app while reusing the existing scraping, ranking, metadata, and download pipeline.

The primary use case is: find recent high-quality Blue Archive illustrations from X using an authenticated browser session, rank candidates by a quality score, download the selected top results, and inspect the output with metadata.

## 2. Goals

- Provide a browser UI for non-command-line operation.
- Support logged-in X web search through Playwright cookies.
- Support quality-based ranking, not only likes.
- Show progress and downloadable results clearly.
- Keep all credentials and cookies local.
- Reuse existing backend modules instead of duplicating scraping logic.
- Make failed states understandable and recoverable.

## 3. Non-Goals

- Do not bypass X, Google, or browser security controls.
- Do not copy or decrypt local browser cookie stores.
- Do not upload cookies, API keys, or downloaded media to any external service.
- Do not build a multi-user hosted service in this phase.
- Do not implement image aesthetic scoring with ML in the first version.

## 4. Target Users

- Primary: local operator who wants to discover and download high-quality illustration posts from X.
- Secondary: user who wants a visual alternative to `xscrape`, `xscrape-browser`, and `xscrape-x-search`.

## 5. Recommended Tech Stack

### Frontend

- Streamlit for first implementation, because `webui.py` already exists and project dependencies already include Streamlit.
- Browser-based UI served locally.
- No separate frontend build system in v1.

### Backend

- Python modules inside `src/xscrape`.
- Playwright for logged-in X search.
- Existing `ImageDownloader` for downloading and deduplication.
- JSON files for task metadata and results in v1.

Future version may migrate to FastAPI + React if task history, real-time queues, or richer galleries become too large for Streamlit.

## 6. Core User Flows

### 6.1 First-Time Login

1. User opens Web GUI.
2. User enters cookies file path, default `x_cookies.json`.
3. User clicks `Open Login Browser`.
4. App launches visible browser through Playwright using persistent profile mode.
5. User logs into X manually.
6. App detects `auth_token` cookie.
7. App saves cookies to local JSON file.
8. UI shows login status as ready.

### 6.2 X Quality Search And Download

1. User selects `X Logged-In Search`.
2. User enters query.
3. User configures:
   - Output name
   - Top N
   - Scroll count
   - Search tab: Latest or Top
   - Ranking mode: Quality score, Likes, or Time
   - Download/display order: Time descending or Likes descending
4. User clicks `Start Search`.
5. Backend opens X search in headless Playwright using saved cookies.
6. Backend captures X SearchTimeline GraphQL responses.
7. Backend extracts media, metrics, dimensions, and tweet metadata.
8. Backend ranks results.
9. Backend writes `metadata.json`.
10. Backend downloads selected media.
11. UI shows stats, metadata table, thumbnails, and output directory.

### 6.3 Review Existing Output

1. User selects an output directory from recent runs.
2. UI loads `metadata.json`.
3. UI displays:
   - Downloaded files
   - Tweet URL
   - Likes, retweets, quotes, replies
   - Quality score
   - Image dimensions
   - Timestamp
4. User can open local output folder.

### 6.4 Fallback Gallery Search

Optional v1.1.

If X login or search fails, user can run a fallback source such as Danbooru public API. UI must clearly label this as gallery score, not X likes.

## 7. Frontend Requirements

### 7.1 Layout

Use a practical dashboard layout:

- Header: app name, current mode, login status.
- Left sidebar: global settings.
- Main area: mode-specific form and run status.
- Result area: tabs for Summary, Metadata, Preview, Logs.

Avoid marketing-style landing pages. The first screen should be the working console.

### 7.2 Sidebar Controls

Global controls:

- Output root directory, default `output`.
- Workers, numeric input from 1 to 20.
- Proxy URL, optional.
- Cookies file path, default `x_cookies.json`.
- Browser profile directory, optional.
- Browser channel: `msedge`, `chrome`, `chromium`.

### 7.3 Mode Selector

Modes:

- X Logged-In Search
- X Login / Cookies
- Official X API Search
- Nitter User Media
- Playwright User Media
- Existing Results

Initial default should be `X Logged-In Search`.

### 7.4 X Logged-In Search Form

Fields:

- Query text area.
- Preset dropdown:
  - Blue Archive Quality
  - Blue Archive Broad
  - Custom
- Output name.
- Top N.
- Scroll count.
- Search tab:
  - Latest (`live`)
  - Top (`top`)
- Ranking mode:
  - Quality score
  - Likes
  - Time
- Download order:
  - Time descending
  - Likes descending
- Quality mode checkbox.
- Minimum likes.
- Minimum retweets.
- Since date.
- Exclude keywords.

Default Blue Archive Quality query:

```text
(Blue Archive OR ブルアカ OR 블루아카) filter:images min_faves:5000 min_retweets:500 -filter:retweets -filter:quote -sketch -wip -meme -comic -漫画 -落書き -らくがき -rkgk -screenshot -AI since:YYYY-MM-DD
```

The UI should generate the final query from structured inputs while still allowing manual override. Quality mode controls candidate ranking before Top N selection; download/display order controls how the selected Top N is presented and saved.

### 7.5 Login Form

Controls:

- Cookies path.
- Profile directory.
- Browser channel.
- Timeout seconds.
- Button: `Open Login Browser`.
- Login status indicator:
  - No cookies file
  - Cookies exist but not verified
  - Auth token detected
  - Login failed or timed out

The UI must not display cookie values.

### 7.6 Run Status

Display:

- Current phase:
  - Starting browser
  - Loading cookies
  - Opening search
  - Capturing results
  - Ranking
  - Downloading
  - Complete
- Parsed candidate count.
- Selected item count.
- Downloaded/skipped/failed count.
- Progress bar for downloads.
- Last log line.

### 7.7 Results Summary

Show summary cards:

- Candidates parsed.
- Selected media.
- Downloaded.
- Skipped.
- Failed.
- Highest like count.
- Highest quality score.

### 7.8 Metadata Table

Columns:

- Rank
- Thumbnail
- Tweet ID
- Author
- Created at
- Likes
- Retweets
- Quotes
- Replies
- Width
- Height
- Quality score
- Tweet URL
- Local file

Sorting should be enabled where Streamlit supports it.

### 7.9 Image Preview

Display a responsive grid of downloaded images.

Each item should show:

- Image thumbnail.
- Rank.
- Likes and quality score.
- Dimensions.
- Link to tweet.

If image file is missing, show a clear missing-file state.

### 7.10 Logs

Show recent log output in a scrollable text area.

Logs must redact:

- Bearer tokens.
- Cookie values.
- Full auth headers.

## 8. Backend Requirements

### 8.1 Module Boundaries

Recommended backend modules:

- `browser.py`
  - Playwright login.
  - X search scraping.
  - GraphQL response extraction.
- `downloader.py`
  - Concurrent downloading.
  - Deduplication.
  - Progress callback.
- `ranking.py` or functions in `browser.py`
  - Quality scoring.
  - Selection.
- `webui.py`
  - Streamlit UI orchestration only.

The UI should not directly call private methods such as `_download_one`.

### 8.2 X Search Backend Contract

Function:

```python
async def scrape_x_search(
    query: str,
    top: int,
    max_scrolls: int,
    headless: bool,
    proxy: str | None,
    cookies_file: str | None,
    download_order: str,
    tab: str,
    profile_dir: str | None,
    channel: str | None,
    quality_mode: bool,
) -> list[dict]:
    ...
```

Returned item fields:

```json
{
  "tweet_id": "2055604551689105733",
  "author_username": "artist",
  "created_at": "2026-05-16T11:01:31Z",
  "like_count": 12062,
  "retweet_count": 1154,
  "reply_count": 0,
  "quote_count": 0,
  "width": 2861,
  "height": 4004,
  "quality_score": 18519.0,
  "url": "https://pbs.twimg.com/media/....?format=jpg&name=orig",
  "type": "photo",
  "tweet_url": "https://x.com/user/status/id",
  "text": "..."
}
```

### 8.3 Quality Score

Initial formula:

```text
quality_score =
  likes
  + retweets * 3
  + quotes * 2
  - replies * 0.5
  + min(megapixels, 6) * 500
  - penalties
```

Penalties:

- Minimum dimension below 900 px: `-1500`.
- Text contains sketch/wip/meme/comic/screenshot/AI/rkgk/落書き/らくがき/漫画: `-3000`.

The formula must be configurable in future, but hardcoded is acceptable in v1.

### 8.4 Download Backend Contract

Function:

```python
ImageDownloader.download_all(
    items: list[dict],
    on_progress: Callable[[int, int, dict], None] | None = None,
    show_progress: bool = True,
) -> dict
```

Stats:

```json
{
  "downloaded": 10,
  "skipped": 0,
  "failed": 0
}
```

### 8.5 Task State

For v1, each run writes files under:

```text
output/<run_name>/
  metadata.json
  run_summary.json
  logs.txt
  <downloaded media files>
```

`run_summary.json` should include:

```json
{
  "mode": "x_logged_in_search",
  "query": "...",
  "started_at": "...",
  "finished_at": "...",
  "candidate_count": 416,
  "selected_count": 10,
  "stats": {
    "downloaded": 10,
    "skipped": 0,
    "failed": 0
  }
}
```

### 8.6 Error Handling

Required user-facing errors:

- Cookies file missing.
- Cookies expired or no `auth_token`.
- X redirects to login page.
- X search returns no candidates.
- Playwright is not installed.
- Browser channel not found.
- Profile directory is locked by an open browser.
- Download failed due to HTTP error.
- Output path is not writable.

Errors should include suggested next action.

### 8.7 Security Requirements

- Never display cookie values.
- Never display Bearer Token values.
- Avoid writing secrets to logs.
- Add `x_cookies.json`, `.xscrape-browser-profile/`, and browser profile directories to `.gitignore`.
- Do not copy cookies from installed browsers automatically.
- Only use cookies explicitly saved by the user through the app or explicitly selected profile directories.

## 9. Data Persistence

### 9.1 Metadata

`metadata.json` stores selected items only.

Optional `candidates.json` stores all parsed candidates for debugging.

### 9.2 File Naming

Downloaded media should use:

```text
<rank>_<YYYYMMDD>_likes<like_count>_<author>_<tweet_id>_<media_id>.<ext>
```

If author is unknown:

```text
unknown
```

Filenames must be sanitized for Windows.

### 9.3 Deduplication

Use content MD5 as currently implemented.

The UI should hide `.hash_*` marker files from previews.

## 10. Acceptance Criteria

### 10.1 Login

- User can open a visible browser from Web UI.
- User can log into X manually.
- Cookies are saved locally.
- UI can detect whether cookies include `auth_token`.

### 10.2 Search

- User can run Blue Archive Quality preset.
- App captures GraphQL search responses.
- App extracts at least:
  - media URL
  - tweet ID
  - created time
  - likes
  - retweets
  - image dimensions
- App ranks by quality mode when enabled.

### 10.3 Download

- App downloads selected top N images.
- App shows progress.
- App writes `metadata.json`.
- App shows downloaded image previews.
- Failed downloads are reflected in stats.

### 10.4 Safety

- No token or cookie values appear in UI logs.
- Existing unrelated output directories are not deleted unless the user explicitly selects and confirms deletion.

## 11. Implementation Plan

### Phase 1: Streamlit GUI MVP

- Refactor `webui.py` into clear sections.
- Add X Login tab.
- Add X Search tab.
- Add quality mode controls.
- Add result preview from output folder.
- Add run summary writing.

### Phase 2: Better Task Management

- Add task history.
- Add cancel button.
- Add retry failed downloads.
- Add candidates export.

### Phase 3: Advanced Quality Filtering

- Add configurable scoring weights.
- Add minimum resolution filters.
- Add duplicate tweet grouping.
- Add optional perceptual hash duplicate detection.

### Phase 4: Alternative Sources

- Add Danbooru fallback mode.
- Add Pixiv mode if user provides logged-in cookies.

## 12. Open Questions

- Should the GUI default to using `x_cookies.json` or a persistent profile directory?
- Should all candidates be saved for later manual selection?
- Should multi-image tweets count as one post or multiple media entries?
- Should ranking happen per tweet or per image?
- Should output include an HTML gallery report?

## 13. Current Known Limitations

- X page and GraphQL structures can change.
- Author username extraction may be incomplete in some GraphQL result variants.
- Search operators are not guaranteed stable.
- X may rate-limit or challenge logged-in browser sessions.
- Quality score is heuristic, not true aesthetic judgment.

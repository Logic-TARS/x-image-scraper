# XScrape

批量下载 X/Twitter 用户媒体图片，支持 **官方 API**、**Nitter**、**Playwright** 三种采集模式。

## 安装

```bash
# 基础安装（requests）
pip install -e .

# 如需 Playwright 浏览器模式
pip install -e .[browser]
playwright install chromium

# 或用 requirements.txt
pip install -r requirements.txt
```

## 快速开始

```bash
# Nitter 模式（无需 API Key）
xscrape elonmusk --nitter https://nitter.privacydev.net --pages 10

# Playwright 浏览器模式
xscrape-browser elonmusk --scrolls 30

# 第一次使用 X 网页搜索：打开浏览器，手动登录后保存 cookies
xscrape-login --cookies x_cookies.json --timeout 180 --channel msedge

# 之后可后台使用已登录 cookies 搜索，按点赞数选前 10 个媒体，再按时间下载
xscrape-x-search ^
  --cookies x_cookies.json ^
  --query "(Blue Archive OR ブルアカ OR 블루아카) filter:images min_faves:1000 -filter:retweets" ^
  --name bluearchive_x_recent_top10 ^
  --top 10 ^
  --download-order time ^
  --scrolls 30 ^
  --quality-mode

# 官方 API 模式（需 Bearer Token）
xscrape elonmusk --bearer-token YOUR_TOKEN --count 500

# 官方 API 最近搜索：按点赞数选前 10 个媒体，再按时间从新到旧下载
xscrape --bearer-token YOUR_TOKEN ^
  --search-query "(Blue Archive OR ブルアカ OR 블루아카) has:images -is:retweet" ^
  --search-name bluearchive_recent_top10 ^
  --count 100 ^
  --top 10 ^
  --download-order time
```

## 三种模式对比

| 模式 | 命令 | 依赖 | 需 API Key | 稳定性 |
|------|------|------|-----------|--------|
| 官方 API | `xscrape --bearer-token` | `requests` | 是 | 高 |
| Nitter | `xscrape --nitter` | `requests` | 否 | 中（依赖实例） |
| Playwright | `xscrape-browser` | `playwright` | 否 | 中（可能触发风控） |

## 参数说明

### `xscrape`（API / Nitter 模式）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `username` | 必填 | 目标用户名（不含 `@`） |
| `-o, --output` | `output` | 图片保存目录 |
| `-n, --count` | `200` | API 模式最大推文数 |
| `-w, --workers` | `4` | 并发下载线程数 |
| `--bearer-token` | — | Twitter Bearer Token |
| `--nitter` | 自动选择 | Nitter 实例 URL |
| `--pages` | `5` | Nitter 翻页数 |
| `--search-query` | — | 官方 API 最近搜索查询，提供后进入搜索模式 |
| `--search-name` | 查询词生成 | 搜索模式输出目录名 |
| `--top` | `10` | 搜索模式按点赞数选取的媒体数量 |
| `--download-order` | `time` | 搜索模式下载排序：`time` 或 `likes` |
| `--since` / `--until` | — | API 时间过滤，ISO 8601 格式 |

### `xscrape-browser`（Playwright 模式）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `username` | 必填 | 目标用户名（不含 `@`） |
| `-o, --output` | `output` | 图片保存目录 |
| `-s, --scrolls` | `20` | 自动滚动次数 |
| `-w, --workers` | `4` | 下载并发数 |
| `--show-browser` | 关闭 | 显示浏览器窗口 |

### `xscrape-login`（保存 X 登录态）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--cookies` | `x_cookies.json` | Cookies 保存路径 |
| `--timeout` | `180` | 等待手动登录的秒数 |
| `--proxy` | — | 代理服务器地址 |
| `--channel` | `msedge` | 浏览器通道：`msedge`、`chrome` 或 `chromium` |
| `--profile-dir` | `.xscrape-browser-profile` | 持久化浏览器配置目录 |

### `xscrape-x-search`（已登录 X 搜索）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--query` | 必填 | X 搜索查询 |
| `--cookies` | `x_cookies.json` | 登录 cookies 文件 |
| `--name` | `x_search` | 输出子目录名 |
| `--top` | `10` | 按点赞数选取的媒体数量 |
| `--download-order` | `time` | 下载排序：`time` 或 `likes` |
| `--tab` | `live` | X 搜索 tab：`live` 或 `top` |
| `--show-browser` | 关闭 | 显示浏览器窗口，默认后台运行 |
| `--quality-mode` | 关闭 | 使用综合质量分排序：点赞、转发、引用、图片尺寸和排除词 |

## 输出结构

```
output/
└── <username>/
    ├── metadata.json       # 图片 URL、推文 ID、时间等元数据
    ├── 1234567890_xxx.jpg
    └── ...
```

- 内容去重：相同 MD5 只存一份
- 断点续传：已存在文件自动跳过
- 元数据保存：每次运行写入 `metadata.json`
- 运行日志：`logs/scraper.log`

## 常用 Nitter 实例

- `https://nitter.privacydev.net`
- `https://nitter.poast.org`
- `https://nitter.1d4.us`

## 作为模块使用

```python
from xscrape.clients import NoAPIClient
from xscrape.downloader import ImageDownloader

client = NoAPIClient("https://nitter.privacydev.net")
images = client.get_images_from_profile("username", pages=5)

dl = ImageDownloader("output/username", workers=4)
stats = dl.download_all(images)
print(stats)  # {"downloaded": 10, "skipped": 3, "failed": 0}
```

## 项目结构

```
src/xscrape/
├── __init__.py          # 包信息
├── __main__.py          # python -m xscrape 入口
├── cli.py               # API/Nitter 模式编排
├── playwright_cli.py    # Playwright 模式编排
├── clients.py           # TwitterAPIClient + NoAPIClient
├── browser.py           # Playwright 抓取逻辑
├── downloader.py        # 下载引擎（去重、并发、断点）
├── logging_utils.py     # 日志配置
└── utils.py             # 工具函数
```

## 注意事项

- 仅下载公开账号的公开内容
- Nitter 实例可能不稳定，失败时切换实例
- API 模式受 Twitter 开发者权限和速率限制
- Playwright 模式可能触发 X 登录墙

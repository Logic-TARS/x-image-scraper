# 🐦 X (Twitter) 图片自动爬取工具

自动批量下载 X (原 Twitter) 用户的媒体图片，支持三种爬取模式。

---

## 📁 项目结构

```
x-image-scraper/
├── src/
│   ├── scraper.py            # 主爬取模块（API + Nitter 模式）
│   └── playwright_scraper.py # 浏览器自动化模式
├── output/                   # 下载图片输出目录
├── logs/                     # 运行日志
├── requirements.txt
└── README.md
```

---

## 🚀 三种爬取模式

### 模式 1：官方 API 模式（推荐，稳定）

需要 Twitter Developer Account 申请 **Bearer Token**。

```bash
python src/scraper.py elonmusk \
  --bearer-token YOUR_BEARER_TOKEN \
  --count 500 \
  --output output
```

**获取 Bearer Token：**
1. 访问 https://developer.twitter.com/en/portal/dashboard
2. 创建项目 → 获取 Bearer Token（免费版每月 500,000 条推文读取）

---

### 模式 2：Nitter 免 API 模式（无需注册）

通过 Nitter（X 的开源镜像前端）爬取，**无需任何 API Key**。

```bash
python src/scraper.py elonmusk \
  --nitter https://nitter.privacydev.net \
  --pages 10 \
  --output output
```

**可用 Nitter 实例（任选其一）：**
- https://nitter.privacydev.net
- https://nitter.poast.org
- https://nitter.1d4.us
- https://nitter.net

> ⚠️ Nitter 实例可能不稳定，若失败请更换实例

---

### 模式 3：Playwright 浏览器自动化（最强，绕过反爬）

模拟真实浏览器操作，自动滚动页面抓取图片链接。

```bash
# 安装 Playwright
pip install playwright
playwright install chromium

# 运行（无头模式）
python src/playwright_scraper.py elonmusk --scrolls 30 --output output

# 可视化运行（显示浏览器窗口，便于调试）
python src/playwright_scraper.py elonmusk --show-browser
```

---

## ⚙️ 安装

```bash
# 克隆项目
git clone <repo-url>
cd x-image-scraper

# 安装依赖
pip install -r requirements.txt

# （可选）安装 Playwright 浏览器驱动
playwright install chromium
```

---

## 📋 参数说明

### scraper.py 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `username` | 必填 | 目标用户名（不含 @） |
| `-o / --output` | `output` | 图片保存目录 |
| `-n / --count` | `200` | 最多爬取推文数（API模式） |
| `-w / --workers` | `4` | 并发下载线程数 |
| `--bearer-token` | 无 | Twitter Bearer Token |
| `--nitter` | 自动选择 | Nitter 实例 URL |
| `--pages` | `5` | Nitter 翻页数 |

### playwright_scraper.py 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `username` | 必填 | 目标用户名 |
| `-s / --scrolls` | `20` | 自动滚动次数（越多图越多）|
| `-w / --workers` | `4` | 下载并发数 |
| `--show-browser` | 隐藏 | 显示浏览器窗口 |

---

## 📂 输出说明

```
output/
└── elonmusk/
    ├── metadata.json        # 图片元数据（URL、推文ID、时间）
    ├── tweet123_photo.jpg
    ├── tweet456_photo.jpg
    └── ...
```

- **自动去重**：相同内容只下载一次（MD5 校验）
- **断点续传**：已下载的文件自动跳过
- **元数据保存**：所有图片的来源推文信息保存至 `metadata.json`

---

## ⚡ 使用示例

```bash
# 下载 NASA 的所有媒体图片（Nitter 免API模式）
python src/scraper.py NASA --nitter https://nitter.privacydev.net --pages 20

# 下载某用户图片（官方API，最多1000张，8线程）
python src/scraper.py username --bearer-token xxxx --count 1000 --workers 8

# 浏览器模式，滚动50次，获取大量图片
python src/playwright_scraper.py username --scrolls 50 --workers 6
```

---

## ⚠️ 注意事项

1. **仅下载公开账号**的公开内容，请遵守 X 服务条款
2. 添加适当的请求延迟（已内置），避免对服务器造成压力
3. 官方 API 免费版有速率限制（15分钟/15次）
4. 本工具仅供学习研究使用

---

## 🔧 常见问题

**Q: Nitter 返回空页面？**
A: 更换 Nitter 实例，或改用 Playwright 模式

**Q: API 返回 403？**
A: Bearer Token 权限不足，检查 Developer Portal 中的 App 权限设置

**Q: Playwright 模式图片为空？**
A: 尝试 `--show-browser` 查看页面状态，可能需要手动登录

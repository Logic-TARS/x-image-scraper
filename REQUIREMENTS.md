# XScrape 交互体验改进 — 需求文档

## 1. 概述

当前 XScrape 是一个纯命令行工具，输出为黑白文本日志。目标是将其升级为**交互式终端 UI（TUI）工具**，同时补齐功能缺口，让用户能直观地配置、执行和监控抓取任务。

### 核心设计原则

- **不增加使用门槛** — 保留 CLI 一键执行能力，交互模式作为可选项
- **实时反馈** — 所有操作立即可见，不黑盒
- **配置记忆** — 用户不用每次重复输入参数

---

## 2. 用户界面方案

### 2.1 主界面模式（Rich CLI）

选择 Rich CLI，兼顾视觉效果与低复杂度，依赖 `rich` + `questionary` 两个库。

### 2.2 交互式流程

```
启动 → 选择采集模式 → 填写参数 → 预览 → 执行 → 查看结果
```

每一步都有彩色提示和默认值引导。

---

## 3. 功能需求

### F1: 交互式模式 (xscrape interactive)

新增 `xscrape interactive` 子命令，进入问答式引导流程：

1. **选择采集模式**
   - 选项：API / Nitter / Playwright
   - 每个选项显示简要说明和前置条件

2. **填写参数**
   - 目标用户名（必填，交互校验格式）
   - 各模式专属参数（API Token、Nitter 实例、滚动次数等）
   - 输出目录（默认 `output/`，Tab 自动补全）
   - 并发下载数

3. **任务预览**
   - 以表格形式展示所有参数
   - 确认后开始执行

4. **执行过程实时展示**
   - 实时日志面板（分色显示 INFO / WARN / ERROR）
   - 下载进度条（图片级 + 总体百分比）
   - 统计面板（已下载 / 跳过 / 失败 实时更新）

5. **结果报告**
   - 执行完毕后展示汇总面板
   - 包含：总图片数、耗时、成功率、输出路径
   - 提供选项：打开输出目录 / 查看 metadata.json / 退出

### F2: 彩色日志输出

改进现有 CLI 模式的日志输出：

- INFO = 青色 / 绿色
- WARNING = 黄色
- ERROR = 红色
- 关键数据（下载数量、URL）用加粗/高亮
- 日志格式简洁化，去掉冗余时间戳（交互模式下）

### F3: 进度条

无论交互模式还是 CLI 模式，下载时显示进度条：

- `tqdm` 或 `rich.progress` 实现
- 显示：当前文件 / 总文件数、实时速度、预计剩余时间
- 多线程下载时保持进度条不乱

### F4: 配置管理与记忆

新增配置文件 `~/.xscrape/config.toml`，支持：

```toml
[defaults]
output_dir = "output"
workers = 4
nitter_instance = "https://nitter.privacydev.net"

[auth]
bearer_token = "..."      # 可选，明文存储时给出安全提示

[browser]
headless = true
scrolls = 20
```

- `xscrape config` 子命令：查看 / 编辑配置
- 交互模式下自动加载配置作为默认值
- 支持 `--no-config` 跳过配置

### F5: 视频/GIF 下载支持

当前只下载图片，需扩展：

- API 模式：已检测到 video/animated_gif 类型，下载最佳质量版本
- Nitter 模式：解析视频/GIF 链接
- Playwright 模式：捕获视频请求
- 文件命名区分：`xxx_photo.jpg`、`xxx_video.mp4`、`xxx_gif.gif`

### F6: 下载重试机制

- 失败自动重试，默认 3 次
- 指数退避（1s → 3s → 9s）
- 可配置 `--retry` 参数

### F7: 代理支持

- 新增 `--proxy` 参数，支持 `http://`、`https://`、`socks5://`
- 所有 HTTP 请求（包括 Playwright）通过代理
- 配置文件中可持久化

### F8: 断点续传增强

- 运行中断后重新运行，跳过已下载文件（已有）
- **增强**：保存已扫描但未下载的图片列表，下次自动继续下载而无需重新扫描页面

### F9: 操作快捷键

交互模式下的快捷键：

| 按键 | 功能 |
|------|------|
| `Ctrl+C` | 安全停止（下载完当前批次后退出）|
| `q` | 返回上一步（参数填写环节） |
| `o` | 结果页打开输出目录 |

### F10: 启动画面

```
╔══════════════════════════════════════╗
║        XScrape — X 媒体采集工具       ║
║        三种模式 · 高速下载 · 去重      ║
╚══════════════════════════════════════╝
```

---

## 4. 技术方案

### 4.1 新增依赖

| 库 | 用途 | 必要性 |
|----|------|--------|
| `rich>=13.0` | 彩色终端输出、进度条、表格、面板 | 核心 |
| `questionary>=2.0` | 交互式问答选择 | 交互模式 |
| `tomli` / `tomllib` (py3.11+) | 配置解析 | 配置管理 |
| `tqdm>=4.60` | 轻量进度条（CLI 模式用） | 可选（可用 rich 替代） |

### 4.2 新增 / 修改文件

| 文件 | 说明 |
|------|------|
| `src/xscrape/tui.py` | 交互模式主流程（新增） |
| `src/xscrape/config.py` | 配置读写（新增） |
| `src/xscrape/console.py` | Rich Console 单例、样式定义（新增） |
| `src/xscrape/cli.py` | 增加 `interactive` 子命令、彩色日志（修改） |
| `src/xscrape/downloader.py` | 增加进度条回调、重试逻辑（修改） |
| `src/xscrape/clients.py` | 视频/GIF 支持、代理透传（修改） |
| `src/xscrape/browser.py` | 代理支持、视频捕获（修改） |

### 4.3 架构调整

```
用户输入层                   业务逻辑层                   输出层
┌──────────┐     ┌──────────────────────┐     ┌──────────────┐
│ CLI args  │────→│  cli.py (编排)       │────→│ downloader   │
│ (argparse)│     │  clients.py (采集)   │     │ (并发下载)    │
├──────────┤     │  browser.py (Play)   │     │              │
│ TUI       │────→│                      │     │ metadata.json│
│ (question │     │  config.py (配置)    │     │              │
│  + rich)  │     │  logging_utils.py    │     │ 终端日志/进度 │
└──────────┘     └──────────────────────┘     └──────────────┘
```

### 4.4 依赖分组调整（pyproject.toml）

```toml
[project.optional-dependencies]
browser = ["playwright>=1.40.0"]
tui = ["rich>=13.0", "questionary>=2.0"]   # 新增
all = ["xscrape[browser,tui]"]
```

---

## 5. 用户故事

### 故事 1：小白用户

> "我不懂 API Token，就想下点图片。"

运行 `xscrape interactive` → 选择 Nitter 模式 → 输入用户名 → 默认参数执行 → 看进度条跑完 → 打开文件夹查看。

### 故事 2：高频用户

> "我每周都要下几个人的图，每次都输一样的参数太烦了。"

配置文件中写好默认参数 → `xscrape interactive` 自动加载 → 只需改用户名 → 直接确认执行。

### 故事 3：开发者

> "我想集成到脚本里。"

照旧使用 `xscrape username --bearer-token xxx` 非交互模式，输出不变，不受 TUI 影响。

### 故事 4：网络受限用户

> "公司网络需要代理。"

`xscrape username --nitter xxx --proxy socks5://127.0.0.1:1080`，或在配置文件中设置一次。

---

## 6. 验收标准

- [ ] `xscrape interactive` 进入交互式引导，所有参数可通过问答填写
- [ ] 执行过程显示彩色日志和实时进度条
- [ ] 完成后展示汇总报告
- [ ] 配置文件读写正确，交互模式自动加载
- [ ] 非交互模式 `xscrape username --nitter xxx` 完全不受影响
- [ ] 视频/GIF 下载可工作（至少 API 模式）
- [ ] 下载失败自动重试，不丢数据
- [ ] `--proxy` 参数在所有模式下生效
- [ ] `Ctrl+C` 优雅退出，不残留孤儿进程

---

## 7. 非功能需求

- Python ≥ 3.10
- Windows / macOS / Linux 兼容（终端颜色自适应）
- TUI 模式依赖 `rich` + `questionary`，不安装则回退为纯文本 CLI
- 日志文件仍然保持纯文本格式，不受终端颜色影响

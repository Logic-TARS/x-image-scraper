# 功能清单 & 开发计划

## 核心功能（已有）

- [x] 官方 Twitter API v2 图片采集
- [x] Nitter 免 API 图片采集
- [x] Playwright 浏览器自动化采集
- [x] 图片并发下载（ThreadPoolExecutor）
- [x] MD5 内容去重
- [x] 断点跳过（已存在文件自动跳过）
- [x] metadata.json 元数据导出
- [x] 文件日志 + 控制台日志

## 待实现功能

### 高优先级

- [x] **视频下载** — 当前仅下载图片，需支持视频 / GIF 下载（API 模式已有 media_type 字段）
- [x] **下载进度条** — 使用 `tqdm` 显示实时下载进度
- [x] **重试机制** — 下载失败自动重试（可配置次数和退避策略）
- [x] **代理支持** — 支持 HTTP/HTTPS/SOCKS 代理，通过 `--proxy` 参数传入

### 中优先级

- [x] **配置化** — 支持 `config.toml` / `config.yaml` 配置文件，避免每次输入 bearer token 等参数
- [x] **日期过滤** — 按时间范围筛选推文 (`--since`, `--until`)
- [x] **关键词过滤** — 只下载包含特定关键词的推文中的图片
- [x] **Cookies / 登录态** — Playwright 模式支持加载已有 cookie 绕过登录墙
- [ ] **暂停 / 恢复下载** — 中断后可从断点恢复，无需重新扫描
- [x] **Docker 镜像** — 提供 Dockerfile，方便部署运行

### 低优先级

- [x] **单元测试** — 针对 clients.py、downloader.py、utils.py 编写测试
- [x] **CI/CD** — GitHub Actions 自动测试 + 构建
- [x] **多用户批量模式** — 从文件读取用户列表批量运行
- [x] **保存为 PDF/HTML 归档** — 将推文内容存档为可阅读的离线页面
- [x] **Web UI** — 简单的 Web 界面管理抓取任务
- [ ] **i18n 支持** — 英文 / 日文等多语言
- [ ] **发布到 PyPI** — 支持 `pip install xscrape`

## 技术债 / 改进项

- [x] **异常处理细化** — 区分网络错误、解析错误、权限错误，给出更明确的提示
- [ ] **类型注解完善** — 补充函数返回值类型，引入 `dataclass` 替代 dict 传递
- [x] **日志轮转** — 使用 `RotatingFileHandler` 避免日志文件无限增长
- [ ] **响应式重试** — Nitter 模式根据 HTTP 状态码（429、503 等）自适应退避
- [x] **cli 代码复用** — cli.py 与 playwright_cli.py 有重复的目录创建 / 下载编排逻辑，可抽取公共函数

"""Interactive Terminal User Interface (TUI) for XScrape."""

import asyncio
import os
import sys
from pathlib import Path
import json

import questionary
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

from .console import console, print_splash
from .config import load_config
from .clients import NoAPIClient, TwitterAPIClient
from .downloader import ImageDownloader
from .utils import ensure_dir, sanitize_filename

def run_interactive():
    """Run the interactive wizard."""
    print_splash()
    config = load_config()
    
    # 1. Select Mode
    mode_choices = [
        questionary.Choice("Nitter (免 API，推荐)", "nitter"),
        questionary.Choice("官方 API (稳定，需 Token)", "api"),
        questionary.Choice("Playwright (浏览器自动化，无需 Token)", "playwright")
    ]
    mode = questionary.select(
        "选择采集模式:",
        choices=mode_choices
    ).ask()
    
    if not mode:
        return

    # 2. Basic Info
    username = questionary.text(
        "🎯 目标用户名 (不含 @):",
        validate=lambda text: True if text.strip() else "用户名不能为空"
    ).ask()
    if not username:
        return
        
    username = username.strip()
    
    output_dir = questionary.text(
        "📂 输出目录:",
        default=config.get("defaults", {}).get("output_dir", "output")
    ).ask()
    if not output_dir: return
    
    workers = questionary.text(
        "⚡ 并发下载数:",
        default=str(config.get("defaults", {}).get("workers", 4)),
        validate=lambda text: True if text.isdigit() and int(text) > 0 else "请输入正整数"
    ).ask()
    if not workers: return
    workers = int(workers)

    # 3. Mode Specific Params
    params = {}
    if mode == "nitter":
        params["nitter_instance"] = questionary.text(
            "🌐 Nitter 实例:",
            default=config.get("defaults", {}).get("nitter_instance", "https://nitter.privacydev.net")
        ).ask()
        params["pages"] = questionary.text(
            "📄 抓取页数:",
            default="5",
            validate=lambda text: True if text.isdigit() and int(text) > 0 else "请输入正整数"
        ).ask()
        if not params["nitter_instance"] or not params["pages"]: return
        params["pages"] = int(params["pages"])
        
    elif mode == "api":
        bearer = config.get("auth", {}).get("bearer_token", "")
        params["bearer_token"] = questionary.password(
            "🔑 Bearer Token:",
            default=bearer
        ).ask()
        if not params["bearer_token"]: return
        
        params["count"] = questionary.text(
            "🔢 抓取推文数:",
            default="200",
            validate=lambda text: True if text.isdigit() and int(text) > 0 else "请输入正整数"
        ).ask()
        if not params["count"]: return
        params["count"] = int(params["count"])
        
    elif mode == "playwright":
        params["scrolls"] = questionary.text(
            "📜 滚动次数:",
            default=str(config.get("browser", {}).get("scrolls", 20)),
            validate=lambda text: True if text.isdigit() and int(text) > 0 else "请输入正整数"
        ).ask()
        if not params["scrolls"]: return
        params["scrolls"] = int(params["scrolls"])
        
        params["headless"] = questionary.confirm(
            "👻 是否使用无头模式 (不显示浏览器窗口)?",
            default=config.get("browser", {}).get("headless", True)
        ).ask()
        if params["headless"] is None: return

    # 4. Preview
    table = Table(title="任务预览", show_header=True, header_style="bold magenta")
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")
    
    table.add_row("目标用户", f"@{username}")
    table.add_row("采集模式", mode.upper())
    table.add_row("输出目录", output_dir)
    table.add_row("并发数", str(workers))
    for k, v in params.items():
        val_str = "********" if k == "bearer_token" else str(v)
        table.add_row(k, val_str)
        
    console.print(table)
    
    confirm = questionary.confirm("🚀 确认开始执行?", default=True).ask()
    if not confirm:
        console.print("[warning]任务已取消。[/warning]")
        return
        
    # 5. Execution
    try:
        execute_task(mode, username, output_dir, workers, params, config)
    except KeyboardInterrupt:
        console.print("\n[error]检测到 Ctrl+C，安全退出。[/error]")
        sys.exit(1)

def execute_task(mode, username, output_dir, workers, params, config):
    target_dir = Path(output_dir) / sanitize_filename(username)
    ensure_dir(str(target_dir))
    
    images = []
    pending_file = target_dir / "pending_downloads.json"
    
    if pending_file.exists():
        resume = questionary.confirm("检测到上次未完成的下载列表，是否跳过扫描直接继续下载?").ask()
        if resume:
            try:
                with open(pending_file, "r", encoding="utf-8") as f:
                    images = json.load(f)
                console.print(f"[info]已从 {pending_file.name} 加载 {len(images)} 个待下载文件。[/info]")
            except Exception:
                pass

    if not images:
        console.print(f"[info]正在获取 @{username} 的媒体数据...[/info]")
        
        if mode == "nitter":
            client = NoAPIClient(params["nitter_instance"], proxy=config.get("defaults", {}).get("proxy"))
            images = client.get_images_from_profile(username, pages=params["pages"])
        elif mode == "api":
            client = TwitterAPIClient(params["bearer_token"], proxy=config.get("defaults", {}).get("proxy"))
            user_id = client.get_user_id(username)
            
            remaining = params["count"]
            next_token = None
            while remaining > 0:
                data = client.get_user_tweets(user_id, min(remaining, 100), next_token)
                batch = client.extract_image_urls(data)
                images.extend(batch)
                next_token = data.get("meta", {}).get("next_token")
                remaining -= 100
                if not next_token:
                    break
        elif mode == "playwright":
            from .browser import scrape_with_playwright
            images = asyncio.run(
                scrape_with_playwright(
                    username,
                    max_scrolls=params["scrolls"],
                    headless=params["headless"],
                    proxy=config.get("defaults", {}).get("proxy")
                )
            )
        
    if not images:
        console.print("[warning]未找到任何图片或视频！[/warning]")
        return
        
    console.print(f"[success]成功找到 {len(images)} 个媒体文件。[/success]")
    
    metadata_file = target_dir / "metadata.json"
    metadata_file.write_text(json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8")
    
    downloader = ImageDownloader(str(target_dir), workers=workers, proxy=config.get("defaults", {}).get("proxy"))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]正在下载...", total=len(images))

        def update_progress(done, total, _stats):
            progress.update(task, completed=done, total=total)

        try:
            stats = downloader.download_all(images, on_progress=update_progress, show_progress=False)
        except KeyboardInterrupt:
            console.print("\n[error]检测到 Ctrl+C，正在停止下载并安全退出...[/error]")
            sys.exit(1)
    
    # 6. Result Report
    panel = Panel(
        f"[bold]任务完成汇总[/bold]\n"
        f"目标用户: @{username}\n"
        f"输出目录: {target_dir.resolve()}\n\n"
        f"✅ 成功下载: {stats['downloaded']}\n"
        f"⏭️  重复跳过: {stats['skipped']}\n"
        f"❌ 下载失败: {stats['failed']}",
        title="🎉 完成",
        border_style="green"
    )
    console.print(panel)
    
    action = questionary.select(
        "下一步操作:",
        choices=[
            questionary.Choice("打开输出目录", "open"),
            questionary.Choice("退出", "exit")
        ]
    ).ask()
    
    if action == "open":
        import platform
        import subprocess
        if platform.system() == "Windows":
            os.startfile(target_dir)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", target_dir])
        else:
            subprocess.Popen(["xdg-open", target_dir])

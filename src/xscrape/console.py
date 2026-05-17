"""Rich console singleton and styles."""

from rich.console import Console
from rich.theme import Theme

# Define a custom theme for our CLI
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "bold magenta",
})

console = Console(theme=custom_theme)

def print_splash():
    """Print the ASCII art splash screen."""
    splash = """
╔══════════════════════════════════════╗
║        XScrape — X 媒体采集工具       ║
║        三种模式 · 高速下载 · 去重      ║
╚══════════════════════════════════════╝
"""
    console.print(splash, style="bold blue")

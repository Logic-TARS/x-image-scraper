"""Configuration management via ~/.xscrape/config.toml."""

import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

CONFIG_DIR = Path.home() / ".xscrape"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "defaults": {
        "output_dir": "output",
        "workers": 4,
        "nitter_instance": "https://nitter.privacydev.net"
    },
    "auth": {
        "bearer_token": ""
    },
    "browser": {
        "headless": True,
        "scrolls": 20
    }
}

def load_config() -> dict:
    """Load configuration from ~/.xscrape/config.toml, returning defaults if not found."""
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, "rb") as f:
            user_config = tomllib.load(f)
            
        # Merge with defaults
        merged = DEFAULT_CONFIG.copy()
        for section, values in user_config.items():
            if section in merged and isinstance(merged[section], dict):
                merged[section].update(values)
            else:
                merged[section] = values
        return merged
    except Exception:
        return DEFAULT_CONFIG

def save_config(config_dict: dict) -> None:
    """Save configuration to ~/.xscrape/config.toml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # We can use a simple writer since we don't have complex structures
    lines = []
    for section, values in config_dict.items():
        lines.append(f"[{section}]")
        for k, v in values.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, int):
                lines.append(f"{k} = {v}")
            else:
                # Basic string escaping
                safe_v = str(v).replace('"', '\\"')
                lines.append(f'{k} = "{safe_v}"')
        lines.append("")
        
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

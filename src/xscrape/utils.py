"""Shared utility helpers."""

import hashlib
import re
from pathlib import Path


def ensure_dir(path: str) -> Path:
    """Create a directory if it does not exist."""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def file_hash(content: bytes) -> str:
    """Generate a content hash for duplicate detection."""
    return hashlib.md5(content).hexdigest()


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid on common file systems."""
    return re.sub(r'[\\/*?:"<>|]', "_", name)

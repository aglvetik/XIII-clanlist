from __future__ import annotations

from datetime import datetime


def format_local_timestamp() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def format_cache_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

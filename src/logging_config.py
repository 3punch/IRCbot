"""
پیکربندی سیستم لاگ‌گیری استاندارد.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """راه‌اندازی و بازگرداندن لاگر ریشه با قالب استاندارد."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # پاک‌سازی هندلرهای قبلی
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # آرام‌کردن لاگ‌های پر سر و صدای کتابخانه‌های خارجی
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

    return logging.getLogger("bot")

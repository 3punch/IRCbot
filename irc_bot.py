"""
نقطه ورود کلاینت IRC برای چت با مدل هوش مصنوعی در سرورهای IRC.
اجرا:
    python irc_bot.py
"""

import asyncio

from src.config import get_settings
from src.irc_client import IRCClient
from src.logging_config import setup_logging
from src.memory import MemoryManager


async def main_async() -> None:
    settings = get_settings()
    logger = setup_logging(settings.log_level)

    logger.info("=" * 60)
    logger.info("🚀 در حال راه‌اندازی کلاینت IRC برای چت با LLM...")
    logger.info("🔹 سرور: %s:%d", settings.irc_server, settings.irc_port)
    logger.info("🔹 کانال: %s", settings.irc_channel)
    logger.info("🔹 نام مستعار: %s", settings.irc_nickname)
    logger.info("=" * 60)

    memory = MemoryManager(
        state_dir=settings.state_dir,
        max_turns=settings.max_history_turns,
    )

    client = IRCClient(settings=settings, memory=memory)
    try:
        await client.connect_and_run()
    except KeyboardInterrupt:
        logger.info("در حال متوقف‌سازی کلاینت IRC...")
        await client.close()


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

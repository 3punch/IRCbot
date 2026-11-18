"""
نقطه ورود اصلی ربات تلگرام هوش مصنوعی با مدل محلی (Ollama).
اجرا:
    python bot.py
یا:
    make run
"""

import asyncio
import sys

from src.config import get_settings
from src.llm import check_ollama_health, get_available_models
from src.logging_config import setup_logging
from src.memory import MemoryManager
from src.telegram_bot import TelegramLLMBot


def main() -> None:
    settings = get_settings()
    logger = setup_logging(settings.log_level)

    logger.info("=" * 60)
    logger.info("🚀 در حال راه‌اندازی ربات تلگرام هوش مصنوعی...")
    logger.info("🔹 آدرس Ollama: %s", settings.ollama_host)
    logger.info("🔹 مدل پیش‌فرض: %s", settings.model_name)
    logger.info("🔹 سقف توکن‌ها: %d", settings.max_tokens)
    logger.info("🔹 پنجره کانتکست: %d", settings.num_ctx)
    logger.info("=" * 60)

    # بررسی توکن ربات تلگرام
    if not settings.telegram_bot_token:
        logger.error(
            "❌ توکن ربات تلگرام تنظیم نشده است!\n"
            "لطفاً فایل .env را ایجاد کرده و TELEGRAM_BOT_TOKEN را در آن قرار دهید.\n"
            "برای نمونه به .env.example مراجعه فرمایید."
        )
        sys.exit(1)

    # بررسی اولیه ارتباط با Ollama
    async def preflight_check():
        is_alive = await check_ollama_health(settings.ollama_host)
        if not is_alive:
            logger.warning(
                "⚠️ هشدار: سرویس اولاما در %s در دسترس نیست!\n"
                "ربات اجرا می‌شود، اما برای دریافت پاسخ باید `ollama serve` فعال باشد.",
                settings.ollama_host,
            )
        else:
            models = await get_available_models(settings.ollama_host)
            logger.info("✅ اتصال به Ollama برقرار است. مدل‌های یافت‌شده: %s", models)
            if settings.model_name not in models:
                logger.warning(
                    "⚠️ توجه: مدل '%s' در اولاما دانلود نشده است. می‌توانید با دستور `ollama pull %s` آن را دریافت کنید.",
                    settings.model_name,
                    settings.model_name,
                )

    try:
        asyncio.run(preflight_check())
    except Exception as exc:
        logger.warning("بررسی اولیه Ollama با خطا مواجه شد: %s", exc)

    # راه‌اندازی انبار حافظه
    memory = MemoryManager(
        state_dir=settings.state_dir,
        max_turns=settings.max_history_turns,
    )

    # ساخت و اجرای بات تلگرام
    bot_service = TelegramLLMBot(settings=settings, memory=memory)
    app = bot_service.build_application()

    logger.info("🟢 ربات تلگرام با موفقیت فعال شد و در حال دریافت پیام‌ها است...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

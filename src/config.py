"""
تنظیمات ربات و ماژول LLM با استفاده از Pydantic.
تمام متغیرها را می‌توان از طریق فایل .env یا متغیرهای محیطی سیستم تغییر داد.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """تنظیمات کلی برنامه."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        protected_namespaces=(),
    )

    # توکن ربات تلگرام
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")

    # آدرس سرویس Ollama
    ollama_host: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_HOST")

    # مدل پیش‌فرض Ollama
    model_name: str = Field(default="qwen2.5:14b", alias="MODEL_NAME")

    # پارامترهای تولید متن
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, alias="TEMPERATURE")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, alias="TOP_P")
    max_tokens: int = Field(default=2048, ge=64, le=32768, alias="MAX_TOKENS")
    num_ctx: int = Field(default=8192, ge=512, le=65536, alias="NUM_CTX")
    llm_timeout: int = Field(default=300, ge=10, le=1800, alias="LLM_TIMEOUT")
    ollama_keep_alive: str = Field(default="2h", alias="OLLAMA_KEEP_ALIVE")

    # حافظه گفتگو
    max_history_turns: int = Field(default=15, ge=1, le=100, alias="MAX_HISTORY_TURNS")

    # شخصیت و رفتار
    default_persona: str = Field(default="general", alias="DEFAULT_PERSONA")
    show_thinking: bool = Field(default=True, alias="SHOW_THINKING")

    # پوشه وضعیت‌ها
    state_dir: str = Field(default=".state", alias="STATE_DIR")

    # لاگ‌ها
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # مدت زمان اجرای ربات به دقیقه (صفر = بدون محدودیت، برای اجرای ۲۴ ساعته روی GitHub Actions)
    run_duration_minutes: float = Field(default=0.0, alias="RUN_DURATION_MINUTES")

    # تنظیمات کلاینت IRC
    irc_enabled: bool = Field(default=False, alias="IRC_ENABLED")
    irc_server: str = Field(default="irc.libera.chat", alias="IRC_SERVER")
    irc_port: int = Field(default=6667, alias="IRC_PORT")
    irc_channel: str = Field(default="#ai-chat", alias="IRC_CHANNEL")
    irc_nickname: str = Field(default="IRCAIBot", alias="IRC_NICKNAME")

    @field_validator("ollama_host")
    @classmethod
    def strip_slash(cls, v: str) -> str:
        return v.rstrip("/")


def get_settings() -> Settings:
    """دریافت تنظیمات معتبر شده."""
    return Settings()

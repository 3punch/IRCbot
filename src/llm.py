"""
کلاینت ارتباط با موتور هوش مصنوعی محلی Ollama.
پشتیبانی از مدل‌های پیشرفته (مانند Qwen 2.5، DeepSeek-R1 و Llama 3.3)،
تفکیک بخش تفکر استدلالی (<think>) و مدیریت خطاهای محلی.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

log = logging.getLogger("bot.llm")

# الگوی شناسایی بخش‌های تفکر در مدل‌های استدلالی مانند DeepSeek-R1
THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)


class LLMError(Exception):
    """خطای پایه ارتباط با مدل."""


class OllamaConnectionError(LLMError):
    """خطای عدم اتصال به سرویس Ollama."""


class OllamaModelNotFoundError(LLMError):
    """خطای موجود نبودن مدل در مخزن محلی Ollama."""


class OllamaTimeoutError(LLMError):
    """خطای پایان مهلت پاسخگویی مدل."""


def extract_thinking(raw_text: str) -> tuple[str | None, str]:
    """
    تفکیک بخش فکر کردن مدل (<think>...</think>) از پاسخ نهایی.
    خروجی: (متن تفکر یا None، پاسخ نهایی تمیز شده)
    """
    if not raw_text:
        return None, ""

    match = THINK_PATTERN.search(raw_text)
    if match:
        thinking = match.group(1).strip()
        answer = THINK_PATTERN.sub("", raw_text).strip()
        return (thinking if thinking else None), answer

    # بررسی تگ‌های باز بدون بسته شدن (در صورت قطع شدن توکن)
    if "<think>" in raw_text and "</think>" not in raw_text:
        parts = raw_text.split("<think>", 1)
        return parts[1].strip(), parts[0].strip()

    return None, raw_text.strip()


async def check_ollama_health(host: str, timeout: float = 5.0) -> bool:
    """بررسی وضعیت فعال بودن سرویس Ollama."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.get(f"{host}/api/tags")
            return res.status_code == 200
    except Exception:
        return False


async def get_available_models(host: str, timeout: float = 10.0) -> list[str]:
    """دریافت لیست نام مدل‌های دانلود شده در Ollama."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.get(f"{host}/api/tags")
            if res.status_code != 200:
                return []
            data = res.json()
            models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            return sorted(models)
    except Exception as exc:
        log.warning("خطا در دریافت لیست مدل‌های اولاما: %s", exc)
        return []


async def chat_generate_api(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    timeout: int = 60,
) -> tuple[str, str | None, dict[str, Any]]:
    """ارسال ناهمگام به APIهای پرسرعت ابری (مانند Groq یا OpenRouter برای سرعت زیر ثانیه)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    client_timeout = httpx.Timeout(connect=10.0, read=float(timeout), write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=client_timeout) as client:
        res = await client.post(url, json=payload, headers=headers)
        if res.status_code != 200:
            raise LLMError(f"خطا در فراخوانی API ابری (کد {res.status_code}): {res.text}")
        data = res.json()
        raw_content = data["choices"][0]["message"]["content"]
        thinking, final_answer = extract_thinking(raw_content)
        return final_answer, thinking, {"source": "api", "model": model}


async def chat_generate(
    host: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    top_p: float = 0.9,
    max_tokens: int = 2048,
    num_ctx: int = 8192,
    timeout: int = 300,
    keep_alive: str = "2h",
    api_key: str = "",
    api_base_url: str = "",
    api_model: str = "",
) -> tuple[str, str | None, dict[str, Any]]:
    """
    ارسال پیام‌ها به مدل و دریافت پاسخ به صورت ناهمگام (Async).
    در صورت تنظیم API_KEY، ابتدا از API فوق سریع استفاده می‌شود و در صورت خطا به اولاما منتقل می‌شود.
    """
    if api_key:
        try:
            target_api_model = api_model or "llama-3.3-70b-versatile"
            target_base_url = api_base_url or "https://api.groq.com/openai/v1"
            log.info("ارسال درخواست به API ابری پرسرعت (%s)...", target_api_model)
            return await chat_generate_api(
                base_url=target_base_url,
                api_key=api_key,
                model=target_api_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=min(timeout, 60),
            )
        except Exception as exc:
            log.warning("فراخوانی API ابری ناموفق بود (%s)؛ انتقال به Ollama محلی...", exc)

    url = f"{host}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
            "num_ctx": num_ctx,
            "repeat_penalty": 1.1,
        },
    }

    try:
        # تنظیم timeout برای خواندن پاسخ
        client_timeout = httpx.Timeout(
            connect=10.0,
            read=float(timeout),
            write=10.0,
            pool=10.0,
        )

        async with httpx.AsyncClient(timeout=client_timeout) as client:
            log.info("ارسال درخواست به مدل %s (تعداد پیام‌ها: %d)", model, len(messages))
            res = await client.post(url, json=payload)

            if res.status_code == 404:
                raise OllamaModelNotFoundError(
                    f"مدل '{model}' در اولاما یافت نشد. لطفاً دستور `ollama pull {model}` را اجرا کنید."
                )

            if res.status_code != 200:
                raise LLMError(f"پاسخ ناموفق از اولاما (کد {res.status_code}): {res.text}")

            result_data = res.json()
            message_obj = result_data.get("message", {})
            raw_content = message_obj.get("content", "")

            thinking, final_answer = extract_thinking(raw_content)

            stats = {
                "total_duration_ms": result_data.get("total_duration", 0) // 1_000_000,
                "prompt_eval_count": result_data.get("prompt_eval_count", 0),
                "eval_count": result_data.get("eval_count", 0),
            }

            return final_answer, thinking, stats

    except httpx.ConnectError as exc:
        log.error("اتصال به سرویس اولاما در %s برقرار نشد: %s", host, exc)
        raise OllamaConnectionError(
            f"عدم امکان اتصال به سرویس Ollama در آدرس {host}.\n"
            "لطفاً مطمئن شوید دستور `ollama serve` اجرا شده است."
        ) from exc

    except httpx.TimeoutException as exc:
        log.error("مهلت پاسخگویی مدل پس از %d ثانیه به پایان رسید.", timeout)
        raise OllamaTimeoutError(
            f"مدل پس از گذشت {timeout} ثانیه پاسخ نداد. ممکن است مدل برای منابع سخت‌افزاری سنگین باشد."
        ) from exc

    except LLMError:
        raise

    except Exception as exc:
        log.exception("خطای ناشناخته در ارتباط با اولاما: %s", exc)
        raise LLMError(f"خطا در پردازش مدل: {exc}") from exc

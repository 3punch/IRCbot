from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.llm import (
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    chat_generate,
    check_ollama_health,
    extract_thinking,
    get_available_models,
)


def test_extract_thinking_with_think_tags():
    raw = "<think>ابتدا باید مسئله را به اجزای کوچک‌تر تقسیم کنیم.</think>پاسخ نهایی مسئله ۲ است."
    thinking, answer = extract_thinking(raw)
    assert thinking == "ابتدا باید مسئله را به اجزای کوچک‌تر تقسیم کنیم."
    assert answer == "پاسخ نهایی مسئله ۲ است."


def test_extract_thinking_without_think_tags():
    raw = "این یک پاسخ بدون استدلال مجزاست."
    thinking, answer = extract_thinking(raw)
    assert thinking is None
    assert answer == "این یک پاسخ بدون استدلال مجزاست."


def test_extract_thinking_empty():
    thinking, answer = extract_thinking("")
    assert thinking is None
    assert answer == ""


@pytest.mark.asyncio
async def test_check_ollama_health_success():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200)
        is_healthy = await check_ollama_health("http://localhost:11434")
        assert is_healthy is True


@pytest.mark.asyncio
async def test_check_ollama_health_failure():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        is_healthy = await check_ollama_health("http://localhost:11434")
        assert is_healthy is False


@pytest.mark.asyncio
async def test_get_available_models():
    mock_payload = {
        "models": [
            {"name": "qwen2.5:14b", "size": 9000000},
            {"name": "deepseek-r1:8b", "size": 5000000},
        ]
    }
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_payload)
        models = await get_available_models("http://localhost:11434")
        assert models == ["deepseek-r1:8b", "qwen2.5:14b"]


@pytest.mark.asyncio
async def test_chat_generate_success():
    mock_response_data = {
        "message": {
            "role": "assistant",
            "content": "<think>در حال بررسی...</think>درود! چطور می‌توانم کمکتان کنم؟",
        },
        "total_duration": 1500000000,
        "prompt_eval_count": 10,
        "eval_count": 25,
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(200, json=mock_response_data)
        answer, thinking, stats = await chat_generate(
            host="http://localhost:11434",
            model="qwen2.5:14b",
            messages=[{"role": "user", "content": "سلام"}],
        )
        assert answer == "درود! چطور می‌توانم کمکتان کنم؟"
        assert thinking == "در حال بررسی..."
        assert stats["total_duration_ms"] == 1500
        assert stats["eval_count"] == 25


@pytest.mark.asyncio
async def test_chat_generate_model_not_found():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(404, text="model not found")
        with pytest.raises(OllamaModelNotFoundError):
            await chat_generate(
                host="http://localhost:11434",
                model="nonexistent-model",
                messages=[{"role": "user", "content": "سلام"}],
            )


@pytest.mark.asyncio
async def test_chat_generate_connection_error():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Failed to connect")
        with pytest.raises(OllamaConnectionError):
            await chat_generate(
                host="http://localhost:11434",
                model="qwen2.5:14b",
                messages=[{"role": "user", "content": "سلام"}],
            )


@pytest.mark.asyncio
async def test_chat_generate_timeout():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("Timeout")
        with pytest.raises(OllamaTimeoutError):
            await chat_generate(
                host="http://localhost:11434",
                model="qwen2.5:14b",
                messages=[{"role": "user", "content": "سلام"}],
                timeout=1,
            )

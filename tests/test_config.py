from src.config import Settings


def test_default_settings(monkeypatch):
    monkeypatch.delenv("NUM_CTX", raising=False)
    monkeypatch.delenv("MAX_TOKENS", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("TEMPERATURE", raising=False)
    monkeypatch.delenv("DEFAULT_PERSONA", raising=False)
    monkeypatch.delenv("MAX_HISTORY_TURNS", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    settings = Settings(_env_file=None)
    assert settings.ollama_host == "http://127.0.0.1:11434"
    assert settings.model_name == "qwen2.5:14b"
    assert settings.temperature == 0.4
    assert settings.max_tokens == 2048
    assert settings.num_ctx == 8192
    assert settings.max_history_turns == 15
    assert settings.default_persona == "general"
    assert settings.show_thinking is True


def test_settings_trailing_slash_strip(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    settings = Settings(ollama_host="http://localhost:11434/", _env_file=None)
    assert settings.ollama_host == "http://localhost:11434"


def test_settings_custom_values(monkeypatch):
    monkeypatch.delenv("NUM_CTX", raising=False)
    monkeypatch.delenv("MAX_TOKENS", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    settings = Settings(
        telegram_bot_token="test-token",
        model_name="deepseek-r1:8b",
        temperature=0.3,
        max_tokens=4096,
        max_history_turns=10,
        _env_file=None,
    )
    assert settings.telegram_bot_token == "test-token"
    assert settings.model_name == "deepseek-r1:8b"
    assert settings.temperature == 0.3
    assert settings.max_tokens == 4096
    assert settings.max_history_turns == 10

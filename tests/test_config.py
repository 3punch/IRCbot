from src.config import Settings


def test_default_settings():
    settings = Settings(_env_file=None)
    assert settings.ollama_host == "http://127.0.0.1:11434"
    assert settings.model_name == "qwen2.5:14b"
    assert settings.temperature == 0.7
    assert settings.max_tokens == 2048
    assert settings.num_ctx == 8192
    assert settings.max_history_turns == 15
    assert settings.default_persona == "general"
    assert settings.show_thinking is True


def test_settings_trailing_slash_strip():
    settings = Settings(ollama_host="http://localhost:11434/", _env_file=None)
    assert settings.ollama_host == "http://localhost:11434"


def test_settings_custom_values():
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

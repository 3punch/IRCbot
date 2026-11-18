import shutil
import tempfile

import pytest

from src.config import Settings
from src.memory import MemoryManager


@pytest.fixture
def temp_state_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_settings(temp_state_dir):
    return Settings(
        telegram_bot_token="123456:TEST_TOKEN",
        ollama_host="http://127.0.0.1:11434",
        model_name="qwen2.5:14b",
        temperature=0.7,
        top_p=0.9,
        max_tokens=1024,
        num_ctx=4096,
        max_history_turns=5,
        default_persona="general",
        state_dir=temp_state_dir,
        _env_file=None,
    )


@pytest.fixture
def memory_manager(temp_state_dir):
    return MemoryManager(state_dir=temp_state_dir, max_turns=5)

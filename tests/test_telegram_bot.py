from unittest.mock import AsyncMock, MagicMock

import pytest

from src.telegram_bot import TelegramLLMBot


def test_build_application(sample_settings, memory_manager):
    bot = TelegramLLMBot(settings=sample_settings, memory=memory_manager)
    app = bot.build_application()
    assert app is not None
    # Check that handlers were added
    handlers = app.handlers[0]
    assert len(handlers) >= 6


@pytest.mark.asyncio
async def test_cmd_reset(sample_settings, memory_manager):
    bot = TelegramLLMBot(settings=sample_settings, memory=memory_manager)
    chat_id = 9876
    memory_manager.add_user_message(chat_id, "سلام")
    assert memory_manager.get_stats(chat_id)["turns"] == 1

    update = MagicMock()
    update.effective_chat.id = chat_id
    mock_bot = AsyncMock()
    update.get_bot.return_value = mock_bot
    context = MagicMock()

    await bot.cmd_reset(update, context)

    # After reset, memory should have 0 turns
    assert memory_manager.get_stats(chat_id)["turns"] == 0
    mock_bot.send_message.assert_called_once()
    sent_text = mock_bot.send_message.call_args[1]["text"]
    assert "حافظه گفتگو با موفقیت پاک شد" in sent_text


@pytest.mark.asyncio
async def test_cmd_start(sample_settings, memory_manager):
    bot = TelegramLLMBot(settings=sample_settings, memory=memory_manager)
    chat_id = 1234
    update = MagicMock()
    update.effective_chat.id = chat_id
    mock_bot = AsyncMock()
    update.get_bot.return_value = mock_bot
    context = MagicMock()

    await bot.cmd_start(update, context)

    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args[1]
    assert "خوش آمدید" in call_kwargs["text"]
    assert call_kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_persona_custom(sample_settings, memory_manager):
    bot = TelegramLLMBot(settings=sample_settings, memory=memory_manager)
    chat_id = 1234
    update = MagicMock()
    update.effective_chat.id = chat_id
    mock_bot = AsyncMock()
    update.get_bot.return_value = mock_bot
    context = MagicMock()
    context.args = ["شما", "یک", "ربات", "طنزپرداز", "هستید"]

    await bot.cmd_persona(update, context)

    mock_bot.send_message.assert_called_once()
    session = memory_manager.get_or_create_session(chat_id)
    assert session.custom_system_prompt == "شما یک ربات طنزپرداز هستید"


@pytest.mark.asyncio
async def test_handle_callback_persona(sample_settings, memory_manager):
    bot = TelegramLLMBot(settings=sample_settings, memory=memory_manager)
    chat_id = 1234
    update = MagicMock()
    update.effective_chat.id = chat_id
    query = AsyncMock()
    query.data = "set_persona:coder"
    update.callback_query = query
    context = MagicMock()

    await bot.handle_callback(update, context)

    query.answer.assert_called_once()
    query.edit_message_text.assert_called_once()
    session = memory_manager.get_or_create_session(chat_id)
    assert session.persona_id == "coder"

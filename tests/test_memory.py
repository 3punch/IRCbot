from src.memory import MemoryManager


def test_memory_add_and_retrieve(memory_manager):
    chat_id = 12345
    memory_manager.add_user_message(chat_id, "سلام، چطوری؟")
    memory_manager.add_assistant_message(chat_id, "سلام! من عالی هستم، چه کمکی از دستم برمی‌آید؟")

    messages = memory_manager.get_messages_for_llm(chat_id)
    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "سلام، چطوری؟"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "سلام! من عالی هستم، چه کمکی از دستم برمی‌آید؟"


def test_memory_pruning(memory_manager):
    chat_id = 9999
    # max_turns is 5, meaning max 10 messages kept
    for i in range(12):
        memory_manager.add_user_message(chat_id, f"پرسش شماره {i}")
        memory_manager.add_assistant_message(chat_id, f"پاسخ شماره {i}")

    session = memory_manager.get_or_create_session(chat_id)
    assert len(session.messages) == 10
    assert session.messages[-1].content == "پاسخ شماره 11"
    assert session.messages[0].content == "پرسش شماره 7"


def test_memory_clear(memory_manager):
    chat_id = 5555
    memory_manager.add_user_message(chat_id, "پیام تست")
    memory_manager.clear(chat_id)

    messages = memory_manager.get_messages_for_llm(chat_id)
    # Only system message remains
    assert len(messages) == 1
    assert messages[0]["role"] == "system"


def test_memory_persona_and_custom_prompt(memory_manager):
    chat_id = 7777
    memory_manager.set_persona(chat_id, "coder")
    session = memory_manager.get_or_create_session(chat_id)
    assert session.persona_id == "coder"

    messages = memory_manager.get_messages_for_llm(chat_id)
    assert "مهندس" in messages[0]["content"] or "نرم‌افزار" in messages[0]["content"]

    # Setting custom prompt overrides persona system prompt
    memory_manager.set_custom_prompt(chat_id, "شما یک دستیار متخصص در لینوکس هستید.")
    messages = memory_manager.get_messages_for_llm(chat_id)
    assert messages[0]["content"] == "شما یک دستیار متخصص در لینوکس هستید."


def test_memory_model_override(memory_manager):
    chat_id = 8888
    assert memory_manager.get_model(chat_id, "default-model") == "default-model"

    memory_manager.set_model(chat_id, "deepseek-r1:14b")
    assert memory_manager.get_model(chat_id, "default-model") == "deepseek-r1:14b"

    memory_manager.set_model(chat_id, None)
    assert memory_manager.get_model(chat_id, "default-model") == "default-model"


def test_memory_persistence(temp_state_dir):
    manager1 = MemoryManager(state_dir=temp_state_dir, max_turns=5)
    chat_id = 4321
    manager1.add_user_message(chat_id, "یادت باشه عدد شانس من ۷ است")
    manager1.add_assistant_message(chat_id, "یادم ماند، ۷.")
    manager1.set_persona(chat_id, "creative")

    # Reload in a new manager instance
    manager2 = MemoryManager(state_dir=temp_state_dir, max_turns=5)
    session = manager2.get_or_create_session(chat_id)
    assert session.persona_id == "creative"
    assert len(session.messages) == 2
    assert session.messages[0].content == "یادت باشه عدد شانس من ۷ است"


def test_memory_stats(memory_manager):
    chat_id = 1111
    stats_empty = memory_manager.get_stats(chat_id)
    assert stats_empty["turns"] == 0

    memory_manager.add_user_message(chat_id, "سلام")
    memory_manager.add_assistant_message(chat_id, "درود")
    memory_manager.add_user_message(chat_id, "خوبی؟")

    stats = memory_manager.get_stats(chat_id)
    assert stats["turns"] == 2
    assert stats["messages_count"] == 3

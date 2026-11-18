from src.formatter import format_response_with_thinking, split_message


def test_split_message_short():
    text = "این یک پیام کوتاه است."
    chunks = split_message(text, max_size=100)
    assert chunks == [text]


def test_split_message_long_paragraphs():
    p1 = "الف" * 60
    p2 = "ب" * 60
    text = f"{p1}\n{p2}"

    chunks = split_message(text, max_size=80)
    assert len(chunks) == 2
    assert chunks[0] == p1
    assert chunks[1] == p2


def test_split_message_preserves_code_block():
    code_lines = ["line " + str(i) for i in range(20)]
    full_code = "```python\n" + "\n".join(code_lines) + "\n```"

    chunks = split_message(full_code, max_size=60)
    assert len(chunks) > 1

    # Chunk 0 starts with ```python and should be closed with ```
    assert chunks[0].startswith("```python")
    assert chunks[0].endswith("```")

    # Chunk 1 should re-open with ```python
    assert chunks[1].startswith("```python")


def test_format_response_with_thinking():
    answer = "پاسخ سوال شما ۴۲ است."
    thinking = "مدل در حال محاسبه پاسخ نهایی به کل جهان هستی بود."

    formatted = format_response_with_thinking(answer, thinking, show_thinking=True)
    assert "💭" in formatted
    assert "مدل در حال محاسبه" in formatted
    assert answer in formatted

    # When show_thinking is False
    without_thinking = format_response_with_thinking(answer, thinking, show_thinking=False)
    assert without_thinking == answer
    assert "💭" not in without_thinking

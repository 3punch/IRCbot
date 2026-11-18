"""
قالب‌بندی پیام‌ها، تقسیم پیام‌های طولانی بر اساس محدودیت تلگرام و حفظ بلوک‌های کد.
"""

from __future__ import annotations

# سقف ایمن کاراکترهای تلگرام (سقف تلگرام ۴۰۹۶ است، ما ۳۹۰۰ می‌گذاریم تا جا برای کاراکترهای اضافی باشد)
MAX_CHUNK_SIZE = 3900


def split_message(text: str, max_size: int = MAX_CHUNK_SIZE) -> list[str]:
    """
    تقسیم هوشمندانه متن‌های بلند به بخش‌های کوچک‌تر با رعایت بلوک‌های کد و پاراگراف‌ها.
    """
    if not text:
        return [""]

    if len(text) <= max_size:
        return [text]

    chunks: list[str] = []
    lines = text.split("\n")

    current_chunk: list[str] = []
    current_length = 0
    in_code_block = False
    current_code_lang = ""

    for line in lines:
        line_len = len(line) + 1  # احتساب \n

        # بررسی ورود یا خروج از بلوک کد
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                current_code_lang = stripped[3:].strip()
            else:
                in_code_block = False
                current_code_lang = ""

        # اگر افزودن این خط از حد مجاز فراتر می‌رود
        if current_length + line_len > max_size and current_chunk:
            # اگر داخل بلوک کد هستیم، بلوک کد را در انتهای این بخش می‌بندیم
            if in_code_block:
                current_chunk.append("```")

            chunk_str = "\n".join(current_chunk)
            chunks.append(chunk_str)

            # آغاز بخش جدید
            current_chunk = []
            current_length = 0

            # اگر داخل بلوک کد بودیم، در بخش بعدی دوباره آن را باز می‌کنیم
            if in_code_block:
                fence = f"```{current_code_lang}" if current_code_lang else "```"
                current_chunk.append(fence)
                current_length += len(fence) + 1

        current_chunk.append(line)
        current_length += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def format_response_with_thinking(
    answer: str,
    thinking: str | None = None,
    show_thinking: bool = True,
) -> str:
    """
    ترکیب بخش استدلال و پاسخ نهایی برای نمایش به کاربر.
    """
    if not thinking or not show_thinking:
        return answer

    # فرمت‌بندی تفکر به صورت نقل‌قول یا بلوک مشخص
    formatted_thinking = (
        "💭 **فرآیند تحلیل و استدلال مدل:**\n> " + "\n> ".join(thinking.split("\n")) + "\n\n"
    )

    return f"{formatted_thinking}{answer}"

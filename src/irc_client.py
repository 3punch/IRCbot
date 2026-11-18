"""
کلاینت ناهمگام (Async) برای پروتکل استاندارد IRC (Internet Relay Chat).
اتصال مستقیم با کتابخانه استاندارد پایتون (asyncio) بدون نیاز به وابستگی‌های خارجی.
"""

from __future__ import annotations

import asyncio
import logging

from src.config import Settings
from src.llm import chat_generate
from src.memory import MemoryManager

log = logging.getLogger("bot.irc")


class IRCClient:
    """کلاینت IRC برای پاسخگویی به چت‌ها با استفاده از موتور LLM."""

    def __init__(self, settings: Settings, memory: MemoryManager):
        self.settings = settings
        self.memory = memory
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._running = False

    async def connect_and_run(self) -> None:
        """اتصال به سرور IRC، ورود به کانال و شنود پیام‌ها."""
        server = self.settings.irc_server
        port = self.settings.irc_port
        nick = self.settings.irc_nickname
        channel = self.settings.irc_channel

        log.info("در حال اتصال به سرور IRC در %s:%d ...", server, port)
        try:
            self.reader, self.writer = await asyncio.open_connection(server, port)
        except Exception as exc:
            log.error("خطا در برقراری اتصال با سرور IRC: %s", exc)
            return

        self._running = True
        # ثبت هویت در IRC
        await self._send(f"NICK {nick}")
        await self._send(f"USER {nick} 0 * :{nick} AI Assistant")

        # ورود به کانال
        await self._send(f"JOIN {channel}")
        log.info("با موفقیت به کانال %s ملحق شدیم.", channel)

        buffer = ""
        while self._running:
            try:
                data = await self.reader.read(2048)
                if not data:
                    log.warning("اتصال IRC قطع شد.")
                    break

                buffer += data.decode("utf-8", errors="replace")
                lines = buffer.split("\r\n")
                buffer = lines.pop()

                for line in lines:
                    await self._handle_line(line)

            except Exception as exc:
                log.error("خطا در حلقه پیام‌های IRC: %s", exc)
                break

        await self.close()

    async def _send(self, message: str) -> None:
        if self.writer:
            self.writer.write(f"{message}\r\n".encode())
            await self.writer.drain()

    async def send_privmsg(self, target: str, message: str) -> None:
        """ارسال پیام به کانال یا کاربر در IRC با محدودیت طول خط."""
        for line in message.split("\n"):
            line = line.strip()
            if not line:
                continue
            # تقسیم خط‌های بسیار طولانی به ۴۰۰ کاراکتر
            for i in range(0, len(line), 400):
                await self._send(f"PRIVMSG {target} :{line[i : i + 400]}")
                await asyncio.sleep(0.5)

    async def _handle_line(self, line: str) -> None:
        if not line:
            return

        # پاسخ به PING سرور IRC
        if line.startswith("PING"):
            server_token = line.split(" ", 1)[1]
            await self._send(f"PONG {server_token}")
            return

        parts = line.split(" ")
        if len(parts) >= 4 and parts[1] == "PRIVMSG":
            sender = parts[0].split("!")[0].lstrip(":")
            target = parts[2]
            msg_text = " ".join(parts[3:])[1:].strip()

            nick = self.settings.irc_nickname
            is_pm = target == nick
            is_mentioned = msg_text.startswith(nick)

            if is_pm or is_mentioned:
                clean_query = msg_text
                if is_mentioned:
                    clean_query = msg_text[len(nick) :].lstrip(": ,").strip()

                reply_target = sender if is_pm else target
                # استفاده از هش نام کاربر به عنوان شناسه چت
                chat_id = hash(f"irc_{sender}")

                # مدیریت دستور ریست
                if clean_query.lower() in ("!new", "!reset", "!clear"):
                    self.memory.clear(chat_id)
                    await self.send_privmsg(reply_target, f"{sender}: حافظه مکالمه پاک شد.")
                    return

                # ذخیره و دریافت پاسخ LLM
                self.memory.add_user_message(chat_id, clean_query)
                messages = self.memory.get_messages_for_llm(chat_id)

                try:
                    answer, _, _ = await chat_generate(
                        host=self.settings.ollama_host,
                        model=self.settings.model_name,
                        messages=messages,
                        temperature=self.settings.temperature,
                        max_tokens=self.settings.max_tokens,
                        num_ctx=self.settings.num_ctx,
                        timeout=self.settings.llm_timeout,
                    )
                    self.memory.add_assistant_message(chat_id, answer)
                    await self.send_privmsg(reply_target, f"{sender}: {answer}")
                except Exception as exc:
                    await self.send_privmsg(reply_target, f"{sender}: خطا در مدل - {exc}")

    async def close(self) -> None:
        self._running = False
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass

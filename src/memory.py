"""
مدیریت حافظه تاریخچه گفتگوها (Multi-turn Context Memory).
هر کاربر/چت تاریخچه مستقل خود را دارد و با رسیدن به سقف، پیام‌های قدیمی آرشیو می‌شوند.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.personas import get_persona

log = logging.getLogger("bot.memory")


@dataclass
class ChatMessage:
    role: str  # "system", "user", "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ChatSession:
    chat_id: int
    persona_id: str = "general"
    custom_system_prompt: str | None = None
    model_override: str | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MemoryManager:
    """مدیریت تاریخچه‌های چت با قابلیت ذخیره‌سازی محلی و بازیابی."""

    def __init__(self, state_dir: str = ".state", max_turns: int = 15):
        self.state_dir = Path(state_dir)
        self.file_path = self.state_dir / "chat_memory.json"
        self.max_turns = max_turns
        self._lock = threading.Lock()
        self._sessions: dict[int, ChatSession] = {}
        self._load()

    def _load(self) -> None:
        """بارگذاری تاریخچه‌ها از دیسک."""
        if not self.file_path.exists():
            return
        try:
            with open(self.file_path, encoding="utf-8") as f:
                raw_data = json.load(f)
            for chat_id_str, sess_data in raw_data.items():
                chat_id = int(chat_id_str)
                msgs = [
                    ChatMessage(
                        role=m.get("role", "user"),
                        content=m.get("content", ""),
                        timestamp=m.get("timestamp", ""),
                    )
                    for m in sess_data.get("messages", [])
                ]
                self._sessions[chat_id] = ChatSession(
                    chat_id=chat_id,
                    persona_id=sess_data.get("persona_id", "general"),
                    custom_system_prompt=sess_data.get("custom_system_prompt"),
                    model_override=sess_data.get("model_override"),
                    messages=msgs,
                    created_at=sess_data.get("created_at", ""),
                    updated_at=sess_data.get("updated_at", ""),
                )
            log.info("تعداد %d جلسه چت از دیسک بازیابی شد.", len(self._sessions))
        except Exception as exc:
            log.warning("بارگذاری حافظه گفتگوها با خطا مواجه شد: %s", exc)

    def _save(self) -> None:
        """ذخیره‌سازی تاریخچه‌ها روی دیسک به صورت امن."""
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            export_data = {}
            for chat_id, sess in self._sessions.items():
                export_data[str(chat_id)] = {
                    "chat_id": sess.chat_id,
                    "persona_id": sess.persona_id,
                    "custom_system_prompt": sess.custom_system_prompt,
                    "model_override": sess.model_override,
                    "created_at": sess.created_at,
                    "updated_at": sess.updated_at,
                    "messages": [
                        {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                        for m in sess.messages[-(self.max_turns * 2) :]
                    ],
                }
            temp_file = self.file_path.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            temp_file.replace(self.file_path)
        except Exception as exc:
            log.warning("ذخیره حافظه روی دیسک با خطا مواجه شد: %s", exc)

    def get_or_create_session(self, chat_id: int) -> ChatSession:
        with self._lock:
            if chat_id not in self._sessions:
                self._sessions[chat_id] = ChatSession(chat_id=chat_id)
            return self._sessions[chat_id]

    def add_user_message(self, chat_id: int, content: str) -> None:
        with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession(chat_id=chat_id))
            session.messages.append(ChatMessage(role="user", content=content))
            session.updated_at = datetime.utcnow().isoformat()
            self._prune(session)
            self._save()

    def add_assistant_message(self, chat_id: int, content: str) -> None:
        with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession(chat_id=chat_id))
            session.messages.append(ChatMessage(role="assistant", content=content))
            session.updated_at = datetime.utcnow().isoformat()
            self._prune(session)
            self._save()

    def _prune(self, session: ChatSession) -> None:
        """محدود کردن سابقه گفتگو به سقف تعیین شده (پنجره لغزان)."""
        max_msgs = self.max_turns * 2
        if len(session.messages) > max_msgs:
            session.messages = session.messages[-max_msgs:]

    def clear(self, chat_id: int) -> None:
        """پاک‌کردن تاریخچه پیام‌های یک چت (آغاز موضوع جدید)."""
        with self._lock:
            if chat_id in self._sessions:
                self._sessions[chat_id].messages.clear()
                self._sessions[chat_id].updated_at = datetime.utcnow().isoformat()
                self._save()

    def set_persona(self, chat_id: int, persona_id: str) -> None:
        with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession(chat_id=chat_id))
            session.persona_id = persona_id
            session.custom_system_prompt = None
            session.updated_at = datetime.utcnow().isoformat()
            self._save()

    def set_custom_prompt(self, chat_id: int, prompt: str) -> None:
        with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession(chat_id=chat_id))
            session.custom_system_prompt = prompt
            session.updated_at = datetime.utcnow().isoformat()
            self._save()

    def set_model(self, chat_id: int, model_name: str | None) -> None:
        with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession(chat_id=chat_id))
            session.model_override = model_name
            session.updated_at = datetime.utcnow().isoformat()
            self._save()

    def get_model(self, chat_id: int, default_model: str) -> str:
        with self._lock:
            session = self._sessions.get(chat_id)
            if session and session.model_override:
                return session.model_override
            return default_model

    def get_messages_for_llm(self, chat_id: int) -> list[dict]:
        """آماده‌سازی آرایه پیام‌ها برای ارسال به Ollama (شامل پرامپت سیستم و سوابق)."""
        with self._lock:
            session = self._sessions.setdefault(chat_id, ChatSession(chat_id=chat_id))

            if session.custom_system_prompt:
                system_text = session.custom_system_prompt
            else:
                persona = get_persona(session.persona_id)
                system_text = persona.system_prompt

            formatted: list[dict] = [{"role": "system", "content": system_text}]

            for msg in session.messages:
                formatted.append({"role": msg.role, "content": msg.content})

            return formatted

    def get_stats(self, chat_id: int) -> dict:
        """دریافت وضعیت و آمار گفتگوی فعلی کاربر."""
        with self._lock:
            session = self._sessions.get(chat_id)
            if not session:
                return {
                    "turns": 0,
                    "messages_count": 0,
                    "persona_id": "general",
                    "model_override": None,
                    "has_custom_prompt": False,
                }
            user_msgs = sum(1 for m in session.messages if m.role == "user")
            return {
                "turns": user_msgs,
                "messages_count": len(session.messages),
                "persona_id": session.persona_id,
                "model_override": session.model_override,
                "has_custom_prompt": bool(session.custom_system_prompt),
            }

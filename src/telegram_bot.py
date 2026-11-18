"""
پیاده‌سازی ربات تلگرام با کتابخانه python-telegram-bot (نسخه ۲۱+ Async).
"""

from __future__ import annotations

import asyncio
import logging
import re

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    constants,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import Settings
from src.formatter import format_response_with_thinking, split_message
from src.llm import (
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    chat_generate,
    check_ollama_health,
    get_available_models,
)
from src.memory import MemoryManager
from src.personas import get_persona, list_personas

log = logging.getLogger("bot.telegram")


class TelegramLLMBot:
    def __init__(self, settings: Settings, memory: MemoryManager):
        self.settings = settings
        self.memory = memory
        self.app: Application | None = None

    async def _auto_stop(self, app: Application, minutes: float) -> None:
        """خاموش‌سازی تمیز ربات پس از مدت مشخص (برای چرخش بین Jobهای GitHub Actions)."""
        await asyncio.sleep(minutes * 60)
        log.info("زمان اجرای برنامه‌ریزی‌شده (%.0f دقیقه) به پایان رسید؛ خاموش‌سازی تمیز...", minutes)
        if app.updater and app.updater.running:
            await app.updater.stop()
        await app.stop()

    async def _post_init(self, app: Application) -> None:
        """تنظیم کارهای اولیه پس از ساخت اپلیکیشن و راه‌اندازی Event Loop."""
        # بررسی اتصال اولیه به Ollama
        try:
            is_alive = await check_ollama_health(self.settings.ollama_host)
            if not is_alive:
                log.warning(
                    "⚠️ هشدار: سرویس اولاما در %s در دسترس نیست! "
                    "ربات اجرا می‌شود، اما برای دریافت پاسخ باید سرویس Ollama در حال اجرا باشد.",
                    self.settings.ollama_host,
                )
            else:
                models = await get_available_models(self.settings.ollama_host)
                log.info("✅ اتصال به Ollama برقرار است. مدل‌های یافت‌شده: %s", models)
                if self.settings.model_name not in models:
                    log.warning(
                        "⚠️ توجه: مدل '%s' در اولاما دانلود نشده است. "
                        "می‌توانید با دستور `ollama pull %s` آن را دریافت کنید.",
                        self.settings.model_name,
                        self.settings.model_name,
                    )
        except Exception as exc:
            log.warning("بررسی اولیه Ollama با خطا مواجه شد: %s", exc)

        if self.settings.run_duration_minutes > 0:
            app.create_task(self._auto_stop(app, self.settings.run_duration_minutes))
            log.info(
                "ربات برای مدت %.0f دقیقه اجرا می‌شود و سپس جایش را به نوبت بعدی Actions می‌دهد.",
                self.settings.run_duration_minutes,
            )

    def build_application(self) -> Application:
        """ساخت و پیکربندی اپلیکیشن ربات تلگرام."""
        app = (
            ApplicationBuilder()
            .token(self.settings.telegram_bot_token)
            .post_init(self._post_init)
            .build()
        )

        # ثبت دستورات
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler(["new", "clear", "reset"], self.cmd_reset))
        app.add_handler(CommandHandler("model", self.cmd_model))
        app.add_handler(CommandHandler("persona", self.cmd_persona))
        app.add_handler(CommandHandler(["history", "stats"], self.cmd_history))

        # ثبت رویداد دکمه‌های شیشه‌ای
        app.add_handler(CallbackQueryHandler(self.handle_callback))

        # ثبت دریافت پیام متنی
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))

        self.app = app
        return app

    # ---------------------------------------------------------------- دستورات

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """پیام خوش‌آمدگویی و معرفی امکانات ربات."""
        chat_id = update.effective_chat.id
        active_model = self.memory.get_model(chat_id, self.settings.model_name)
        active_persona = get_persona(self.memory.get_or_create_session(chat_id).persona_id)

        keyboard = [
            [
                InlineKeyboardButton("💬 گفتگوی جدید", callback_data="btn_new_chat"),
                InlineKeyboardButton("🎭 انتخاب شخصیت", callback_data="btn_personas"),
            ],
            [
                InlineKeyboardButton("🧠 مدل‌های موجود", callback_data="btn_models"),
                InlineKeyboardButton("📊 وضعیت حافظه", callback_data="btn_stats"),
            ],
            [
                InlineKeyboardButton("📖 راهنمای دستورات", callback_data="btn_help"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "👋 **درود! به دستیار هوشمند و همه‌منظوره محلی خوش آمدید.**\n\n"
            "این ربات مستقیماً به مدل‌های زبانی پیشرفته محلی (Ollama) متصل است و هیچ محدودیتی در موضوع گفتگو ندارد.\n\n"
            f"🔹 **مدل فعال فعلی:** `{active_model}`\n"
            f"🔹 **شخصیت فعال:** {active_persona.icon} {active_persona.name}\n\n"
            "✨ **قابلیت‌ها:**\n"
            "• حافظه مکالمه و پاسخ‌دهی پیوسته به گفتگوها\n"
            "• پاسخ به سوالات علمی، برنامه‌نویسی، نگارش، تحلیل و ترجمه\n"
            "• پشتیبانی از مدل‌های استدلالی (مانند DeepSeek-R1 و Qwen 2.5)\n"
            "• تغییر سریع شخصیت یا مدل با دکمه‌های شیشه‌ای\n\n"
            "💬 برای شروع، کافی است پرسش یا درخواست خود را در قالب یک پیام ارسال کنید."
        )

        await self._send_safe_message(update, text, reply_markup=reply_markup)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """راهنمای کامل دستورات."""
        text = (
            "📚 **راهنمای استفاده از ربات هوش مصنوعی:**\n\n"
            "• `/new` یا `/clear` یا `/reset` : پاک‌سازی تاریخچه گفتگو و آغاز موضوع جدید\n"
            "• `/model` : مشاهده یا تغییر مدل زبانی فعال\n"
            "• `/persona` : تغییر سبک پاسخگویی (برنامه‌نویس، علمی، ادبی، و...)\n"
            "• `/history` : مشاهده تعداد پیام‌ها و آمار گفتگوی فعلی\n"
            "• `/help` : نمایش همین راهنما\n\n"
            "💡 **نکات کاربردی:**\n"
            "۱. ربات دارای حافظه است؛ یعنی می‌توانید به پیام‌های قبلی ارجاع دهید (مثال: «کد بالا را به پایتون بازنویسی کن»).\n"
            "۲. هر زمان که موضوع صحبت عوض شد، برای عملکرد بهتر از دستور `/new` استفاده کنید.\n"
            "۳. تمام کدهای برنامه‌نویسی در قالب بلوک‌های خوانا با قابلیت کپی آسان ارسال می‌شوند."
        )
        await self._send_safe_message(update, text)

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """پاک کردن حافظه گفتگو."""
        chat_id = update.effective_chat.id
        self.memory.clear(chat_id)
        text = "🧹 **حافظه گفتگو با موفقیت پاک شد.**\nآماده‌ام برای گفتگوی جدید در هر موضوعی که بخواهید!"
        await self._send_safe_message(update, text)

    async def cmd_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """نمایش و تغییر مدل فعال."""
        chat_id = update.effective_chat.id
        current_model = self.memory.get_model(chat_id, self.settings.model_name)

        available_models = await get_available_models(self.settings.ollama_host)

        buttons = []
        if available_models:
            for m in available_models:
                mark = " ✅" if m == current_model else ""
                buttons.append([InlineKeyboardButton(f"{m}{mark}", callback_data=f"set_model:{m}")])
        else:
            buttons.append(
                [InlineKeyboardButton("⚠️ مدلی در اولاما یافت نشد", callback_data="none")]
            )

        if current_model != self.settings.model_name:
            buttons.append(
                [
                    InlineKeyboardButton(
                        "🔄 بازگشت به پیش‌فرض سیستم", callback_data="reset_model_default"
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(buttons)
        text = (
            f"🧠 **تنظیمات مدل زبانی (LLM):**\n\n"
            f"• **مدل فعال فعلی شما:** `{current_model}`\n"
            f"• **مدل پیش‌فرض سرور:** `{self.settings.model_name}`\n"
            f"• **آدرس اولاما:** `{self.settings.ollama_host}`\n\n"
            "برای تغییر مدل، یکی از گزینه‌های دانلود شده زیر را انتخاب کنید:"
        )
        await self._send_safe_message(update, text, reply_markup=reply_markup)

    async def cmd_persona(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """انتخاب شخصیت و سبک پاسخگویی."""
        chat_id = update.effective_chat.id

        # بررسی آرگومان‌های سفارشی: مثلاً /persona custom متن دلخواه
        if context.args and len(context.args) > 0:
            custom_text = " ".join(context.args)
            self.memory.set_custom_prompt(chat_id, custom_text)
            await self._send_safe_message(
                update, f"✅ **پرامپت سیستمی سفارشی شما ثبت شد:**\n\n_{custom_text}_"
            )
            return

        session = self.memory.get_or_create_session(chat_id)
        current_pid = session.persona_id

        buttons = []
        for p in list_personas():
            is_current = p.id == current_pid and not session.custom_system_prompt
            label = f"{p.icon} {p.name}" + (" ✅" if is_current else "")
            buttons.append([InlineKeyboardButton(label, callback_data=f"set_persona:{p.id}")])

        reply_markup = InlineKeyboardMarkup(buttons)
        text = (
            "🎭 **انتخاب سبک و شخصیت دستیار:**\n\n"
            "شما می‌توانید نحوه و زاویه دید پاسخگویی مدل را مطابق نیاز خود تنظیم کنید:\n\n"
        )
        for p in list_personas():
            text += f"• **{p.icon} {p.name}:** {p.description}\n"

        text += "\n💡 همچنین می‌توانید با ارسال دستور زیر پرامپت اختصاصی خود را اعمال کنید:\n`/persona متن پرامپت دلخواه شما`"

        await self._send_safe_message(update, text, reply_markup=reply_markup)

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """نمایش آمار حافظه چت."""
        chat_id = update.effective_chat.id
        stats = self.memory.get_stats(chat_id)
        current_model = self.memory.get_model(chat_id, self.settings.model_name)
        persona = get_persona(stats["persona_id"])

        text = (
            "📊 **وضعیت نشست گفتگوی جاری:**\n\n"
            f"• **تعداد نوبت‌های گفتگو:** {stats['turns']} از حداکثر {self.settings.max_history_turns}\n"
            f"• **کل پیام‌های نگه‌داری‌شده:** {stats['messages_count']}\n"
            f"• **مدل در حال استفاده:** `{current_model}`\n"
            f"• **شخصیت پاسخگویی:** {persona.icon} {persona.name}\n"
        )
        if stats["has_custom_prompt"]:
            text += "• **نوع پرامپت:** سفارشی کاربر ✍️\n"

        keyboard = [[InlineKeyboardButton("🧹 پاک‌سازی حافظه", callback_data="btn_new_chat")]]
        await self._send_safe_message(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------------------------------------------------------------- دکمه‌های شیشه‌ای

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return

        await query.answer()
        data = query.data or ""
        chat_id = update.effective_chat.id

        if data == "btn_new_chat":
            self.memory.clear(chat_id)
            await query.edit_message_text(
                "🧹 **حافظه گفتگو پاک شد.** آماده شروع یک موضوع تازه هستیم!"
            )
        elif data == "btn_personas":
            await self.cmd_persona(update, context)
        elif data == "btn_models":
            await self.cmd_model(update, context)
        elif data == "btn_stats":
            await self.cmd_history(update, context)
        elif data == "btn_help":
            await self.cmd_help(update, context)
        elif data.startswith("set_persona:"):
            pid = data.split(":", 1)[1]
            self.memory.set_persona(chat_id, pid)
            p = get_persona(pid)
            await query.edit_message_text(
                f"✅ **شخصیت با موفقیت تغییر کرد:**\n\n{p.icon} **{p.name}**\n_{p.description}_"
            )
        elif data.startswith("set_model:"):
            target_model = data.split(":", 1)[1]
            self.memory.set_model(chat_id, target_model)
            await query.edit_message_text(
                f"✅ **مدل زبانی این گفتگو تغییر کرد به:**\n`{target_model}`"
            )
        elif data == "reset_model_default":
            self.memory.set_model(chat_id, None)
            await query.edit_message_text(
                f"🔄 مدل به پیش‌فرض سیستم بازگردانده شد:\n`{self.settings.model_name}`"
            )

    # ---------------------------------------------------------------- دریافت پیام و ارسال به LLM

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        chat = update.effective_chat
        chat_id = chat.id
        raw_text = update.message.text.strip()
        if not raw_text:
            return

        is_group = chat.type in (constants.ChatType.GROUP, constants.ChatType.SUPERGROUP)
        bot_user = context.bot
        bot_username = bot_user.username or ""

        # در گروه‌ها: فقط زمانی پاسخ بده که ربات تگ (منشن) شده باشد یا به پیام ربات ریپلای شده باشد
        if is_group:
            is_reply_to_bot = (
                update.message.reply_to_message is not None
                and update.message.reply_to_message.from_user is not None
                and update.message.reply_to_message.from_user.id == bot_user.id
            )

            has_mention = False
            if bot_username:
                mention_pattern = rf"@{re.escape(bot_username)}\b"
                has_mention = bool(re.search(mention_pattern, raw_text, re.IGNORECASE))

            # همچنین بررسی entityهای منشن تلگرام
            if not has_mention and update.message.entities:
                for entity in update.message.entities:
                    if entity.type == constants.MessageEntityType.MENTION:
                        ent_text = raw_text[entity.offset : entity.offset + entity.length]
                        if bot_username and ent_text.lstrip("@").lower() == bot_username.lower():
                            has_mention = True
                            break

            # اگر نه تگ شده و نه ریپلای روی ربات است، پیام گروه را نادیده بگیر
            if not (has_mention or is_reply_to_bot):
                return

            # پاک‌سازی تگ ربات از متن سوال کاربر
            user_text = re.sub(
                rf"@{re.escape(bot_username)}\b", "", raw_text, flags=re.IGNORECASE
            ).strip()
            if not user_text:
                if is_reply_to_bot and update.message.reply_to_message.text:
                    user_text = "در مورد پیام بالا نظرت چیه؟"
                else:
                    await self._send_safe_message(
                        update,
                        "جونم؟ صدام زدی؟ 🤡 بگو در خدمتم!",
                        reply_to_message_id=update.message.message_id,
                    )
                    return
        else:
            user_text = raw_text

        # افزودن پیام کاربر به حافظه
        self.memory.add_user_message(chat_id, user_text)

        # دریافت سوابق گفتگو برای ارسال به Ollama
        messages = self.memory.get_messages_for_llm(chat_id)
        active_model = self.memory.get_model(chat_id, self.settings.model_name)

        # ارسال مداوم وضعیت "در حال تایپ" (typing action) تا زمان دریافت پاسخ
        stop_typing = asyncio.Event()

        async def send_typing_loop():
            while not stop_typing.is_set():
                try:
                    await context.bot.send_chat_action(
                        chat_id=chat_id,
                        action=ChatAction.TYPING,
                    )
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(stop_typing.wait(), timeout=4.0)
                except asyncio.TimeoutError:
                    pass

        typing_task = asyncio.create_task(send_typing_loop())

        try:
            answer, thinking, stats = await chat_generate(
                host=self.settings.ollama_host,
                model=active_model,
                messages=messages,
                temperature=self.settings.temperature,
                top_p=self.settings.top_p,
                max_tokens=self.settings.max_tokens,
                num_ctx=self.settings.num_ctx,
                timeout=self.settings.llm_timeout,
                keep_alive=self.settings.ollama_keep_alive,
                api_key=self.settings.api_key,
                api_base_url=self.settings.api_base_url,
                api_model=self.settings.api_model,
            )

            # ثبت پاسخ دستیار در حافظه
            self.memory.add_assistant_message(chat_id, answer)

            # قالب‌بندی نهایی
            full_reply = format_response_with_thinking(
                answer=answer,
                thinking=thinking,
                show_thinking=self.settings.show_thinking,
            )

            # ارسال پیام به کاربر (در گروه‌ها با ریپلای روی پیام کاربر)
            chunks = split_message(full_reply)
            reply_to_id = update.message.message_id if is_group else None
            for idx, chunk in enumerate(chunks):
                await self._send_safe_message(
                    update,
                    chunk,
                    reply_to_message_id=(reply_to_id if idx == 0 else None),
                )

        except OllamaConnectionError as exc:
            err_msg = (
                "⚠️ **خطای ارتباط با سرور هوش مصنوعی (Ollama)**\n\n"
                f"{exc}\n\n"
                "💡 **راهکار:** لطفاً بررسی کنید سرویس اولاما روشن باشد (`ollama serve`)."
            )
            await self._send_safe_message(update, err_msg)

        except OllamaModelNotFoundError as exc:
            err_msg = (
                "⚠️ **مدل انتخاب‌شده یافت نشد**\n\n"
                f"{exc}\n\n"
                f"💡 با دستور `/model` می‌توانید از میان مدل‌های نصب‌شده یکی را انتخاب کنید."
            )
            await self._send_safe_message(update, err_msg)

        except OllamaTimeoutError as exc:
            err_msg = (
                "⏳ **مهلت پاسخگویی مدل به پایان رسید**\n\n"
                f"{exc}\n\n"
                "💡 پیشنهاد می‌شود از مدل‌های سبک‌تر مثل `qwen2.5:7b` استفاده کنید یا مهلت را در تنظیمات افزایش دهید."
            )
            await self._send_safe_message(update, err_msg)

        except Exception as exc:
            log.exception("خطای پیش‌بینی‌نشده در پردازش پیام: %s", exc)
            err_msg = (
                "❌ **متأسفانه در پردازش پاسخ خطایی رخ داد.**\n\n"
                f"جزئیات: `{str(exc)}`\n"
                "لطفاً مجدداً تلاش کنید یا با دستور `/new` یک گفتگوی تازه آغاز نمایید."
            )
            await self._send_safe_message(update, err_msg)

        finally:
            stop_typing.set()
            await typing_task

    # ---------------------------------------------------------------- ابزارهای کمکی ارسال پیام

    async def _send_safe_message(
        self,
        update: Update,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        reply_to_message_id: int | None = None,
    ) -> None:
        """
        ارسال امن پیام با تلاش اولیه با فرمت Markdown و در صورت بروز خطا با متن ساده.
        این روش مانع از شکست ارسال به خاطر کاراکترهای خاص تلگرام می‌شود.
        """
        chat_id = update.effective_chat.id
        bot = update.get_bot()

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id,
                disable_web_page_preview=True,
            )
        except BadRequest as e:
            log.warning("ارسال با Markdown با شکست مواجه شد (%s)، تلاش با متن ساده...", e)
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=None,
                    reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id,
                    disable_web_page_preview=True,
                )
            except Exception as final_e:
                log.error("ارسال پیام به چت %s ناموفق بود: %s", chat_id, final_e)
        except Exception as exc:
            log.error("خطا در ارسال پیام: %s", exc)

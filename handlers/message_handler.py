from aiogram import types, Router
from io import BytesIO
import logging
from datetime import datetime, timedelta

from html import escape
from config import bot
from schemas.media_schemas import MediaType
from storage import (
    pending_callbacks,
    admin_context,
    clear_admin_context,
    clear_pending_file,
)
from services.github_service import GitHubService

logger = logging.getLogger(__name__)
router = Router()

github_service = GitHubService()


@router.message()
async def handle_admin_message(message: types.Message):
    """
    Обработка сообщений от админа - ЭТАП 2

    Проверяет, ждём ли мы названия файла.
    Если да - загружает файл с указанным названием на GitHub.
    """
    try:
        admin_id = message.from_user.id

        # ✅ Проверяем, есть ли контекст для этого админа
        if admin_id not in admin_context:
            logger.info(f"⚠️ Нет контекста для админа {admin_id}, игнорируем сообщение")
            return

        context = admin_context[admin_id]
        short_id = context.get("last_approved_short_id")
        waiting_since = context.get("waiting_since")

        if not short_id:
            logger.warning(f"⚠️ short_id не найден в контексте админа")
            return

        # ✅ Проверяем timeout (если прошло более 10 минут - отменяем)
        if waiting_since and datetime.now() - waiting_since > timedelta(minutes=10):
            logger.warning(f"⏱️ Timeout: админ не ввел название вовремя")
            await message.reply(
                "❌ Время ожидания истекло. Пожалуйста, одобрите файл снова.",
                parse_mode="HTML",
            )
            clear_admin_context(admin_id)
            return

        # ✅ Получаем файл из кэша
        pending_file = pending_callbacks.get(short_id)

        if not pending_file:
            logger.error(f"❌ Файл не найден для short_id: {short_id}")
            await message.reply("❌ Ошибка: файл не найден в системе")
            clear_admin_context(admin_id)
            return

        if not pending_file.waiting_for_name:
            logger.info(f"⚠️ Файл уже обработан или не ждёт названия")
            return

        # ✅ Получаем введённое название
        new_filename = message.text.strip()

        # ✅ Валидируем название
        if not new_filename or len(new_filename) < 2:
            await message.reply(
                "❌ Название слишком короткое. Минимум 2 символа.", parse_mode="HTML"
            )
            return

        if len(new_filename) > 255:
            await message.reply(
                "❌ Название слишком длинное. Максимум 255 символов.", parse_mode="HTML"
            )
            return

        # ✅ Проверяем недопустимые символы
        forbidden_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        if any(char in new_filename for char in forbidden_chars):
            forbidden_str = ", ".join(forbidden_chars)
            escaped_forbidden_str = escape(forbidden_str)
            await message.reply(
                f"❌ Название содержит недопустимые символы: {escaped_forbidden_str}\n\n"
                f"✅ Разрешены: буквы, цифры, пробелы, дефисы, точки, скобки",
                parse_mode="HTML",
            )
            return

        logger.info(f"📝 Введённое название: '{new_filename}'")

        # ✅ Отправляем уведомление о начале загрузки
        processing_msg = await message.reply(
            "⏳ Загружаю файл с новым названием на GitHub...", parse_mode="HTML"
        )

        try:
            # ✅ Скачиваем файл из Telegram
            logger.info(f"📥 Скачиваю файл из Telegram: {pending_file.file_id}")
            file_info = await bot.get_file(pending_file.file_id)
            file_bytes = await bot.download_file(file_info.file_path)
            file_data = BytesIO(file_bytes.read())
            logger.info(f"✅ Файл скачан: {file_info.file_size} bytes")

            # ✅ Определяем окончательное имя файла
            # Если имя содержит точку, используем как есть
            # Если нет - добавляем расширение на основе исходного файла
            if "." not in new_filename:
                original_ext = pending_file.original_filename.split(".")[-1].lower()
                final_filename = f"{new_filename}.{original_ext}"
            else:
                final_filename = new_filename

            logger.info(f"📤 Загружаю в GitHub с именем: {final_filename}")

            # ✅ Определяем тип медиа
            media_type = (
                MediaType.PHOTO
                if pending_file.media_type == "PHOTO"
                else MediaType.DOCUMENT
            )

            # ✅ Загружаем в GitHub
            storage_url = await github_service.upload_file_to_github(
                file_data, final_filename, media_type
            )

            logger.info(f"✅ Файл успешно загружен: {storage_url}")

            # ✅ Отправляем успешное уведомление
            media_emoji = "📷" if media_type == MediaType.PHOTO else "📄"
            escaped_filename = escape(final_filename)
            escaped_url = escape(storage_url)

            success_text = (
                f"✅ <b>{media_emoji} Файл успешно загружен!</b>\n\n"
                f"📝 <b>Имя:</b> <code>{escaped_filename}</code>\n"
                f"🔗 <b>URL:</b>\n<code>{escaped_url}</code>"
            )

            await bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text=success_text,
                parse_mode="HTML",
            )

            # ✅ Очищаем кэш
            clear_pending_file(short_id)
            clear_admin_context(admin_id)

        except Exception as upload_error:
            logger.error(f"❌ Ошибка при загрузке файла: {upload_error}", exc_info=True)

            escaped_error = escape(str(upload_error)[:200])

            error_text = (
                f"❌ <b>Ошибка при загрузке:</b>\n"
                f"<code>{escaped_error}</code>\n\n"
                f"Попробуйте ещё раз или отклоните файл."
            )

            await bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text=error_text,
                parse_mode="HTML",
            )

            # Очищаем контекст при ошибке
            clear_admin_context(admin_id)

    except Exception as e:
        logger.error(f"❌ ОШИБКА В HANDLE_ADMIN_MESSAGE: {e}", exc_info=True)
        try:
            escaped_error = escape(str(e)[:100])
            await message.reply(
                f"❌ Произошла ошибка при обработке сообщения: {escaped_error}",
                parse_mode="HTML",
            )
        except Exception as reply_error:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {reply_error}")

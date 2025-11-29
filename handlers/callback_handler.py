from aiogram import types, Router, F
from datetime import datetime
import logging
from html import escape

from config import bot
from storage import pending_callbacks, admin_context, PendingFile, clear_admin_context

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("approve_"))
async def handle_approve(query: types.CallbackQuery):
    """
    Обработка одобрения файла - ЭТАП 1

    Админ нажимает "✅ Загрузить"
    -> Бот просит ввести название файла
    """
    try:
        short_id = query.data.replace("approve_", "")
        logger.info(f"🔥 CALLBACK ОДОБРЕНИЯ!!! data={query.data}")
        logger.info(f"✅ Approve: short_id={short_id}")

        logger.info(f"📌 Cache: {len(pending_callbacks)} items")
        pending_file: PendingFile = pending_callbacks.get(short_id)

        if not pending_file:
            logger.error(f"❌ Файл не найден для short_id: {short_id}")
            await query.answer("❌ Ошибка: файл не найден", show_alert=True)
            return

        logger.info(f"📌 Файл найден: {pending_file.original_filename}")

        # ✅ Помечаем, что файл одобрен
        pending_file.approved_at = datetime.now()
        pending_file.waiting_for_name = True

        # ✅ Сохраняем контекст администратора
        admin_id = query.from_user.id
        admin_context[admin_id] = {
            "last_approved_short_id": short_id,
            "waiting_since": datetime.now(),
        }

        logger.info(f"💾 Контекст админа сохранён: {admin_context[admin_id]}")

        # ✅ Отправляем запрос на ввод названия
        media_emoji = "📷" if pending_file.media_type == "PHOTO" else "📄"
        size_mb = pending_file.size_bytes / 1024 / 1024

        escaped_filename = escape(pending_file.original_filename)
        escaped_media_type = escape(pending_file.media_type)
        message_text = (
            f"{media_emoji} <b>Введите название файла для сайта</b>\n\n"
            f"📝 <b>Текущее имя:</b> <code>{escaped_filename}</code>\n"
            f"📊 <b>Размер:</b> <code>{size_mb:.1f} МБ</code>\n"
            f"📌 <b>Тип:</b> <code>{escaped_media_type}</code>\n\n"
            f"💬 <b>Пожалуйста, напишите желаемое название</b>\n\n"
            f"<i>Примеры:</i>\n"
            f"<code>Приказ (2025) - Военные юристы</code>\n"
            f"<code>документ-образец</code>\n"
            f"<code>фото_конференции_01</code>\n\n"
            f"✅ Название может содержать: буквы, цифры, пробелы, дефисы, точки, скобки\n"
            f"❌ Не нужно указывать расширение (.pdf, .jpg и т.д.)"
        )

        await bot.send_message(chat_id=admin_id, text=message_text, parse_mode="HTML")

        logger.info(f"📤 Запрос на ввод названия отправлен админу {admin_id}")

        # ✅ Отредактируем исходное сообщение с кнопками
        try:
            if pending_file.media_type == "PHOTO":
                await bot.edit_message_caption(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    caption="⏳ Ожидание названия файла...",
                )
            else:
                await bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text="⏳ Ожидание названия файла...",
                )
            logger.info(f"✅ Исходное сообщение отредактировано")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать исходное сообщение: {e}")

        await query.answer("✅ Введите название файла", show_alert=False)

    except Exception as e:
        logger.error(f"❌ ОШИБКА В HANDLE_APPROVE: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)


@router.callback_query(F.data.startswith("reject_"))
async def handle_reject(query: types.CallbackQuery):
    """Обработка отклонения файла"""
    try:
        short_id = query.data.replace("reject_", "")
        logger.info(f"🔥 CALLBACK ОТКЛОНЕНИЯ: {short_id}")

        pending_file: PendingFile = pending_callbacks.get(short_id)

        if not pending_file:
            logger.error(f"❌ Файл не найден для short_id: {short_id}")
            await query.answer("❌ Файл не найден", show_alert=True)
            return

        media_emoji = "📷" if pending_file.media_type == "PHOTO" else "📄"
        status_text = (
            f"❌ {media_emoji} Файл отклонен: {pending_file.original_filename}"
        )

        logger.info(f"📌 Отклоняем файл: {pending_file.original_filename}")

        # ✅ Редактируем сообщение
        try:
            if pending_file.media_type == "PHOTO":
                await bot.edit_message_caption(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    caption=status_text,
                )
            else:
                await bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=status_text,
                )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать сообщение: {e}")

        # ✅ Очищаем кэш
        if short_id in pending_callbacks:
            del pending_callbacks[short_id]
            logger.info(f"🗑️ Файл удален из кэша: {short_id}")

        # ✅ Очищаем контекст админа
        admin_id = query.from_user.id
        if admin_id in admin_context:
            if admin_context[admin_id].get("last_approved_short_id") == short_id:
                clear_admin_context(admin_id)

        await query.answer("✅ Файл отклонен", show_alert=True)

    except Exception as e:
        logger.error(f"❌ ОШИБКА ПРИ ОТКЛОНЕНИИ: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

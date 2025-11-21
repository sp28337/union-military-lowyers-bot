import logging
from io import BytesIO
from aiogram import Bot, Router, F
from aiogram.types import CallbackQuery, Message
# from aiogram.filters import Command
# from aiogram.client.session import aiohttp_helpers

from config import telegram_config, app_config
from models.schemas import MediaStatus, MediaType
from services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)
router = Router()

supabase_service = SupabaseService()


def admin_only(func):
    """Декоратор для проверки прав админа"""

    async def wrapper(message_or_query, *args, **kwargs):
        user_id = message_or_query.from_user.id if isinstance(message_or_query,
                                                              Message) else message_or_query.from_user.id
        if user_id != telegram_config.admin_id:
            await message_or_query.answer("❌ У вас нет прав!")
            return
        return await func(message_or_query, *args, **kwargs)

    return wrapper


@router.callback_query(F.data.startswith("approve_"))
@admin_only
async def handle_approve(callback_query: CallbackQuery, bot: Bot):
    """
    Обработчик кнопки "✅ Загрузить"

    Алгоритм:
    1. Извлекаем telegram_file_id из callback_data
    2. Скачиваем файл из Telegram
    3. Загружаем в Supabase Storage
    4. Сохраняем метаданные в БД
    5. Удаляем из pending_uploads
    6. Уведомляем админа об успехе
    """
    try:
        # Извлекаем file_id
        telegram_file_id = callback_query.data.replace("approve_", "")

        # Получаем информацию о файле из pending_uploads
        pending_uploads = await supabase_service.get_pending_uploads()
        media_item = next(
            (item for item in pending_uploads if item["telegram_file_id"] == telegram_file_id),
            None
        )

        if not media_item:
            await callback_query.answer("❌ Файл не найден!", show_alert=True)
            return

        # Отправляем сообщение о начале загрузки
        await callback_query.answer("⏳ Загружаю файл...", show_alert=False)
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="⏳ Загружаю файл на сервер..."
        )

        # Скачиваем файл из Telegram
        file_info = await bot.get_file(telegram_file_id)
        downloaded = await bot.session.download_file(file_info.file_path)
        file_data = BytesIO(downloaded)

        # Загружаем в Supabase Storage
        storage_url = await supabase_service.upload_file_to_storage(
            file_data=file_data,
            filename=media_item["filename"],
            media_type=MediaType(media_item["media_type"])
        )

        # Обновляем информацию о файле
        media_item_obj = MediaItem(
            telegram_file_id=telegram_file_id,
            media_type=MediaType(media_item["media_type"]),
            filename=media_item["filename"],
            mime_type=media_item.get("mime_type", ""),
            size_bytes=media_item["size_bytes"],
            storage_url=storage_url,
            caption=media_item.get("caption"),
            telegram_post_id=media_item["telegram_post_id"],
            status=MediaStatus.UPLOADED
        )

        # Сохраняем в основную таблицу (documents или photos)
        await supabase_service.save_media_to_db(media_item_obj)

        # Удаляем из pending_uploads
        await supabase_service.approve_upload(telegram_file_id)

        # Уведомляем админа об успехе
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"✅ Файл успешно загружен!\n\n"
                 f"📎 Ссылка: {storage_url}"
        )

        logger.info(f"✅ Файл успешно загружен: {media_item['filename']}")

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке: {e}")
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"❌ Ошибка при загрузке:\n{str(e)}"
        )


@router.callback_query(F.data.startswith("reject_"))
@admin_only
async def handle_reject(callback_query: CallbackQuery, bot: Bot):
    """Обработчик кнопки "❌ Отклонить" """
    try:
        telegram_file_id = callback_query.data.replace("reject_", "")

        # Удаляем из pending_uploads
        # (Здесь нужно добавить метод delete в SupabaseService)

        await callback_query.answer("✅ Файл отклонен", show_alert=True)
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="❌ Файл отклонен и не будет загружен на сайт"
        )

        logger.info(f"❌ Файл отклонен: {telegram_file_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при отклонении: {e}")


@router.command("status")
@admin_only
async def handle_status(message: Message):
    """Проверить статус загрузок"""
    try:
        pending = await supabase_service.get_pending_uploads()

        status_text = f"📊 *Статус загрузок*\n\n"
        status_text += f"⏳ Ожидают подтверждения: {len(pending)}\n\n"

        if pending:
            for item in pending[:5]:  # Показываем первые 5
                status_text += f"• {item['filename']}\n"

            if len(pending) > 5:
                status_text += f"\n... и ещё {len(pending) - 5} файлов"

        await message.answer(status_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {e}")

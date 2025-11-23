from aiogram import types, Router, F
from aiogram.types import CallbackQuery
from io import BytesIO
import logging

from config import bot, telegram_config, app_config
from services.supabase_service import SupabaseService
from models.schemas import MediaType
from handlers.channel_handler import file_cache

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("approve_"))
async def handle_approve(query: types.CallbackQuery):
    """Обработка одобрения файла"""
    try:
        short_id = query.data.replace("approve_", "")
        logger.info(f"🔥 CALLBACK СРАБОТАЛ!!! data={query.data}")
        logger.info(f"✅ Approve: short_id={short_id}")

        logger.info(f"📌 Cache: {file_cache}")
        file_id = file_cache.get(short_id)

        if not file_id:
            logger.error(f"❌ File ID не найден для short_id: {short_id}")
            await query.answer("❌ Ошибка: файл не найден", show_alert=True)
            return

        logger.info(f"📌 file_id found: {file_id}")

        logger.info(f"📥 Загружаю файл: {file_id}")
        file_info = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        file_data = BytesIO(file_bytes.read())
        logger.info(f"✅ Файл скачан: {file_info.file_size} bytes")

        # Получаем информацию о файле из pending_uploads
        pending = await SupabaseService.get_pending_uploads()
        media_item = None
        media_type = None

        for item in pending:
            if item["telegram_file_id"] == file_id:
                media_item = item
                media_type = MediaType[item["media_type"].upper()]
                break

        if not media_item:
            logger.error(f"❌ Информация о файле не найдена в pending_uploads")
            await query.answer("❌ Информация о файле не найдена", show_alert=True)
            return

        logger.info(f"📤 Загружаю в Supabase Storage...")

        # Загружаем в Storage
        storage_url = await SupabaseService.upload_file_to_storage(
            file_data,
            media_item["filename"],
            media_type
        )

        # Определяем тип медиа для ответа
        media_type_str = "Документ" if media_type == MediaType.DOCUMENT else "Фото"
        success_msg = f"✅ {media_type_str} одобрен и загружен!\n🔗 URL: {storage_url}"

        # Редактируем сообщение в зависимости от типа
        try:
            if media_type == MediaType.DOCUMENT:
                # Документ - есть текст
                await bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=success_msg
                )
            else:
                # Фото - используем caption
                await bot.edit_message_caption(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    caption=success_msg
                )
            logger.info(f"✅ {media_type_str} успешно одобрен")
        except Exception as e:
            logger.warning(f"⚠️ Не получилось отредактировать сообщение: {e}")

        # Одобрляем и удаляем из очереди
        await SupabaseService.approve_upload(file_id)

        # Очищаем кэш
        if short_id in file_cache:
            del file_cache[short_id]
            logger.info(f"🗑️ Кэш очищен для {short_id}")

        await query.answer("✅ Файл одобрен!", show_alert=True)

    except Exception as e:
        logger.error(f"❌ ОШИБКА: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("reject_"))
async def handle_reject(query: types.CallbackQuery):
    """Обработка отклонения файла"""
    try:
        short_id = query.data.replace("reject_", "")
        logger.info(f"🔥 REJECT CALLBACK: {short_id}")

        file_id = file_cache.get(short_id)

        if not file_id:
            logger.error(f"❌ File ID не найден для short_id: {short_id}")
            await query.answer("❌ Файл не найден", show_alert=True)
            return

        # Получаем информацию о файле из pending_uploads
        pending = await SupabaseService.get_pending_uploads()
        media_item = None

        for item in pending:
            if item["telegram_file_id"] == file_id:
                media_item = item
                break

        if not media_item:
            await query.answer("❌ Информация о файле не найдена", show_alert=True)
            return

        media_type_str = "Документ" if media_item["media_type"] == "DOCUMENT" else "Фото"

        # Отклоняем и удаляем из очереди
        await SupabaseService.reject_upload(file_id)

        # Редактируем сообщение
        try:
            if media_item["media_type"] == "DOCUMENT":
                await bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=f"❌ {media_type_str} отклонен"
                )
            else:
                await bot.edit_message_caption(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    caption=f"❌ {media_type_str} отклонен"
                )
        except Exception as e:
            logger.warning(f"⚠️ Не получилось отредактировать сообщение: {e}")

        # Очищаем кэш
        if short_id in file_cache:
            del file_cache[short_id]

        await query.answer("✅ Файл отклонен", show_alert=True)

    except Exception as e:
        logger.error(f"❌ ОШИБКА при отклонении: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

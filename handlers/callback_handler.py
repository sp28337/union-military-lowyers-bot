from aiogram import types, Router, F
from io import BytesIO
import logging

from config import bot
from services.github_service import GitHubService
from schemas.media_schemas import MediaType
from storage import pending_callbacks

logger = logging.getLogger(__name__)
router = Router()

github_service = GitHubService()


@router.callback_query(F.data.startswith("approve_"))
async def handle_approve(query: types.CallbackQuery):
    """Обработка одобрения файла"""
    try:
        short_id = query.data.replace("approve_", "")
        logger.info(f"🔥 CALLBACK СРАБОТАЛ!!! data={query.data}")
        logger.info(f"✅ Approve: short_id={short_id}")

        logger.info(f"📌 Cache: {pending_callbacks}")
        file_id = pending_callbacks.get(short_id)

        if not file_id:
            logger.error(f"❌ File ID не найден для short_id: {short_id}")
            await query.answer("❌ Ошибка: файл не найден", show_alert=True)
            return

        logger.info(f"📌 file_id found: {file_id}")

        logger.info(f"📥 Загружаю файл из Telegram: {file_id}")
        file_info = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        file_data = BytesIO(file_bytes.read())
        logger.info(f"✅ Файл скачан: {file_info.file_size} bytes")

        # Telegram не сохраняет оригинальное имя в file_info
        # Поэтому используем расширение из file_path
        filename = file_info.file_path.split("/")[-1]
        if "." not in filename:
            # Если расширения нет, определяем по содержимому или используем генерируемое имя
            filename = f"file_{file_id[:8]}"

        # Определяем тип медиа (фото или документ)
        file_ext = filename.split(".")[-1].lower()
        media_type = (
            MediaType.PHOTO
            if file_ext in ["jpg", "jpeg", "png", "gif", "webp"]
            else MediaType.DOCUMENT
        )

        logger.info(f"📤 Загружаю в GitHub...")
        logger.info(f"📝 Filename: {filename}")
        logger.info(f"📌 Media Type: {media_type}")

        # ✅ Загружаем в GitHub
        storage_url = await github_service.upload_file_to_github(
            file_data, filename, media_type
        )

        # Определяем тип медиа для ответа
        media_type_str = "Документ" if media_type == MediaType.DOCUMENT else "Фото"
        success_msg = (
            f"✅ {media_type_str} одобрен и загружен!\n\n"
            f"🔗 <b>URL:</b>\n<code>{storage_url}</code>"
        )

        # Редактируем сообщение в зависимости от типа
        try:
            if media_type == MediaType.DOCUMENT:
                # Документ - есть текст
                await bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=success_msg,
                    parse_mode="HTML",
                )
            else:
                # Фото - используем caption
                await bot.edit_message_caption(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    caption=success_msg,
                    parse_mode="HTML",
                )
            logger.info(f"✅ {media_type_str} успешно одобрен")
        except Exception as e:
            logger.warning(f"⚠️ Не получилось отредактировать сообщение: {e}")

        # ✅ Очищаем кэш
        if short_id in pending_callbacks:
            del pending_callbacks[short_id]
            logger.info(f"🗑️ Кэш очищен для {short_id}")

        await query.answer("✅ Файл одобрен и загружен!", show_alert=True)

    except Exception as e:
        logger.error(f"❌ ОШИБКА: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)


@router.callback_query(F.data.startswith("reject_"))
async def handle_reject(query: types.CallbackQuery):
    """Обработка отклонения файла"""
    try:
        short_id = query.data.replace("reject_", "")
        logger.info(f"🔥 REJECT CALLBACK: {short_id}")

        file_id = pending_callbacks.get(short_id)

        if not file_id:
            logger.error(f"❌ File ID не найден для short_id: {short_id}")
            await query.answer("❌ Файл не найден", show_alert=True)
            return

        media_type = MediaType.DOCUMENT  # Значение по умолчанию
        media_type_str = "Документ"

        # Редактируем сообщение
        try:
            if query.message.photo:
                # Это было фото
                media_type_str = "Фото"
                await bot.edit_message_caption(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    caption=f"❌ {media_type_str} отклонен",
                )
            else:
                # Это был документ/текст
                await bot.edit_message_text(
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    text=f"❌ {media_type_str} отклонен",
                )
        except Exception as e:
            logger.warning(f"⚠️ Не получилось отредактировать сообщение: {e}")

        # ✅ Очищаем кэш
        if short_id in pending_callbacks:
            del pending_callbacks[short_id]
            logger.info(f"🗑️ Кэш очищен для {short_id}")

        await query.answer("✅ Файл отклонен", show_alert=True)

    except Exception as e:
        logger.error(f"❌ ОШИБКА при отклонении: {e}", exc_info=True)
        await query.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

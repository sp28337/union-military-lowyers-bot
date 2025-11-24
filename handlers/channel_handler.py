import logging
from aiogram import Bot, Router
from aiogram.types import Message
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import uuid

from storage import pending_callbacks
from schemas.media_schemas import MediaItem, MediaType, MediaStatus
from services.github_service import GitHubService
from config import telegram_config, app_config

logger = logging.getLogger(__name__)
router = Router()

github_service = GitHubService()


@router.channel_post()
async def handle_channel_posts(message: Message, bot: Bot):
    """Обработчик всех постов из канала"""
    logger.info(f"📨 Новый пост в канале: ID={message.message_id}")

    if message.document:
        await handle_document(message, bot)
    elif message.photo:
        await handle_photo(message, bot)
    elif message.media_group_id:
        logger.info(f"📦 Обнаружен альбом: {message.media_group_id}")
        await handle_photo(message, bot)


async def handle_document(message: Message, bot: Bot) -> None:
    """Обработка документов"""
    try:
        document = message.document
        logger.info(f"📄 Обнаружен документ: {document.file_name}")

        if document.mime_type not in app_config.ALLOWED_DOCUMENTS:
            logger.warning(f"⚠️ Неподдерживаемый формат: {document.mime_type}")
            return

        max_size_bytes = app_config.MAX_FILE_SIZE_MB * 1024 * 1024
        if document.file_size > max_size_bytes:
            logger.warning(f"⚠️ Файл слишком большой")
            return

        media_item = MediaItem(
            telegram_file_id=document.file_id,
            media_type=MediaType.DOCUMENT,
            filename=document.file_name,
            mime_type=document.mime_type,
            size_bytes=document.file_size,
            caption=message.caption,
            telegram_post_id=message.message_id,
            status=MediaStatus.PENDING,
        )

        await ask_admin_for_approval(bot, media_item)
        logger.info(f"✅ Документ добавлен в очередь: {document.file_name}")

    except Exception as e:
        logger.error(f"❌ Ошибка обработки документа: {e}", exc_info=True)


async def handle_photo(message: Message, bot: Bot) -> None:
    """Обработка фотографий"""
    try:
        photo = message.photo[-1]
        logger.info(f"📷 Обнаружено фото: {photo.file_id}")

        max_size_bytes = app_config.MAX_IMAGE_SIZE_MB * 1024 * 1024
        if photo.file_size > max_size_bytes:
            logger.warning(f"⚠️ Фото слишком большое")
            return

        media_item = MediaItem(
            telegram_file_id=photo.file_id,
            media_type=MediaType.PHOTO,
            filename=f"photo_{message.message_id}.jpg",
            mime_type="image/jpeg",
            size_bytes=photo.file_size,
            caption=message.caption,
            telegram_post_id=message.message_id,
            status=MediaStatus.PENDING,
        )

        await ask_admin_for_approval(bot, media_item)
        logger.info(f"✅ Фото добавлено в очередь")

    except Exception as e:
        logger.error(f"❌ Ошибка обработки фото: {e}", exc_info=True)


async def ask_admin_for_approval(bot: Bot, media_item: MediaItem) -> None:
    """Отправляет админу запрос подтверждения"""

    # ✅ Генерируем short_id и СОХРАНЯЕМ В ПАМЯТИ
    short_id = str(uuid.uuid4())[:8]
    pending_callbacks[short_id] = media_item.telegram_file_id

    logger.info(f"💾 Сохранил mapping: {short_id} -> {media_item.telegram_file_id}")
    logger.info(f"📌 Всё в кэше: {pending_callbacks}")

    media_emoji = "📷" if media_item.media_type == MediaType.PHOTO else "📄"
    size_mb = media_item.size_bytes / 1024 / 1024

    caption = (
        f"{media_emoji} <b>Новый файл для загрузки</b>\n\n"
        f"📝 Имя: <code>{media_item.filename}</code>\n"
        f"📊 Размер: <code>{size_mb:.1f} МБ</code>\n"
        f"📌 Тип: <code>{media_item.media_type.value}</code>\n"
    )

    if media_item.caption:
        caption += f"💬 Описание: <code>{media_item.caption}</code>\n"

    caption += f"\n❓ Загрузить на сайт?"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Загрузить", callback_data=f"approve_{short_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"reject_{short_id}"
                ),
            ]
        ]
    )

    logger.warning(f"⚠️ ПЕРЕД ОТПРАВКОЙ КНОПОК:")
    logger.warning(f"⚠️ callback_data должна быть: approve_{short_id}")
    logger.warning(f"⚠️ Длина callback_data: {len(f'approve_{short_id}')}")

    if media_item.media_type == MediaType.PHOTO:
        try:
            await bot.send_photo(
                chat_id=telegram_config.admin_id,
                photo=media_item.telegram_file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            logger.info(f"✅ Запрос подтверждения отправлен (фото)")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фото: {e}")
            await bot.send_message(
                chat_id=telegram_config.admin_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    else:
        await bot.send_message(
            chat_id=telegram_config.admin_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        logger.info(f"✅ Запрос подтверждения отправлен (документ)")

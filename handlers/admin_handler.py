import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from config import telegram_config
from services.github_service import GitHubService  # ✅ GitHub
from models.schemas import MediaType

logger = logging.getLogger(__name__)
router = Router()

github_service = GitHubService()


def admin_only(func):
    """Декоратор для проверки прав админа"""

    async def wrapper(message_or_query, *args, **kwargs):
        user_id = (
            message_or_query.from_user.id
            if hasattr(message_or_query, 'from_user')
            else message_or_query.message.from_user.id
        )
        if user_id != telegram_config.admin_id:
            if isinstance(message_or_query, Message):
                await message_or_query.answer("❌ У вас нет прав!")
            else:
                await message_or_query.answer("❌ У вас нет прав!", show_alert=True)
            return
        return await func(message_or_query, *args, **kwargs)

    return wrapper


@router.message(Command("status"))
async def handle_status(message: Message):
    """Проверить статус загрузок и хранилища"""
    # ПРОВЕРКА ПРАВ АДМИНА
    if message.from_user.id != telegram_config.admin_id:
        await message.answer("❌ У вас нет прав!")
        return

    try:
        # ✅ Получаем статистику из GitHub
        stats = await github_service.get_storage_stats()

        status_text = f"📊 <b>Статус GitHub Storage</b>\n\n"
        status_text += f"🐙 Репозиторий: <code>{stats.get('repo_name', 'N/A')}</code>\n"
        status_text += f"📁 Папка: <code>{stats.get('media_folder', 'N/A')}</code>\n"
        status_text += f"🌿 Ветка: <code>{stats.get('branch', 'main')}</code>\n\n"

        status_text += f"📦 <b>Использование:</b>\n"
        status_text += f"📄 Файлов: <b>{stats.get('total_files', 0)}</b>\n"
        status_text += f"💾 Размер: <b>{stats.get('total_size_mb', 0):.2f} МБ</b>\n\n"

        status_text += f"✅ Система работает стабильно"

        await message.answer(status_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка получения статистики: {str(e)[:200]}")


@router.message(Command("files"))
async def handle_list_files(message: Message):
    """Список загруженных файлов"""
    if message.from_user.id != telegram_config.admin_id:
        await message.answer("❌ У вас нет прав!")
        return

    try:
        # Получаем список всех файлов
        files = await github_service.list_uploaded_files()

        if not files:
            await message.answer("📂 Хранилище пусто")
            return

        # Группируем по типам
        photos = [f for f in files if f['type'] == 'photo']
        documents = [f for f in files if f['type'] == 'document']

        text = f"📂 <b>Загруженные файлы</b>\n\n"
        text += f"📷 Фото: <b>{len(photos)}</b>\n"
        text += f"📄 Документы: <b>{len(documents)}</b>\n\n"

        text += f"<b>Последние 10 файлов:</b>\n"
        for i, file in enumerate(files[:10], 1):
            size_kb = file['size'] / 1024
            text += f"{i}. {file['name']} ({size_kb:.1f} КБ)\n"

        if len(files) > 10:
            text += f"\n... и ещё {len(files) - 10} файлов"

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")


@router.message(Command("start"))
async def handle_start(message: Message):
    """Команда /start для админа"""
    if message.from_user.id != telegram_config.admin_id:
        await message.answer("❌ У вас нет прав!")
        return

    welcome_text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"🤖 Я бот для управления загрузкой файлов на GitHub.\n\n"
        f"📝 Доступные команды:\n"
        f"/status - Статистика GitHub хранилища\n"
        f"/files - Список загруженных файлов\n"
        f"/help - Справка\n\n"
        f"💡 Когда в канал загружается документ или фото, я пришлю вам запрос на подтверждение."
    )

    await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
async def handle_help(message: Message):
    """Справка по командам"""
    if message.from_user.id != telegram_config.admin_id:
        await message.answer("❌ У вас нет прав!")
        return

    help_text = (
        f"<b>📚 Справка по командам</b>\n\n"
        f"<b>/start</b> - Главное меню\n"
        f"<b>/status</b> - Статистика GitHub Storage\n"
        f"<b>/files</b> - Список всех загруженных файлов\n"
        f"<b>/help</b> - Эта справка\n\n"
        f"<b>Как это работает:</b>\n"
        f"1️⃣ Вы загружаете файл в канал\n"
        f"2️⃣ Я обнаруживаю файл и отправляю вам уведомление\n"
        f"3️⃣ Вы нажимаете '✅ Загрузить' или '❌ Отклонить'\n"
        f"4️⃣ Файл попадает в GitHub или отклоняется\n\n"
        f"<b>Где хранятся файлы:</b>\n"
        f"🐙 GitHub репозиторий: <code>{telegram_config.github_repo}</code>\n"
        f"📁 Папка: <code>media/</code>\n"
        f"🌐 Доступ: через raw.githubusercontent.com\n\n"
        f"<b>Поддерживаемые форматы:</b>\n"
        f"📄 Документы: PDF, DOCX, XLSX\n"
        f"📷 Фото: JPG, PNG, WebP, GIF"
    )

    await message.answer(help_text, parse_mode="HTML")

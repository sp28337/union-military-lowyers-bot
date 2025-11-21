import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import telegram_config, app_config
from handlers import channel_handler, admin_handler
from services.supabase_service import SupabaseService

# Конфиг логирования
logging.basicConfig(
    level=app_config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Инициализация сервисов
supabase_service = SupabaseService()


async def main():
    """Главная функция приложения"""

    logger.info("🚀 Запуск Telegram бота...")
    logger.info(f"✅ Версия aiogram: 3.22.0")
    logger.info(f"✅ Администратор: {telegram_config.admin_id}")
    logger.info(f"✅ Канал: {telegram_config.channel_id}")

    # Инициализация Bot и Dispatcher
    bot = Bot(
        token=telegram_config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dispatcher = Dispatcher()

    # Добавляем роутеры
    dispatcher.include_router(channel_handler.router)
    dispatcher.include_router(admin_handler.router)

    try:
        # Инициализируем Supabase (создаём таблицы если нужно)
        await supabase_service.initialize_tables()

        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Бот активирован: @{bot_info.username}")

        # Запускаем бота
        logger.info("⏳ Слушаю Telegram канал...")
        await dispatcher.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")

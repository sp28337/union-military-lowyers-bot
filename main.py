import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from services.supabase_service import SupabaseService
from config import bot, dp, telegram_config, app_config
from handlers import channel_handler, callback_handler


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

    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК TELEGRAM БОТА")
    logger.info("=" * 60)
    logger.info(f"✅ Версия aiogram: 3.22.0")
    logger.info(f"✅ Администратор ID: {telegram_config.admin_id}")
    logger.info(f"✅ Канал ID: {telegram_config.channel_id}")
    logger.info("=" * 60)

    # Инициализация Bot и Dispatcher
    bot = Bot(
        token=telegram_config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dispatcher = Dispatcher(storage=MemoryStorage())

    # ✅ Правильное добавление роутеров в aiogram 3.22.0
    dispatcher.include_router(channel_handler.router)
    dispatcher.include_router(admin_handler.router)
    dispatcher.include_router(callback_handler.router)

    try:
        # Инициализируем Supabase (создаём таблицы если нужно)
        logger.info("🔄 Инициализация Supabase...")
        await supabase_service.initialize_tables()
        logger.info("✅ Supabase инициализирован")

        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"✅ Бот активирован: @{bot_info.username}")
        logger.info(f"✅ ID бота: {bot_info.id}")

        # Отправляем уведомление админу
        await bot.send_message(
            chat_id=telegram_config.admin_id,
            text=f"✅ <b>Бот запущен!</b>\n\n"
                 f"🤖 @{bot_info.username}\n"
                 f"📌 ID: <code>{bot_info.id}</code>\n\n"
                 f"Я готов мониторить канал и обрабатывать файлы.",
            parse_mode="HTML"
        )

        # Запускаем бота
        logger.info("⏳ Слушаю Telegram канал...")
        logger.info("💡 Нажмите Ctrl+C для остановки")

        # ✅ ИСПРАВЛЕНИЕ: Принимаем ВСЕ обновления
        await dispatcher.start_polling(bot, allowed_updates=None)

    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}", exc_info=True)
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

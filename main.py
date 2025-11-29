import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from services.github_service import GitHubService
from config import telegram_config, app_config, github_config
from handlers import (
    channel_handler,
    callback_handler,
    message_handler,
    admin_handler,
)


logging.basicConfig(
    level=app_config.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

github_service = GitHubService()


async def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК TELEGRAM БОТА")
    logger.info("=" * 60)
    logger.info(f"✅ Версия aiogram: 3.22.0")
    logger.info(f"✅ Администратор ID: {telegram_config.admin_id}")
    logger.info(f"✅ Канал ID: {telegram_config.channel_id}")
    logger.info(f"✅ GitHub Repo: {github_config.repo}")
    logger.info(f"✅ Media Folder: {github_config.media_folder}")
    logger.info("=" * 60)

    bot_instance = Bot(
        token=telegram_config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dispatcher = Dispatcher(storage=MemoryStorage())

    # ВАЖНО: MessageHandler ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ!
    dispatcher.include_router(admin_handler.router)
    dispatcher.include_router(channel_handler.router)
    dispatcher.include_router(callback_handler.router)
    dispatcher.include_router(message_handler.router)  # ✅ ПОСЛЕДНИЙ!

    try:
        logger.info("🔄 Инициализация GitHub Storage...")
        stats = await github_service.get_storage_stats()
        logger.info(f"✅ GitHub инициализирован")
        logger.info(f"📊 Текущее использование: {stats.get('total_size_mb', 0):.2f} МБ")

        bot_info = await bot_instance.get_me()
        logger.info(f"✅ Бот активирован: @{bot_info.username}")
        logger.info(f"✅ ID бота: {bot_info.id}")

        await bot_instance.send_message(
            chat_id=telegram_config.admin_id,
            text=f"✅ <b>Бот запущен!</b>\n\n"
            f"🤖 @{bot_info.username}\n"
            f"📌 ID: <code>{bot_info.id}</code>\n\n"
            f"🐙 GitHub Repo: <code>{github_config.repo}</code>\n"
            f"📁 Media Folder: <code>{github_config.media_folder}</code>\n\n",
            parse_mode="HTML",
        )

        logger.info("⏳ Слушаю Telegram канал...")
        logger.info("💡 Нажмите Ctrl+C для остановки")

        await dispatcher.start_polling(bot_instance, allowed_updates=None)

    except Exception as error:
        logger.error(f"❌ Ошибка запуска: {error}", exc_info=True)
        raise
    finally:
        await bot_instance.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig:
    """Конфиг Telegram Bot API"""
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id: int = int(os.getenv("TELEGRAM_CHANNEL_ID", "0"))
    admin_id: int = int(os.getenv("ADMIN_ID", "0"))

    def __post_init__(self):
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env")
        if self.channel_id == 0:
            raise ValueError("TELEGRAM_CHANNEL_ID не установлен в .env")
        if self.admin_id == 0:
            raise ValueError("ADMIN_ID не установлен в .env")


@dataclass
class GitHubConfig:
    """Конфиг GitHub Storage"""
    token: str = os.getenv("GITHUB_TOKEN")
    repo: str = os.getenv("GITHUB_REPO")  # format: "username/repo"
    media_folder: str = os.getenv("GITHUB_MEDIA_FOLDER", "media")

    def __post_init__(self):
        if not self.token:
            raise ValueError("GITHUB_TOKEN не установлен в .env")
        if not self.repo:
            raise ValueError("GITHUB_REPO не установлен в .env")
        if "/" not in self.repo:
            raise ValueError("GITHUB_REPO должен быть в формате 'username/repo'")


@dataclass
class AppConfig:
    """Основные параметры приложения"""
    # Размеры файлов (в МБ)
    MAX_FILE_SIZE_MB: int = 50
    MAX_IMAGE_SIZE_MB: int = 10

    # Поддерживаемые форматы
    ALLOWED_DOCUMENTS: tuple = (
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    ALLOWED_IMAGES: tuple = (
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/jpg",
        "image/gif",
    )

    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def allowed_mime_types(self) -> tuple:
        """Получить все поддерживаемые MIME типы"""
        return self.ALLOWED_DOCUMENTS + self.ALLOWED_IMAGES


# ============================================================
# Инициализация конфигов
# ============================================================

telegram_config = TelegramConfig()
github_config = GitHubConfig()
app_config = AppConfig()

# ============================================================
# Инициализация Telegram Bot и Dispatcher
# ============================================================

default_properties = DefaultBotProperties(
    parse_mode=ParseMode.HTML
)

bot = Bot(
    token=telegram_config.bot_token,
    default=default_properties
)

dp = Dispatcher()

logger.info("✅ Config инициализирован")
logger.info(f"🤖 Telegram Token: {telegram_config.bot_token[:20]}...")
logger.info(f"👤 Admin ID: {telegram_config.admin_id}")
logger.info(f"📢 Channel ID: {telegram_config.channel_id}")
logger.info(f"🐙 GitHub Repo: {github_config.repo}")
logger.info(f"📁 GitHub Media Folder: {github_config.media_folder}")

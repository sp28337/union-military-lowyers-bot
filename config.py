import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TelegramConfig:
    """Конфиг Telegram Bot API"""
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id: int = int(os.getenv("TELEGRAM_CHANNEL_ID", "0"))
    admin_id: int = int(os.getenv("ADMIN_ID", "0"))

    def __post_init__(self):
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env")


@dataclass
class SupabaseConfig:
    """Конфиг Supabase Storage и Database"""
    url: str = os.getenv("SUPABASE_URL")
    key: str = os.getenv("SUPABASE_KEY")
    bucket_name: str = os.getenv("SUPABASE_BUCKET", "documents")

    def __post_init__(self):
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL и SUPABASE_KEY не установлены в .env")


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
    )

    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def allowed_mime_types(self) -> tuple:
        """Получить все поддерживаемые MIME типы"""
        return self.ALLOWED_DOCUMENTS + self.ALLOWED_IMAGES


# Инициализация конфигов
telegram_config = TelegramConfig()
supabase_config = SupabaseConfig()
app_config = AppConfig()

import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PendingFile:
    """Структура для хранения информации о файле на модерации"""

    file_id: str
    media_type: str  # "PHOTO" или "DOCUMENT"
    original_filename: str
    mime_type: str
    size_bytes: int
    caption: Optional[str] = None
    telegram_post_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    waiting_for_name: bool = False  # Флаг: ждём ввода названия


# Основной кэш для ожидающих подтверждения файлов
# short_id -> PendingFile
pending_callbacks: Dict[str, PendingFile] = {}

# Второй кэш для связи с диалогом
# Хранит: admin_id -> {"last_approved_short_id": str, "waiting_since": datetime}
# Это нужно, чтобы связать сообщение админа с правильным файлом
admin_context: Dict[int, Dict] = {}


def log_cache_state():
    """Логирование состояния кэша"""
    logger.info(f"📊 Cache state: {len(pending_callbacks)} items")
    for short_id, pending_file in pending_callbacks.items():
        logger.debug(
            f"  - {short_id}: {pending_file.original_filename} "
            f"({pending_file.media_type}) - "
            f"waiting_for_name={pending_file.waiting_for_name}"
        )

    logger.info(f"👥 Admin context: {len(admin_context)} active")
    for admin_id, context in admin_context.items():
        logger.debug(f"  - Admin {admin_id}: {context.get('last_approved_short_id')}")


def clear_admin_context(admin_id: int):
    """Очистить контекст админа"""
    if admin_id in admin_context:
        del admin_context[admin_id]
        logger.info(f"🗑️ Контекст админа {admin_id} очищен")


def clear_pending_file(short_id: str):
    """Очистить файл из кэша"""
    if short_id in pending_callbacks:
        del pending_callbacks[short_id]
        logger.info(f"🗑️ Файл {short_id} удален из кэша")

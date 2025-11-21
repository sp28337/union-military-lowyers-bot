from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional


class MediaType(str, Enum):
    """Типы медиа"""
    PHOTO = "photo"
    DOCUMENT = "document"


class MediaStatus(str, Enum):
    """Статус загрузки"""
    PENDING = "pending"  # Ожидает подтверждения админа
    APPROVED = "approved"  # Одобрено админом
    REJECTED = "rejected"  # Отклонено админом
    UPLOADED = "uploaded"  # Загружено на сервер
    FAILED = "failed"  # Ошибка при загрузке


class MediaItem(BaseModel):
    """Модель элемента медиа"""
    id: Optional[str] = None
    telegram_file_id: str
    media_type: MediaType
    filename: str
    mime_type: str
    size_bytes: int
    storage_url: Optional[str] = None
    caption: Optional[str] = None
    telegram_post_id: int
    status: MediaStatus = MediaStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class PendingUpload(BaseModel):
    """Модель ожидающей загрузки"""
    media_item: MediaItem
    telegram_message_id: int
    admin_query_message_id: Optional[int] = None

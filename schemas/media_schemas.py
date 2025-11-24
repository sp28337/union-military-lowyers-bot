from pydantic import BaseModel
from enum import Enum
from typing import Optional


class MediaType(str, Enum):
    """Типы медиа"""

    PHOTO = "photo"
    DOCUMENT = "document"


class MediaStatus(str, Enum):
    """Статус загрузки"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UPLOADED = "uploaded"
    FAILED = "failed"


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

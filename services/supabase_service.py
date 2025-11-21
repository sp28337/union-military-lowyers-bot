# services/supabase_service.py
"""
Сервис для работы с Supabase Storage и Database
"""
import logging
from typing import Optional, List, BinaryIO
from datetime import datetime
from io import BytesIO

from supabase import create_client, Client
from config import supabase_config, app_config
from models.schemas import MediaItem, MediaStatus, MediaType

logger = logging.getLogger(__name__)


class SupabaseService:
    """Сервис Supabase"""

    def __init__(self):
        self.client: Client = create_client(
            supabase_url=supabase_config.url,
            supabase_key=supabase_config.key
        )
        self.bucket_name = supabase_config.bucket_name

    async def initialize_tables(self) -> None:
        """
        Инициализирует таблицы в БД при первом запуске

        SQL запросы создают две таблицы:
        1. documents - для документов (PDF, DOCX и т.д.)
        2. photos - для фотографий
        3. pending_uploads - для ожидающих одобрения
        """
        try:
            # Создаём таблицу для документов
            self.client.table("documents").select("*", count="exact").execute()
        except Exception as e:
            logger.info("Создаём таблицу documents...")
            self._create_documents_table()

        try:
            # Создаём таблицу для фото
            self.client.table("photos").select("*", count="exact").execute()
        except Exception as e:
            logger.info("Создаём таблицу photos...")
            self._create_photos_table()

        try:
            # Создаём таблицу для ожидающих загрузок
            self.client.table("pending_uploads").select("*", count="exact").execute()
        except Exception as e:
            logger.info("Создаём таблицу pending_uploads...")
            self._create_pending_uploads_table()

    def _create_documents_table(self) -> None:
        """Создание таблицы документов"""
        sql = """
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            telegram_file_id TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            storage_url TEXT,
            caption TEXT,
            telegram_post_id INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_documents_status 
            ON documents(status);
        CREATE INDEX IF NOT EXISTS idx_documents_telegram_file_id 
            ON documents(telegram_file_id);
        """
        try:
            self.client.postgrest.request(
                "POST",
                "/rpc/execute_raw_sql",
                json={"sql": sql}
            )
            logger.info("✅ Таблица documents создана")
        except Exception as e:
            logger.warning(f"Таблица documents могла быть уже создана: {e}")

    def _create_photos_table(self) -> None:
        """Создание таблицы фотографий"""
        sql = """
        CREATE TABLE IF NOT EXISTS photos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            telegram_file_id TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            storage_url TEXT,
            caption TEXT,
            telegram_post_id INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_photos_status 
            ON photos(status);
        """
        try:
            self.client.postgrest.request(
                "POST",
                "/rpc/execute_raw_sql",
                json={"sql": sql}
            )
            logger.info("✅ Таблица photos создана")
        except Exception as e:
            logger.warning(f"Таблица photos могла быть уже создана: {e}")

    def _create_pending_uploads_table(self) -> None:
        """Создание таблицы ожидающих загрузок"""
        sql = """
        CREATE TABLE IF NOT EXISTS pending_uploads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            telegram_file_id TEXT NOT NULL UNIQUE,
            media_type VARCHAR(20) NOT NULL,
            filename TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            caption TEXT,
            telegram_post_id INTEGER NOT NULL,
            telegram_message_id INTEGER NOT NULL,
            admin_query_message_id INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (telegram_file_id) REFERENCES documents(telegram_file_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_pending_uploads_status 
            ON pending_uploads(telegram_file_id);
        """
        try:
            self.client.postgrest.request(
                "POST",
                "/rpc/execute_raw_sql",
                json={"sql": sql}
            )
            logger.info("✅ Таблица pending_uploads создана")
        except Exception as e:
            logger.warning(f"Таблица pending_uploads могла быть уже создана: {e}")

    async def upload_file_to_storage(
            self,
            file_data: BytesIO,
            filename: str,
            media_type: MediaType
    ) -> str:
        """
        Загружает файл в Supabase Storage

        Параметры:
            file_data (BytesIO): Бинарные данные файла
            filename (str): Имя файла
            media_type (MediaType): Тип медиа (photo/document)

        Возвращает:
            str: Публичный URL файла

        Процесс:
            1. Генерируем уникальный путь: documents/2025-11-21/uuid-filename
            2. Загружаем в Supabase Storage (параллельно)
            3. Получаем публичный URL
        """
        try:
            # Генерируем путь с датой для организации
            from datetime import datetime
            date_path = datetime.utcnow().strftime("%Y-%m-%d")
            media_folder = "photos" if media_type == MediaType.PHOTO else "documents"
            storage_path = f"{media_folder}/{date_path}/{filename}"

            # Читаем данные
            file_data.seek(0)
            file_content = file_data.read()

            # Загружаем в Storage
            response = self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=(filename, file_content, "application/octet-stream"),
                file_options={"cache-control": "3600"}
            )

            # Получаем публичный URL
            public_url = self.client.storage.from_(
                self.bucket_name
            ).get_public_url(storage_path)

            logger.info(f"✅ Файл загружен: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки файла {filename}: {e}")
            raise

    async def save_media_to_db(self, media_item: MediaItem) -> str:
        """
        Сохраняет информацию о медиа в базу данных

        Параметры:
            media_item (MediaItem): Объект с информацией о медиа

        Возвращает:
            str: ID записи в БД
        """
        try:
            table_name = "photos" if media_item.media_type == MediaType.PHOTO else "documents"

            data = {
                "telegram_file_id": media_item.telegram_file_id,
                "filename": media_item.filename,
                "mime_type": media_item.mime_type if media_item.media_type == MediaType.DOCUMENT else "image",
                "size_bytes": media_item.size_bytes,
                "storage_url": media_item.storage_url,
                "caption": media_item.caption,
                "telegram_post_id": media_item.telegram_post_id,
                "status": media_item.status.value,
            }

            response = self.client.table(table_name).insert(data).execute()

            logger.info(f"✅ Медиа сохранено в БД: {media_item.filename}")
            return response.data[0]["id"]

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в БД: {e}")
            raise

    async def add_pending_upload(self, media_item: MediaItem, telegram_message_id: int) -> None:
        """
        Добавляет файл в очередь ожидающих загрузок

        Параметры:
            media_item (MediaItem): Информация о медиа
            telegram_message_id (int): ID сообщения в Telegram
        """
        try:
            data = {
                "telegram_file_id": media_item.telegram_file_id,
                "media_type": media_item.media_type.value,
                "filename": media_item.filename,
                "size_bytes": media_item.size_bytes,
                "caption": media_item.caption,
                "telegram_post_id": media_item.telegram_post_id,
                "telegram_message_id": telegram_message_id,
            }

            self.client.table("pending_uploads").insert(data).execute()
            logger.info(f"✅ Загрузка добавлена в очередь: {media_item.filename}")

        except Exception as e:
            logger.error(f"❌ Ошибка добавления в очередь: {e}")
            raise

    async def get_pending_uploads(self) -> List[dict]:
        """Получить все ожидающие загрузки"""
        try:
            response = self.client.table("pending_uploads").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Ошибка получения ожидающих: {e}")
            return []

    async def approve_upload(self, telegram_file_id: str) -> None:
        """Одобрить загрузку"""
        try:
            self.client.table("pending_uploads").update(
                {"status": "approved"}
            ).eq("telegram_file_id", telegram_file_id).execute()
            logger.info(f"✅ Загрузка одобрена: {telegram_file_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка одобрения: {e}")
            raise

    async def get_all_uploaded_media(self, media_type: MediaType) -> List[dict]:
        """Получить все загруженные медиа определённого типа"""
        try:
            table_name = "photos" if media_type == MediaType.PHOTO else "documents"
            response = self.client.table(table_name).select("*").eq(
                "status", "uploaded"
            ).order("created_at", desc=True).execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Ошибка получения медиа: {e}")
            return []

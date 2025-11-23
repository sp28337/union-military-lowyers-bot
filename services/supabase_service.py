import logging
from typing import Optional, List
from datetime import datetime
from io import BytesIO
import uuid

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
        """Инициализирует таблицы в БД при первом запуске"""
        try:
            self.client.table("documents").select("*", count="exact").execute()
        except Exception as e:
            logger.info("Создаём таблицу documents...")
            self._create_documents_table()

        try:
            self.client.table("photos").select("*", count="exact").execute()
        except Exception as e:
            logger.info("Создаём таблицу photos...")
            self._create_photos_table()

        try:
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
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_pending_uploads_file_id 
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
        """Загружает файл в Supabase Storage"""
        try:
            date_path = datetime.utcnow().strftime("%Y-%m-%d")

            # ✅ Генерируем безопасное имя файла
            file_ext = filename.split('.')[-1] if '.' in filename else 'bin'
            safe_filename = f"{uuid.uuid4().hex}.{file_ext}"
            storage_path = f"{date_path}/{safe_filename}"

            logger.info(f"📝 Original filename: {filename}")
            logger.info(f"📝 Safe storage path: {storage_path}")
            logger.info(f"📁 Bucket: {self.bucket_name}")

            # Читаем данные из BytesIO
            file_data.seek(0)
            file_content = file_data.read()
            logger.info(f"📊 File size: {len(file_content)} bytes")

            # ✅ Загружаем файл
            response = self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=file_content,
                file_options={"cache-control": "3600"}
            )
            logger.info(f"✅ Upload response: {response}")

            # Получаем публичный URL
            public_url = self.client.storage.from_(
                self.bucket_name
            ).get_public_url(storage_path)

            logger.info(f"✅ Файл загружен: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки файла {filename}: {e}", exc_info=True)
            raise

    async def save_media_to_db(self, media_item: MediaItem) -> str:
        """Сохраняет информацию о медиа в базу данных"""
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
            logger.error(f"❌ Ошибка сохранения в БД: {e}", exc_info=True)
            raise

    async def add_pending_upload(self, media_item: MediaItem, telegram_message_id: int) -> None:
        """Добавляет файл в очередь ожидающих загрузок"""
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
            # ✅ Обработка ошибки дублирования
            if "duplicate key" in str(e).lower() or "23505" in str(e):
                logger.warning(f"⚠️ Файл уже в очереди: {media_item.filename}")
                # Не пробрасываем ошибку, просто логируем
            else:
                logger.error(f"❌ Ошибка добавления в очередь: {e}", exc_info=True)
                raise

    async def get_pending_uploads(self) -> List[dict]:
        """Получить все ожидающие загрузки"""
        try:
            response = self.client.table("pending_uploads").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Ошибка получения ожидающих: {e}", exc_info=True)
            return []

    async def approve_upload(self, telegram_file_id: str) -> None:
        """✅ Одобрить загрузку - УДАЛИТЬ из pending_uploads"""
        try:
            # ✅ ПРАВИЛЬНО - УДАЛЯЕМ из очереди!
            self.client.table("pending_uploads").delete().eq(
                "telegram_file_id", telegram_file_id
            ).execute()
            logger.info(f"✅ Загрузка одобрена и удалена из очереди: {telegram_file_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка одобрения: {e}", exc_info=True)
            raise

    async def reject_upload(self, telegram_file_id: str) -> None:
        """❌ Отклонить загрузку - УДАЛИТЬ из pending_uploads"""
        try:
            # ✅ УДАЛЯЕМ из очереди
            self.client.table("pending_uploads").delete().eq(
                "telegram_file_id", telegram_file_id
            ).execute()
            logger.info(f"❌ Загрузка отклонена и удалена из очереди: {telegram_file_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отклонения: {e}", exc_info=True)
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
            logger.error(f"❌ Ошибка получения медиа: {e}", exc_info=True)
            return []

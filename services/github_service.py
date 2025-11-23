import logging
import base64
from typing import Optional, List
from datetime import datetime
from io import BytesIO
import uuid

from github import Github, GithubException
from config import github_config, app_config
from models.schemas import MediaItem, MediaStatus, MediaType

logger = logging.getLogger(__name__)


class GitHubService:
    """Сервис для работы с GitHub Storage"""

    def __init__(self):
        """Инициализация GitHub клиента"""
        self.github = Github(github_config.token)
        self.repo_name = github_config.repo
        self.media_folder = github_config.media_folder

        try:
            # ✅ Проверяем доступ к репозиторию
            owner, repo = self.repo_name.split("/")
            self.repo = self.github.get_user(owner).get_repo(repo)
            logger.info(f"✅ Подключение к GitHub репо: {self.repo_name}")
            logger.info(f"📊 Статистика репо: {self.repo.stargazers_count} звёзд")
        except GithubException as e:
            logger.error(f"❌ Ошибка подключения к GitHub: {e}")
            raise ValueError(f"Не удалось подключиться к репо {self.repo_name}")

    async def upload_file_to_github(
            self,
            file_data: BytesIO,
            filename: str,
            media_type: MediaType
    ) -> str:
        """
        Загружает файл в GitHub репозиторий

        ✅ ЛОГИКА:
        1. Генерируем безопасное имя файла (UUID + расширение)
        2. Создаём путь: media/2025-11-23/filename.ext
        3. Кодируем файл в base64 (требование GitHub API)
        4. Загружаем через GitHub API
        5. Возвращаем публичный URL (raw.githubusercontent.com)

        ❌ НЕ ДЕЛАЕМ:
        - Не используем file_cache (кэш в памяти)
        - Не создаём локальные файлы
        - Не используем webhook'и

        ✅ ДЕЛАЕМ:
        - Async/await для неблокирующей работы
        - Правильные пути с датой
        - Полные публичные URLs
        """
        try:
            date_path = datetime.utcnow().strftime("%Y-%m-%d")

            # ✅ Генерируем безопасное имя файла
            file_ext = filename.split('.')[-1] if '.' in filename else 'bin'
            safe_filename = f"{uuid.uuid4().hex}.{file_ext}"

            # ✅ Путь внутри репозитория
            github_path = f"{self.media_folder}/{date_path}/{safe_filename}"

            logger.info(f"📝 Original filename: {filename}")
            logger.info(f"📝 Safe filename: {safe_filename}")
            logger.info(f"📝 GitHub path: {github_path}")

            # ✅ Читаем содержимое файла
            file_data.seek(0)
            file_content = file_data.read()
            logger.info(f"📊 File size: {len(file_content)} bytes")

            # ✅ GitHub API требует base64 кодирование для бинарных файлов
            encoded_content = base64.b64encode(file_content).decode('utf-8')

            # ✅ Создаём commit с файлом
            try:
                self.repo.create_file(
                    path=github_path,
                    message=f"📤 Upload: {filename} ({media_type.value})",
                    content=file_content,
                    branch="main"
                )
                logger.info(f"✅ Файл успешно загружен в GitHub")
            except GithubException as e:
                if "422" in str(e):  # File exists
                    logger.warning(f"⚠️ Файл уже существует, пытаемся перезаписать")
                    # Получаем SHA текущего файла для обновления
                    try:
                        file_content_obj = self.repo.get_contents(github_path)
                        self.repo.update_file(
                            path=github_path,
                            message=f"🔄 Update: {filename}",
                            content=file_content,
                            sha=file_content_obj.sha,
                            branch="main"
                        )
                        logger.info(f"✅ Файл успешно обновлен в GitHub")
                    except GithubException as update_error:
                        logger.error(f"❌ Ошибка обновления файла: {update_error}")
                        raise
                else:
                    raise

            # ✅ Формируем публичный URL (raw.githubusercontent.com)
            owner, repo_name = self.repo_name.split("/")
            public_url = (
                f"https://raw.githubusercontent.com/{owner}/"
                f"{repo_name}/main/{github_path}"
            )

            logger.info(f"✅ Публичный URL: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки файла в GitHub: {e}", exc_info=True)
            raise

    async def create_pending_issue(
            self,
            media_item: MediaItem,
            short_id: str
    ) -> Optional[int]:
        """
        ✅ ОПЦИОНАЛЬНО: Создаём GitHub Issue для отслеживания

        Это не обязательно, но полезно для:
        - Отслеживания истории загрузок
        - Комментариев и обсуждений
        - Интеграции с CI/CD

        ❌ НЕ ИСПОЛЬЗУЕМ:
        - Database (pending_uploads в Supabase)

        ✅ ИСПОЛЬЗУЕМ:
        - GitHub Issues как "очередь" задач
        """
        try:
            media_emoji = "📷" if media_item.media_type == MediaType.PHOTO else "📄"
            size_mb = media_item.size_bytes / 1024 / 1024

            issue_body = (
                f"{media_emoji} **Новый файл для загрузки**\n\n"
                f"- **Имя**: `{media_item.filename}`\n"
                f"- **Размер**: {size_mb:.1f} МБ\n"
                f"- **Тип**: {media_item.media_type.value}\n"
                f"- **Short ID**: `{short_id}`\n"
                f"- **Telegram Post ID**: {media_item.telegram_post_id}\n"
            )

            if media_item.caption:
                issue_body += f"- **Описание**: {media_item.caption}\n"

            # Создаём Issue
            issue = self.repo.create_issue(
                title=f"{media_emoji} {media_item.filename}",
                body=issue_body,
                labels=["media-upload", "pending"]
            )

            logger.info(f"✅ GitHub Issue создана: #{issue.number}")
            return issue.number

        except Exception as e:
            logger.warning(f"⚠️ Не удалось создать Issue: {e}")
            return None

    async def list_uploaded_files(self, media_type: Optional[MediaType] = None) -> List[dict]:
        """
        Получить список всех загруженных файлов

        ✅ ВОЗВРАЩАЕТ:
        - Список файлов с путями и URL'ами
        - Отфильтрованный по типу медиа (если указан)
        """
        try:
            files = []

            # Проходим по всем файлам в media папке
            try:
                contents = self.repo.get_contents(self.media_folder)

                def traverse_folder(items):
                    for item in items:
                        if item.type == "dir":
                            # Рекурсивно проходим по подпапкам
                            traverse_folder(self.repo.get_contents(item.path))
                        else:
                            owner, repo_name = self.repo_name.split("/")
                            url = (
                                f"https://raw.githubusercontent.com/{owner}/"
                                f"{repo_name}/main/{item.path}"
                            )

                            files.append({
                                "path": item.path,
                                "name": item.name,
                                "url": url,
                                "size": item.size,
                                "type": "photo" if item.name.lower().endswith(
                                    ('.jpg', '.jpeg', '.png', '.gif', '.webp')) else "document"
                            })

                traverse_folder(contents)

            except GithubException as e:
                if "404" in str(e):
                    logger.info(f"📁 Папка {self.media_folder} ещё не существует")
                else:
                    raise

            # Фильтруем по типу медиа
            if media_type:
                media_type_str = "photo" if media_type == MediaType.PHOTO else "document"
                files = [f for f in files if f["type"] == media_type_str]

            logger.info(f"📊 Найдено файлов: {len(files)}")
            return files

        except Exception as e:
            logger.error(f"❌ Ошибка при получении файлов: {e}", exc_info=True)
            return []

    async def delete_file(self, file_path: str) -> bool:
        """Удалить файл из репозитория"""
        try:
            file_content = self.repo.get_contents(file_path)
            self.repo.delete_file(
                path=file_path,
                message=f"🗑️ Delete: {file_content.name}",
                sha=file_content.sha,
                branch="main"
            )
            logger.info(f"✅ Файл удалён: {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления файла: {e}")
            return False

    async def get_storage_stats(self) -> dict:
        """Получить статистику использования хранилища"""
        try:
            files = await self.list_uploaded_files()
            total_size = sum(f["size"] for f in files)

            stats = {
                "total_files": len(files),
                "total_size_mb": total_size / (1024 * 1024),
                "repo_name": self.repo_name,
                "branch": "main",
                "media_folder": self.media_folder
            }

            logger.info(f"📊 Storage stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}

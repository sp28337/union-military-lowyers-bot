import logging

pending_callbacks: dict[str, str] = {}

logger = logging.getLogger(__name__)


def log_cache_state():
    """Логирование состояния кэша"""
    logger.info(f"📊 Cache state: {len(pending_callbacks)} items")
    for short_id, file_id in pending_callbacks.items():
        logger.debug(f"  - {short_id}: {file_id[:20]}...")

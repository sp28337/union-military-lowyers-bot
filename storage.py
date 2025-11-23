import logging

logger = logging.getLogger(__name__)

pending_callbacks = {}

logger.info(f"✅ storage.py загружен, pending_callbacks инициализирован: {pending_callbacks}")

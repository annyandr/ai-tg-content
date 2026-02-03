"""
Настройка логирования
"""

import logging
import sys
from datetime import datetime

# Создаём logger
logger = logging.getLogger("medical_smm")
logger.setLevel(logging.INFO)

# Форматтер
formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# File handler (опционально)
try:
    file_handler = logging.FileHandler(
        f'logs/medical_smm_{datetime.now().strftime("%Y%m%d")}.log',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except (OSError, IOError) as e:
    # Если нет папки logs или нет прав доступа - работаем без файлового логирования
    pass

logger.addHandler(console_handler)

__all__ = ["logger"]

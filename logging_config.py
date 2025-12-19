import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(message)s"
)

def setup_logger():
    logger = logging.getLogger("tts_app")
    logger.setLevel(logging.INFO)

    # tránh add handler nhiều lần
    if logger.handlers:
        return logger

    # Log file
    file_handler = RotatingFileHandler(
        f"{LOG_DIR}/app.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # Log console (Railway đọc)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

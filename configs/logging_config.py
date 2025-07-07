import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime


def setup_logging(
    logger_name: str = "AppLogger",
    log_dir: str = "logs",
    filename_prefix: str = "app",
    level: str = "INFO"
) -> logging.Logger:
    """
    Thiết lập logging đơn giản và tái sử dụng được.

    Parameters
    ----------
    logger_name : str
        Tên logger.
    log_dir : str
        Thư mục chứa file log.
    filename_prefix : str
        Tiền tố tên file log.
    level : str
        Mức độ log: DEBUG, INFO, WARNING, ERROR, CRITICAL.

    Returns
    -------
    logging.Logger
        Logger đã cấu hình sẵn.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    file_name = f"{filename_prefix}_{today}.log"
    file_path = log_path / file_name

    log_level = getattr(logging, level.upper(), logging.INFO)
    log_format = (
        "%(asctime)s - %(levelname)s - %(name)s - "
        "%(filename)s:%(lineno)d - %(message)s"
    )
    formatter = logging.Formatter(log_format)

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    logger.propagate = False

    if logger.hasHandlers():
        logger.handlers.clear()

    # Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File
    file_handler = TimedRotatingFileHandler(
        filename=file_path,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d.log"
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("Logger initialized.")
    return logger

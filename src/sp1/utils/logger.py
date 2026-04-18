import logging
from logging.handlers import RotatingFileHandler

from sp1.constants import LOG_FILE_PATH, MAX_LOG_BACKUP_COUNT, MAX_LOG_FILE_SIZE


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Returns a logger with the given name and level.

    :param str name: The name of the logger
    :param int level: The logging level
    :return logging.Logger: The logger object
    """
    logger = logging.getLogger(name)

    # Exit early if the logger already has all required handlers
    if logger.hasHandlers():
        return logger

    # Don't propagate messages to the root logger
    logger.propagate = False

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(processName)s[%(process)d] - %(threadName)s[%(thread)d] - "
        "%(name)s - %(levelname)s - %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if not LOG_FILE_PATH.parent.exists():
        LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        rotating_file_handler = RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=MAX_LOG_FILE_SIZE,
            backupCount=MAX_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        rotating_file_handler.setLevel(level)
        rotating_file_handler.setFormatter(formatter)
        logger.addHandler(rotating_file_handler)
    except Exception as e:
        logger.error(f"Failed to create the rotating file handler: {e}")

        # If the RotatingFileHandler is not available, use the NullHandler
        # to prevent the logger from raising an exception
        logger.addHandler(logging.NullHandler())

    return logger

import sys
import re
from datetime import datetime
from loguru import logger


def formatter(record, format_string):
    return format_string + record["extra"].get("end", "\n") + "{exception}"


def clean_brackets(raw_str):
    return re.sub(r"<.*?>", "", raw_str)


def logging_setup():
    format_info = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <blue>{level}</blue> | <level>{message}</level>"
    format_error = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <blue>{level}</blue> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
    )
    current_date = datetime.now().strftime("%Y-%m-%d")
    logger_path = f"logs/{current_date}.log"
    logger.remove()
    logger.add(
        logger_path,
        colorize=True,
        format=lambda record: formatter(record, clean_brackets(format_error)),
        rotation="100 MB",
    )
    logger.add(
        sys.stdout,
        colorize=True,
        format=lambda record: formatter(record, format_info),
        level="DEBUG",
    )


logging_setup()

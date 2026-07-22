import logging
import os
import sys
from datetime import datetime


def setup_logging(debug: bool = False) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    logger = logging.getLogger("BarHighLight")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(console)

    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, "barhighlight.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s.%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "BarHighLight") -> logging.Logger:
    return logging.getLogger(name)

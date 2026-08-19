from typing import TextIO

from loguru import logger


def configure_logging(debug: bool, stdout: TextIO, stderr: TextIO) -> None:
    error_level = logger.level("ERROR").no

    logger.remove()
    logger.add(
        stdout,
        level="DEBUG" if debug else "INFO",
        filter=lambda record: record["level"].no < error_level,
    )
    logger.add(stderr, level="ERROR")

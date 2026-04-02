import sys
from pathlib import Path

from loguru import logger


def init_logger(log_file: str, level: str = "INFO"):
    """
    Initializes structured JSON logs (JSON Lines) to both console and a file.
    """

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    # `serialize=True` makes each log entry a single JSON line.
    logger.add(sys.stderr, level=level, serialize=True)
    logger.add(str(log_path), level=level, serialize=True)

    return logger


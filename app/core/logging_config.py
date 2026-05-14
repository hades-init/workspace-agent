import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger.json import JsonFormatter
from app.core.config import settings


def setup_logging():
    # level = settings.LOG_LEVEL
    level = logging.INFO    # override log level for dev environment

    # # Use UTC for all log timestamps
    # logging.Formatter.converter = time.gmtime

    # ----- Root Logger -----

    formatter = logging.Formatter(
        fmt="%(asctime)-20s %(levelname)-8s %(name)s -   %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Stream handler
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    
    # File handler
    file_handler = RotatingFileHandler(
        "resources/logs/app.log", 
        maxBytes=10 * 1024 * 1024, 
        backupCount=2,
    )
    file_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)


    # ----- Agent Response Logger -----

    agent_handler = RotatingFileHandler(
        "resources/logs/agent.jsonl", 
        maxBytes=10 * 1024 * 1024, 
        backupCount=2,
    )
    json_formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )
    agent_handler.setFormatter(json_formatter)

    agent_logger = logging.getLogger("agent")
    agent_logger.addHandler(agent_handler)
    agent_logger.propagate = True


    # ----- quiet noisy third-party loggers -----

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
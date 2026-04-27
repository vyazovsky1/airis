import logging
import sys
from core.config import config

def setup_logging():
    """Configures global logging for the entire AIRIS platform."""
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    # Suppress noisy third-party loggers regardless of LOG_LEVEL
    for _noisy in ("asyncio", "httpx", "httpcore", "openai", "googleapiclient", "google"):
        logging.getLogger(_noisy).setLevel(logging.WARNING)
    
    # Ensure stdout is using UTF-8
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            # sys.stdout might not support reconfigure in some environments
            pass

def get_logger(name: str):
    """Returns a logger instance with the specified name."""
    return logging.getLogger(name)

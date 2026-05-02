import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Define log directory and file
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

def setup_logger(name: str = "assistant"):
    """Sets up a standardized logger for the application."""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Formatter for logs
    log_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # File Handler (Rotating log file, 10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    return logger

# Create a default logger instance
logger = setup_logger()

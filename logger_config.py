"""
Logging configuration module for Email AI application.
Provides centralized logging setup with datetime-stamped log files.
"""

import logging
import os
from datetime import datetime
from pathlib import Path


class LoggerConfig:
    """Centralized logger configuration for the application."""

    _logger = None
    _log_dir = Path("logs")

    @classmethod
    def get_logger(cls, name: str = "email_ai") -> logging.Logger:
        """
        Get or create a logger instance with file and console handlers.

        Args:
            name: Logger name (default: "email_ai")

        Returns:
            Configured logger instance
        """
        if cls._logger is not None:
            return cls._logger

        # Create logs directory if it doesn't exist
        cls._log_dir.mkdir(exist_ok=True)

        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)

        # Prevent duplicate handlers
        if logger.handlers:
            return logger

        # Create datetime-stamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = cls._log_dir / f"email_ai_{timestamp}.log"

        # File handler - detailed logging
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        # Console handler - important messages only
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        cls._logger = logger
        logger.info(f"Logger initialized. Log file: {log_filename}")

        return logger


def log_function_call(func):
    """
    Decorator to log function calls and exceptions.

    Usage:
        @log_function_call
        def my_function():
            pass
    """
    def wrapper(*args, **kwargs):
        logger = LoggerConfig.get_logger()
        func_name = func.__name__
        logger.info(f"Calling function: {func_name}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"Function {func_name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Function {func_name} failed with error: {str(e)}", exc_info=True)
            raise
    return wrapper

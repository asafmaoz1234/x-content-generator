import logging
import json
from datetime import datetime


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'function': record.funcName,
            'module': record.module
        }

        # Add extra fields if they exist
        if hasattr(record, 'extra_data'):
            log_record['extra_data'] = record.extra_data

        # Add exception info if it exists
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logger() -> logging.Logger:
    """Configure and return a logger with JSON formatting"""
    logger = logging.getLogger('content_generator')

    # Remove existing handlers
    logger.handlers.clear()

    # Set logging level based on environment or default to INFO
    logger.setLevel(logging.INFO)

    # Create console handler
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    return logger

# Create logger instance
logger = setup_logger()

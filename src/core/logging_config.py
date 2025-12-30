import logging
import logging.config
import os

def setup_logging(log_level=logging.INFO):
    """
    Configures logging for the application.
    """
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter", # Optional if we wanted JSON logs
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": log_level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "level": log_level,
                "filename": os.path.join(log_dir, "app.log"),
                "maxBytes": 10 * 1024 * 1024, # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
        },
        "loggers": {
            "root": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": True
            },
            "uvicorn": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "src": {  # Application specific logger
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False
            }
        }
    }

    logging.config.dictConfig(logging_config)
    logging.info("Logging configured successfully.")

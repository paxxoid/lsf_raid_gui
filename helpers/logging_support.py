import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime


from PySide6.QtWidgets import QTextBrowser, QWidget
from PySide6.QtCore import QObject, Signal


class Logger(QObject):
    gui_log_message = Signal(str)
    def __init__(
        self,
        rot_length=None,
        log_dir=None,
        log_file=None,
        console_output=False,
        debug_mode=False,
        backup_count=5,
        window=None
    ):
        super().__init__()
        if log_dir is None:
            log_dir = "log"

        if log_file is None:
            log_file = "log_file_{date}.log"

        # Replace {date} in the filename with today's date
        log_file = log_file.replace(
            "{date}",
            datetime.now().strftime("%Y-%m-%d")
        )

        self.max_bytes = rot_length * 1024 * 1024  if rot_length is not None else 5 * 1024 * 1024  # 5 MB
        self.backup_count = backup_count
        self.log_file_path = os.path.join(log_dir, log_file)
        self.console_output = console_output
        self.debug_mode = debug_mode
        self.window = window

        self.application_log = None

        for widget in self.window.findChildren(QWidget):
            if "log" in widget.objectName().lower():
                print(
                    widget.objectName(),
                    type(widget).__name__,
                )
            self.application_log = self.window.findChild(
                QTextBrowser,
                "application_log",
            )

            if self.application_log is None:
                raise RuntimeError(
                    "QTextBrowser named application_log was not found"
                )

            self.gui_log_message.connect(
                self.application_log.append
            ) 

       

    def configure_logging(self):
        log_dir = os.path.dirname(self.log_file_path)

        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)

        # Prevent duplicate log entries if configure_logging is called more than once
        for existing_handler in logger.handlers[:]:
            logger.removeHandler(existing_handler)
            existing_handler.close()

        formatter = logging.Formatter(
            "[%(asctime)s] - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        file_handler = RotatingFileHandler(
            self.log_file_path,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8"
        )

        file_handler.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if self.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    def log_to_file(self, level, messages):
        """
        Logs one message or a list/tuple of messages.

        Example:
            logger.log_to_file("INFO", "Process started")
            logger.log_to_file("ERROR", ["Error one", "Error two"])
        """

        if isinstance(messages, str):
            messages = [messages]

        if not isinstance(messages, (list, tuple)):
            messages = [str(messages)]

        level = level.upper()
        for message in messages:
            self.application_log.append(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] - [{level}] - {message}")
            match level:
                case "DEBUG":
                    logging.debug(message)

                case "INFO":
                    logging.info(message)
                case "WARNING":
                    logging.warning(message)
                case "ERROR":
                    logging.error(message)
                case "CRITICAL":
                    logging.critical(message)
                case _:
                    logging.info(
                        f"Unrecognized level: {level}. Defaulting to INFO. {message}"
                    )
        
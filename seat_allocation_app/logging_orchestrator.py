from __future__ import annotations

import logging
from dataclasses import dataclass, field


@dataclass(slots=True)
class LoggingOrchestrator:
    logger_name: str = "seat_allocation"
    logger: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(self.logger_name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

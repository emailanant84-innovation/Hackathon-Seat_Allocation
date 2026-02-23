from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    idle_zone_threshold: int = 0
    notification_timeout_seconds: float = 0.5
    stream_poll_interval_seconds: float = 0.01

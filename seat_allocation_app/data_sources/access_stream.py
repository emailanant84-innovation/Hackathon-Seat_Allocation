from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from seat_allocation_app.models import AccessEvent


class AccessControlStream:
    """Represents a live stream from building access management."""

    def __init__(self, events: list[AccessEvent] | None = None) -> None:
        self._events = events or []

    def publish(self, employee_id: str, card_id: str) -> None:
        self._events.append(
            AccessEvent(employee_id=employee_id, card_id=card_id, entered_at=datetime.utcnow())
        )

    def consume(self) -> Iterator[AccessEvent]:
        while self._events:
            yield self._events.pop(0)

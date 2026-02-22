from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


SeatStatus = Literal["available", "occupied"]


@dataclass(slots=True)
class Employee:
    employee_id: str
    card_id: str
    name: str
    email: str
    phone: str
    department: str
    team: str


@dataclass(slots=True)
class AccessEvent:
    employee_id: str
    card_id: str
    entered_at: datetime


@dataclass(slots=True)
class Seat:
    seat_id: str
    building: str
    floor: str
    zone: str
    department: str
    team_cluster: str
    status: SeatStatus = "available"
    occupied_by: str | None = None
    occupied_department: str | None = None
    occupied_team: str | None = None


@dataclass(slots=True)
class Assignment:
    employee_id: str
    seat_id: str
    building: str
    floor: str
    zone: str
    reasoning: str
    assigned_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class DeviceCommand:
    building: str
    floor: str
    zone: str
    command: Literal["POWER_ON", "POWER_OFF"]
    reason: str

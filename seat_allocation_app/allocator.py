from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from seat_allocation_app.models import Assignment, Employee, Seat


@dataclass(slots=True)
class SeatAllocator:
    """Allocates seats keeping same-team members together where possible."""

    def select_seat(self, employee: Employee, candidate_seats: list[Seat]) -> Assignment | None:
        if not candidate_seats:
            return None

        team_cluster_matches = [
            seat for seat in candidate_seats if seat.team_cluster == employee.team
        ]

        selected = (team_cluster_matches or candidate_seats)[0]
        return Assignment(
            employee_id=employee.employee_id,
            seat_id=selected.seat_id,
            building=selected.building,
            floor=selected.floor,
            zone=selected.zone,
            assigned_at=datetime.utcnow(),
        )

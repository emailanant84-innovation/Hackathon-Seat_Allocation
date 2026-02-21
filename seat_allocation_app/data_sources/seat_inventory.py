from __future__ import annotations

from collections import Counter

from seat_allocation_app.models import Seat


class SeatInventoryClient:
    def __init__(self, seats: list[Seat]) -> None:
        self._seats = {seat.seat_id: seat for seat in seats}

    def available_seats(self) -> list[Seat]:
        return [seat for seat in self._seats.values() if seat.status == "available"]

    def seats_for_department(self, department: str) -> list[Seat]:
        return [seat for seat in self._seats.values() if seat.department == department and seat.status == "available"]

    def occupied_zone_counts(self) -> Counter[tuple[str, str, str]]:
        counts: Counter[tuple[str, str, str]] = Counter()
        for seat in self._seats.values():
            if seat.status == "occupied":
                counts[(seat.building, seat.floor, seat.zone)] += 1
        return counts

    def mark_occupied(self, seat_id: str, employee_id: str, department: str, team: str) -> None:
        seat = self._seats[seat_id]
        seat.status = "occupied"
        seat.occupied_by = employee_id
        seat.occupied_department = department
        seat.occupied_team = team

    def all_seats(self) -> list[Seat]:
        return list(self._seats.values())

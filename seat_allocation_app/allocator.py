from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from seat_allocation_app.models import Assignment, Employee, Seat


@dataclass(slots=True)
class SeatAllocator:
    """Beam-search allocator with learning cache and strict team/dept locality guarantees."""

    beam_width: int = 16
    learned_location_by_team: dict[tuple[str, str], tuple[str, str, str]] = field(default_factory=dict)
    seat_success_score: dict[tuple[str, str], dict[str, int]] = field(default_factory=dict)

    def select_seat(
        self,
        employee: Employee,
        candidate_seats: list[Seat],
        all_seats: list[Seat],
    ) -> Assignment | None:
        if not candidate_seats:
            return None

        team_key = (employee.department, employee.team)
        required_location = self._required_location(team_key, all_seats)
        locality_reason = ""
        if required_location:
            candidate_seats = [
                seat
                for seat in candidate_seats
                if (seat.building, seat.floor, seat.zone) == required_location
            ]
            locality_reason = (
                f"strict locality for {employee.department}/{employee.team} -> "
                f"{required_location[0]}/{required_location[1]}/{required_location[2]}"
            )
            if not candidate_seats:
                return None

        ranked = self._beam_search_ranked_candidates(team_key, candidate_seats, all_seats)
        if not ranked:
            return None

        selected = ranked[0]
        self.learned_location_by_team[team_key] = (
            selected.building,
            selected.floor,
            selected.zone,
        )
        self.seat_success_score.setdefault(team_key, {})
        self.seat_success_score[team_key][selected.seat_id] = (
            self.seat_success_score[team_key].get(selected.seat_id, 0) + 1
        )

        reasoning = (
            "Beam search ranking: same_team > same_department > same_zone_density; "
            f"selected={selected.seat_id}; {locality_reason or 'new locality learned'}"
        )

        return Assignment(
            employee_id=employee.employee_id,
            seat_id=selected.seat_id,
            building=selected.building,
            floor=selected.floor,
            zone=selected.zone,
            reasoning=reasoning,
            assigned_at=datetime.utcnow(),
        )

    def _required_location(
        self,
        team_key: tuple[str, str],
        all_seats: list[Seat],
    ) -> tuple[str, str, str] | None:
        if team_key in self.learned_location_by_team:
            return self.learned_location_by_team[team_key]

        dept, team = team_key
        for seat in all_seats:
            if (
                seat.status == "occupied"
                and seat.department == dept
                and seat.team_cluster == team
            ):
                location = (seat.building, seat.floor, seat.zone)
                self.learned_location_by_team[team_key] = location
                return location
        return None

    def _beam_search_ranked_candidates(
        self,
        team_key: tuple[str, str],
        candidates: list[Seat],
        all_seats: list[Seat],
    ) -> list[Seat]:
        dept, team = team_key
        zone_load = self._zone_load(all_seats)
        learned_scores = self.seat_success_score.get(team_key, {})

        def score(seat: Seat) -> tuple[int, int, int, int]:
            same_team = int(seat.team_cluster == team)
            same_department = int(seat.department == dept)
            same_zone_density = zone_load.get((seat.building, seat.floor, seat.zone), 0)
            learned = learned_scores.get(seat.seat_id, 0)
            return (same_team, same_department, same_zone_density, learned)

        frontier = sorted(candidates, key=score, reverse=True)
        beam = frontier[: self.beam_width]
        if len(frontier) > self.beam_width:
            next_slice = frontier[self.beam_width : self.beam_width * 2]
            beam = sorted(beam + next_slice, key=score, reverse=True)[: self.beam_width]

        return beam

    @staticmethod
    def _zone_load(all_seats: list[Seat]) -> dict[tuple[str, str, str], int]:
        load: dict[tuple[str, str, str], int] = {}
        for seat in all_seats:
            if seat.status == "occupied":
                key = (seat.building, seat.floor, seat.zone)
                load[key] = load.get(key, 0) + 1
        return load

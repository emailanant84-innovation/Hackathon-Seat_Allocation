from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from seat_allocation_app.models import Assignment, Employee, Seat


@dataclass(slots=True)
class SeatAllocator:
    """Beam-search allocator maximizing utilization with team/department cohesion."""

    beam_width: int = 20

    def select_seat(
        self,
        employee: Employee,
        candidate_seats: list[Seat],
        all_seats: list[Seat],
    ) -> Assignment | None:
        if not candidate_seats:
            return None

        occupied = [s for s in all_seats if s.status == "occupied"]
        available = [s for s in all_seats if s.status == "available"]

        team_zone_counts = Counter()
        dept_zone_counts = Counter()
        zone_load = Counter()
        zone_departments: dict[tuple[str, str, str], set[str]] = {}

        for seat in occupied:
            zone_key = (seat.building, seat.floor, seat.zone)
            zone_load[zone_key] += 1
            zone_departments.setdefault(zone_key, set()).add(seat.department)
            if seat.department == employee.department:
                dept_zone_counts[zone_key] += 1
                if seat.team_cluster == employee.team:
                    team_zone_counts[zone_key] += 1

        team_anchor = team_zone_counts.most_common(1)[0][0] if team_zone_counts else None
        dept_anchor = dept_zone_counts.most_common(1)[0][0] if dept_zone_counts else None

        # Hard rule: keep same-department employees in the same zone when that zone still has capacity.
        dept_locked = False
        if dept_anchor:
            dept_zone_candidates = [
                seat for seat in candidate_seats if (seat.building, seat.floor, seat.zone) == dept_anchor
            ]
            if dept_zone_candidates:
                candidate_seats = dept_zone_candidates
                dept_locked = True

        # Hard rule: at most two unique departments can occupy any single zone.
        candidate_seats = [
            seat
            for seat in candidate_seats
            if len(zone_departments.get((seat.building, seat.floor, seat.zone), set()) | {employee.department}) <= 2
        ]

        if not candidate_seats:
            return None

        def base_score(seat: Seat) -> float:
            zone_key = (seat.building, seat.floor, seat.zone)
            score = 0.0

            # 1) same team together (strongest)
            if team_anchor and zone_key == team_anchor:
                score += 10_000
            score += team_zone_counts.get(zone_key, 0) * 1_200
            score += 500 if seat.team_cluster == employee.team else 0

            # 2) teams from same department together in zone
            if dept_anchor and zone_key == dept_anchor:
                score += 2_500
            score += dept_zone_counts.get(zone_key, 0) * 350
            score += 80 if seat.department == employee.department else 0

            # 3) maximize utilization by consolidating occupied zones
            score += zone_load.get(zone_key, 0) * 14

            # go to different floor/building only when required
            if team_anchor and zone_key[:2] != team_anchor[:2]:
                score -= 180
            if dept_anchor and zone_key[:2] != dept_anchor[:2]:
                score -= 75

            suffix = seat.seat_id.split("-")[-1]
            score -= (int(suffix) if suffix.isdigit() else 0) * 0.001
            return score

        def lookahead_score(seat: Seat) -> float:
            zone_key = (seat.building, seat.floor, seat.zone)
            remaining_same_team = sum(
                1
                for s in available
                if s.seat_id != seat.seat_id
                and s.team_cluster == employee.team
                and s.department == employee.department
                and (s.building, s.floor, s.zone) == zone_key
            )
            remaining_same_dept = sum(
                1
                for s in available
                if s.seat_id != seat.seat_id
                and s.department == employee.department
                and (s.building, s.floor, s.zone) == zone_key
            )
            return remaining_same_team * 120 + remaining_same_dept * 18

        frontier = sorted(candidate_seats, key=base_score, reverse=True)
        beam = frontier[: self.beam_width]

        if not beam:
            return None

        ranked_with_lookahead = sorted(
            beam,
            key=lambda seat: (base_score(seat) + lookahead_score(seat)),
            reverse=True,
        )

        selected = ranked_with_lookahead[0]
        reasoning = (
            "Beam search scoring: team_together > dept_zone_together > utilization; "
            f"selected={selected.seat_id}; team_anchor={team_anchor}; dept_anchor={dept_anchor}; "
            f"dept_zone_lock={'on' if dept_locked else 'off'}"
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

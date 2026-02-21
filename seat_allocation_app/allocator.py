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
        floor_load = Counter()
        zone_departments: dict[tuple[str, str, str], set[str]] = {}

        for seat in occupied:
            zone_key = (seat.building, seat.floor, seat.zone)
            floor_key = (seat.building, seat.floor)
            occupied_department = seat.occupied_department or seat.department
            occupied_team = seat.occupied_team or seat.team_cluster

            zone_load[zone_key] += 1
            floor_load[floor_key] += 1
            zone_departments.setdefault(zone_key, set()).add(occupied_department)

            if occupied_department == employee.department:
                dept_zone_counts[zone_key] += 1
                if occupied_team == employee.team:
                    team_zone_counts[zone_key] += 1

        team_anchor = team_zone_counts.most_common(1)[0][0] if team_zone_counts else None
        dept_anchor = dept_zone_counts.most_common(1)[0][0] if dept_zone_counts else None
        dept_zones_by_strength = [zone for zone, _count in dept_zone_counts.most_common()]

        original_candidates = list(candidate_seats)

        # Hard rule: keep same-department employees in the same zone when that zone still has capacity.
        dept_locked = False
        if dept_anchor:
            dept_zone_candidates = [
                seat for seat in candidate_seats if (seat.building, seat.floor, seat.zone) == dept_anchor
            ]
            if dept_zone_candidates:
                candidate_seats = dept_zone_candidates
                dept_locked = True

        def enforce_zone_department_cap(seats: list[Seat]) -> list[Seat]:
            return [
                seat
                for seat in seats
                if len(zone_departments.get((seat.building, seat.floor, seat.zone), set()) | {employee.department}) <= 2
            ]

        # Domain reduction pass 1: keep only zone-cap-valid candidates.
        candidate_seats = enforce_zone_department_cap(candidate_seats)

        # If dept-zone lock over-constrains domain, relax lock in a controlled way:
        # prefer other zones that already host this department before global fallback.
        lock_relaxed = False
        if not candidate_seats and dept_locked:
            cap_valid_original = enforce_zone_department_cap(original_candidates)
            prioritized_dept_zones = [
                seat
                for seat in cap_valid_original
                if (seat.building, seat.floor, seat.zone) in set(dept_zones_by_strength)
            ]
            if prioritized_dept_zones:
                candidate_seats = prioritized_dept_zones
            else:
                candidate_seats = cap_valid_original
            lock_relaxed = True

        if not candidate_seats:
            return None

        # Precompute employee-specific availability maps for fast lookahead scoring.
        available_same_team_by_zone: Counter[tuple[str, str, str]] = Counter()
        available_same_dept_by_zone: Counter[tuple[str, str, str]] = Counter()
        for seat in available:
            zone_key = (seat.building, seat.floor, seat.zone)
            if seat.department == employee.department:
                available_same_dept_by_zone[zone_key] += 1
                if seat.team_cluster == employee.team:
                    available_same_team_by_zone[zone_key] += 1

        # Domain reduction pass 2: strict floor-first, then building-first.
        floor_preferred = False
        building_preferred = False

        preferred_floor: tuple[str, str] | None = None
        if team_anchor:
            preferred_floor = (team_anchor[0], team_anchor[1])
        elif dept_anchor:
            preferred_floor = (dept_anchor[0], dept_anchor[1])
        elif floor_load:
            preferred_floor = floor_load.most_common(1)[0][0]
        else:
            preferred_floor = min((seat.building, seat.floor) for seat in candidate_seats)

        same_floor = [seat for seat in candidate_seats if (seat.building, seat.floor) == preferred_floor]
        if same_floor:
            candidate_seats = same_floor
            floor_preferred = True

        same_building = [seat for seat in candidate_seats if seat.building == preferred_floor[0]]
        if same_building:
            candidate_seats = same_building
            building_preferred = True

        def base_score(seat: Seat) -> float:
            zone_key = (seat.building, seat.floor, seat.zone)
            score = 0.0

            if team_anchor and zone_key == team_anchor:
                score += 10_000
            score += team_zone_counts.get(zone_key, 0) * 1_200
            score += 500 if seat.team_cluster == employee.team else 0

            if dept_anchor and zone_key == dept_anchor:
                score += 2_500
            score += dept_zone_counts.get(zone_key, 0) * 350
            score += 80 if seat.department == employee.department else 0

            score += zone_load.get(zone_key, 0) * 14

            if team_anchor and zone_key[:2] != team_anchor[:2]:
                score -= 180
            if dept_anchor and zone_key[:2] != dept_anchor[:2]:
                score -= 75

            suffix = seat.seat_id.split("-")[-1]
            score -= (int(suffix) if suffix.isdigit() else 0) * 0.001
            return score

        def lookahead_score(seat: Seat) -> float:
            zone_key = (seat.building, seat.floor, seat.zone)
            remaining_same_team = max(0, available_same_team_by_zone.get(zone_key, 0) - 1)
            remaining_same_dept = max(0, available_same_dept_by_zone.get(zone_key, 0) - 1)
            return remaining_same_team * 120 + remaining_same_dept * 18

        base_scores = {seat.seat_id: base_score(seat) for seat in candidate_seats}
        frontier = sorted(candidate_seats, key=lambda seat: base_scores[seat.seat_id], reverse=True)
        beam = frontier[: self.beam_width]

        if not beam:
            return None

        lookahead_scores = {seat.seat_id: lookahead_score(seat) for seat in beam}
        ranked_with_lookahead = sorted(
            beam,
            key=lambda seat: (base_scores[seat.seat_id] + lookahead_scores[seat.seat_id]),
            reverse=True,
        )

        selected = ranked_with_lookahead[0]
        reasoning = (
            "Beam search scoring: team_together > dept_zone_together > utilization; "
            f"selected={selected.seat_id}; team_anchor={team_anchor}; dept_anchor={dept_anchor}; "
            f"dept_zone_lock={'on' if dept_locked else 'off'}; "
            f"dept_zone_lock_relaxed={'yes' if lock_relaxed else 'no'}; "
            f"dept_lock_relax_mode={'dept_zone_priority' if lock_relaxed else 'n/a'}; "
            f"domain_reduction_floor_pref={'yes' if floor_preferred else 'no'}; "
            f"domain_reduction_building_pref={'yes' if building_preferred else 'no'}"
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

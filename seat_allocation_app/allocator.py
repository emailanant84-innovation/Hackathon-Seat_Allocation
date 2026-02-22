from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from seat_allocation_app.models import Assignment, Employee, Seat


@dataclass(slots=True)
class SeatAllocator:
    """Hybrid CSP + heuristic best-first (beam) allocator."""

    beam_width: int = 40

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

        zone_departments: dict[tuple[str, str, str], set[str]] = {}
        zone_load: Counter[tuple[str, str, str]] = Counter()
        floor_load: Counter[tuple[str, str]] = Counter()
        building_load: Counter[str] = Counter()

        team_zone_counts: Counter[tuple[str, str, str]] = Counter()
        dept_zone_counts: Counter[tuple[str, str, str]] = Counter()
        team_dept_zone_counts: Counter[tuple[str, str, str]] = Counter()

        team_seat_sum: Counter[tuple[str, str, str]] = Counter()
        team_seat_count: Counter[tuple[str, str, str]] = Counter()

        for seat in occupied:
            zone_key = (seat.building, seat.floor, seat.zone)
            floor_key = (seat.building, seat.floor)
            occupied_department = seat.occupied_department or seat.department
            occupied_team = seat.occupied_team or seat.team_cluster

            zone_departments.setdefault(zone_key, set()).add(occupied_department)
            zone_load[zone_key] += 1
            floor_load[floor_key] += 1
            building_load[seat.building] += 1

            if occupied_department == employee.department:
                dept_zone_counts[zone_key] += 1
            if occupied_team == employee.team:
                team_zone_counts[zone_key] += 1
            if occupied_department == employee.department and occupied_team == employee.team:
                team_dept_zone_counts[zone_key] += 1
                suffix = seat.seat_id.split("-")[-1]
                if suffix.isdigit():
                    team_seat_sum[zone_key] += int(suffix)
                    team_seat_count[zone_key] += 1

        team_dept_anchor = team_dept_zone_counts.most_common(1)[0][0] if team_dept_zone_counts else None
        team_anchor = team_zone_counts.most_common(1)[0][0] if team_zone_counts else None
        dept_anchor = dept_zone_counts.most_common(1)[0][0] if dept_zone_counts else None

        def zone_key(seat: Seat) -> tuple[str, str, str]:
            return (seat.building, seat.floor, seat.zone)

        # -------- CSP / domain reduction (hard constraints first) --------
        reduced = [
            seat
            for seat in candidate_seats
            if len(zone_departments.get(zone_key(seat), set()) | {employee.department}) <= 2
        ]

        if team_dept_anchor:
            anchored = [seat for seat in reduced if zone_key(seat) == team_dept_anchor]
            if anchored:
                reduced = anchored

        if team_anchor and (not team_dept_anchor):
            anchored = [seat for seat in reduced if zone_key(seat) == team_anchor]
            if anchored:
                reduced = anchored

        if dept_anchor and (not team_dept_anchor):
            anchored = [seat for seat in reduced if zone_key(seat) == dept_anchor]
            if anchored:
                reduced = anchored

        if not reduced:
            return None

        preferred_floor: tuple[str, str] | None = None
        if team_dept_anchor:
            preferred_floor = (team_dept_anchor[0], team_dept_anchor[1])
        elif team_anchor:
            preferred_floor = (team_anchor[0], team_anchor[1])
        elif dept_anchor:
            preferred_floor = (dept_anchor[0], dept_anchor[1])
        elif floor_load:
            preferred_floor = floor_load.most_common(1)[0][0]

        floor_reduced = reduced
        if preferred_floor:
            same_floor = [seat for seat in reduced if (seat.building, seat.floor) == preferred_floor]
            if same_floor:
                floor_reduced = same_floor

        building_reduced = floor_reduced
        if preferred_floor:
            same_building = [seat for seat in floor_reduced if seat.building == preferred_floor[0]]
            if same_building:
                building_reduced = same_building

        reduced = building_reduced

        available_same_team_by_zone: Counter[tuple[str, str, str]] = Counter()
        available_same_dept_by_zone: Counter[tuple[str, str, str]] = Counter()
        for seat in available:
            z = zone_key(seat)
            if seat.department == employee.department:
                available_same_dept_by_zone[z] += 1
                if seat.team_cluster == employee.team:
                    available_same_team_by_zone[z] += 1

        def base_score(seat: Seat) -> float:
            z = zone_key(seat)
            score = 0.0

            # Priority 1: same team+department
            if team_dept_anchor and z == team_dept_anchor:
                score += 20_000

            # Priority 2: same team
            if team_anchor and z == team_anchor:
                score += 9_000
            score += team_zone_counts.get(z, 0) * 1_100

            # Priority 3: same department
            if dept_anchor and z == dept_anchor:
                score += 8_000
            score += dept_zone_counts.get(z, 0) * 700

            # Utilization
            score += zone_load.get(z, 0) * 18
            score += floor_load.get((seat.building, seat.floor), 0) * 5
            score += building_load.get(seat.building, 0) * 2

            # Prefer staying in same floor/building when anchors exist
            if preferred_floor and (seat.building, seat.floor) != preferred_floor:
                score -= 500
            if preferred_floor and seat.building != preferred_floor[0]:
                score -= 300

            # Seat locality for existing team cluster
            suffix = seat.seat_id.split("-")[-1]
            if suffix.isdigit():
                seat_num = int(suffix)
                if team_seat_count.get(z, 0) > 0:
                    center = team_seat_sum[z] / team_seat_count[z]
                    score -= abs(seat_num - center) * 0.35
                score -= seat_num * 0.001

            return score

        def lookahead_score(seat: Seat) -> float:
            z = zone_key(seat)
            remaining_team = max(0, available_same_team_by_zone.get(z, 0) - 1)
            remaining_dept = max(0, available_same_dept_by_zone.get(z, 0) - 1)
            return remaining_team * 130 + remaining_dept * 90

        base_scores = {seat.seat_id: base_score(seat) for seat in reduced}
        frontier = sorted(reduced, key=lambda seat: base_scores[seat.seat_id], reverse=True)
        beam = frontier[: self.beam_width]
        if not beam:
            return None

        lookahead_scores = {seat.seat_id: lookahead_score(seat) for seat in beam}
        ranked = sorted(
            beam,
            key=lambda seat: (base_scores[seat.seat_id] + lookahead_scores[seat.seat_id]),
            reverse=True,
        )

        selected = ranked[0]

        # Safeguard: if dept anchor seats exist in beam and are still valid, keep anchor first.
        if dept_anchor:
            anchored = [seat for seat in ranked if zone_key(seat) == dept_anchor]
            if anchored and available_same_dept_by_zone.get(dept_anchor, 0) > 0:
                selected = anchored[0]

        reasoning = (
            "CSP+Heuristic Beam: team_dept > team > dept > utilization; "
            f"selected={selected.seat_id}; team_dept_anchor={team_dept_anchor}; "
            f"team_anchor={team_anchor}; dept_anchor={dept_anchor}; "
            f"preferred_floor={preferred_floor}; beam_width={self.beam_width}"
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

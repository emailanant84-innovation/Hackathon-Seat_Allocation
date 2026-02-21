from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from seat_allocation_app.models import Assignment, Employee, Seat


@dataclass(slots=True)
class SeatAllocator:
    """Utilization-first allocator with team/department cohesion heuristics."""

    def select_seat(
        self,
        employee: Employee,
        candidate_seats: list[Seat],
        all_seats: list[Seat],
    ) -> Assignment | None:
        if not candidate_seats:
            return None

        occupied = [seat for seat in all_seats if seat.status == "occupied"]
        occupancy_ratio = len(occupied) / len(all_seats) if all_seats else 0.0

        team_zone_counts: Counter[tuple[str, str, str]] = Counter()
        dept_zone_counts: Counter[tuple[str, str, str]] = Counter()
        zone_load: Counter[tuple[str, str, str]] = Counter()
        zone_dept_counts: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)

        for seat in occupied:
            zone_key = (seat.building, seat.floor, seat.zone)
            zone_load[zone_key] += 1
            zone_dept_counts[zone_key][seat.department] += 1
            if seat.team_cluster == employee.team and seat.department == employee.department:
                team_zone_counts[zone_key] += 1
            if seat.department == employee.department:
                dept_zone_counts[zone_key] += 1

        team_anchor = team_zone_counts.most_common(1)[0][0] if team_zone_counts else None
        dept_anchor = dept_zone_counts.most_common(1)[0][0] if dept_zone_counts else None

        best_seat = None
        best_score = None

        consolidation_weight = 8 if occupancy_ratio < 0.8 else 4

        for seat in candidate_seats:
            zone_key = (seat.building, seat.floor, seat.zone)
            same_team_zone = team_zone_counts.get(zone_key, 0)
            same_dept_zone = dept_zone_counts.get(zone_key, 0)
            zone_occupancy = zone_load.get(zone_key, 0)
            same_seat_department = int(seat.department == employee.department)

            score = 0

            # 1) same team together (highest priority)
            score += same_team_zone * 1000
            if team_anchor and zone_key == team_anchor:
                score += 5000

            # 2) teams in same department together in same zone
            score += same_dept_zone * 300
            if dept_anchor and zone_key == dept_anchor:
                score += 1500

            # Prefer zones that already host the department (while allowing mixed departments)
            if zone_dept_counts[zone_key].get(employee.department, 0) > 0:
                score += 400

            # 3) maximize utilization (consolidate occupancy)
            score += zone_occupancy * consolidation_weight

            # Prefer designated seat department if tie-ish
            score += same_seat_department * 40

            # only go to different floor/building when needed (soft penalty)
            if team_anchor and zone_key[:2] != team_anchor[:2]:
                score -= 120
            if dept_anchor and zone_key[:2] != dept_anchor[:2]:
                score -= 50

            # tiny deterministic tiebreak for stability
            suffix = seat.seat_id.split("-")[-1]
            numeric_suffix = int(suffix) if suffix.isdigit() else 0
            score += numeric_suffix * -0.001

            if best_score is None or score > best_score:
                best_score = score
                best_seat = seat

        if not best_seat:
            return None

        reasoning = (
            "Utilization-first scoring: team_together > department_zone_together > "
            "zone_consolidation; selected="
            f"{best_seat.seat_id}; occupancy_ratio={occupancy_ratio:.2f}; "
            f"team_anchor={team_anchor}; dept_anchor={dept_anchor}"
        )

        return Assignment(
            employee_id=employee.employee_id,
            seat_id=best_seat.seat_id,
            building=best_seat.building,
            floor=best_seat.floor,
            zone=best_seat.zone,
            reasoning=reasoning,
            assigned_at=datetime.utcnow(),
        )

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from seat_allocation_app.models import Assignment, Employee, Seat


@dataclass(slots=True)
class SeatAllocator:
    """Beam-search allocator maximizing utilization with team/department cohesion."""

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

        original_candidates = list(candidate_seats)

        # Prefer same-department employees in the same zone when that zone still has capacity.
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

        # Controlled fallback: if lock emptied domain, re-open cap-valid original domain.
        lock_relaxed = False
        if not candidate_seats and dept_locked:
            candidate_seats = enforce_zone_department_cap(original_candidates)
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

        team_suffix_totals_by_zone: Counter[tuple[str, str, str]] = Counter()
        team_suffix_counts_by_zone: Counter[tuple[str, str, str]] = Counter()
        team_max_suffix_by_zone: dict[tuple[str, str, str], int] = {}
        dept_team_counts_by_zone: dict[tuple[str, str, str], Counter[str]] = {}
        zone_dept_min_suffix: dict[tuple[str, str, str], dict[str, int]] = {}
        for seat in occupied:
            zone_key = (seat.building, seat.floor, seat.zone)
            occupied_department = seat.occupied_department or seat.department
            occupied_team = seat.occupied_team or seat.team_cluster
            if occupied_department == employee.department:
                dept_team_counts_by_zone.setdefault(zone_key, Counter())[occupied_team] += 1

            suffix = seat.seat_id.split("-")[-1]
            if suffix.isdigit():
                seat_num = int(suffix)
                current_min = zone_dept_min_suffix.setdefault(zone_key, {}).get(occupied_department)
                if current_min is None or seat_num < current_min:
                    zone_dept_min_suffix[zone_key][occupied_department] = seat_num

            if occupied_department != employee.department or occupied_team != employee.team:
                continue
            if suffix.isdigit():
                seat_num = int(suffix)
                team_suffix_totals_by_zone[zone_key] += seat_num
                team_suffix_counts_by_zone[zone_key] += 1
                team_max_suffix_by_zone[zone_key] = max(team_max_suffix_by_zone.get(zone_key, 0), seat_num)

        # Domain reduction pass 2: strict floor-first, then building-first.
        floor_preferred = False
        building_preferred = False

        preferred_floor: tuple[str, str] | None = None
        if dept_locked and dept_anchor:
            preferred_floor = (dept_anchor[0], dept_anchor[1])
        elif team_anchor:
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

        def preferred_department_slot(zone_key: tuple[str, str, str]) -> int | None:
            current_depts = zone_departments.get(zone_key, set())
            if not current_depts:
                return 0

            dept_min = zone_dept_min_suffix.get(zone_key, {})
            if employee.department in current_depts:
                employee_min = dept_min.get(employee.department, 1)
                return 0 if employee_min <= 50 else 1

            if len(current_depts) >= 2:
                return None

            existing_dept = next(iter(current_depts))
            existing_min = dept_min.get(existing_dept, 1)
            return 1 if existing_min <= 50 else 0

        def preferred_team_section(seat: Seat) -> tuple[int, int] | None:
            z = (seat.building, seat.floor, seat.zone)
            dept_slot = preferred_department_slot(z)
            if dept_slot is None:
                return None

            if dept_slot == 0:
                section_ranges = [(1, 25), (26, 50)]
            else:
                section_ranges = [(51, 75), (76, 100)]

            dept_team_counts = dept_team_counts_by_zone.get(z, Counter())
            ordered_teams = [team for team, _count in dept_team_counts.most_common() if team]
            if employee.team in ordered_teams:
                team_slot = ordered_teams.index(employee.team) % 2
            else:
                team_slot = len(ordered_teams) % 2

            return section_ranges[team_slot]

        def base_score(seat: Seat) -> float:
            zone_key = (seat.building, seat.floor, seat.zone)
            score = 0.0

            if team_anchor and zone_key == team_anchor:
                score += 10_000
            score += team_zone_counts.get(zone_key, 0) * 1_200
            score += 500 if seat.team_cluster == employee.team else 0

            if dept_anchor and zone_key == dept_anchor:
                score += 8_500
            score += dept_zone_counts.get(zone_key, 0) * 600
            score += 80 if seat.department == employee.department else 0

            score += zone_load.get(zone_key, 0) * 450
            score += len(zone_departments.get(zone_key, set())) * 700

            if team_anchor and zone_key[:2] != team_anchor[:2]:
                score -= 180
            if dept_anchor and zone_key[:2] != dept_anchor[:2]:
                score -= 220
            if dept_anchor and zone_key != dept_anchor and available_same_dept_by_zone.get(dept_anchor, 0) > 0:
                score -= 3_500

            suffix = seat.seat_id.split("-")[-1]
            if suffix.isdigit():
                seat_num = int(suffix)

                section = preferred_team_section(seat)
                if section and section[0] <= seat_num <= section[1]:
                    score += 300

                dept_slot = preferred_department_slot(zone_key)
                if dept_slot is not None:
                    dept_half = (1, 50) if dept_slot == 0 else (51, 100)
                    if dept_half[0] <= seat_num <= dept_half[1]:
                        score += 700

                team_count = team_suffix_counts_by_zone.get(zone_key, 0)
                if team_count:
                    team_center = team_suffix_totals_by_zone[zone_key] / team_count
                    score -= abs(seat_num - team_center) * 0.25

                if team_suffix_counts_by_zone.get(zone_key, 0) > 0:
                    next_for_team = team_max_suffix_by_zone.get(zone_key, 0) + 1
                    if next_for_team == seat_num:
                        score += 2_600

                score -= seat_num * 0.001
            return score

        def lookahead_score(seat: Seat) -> float:
            zone_key = (seat.building, seat.floor, seat.zone)
            remaining_same_team = max(0, available_same_team_by_zone.get(zone_key, 0) - 1)
            remaining_same_dept = max(0, available_same_dept_by_zone.get(zone_key, 0) - 1)
            return remaining_same_team * 100 + remaining_same_dept * 65

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
        if dept_anchor:
            anchored = [s for s in ranked_with_lookahead if (s.building, s.floor, s.zone) == dept_anchor]
            if anchored and available_same_dept_by_zone.get(dept_anchor, 0) > 0:
                selected = anchored[0]
        reasoning = (
            "Beam search scoring: team_together > dept_zone_together > utilization; "
            f"selected={selected.seat_id}; team_anchor={team_anchor}; dept_anchor={dept_anchor}; "
            f"dept_zone_lock={'on' if dept_locked else 'off'}; "
            f"dept_zone_lock_relaxed={'yes' if lock_relaxed else 'no'}; "
            f"dept_lock_relax_mode={'cap_valid_fallback' if lock_relaxed else 'n/a'}; "
            f"domain_reduction_floor_pref={'yes' if floor_preferred else 'no'}; "
            f"domain_reduction_building_pref={'yes' if building_preferred else 'no'}; "
            "section_heuristic=on"
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

from __future__ import annotations

import random
from datetime import datetime

from seat_allocation_app.models import AccessEvent, Employee, Seat


def all_departments() -> list[str]:
    return [f"Department-{index:02d}" for index in range(1, 11)]


def all_teams() -> list[str]:
    return [f"Team-{index:03d}" for index in range(1, 26)]


def team_department_map() -> dict[str, str]:
    departments = all_departments()
    return {
        team: departments[idx % len(departments)]
        for idx, team in enumerate(all_teams())
    }


def build_seat_topology() -> list[Seat]:
    seats: list[Seat] = []
    teams = all_teams()
    team_dept = team_department_map()

    for building in range(1, 3):
        for floor in range(1, 3):
            for zone in ("A", "B", "C"):
                for number in range(1, 61):
                    team = teams[(number - 1 + (building - 1) * 5 + (floor - 1) * 3 + (ord(zone) - 65)) % len(teams)]
                    seats.append(
                        Seat(
                            seat_id=f"S-B{building}-F{floor}-{zone}-{number:03d}",
                            building=f"B{building}",
                            floor=f"F{floor}",
                            zone=zone,
                            department=team_dept[team],
                            team_cluster=team,
                        )
                    )
    return seats


def build_employee_directory(
    total_employees: int = 300,
    active_departments: int = 10,
    active_teams: int = 25,
    seed: int | None = None,
) -> list[Employee]:
    rng = random.Random(seed)
    team_dept = team_department_map()

    selected_departments = set(rng.sample(all_departments(), k=active_departments))
    eligible_teams = [team for team, dept in team_dept.items() if dept in selected_departments]
    selected_teams = rng.sample(eligible_teams, k=min(active_teams, len(eligible_teams)))

    employees: list[Employee] = []
    for i in range(1, total_employees + 1):
        employee_id = f"E{i:04d}"
        team = selected_teams[(i - 1) % len(selected_teams)]
        department = team_dept[team]
        employees.append(
            Employee(
                employee_id=employee_id,
                card_id=f"CARD-{employee_id}",
                name=f"Employee {i}",
                email=f"employee{i}@corp.com",
                phone=f"+1202555{i:04d}",
                department=department,
                team=team,
            )
        )
    return employees


def create_access_event(employee_id: str, card_id: str) -> AccessEvent:
    return AccessEvent(employee_id=employee_id, card_id=card_id, entered_at=datetime.utcnow())

from __future__ import annotations

import random
from datetime import datetime

from seat_allocation_app.models import AccessEvent, Employee, Seat


def _clone_seat(seat: Seat) -> Seat:
    return Seat(
        seat_id=seat.seat_id,
        building=seat.building,
        floor=seat.floor,
        zone=seat.zone,
        department=seat.department,
        team_cluster=seat.team_cluster,
        status=seat.status,
        occupied_by=seat.occupied_by,
        occupied_department=seat.occupied_department,
        occupied_team=seat.occupied_team,
    )


def _clone_employee(employee: Employee) -> Employee:
    return Employee(
        employee_id=employee.employee_id,
        card_id=employee.card_id,
        name=employee.name,
        email=employee.email,
        phone=employee.phone,
        department=employee.department,
        team=employee.team,
    )


# Pre-created simulation tables (single build, reused at runtime).
DEPARTMENTS_TABLE: list[str] = [f"Department-{index:02d}" for index in range(1, 11)]
TEAMS_TABLE: list[str] = [f"Team-{index:03d}" for index in range(1, 26)]
TEAM_DEPARTMENT_TABLE: dict[str, str] = {
    team: DEPARTMENTS_TABLE[idx % len(DEPARTMENTS_TABLE)]
    for idx, team in enumerate(TEAMS_TABLE)
}


def _build_seat_table() -> list[Seat]:
    seats: list[Seat] = []
    for building in range(1, 3):
        for floor in range(1, 3):
            for zone in ("A", "B", "C"):
                for number in range(1, 61):
                    team = TEAMS_TABLE[
                        (number - 1 + (building - 1) * 5 + (floor - 1) * 3 + (ord(zone) - 65))
                        % len(TEAMS_TABLE)
                    ]
                    seats.append(
                        Seat(
                            seat_id=f"S-B{building}-F{floor}-{zone}-{number:03d}",
                            building=f"B{building}",
                            floor=f"F{floor}",
                            zone=zone,
                            department=TEAM_DEPARTMENT_TABLE[team],
                            team_cluster=team,
                        )
                    )
    return seats


def _build_employee_table(
    total_employees: int = 300,
    active_departments: int = 10,
    active_teams: int = 25,
    seed: int = 42,
) -> list[Employee]:
    rng = random.Random(seed)

    selected_departments = set(rng.sample(DEPARTMENTS_TABLE, k=active_departments))
    eligible_teams = [team for team, dept in TEAM_DEPARTMENT_TABLE.items() if dept in selected_departments]
    selected_teams = rng.sample(eligible_teams, k=min(active_teams, len(eligible_teams)))

    employees: list[Employee] = []
    for i in range(1, total_employees + 1):
        employee_id = f"E{i:04d}"
        team = selected_teams[(i - 1) % len(selected_teams)]
        department = TEAM_DEPARTMENT_TABLE[team]
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


SEATS_TABLE: list[Seat] = _build_seat_table()
EMPLOYEES_TABLE: list[Employee] = _build_employee_table()


def all_departments() -> list[str]:
    return list(DEPARTMENTS_TABLE)


def all_teams() -> list[str]:
    return list(TEAMS_TABLE)


def team_department_map() -> dict[str, str]:
    return dict(TEAM_DEPARTMENT_TABLE)


def build_seat_topology() -> list[Seat]:
    return [_clone_seat(seat) for seat in SEATS_TABLE]


def build_employee_directory(
    total_employees: int = 300,
    active_departments: int = 10,
    active_teams: int = 25,
    seed: int | None = None,
) -> list[Employee]:
    if (
        total_employees == 300
        and active_departments == 10
        and active_teams == 25
        and seed is None
    ):
        return [_clone_employee(employee) for employee in EMPLOYEES_TABLE]

    resolved_seed = 42 if seed is None else seed
    return _build_employee_table(
        total_employees=total_employees,
        active_departments=active_departments,
        active_teams=active_teams,
        seed=resolved_seed,
    )


def create_access_event(employee_id: str, card_id: str) -> AccessEvent:
    return AccessEvent(employee_id=employee_id, card_id=card_id, entered_at=datetime.utcnow())


def random_employee_event(employees: list[Employee], rng: random.Random | None = None) -> AccessEvent:
    chooser = rng or random
    employee = chooser.choice(employees)
    return create_access_event(employee.employee_id, employee.card_id)

from __future__ import annotations

from datetime import datetime

from seat_allocation_app.models import AccessEvent, Employee, Seat


def _departments() -> list[str]:
    return [f"Department-{index:02d}" for index in range(1, 21)]


def _teams() -> list[str]:
    return [f"Team-{index:03d}" for index in range(1, 101)]


def build_seat_topology() -> list[Seat]:
    seats: list[Seat] = []
    departments = _departments()
    teams = _teams()

    for building in range(1, 3):
        for floor in range(1, 6):
            for zone in ("A", "B"):
                for number in range(1, 101):
                    department = departments[((building - 1) * 10 + (floor - 1) * 2 + (0 if zone == "A" else 1)) % len(departments)]
                    team = teams[(number - 1) % len(teams)]
                    seats.append(
                        Seat(
                            seat_id=f"S-B{building}-F{floor}-{zone}-{number:03d}",
                            building=f"B{building}",
                            floor=f"F{floor}",
                            zone=zone,
                            department=department,
                            team_cluster=team,
                        )
                    )
    return seats


def build_employee_directory(total_employees: int = 2500) -> list[Employee]:
    departments = _departments()
    teams = _teams()

    employees: list[Employee] = []
    for i in range(1, total_employees + 1):
        employee_id = f"E{i:04d}"
        employees.append(
            Employee(
                employee_id=employee_id,
                card_id=f"CARD-{employee_id}",
                name=f"Employee {i}",
                email=f"employee{i}@corp.com",
                phone=f"+1202555{i:04d}",
                department=departments[(i - 1) % len(departments)],
                team=teams[(i - 1) % len(teams)],
            )
        )
    return employees


def create_access_event(employee_id: str, card_id: str) -> AccessEvent:
    return AccessEvent(employee_id=employee_id, card_id=card_id, entered_at=datetime.utcnow())

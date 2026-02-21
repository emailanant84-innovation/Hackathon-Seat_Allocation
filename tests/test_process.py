from __future__ import annotations

from datetime import datetime

from seat_allocation_app.allocator import SeatAllocator
from seat_allocation_app.data_sources.access_stream import AccessControlStream
from seat_allocation_app.data_sources.employee_directory import EmployeeDirectoryClient
from seat_allocation_app.data_sources.seat_inventory import SeatInventoryClient
from seat_allocation_app.device_usage import summarize_device_usage
from seat_allocation_app.energy_optimizer import EnergyOptimizer
from seat_allocation_app.iot_client import IoTDeviceClient
from seat_allocation_app.logging_orchestrator import LoggingOrchestrator
from seat_allocation_app.models import AccessEvent, Employee, Seat
from seat_allocation_app.notifications.email_client import EmailNotifier
from seat_allocation_app.notifications.message_client import MessageNotifier
from seat_allocation_app.process_orchestrator import ProcessOrchestrator
from seat_allocation_app.simulation import (
    all_departments,
    all_teams,
    build_employee_directory,
    build_seat_topology,
    team_department_map,
)


def test_orchestrator_assigns_and_notifies() -> None:
    orchestrator = ProcessOrchestrator(
        access_stream=AccessControlStream(
            [
                AccessEvent("E1", "C1", datetime.utcnow()),
                AccessEvent("E2", "C2", datetime.utcnow()),
            ]
        ),
        employee_directory=EmployeeDirectoryClient(
            [
                Employee("E1", "CARD-E1", "Alex", "alex@example.com", "+111", "Engineering", "Platform"),
                Employee("E2", "CARD-E2", "Blair", "blair@example.com", "+222", "Engineering", "Data"),
            ]
        ),
        seat_inventory=SeatInventoryClient(
            [
                Seat("S1", "B1", "F1", "A", "Engineering", "Platform"),
                Seat("S2", "B1", "F1", "A", "Engineering", "Data"),
            ]
        ),
        seat_allocator=SeatAllocator(),
        energy_optimizer=EnergyOptimizer(),
        iot_client=IoTDeviceClient(),
        email_notifier=EmailNotifier(),
        message_notifier=MessageNotifier(),
        logger=LoggingOrchestrator("test_logger"),
    )

    assignments = orchestrator.run_once()

    occupied = {seat.seat_id: seat.occupied_by for seat in orchestrator.seat_inventory.all_seats()}
    assert occupied["S1"] == "E1"
    assert occupied["S2"] == "E2"
    assert assignments[0].building == "B1"
    assert "Beam search scoring" in assignments[0].reasoning
    assert len(orchestrator.email_notifier.sent_messages) == 2
    assert len(orchestrator.message_notifier.sent_messages) == 2


def test_same_team_prefers_same_zone() -> None:
    allocator = SeatAllocator()
    employee = Employee("E2", "CARD-E2", "Pat", "p@x", "+2", "Dept-A", "Team-X")

    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-X", status="occupied", occupied_by="E1"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Dept-A", "Team-X"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-A", "Team-X"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[1], all_seats[2]], all_seats)
    assert assignment is not None
    assert assignment.zone == "A"


def test_department_teams_cluster_in_zone() -> None:
    allocator = SeatAllocator()
    employee = Employee("E3", "CARD-E3", "Sam", "s@x", "+3", "Dept-A", "Team-Y")

    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-Z", status="occupied", occupied_by="E1"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Dept-A", "Team-Y"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-A", "Team-Y"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[1], all_seats[2]], all_seats)
    assert assignment is not None
    assert assignment.zone == "A"


def test_simulation_topology_and_team_department_connection() -> None:
    seats = build_seat_topology()
    employees = build_employee_directory(seed=42)
    mapping = team_department_map()

    assert len(seats) == 720
    assert len({seat.department for seat in seats}) == 10
    assert len({seat.team_cluster for seat in seats}) == 25

    assert len(all_departments()) == 10
    assert len(all_teams()) == 25

    # connection between team and department is consistent in both seats and employees
    for seat in seats[:100]:
        assert mapping[seat.team_cluster] == seat.department
    for employee in employees[:100]:
        assert mapping[employee.team] == employee.department

    assert len(employees) == 300
    assert len({employee.department for employee in employees}) == 10
    assert len({employee.team for employee in employees}) == 25


def test_device_usage_summary_calculation() -> None:
    seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Engineering", "Platform", status="occupied", occupied_by="E1"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Engineering", "Platform", status="occupied", occupied_by="E2"),
        Seat("S-B1-F1-A-003", "B1", "F1", "A", "Engineering", "Platform"),
    ]

    rows = summarize_device_usage(seats)
    row = next(item for item in rows if (item.building, item.floor, item.zone) == ("B1", "F1", "A"))
    assert row.occupied_seats == 2
    assert row.lights_on == 1
    assert row.routers_on == 1
    assert row.monitors_on == 2
    assert row.desktop_cpus_on == 2
    assert row.ac_vents_on == 1

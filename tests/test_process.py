from __future__ import annotations

from datetime import datetime

from seat_allocation_app.allocator import SeatAllocator
from seat_allocation_app.data_sources.access_stream import AccessControlStream
from seat_allocation_app.data_sources.employee_directory import EmployeeDirectoryClient
from seat_allocation_app.data_sources.seat_inventory import SeatInventoryClient
from seat_allocation_app.device_usage import summarize_device_usage
from seat_allocation_app.energy_optimizer import EnergyOptimizer
from seat_allocation_app.gui_orchestrator import GUIOrchestrator
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
    random_employee_event,
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




def test_same_department_stays_same_zone_when_capacity_exists() -> None:
    allocator = SeatAllocator()
    employee = Employee("E4", "CARD-E4", "Jo", "j@x", "+4", "Dept-A", "Team-Q")

    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-Z", status="occupied", occupied_by="E1"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Dept-A", "Team-Q"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-A", "Team-Q"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[1], all_seats[2]], all_seats)
    assert assignment is not None
    assert assignment.zone == "A"



def test_zone_rejects_third_department() -> None:
    allocator = SeatAllocator()
    employee = Employee("E9", "CARD-E9", "Kai", "k@x", "+9", "Dept-C", "Team-C1")

    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-A1", status="occupied", occupied_by="E1"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Dept-B", "Team-B1", status="occupied", occupied_by="E2"),
        Seat("S-B1-F1-A-003", "B1", "F1", "A", "Dept-C", "Team-C1"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-C", "Team-C1"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[2], all_seats[3]], all_seats)
    assert assignment is not None
    assert assignment.zone == "B"


def test_zone_allows_second_department() -> None:
    allocator = SeatAllocator()
    employee = Employee("E10", "CARD-E10", "Lee", "l@x", "+10", "Dept-B", "Team-B1")

    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-A1", status="occupied", occupied_by="E1"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Dept-B", "Team-B1"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-B", "Team-B1"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[1], all_seats[2]], all_seats)
    assert assignment is not None
    assert assignment.zone == "A"



def test_dept_lock_relaxes_when_anchor_zone_is_cap_blocked() -> None:
    allocator = SeatAllocator()
    employee = Employee("E11", "CARD-E11", "Mia", "m@x", "+11", "Dept-A", "Team-A2")

    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-A1", status="occupied", occupied_by="E1"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Dept-B", "Team-B1", status="occupied", occupied_by="E2"),
        Seat("S-B1-F1-A-003", "B1", "F1", "A", "Dept-C", "Team-C1", status="occupied", occupied_by="E3"),
        Seat("S-B1-F1-A-004", "B1", "F1", "A", "Dept-A", "Team-A2"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-A", "Team-A2"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[3], all_seats[4]], all_seats)
    assert assignment is not None
    assert assignment.zone == "B"


def test_prefers_same_floor_before_other_floor_or_building() -> None:
    allocator = SeatAllocator()
    employee = Employee("E12", "CARD-E12", "Noa", "n@x", "+12", "Dept-A", "Team-A1")

    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-A1", status="occupied", occupied_by="E1"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-A", "Team-A1"),
        Seat("S-B1-F2-A-001", "B1", "F2", "A", "Dept-A", "Team-A1"),
        Seat("S-B2-F1-A-001", "B2", "F1", "A", "Dept-A", "Team-A1"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[1], all_seats[2], all_seats[3]], all_seats)
    assert assignment is not None
    assert assignment.building == "B1"
    assert assignment.floor == "F1"



def test_zone_cap_uses_actual_occupied_department_not_seat_template() -> None:
    allocator = SeatAllocator()
    employee = Employee("E13", "CARD-E13", "Ira", "i@x", "+13", "Dept-C", "Team-C2")

    all_seats = [
        Seat(
            "S-B1-F1-A-001",
            "B1",
            "F1",
            "A",
            "Dept-A",
            "Team-A1",
            status="occupied",
            occupied_by="E1",
            occupied_department="Dept-A",
            occupied_team="Team-A1",
        ),
        Seat(
            "S-B1-F1-A-002",
            "B1",
            "F1",
            "A",
            "Dept-A",
            "Team-A1",
            status="occupied",
            occupied_by="E2",
            occupied_department="Dept-B",
            occupied_team="Team-B2",
        ),
        Seat("S-B1-F1-A-003", "B1", "F1", "A", "Dept-A", "Team-A1"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-C", "Team-C2"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[2], all_seats[3]], all_seats)
    assert assignment is not None
    assert assignment.zone == "B"


def test_floor_preference_follows_current_occupied_floor_when_no_anchor() -> None:
    allocator = SeatAllocator()
    employee = Employee("E14", "CARD-E14", "Uma", "u@x", "+14", "Dept-X", "Team-X1")

    all_seats = [
        Seat("S-B2-F2-A-001", "B2", "F2", "A", "Dept-A", "Team-A1", status="occupied", occupied_by="E1"),
        Seat("S-B2-F2-A-002", "B2", "F2", "A", "Dept-X", "Team-X1"),
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-X", "Team-X1"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[1], all_seats[2]], all_seats)
    assert assignment is not None
    assert assignment.building == "B2"
    assert assignment.floor == "F2"



def test_relaxed_dept_lock_falls_back_to_other_valid_dept_zone() -> None:
    allocator = SeatAllocator()
    employee = Employee("E15", "CARD-E15", "Rin", "r@x", "+15", "Dept-A", "Team-A9")

    all_seats = [
        # Strongest department anchor zone A, but it already has Dept-B and Dept-C -> invalid for Dept-A under cap.
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-A1", status="occupied", occupied_by="E1", occupied_department="Dept-A", occupied_team="Team-A1"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Dept-A", "Team-A1", status="occupied", occupied_by="E2", occupied_department="Dept-B", occupied_team="Team-B1"),
        Seat("S-B1-F1-A-003", "B1", "F1", "A", "Dept-A", "Team-A1", status="occupied", occupied_by="E3", occupied_department="Dept-C", occupied_team="Team-C1"),
        # Another Dept-A zone exists and should be used as fallback.
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-A", "Team-A2", status="occupied", occupied_by="E4", occupied_department="Dept-A", occupied_team="Team-A2"),
        # Candidates
        Seat("S-B1-F1-A-010", "B1", "F1", "A", "Dept-A", "Team-A9"),
        Seat("S-B1-F1-B-010", "B1", "F1", "B", "Dept-A", "Team-A9"),
        Seat("S-B2-F2-B-010", "B2", "F2", "B", "Dept-A", "Team-A9"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[4], all_seats[5], all_seats[6]], all_seats)
    assert assignment is not None
    assert assignment.zone == "B"
    assert assignment.building == "B1"
    assert assignment.floor == "F1"



def test_run_once_orders_each_batch_of_two_by_department_team() -> None:
    first = datetime.utcnow()
    second = datetime.utcnow()

    orchestrator = ProcessOrchestrator(
        access_stream=AccessControlStream([AccessEvent("E2", "C2", first), AccessEvent("E1", "C1", second)]),
        employee_directory=EmployeeDirectoryClient(
            [
                Employee("E1", "CARD-E1", "Alex", "alex@example.com", "+111", "Dept-A", "Team-A"),
                Employee("E2", "CARD-E2", "Blair", "blair@example.com", "+222", "Dept-B", "Team-B"),
            ]
        ),
        seat_inventory=SeatInventoryClient(
            [
                Seat("S1", "B1", "F1", "A", "Dept-A", "Team-A"),
                Seat("S2", "B1", "F1", "A", "Dept-B", "Team-B"),
            ]
        ),
        seat_allocator=SeatAllocator(),
        energy_optimizer=EnergyOptimizer(),
        iot_client=IoTDeviceClient(),
        email_notifier=EmailNotifier(),
        message_notifier=MessageNotifier(),
        logger=LoggingOrchestrator("batch_order_test"),
    )

    ordered = orchestrator._order_batch([AccessEvent("E2", "C2", first), AccessEvent("E1", "C1", second)])
    assert [event.employee_id for event in ordered] == ["E1", "E2"]


def test_same_team_prefers_nearby_seat_numbers_within_zone() -> None:
    allocator = SeatAllocator()
    employee = Employee("E16", "CARD-E16", "Tao", "t@x", "+16", "Dept-A", "Team-X")

    all_seats = [
        Seat(
            "S-B1-F1-A-049",
            "B1",
            "F1",
            "A",
            "Dept-A",
            "Team-X",
            status="occupied",
            occupied_by="E1",
            occupied_department="Dept-A",
            occupied_team="Team-X",
        ),
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-X"),
        Seat("S-B1-F1-A-050", "B1", "F1", "A", "Dept-A", "Team-X"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[1], all_seats[2]], all_seats)
    assert assignment is not None
    assert assignment.seat_id == "S-B1-F1-A-050"





def test_prefers_anchor_zone_when_anchor_seats_still_available() -> None:
    allocator = SeatAllocator()
    employee = Employee("E30", "CARD-E30", "Ana", "a@x", "+30", "Dept-A", "Team-Q")

    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-Z", status="occupied", occupied_by="E1", occupied_department="Dept-A", occupied_team="Team-Z"),
        Seat("S-B1-F1-A-002", "B1", "F1", "A", "Dept-A", "Team-Q"),
        Seat("S-B1-F1-B-001", "B1", "F1", "B", "Dept-A", "Team-Q"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[1], all_seats[2]], all_seats)
    assert assignment is not None
    assert assignment.zone == "A"





def test_section_heuristic_same_department_next_team_moves_to_next_quarter() -> None:
    allocator = SeatAllocator()

    employee = Employee("E40", "CARD-E40", "A", "a@x", "+40", "Dept-A", "Team-02")
    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-01", status="occupied", occupied_by="E1", occupied_department="Dept-A", occupied_team="Team-01"),
        Seat("S-B1-F1-A-005", "B1", "F1", "A", "Dept-A", "Team-01", status="occupied", occupied_by="E2", occupied_department="Dept-A", occupied_team="Team-01"),
        Seat("S-B1-F1-A-010", "B1", "F1", "A", "Dept-A", "Team-02"),
        Seat("S-B1-F1-A-030", "B1", "F1", "A", "Dept-A", "Team-02"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[2], all_seats[3]], all_seats)
    assert assignment is not None
    assert assignment.seat_id == "S-B1-F1-A-030"


def test_section_heuristic_second_department_prefers_51_to_75_range() -> None:
    allocator = SeatAllocator()

    employee = Employee("E41", "CARD-E41", "B", "b@x", "+41", "Dept-B", "Team-10")
    all_seats = [
        Seat("S-B1-F1-A-001", "B1", "F1", "A", "Dept-A", "Team-01", status="occupied", occupied_by="E1", occupied_department="Dept-A", occupied_team="Team-01"),
        Seat("S-B1-F1-A-020", "B1", "F1", "A", "Dept-A", "Team-01", status="occupied", occupied_by="E2", occupied_department="Dept-A", occupied_team="Team-01"),
        Seat("S-B1-F1-A-055", "B1", "F1", "A", "Dept-B", "Team-10"),
        Seat("S-B1-F1-A-078", "B1", "F1", "A", "Dept-B", "Team-10"),
    ]

    assignment = allocator.select_seat(employee, [all_seats[2], all_seats[3]], all_seats)
    assert assignment is not None
    assert assignment.seat_id == "S-B1-F1-A-055"

def test_simulation_uses_precreated_tables_for_defaults() -> None:
    employees_first = build_employee_directory()
    employees_second = build_employee_directory()
    assert len(employees_first) == 300
    assert len(employees_second) == 300
    assert employees_first[0].employee_id == employees_second[0].employee_id
    assert employees_first[0] is not employees_second[0]

    seats_first = build_seat_topology()
    seats_second = build_seat_topology()
    assert len(seats_first) == 800
    assert len(seats_second) == 800
    assert seats_first[0].seat_id == seats_second[0].seat_id
    assert seats_first[0] is not seats_second[0]


def test_random_employee_event_picks_from_existing_directory() -> None:
    employees = build_employee_directory()
    event = random_employee_event(employees)
    assert any(employee.employee_id == event.employee_id for employee in employees)

def test_simulation_topology_and_team_department_connection() -> None:
    seats = build_seat_topology()
    employees = build_employee_directory(seed=42)
    mapping = team_department_map()

    assert len(seats) == 800
    assert len({seat.department for seat in seats}) == 8
    assert len({seat.team_cluster for seat in seats}) == 20

    assert len(all_departments()) == 8
    assert len(all_teams()) == 20

    # connection between team and department is consistent in both seats and employees
    for seat in seats[:100]:
        assert mapping[seat.team_cluster] == seat.department
    for employee in employees[:100]:
        assert mapping[employee.team] == employee.department

    assert len(employees) == 300
    assert len({employee.department for employee in employees}) == 8
    assert len({employee.team for employee in employees}) == 20




def test_simulation_100_events_no_misassignment() -> None:
    import random
    from collections import defaultdict

    rng = random.Random(42)
    employees = build_employee_directory()

    orchestrator = ProcessOrchestrator(
        access_stream=AccessControlStream([]),
        employee_directory=EmployeeDirectoryClient(employees),
        seat_inventory=SeatInventoryClient(build_seat_topology()),
        seat_allocator=SeatAllocator(),
        energy_optimizer=EnergyOptimizer(),
        iot_client=IoTDeviceClient(),
        email_notifier=EmailNotifier(),
        message_notifier=MessageNotifier(),
        logger=LoggingOrchestrator("sim_100_test"),
    )

    for _ in range(100):
        event = random_employee_event(employees, rng=rng)
        orchestrator.access_stream.publish(event.employee_id, event.card_id)

    assignments = orchestrator.run_once()
    assert len(assignments) == 100

    occupied = [seat for seat in orchestrator.seat_inventory.all_seats() if seat.status == "occupied"]

    team_locs = defaultdict(set)
    dept_locs = defaultdict(set)
    zone_depts = defaultdict(set)

    for seat in occupied:
        department = seat.occupied_department or seat.department
        team = seat.occupied_team or seat.team_cluster
        loc = (seat.building, seat.floor, seat.zone)
        team_locs[(department, team)].add(loc)
        dept_locs[department].add(loc)
        zone_depts[loc].add(department)

    assert all(len(locations) == 1 for locations in team_locs.values())
    assert all(len(locations) == 1 for locations in dept_locs.values())
    assert all(len(departments) <= 2 for departments in zone_depts.values())



def test_gui_color_uses_occupied_department_when_present() -> None:
    seat = Seat(
        "S-B1-F1-A-001",
        "B1",
        "F1",
        "A",
        "Department-01",
        "Team-001",
        status="occupied",
        occupied_by="E1",
        occupied_department="Department-02",
    )
    assert GUIOrchestrator._seat_display_department(seat) == "Department-02"



def test_power_saving_percent_calculation() -> None:
    rows = [
        type("Row", (), {
            "building": "B1",
            "floor": "F1",
            "zone": "A",
            "lights_on": 5,
            "routers_on": 1,
            "monitors_on": 40,
            "desktop_cpus_on": 40,
            "ac_vents_on": 2,
        })(),
        type("Row", (), {
            "building": "B1",
            "floor": "F1",
            "zone": "B",
            "lights_on": 6,
            "routers_on": 1,
            "monitors_on": 50,
            "desktop_cpus_on": 50,
            "ac_vents_on": 3,
        })(),
    ]

    saving = GUIOrchestrator._compute_power_saving_percent(rows, total_seats=200, zone_count=2)
    assert saving > 0
    assert saving < 100

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

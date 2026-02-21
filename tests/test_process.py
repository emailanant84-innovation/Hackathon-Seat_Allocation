from __future__ import annotations

from datetime import datetime

from seat_allocation_app.allocator import SeatAllocator
from seat_allocation_app.data_sources.access_stream import AccessControlStream
from seat_allocation_app.data_sources.employee_directory import EmployeeDirectoryClient
from seat_allocation_app.data_sources.seat_inventory import SeatInventoryClient
from seat_allocation_app.energy_optimizer import EnergyOptimizer
from seat_allocation_app.iot_client import IoTDeviceClient
from seat_allocation_app.logging_orchestrator import LoggingOrchestrator
from seat_allocation_app.models import AccessEvent, Employee, Seat
from seat_allocation_app.notifications.email_client import EmailNotifier
from seat_allocation_app.notifications.message_client import MessageNotifier
from seat_allocation_app.process_orchestrator import ProcessOrchestrator
from seat_allocation_app.simulation import build_employee_directory, build_seat_topology


def test_orchestrator_assigns_team_cluster_and_notifies() -> None:
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
    assert len(orchestrator.email_notifier.sent_messages) == 2
    assert len(orchestrator.message_notifier.sent_messages) == 2
    assert any(cmd.command == "POWER_ON" for cmd in orchestrator.iot_client.command_history)


def test_simulation_topology_has_2000_seats() -> None:
    seats = build_seat_topology()
    assert len(seats) == 2000
    assert len({(s.building, s.floor, s.zone) for s in seats}) == 20


def test_employee_directory_contains_card_id() -> None:
    employees = build_employee_directory(total_employees=3)
    assert employees[0].card_id == "CARD-E0001"
    assert employees[1].card_id == "CARD-E0002"

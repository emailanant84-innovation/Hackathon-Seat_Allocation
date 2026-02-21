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
                Employee("E1", "Alex", "alex@example.com", "+111", "Engineering", "Platform"),
                Employee("E2", "Blair", "blair@example.com", "+222", "Engineering", "Data"),
            ]
        ),
        seat_inventory=SeatInventoryClient(
            [
                Seat("S1", "F1", "A", "Engineering", "Platform"),
                Seat("S2", "F1", "A", "Engineering", "Data"),
            ]
        ),
        seat_allocator=SeatAllocator(),
        energy_optimizer=EnergyOptimizer(),
        iot_client=IoTDeviceClient(),
        email_notifier=EmailNotifier(),
        message_notifier=MessageNotifier(),
        logger=LoggingOrchestrator("test_logger"),
    )

    orchestrator.run_once()

    occupied = {seat.seat_id: seat.occupied_by for seat in orchestrator.seat_inventory.all_seats()}
    assert occupied["S1"] == "E1"
    assert occupied["S2"] == "E2"
    assert len(orchestrator.email_notifier.sent_messages) == 2
    assert len(orchestrator.message_notifier.sent_messages) == 2
    assert any(cmd.command == "POWER_ON" for cmd in orchestrator.iot_client.command_history)

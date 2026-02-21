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


def bootstrap_demo() -> ProcessOrchestrator:
    employees = [
        Employee("E001", "Asha", "asha@corp.com", "+12025550101", "Engineering", "Platform"),
        Employee("E002", "Miguel", "miguel@corp.com", "+12025550102", "Engineering", "Platform"),
        Employee("E003", "Neha", "neha@corp.com", "+12025550103", "Engineering", "Data"),
    ]
    seats = [
        Seat("S-F1-A-01", "F1", "A", "Engineering", "Platform"),
        Seat("S-F1-A-02", "F1", "A", "Engineering", "Platform"),
        Seat("S-F1-B-01", "F1", "B", "Engineering", "Data"),
        Seat("S-F2-A-01", "F2", "A", "HR", "PeopleOps"),
    ]
    events = [
        AccessEvent("E001", "CARD-101", datetime.utcnow()),
        AccessEvent("E002", "CARD-102", datetime.utcnow()),
        AccessEvent("E003", "CARD-103", datetime.utcnow()),
    ]

    return ProcessOrchestrator(
        access_stream=AccessControlStream(events),
        employee_directory=EmployeeDirectoryClient(employees),
        seat_inventory=SeatInventoryClient(seats),
        seat_allocator=SeatAllocator(),
        energy_optimizer=EnergyOptimizer(),
        iot_client=IoTDeviceClient(),
        email_notifier=EmailNotifier(),
        message_notifier=MessageNotifier(),
        logger=LoggingOrchestrator(),
    )


if __name__ == "__main__":
    orchestrator = bootstrap_demo()
    orchestrator.run_once()

from __future__ import annotations

import sys

from seat_allocation_app.allocator import SeatAllocator
from seat_allocation_app.data_sources.access_stream import AccessControlStream
from seat_allocation_app.data_sources.employee_directory import EmployeeDirectoryClient
from seat_allocation_app.data_sources.seat_inventory import SeatInventoryClient
from seat_allocation_app.energy_optimizer import EnergyOptimizer
from seat_allocation_app.gui_orchestrator import GUIOrchestrator
from seat_allocation_app.iot_client import IoTDeviceClient
from seat_allocation_app.logging_orchestrator import LoggingOrchestrator
from seat_allocation_app.notifications.email_client import EmailNotifier
from seat_allocation_app.notifications.message_client import MessageNotifier
from seat_allocation_app.process_orchestrator import ProcessOrchestrator
from seat_allocation_app.simulation import build_employee_directory, build_seat_topology


def bootstrap_orchestrator() -> tuple[ProcessOrchestrator, list[str]]:
    employees = build_employee_directory(total_employees=2500)
    seats = build_seat_topology()

    orchestrator = ProcessOrchestrator(
        access_stream=AccessControlStream([]),
        employee_directory=EmployeeDirectoryClient(employees),
        seat_inventory=SeatInventoryClient(seats),
        seat_allocator=SeatAllocator(),
        energy_optimizer=EnergyOptimizer(),
        iot_client=IoTDeviceClient(),
        email_notifier=EmailNotifier(),
        message_notifier=MessageNotifier(),
        logger=LoggingOrchestrator(),
    )
    employee_ids = [employee.employee_id for employee in employees]
    return orchestrator, employee_ids


def run_cli_demo() -> None:
    orchestrator, employee_ids = bootstrap_orchestrator()
    for employee_id in employee_ids[:5]:
        orchestrator.access_stream.publish(employee_id, f"CARD-{employee_id}")
    assignments = orchestrator.run_once()
    print(f"Processed {len(assignments)} assignment(s) in CLI demo")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli_demo()
    else:
        orchestrator, employee_ids = bootstrap_orchestrator()
        gui = GUIOrchestrator(orchestrator, employee_ids)
        gui.run()

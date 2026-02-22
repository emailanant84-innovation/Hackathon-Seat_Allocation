from __future__ import annotations

from dataclasses import dataclass
from itertools import islice

from seat_allocation_app.allocator import SeatAllocator
from seat_allocation_app.data_sources.access_stream import AccessControlStream
from seat_allocation_app.data_sources.employee_directory import EmployeeDirectoryClient
from seat_allocation_app.data_sources.seat_inventory import SeatInventoryClient
from seat_allocation_app.energy_optimizer import EnergyOptimizer
from seat_allocation_app.iot_client import IoTDeviceClient
from seat_allocation_app.logging_orchestrator import LoggingOrchestrator
from seat_allocation_app.models import AccessEvent, Assignment
from seat_allocation_app.notifications.email_client import EmailNotifier
from seat_allocation_app.notifications.message_client import MessageNotifier


@dataclass(slots=True)
class ProcessOrchestrator:
    access_stream: AccessControlStream
    employee_directory: EmployeeDirectoryClient
    seat_inventory: SeatInventoryClient
    seat_allocator: SeatAllocator
    energy_optimizer: EnergyOptimizer
    iot_client: IoTDeviceClient
    email_notifier: EmailNotifier
    message_notifier: MessageNotifier
    logger: LoggingOrchestrator


    def _order_batch(self, batch: list[AccessEvent]) -> list[AccessEvent]:
        def key(event: AccessEvent) -> tuple[str, str, str, str]:
            employee = self.employee_directory.get_employee(event.employee_id)
            if not employee:
                return ("~", "~", event.entered_at.isoformat(), event.employee_id)
            return (
                employee.department,
                employee.team,
                event.entered_at.isoformat(),
                event.employee_id,
            )

        return sorted(batch, key=key)

    def process_event(self, access_event: AccessEvent) -> Assignment | None:
        self.logger.info(
            f"Access event received for employee_id={access_event.employee_id} card={access_event.card_id}"
        )
        employee = self.employee_directory.get_employee(access_event.employee_id)
        if not employee:
            self.logger.warning(
                f"Employee profile missing for employee_id={access_event.employee_id}."
            )
            return None

        candidates = self.seat_inventory.available_seats()
        assignment = self.seat_allocator.select_seat(
            employee,
            candidates,
            self.seat_inventory.all_seats(),
        )
        if not assignment:
            self.logger.warning(
                f"No seat available for employee_id={employee.employee_id} department={employee.department}."
            )
            return None

        self.seat_inventory.mark_occupied(
            assignment.seat_id,
            employee.employee_id,
            employee.department,
            employee.team,
        )
        self.email_notifier.send_seat_assignment(employee, assignment)
        self.message_notifier.send_seat_assignment(employee, assignment)

        self.logger.info(
            f"Seat {assignment.seat_id} assigned to {employee.employee_id} "
            f"({employee.department}/{employee.team}) at {assignment.building}/{assignment.floor}/{assignment.zone}."
        )

        zone_counts = self.seat_inventory.occupied_zone_counts()
        energy_commands = self.energy_optimizer.optimize(zone_counts)
        for command in energy_commands:
            self.iot_client.send_command(command)
        self.logger.info(
            f"Energy optimization dispatched {len(energy_commands)} IoT command(s)."
        )
        return assignment

    def run_once(self) -> list[Assignment]:
        assignments: list[Assignment] = []
        stream = self.access_stream.consume()

        while True:
            batch = list(islice(stream, 2))
            if not batch:
                break

            ordered_batch = self._order_batch(batch)
            batch_employees = [
                employee
                for employee in (
                    self.employee_directory.get_employee(event.employee_id)
                    for event in ordered_batch
                )
                if employee is not None
            ]
            self.seat_allocator.prepare_batch_baseline(
                batch_employees,
                self.seat_inventory.all_seats(),
            )

            for access_event in ordered_batch:
                assignment = self.process_event(access_event)
                if assignment:
                    assignments.append(assignment)

        return assignments

from __future__ import annotations

from seat_allocation_app.models import Assignment, Employee


class EmailNotifier:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []

    def send_seat_assignment(self, employee: Employee, assignment: Assignment) -> None:
        message = (
            f"Email to {employee.email}: Hi {employee.name}, your seat is "
            f"{assignment.seat_id} ({assignment.building}/{assignment.floor}/{assignment.zone})."
        )
        self.sent_messages.append(message)

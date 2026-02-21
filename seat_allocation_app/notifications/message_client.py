from __future__ import annotations

from seat_allocation_app.models import Assignment, Employee


class MessageNotifier:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []

    def send_seat_assignment(self, employee: Employee, assignment: Assignment) -> None:
        message = (
            f"SMS to {employee.phone}: Seat {assignment.seat_id} allocated in "
            f"{assignment.floor}/{assignment.zone}."
        )
        self.sent_messages.append(message)

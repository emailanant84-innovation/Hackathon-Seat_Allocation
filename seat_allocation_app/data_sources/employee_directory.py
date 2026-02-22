from __future__ import annotations

from seat_allocation_app.models import Employee


class EmployeeDirectoryClient:
    def __init__(self, employees: list[Employee]) -> None:
        self._employees = {employee.employee_id: employee for employee in employees}

    def get_employee(self, employee_id: str) -> Employee | None:
        return self._employees.get(employee_id)

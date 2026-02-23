from __future__ import annotations

from seat_allocation_app.models import DeviceCommand


class IoTDeviceClient:
    def __init__(self) -> None:
        self.command_history: list[DeviceCommand] = []

    def send_command(self, command: DeviceCommand) -> None:
        self.command_history.append(command)

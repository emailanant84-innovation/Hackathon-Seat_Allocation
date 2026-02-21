from __future__ import annotations

from dataclasses import dataclass

from seat_allocation_app.models import DeviceCommand


@dataclass(slots=True)
class EnergyOptimizer:
    idle_zone_threshold: int = 0

    def optimize(self, occupied_zone_counts: dict[tuple[str, str], int]) -> list[DeviceCommand]:
        commands: list[DeviceCommand] = []
        for (floor, zone), occupants in occupied_zone_counts.items():
            if occupants > self.idle_zone_threshold:
                commands.append(
                    DeviceCommand(
                        floor=floor,
                        zone=zone,
                        command="POWER_ON",
                        reason="Active occupancy detected",
                    )
                )

        active_zones = set(occupied_zone_counts)
        # In a real system, floor map service would return every zone.
        # This sample predefines known zones for command completeness.
        known_zones = {
            ("F1", "A"),
            ("F1", "B"),
            ("F2", "A"),
            ("F2", "B"),
        }

        for floor, zone in known_zones - active_zones:
            commands.append(
                DeviceCommand(
                    floor=floor,
                    zone=zone,
                    command="POWER_OFF",
                    reason="No occupancy detected",
                )
            )
        return commands

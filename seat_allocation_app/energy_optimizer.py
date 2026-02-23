from __future__ import annotations

from dataclasses import dataclass

from seat_allocation_app.models import DeviceCommand


@dataclass(slots=True)
class EnergyOptimizer:
    idle_zone_threshold: int = 0

    def optimize(
        self,
        occupied_zone_counts: dict[tuple[str, str, str], int],
        known_zones: set[tuple[str, str, str]] | None = None,
    ) -> list[DeviceCommand]:
        commands: list[DeviceCommand] = []
        for (building, floor, zone), occupants in occupied_zone_counts.items():
            if occupants > self.idle_zone_threshold:
                commands.append(
                    DeviceCommand(
                        building=building,
                        floor=floor,
                        zone=zone,
                        command="POWER_ON",
                        reason="Active occupancy detected",
                    )
                )

        if known_zones is None:
            known_zones = {
                (f"B{building}", f"F{floor}", zone)
                for building in range(1, 3)
                for floor in range(1, 3)
                for zone in ("A", "B", "C")
            }

        active_zones = set(occupied_zone_counts)
        for building, floor, zone in known_zones - active_zones:
            commands.append(
                DeviceCommand(
                    building=building,
                    floor=floor,
                    zone=zone,
                    command="POWER_OFF",
                    reason="No occupancy detected",
                )
            )
        return commands

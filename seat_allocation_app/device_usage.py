from __future__ import annotations

from dataclasses import dataclass

from seat_allocation_app.models import Seat


@dataclass(slots=True)
class DeviceUsageRow:
    building: str
    floor: str
    zone: str
    occupied_seats: int
    lights_on: int
    routers_on: int
    monitors_on: int
    desktop_cpus_on: int
    ac_vents_on: int


def summarize_device_usage(seats: list[Seat]) -> list[DeviceUsageRow]:
    grouped: dict[tuple[str, str, str], list[Seat]] = {}
    for seat in seats:
        grouped.setdefault((seat.building, seat.floor, seat.zone), []).append(seat)

    rows: list[DeviceUsageRow] = []
    for building in ("B1", "B2"):
        for floor in ("F1", "F2"):
            for zone in ("A", "B"):
                zone_seats = grouped.get((building, floor, zone), [])
                occupied = sum(1 for seat in zone_seats if seat.status == "occupied")
                lights_on = min(10, (occupied + 9) // 10)  # 10 light circuits for 100 seats/zone
                routers_on = 1 if occupied else 0
                ac_vents_on = min(3, (occupied + 19) // 20)  # 3 vents per zone

                rows.append(
                    DeviceUsageRow(
                        building=building,
                        floor=floor,
                        zone=zone,
                        occupied_seats=occupied,
                        lights_on=lights_on,
                        routers_on=routers_on,
                        monitors_on=occupied,
                        desktop_cpus_on=occupied,
                        ac_vents_on=ac_vents_on,
                    )
                )
    return rows

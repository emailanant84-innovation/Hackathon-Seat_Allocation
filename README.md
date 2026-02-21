# Live Access-Driven Seat Allocation and Energy Optimization

This Python application allocates an employee seat in near real-time when a building access event is captured.
It keeps employees with their teams by prioritizing team-clustered seats, then optimizes floor energy usage by powering on occupied zones and powering off idle zones.

## Topology covered

- Buildings: 2 (`B1`, `B2`)
- Floors per building: 2 (`F1`-`F2`)
- Zones per floor: 3 (`A`, `B`, `C`)
- Seats per zone: 60
- Total capacity: 720 seats
- Total possible departments: 20
- Total possible teams: 40
- Simulation employee pool: 300 employees
- Runtime random simulation scope: 12 departments + 25 teams

## Seat allocation algorithm

The allocator uses a **beam-search strategy** with a learning cache:
- Priority order for seat selection: **same team**, then **same department**, then **same zone density**.
- Learning: successful placements are cached by `(department, team)` and reused for faster future decisions.
- Strict locality rule: once a team+department has an occupied location, future members of that same team+department are constrained to the same `(building, floor, zone)`.

## Modules

- `seat_allocation_app/process_orchestrator.py`: Main workflow orchestrator.
- `seat_allocation_app/allocator.py`: Beam-search seat allocator with learning cache.
- `seat_allocation_app/gui_orchestrator.py`: Top-level GUI orchestrator with run/pause/reset controls, responsive graphics, scrollbars, live assignment tab, live reasoning tab, and electrical usage tab.
- `seat_allocation_app/device_usage.py`: Electrical device usage summary calculator.
- `seat_allocation_app/logging_orchestrator.py`: Centralized activity logging orchestrator.
- `seat_allocation_app/data_sources/access_stream.py`: Access-management live stream adapter.
- `seat_allocation_app/data_sources/employee_directory.py`: Employee profile lookup adapter.
- `seat_allocation_app/data_sources/seat_inventory.py`: Seat inventory and occupancy adapter.
- `seat_allocation_app/energy_optimizer.py`: Energy optimization logic for floor zones.
- `seat_allocation_app/iot_client.py`: IoT command dispatch adapter.
- `seat_allocation_app/notifications/email_client.py`: Email dispatch adapter.
- `seat_allocation_app/notifications/message_client.py`: SMS/message dispatch adapter.
- `seat_allocation_app/simulation.py`: Runtime data generation for topology and employees.

## Run GUI simulation

```bash
python main.py
```

The GUI opens in fit-to-page mode by default.

Tabs:
- **Buildings** (2 floors × 3 zones/floor × 60 seat-squares/zone per building, dynamically highlighted)
- **Floors**
- **Zones**
- **Seats**
- **LIVE Seat Assignments** (employee details, seat, and assignment time)
- **LIVE Reasoning** (allocator reasoning string for each live assignment)
- **Electrical Usage** (lights, routers, monitors, desktop CPUs, AC vents usage summary)

Event simulation behavior:
- Simulation interval is **2 seconds**.
- After every **4 to 5 events**, generator intentionally repeats an employee with the same team or same department pattern.

## Run CLI demo

```bash
python main.py --cli
```

## Run tests

```bash
pytest -q
```

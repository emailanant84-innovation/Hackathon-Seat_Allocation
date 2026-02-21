# Live Access-Driven Seat Allocation and Energy Optimization

This Python application allocates an employee seat in near real-time when a building access event is captured.
It keeps employees with their teams by prioritizing team-clustered seats, then optimizes floor energy usage by powering on occupied zones and powering off idle zones.

## Topology covered

- Buildings: 2 (`B1`, `B2`)
- Floors per building: 5 (`F1`-`F5`)
- Zones per floor: 2 (`A`, `B`)
- Seats per zone: 100
- Total capacity: 2000 seats
- Departments in simulation: 20
- Teams in simulation: 100

## Seat allocation algorithm

The allocator uses a **beam-search strategy** with a learning cache:
- Priority order for seat selection: **same team**, then **same department**, then **same zone density**.
- Learning: successful placements are cached by `(department, team)` and reused for faster future decisions.
- Strict locality rule: once a team+department has an occupied location, future members of that same team+department are constrained to the same `(building, floor, zone)`.

## Modules

- `seat_allocation_app/process_orchestrator.py`: Main workflow orchestrator.
- `seat_allocation_app/allocator.py`: Beam-search seat allocator with learning cache.
- `seat_allocation_app/gui_orchestrator.py`: Top-level GUI orchestrator with run/pause/reset controls, responsive graphics, scrollbars, live assignment tab, and electrical usage tab.
- `seat_allocation_app/device_usage.py`: Electrical device usage summary calculator.
- `seat_allocation_app/logging_orchestrator.py`: Centralized activity logging orchestrator.
- `seat_allocation_app/data_sources/access_stream.py`: Access-management live stream adapter.
- `seat_allocation_app/data_sources/employee_directory.py`: Employee profile lookup adapter.
- `seat_allocation_app/data_sources/seat_inventory.py`: Seat inventory and occupancy adapter.
- `seat_allocation_app/energy_optimizer.py`: Energy optimization logic for floor zones.
- `seat_allocation_app/iot_client.py`: IoT command dispatch adapter.
- `seat_allocation_app/notifications/email_client.py`: Email dispatch adapter.
- `seat_allocation_app/notifications/message_client.py`: SMS/message dispatch adapter.
- `seat_allocation_app/simulation.py`: Runtime data generation for 2000-seat topology and employees.

## Run GUI simulation

```bash
python main.py
```

The GUI opens in fit-to-page mode by default.

Tabs:
- **Buildings** (for each building, image shows 2 floors (`F1`, `F2`), 2 zones per floor, and **100 small seat squares per zone** highlighted dynamically based on occupancy, responsive to canvas size)
- **Floors**
- **Zones**
- **Seats**
- **LIVE Seat Assignments** (employee details, seat, and assignment time)
- **Electrical Usage** (lights, routers, monitors, desktop CPUs, AC vents usage summary)

Each data-heavy tab includes vertical/horizontal scrollbars for browsing all rows.

Use buttons to:
- **Run Simulation** (auto event injection every 3 seconds)
- **Pause Simulation**
- **Inject Event Now**
- **Reset Simulation**

## Run CLI demo

```bash
python main.py --cli
```

## Run tests

```bash
pytest -q
```

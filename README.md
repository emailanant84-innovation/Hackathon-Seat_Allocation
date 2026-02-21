# Live Access-Driven Seat Allocation and Energy Optimization

This Python application allocates an employee seat in near real-time when a building access event is captured.
It keeps employees with their teams by prioritizing team-clustered seats, then optimizes floor energy usage by powering on occupied zones and powering off idle zones.

## Topology covered

- Buildings: 2 (`B1`, `B2`)
- Floors per building: 2 (`F1`-`F2`)
- Zones per floor: 3 (`A`, `B`, `C`)
- Seats per zone: 60
- Total capacity: 720 seats
- Total possible departments: 10
- Total possible teams: 25
- Simulation employee pool: 300 employees
- Runtime simulation scope: same 10 departments + 25 teams

## Seat allocation algorithm

The allocator uses a **beam-search strategy** to maximize utilization while preserving locality:
- Priority order for seat selection: **same team**, then **same department zone cohesion**, then **zone utilization/consolidation**.
- Same-team together: beam score strongly anchors employees to zones where their team already sits.
- Department cohesion: teams from the same department are clustered in the same zone; if an existing department zone has capacity, allocator keeps subsequent department members there.
- Domain reduction fallback: when constraints conflict (for example, a department anchor zone already has 2 departments), allocator relaxes the anchor lock and reduces the search to valid zones instead of halting allocation.
- Controlled mixing: different departments can share a zone when team and department priorities are preserved.
- Zone department cap: each zone can host employees from at most **2 departments** at a time.
- Building/floor preference: allocator first reduces candidates to the same floor (if possible), then same building, before considering other locations.

## Team ↔ Department connection in simulation

Simulation maintains a deterministic mapping between teams and departments (`team_department_map()`):
- Every team belongs to exactly one department.
- Seat topology and employee generation use the same mapping.
- The allocator uses this same connection while scoring seats.

## Modules

- `seat_allocation_app/process_orchestrator.py`: Main workflow orchestrator.
- `seat_allocation_app/allocator.py`: Beam-search seat allocator maximizing utilization with locality constraints.
- `seat_allocation_app/gui_orchestrator.py`: Top-level GUI orchestrator with run/pause/reset controls, responsive graphics, scrollbars, live assignment tabs, and electrical usage tab.
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
- **LIVE Seat Assignments** (live assignment stream)
- **LIVE Assignments Ordered** (ordered by department-team map, zone, floor, building)
- **Electrical Usage** (lights, routers, monitors, desktop CPUs, AC vents usage summary)

Buildings tab color behavior:
- Occupied seats are colored by **department**.
- Zone-based coloring has been removed.

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

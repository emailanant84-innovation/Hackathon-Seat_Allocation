# Live Access-Driven Seat Allocation and Energy Optimization

This Python application allocates an employee seat in near real-time when a building access event is captured.
It keeps employees with their teams by prioritizing team-clustered seats, then optimizes floor energy usage by powering on occupied zones and powering off idle zones.

## Modules

- `seat_allocation_app/process_orchestrator.py`: Main workflow orchestrator.
- `seat_allocation_app/logging_orchestrator.py`: Centralized activity logging orchestrator.
- `seat_allocation_app/data_sources/access_stream.py`: Access-management live stream adapter.
- `seat_allocation_app/data_sources/employee_directory.py`: Employee profile lookup adapter.
- `seat_allocation_app/data_sources/seat_inventory.py`: Seat inventory and occupancy adapter.
- `seat_allocation_app/allocator.py`: Team-aware seat assignment engine.
- `seat_allocation_app/energy_optimizer.py`: Energy optimization logic for floor zones.
- `seat_allocation_app/iot_client.py`: IoT command dispatch adapter.
- `seat_allocation_app/notifications/email_client.py`: Email dispatch adapter.
- `seat_allocation_app/notifications/message_client.py`: SMS/message dispatch adapter.

## Run demo

```bash
python main.py
```

## Run tests

```bash
pytest -q
```

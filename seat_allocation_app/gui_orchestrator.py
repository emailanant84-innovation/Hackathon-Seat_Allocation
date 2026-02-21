from __future__ import annotations

import tkinter as tk
from collections import Counter
from tkinter import ttk
from typing import Callable

from seat_allocation_app.process_orchestrator import ProcessOrchestrator


class GUIOrchestrator:
    """Top-level UI orchestrator with run/pause/reset simulation controls."""

    def __init__(
        self,
        bootstrap_callback: Callable[[], tuple[ProcessOrchestrator, list[str], dict[str, str]]],
    ) -> None:
        self._bootstrap_callback = bootstrap_callback
        self.process_orchestrator, self.employee_ids, self.card_by_employee = self._bootstrap_callback()
        self.employee_index = 0
        self.is_running = False
        self._after_id: str | None = None

        self.root = tk.Tk()
        self.root.title("Live Seat Allocation Control Tower")
        self.root.geometry("1200x800")

        self.latest_assignment_var = tk.StringVar(value="Waiting for first access event...")

        self._build_layout()
        self._refresh_views()

    def _build_layout(self) -> None:
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=10, pady=10)

        ttk.Label(
            header,
            text="Real-time Seat Allocation (2 Buildings, 5 Floors, 2 Zones, 100 Seats/Zone)",
            font=("Arial", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(header, textvariable=self.latest_assignment_var, foreground="blue").pack(anchor="w")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.buildings_tab = ttk.Frame(notebook)
        self.floors_tab = ttk.Frame(notebook)
        self.zones_tab = ttk.Frame(notebook)
        self.seats_tab = ttk.Frame(notebook)

        notebook.add(self.buildings_tab, text="Buildings")
        notebook.add(self.floors_tab, text="Floors")
        notebook.add(self.zones_tab, text="Zones")
        notebook.add(self.seats_tab, text="Seats")

        self.building_canvas = tk.Canvas(self.buildings_tab, bg="white")
        self.building_canvas.pack(fill="both", expand=True)

        self.floor_tree = ttk.Treeview(
            self.floors_tab,
            columns=("building", "floor", "occupied", "available"),
            show="headings",
        )
        for col in ("building", "floor", "occupied", "available"):
            self.floor_tree.heading(col, text=col.title())
        self.floor_tree.pack(fill="both", expand=True)

        self.zone_tree = ttk.Treeview(
            self.zones_tab,
            columns=("building", "floor", "zone", "occupied", "available"),
            show="headings",
        )
        for col in ("building", "floor", "zone", "occupied", "available"):
            self.zone_tree.heading(col, text=col.title())
        self.zone_tree.pack(fill="both", expand=True)

        self.seat_tree = ttk.Treeview(
            self.seats_tab,
            columns=("seat_id", "building", "floor", "zone", "status", "occupied_by"),
            show="headings",
        )
        for col in ("seat_id", "building", "floor", "zone", "status", "occupied_by"):
            self.seat_tree.heading(col, text=col.title())
        self.seat_tree.pack(fill="both", expand=True)

        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=10, pady=5)
        self.toggle_button = ttk.Button(controls, text="Run Simulation", command=self._toggle_running)
        self.toggle_button.pack(side="left")
        ttk.Button(controls, text="Inject Event Now", command=self.inject_single_event).pack(side="left", padx=8)
        ttk.Button(controls, text="Reset Simulation", command=self.reset_simulation).pack(side="left", padx=8)
        ttk.Label(controls, text="Automatic simulation interval: 3 seconds").pack(side="left", padx=15)

    def _toggle_running(self) -> None:
        if self.is_running:
            self.pause_simulation()
        else:
            self.start_simulation()

    def start_simulation(self) -> None:
        self.is_running = True
        self.toggle_button.configure(text="Pause Simulation")
        self._schedule_next_tick(0)

    def pause_simulation(self) -> None:
        self.is_running = False
        self.toggle_button.configure(text="Run Simulation")
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def reset_simulation(self) -> None:
        self.pause_simulation()
        self.process_orchestrator, self.employee_ids, self.card_by_employee = self._bootstrap_callback()
        self.employee_index = 0
        self.latest_assignment_var.set("Simulation reset. Click Run Simulation to start demo.")
        self._refresh_views()

    def _schedule_next_tick(self, delay_ms: int = 3000) -> None:
        if self.is_running:
            self._after_id = self.root.after(delay_ms, self._simulation_tick)

    def _simulation_tick(self) -> None:
        if not self.is_running:
            return
        self.inject_single_event()
        self._schedule_next_tick(3000)

    def _next_employee_id(self) -> str:
        employee_id = self.employee_ids[self.employee_index % len(self.employee_ids)]
        self.employee_index += 1
        return employee_id

    def inject_single_event(self) -> None:
        employee_id = self._next_employee_id()
        card_id = self.card_by_employee.get(employee_id, f"CARD-{employee_id}")
        self.process_orchestrator.access_stream.publish(employee_id, card_id)
        assignments = self.process_orchestrator.run_once()
        assignment = assignments[-1] if assignments else None

        if assignment:
            self.latest_assignment_var.set(
                f"Assigned {assignment.employee_id} -> {assignment.seat_id} "
                f"({assignment.building}/{assignment.floor}/{assignment.zone})"
            )
        else:
            self.latest_assignment_var.set(f"No seat allocation produced for {employee_id}.")

        self._refresh_views()

    def _refresh_views(self) -> None:
        seats = self.process_orchestrator.seat_inventory.all_seats()
        self._refresh_building_canvas(seats)
        self._refresh_floor_table(seats)
        self._refresh_zone_table(seats)
        self._refresh_seat_table(seats)

    def _refresh_building_canvas(self, seats: list) -> None:
        self.building_canvas.delete("all")
        building_stats = Counter((seat.building, seat.status) for seat in seats)

        for i, building in enumerate(("B1", "B2")):
            x0, y0 = 80 + i * 500, 100
            x1, y1 = x0 + 300, y0 + 500
            self.building_canvas.create_rectangle(x0, y0, x1, y1, fill="#f3f3f3", outline="black")
            self.building_canvas.create_text((x0 + x1) / 2, 70, text=f"Building {building}", font=("Arial", 12, "bold"))

            occupied = building_stats[(building, "occupied")]
            available = building_stats[(building, "available")]
            total = occupied + available
            ratio = occupied / total if total else 0

            bar_height = int((y1 - y0 - 80) * ratio)
            self.building_canvas.create_rectangle(x1 + 20, y1 - 20 - bar_height, x1 + 60, y1 - 20, fill="green")
            self.building_canvas.create_rectangle(x1 + 20, y0 + 20, x1 + 60, y1 - 20 - bar_height, fill="lightgray")
            self.building_canvas.create_text(x1 + 40, y1 + 10, text=f"{occupied}/{total}")

    def _refresh_floor_table(self, seats: list) -> None:
        for item in self.floor_tree.get_children():
            self.floor_tree.delete(item)

        floors = Counter((seat.building, seat.floor, seat.status) for seat in seats)
        for building in ("B1", "B2"):
            for floor in ("F1", "F2", "F3", "F4", "F5"):
                occupied = floors[(building, floor, "occupied")]
                available = floors[(building, floor, "available")]
                self.floor_tree.insert("", "end", values=(building, floor, occupied, available))

    def _refresh_zone_table(self, seats: list) -> None:
        for item in self.zone_tree.get_children():
            self.zone_tree.delete(item)

        zones = Counter((seat.building, seat.floor, seat.zone, seat.status) for seat in seats)
        for building in ("B1", "B2"):
            for floor in ("F1", "F2", "F3", "F4", "F5"):
                for zone in ("A", "B"):
                    occupied = zones[(building, floor, zone, "occupied")]
                    available = zones[(building, floor, zone, "available")]
                    self.zone_tree.insert(
                        "", "end", values=(building, floor, zone, occupied, available)
                    )

    def _refresh_seat_table(self, seats: list) -> None:
        for item in self.seat_tree.get_children():
            self.seat_tree.delete(item)

        for seat in seats[:250]:
            self.seat_tree.insert(
                "",
                "end",
                values=(
                    seat.seat_id,
                    seat.building,
                    seat.floor,
                    seat.zone,
                    seat.status,
                    seat.occupied_by or "-",
                ),
            )

    def run(self) -> None:
        self.root.mainloop()

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
        self._last_seats_snapshot: list = []

        self.root = tk.Tk()
        self.root.title("Live Seat Allocation Control Tower")
        self.root.geometry("1280x900")
        self._fit_to_page()

        self.latest_assignment_var = tk.StringVar(value="Waiting for first access event...")
        self.live_assignment_rows: list[tuple[str, ...]] = []

        self._build_layout()
        self._refresh_views()

    def _fit_to_page(self) -> None:
        try:
            self.root.state("zoomed")
        except tk.TclError:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_w}x{screen_h}+0+0")

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
        self.live_tab = ttk.Frame(notebook)

        notebook.add(self.buildings_tab, text="Buildings")
        notebook.add(self.floors_tab, text="Floors")
        notebook.add(self.zones_tab, text="Zones")
        notebook.add(self.seats_tab, text="Seats")
        notebook.add(self.live_tab, text="LIVE Seat Assignments")

        self.building_canvas = tk.Canvas(self.buildings_tab, bg="white")
        self.building_canvas.pack(fill="both", expand=True)
        self.building_canvas.bind("<Configure>", self._on_canvas_resize)

        self.floor_tree = self._create_table_with_scrollbar(
            self.floors_tab,
            ("building", "floor", "occupied", "available"),
        )
        self.zone_tree = self._create_table_with_scrollbar(
            self.zones_tab,
            ("building", "floor", "zone", "occupied", "available"),
        )
        self.seat_tree = self._create_table_with_scrollbar(
            self.seats_tab,
            ("seat_id", "building", "floor", "zone", "status", "occupied_by"),
        )
        self.live_tree = self._create_table_with_scrollbar(
            self.live_tab,
            (
                "employee_id",
                "employee_name",
                "card_id",
                "department",
                "team",
                "seat_id",
                "building",
                "floor",
                "zone",
                "assigned_at",
            ),
        )

        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=10, pady=5)
        self.toggle_button = ttk.Button(controls, text="Run Simulation", command=self._toggle_running)
        self.toggle_button.pack(side="left")
        ttk.Button(controls, text="Inject Event Now", command=self.inject_single_event).pack(side="left", padx=8)
        ttk.Button(controls, text="Reset Simulation", command=self.reset_simulation).pack(side="left", padx=8)
        ttk.Label(controls, text="Automatic simulation interval: 3 seconds").pack(side="left", padx=15)

    def _create_table_with_scrollbar(self, parent: ttk.Frame, columns: tuple[str, ...]) -> ttk.Treeview:
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        tree = ttk.Treeview(container, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=140, minwidth=110, anchor="center")

        y_scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        x_scrollbar = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        return tree

    def _on_canvas_resize(self, _event: tk.Event) -> None:
        self._refresh_building_canvas(self._last_seats_snapshot)

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
        self.live_assignment_rows = []
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
            employee = self.process_orchestrator.employee_directory.get_employee(assignment.employee_id)
            self.live_assignment_rows.append(
                (
                    assignment.employee_id,
                    employee.name if employee else "Unknown",
                    card_id,
                    employee.department if employee else "Unknown",
                    employee.team if employee else "Unknown",
                    assignment.seat_id,
                    assignment.building,
                    assignment.floor,
                    assignment.zone,
                    assignment.assigned_at.strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
            self.latest_assignment_var.set(
                f"Assigned {assignment.employee_id} -> {assignment.seat_id} "
                f"({assignment.building}/{assignment.floor}/{assignment.zone})"
            )
        else:
            self.latest_assignment_var.set(f"No seat allocation produced for {employee_id}.")

        self._refresh_views()

    def _refresh_views(self) -> None:
        seats = self.process_orchestrator.seat_inventory.all_seats()
        self._last_seats_snapshot = seats
        self._refresh_building_canvas(seats)
        self._refresh_floor_table(seats)
        self._refresh_zone_table(seats)
        self._refresh_seat_table(seats)
        self._refresh_live_assignment_table()

    def _refresh_building_canvas(self, seats: list) -> None:
        self.building_canvas.delete("all")
        if not seats:
            return

        width = max(self.building_canvas.winfo_width(), 900)
        height = max(self.building_canvas.winfo_height(), 450)
        margin_x = 40
        panel_gap = 40
        panel_width = (width - (2 * margin_x) - panel_gap) / 2
        panel_height = height - 120
        y0 = 70

        zone_stats = Counter((seat.building, seat.zone, seat.status) for seat in seats)
        zone_colors = {"A": "#35a853", "B": "#2f6df6"}

        for index, building in enumerate(("B1", "B2")):
            x0 = margin_x + index * (panel_width + panel_gap)
            x1 = x0 + panel_width
            y1 = y0 + panel_height

            self.building_canvas.create_rectangle(x0, y0, x1, y1, fill="#f5f5f5", outline="#777")
            self.building_canvas.create_text(
                (x0 + x1) / 2,
                y0 - 20,
                text=f"Building {building}",
                font=("Arial", 12, "bold"),
            )

            for zone_index, zone in enumerate(("A", "B")):
                zx0 = x0 + 35 + zone_index * (panel_width / 2)
                zx1 = zx0 + (panel_width / 2) - 70
                zy0 = y0 + 40
                zy1 = y1 - 30

                occupied = zone_stats[(building, zone, "occupied")]
                available = zone_stats[(building, zone, "available")]
                total = occupied + available
                ratio = occupied / total if total else 0
                fill_top = zy1 - (zy1 - zy0) * ratio

                self.building_canvas.create_rectangle(zx0, zy0, zx1, zy1, fill="#d9d9d9", outline="#999")
                self.building_canvas.create_rectangle(zx0, fill_top, zx1, zy1, fill=zone_colors[zone], outline="")
                self.building_canvas.create_text((zx0 + zx1) / 2, zy1 + 15, text=f"Zone {zone}")
                self.building_canvas.create_text(
                    (zx0 + zx1) / 2,
                    zy0 - 12,
                    text=f"{occupied}/{total}",
                    fill=zone_colors[zone],
                    font=("Arial", 10, "bold"),
                )

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
                    self.zone_tree.insert("", "end", values=(building, floor, zone, occupied, available))

    def _refresh_seat_table(self, seats: list) -> None:
        for item in self.seat_tree.get_children():
            self.seat_tree.delete(item)

        for seat in seats:
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

    def _refresh_live_assignment_table(self) -> None:
        for item in self.live_tree.get_children():
            self.live_tree.delete(item)

        for row in reversed(self.live_assignment_rows):
            self.live_tree.insert("", "end", values=row)

    def run(self) -> None:
        self.root.mainloop()

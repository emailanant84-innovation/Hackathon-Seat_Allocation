from __future__ import annotations

import random
import tkinter as tk
from collections import Counter
from tkinter import ttk
from typing import Callable

from seat_allocation_app.device_usage import summarize_device_usage
from seat_allocation_app.process_orchestrator import ProcessOrchestrator
from seat_allocation_app.simulation import random_employee_event


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

        self._events_since_pattern = 0
        self._pattern_interval = random.randint(4, 5)
        self._pattern_anchor_id: str | None = None

        self.root = tk.Tk()
        self.root.title("Live Seat Allocation Control Tower")

        self.latest_assignment_var = tk.StringVar(value="Waiting for first access event...")
        self.device_summary_var = tk.StringVar(value="Totals: n/a | Power saving: n/a")
        self.live_assignment_rows: list[tuple[str, ...]] = []
        self._last_email_count = 0
        self._last_phone_count = 0
        self._last_iot_count = 0

        self._build_layout()
        self._fit_to_page()
        self._rebuild_employee_indexes()
        self._refresh_views()

    def _fit_to_page(self) -> None:
        # Compute geometry after widgets are created so controls row stays visible.
        self.root.update_idletasks()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Virtual-root dimensions can exclude taskbar/dock area on some platforms.
        usable_w = min(screen_w, self.root.winfo_vrootwidth() or screen_w)
        usable_h = min(screen_h, self.root.winfo_vrootheight() or screen_h)

        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()

        side_margin = max(16, int(usable_w * 0.02))
        top_margin = max(16, int(usable_h * 0.02))
        taskbar_reserve = max(72, int(usable_h * 0.10))

        max_w = max(720, usable_w - (2 * side_margin))
        max_h = max(560, usable_h - top_margin - taskbar_reserve)

        min_w, min_h = 960, 640
        desired_w = max(min_w, req_w + 20)
        desired_h = max(min_h, req_h + 20)

        window_w = min(desired_w, max_w)
        window_h = min(desired_h, max_h)

        x_offset = max(0, (usable_w - window_w) // 2)
        y_offset = max(0, max(8, (usable_h - window_h) // 2))

        self.root.geometry(f"{window_w}x{window_h}+{x_offset}+{y_offset}")

        # Keep resize floor practical but never above what can fit on current display.
        self.root.minsize(min(min_w, max_w), min(min_h, max_h))

    def _build_layout(self) -> None:
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=10, pady=10)

        ttk.Label(
            header,
            text="Real-time Seat Allocation (2 Buildings, 2 Floors, 2 Zones, 100 Seats/Zone)",
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
        self.live_ordered_tab = ttk.Frame(notebook)
        self.device_tab = ttk.Frame(notebook)
        self.live_comms_tab = ttk.Frame(notebook)

        notebook.add(self.buildings_tab, text="Buildings")
        notebook.add(self.floors_tab, text="Floors")
        notebook.add(self.zones_tab, text="Zones")
        notebook.add(self.seats_tab, text="Seats")
        notebook.add(self.live_tab, text="LIVE Seat Assignments")
        notebook.add(self.live_ordered_tab, text="LIVE Assignments Ordered")
        notebook.add(self.device_tab, text="Electrical Usage")
        notebook.add(self.live_comms_tab, text="LIVE Communications")

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
        live_columns = (
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
        )
        self.live_tree = self._create_table_with_scrollbar(self.live_tab, live_columns)
        self.live_ordered_tree = self._create_table_with_scrollbar(self.live_ordered_tab, live_columns)

        self.device_tree = self._create_table_with_scrollbar(
            self.device_tab,
            (
                "building",
                "floor",
                "zone",
                "occupied_seats",
                "lights_on",
                "routers_on",
                "monitors_on",
                "desktop_cpus_on",
                "ac_vents_on",
            ),
        )
        ttk.Label(self.device_tab, textvariable=self.device_summary_var, foreground="#1f4e79").pack(anchor="w", padx=8, pady=6)


        self.email_live_list = self._create_scrolled_live_list(self.live_comms_tab, "LIVE Email Messages")
        self.phone_live_list = self._create_scrolled_live_list(self.live_comms_tab, "LIVE Phone Messages")
        self.iot_live_list = self._create_scrolled_live_list(self.live_comms_tab, "LIVE IoT Commands Sent")

        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=10, pady=5)
        self.toggle_button = ttk.Button(controls, text="Run Simulation", command=self._toggle_running)
        self.toggle_button.pack(side="left")
        ttk.Button(controls, text="Inject Event Now", command=self.inject_single_event).pack(side="left", padx=8)
        ttk.Button(controls, text="Reset Simulation", command=self.reset_simulation).pack(side="left", padx=8)
        ttk.Label(controls, text="Automatic simulation interval: 2 seconds").pack(side="left", padx=15)

    def _create_table_with_scrollbar(self, parent: ttk.Frame, columns: tuple[str, ...]) -> ttk.Treeview:
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        tree = ttk.Treeview(container, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=130, minwidth=100, anchor="center")

        y_scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        x_scrollbar = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        return tree

    def _create_scrolled_live_list(self, parent: ttk.Frame, title: str) -> tk.Listbox:
        section = ttk.LabelFrame(parent, text=title)
        section.pack(fill="both", expand=True, padx=8, pady=8)

        list_container = ttk.Frame(section)
        list_container.pack(fill="both", expand=True, padx=6, pady=6)

        listbox = tk.Listbox(list_container, font=("Courier New", 10), activestyle="none")
        listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.configure(yscrollcommand=scrollbar.set)
        return listbox

    @staticmethod
    def _format_iot_command(command) -> str:
        return (
            f"{command.building}/{command.floor}/{command.zone} -> "
            f"lights={command.lights_on}, routers={command.routers_on}, "
            f"monitors={command.monitors_on}, desktops={command.desktop_cpus_on}, ac_vents={command.ac_vents_on}"
        )


    def _rebuild_employee_indexes(self) -> None:
        self._employee_by_id = {
            employee_id: self.process_orchestrator.employee_directory.get_employee(employee_id)
            for employee_id in self.employee_ids
        }
        self._ids_by_team: dict[str, list[str]] = {}
        self._ids_by_department: dict[str, list[str]] = {}
        for employee_id, employee in self._employee_by_id.items():
            if not employee:
                continue
            self._ids_by_team.setdefault(employee.team, []).append(employee_id)
            self._ids_by_department.setdefault(employee.department, []).append(employee_id)
        dept_palette = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        ]
        depts = sorted(self._ids_by_department.keys())
        self._dept_colors = {
            dept: dept_palette[idx % len(dept_palette)]
            for idx, dept in enumerate(depts)
        }


    @staticmethod
    def _seat_display_department(seat) -> str:
        return seat.occupied_department or seat.department

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
        self._events_since_pattern = 0
        self._pattern_interval = random.randint(4, 5)
        self._pattern_anchor_id = None
        self._rebuild_employee_indexes()
        self.live_assignment_rows = []
        self._last_email_count = 0
        self._last_phone_count = 0
        self._last_iot_count = 0
        self.latest_assignment_var.set("Simulation reset. Click Run Simulation to start demo.")
        self._refresh_views()

    def _schedule_next_tick(self, delay_ms: int = 2000) -> None:
        if self.is_running:
            self._after_id = self.root.after(delay_ms, self._simulation_tick)

    def _simulation_tick(self) -> None:
        if not self.is_running:
            return
        self.inject_single_event()
        self._schedule_next_tick(2000)

    def _next_employee_id(self) -> str:
        employees = [
            employee
            for employee in (
                self.process_orchestrator.employee_directory.get_employee(employee_id)
                for employee_id in self.employee_ids
            )
            if employee is not None
        ]
        access_event = random_employee_event(employees)
        return access_event.employee_id

    def inject_single_event(self) -> None:
        employee_id = self._next_employee_id()
        card_id = self.card_by_employee.get(employee_id, f"CARD-{employee_id}")
        self.process_orchestrator.access_stream.publish(employee_id, card_id)
        assignments = self.process_orchestrator.run_once()
        assignment = assignments[-1] if assignments else None

        if assignment:
            employee = self.process_orchestrator.employee_directory.get_employee(assignment.employee_id)
            assigned_at = assignment.assigned_at.strftime("%Y-%m-%d %H:%M:%S")
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
                    assigned_at,
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
        self._refresh_live_ordered_assignment_table()
        self._refresh_device_usage_table(seats)
        self._refresh_live_communications()

    def _refresh_building_canvas(self, seats: list) -> None:
        self.building_canvas.delete("all")
        if not seats:
            return

        width = max(self.building_canvas.winfo_width(), 760)
        height = max(self.building_canvas.winfo_height(), 460)
        margin = max(8, width * 0.015)
        gap = max(12, width * 0.02)
        building_width = (width - 2 * margin - gap) / 2
        building_height = height - 50
        y0 = 25

        seat_map = {
            (seat.building, seat.floor, seat.zone, int(seat.seat_id.split("-")[-1])): (
                seat.status,
                self._seat_display_department(seat),
            )
            for seat in seats
        }

        for b_idx, building in enumerate(("B1", "B2")):
            bx0 = margin + b_idx * (building_width + gap)
            bx1 = bx0 + building_width
            by0 = y0
            by1 = by0 + building_height
            self.building_canvas.create_rectangle(bx0, by0, bx1, by1, outline="#666", width=2)
            self.building_canvas.create_text((bx0 + bx1) / 2, by0 - 12, text=f"Building {building}", font=("Arial", 11, "bold"))

            floor_height = (building_height - 24) / 2
            for f_idx, floor in enumerate(("F1", "F2")):
                fy0 = by0 + 12 + f_idx * floor_height
                fy1 = fy0 + floor_height - 8
                self.building_canvas.create_rectangle(bx0 + 8, fy0, bx1 - 8, fy1, outline="#999")
                self.building_canvas.create_text(bx0 + 40, fy0 + 10, text=floor, font=("Arial", 9, "bold"))

                zone_gap = 8
                zone_width = ((bx1 - bx0) - 24 - zone_gap) / 2
                for z_idx, zone in enumerate(("A", "B")):
                    zx0 = bx0 + 16 + z_idx * (zone_width + zone_gap)
                    zx1 = zx0 + zone_width
                    zy0 = fy0 + 20
                    zy1 = fy1 - 8

                    self.building_canvas.create_rectangle(zx0, zy0, zx1, zy1, outline="#888", width=2)
                    self.building_canvas.create_text((zx0 + zx1) / 2, zy0 - 8, text=f"Zone {zone}", fill="#444", font=("Arial", 8, "bold"))

                    self._draw_seat_squares(
                        building=building,
                        floor=floor,
                        zone=zone,
                        x0=zx0 + 3,
                        y0=zy0 + 3,
                        x1=zx1 - 3,
                        y1=zy1 - 3,
                        seat_map=seat_map,
                    )

    def _draw_seat_squares(
        self,
        building: str,
        floor: str,
        zone: str,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        seat_map: dict[tuple[str, str, str, int], tuple[str, str]],
    ) -> None:
        rows = 10
        cols = 10
        sq_w = (x1 - x0) / cols
        sq_h = (y1 - y0) / rows

        for seat_no in range(1, 101):
            row = (seat_no - 1) // cols
            col = (seat_no - 1) % cols
            sx0 = x0 + col * sq_w + 1
            sy0 = y0 + row * sq_h + 1
            sx1 = sx0 + sq_w - 2
            sy1 = sy0 + sq_h - 2
            status, department = seat_map.get((building, floor, zone, seat_no), ("available", ""))
            fill = self._dept_colors.get(department, "#9aa0a6") if status == "occupied" else "#e6e6e6"
            self.building_canvas.create_rectangle(sx0, sy0, sx1, sy1, fill=fill, outline="#c9c9c9")

    def _refresh_floor_table(self, seats: list) -> None:
        for item in self.floor_tree.get_children():
            self.floor_tree.delete(item)

        floors = Counter((seat.building, seat.floor, seat.status) for seat in seats)
        for building in ("B1", "B2"):
            for floor in ("F1", "F2"):
                occupied = floors[(building, floor, "occupied")]
                available = floors[(building, floor, "available")]
                self.floor_tree.insert("", "end", values=(building, floor, occupied, available))

    def _refresh_zone_table(self, seats: list) -> None:
        for item in self.zone_tree.get_children():
            self.zone_tree.delete(item)

        zones = Counter((seat.building, seat.floor, seat.zone, seat.status) for seat in seats)
        for building in ("B1", "B2"):
            for floor in ("F1", "F2"):
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

    def _refresh_live_ordered_assignment_table(self) -> None:
        for item in self.live_ordered_tree.get_children():
            self.live_ordered_tree.delete(item)

        def sort_key(row: tuple[str, ...]) -> tuple[str, str, str, str, str]:
            # department, team map, zone, floor, building
            return (row[3], row[4], row[8], row[7], row[6])

        for row in sorted(self.live_assignment_rows, key=sort_key):
            self.live_ordered_tree.insert("", "end", values=row)


    @staticmethod
    def _compute_power_saving_percent(rows, total_seats: int, zone_count: int) -> float:
        active_lights = sum(row.lights_on for row in rows)
        active_routers = sum(row.routers_on for row in rows)
        active_monitors = sum(row.monitors_on for row in rows)
        active_desktops = sum(row.desktop_cpus_on for row in rows)
        active_ac_vents = sum(row.ac_vents_on for row in rows)

        max_lights = zone_count * 10
        max_routers = zone_count
        max_monitors = total_seats
        max_desktops = total_seats
        max_ac_vents = zone_count * 3

        active_total = active_lights + active_routers + active_monitors + active_desktops + active_ac_vents
        max_total = max_lights + max_routers + max_monitors + max_desktops + max_ac_vents
        if max_total == 0:
            return 0.0
        return max(0.0, (1 - (active_total / max_total)) * 100.0)

    def _refresh_device_usage_table(self, seats: list) -> None:
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)

        rows = summarize_device_usage(seats)
        total_occupied = 0
        total_lights = 0
        total_routers = 0
        total_monitors = 0
        total_desktops = 0
        total_ac_vents = 0

        for usage in rows:
            total_occupied += usage.occupied_seats
            total_lights += usage.lights_on
            total_routers += usage.routers_on
            total_monitors += usage.monitors_on
            total_desktops += usage.desktop_cpus_on
            total_ac_vents += usage.ac_vents_on

            self.device_tree.insert(
                "",
                "end",
                values=(
                    usage.building,
                    usage.floor,
                    usage.zone,
                    usage.occupied_seats,
                    usage.lights_on,
                    usage.routers_on,
                    usage.monitors_on,
                    usage.desktop_cpus_on,
                    usage.ac_vents_on,
                ),
            )

        self.device_tree.insert(
            "",
            "end",
            values=(
                "TOTAL",
                "-",
                "-",
                total_occupied,
                total_lights,
                total_routers,
                total_monitors,
                total_desktops,
                total_ac_vents,
            ),
        )

        zone_count = len({(row.building, row.floor, row.zone) for row in rows})
        power_saving = self._compute_power_saving_percent(rows, total_seats=len(seats), zone_count=zone_count)
        self.device_summary_var.set(
            f"Totals -> occupied={total_occupied}, lights={total_lights}, routers={total_routers}, "
            f"monitors={total_monitors}, desktops={total_desktops}, ac_vents={total_ac_vents} | "
            f"Power saving: {power_saving:.2f}%"
        )

    def _refresh_live_communications(self) -> None:
        email_messages = self.process_orchestrator.email_notifier.sent_messages
        phone_messages = self.process_orchestrator.message_notifier.sent_messages
        iot_commands = self.process_orchestrator.iot_client.command_history

        if len(email_messages) != self._last_email_count:
            self.email_live_list.delete(0, tk.END)
            for index, message in enumerate(reversed(email_messages), start=1):
                self.email_live_list.insert(tk.END, f"{index:04d}. {message}")
            self._last_email_count = len(email_messages)

        if len(phone_messages) != self._last_phone_count:
            self.phone_live_list.delete(0, tk.END)
            for index, message in enumerate(reversed(phone_messages), start=1):
                self.phone_live_list.insert(tk.END, f"{index:04d}. {message}")
            self._last_phone_count = len(phone_messages)

        if len(iot_commands) != self._last_iot_count:
            self.iot_live_list.delete(0, tk.END)
            for index, command in enumerate(reversed(iot_commands), start=1):
                formatted = self._format_iot_command(command)
                self.iot_live_list.insert(tk.END, f"{index:04d}. {formatted}")
            self._last_iot_count = len(iot_commands)


    def run(self) -> None:
        self.root.mainloop()

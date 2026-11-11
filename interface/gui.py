"""Tkinter settings window with one tab per mode."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Sequence

from ..core.config_loader import ConfigLoader
from ..core.controller import Controller
from ..core.mode_profile import ModeProfile
from ..models.goal import Goal
from ..modes.cube.combination_generator import CombinationGenerator
from ..modes.cube.goal_config import CubeGoalConfig
from ..modes.cube.presenter import CubePresenter
from ..modes.cube.profile import DATA_DIR as CUBE_DATA_DIR, build_profile
from ..modes.cube.value_profile import ValueProfile
from ..modes.flame.goal_config import FlameGoalConfig
from ..modes.flame.presenter import FlamePresenter
from ..modes.flame.profile import DATA_DIR as FLAME_DATA_DIR
from ..modes.flame.profile import build_profile as build_flame_profile
from .logic_builder import LogicGroup

TAB_TITLES = ("Cube Settings", "Flame Settings")

# How often the GUI thread checks whether the worker posted its outcome.
POLL_INTERVAL_MS = 100


class ScrollFrame(ttk.Frame):
    """A vertically scrollable container; put content in ``inner``."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = ttk.Frame(self.canvas, padding=16)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Scroll only while the pointer is over this area."""
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            # Tk can report a transient widget (e.g. a combobox "popdown"
            # menu) that no longer exists, so the lookup fails.
            return
        while widget is not None:
            if widget is self:
                self.canvas.yview_scroll(-event.delta // 120, "units")
                return
            widget = widget.master


class SettingsWindow(tk.Tk):
    """Main window; each tab holds the settings for one mode."""

    def __init__(self) -> None:
        super().__init__()
        self.title("AutoCube")
        self.geometry("700x760")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._worker: Optional[threading.Thread] = None
        self._controller: Optional[Controller] = None
        # Button and status label of the tab that started the running session.
        self._run_ui: Optional[tuple[ttk.Button, ttk.Label]] = None
        # False while the goal describes stats the item can never roll.
        self._goal_valid = True
        self._flame_goal_valid = True
        # Written by the worker thread, read by the GUI thread.
        self._results: "queue.Queue[str]" = queue.Queue()

        # Larger tab headers so they are easy to click.
        ttk.Style(self).configure(
            "TNotebook.Tab", padding=(24, 12), font=("Segoe UI", 12)
        )

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        cube_scroll = ScrollFrame(self.notebook)
        self.flame_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(cube_scroll, text=TAB_TITLES[0])
        self.notebook.add(self.flame_tab, text=TAB_TITLES[1])
        self.cube_tab = cube_scroll.inner

        self._build_cube_tab()
        self._build_flame_tab()

    def _build_cube_tab(self) -> None:
        config_loader = ConfigLoader(CUBE_DATA_DIR)
        presenter = CubePresenter(config_loader)
        categories = config_loader.load_categories()
        if "categories" in categories:
            categories = categories["categories"]
        self._category_stats = categories

        self.cube_tab.columnconfigure(1, weight=1)
        self.cube_category = self._add_dropdown(
            self.cube_tab, 0, "Item Category", list(categories)
        )
        self.cube_level = self._add_dropdown(
            self.cube_tab, 1, "Item Level", presenter.get_level_range_options()
        )
        self.cube_target_tier = self._add_dropdown(
            self.cube_tab, 2, "Target Tier", config_loader.load_tiers(), "Legendary"
        )

        logic = ttk.LabelFrame(self.cube_tab, text="Goal Logic", padding=12)
        logic.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.logic_root = LogicGroup(
            logic,
            self._current_stats,
            self._value_options,
            on_change=self._refresh_summary,
        )
        self.logic_root.pack(fill="x")
        self.logic_summary = ttk.Label(logic, text="", wraplength=620)
        self.logic_summary.pack(fill="x", pady=(8, 0))
        self.logic_root.add_condition()

        self.cube_category.bind(
            "<<ComboboxSelected>>", lambda _event: self._on_category_changed()
        )
        self.cube_level.bind(
            "<<ComboboxSelected>>", lambda _event: self._on_values_changed()
        )
        self.cube_target_tier.bind(
            "<<ComboboxSelected>>", lambda _event: self._on_values_changed()
        )
        self.go_button = ttk.Button(
            self.cube_tab, text="GO", command=self._toggle_cube_run
        )
        self.go_button.grid(row=4, column=0, sticky="w", pady=(12, 0))
        self.status = ttk.Label(self.cube_tab, text="")
        self.status.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(12, 0))
        self._on_category_changed()

    def _build_flame_tab(self) -> None:
        config_loader = ConfigLoader(FLAME_DATA_DIR)
        self._flame_presenter = FlamePresenter(config_loader)
        self.flame_tab.columnconfigure(1, weight=1)

        self.flame_category = self._add_dropdown(
            self.flame_tab,
            0,
            "Item Category",
            self._flame_presenter.get_category_options(),
        )
        self.flame_attack_type = self._add_dropdown(
            self.flame_tab, 1, "Weapon Attack Type", ["Attack Power", "Magic ATT"]
        )
        self.flame_stat_combo = self._add_dropdown(
            self.flame_tab,
            2,
            "Stat Combo",
            self._flame_presenter.get_stat_combo_options(),
        )

        target = ttk.LabelFrame(self.flame_tab, text="Flame Score Target", padding=12)
        target.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        target.columnconfigure(1, weight=1)

        self.flame_score_mode = tk.StringVar(self, "better")
        self._flame_score_radios = [
            ttk.Radiobutton(
                target,
                text="Better than current score",
                variable=self.flame_score_mode,
                value="better",
                command=self._on_flame_target_changed,
            ),
            ttk.Radiobutton(
                target,
                text="At least",
                variable=self.flame_score_mode,
                value="at_least",
                command=self._on_flame_target_changed,
            ),
        ]
        self._flame_score_radios[0].grid(row=0, column=0, columnspan=2, sticky="w")
        self._flame_score_radios[1].grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.flame_score_value = ttk.Entry(target, width=10)
        self.flame_score_value.grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        self.flame_score_value.bind(
            "<KeyRelease>", lambda _event: self._refresh_flame_summary()
        )

        self.flame_summary = ttk.Label(self.flame_tab, text="", wraplength=620)
        self.flame_summary.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.flame_go_button = ttk.Button(
            self.flame_tab, text="GO", command=self._toggle_flame_run
        )
        self.flame_go_button.grid(row=5, column=0, sticky="w", pady=(12, 0))
        self.flame_status = ttk.Label(self.flame_tab, text="")
        self.flame_status.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(12, 0))

        self.flame_category.bind(
            "<<ComboboxSelected>>", lambda _event: self._on_flame_category_changed()
        )
        for box in (self.flame_attack_type, self.flame_stat_combo):
            box.bind(
                "<<ComboboxSelected>>", lambda _event: self._refresh_flame_summary()
            )
        self._on_flame_category_changed()

    def _on_flame_category_changed(self) -> None:
        """Only weapons use a specific attack stat."""
        self._update_flame_attack_state(True)
        self._refresh_flame_summary()

    def _on_flame_target_changed(self) -> None:
        """Enable the score entry only for an explicit target."""
        self._update_score_entry_state(True)
        self._refresh_flame_summary()

    def _update_flame_attack_state(self, enabled: bool) -> None:
        """Keep the attack type selectable for weapons only."""
        is_weapon = self.flame_category.get() == "Weapon"
        self.flame_attack_type.configure(
            state="readonly" if enabled and is_weapon else "disabled"
        )

    def _update_score_entry_state(self, enabled: bool) -> None:
        """Keep the score entry editable only in "at least" mode."""
        editable = enabled and self.flame_score_mode.get() == "at_least"
        self.flame_score_value.configure(state="normal" if editable else "disabled")

    def _build_flame_goal(self) -> Optional[FlameGoalConfig]:
        """Return the goal described by the flame settings, or None if invalid."""
        is_better = self.flame_score_mode.get() == "better"
        base_score: Optional[int] = None
        if not is_better:
            text = self.flame_score_value.get().strip()
            if not text.isdigit():
                return None
            base_score = int(text)

        combo = self._flame_presenter.get_stat_combo_by_name(
            self.flame_stat_combo.get()
        )
        return FlameGoalConfig(
            category=self.flame_category.get(),
            main_stat=combo["main"],
            secondary_stat=combo["secondary"],
            is_better=is_better,
            base_score=base_score,
            weapon_attack_type=(
                self.flame_attack_type.get()
                if self.flame_category.get() == "Weapon"
                else None
            ),
        )

    def _refresh_flame_summary(self) -> None:
        """Show the flame target, or ``Invalid`` when the score is malformed."""
        goal = self._build_flame_goal()
        self._flame_goal_valid = goal is not None
        if goal is None:
            self.flame_summary.configure(text="Invalid")
        else:
            combo = f"{goal.main_stat} / {goal.secondary_stat}"
            target = "> current" if goal.is_better else f">= {goal.base_score:g}"
            self.flame_summary.configure(text=f"Goal: Flame score {target} ({combo})")
        self._update_flame_go_state()

    def _update_flame_go_state(self) -> None:
        """Disable GO while the score target is not a non-negative integer.

        The tab is still being built the first time this runs, so the button
        may not exist yet.
        """
        button = getattr(self, "flame_go_button", None)
        if button is not None:
            button.configure(state="normal" if self._flame_goal_valid else "disabled")

    def _current_stats(self) -> Sequence[str]:
        """Return the stats allowed for the selected category and tier.

        Flat stats (cooldown reduction) keep their values as plain numbers
        instead of percentages and are available at every tier, while
        Legendary-only stats such as Critical Damage are hidden below
        Legendary.
        """
        stats = self._category_stats.get(self.cube_category.get(), [])
        if self.cube_target_tier.get() == "Legendary":
            return stats
        return [stat for stat in stats if not ValueProfile.is_legendary_only(stat)]

    def _value_options(self, stat: str) -> Sequence[str]:
        """Return the real line values offered for *stat*, e.g. ``12%``."""
        if not stat:
            return []
        suffix = "" if ValueProfile.is_flat_stat(stat) else "%"
        return [f"{value}{suffix}" for value in self._generator().line_values_for(stat)]

    def _generator(self) -> CombinationGenerator:
        """Return a generator for the selected level range and tier."""
        return CombinationGenerator(self.cube_level.get(), self.cube_target_tier.get())

    def _on_category_changed(self) -> None:
        """Repopulate the row stats for the selected category."""
        for row in self.logic_root.condition_rows():
            row.set_stats(self._current_stats())
            row.refresh_values()
        self._refresh_summary()

    def _on_values_changed(self) -> None:
        """Repopulate the row stats and values for the selected level and tier."""
        for row in self.logic_root.condition_rows():
            row.set_stats(self._current_stats())
            row.refresh_values()
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        """Show the compiled goal, or ``Invalid`` when the goal cannot be met."""
        root = self.logic_root.to_node()
        compiled = root.to_goal()
        if compiled is None:
            self._goal_valid = True
            self.logic_summary.configure(text="No goal set - stop at target rank")
        elif self._generator().generate_for_goal(compiled):
            self._goal_valid = True
            self.logic_summary.configure(text=f"Goal: {root.describe()}")
        else:
            self._goal_valid = False
            self.logic_summary.configure(text="Invalid")
        self._update_go_state()

    def _update_go_state(self) -> None:
        """Disable GO while the goal describes unreachable stat values.

        The first goal row is added while the tab is still being built, so the
        button may not exist yet.
        """
        button = getattr(self, "go_button", None)
        if button is not None:
            button.configure(state="normal" if self._goal_valid else "disabled")

    def _build_goal(self) -> CubeGoalConfig:
        """Return the goal described by the current settings and row tree."""
        compiled = self.logic_root.to_node().to_goal()
        goals = [compiled] if compiled is not None else []
        return CubeGoalConfig(
            category=self.cube_category.get(),
            target_rank=self.cube_target_tier.get(),
            goals=goals,
        )

    def _toggle_cube_run(self) -> None:
        """Start the cube controller, or ask the running session to stop."""
        self._toggle_run(
            lambda: self._build_goal() if self._goal_valid else None,
            build_profile,
            self.go_button,
            self.status,
        )

    def _toggle_flame_run(self) -> None:
        """Start the flame controller, or ask the running session to stop."""
        self._toggle_run(
            self._build_flame_goal,
            build_flame_profile,
            self.flame_go_button,
            self.flame_status,
        )

    def _toggle_run(
        self,
        goal_builder: Callable[[], Optional[Goal]],
        profile_builder: Callable[[], ModeProfile],
        button: ttk.Button,
        status: ttk.Label,
    ) -> None:
        """Start the controller for a tab, or stop the session it is running."""
        if self._controller is not None:
            # Never join here: the worker still needs this thread to finish its UI
            # reset, so blocking would freeze the window until the session ends.
            self._controller.stop()
            status.configure(text="Stopping…")
            button.configure(state="disabled")
            return
        goal = goal_builder()
        if goal is None:
            return
        self._start_run(goal, profile_builder, button, status)

    def _start_run(
        self,
        goal: Goal,
        profile_builder: Callable[[], ModeProfile],
        button: ttk.Button,
        status: ttk.Label,
    ) -> None:
        try:
            controller = Controller(profile_builder())
        except Exception as error:
            status.configure(text=f"Failed to start: {error}")
            return

        self._controller = controller
        self._run_ui = (button, status)
        self._set_all_settings_enabled(False)
        self.go_button.configure(state="disabled")
        self.flame_go_button.configure(state="disabled")
        button.configure(state="normal", text="STOP")
        status.configure(text="Running…")
        self._worker = threading.Thread(
            target=self._run_controller,
            args=(controller, goal),
            name="controller",
            daemon=True,
        )
        self._worker.start()
        self.after(POLL_INTERVAL_MS, self._poll_result)

    def _run_controller(self, controller: Controller, goal: Goal) -> None:
        """Worker thread: run the session, then post the outcome and return."""
        try:
            controller.run(goal)
            outcome_text = self._describe_outcome(controller, goal)
        except Exception as error:
            logging.getLogger(__name__).exception(
                "Controller session failed error: %s", error
            )
            outcome_text = f"Failed: {error}"
        self._results.put(outcome_text)

    def _poll_result(self) -> None:
        """GUI thread: pick up the posted outcome, or keep waiting for one."""
        try:
            outcome_text = self._results.get_nowait()
        except queue.Empty:
            self.after(POLL_INTERVAL_MS, self._poll_result)
            return
        self._finish_run(outcome_text)

    def _finish_run(self, outcome_text: str) -> None:
        """GUI thread: restore every control once the session has ended."""
        self._worker = None
        self._controller = None
        button, status = self._run_ui
        self._run_ui = None
        status.configure(text=outcome_text)
        button.configure(text="GO")
        self._set_all_settings_enabled(True)
        self._update_go_state()
        self._update_flame_go_state()

    @staticmethod
    def _describe_outcome(controller: Controller, goal: Goal) -> str:
        """Summarise why the session ended."""
        if controller.stop_requested:
            return "Stopped"
        equipment = controller.equipment
        if equipment is not None and goal.is_met(equipment):
            return "Goal met"
        return "Finished without meeting goal"

    def _set_all_settings_enabled(self, enabled: bool) -> None:
        """Enable or lock the inputs of both tabs during a session."""
        self._set_cube_settings_enabled(enabled)
        self._set_flame_settings_enabled(enabled)

    def _set_cube_settings_enabled(self, enabled: bool) -> None:
        """Enable or lock every cube input that shapes the next goal."""
        state = "readonly" if enabled else "disabled"
        for box in (
            self.cube_category,
            self.cube_level,
            self.cube_target_tier,
        ):
            box.configure(state=state)
        self.logic_root.set_enabled(enabled)

    def _set_flame_settings_enabled(self, enabled: bool) -> None:
        """Enable or lock every flame input that shapes the next goal."""
        state = "readonly" if enabled else "disabled"
        self.flame_category.configure(state=state)
        self.flame_stat_combo.configure(state=state)
        for radio in self._flame_score_radios:
            radio.configure(state="normal" if enabled else "disabled")
        self._update_flame_attack_state(enabled)
        self._update_score_entry_state(enabled)

    def _on_close(self) -> None:
        if self._controller is not None:
            self._controller.stop()
        worker = self._worker
        if worker is not None and worker.is_alive():
            # Blocking a short while is acceptable here: we are tearing down.
            worker.join(timeout=2)
        self.destroy()

    def _add_dropdown(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        values: Sequence[str],
        default: Optional[str] = None,
    ) -> ttk.Combobox:
        """Add a labelled readonly dropdown row and return the combobox."""
        box = ttk.Combobox(parent, values=values, state="readonly")
        if default is not None:
            box.set(default)
        elif values:
            box.set(values[0])

        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(0, 8))
        box.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))
        return box

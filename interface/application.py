"""Application entry point"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from ..core.config_loader import ConfigLoader
from ..core.controller import Controller
from ..core.mode_profile import ModeProfile
from ..models.goal import Goal
from ..modes.cube.flow import collect_goal as collect_cube_goal
from ..modes.cube.presenter import CubePresenter
from ..modes.cube.profile import build_profile as build_cube_profile
from ..modes.flame.flow import collect_goal as collect_flame_goal
from ..modes.flame.presenter import FlamePresenter
from ..modes.flame.profile import build_profile as build_flame_profile
from .base_presenter import BasePresenter
from .gui import SettingsWindow


@dataclass(frozen=True)
class ModeEntry:
    """Everything the application needs to run one mode."""

    build_profile: Callable[[], ModeProfile]
    build_presenter: Callable[[ConfigLoader], BasePresenter]
    collect_goal: Callable[[ConfigLoader, BasePresenter, Callable], Goal]


MODES = {
    "Cube": ModeEntry(build_cube_profile, CubePresenter, collect_cube_goal),
    "Flame": ModeEntry(build_flame_profile, FlamePresenter, collect_flame_goal),
}


class Application:
    """Main application that orchestrates the automation workflow."""

    def run_gui(self) -> None:
        """Open the settings window."""
        SettingsWindow().mainloop()

    def run(self, input_func: Callable = input) -> Goal:
        """Run the interactive CLI workflow for the selected mode."""

        mode_name = BasePresenter().get_selection(
            list(MODES), "Select Mode", input_func
        )
        entry = MODES[mode_name]
        profile = entry.build_profile()
        config_loader = ConfigLoader(profile.data_dir)
        presenter = entry.build_presenter(config_loader)

        if not config_loader.validate_data_files(profile.data_files):
            presenter.display_error(
                f"Critical Error: Missing data files in {profile.data_dir}."
            )
            sys.exit(1)

        try:
            goal_config = entry.collect_goal(config_loader, presenter, input_func)
        except ValueError as error:
            presenter.display_error(str(error))
            return None

        presenter.display_config(goal_config)
        self._run_phase(profile, presenter, goal_config, input_func)
        return goal_config

    def _run_phase(
        self,
        profile: ModeProfile,
        presenter: BasePresenter,
        goal_config: Goal,
        input_func: Callable,
    ) -> None:
        """Confirm and run the state machine."""
        presenter.display_start()
        choice = presenter.get_selection(
            ["Start", "Cancel"],
            f"Ready to begin {profile.name.lower()}?",
            input_func,
        )
        if choice == "Cancel":
            presenter.display_cancelled()
            return

        try:
            controller = Controller(profile)
        except Exception as error:
            presenter.display_error(f"Failed to initialize screen capture: {error}")
            return

        try:
            controller.run(goal_config, profile=True)
            presenter.display_result(goal_config, controller.equipment)
        except KeyboardInterrupt:
            controller.screen_capture.stop()
            presenter.display_cancelled()
        except Exception as error:
            controller.screen_capture.stop()
            presenter.display_error(f"{profile.name} session failed: {error}")

"""Flame (bonus stat) CLI presenter."""

from __future__ import annotations

from typing import Callable, List

from ...interface.base_presenter import BasePresenter


class FlamePresenter(BasePresenter):
    """Flame-specific menus and session messages."""

    def get_stat_combo_options(self) -> List[str]:
        """Return stat-combo labels (e.g. ``"STR / DEX"``) from config."""
        combos = self.config_loader.load_flame_config().get("stat_combos", [])
        return [combo["name"] for combo in combos]

    def get_stat_combo_by_name(self, name: str) -> dict:
        """Look up a stat-combo dict by its display name."""
        combos = self.config_loader.load_flame_config().get("stat_combos", [])
        for combo in combos:
            if combo["name"] == name:
                return combo
        return {"main": "STR", "secondary": "DEX"}

    def get_flame_score_target(self, input_func: Callable = input) -> int | str:
        """Prompt for the flame score target, or the "better than current" mode."""
        while True:
            print("\n--- Flame Score Target ---")
            print("1. Enter a specific flame score")
            print("2. Better than current score")
            choice = input_func("Select (1-2): ")
            if choice == "1":
                while True:
                    try:
                        value = int(input_func("Enter desired flame score (min 0): "))
                        if value >= 0:
                            return value
                        print("Please enter a non-negative value.")
                    except ValueError:
                        print("Please enter a valid number.")
            elif choice == "2":
                return "better"
            else:
                print("Invalid input. Please enter 1 or 2.")

    # -- Session messages ------------------------------------------------

    def display_start(self) -> None:
        print("\n" + "=" * 50)
        print("  Enhancement Session Starting")
        print("  The controller will now capture the game window")
        print("  and calculate flame score against your goal.")
        print("  Press Ctrl+C to abort at any time.")
        print("=" * 50)

    def display_result(self, goal_config, equipment=None) -> None:
        print("\n" + "=" * 50)
        print("  Enhancement session complete!")
        combo = f"{goal_config.main_stat} / {goal_config.secondary_stat}"
        if goal_config.is_better:
            target = f"> {goal_config.base_score} (better than current)"
        else:
            target = f">= {goal_config.base_score}"
        print(f"  Goal: Score {target} ({combo})")
        if equipment is not None:
            score = goal_config.scorer.calculate(
                equipment.lines,
                goal_config.main_stat,
                goal_config.secondary_stat,
                weapon_attack_type=goal_config.weapon_attack_type,
            )
            print(f"  Final score: {score:.1f}")
        print("=" * 50)

    def display_cancelled(self) -> None:
        print("\nEnhancement session cancelled by user.")

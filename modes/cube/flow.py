"""Cube mode configuration flow."""

from __future__ import annotations

from typing import Callable

from ...core.config_loader import ConfigLoader
from .combination_generator import CombinationGenerator
from .combination_goal import DumpAllGoal
from .goal_config import CubeGoalConfig
from .goal_config_builder import GoalConfigBuilder
from .presenter import CubePresenter

_PRIMARY_STATS = {"STR", "DEX", "INT", "LUK"}


def _allowed_stats(config_loader: ConfigLoader, category: str) -> list[str]:
    categories = config_loader.load_categories()
    if "categories" in categories:
        categories = categories["categories"]
    return categories.get(category, [])


def collect_goal(
    config_loader: ConfigLoader,
    presenter: CubePresenter,
    input_func: Callable = input,
) -> CubeGoalConfig:
    """Walk the user through the cube configuration steps."""
    selected_category = presenter.get_selection(
        presenter.get_category_options(), "Step 1: Select Item Category", input_func
    )
    selected_range = presenter.get_selection(
        presenter.get_level_range_options(),
        "Step 2: Select Item Level Range",
        input_func,
    )
    selected_stat = presenter.get_selection(
        presenter.get_stat_options_for_category(selected_category),
        "Step 3: Select Target Stat",
        input_func,
    )
    selected_tier = presenter.get_selection(
        presenter.get_tier_options(),
        "Step 4: Select Desired Tier",
        input_func,
    )

    allowed_stats = _allowed_stats(config_loader, selected_category)
    if selected_stat in _PRIMARY_STATS and "All Stats" in allowed_stats:
        filtered_stats = [selected_stat, "All Stats"]
    else:
        filtered_stats = [selected_stat]

    all_combinations = CombinationGenerator(
        selected_range, selected_tier
    ).generate_all_combinations(filtered_stats)

    print(f"\n{'=' * 60}")
    print(
        f"  All Possible Combinations for {selected_category} "
        f"({selected_range}, {selected_tier})"
    )
    print(f"  Target stat: {selected_stat}  |  Allowed: {', '.join(filtered_stats)}")
    print(f"  Total combinations: {len(all_combinations)}")
    print(f"{'=' * 60}")

    for index, combination in enumerate(all_combinations, 1):
        print(f"  {index:4d}. {combination}")

    goal_options = presenter.get_goal_options(
        selected_category, selected_stat, selected_range, selected_tier
    )
    goal_options.append("No filter (keep all)")
    selected_goal = presenter.get_selection(
        goal_options, f"Step 5: Filter Goal for {selected_category}", input_func
    )

    if selected_goal == "No filter (keep all)":
        return CubeGoalConfig(
            category=selected_category,
            target_rank=selected_tier,
            goals=[DumpAllGoal(stats=frozenset(filtered_stats))],
        )

    return GoalConfigBuilder(config_loader).build_goal_config(
        category=selected_category,
        target_stat=selected_stat,
        goal_selection=selected_goal,
        target_rank=selected_tier,
    )

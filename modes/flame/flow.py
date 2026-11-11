"""Flame mode configuration flow."""

from __future__ import annotations

from typing import Callable

from ...core.config_loader import ConfigLoader
from .goal_config import FlameGoalConfig
from .presenter import FlamePresenter


def collect_goal(
    config_loader: ConfigLoader,
    presenter: FlamePresenter,
    input_func: Callable = input,
) -> FlameGoalConfig:
    """Walk the user through the flame configuration steps."""
    selected_category = presenter.get_selection(
        presenter.get_category_options(), "Select Item Category", input_func
    )
    weapon_attack_type = presenter.get_selection(
        ["Attack Power", "Magic ATT"], "Select Weapon Attack Type", input_func
    )
    selected_combo_name = presenter.get_selection(
        presenter.get_stat_combo_options(),
        "Select Main / Secondary Stat Combo",
        input_func,
    )
    stat_combo = presenter.get_stat_combo_by_name(selected_combo_name)
    target = presenter.get_flame_score_target(input_func)

    is_better = target == "better"
    return FlameGoalConfig(
        category=selected_category,
        main_stat=stat_combo["main"],
        secondary_stat=stat_combo["secondary"],
        is_better=is_better,
        base_score=None if is_better else target,
        weapon_attack_type=weapon_attack_type,
    )

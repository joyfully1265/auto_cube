"""Cube (potential) CLI presenter."""

from __future__ import annotations

from typing import List

from ...interface.base_presenter import BasePresenter
from .value_profile import ValueProfile


class CubePresenter(BasePresenter):
    """Cube-specific menus and session messages."""

    def get_level_range_options(self) -> List[str]:
        return ["71-150", "151+"]

    def get_tier_options(self) -> List[str]:
        """Return the potential ranks, lowest first."""
        return self.config_loader.load_tiers()

    def get_stat_options_for_category(self, category: str) -> List[str]:
        categories = self.config_loader.load_categories()
        if "categories" in categories:
            categories = categories["categories"]
        allowed_stats = categories.get(category, [])
        filtered = [stat for stat in allowed_stats if stat != "All Stats"]
        # For weapon-like categories, only offer the primary damage stat;
        # secondary stats (Boss Damage, Ignore Defense) are auto-generated.
        primary_stats = {"Attack Power", "Magic ATT"}
        if primary_stats & set(filtered):
            return [stat for stat in filtered if stat in primary_stats]
        return filtered

    def get_goal_options(
        self, category: str, target_stat: str, level_range: str, tier: str = "Legendary"
    ) -> List[str]:
        """Return the curated goal presets for a category, stat and tier."""
        profile = ValueProfile.for_level_range(level_range, tier)
        categories = self.config_loader.load_categories()
        if "categories" in categories:
            categories = categories["categories"]
        allowed_stats = categories.get(category, [])

        if "Item Drop Rate" in allowed_stats:
            return self._get_accessory_goal_options(target_stat, profile)
        return self._get_damage_goal_options(
            target_stat, allowed_stats, profile, profile.max_single_stat
        )

    # -- Accessory goals (Drop / Meso / Stat) ---------------------------

    def _get_accessory_goal_options(
        self, target_stat: str, profile: ValueProfile
    ) -> List[str]:
        """Goal options for accessories (drop / meso / primary stat)."""
        goal_options = self._build_stat_sum_goals(target_stat, profile)
        goal_options.extend(
            [
                "1 Line Meso",
                "1 Line Drop",
                "1 Line Drop or Meso",
                "2 Line Meso",
                "2 Line Drop",
                "2 Line Drop or Meso",
                "3 Line Meso",
                "3 Line Drop",
                "1 Line Meso and 1 Line Stat",
                "1 Line Drop and 1 Line Stat",
                "1 Line Drop or Meso and 1 Line Stat",
            ]
        )
        return goal_options

    # -- Damage-category goals (Weapon / Emblem / Secondary) ------------

    @staticmethod
    def _achievable_sums(profile: ValueProfile) -> List[int]:
        """Return every achievable 1-3 line total for standard stats."""
        best = profile.line_values[0]
        worst = profile.line_values[-1]
        return sorted(
            {
                best * hits + worst * (lines - hits)
                for lines in range(1, 4)
                for hits in range(lines + 1)
            }
        )

    def _build_stat_sum_goals(
        self, target_stat: str, profile: ValueProfile
    ) -> List[str]:
        """Build tier-aware stat-sum labels such as ``'20%+ STR'``."""
        sums = self._achievable_sums(profile)
        canonical_tiers = [18, 21, 24, 30, 33, 36]
        labels: List[str] = []
        for threshold in canonical_tiers:
            achievable = [total for total in sums if total >= threshold]
            if achievable:
                label = f"{achievable[0]}%+ {target_stat}"
                if label not in labels:
                    labels.append(label)
        if sums:
            max_label = f"{sums[-1]}%+ {target_stat}"
            if max_label not in labels:
                labels.append(max_label)
        return labels

    def _get_damage_goal_options(
        self,
        target_stat: str,
        category_stats: List[str],
        profile: ValueProfile,
        max_stat: int,
    ) -> List[str]:
        """Goal options for damage-oriented categories."""
        damage_stats = {
            "Attack Power",
            "Magic ATT",
            "Boss Damage",
            "Ignore Defense",
        }
        has_any_damage = bool(set(category_stats) & damage_stats)
        has_boss = "Boss Damage" in category_stats
        has_ied = "Ignore Defense" in category_stats

        atk = "Atk"
        boss = "Boss"
        ied = "IED"

        if not has_any_damage:
            return self._build_stat_sum_goals(target_stat, profile)

        if has_boss and has_ied:
            useful_set = f"{atk} or {boss} or {ied}"
        elif has_ied:
            useful_set = f"{atk} or {ied}"
        else:
            useful_set = atk

        atk_boss_set = f"{atk} or {boss}"
        atk_ied_set = f"{atk} or {ied}"

        goal_options: List[str] = []

        # -- Stat sums (tier-aware) ---------------------------------------
        attack_sums = self._achievable_sums(profile)
        goal_options.extend(self._build_stat_sum_goals(target_stat, profile))

        # -- Attack with 1 line of IED ------------------------------------
        if has_ied:
            for threshold in (18, 21, 24):
                achievable = [total for total in attack_sums if total >= threshold]
                if achievable:
                    label = f"{achievable[0]}%+ {target_stat} and {ied}"
                    if label not in goal_options:
                        goal_options.append(label)

        # -- Any useful lines ---------------------------------------------
        for count in (1, 2, 3):
            goal_options.append(f"{count} Line {useful_set}")

        # -- Attack + any useful lines ------------------------------------
        if has_boss and has_ied:
            goal_options.append(f"1 Line {atk} with 1 Line {useful_set}")
            goal_options.append(f"1 Line {atk} with 2 Line {useful_set}")
            goal_options.append(f"2 Line {atk} with 1 Line {useful_set}")

        # -- Attack and Boss Damage ---------------------------------------
        if has_boss:
            for atk_lines, boss_lines in ((1, 1), (1, 2), (2, 1)):
                goal_options.append(
                    f"{atk_lines} Line {atk} + {boss_lines} Line {boss}"
                )
            for atk_value in (21, 24):
                for boss_value in (30, 35, 40):
                    if atk_value <= max_stat:
                        goal_options.append(
                            f"{atk_value}%+ {target_stat} and {boss_value}%+ {boss}"
                        )

        # -- Attack or Boss Damage ----------------------------------------
        if has_boss:
            for count in (1, 2, 3):
                goal_options.append(f"{count} Line {atk_boss_set}")

        # -- Attack and IED -----------------------------------------------
        if has_ied:
            for atk_lines, ied_lines in ((1, 1), (1, 2), (2, 1)):
                goal_options.append(f"{atk_lines} Line {atk} + {ied_lines} Line {ied}")
            for atk_value in (21, 24):
                for ied_value in (30, 35, 40):
                    if atk_value <= max_stat:
                        goal_options.append(
                            f"{atk_value}%+ {target_stat} and {ied_value}%+ {ied}"
                        )

        # -- Attack or IED ------------------------------------------------
        if has_ied:
            for count in (1, 2, 3):
                goal_options.append(f"{count} Line {atk_ied_set}")

        return goal_options

    # -- Session messages ------------------------------------------------

    def display_start(self) -> None:
        print("\n" + "=" * 50)
        print("  Cubing Session Starting")
        print("  The controller will now capture the game window")
        print("  and evaluate potentials against your goal.")
        print("  Press Ctrl+C to abort at any time.")
        print("=" * 50)

    def display_result(self, goal_config, equipment=None) -> None:
        print("\n" + "=" * 50)
        print("  Cubing session complete!")
        print(
            f"  Goal: {goal_config.goals[0].describe() if goal_config.goals else 'N/A'}"
        )
        print("=" * 50)

    def display_cancelled(self) -> None:
        print("\nCubing session cancelled by user.")

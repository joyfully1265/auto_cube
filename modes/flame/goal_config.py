"""Flame (bonus stat) goal configuration.

Flames have no rank and no combination semantics: the stop condition is a
weighted score derived from the stat lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ...models.equipment import Equipment
from ...models.goal import Goal
from .flame_scorer import FlameScorer


@dataclass
class FlameGoalConfig(Goal):
    """Configuration for a flame goal.

    Attributes:
        category: Item category (``"Armor"`` or ``"Weapon"``).
        main_stat: Primary stat (e.g. ``"STR"``).
        secondary_stat: Secondary stat (e.g. ``"DEX"``).
        is_better: Require score > base_score instead of >= base_score.
        base_score: Target score, or the baseline captured from the first read
            when ``is_better`` is set.
        weapon_attack_type: ``"Attack Power"`` or ``"Magic ATT"`` for weapons.
    """

    category: str
    main_stat: str
    secondary_stat: str
    is_better: bool = False
    base_score: Optional[float] = None
    weapon_attack_type: Optional[str] = None
    _scorer: Optional[FlameScorer] = field(
        default=None, init=False, repr=False, compare=False
    )

    @property
    def scorer(self) -> FlameScorer:
        """Lazily loaded scorer so config files are read at most once."""
        if self._scorer is None:
            self._scorer = FlameScorer.from_config_file()
        return self._scorer

    def __str__(self) -> str:
        lines = [
            "GoalConfig:",
            f"  Category: {self.category}",
            f"  Stat Combo: {self.main_stat} / {self.secondary_stat}",
        ]
        if self.is_better:
            lines.append("  Flame Score Target: Better than current")
        else:
            lines.append(f"  Flame Score Target: >= {self.base_score}")
        if self.weapon_attack_type is not None:
            lines.append(f"  Weapon Attack Type: {self.weapon_attack_type}")
        return "\n".join(lines)

    def describe(self) -> str:
        return str(self)

    def prepare(self, equipment: Equipment) -> None:
        """Capture the baseline score the first time "better" mode is used."""
        if self.is_better and self.base_score is None:
            self.base_score = self._score(equipment)

    def is_met(self, equipment: Equipment) -> bool:
        """Return True when the flame score satisfies the target."""
        if self.base_score is None:
            return False

        score = self._score(equipment)
        if self.is_better:
            return score > self.base_score
        return score >= self.base_score

    def describe_state(self, equipment: Equipment) -> str:
        """Per-line flame score breakdown for logging."""
        total, breakdown = self.scorer.calculate_and_format(
            equipment.lines,
            self.main_stat,
            self.secondary_stat,
            weapon_attack_type=self.weapon_attack_type,
        )
        return (
            "── Flame Score ──────────────────────────\n"
            + "\n".join(breakdown)
            + f"\n  Total: {total:.1f}"
            + f"  Goal: {self.base_score}"
            + "\n─────────────────────────────────────────"
        )

    def _score(self, equipment: Equipment) -> float:
        return self.scorer.calculate(
            equipment.lines,
            self.main_stat,
            self.secondary_stat,
            weapon_attack_type=self.weapon_attack_type,
        )

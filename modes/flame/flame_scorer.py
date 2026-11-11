"""FlameScorer model.

Calculates a weighted "flame score" from OCR'd stat lines using
class-specific conversion rates.  In the flame enhancement system,
stats are unpredictable (unlike cube potentials), so instead of
matching against specific combinations the program computes a
single score and compares it to a user-defined threshold.

Conversion rates (user-configurable via ``flame_conversion.json``)::

    Stat                  Rate
    ─────────────────────────────
    Main stat (flat)       × 1
    Secondary stat (flat)  ÷ 12
    All Stats %            × 10
    Attack Power / Magic ATT    × 3
    Boss Damage %          × 15
    Damage %               × 15
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Sequence, Tuple

from ...models.stat_line import StatLine


class FlameScorer:
    """Calculates flame scores from OCR'd stat lines.

    Usage::

        scorer = FlameScorer()
        score = scorer.calculate(equipment.lines, main_stat="STR", secondary_stat="DEX")
    """

    _DEFAULT_CONVERSION_RATES: Dict[str, float] = {
        "All Stats": 10.0,
        "Attack Power": 3.0,
        "Magic ATT": 3.0,
        "Boss Damage": 15.0,
        "Damage": 15.0,
    }
    _DEFAULT_SECONDARY_DIVISOR: float = 12.0
    _DEFAULT_MAIN_MULTIPLIER: float = 1.0

    def __init__(self, conversion_config: dict | None = None):
        """Initialise with optional custom conversion configuration.

        Args:
            conversion_config: A dict with optional keys ``conversion_rates``,
                ``secondary_divisor``, and ``main_stat_multiplier``.
                Falls back to defaults for any missing key.
        """
        rates = conversion_config.get("conversion_rates", {}) if conversion_config else {}
        self._conversion_rates: Dict[str, float] = {
            **self._DEFAULT_CONVERSION_RATES,
            **rates,
        }
        self._secondary_divisor: float = (
            conversion_config.get("secondary_divisor", self._DEFAULT_SECONDARY_DIVISOR)
            if conversion_config
            else self._DEFAULT_SECONDARY_DIVISOR
        )
        self._main_multiplier: float = (
            conversion_config.get("main_stat_multiplier", self._DEFAULT_MAIN_MULTIPLIER)
            if conversion_config
            else self._DEFAULT_MAIN_MULTIPLIER
        )

    # -- Public API -----------------------------------------------------------

    def calculate(
        self,
        lines: Sequence[StatLine],
        main_stat: str,
        secondary_stat: str,
        weapon_attack_type: str | None = None,
    ) -> float:
        """Compute the flame score for *lines*.

        Args:
            lines: OCR'd stat lines from equipment.
            main_stat: The character's primary stat (e.g. ``"STR"``).
            secondary_stat: The character's secondary stat (e.g. ``"DEX"``).
            weapon_attack_type: For weapons, ``"Attack Power"`` or
                ``"Magic ATT"`` to count only that attack type.
                ``None`` (armour or legacy) counts both.

        Returns:
            Weighted flame score as a float.
        """
        total = 0.0
        for line in lines:
            total += self._contribution(line, main_stat, secondary_stat, weapon_attack_type)
        return total

    def calculate_and_format(
        self,
        lines: Sequence[StatLine],
        main_stat: str,
        secondary_stat: str,
        weapon_attack_type: str | None = None,
    ) -> Tuple[float, List[str]]:
        """Same as :meth:`calculate` but also returns per-line breakdown strings."""
        breakdown: List[str] = []
        total = 0.0
        for line in lines:
            contrib = self._contribution(line, main_stat, secondary_stat, weapon_attack_type)
            total += contrib
            rate = self._describe_rate(line, main_stat, secondary_stat)
            breakdown.append(
                f"  {line.stat}: {line.value}{'%' if line.is_percent else ''} → "
                f"{contrib:.1f}  ({rate})"
            )
        return total, breakdown

    # -- Internal helpers -----------------------------------------------------

    def _contribution(
        self,
        line: StatLine,
        main_stat: str,
        secondary_stat: str,
        weapon_attack_type: str | None = None,
    ) -> float:
        """Return the contribution of a single stat line to the flame score."""
        stat = line.stat
        value = line.value

        # ── Weapon attack-type gating ──────────────────────────────────
        # If a weapon_attack_type is specified, the *other* attack stat
        # contributes 0 (e.g. a physical weapon should not count MA/green).
        if weapon_attack_type is not None:
            other_attack = (
                "Magic ATT" if weapon_attack_type == "Attack Power"
                else "Attack Power"
            )
            if stat == other_attack:
                return 0.0

        # Primary stat (main) – flat 1:1
        if stat == main_stat:
            return value * self._main_multiplier

        # Secondary stat – flat, divisor
        if stat == secondary_stat:
            return value / self._secondary_divisor

        # All Stats – % uses ×10 rate; flat uses ×1
        if stat == "All Stats":
            if line.is_percent:
                return value * self._conversion_rates.get("All Stats", 10.0)
            return value * self._main_multiplier

        # Stats with conversion rates (Attack Power, Boss Damage, Damage, etc.)
        rate = self._conversion_rates.get(stat)
        if rate is not None:
            return value * rate

        # Unknown / unmapped stat – contribute nothing
        return 0.0

    def _describe_rate(self, line: StatLine, main_stat: str, secondary_stat: str) -> str:
        """Return a human-readable description of the conversion rate applied."""
        stat = line.stat
        if stat == main_stat:
            return f"main stat ×{self._main_multiplier}"
        if stat == secondary_stat:
            return f"secondary stat ÷{self._secondary_divisor}"
        if stat == "All Stats" and not line.is_percent:
            return f"All Stats flat ×{self._main_multiplier}"
        rate = self._conversion_rates.get(stat)
        if rate is not None:
            return f"×{rate}"
        return "ignored"

    @classmethod
    def from_config_file(cls, path: str | None = None) -> FlameScorer:
        """Create a ``FlameScorer`` from a JSON config file.

        Args:
            path: Path to ``flame_conversion.json``.  If ``None``, resolves
                the default location relative to this source file.
        """
        if path is None:
            path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "data",
                "flame",
                "flame_conversion.json",
            )
        try:
            with open(path, "r") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config = {}
        return cls(conversion_config=config)
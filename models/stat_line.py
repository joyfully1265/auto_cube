"""StatLine model.

This file defines the :class:`StatLine` dataclass which represents a single
stat line on a piece of equipment. It is extracted from the original
``stat.py`` module so that each model lives in its own file.
"""

from dataclasses import dataclass

# Canonical name of the flat cooldown-reduction stat.  The seconds of
# reduction are stored as the line value, never inside the stat name.
COOLDOWN_STAT = "Skill Cooldowns"


@dataclass
class StatLine:
    """Represents a single cube line with stat, value and percent flag.

    The string representation is ``"{stat}: {value}%"``. For flat stats
    (is_percent=False), no percent sign is appended.
    """

    stat: str
    value: int
    is_percent: bool = True

    def __str__(self) -> str:
        percent_marker = "%" if self.is_percent else ""
        return f"{self.stat}: {self.value}{percent_marker}"

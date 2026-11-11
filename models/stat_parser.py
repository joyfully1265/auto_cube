"""Stat line parser for converting OCR text to StatLine objects.

Merges the potential (cube) and bonus-stat (flame) parsing rules:

* Tesseract OCR confusion handling (``B``/``6``/``8``, ``I``/``L``/``1``).
* Signed flat stats (e.g. cooldown ``-2``) as well as percentages.
* Trash potential lines whose value leads the text (e.g. ``20% chance to
  ignore 26 damage``).
* Rank extraction for potential windows.
* PaddleOCR token-based parsing for engines that do not preserve line layout.
"""

from __future__ import annotations

import re
from typing import List, Optional

from .stat_line import COOLDOWN_STAT, StatLine

# Mapping of common OCR variations to standardized stat names
STAT_NAME_MAPPINGS = {
    # Attack stats
    "attack power": "Attack Power",
    "att": "Attack Power",
    "atk": "Attack Power",
    "magic attack": "Magic ATT",
    "magic att": "Magic ATT",
    "mat": "Magic ATT",
    "matk": "Magic ATT",
    # Damage stats
    "boss damage": "Boss Damage",
    "boss dmg": "Boss Damage",
    "boss": "Boss Damage",
    "damage": "Damage",
    "dmg": "Damage",
    # Defense stats
    "ignore defense": "Ignore Defense",
    "ied": "Ignore Defense",
    "defense ignore": "Ignore Defense",
    # Primary stats
    "str": "STR",
    "dex": "DEX",
    "int": "INT",
    "luk": "LUK",
    "all stats": "All Stats",
    "all stat": "All Stats",
    # Other common stats
    "critical rate": "Critical Rate",
    "critical damage": "Critical Damage",
    "crit rate": "Critical Rate",
    "crit dmg": "Critical Damage",
    "item drop rate": "Item Drop Rate",
    "mesos obtained": "Mesos Obtained",
    "skill cooldowns": COOLDOWN_STAT,
    "skill cooldown": COOLDOWN_STAT,
    "defense": "Defense",
    "speed": "Speed",
    "jump": "Jump",
    "maxhp": "Max HP",
    "max hp": "Max HP",
    "maxmp": "Max MP",
    "max mp": "Max MP",
    "elrequirement": "Reduced Level Requirement",
    "el requirement": "Reduced Level Requirement",
    # Trash potential lines. Parsing them keeps a window whose lines are all
    # junk from being mistaken for a failed OCR read. No goal targets these
    # names, so their values can never affect a goal decision.
    "chance to ignore damage": "Chance to Ignore Damage",
    "hp recovery items and skills efficiency": (
        "HP Recovery Items and Skills Efficiency"
    ),
}

# Stat-specific percent values that OCR can mangle due to B/6/8 visual
# confusion. Keyed by the normalized stat name.
# - "All Stats" never rolls 8% (valid values are 3/4/6/7/9/10).
# - "Critical Damage" can only be 8% (6% is not a valid roll).
_OCR_VALUE_BY_STAT = {
    "All Stats": 6,
    "Critical Damage": 8,
}

# Trash potential lines lead with their value, e.g. "20% chance to ignore 26
# damage when attacked". Tokenising such a line would turn the description into
# bogus stats like "To Ignore: 26", so both parsers treat it as a whole line.
_LEADING_PERCENT_LINE = re.compile(r"^([\dB]+)%\s*(.+)$")

# Cooldown lines put a unit after the value ("Skill Cooldowns -2 sec"), so the
# number is not the last token.  OCR may also split the name and the value into
# separate boxes, leaving a bare "-2 sec" fragment.
_COOLDOWN_LINE = re.compile(
    r"(?:skill\s+cooldowns?\s*:?\s*)?([+-]?\s*\d+)\s*(?:sec|secs|seconds)\b",
    re.IGNORECASE,
)


def _ocr_confusion_candidates(word: str) -> List[str]:
    """Generate variants of a word swapping common OCR-confusable characters."""
    confusions = {
        "l": "i",
        "1": "i",
        "o": "0",
        "0": "o",
    }
    candidates = [""]
    for ch in word:
        replacements = confusions.get(ch, ch)
        candidates = [prefix + r for prefix in candidates for r in replacements]
    return candidates


def normalize_stat_name(stat_name: str) -> str:
    """Normalize a stat name to a standard format."""
    normalized = stat_name.lower().strip()
    if normalized in STAT_NAME_MAPPINGS:
        return STAT_NAME_MAPPINGS[normalized]

    # Try matching each word with common OCR confusions (I/L/1, O/0) to a
    # known stat name. This catches cases like "Ltem" -> "Item".
    for word in normalized.split():
        for candidate in _ocr_confusion_candidates(word):
            if candidate in STAT_NAME_MAPPINGS:
                return STAT_NAME_MAPPINGS[candidate]

    return stat_name.title()


def _extract_stat_name_candidate(stat_name_candidate: str) -> str:
    """Extract a clean stat name from an OCR candidate phrase."""
    phrase = stat_name_candidate.strip()
    if phrase.lower().startswith("b "):
        phrase = phrase[2:].strip()

    lower = phrase.lower()
    for key in sorted(STAT_NAME_MAPPINGS.keys(), key=len, reverse=True):
        if lower.endswith(key):
            return normalize_stat_name(key)
        if key in lower:
            start = lower.rfind(key)
            return normalize_stat_name(lower[start : start + len(key)])

    return normalize_stat_name(phrase)


def _normalize_trash_description(description: str) -> str:
    """Derive a stat name from the trailing text of a trash potential line.

    Numbers embedded in the description are noise (e.g. the damage amount in
    "20% chance to ignore 26 damage"), and single-character OCR fragments from
    a clipped line are dropped.
    """
    words = [
        word
        for word in re.sub(r"\d+", " ", description.lower()).split()
        if len(word) > 1
    ]
    return _extract_stat_name_candidate(" ".join(words))


def _resolve_ocr_value(stat_name: str, raw_value: str) -> int:
    """Resolve an OCR-mangled numeric value to the intended integer.

    OCR frequently reads 'B' in place of '6' or '8' on small game text. The
    correction uses the stat's only legal value when the read is ambiguous and
    fixes values that are impossible for a given stat.
    """
    raw_value = raw_value.strip().lstrip("+-")
    if not raw_value.isdigit():
        return _OCR_VALUE_BY_STAT.get(stat_name, 6)

    value = int(raw_value)

    if stat_name == "All Stats" and value == 8:
        return 6
    if stat_name == "Critical Damage" and value == 6:
        return 8

    return value


def _parse_cooldown_line(line: str) -> Optional[StatLine]:
    """Parse a cooldown line whose value is followed by a unit.

    The game renders cooldown reduction as e.g. ``Skill Cooldowns -2 sec``, so
    the number is not at the end of the line.  A bare ``-2 sec`` fragment is
    accepted as well because PaddleOCR can split the name and value into
    separate boxes.  The line value is the seconds of reduction, always
    positive (``-2 sec`` becomes ``2``).
    """
    match = _COOLDOWN_LINE.search(line)
    if match is None:
        return None

    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        return None

    return StatLine(stat=COOLDOWN_STAT, value=int(digits), is_percent=False)


def parse_stat_line(line: str) -> Optional[StatLine]:
    """Parse a single OCR text line into a StatLine object.

    Expected formats:
    - "Attack Power: 15%" (percent stat)
    - "STR +5%" (alternative format with plus)
    - "Boss Damage 10%" (without colon)
    - "luk: +3%" (colon with plus)
    - "dex +6" (flat stat without percent)
    - "20% chance to ignore 26 damage" (trash line with a leading value)
    """
    if not line or not line.strip():
        return None

    line = line.strip()

    # Strip common OCR artifacts like "B " prefix
    if line.startswith("B "):
        line = line[2:]

    # Cooldown lines carry a unit after their value; handle them before the
    # value-at-end patterns below.
    cooldown_line = _parse_cooldown_line(line)
    if cooldown_line is not None:
        return cooldown_line

    # Pattern 1: "Stat Name: Value%"
    match = re.match(r"^(.+?):\s*([\dB]+)%", line)
    if match:
        stat_name = normalize_stat_name(match.group(1))
        value = _resolve_ocr_value(stat_name, match.group(2))
        return StatLine(stat=stat_name, value=value)

    # Pattern 1b: "Stat Name: +Value%" (colon with plus)
    match = re.match(r"^(.+?):\s*\+([\dB]+)%", line)
    if match:
        stat_name = normalize_stat_name(match.group(1))
        value = _resolve_ocr_value(stat_name, match.group(2))
        return StatLine(stat=stat_name, value=value)

    # Pattern 2: "Stat Name +Value%" (alternative format)
    match = re.match(r"^(.+?)\s*\+([\dB]+)%", line)
    if match:
        stat_name = normalize_stat_name(match.group(1))
        value = _resolve_ocr_value(stat_name, match.group(2))
        return StatLine(stat=stat_name, value=value)

    # Pattern 2b: "Stat Name +Value" (flat stat without percent)
    match = re.match(r"^(.+?)\s*(\+|\-)([\dB]+)", line)
    if match:
        stat_name = _extract_stat_name_candidate(match.group(1))
        value = _resolve_ocr_value(stat_name, match.group(3))
        return StatLine(stat=stat_name, value=value, is_percent=False)

    # Pattern 3: "Stat Name Value%" (without colon or plus)
    match = re.match(r"^(.+?)\s+([\dB]+)%", line)
    if match:
        stat_name = normalize_stat_name(match.group(1))
        value = _resolve_ocr_value(stat_name, match.group(2))
        return StatLine(stat=stat_name, value=value)

    # Pattern 4: "Value% <description>" (trash lines where the percentage leads
    # the text, e.g. "20% chance to ignore 26 damage when attacked")
    match = _LEADING_PERCENT_LINE.match(line)
    if match:
        stat_name = _normalize_trash_description(match.group(2))
        value = _resolve_ocr_value(stat_name, match.group(1))
        return StatLine(stat=stat_name, value=value)

    return None


def parse_stat_lines(lines: List[str]) -> List[StatLine]:
    """Parse multiple OCR text lines into StatLine objects.

    Unparseable lines are skipped so a single OCR glitch does not discard a
    otherwise valid read.
    """
    stat_lines = []
    for line in lines:
        stat_line = parse_stat_line(line)
        if stat_line is not None:
            stat_lines.append(stat_line)
    return stat_lines


def _build_paddle_stat_line(name_tokens: List[str], value: re.Match) -> StatLine:
    """Build a StatLine from stat name tokens and an OCR value match."""
    stat_name = _extract_stat_name_candidate(" ".join(name_tokens))
    resolved_value = _resolve_ocr_value(stat_name, value.group(1))
    is_percent = value.group(2) == "%"
    return StatLine(
        stat=stat_name,
        value=resolved_value,
        is_percent=is_percent,
    )


def parse_stat_lines_paddle(lines: List[str]) -> List[StatLine]:
    """Parse OCR text lines using token-based parsing.

    PaddleOCR returns detected text fragments that do not always preserve the
    "Stat: Value" layout, so each line is tokenised into name and value
    candidates. Both "STR +28" and "+28 STR" orders are supported.
    """
    stat_lines = []
    value_pattern = re.compile(r"^([+-]?\d+(?:\.\d+)?)(%?)$")
    token_pattern = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*|[+-]?\d+(?:\.\d+)?%?")

    for line in lines:
        # Cooldown values are followed by a unit, so tokenising them would
        # turn the unit into a bogus stat; parse the line as a whole instead.
        cooldown_line = _parse_cooldown_line(line)
        if cooldown_line is not None:
            stat_lines.append(cooldown_line)
            continue

        # A leading percentage value marks a trash description; parse the line
        # as a whole so its words are not split into bogus stats.
        if _LEADING_PERCENT_LINE.match(line):
            stat_line = parse_stat_line(line)
            if stat_line is not None:
                stat_lines.append(stat_line)
                continue

        stat_name_tokens: List[str] = []
        pending_value = None
        for tok in token_pattern.findall(line):
            value = value_pattern.match(tok)
            if value is None:
                stat_name_tokens.append(tok)
                if pending_value is not None:
                    stat_lines.append(
                        _build_paddle_stat_line(stat_name_tokens, pending_value)
                    )
                    stat_name_tokens = []
                    pending_value = None
            elif stat_name_tokens:
                stat_lines.append(_build_paddle_stat_line(stat_name_tokens, value))
                stat_name_tokens = []
            else:
                pending_value = value

    return stat_lines


def extract_rank(lines: List[str]) -> Optional[str]:
    """Extract the rank from OCR text lines.

    Looks for rank keywords like "Legendary", "Epic", "Unique".  Rare is
    not a supported rank and is therefore ignored.
    """
    rank_keywords = ["legendary", "epic", "unique"]

    for line in lines:
        line_lower = line.lower().strip()
        for rank in rank_keywords:
            if rank in line_lower:
                return rank.title()

    return None

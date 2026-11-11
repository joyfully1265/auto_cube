"""Cube (potential) window layout: template names and region offsets."""

from ...core.window_analyzer import WindowOffsets

# Reset button: relative to the reset-button anchor
RESET_BUTTON_OFFSET = {
    "x_offset": 0,
    "y_offset": 0,
    "width": 84,
    "height": 25,
}

# Reset purple button: relative to the purple reset-button anchor
RESET_PURPLE_OFFSET = {
    "x_offset": 0,
    "y_offset": 0,
    "width": 81,
    "height": 28,
}

# Blue window: stats sit below the enhance anchor
BLUE_STATS_REGION = {
    "x_offset": 253,
    "y_offset": 280,
    "width": 285,
    "height": 98,
}

# Purple window: stats sit directly below the AFTER label
PURPLE_STATS_REGION = {
    "x_offset": 23,
    "y_offset": 70,
    "width": 180,
    "height": 80,
}

# Rank strip above the stats
RANK_REGION_BLUE = {
    "x_offset": 265,
    "y_offset": 250,
    "width": 160,
    "height": 32,
}

RANK_REGION_PURPLE = {
    "x_offset": 28,
    "y_offset": 22,
    "width": 160,
    "height": 24,
}

TEMPLATES = {
    "after": "after.PNG",
    "enhance": "enhance_window.PNG",
    "reset_button": "reset.PNG",
    "reset_button_purple": "reset_purple.PNG",
}

OFFSETS = WindowOffsets(
    after_stats_region=PURPLE_STATS_REGION,
    purple_rank_region=RANK_REGION_PURPLE,
    blue_stats_region=BLUE_STATS_REGION,
    blue_rank_region=RANK_REGION_BLUE,
    reset_button_offset=RESET_BUTTON_OFFSET,
    reset_purple_offset=RESET_PURPLE_OFFSET,
    templates=TEMPLATES,
)

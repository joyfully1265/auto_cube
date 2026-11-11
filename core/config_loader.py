import json
import os
from typing import Any, Dict, List, Sequence


class ConfigLoader:
    """Handles loading configuration data from JSON files."""

    def __init__(self, data_dir: str = None):
        """Initialize with optional custom data directory."""
        self.data_dir = data_dir or os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "data")
        )

    def load_config(self, filename: str) -> Any:
        """
        Load configuration from the data directory.
        Returns data or empty list/dict if file doesn't exist.
        """
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        try:
            with open(path, "r") as f:
                data = json.load(f)
                # If the JSON is a list, return it directly.
                if isinstance(data, list):
                    return data
                # If the JSON is a dict, return it directly – callers can decide which key they need.
                if isinstance(data, dict):
                    return data
                # Fallback – unexpected type.
                return []
        except json.JSONDecodeError:
            print(f"Error: {filename} is not valid JSON.")
            return []

    def load_categories(self) -> Dict[str, List[str]]:
        """Load item categories configuration."""
        return self.load_config("item_category.json") or {}

    def load_stats(self) -> List[str]:
        """Load available stats list."""
        return self.load_config("stats.json") or []

    def load_tiers(self) -> List[str]:
        """Load tier configuration."""
        return self.load_config("tier.json") or []

    def load_flame_config(self) -> dict:
        """Load flame-score conversion configuration."""
        config = self.load_config("flame_conversion.json")
        if isinstance(config, dict):
            return config
        return {}

    def validate_data_files(
        self, required: Sequence[str] = ("item_category.json", "stats.json")
    ) -> bool:
        """Check if all required data files exist and are valid."""
        return all(
            os.path.exists(os.path.join(self.data_dir, filename))
            for filename in required
        )

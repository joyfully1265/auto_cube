"""CLI helpers shared by every mode presenter."""

from __future__ import annotations

from typing import Callable, List, Optional

from ..core.config_loader import ConfigLoader


class BasePresenter:
    """Handles CLI interaction shared by all modes."""

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        self.config_loader = config_loader or ConfigLoader()

    def get_selection(
        self, options: List[str], prompt: str, input_func: Callable = input
    ) -> str:
        """Print a numbered menu and return the selected option."""
        print(f"\n--- {prompt} ---")
        for index, option in enumerate(options, 1):
            print(f"{index}. {option}")

        while True:
            try:
                choice = int(input_func(f"Select (1-{len(options)}): "))
                if 1 <= choice <= len(options):
                    return options[choice - 1]
            except ValueError:
                pass
            print("Invalid input. Please enter a number.")

    def display_config(self, config) -> None:
        """Display the generated configuration."""
        print("\n[Interface Focus] Configuration generated successfully:")
        print(str(config))

    def display_error(self, message: str) -> None:
        print(f"Error: {message}")

    def display_success(self, message: str) -> None:
        print(f"Success: {message}")

    def get_category_options(self) -> List[str]:
        """Return the item categories from the mode's data directory."""
        categories = self.config_loader.load_categories()
        if "categories" in categories:
            categories = categories["categories"]
        return list(categories.keys())

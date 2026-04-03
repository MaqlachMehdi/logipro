"""Base class for all loss visualisation modes."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseVisualisation(ABC):
    """Every visualisation mode must subclass this and implement the two methods."""

    name: str  # short identifier (used in file names, logs)
    label: str  # human-readable label shown in the questionary menu

    @abstractmethod
    def prompt_parameters(self) -> dict:
        """Interactively ask the user for mode-specific parameters.

        Returns a dict that will be forwarded to ``run``.
        """

    @abstractmethod
    def run(self, data_file: str, output_dir: str, **params) -> str:
        """Execute the visualisation and return the path to the generated HTML."""

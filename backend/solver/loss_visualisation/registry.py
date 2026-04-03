"""Central registry of all available visualisation modes.

To add a new mode, import its class and append it to VISUALISATIONS.
"""

from __future__ import annotations

from loss_visualisation.base import BaseVisualisation
from loss_visualisation.visualisations.edge_similarity import EdgeSimilarity
from loss_visualisation.visualisations.time_over_consumption import TimeOverConsumption

VISUALISATIONS: list[BaseVisualisation] = [
    TimeOverConsumption(),
    EdgeSimilarity(),
]


def get_choices() -> list[tuple[str, BaseVisualisation]]:
    """Return (label, instance) pairs for use in questionary."""
    return [(v.label, v) for v in VISUALISATIONS]

"""Entry point for the loss_visualisation module.

Usage:
    python -m loss_visualisation.main
    # or
    python backend/solver/loss_visualisation/main.py
"""

from __future__ import annotations

import os
import sys

import questionary

# Ensure the solver package is importable
_SOLVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SOLVER_DIR not in sys.path:
    sys.path.insert(0, _SOLVER_DIR)

from loss_visualisation.registry import get_choices

DEFAULT_DATA_FILE = os.path.join(_SOLVER_DIR, "vrppd_data.json")
DEFAULT_OUTPUT_DIR = os.path.join(_SOLVER_DIR, "solution")


def main() -> int:
    choices = get_choices()
    selected = questionary.select(
        "Which visualisation do you want to run?",
        choices=[questionary.Choice(title=label, value=vis) for label, vis in choices],
    ).ask()
    if selected is None:
        return 1

    data_file = questionary.path(
        "Path to VRPPD data file:",
        default=DEFAULT_DATA_FILE,
    ).ask()
    if data_file is None:
        return 1

    params = selected.prompt_parameters()
    output_path = selected.run(data_file=data_file, output_dir=DEFAULT_OUTPUT_DIR, **params)
    print(f"\nDone! Open {output_path} in a browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

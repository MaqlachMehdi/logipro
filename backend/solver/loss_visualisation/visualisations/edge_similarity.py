"""Visualisation: Edge similarity between S(alpha) and S(alpha_0).

For each alpha_0 reference and each alpha in the sweep grid:
  1. Solve S(alpha) and S(alpha_0)
  2. Extract the binary edge decisions e_vjk (0 or 1) for each vehicle
  3. Compute similarity = |edges(alpha) ∩ edges(alpha_0)| / |edges(alpha) ∪ edges(alpha_0)|
     (Jaccard index over the set of active edges)
  4. Plot similarity as a function of alpha, one curve per alpha_0
"""

from __future__ import annotations

import json
import os

import questionary

from loss_visualisation.base import BaseVisualisation
from loss_visualisation.html_renderer import wrap_plotly_page, write_html
from loss_visualisation.solver_utils import load_data, solve_and_extract

_COLORS = [
    "#5b9aff", "#ff6b6b", "#4ecdc4", "#ffe66d", "#a78bfa",
    "#ff9f43", "#ee5a9f", "#26de81", "#45aaf2", "#fed330",
]


def _edge_set(active_edges: dict[tuple, float]) -> set[tuple]:
    """Return the set of (start, end, vehicle) keys that are active."""
    return set(active_edges.keys())


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity: |A ∩ B| / |A ∪ B|.  Returns 1.0 if both empty."""
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 1.0


class EdgeSimilarity(BaseVisualisation):
    name = "edge_similarity"
    label = "Edge Similarity: Jaccard(S(alpha), S(alpha_0))"

    def prompt_parameters(self) -> dict:
        n_str = questionary.text(
            "How many alpha_0 values do you want to compare?",
            default="1",
            validate=lambda v: "Must be a positive integer" if not v.isdigit() or int(v) < 1 else True,
        ).ask()
        if n_str is None:
            raise KeyboardInterrupt
        n = int(n_str)

        alpha_0s: list[float] = []
        for i in range(n):
            label = f"Enter alpha_0 #{i+1} (between 0 and 1):" if n > 1 else "Enter alpha_0 (between 0 and 1):"
            default = f"{i / max(n - 1, 1):.2f}" if n > 1 else "0.5"
            val = questionary.text(
                label,
                default=default,
                validate=lambda v: "Must be a float between 0 and 1" if not _is_valid_alpha(v) else True,
            ).ask()
            if val is None:
                raise KeyboardInterrupt
            alpha_0s.append(float(val))

        step_str = questionary.text(
            "Alpha sweep step size:",
            default="0.1",
        ).ask()
        if step_str is None:
            raise KeyboardInterrupt

        time_limit_str = questionary.text(
            "Solver time limit per alpha (seconds):",
            default="120",
        ).ask()
        if time_limit_str is None:
            raise KeyboardInterrupt

        return {
            "alpha_0s": alpha_0s,
            "step": float(step_str),
            "time_limit": int(time_limit_str),
        }

    def run(self, data_file: str, output_dir: str, **params) -> str:
        alpha_0s: list[float] = params["alpha_0s"]
        step: float = params.get("step", 0.1)
        time_limit: int = params.get("time_limit", 120)

        data = load_data(data_file)

        # -- build alpha grid --
        n_points = int(round(1.0 / step)) + 1
        alphas = [round(i * step, 10) for i in range(n_points)]

        # -- solve each reference alpha_0 --
        refs: list[tuple[float, set[tuple]]] = []
        for a0 in alpha_0s:
            print(f"\n{'='*60}")
            print(f"Solving reference S(alpha_0={a0}) ...")
            print(f"{'='*60}")
            status_0, _, time_0, _, edges_0 = solve_and_extract(
                data,
                alpha_time=a0,
                alpha_distance=1.0 - a0,
                alpha_load=0.0,
                time_limit=time_limit,
                data_file=data_file,
            )
            edge_set_0 = _edge_set(edges_0)
            print(f"  -> {status_0} in {time_0:.1f}s | {len(edge_set_0)} active edges")
            refs.append((a0, edge_set_0))

        # -- solve for each alpha in the grid --
        grid_results: list[tuple[float, set[tuple]] | None] = []
        for idx, alpha in enumerate(alphas):
            print(f"\n[{idx + 1}/{n_points}] Solving S(alpha={alpha:.4f}) ...")
            try:
                status, _, st, _, edges = solve_and_extract(
                    data,
                    alpha_time=alpha,
                    alpha_distance=1.0 - alpha,
                    alpha_load=0.0,
                    time_limit=time_limit,
                    data_file=data_file,
                )
            except RuntimeError as e:
                print(f"  -> FAILED: {e}")
                grid_results.append(None)
                continue

            edge_set = _edge_set(edges)
            print(f"  -> {status} in {st:.1f}s | {len(edge_set)} active edges")
            grid_results.append((alpha, edge_set))

        # -- build one trace per alpha_0 --
        traces_js_parts: list[str] = []
        shapes_js_parts: list[str] = []
        annotations_js_parts: list[str] = []

        for curve_idx, (a0, edge_set_0) in enumerate(refs):
            color = _COLORS[curve_idx % len(_COLORS)]
            curve_alphas: list[float] = []
            curve_similarities: list[float] = []
            curve_meta: list[dict] = []

            for res in grid_results:
                if res is None:
                    continue
                alpha, edge_set = res
                similarity = _jaccard(edge_set, edge_set_0)
                n_common = len(edge_set & edge_set_0)
                n_union = len(edge_set | edge_set_0)

                curve_alphas.append(alpha)
                curve_similarities.append(similarity)
                curve_meta.append({
                    "alpha": alpha,
                    "similarity": similarity,
                    "n_common": n_common,
                    "n_union": n_union,
                    "n_edges_alpha": len(edge_set),
                    "n_edges_alpha0": len(edge_set_0),
                })

            traces_js_parts.append(f"""{{
      x: {json.dumps(curve_alphas)},
      y: {json.dumps(curve_similarities)},
      mode: 'lines+markers',
      type: 'scatter',
      name: 'alpha_0 = {a0}',
      line: {{ color: '{color}', width: 3 }},
      marker: {{ size: 6, color: '{color}' }},
      customdata: {json.dumps(curve_meta)},
      hovertemplate:
        '<b>alpha</b>: %{{x:.4f}}<br>' +
        '<b>similarity</b>: %{{y:.4f}}<br>' +
        'common edges: %{{customdata.n_common}}<br>' +
        'union edges: %{{customdata.n_union}}<br>' +
        'edges(alpha): %{{customdata.n_edges_alpha}}<br>' +
        'edges(alpha_0): %{{customdata.n_edges_alpha0}}<extra></extra>'
    }}""")

            # vertical dashed line at each alpha_0
            shapes_js_parts.append(f"""{{
      type: 'line',
      x0: {a0}, x1: {a0},
      y0: 0, y1: 1, yref: 'paper',
      line: {{ color: '{color}', width: 2, dash: 'dash' }}
    }}""")
            annotations_js_parts.append(f"""{{
      x: {a0}, y: 1.04, yref: 'paper',
      text: 'a0={a0}',
      showarrow: false,
      font: {{ color: '{color}', size: 12 }}
    }}""")

        traces_js = ",\n    ".join(traces_js_parts)
        shapes_js = ",\n    ".join(shapes_js_parts)
        annotations_js = ",\n    ".join(annotations_js_parts)

        plotly_js = f"""
    const traces = [
    {traces_js}
    ];

    const layout = {{
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      xaxis: {{
        title: 'alpha  (weight on time)',
        range: [-0.02, 1.02],
        gridcolor: '#37507e',
        zerolinecolor: '#49679d',
        color: '#b8c6ea'
      }},
      yaxis: {{
        title: 'Jaccard similarity (edge decisions)',
        range: [-0.02, 1.05],
        gridcolor: '#37507e',
        zerolinecolor: '#49679d',
        color: '#b8c6ea'
      }},
      shapes: [{shapes_js}],
      annotations: [{annotations_js}],
      legend: {{
        font: {{ color: '#b8c6ea' }},
        bgcolor: 'rgba(0,0,0,0.3)',
        bordercolor: 'rgba(255,255,255,0.1)',
        borderwidth: 1
      }},
      margin: {{ l: 80, r: 30, t: 30, b: 60 }}
    }};

    Plotly.newPlot('chart', traces, layout, {{ responsive: true }});
"""

        # -- stats --
        a0_label = ", ".join(f"{a0}" for a0 in alpha_0s)
        n_solved = sum(1 for r in grid_results if r is not None)

        output_file = os.path.join(output_dir, "edge_similarity.html")

        html = wrap_plotly_page(
            title="Edge Similarity: S(alpha) vs S(alpha_0)",
            subtitle=(
                f"Jaccard similarity of active edge sets between S(alpha) and S(alpha_0) "
                f"for alpha_0 in {{{a0_label}}}."
            ),
            chart_div_id="chart",
            stats_cards=[
                ("alpha_0 values", a0_label),
                ("Step", f"{step}"),
                ("Solves", f"{n_solved}/{n_points}"),
                ("Curves", f"{len(alpha_0s)}"),
            ],
            plotly_js=plotly_js,
            note=(
                "Jaccard similarity = |edges(alpha) ∩ edges(alpha_0)| / |edges(alpha) ∪ edges(alpha_0)|. "
                "A value of 1 means identical routing decisions; 0 means completely different. "
                "Edges are the binary e_vjk variables (vehicle v travels from node j to node k). "
                "Dashed vertical lines mark each alpha_0."
            ),
        )

        write_html(output_file, html)
        print(f"\nHTML written to {output_file}")
        return output_file


def _is_valid_alpha(val: str) -> bool:
    try:
        f = float(val)
        return 0.0 <= f <= 1.0
    except ValueError:
        return False

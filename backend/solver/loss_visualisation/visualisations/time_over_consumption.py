"""Visualisation: L_alpha(S(alpha)) / L_alpha(S(alpha_0)) as a function of alpha.

The user picks one or more alpha_0 values.  For each alpha in the sweep grid we:
  1. Solve S(alpha) optimally  (alpha_time=alpha, alpha_distance=1-alpha, alpha_load=0)
  2. For each alpha_0, evaluate the ratio L_alpha(S(alpha)) / L_alpha(S(alpha_0))
  3. Plot one curve per alpha_0 on the same chart
"""

from __future__ import annotations

import json
import os

import questionary

from loss_visualisation.base import BaseVisualisation
from loss_visualisation.html_renderer import wrap_plotly_page, write_html
from loss_visualisation.solver_utils import load_data, solve_and_extract, LossComponents

# distinct colours for up to 10 curves
_COLORS = [
    "#5b9aff", "#ff6b6b", "#4ecdc4", "#ffe66d", "#a78bfa",
    "#ff9f43", "#ee5a9f", "#26de81", "#45aaf2", "#fed330",
]


class TimeOverConsumption(BaseVisualisation):
    name = "time_over_consumption"
    label = "Time vs Consumption: L_alpha(S(alpha)) / L_alpha(S(alpha_0))"

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
        refs: list[tuple[float, LossComponents, float, float]] = []
        for a0 in alpha_0s:
            print(f"\n{'='*60}")
            print(f"Solving reference S(alpha_0={a0}) ...")
            print(f"{'='*60}")
            status_0, comp_0, time_0, obj_0, _ = solve_and_extract(
                data,
                alpha_time=a0,
                alpha_distance=1.0 - a0,
                alpha_load=0.0,
                time_limit=time_limit,
                data_file=data_file,
            )
            recomp_0 = a0 * comp_0.time + (1 - a0) * comp_0.distance
            print(
                f"  -> {status_0} in {time_0:.1f}s | "
                f"time_comp={comp_0.time:.6f}, dist_comp={comp_0.distance:.6f}\n"
                f"     objective={obj_0:.6f}, recomputed={recomp_0:.6f}"
            )
            refs.append((a0, comp_0, time_0, obj_0))

        # -- solve for each alpha in the grid --
        # solves are shared across all alpha_0 curves (cache helps too)
        grid_results: list[dict | None] = []
        for idx, alpha in enumerate(alphas):
            print(f"\n[{idx + 1}/{n_points}] Solving S(alpha={alpha:.4f}) ...")
            try:
                status, comp, st, obj, _ = solve_and_extract(
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

            recomputed = alpha * comp.time + (1 - alpha) * comp.distance
            print(
                f"  -> {status} in {st:.1f}s | "
                f"objective={obj:.6f}, recomputed={recomputed:.6f}"
            )
            grid_results.append({
                "alpha": alpha,
                "objective": obj,
                "recomputed": recomputed,
                "status": status,
                "solve_time": st,
                "time_comp": comp.time,
                "dist_comp": comp.distance,
            })

        # -- build one trace per alpha_0 --
        traces_js_parts: list[str] = []
        shapes_js_parts: list[str] = []
        annotations_js_parts: list[str] = []

        for curve_idx, (a0, comp_0, time_0, obj_0) in enumerate(refs):
            color = _COLORS[curve_idx % len(_COLORS)]
            curve_alphas: list[float] = []
            curve_ratios: list[float] = []
            curve_meta: list[dict] = []

            for res in grid_results:
                if res is None:
                    continue
                alpha = res["alpha"]
                l_alpha_s_alpha0 = alpha * comp_0.time + (1 - alpha) * comp_0.distance
                if l_alpha_s_alpha0 == 0:
                    continue
                ratio = res["objective"] / l_alpha_s_alpha0
                curve_alphas.append(alpha)
                curve_ratios.append(ratio)
                curve_meta.append({**res, "l_alpha_s_alpha0": l_alpha_s_alpha0, "ratio": ratio})

            traces_js_parts.append(f"""{{
      x: {json.dumps(curve_alphas)},
      y: {json.dumps(curve_ratios)},
      mode: 'lines+markers',
      type: 'scatter',
      name: 'alpha_0 = {a0}',
      line: {{ color: '{color}', width: 3 }},
      marker: {{ size: 6, color: '{color}' }},
      customdata: {json.dumps(curve_meta)},
      hovertemplate:
        '<b>alpha</b>: %{{x:.4f}}<br>' +
        '<b>ratio</b>: %{{y:.6f}}<br>' +
        'objective: %{{customdata.objective:.6f}}<br>' +
        'L_a(S(a0)): %{{customdata.l_alpha_s_alpha0:.6f}}<br>' +
        'time_comp: %{{customdata.time_comp:.6f}}<br>' +
        'dist_comp: %{{customdata.dist_comp:.6f}}<br>' +
        'solve: %{{customdata.solve_time:.1f}}s<extra></extra>'
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

    // horizontal line at ratio = 1
    const hline = {{
      type: 'line',
      x0: 0, x1: 1,
      y0: 1, y1: 1,
      line: {{ color: '#ffcc44', width: 1.5, dash: 'dot' }}
    }};

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
        title: 'L_alpha(S(alpha)) / L_alpha(S(alpha_0))',
        gridcolor: '#37507e',
        zerolinecolor: '#49679d',
        color: '#b8c6ea'
      }},
      shapes: [hline, {shapes_js}],
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

        output_file = os.path.join(output_dir, "loss_time_over_consumption.html")

        html = wrap_plotly_page(
            title="Time vs Consumption: Optimality Ratio",
            subtitle=(
                f"Ratio L_alpha(S(alpha)) / L_alpha(S(alpha_0)) for alpha_0 in {{{a0_label}}}. "
                f"Ratio < 1 means S(alpha_0) is suboptimal for that alpha."
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
                "Each point on the x-axis corresponds to a single optimal solve S(alpha). "
                "Each curve shows the ratio against a different reference solution S(alpha_0). "
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

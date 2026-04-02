import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from time import perf_counter

import pulp


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
	sys.path.insert(0, _PROJECT_ROOT)

from solver.solver.loss_functions import MixedUsedTotalDistAndTime
from solver.solver.lip_solver import SolverTimeoutError, build_pulp_problem, solve_with_progress
from solver.solver.problem import TimeMargin, build_problem


RECALL_MAP_API = 0
MARGIN_BEFORE_CONCERT = 15
MARGIN_AFTER_CONCERT = 20
MARGIN_BEFORE_CLOSING = 30


@dataclass
class SweepResult:
	alpha_time: float
	alpha_distance: float
	alpha_load: float
	loss: float | None
	status: str
	solve_time: float


def _parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Sweep alpha weights and generate a 3D HTML loss visualization."
	)
	parser.add_argument(
		"--data-file",
		default=os.path.join(os.path.dirname(__file__), "vrppd_data.json"),
		help="Path to the VRPPD JSON input file.",
	)
	parser.add_argument(
		"--output-file",
		default=os.path.join(os.path.dirname(__file__), "solution", "loss_alpha_3d.html"),
		help="Path to the generated HTML file.",
	)
	parser.add_argument(
		"--step",
		type=float,
		default=0.1,
		help="Alpha grid step. Default: 0.1",
	)
	parser.add_argument(
		"--time-limit",
		type=int,
		default=60,
		help="CBC time limit per alpha combination in seconds. Default: 60",
	)
	parser.add_argument(
		"--threads",
		type=int,
		default=None,
		help="Optional CBC thread count.",
	)
	parser.add_argument(
		"--verbose",
		action="store_true",
		help="Show solver output for each combination.",
	)
	return parser.parse_args()


def _load_data(data_file: str) -> dict:
	with open(data_file, "r", encoding="utf-8") as handle:
		data = json.load(handle)

	data["vehicles"] = [
		vehicle for vehicle in data.get("vehicles", []) if vehicle.get("is_available", 1) != 0
	]
	if not data["vehicles"]:
		raise ValueError("No available vehicles found in input data.")

	bad_locations = [
		location.get("name", str(location.get("id")))
		for location in data.get("locations", [])
		if location.get("lat", 0) == 0 and location.get("lon", 0) == 0
	]
	if bad_locations:
		raise ValueError(
			"Locations without GPS coordinates: " + ", ".join(bad_locations)
		)

	return data


def _build_alpha_grid(step: float) -> list[tuple[float, float, float]]:
	if step <= 0:
		raise ValueError("step must be > 0")

	scaled_step = round(1.0 / step)
	if not math.isclose(scaled_step * step, 1.0, rel_tol=0.0, abs_tol=1e-9):
		raise ValueError("step must divide 1 exactly, e.g. 0.1, 0.2, 0.25, 0.5")

	combinations: list[tuple[float, float, float]] = []
	for time_idx in range(scaled_step + 1):
		for dist_idx in range(scaled_step - time_idx + 1):
			load_idx = scaled_step - time_idx - dist_idx
			combinations.append(
				(
					round(time_idx * step, 10),
					round(dist_idx * step, 10),
					round(load_idx * step, 10),
				)
			)
	return combinations


def _solve_for_alphas(
	data: dict,
	alpha_time: float,
	alpha_distance: float,
	alpha_load: float,
	time_limit: int,
	threads: int | None,
	verbose: bool,
) -> SweepResult:
	loss_function = MixedUsedTotalDistAndTime(
		alpha_time=alpha_time,
		alpha_distance=alpha_distance,
		alpha_load=alpha_load,
	)
	time_margin = TimeMargin(
		before_concert=MARGIN_BEFORE_CONCERT,
		after_concert=MARGIN_AFTER_CONCERT,
		before_closing=MARGIN_BEFORE_CLOSING,
	)
	problem = build_problem(
		data,
		loss_function,
		time_margin,
		recall_api=RECALL_MAP_API,
	)
	pulp_problem, choose_edges = build_pulp_problem(problem, verbose=verbose)

	started_at = perf_counter()
	status = "unknown"
	try:
		solve_status = solve_with_progress(
			pulp_problem,
			problem=problem,
			choose_edges=choose_edges,
			verbose=verbose,
			time_limit=time_limit,
			threads=threads,
			warm_start=True,
		)
		status = pulp.LpStatus.get(solve_status, str(solve_status))
	except SolverTimeoutError:
		objective_value = pulp.value(pulp_problem.objective)
		elapsed = perf_counter() - started_at
		if objective_value is not None:
			return SweepResult(
				alpha_time=alpha_time,
				alpha_distance=alpha_distance,
				alpha_load=alpha_load,
				loss=float(objective_value),
				status="TimedOutFeasible",
				solve_time=elapsed,
			)
		return SweepResult(
			alpha_time=alpha_time,
			alpha_distance=alpha_distance,
			alpha_load=alpha_load,
			loss=None,
			status="TimedOutNoFeasible",
			solve_time=elapsed,
		)
	except Exception as exc:
		return SweepResult(
			alpha_time=alpha_time,
			alpha_distance=alpha_distance,
			alpha_load=alpha_load,
			loss=None,
			status=f"Error: {exc}",
			solve_time=perf_counter() - started_at,
		)

	objective_value = pulp.value(pulp_problem.objective)
	return SweepResult(
		alpha_time=alpha_time,
		alpha_distance=alpha_distance,
		alpha_load=alpha_load,
		loss=None if objective_value is None else float(objective_value),
		status=status,
		solve_time=perf_counter() - started_at,
	)


def _generate_html(results: list[SweepResult], step: float, time_limit: int) -> str:
	rows = [asdict(result) for result in results]
	valid_losses = [row["loss"] for row in rows if row["loss"] is not None]
	min_loss = min(valid_losses) if valid_losses else None
	max_loss = max(valid_losses) if valid_losses else None
	optimal_count = sum(1 for row in rows if row["status"] == "Optimal")

	return f"""<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>3D Loss Sweep</title>
	<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
	<style>
		* {{ box-sizing: border-box; }}
		body {{
			margin: 0;
			font-family: "Segoe UI", Tahoma, sans-serif;
			background: radial-gradient(circle at top, #1f355c 0%, #0d1526 55%, #070b14 100%);
			color: #eef3ff;
			min-height: 100vh;
		}}
		.page {{
			width: min(1400px, calc(100vw - 32px));
			margin: 24px auto;
			padding: 24px;
			border-radius: 24px;
			background: rgba(7, 13, 24, 0.78);
			border: 1px solid rgba(255, 255, 255, 0.08);
			box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
			backdrop-filter: blur(16px);
		}}
		h1 {{ margin: 0 0 8px; font-size: 32px; }}
		p {{ margin: 0; color: #b8c6ea; }}
		.stats {{
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
			gap: 12px;
			margin: 24px 0;
		}}
		.card {{
			padding: 16px;
			border-radius: 16px;
			background: linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.03));
			border: 1px solid rgba(255,255,255,0.08);
		}}
		.card-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #8ea4d8; }}
		.card-value {{ margin-top: 8px; font-size: 26px; font-weight: 700; color: #ffffff; }}
		.chart {{ height: 760px; border-radius: 18px; overflow: hidden; }}
		.note {{ margin-top: 14px; font-size: 14px; color: #90a5d1; }}
	</style>
</head>
<body>
	<div class="page">
		<h1>3D Loss Sweep for MixedUsedTotalDistAndTime</h1>
		<p>Axes: alpha_time, alpha_distance, alpha_load. Marker color = solved objective value.</p>
		<div class="stats">
			<div class="card"><div class="card-label">Step</div><div class="card-value">{step:.3f}</div></div>
			<div class="card"><div class="card-label">Combinations</div><div class="card-value">{len(rows)}</div></div>
			<div class="card"><div class="card-label">Optimal solves</div><div class="card-value">{optimal_count}</div></div>
			<div class="card"><div class="card-label">Min loss</div><div class="card-value">{"-" if min_loss is None else f"{min_loss:.4f}"}</div></div>
			<div class="card"><div class="card-label">Max loss</div><div class="card-value">{"-" if max_loss is None else f"{max_loss:.4f}"}</div></div>
			<div class="card"><div class="card-label">Time limit / solve</div><div class="card-value">{time_limit}s</div></div>
		</div>
		<div id="loss-3d-chart" class="chart"></div>
		<div class="note">Points without feasible solution are excluded from the 3D cloud. Hover a point to inspect alphas, loss, status and solve time.</div>
	</div>
	<script>
		const results = {json.dumps(rows, ensure_ascii=True)};
		const feasible = results.filter((row) => row.loss !== null);
		const infeasibleCount = results.length - feasible.length;

		const trace = {{
			type: 'scatter3d',
			mode: 'markers',
			x: feasible.map((row) => row.alpha_time),
			y: feasible.map((row) => row.alpha_distance),
			z: feasible.map((row) => row.alpha_load),
			text: feasible.map((row) => `status=${{row.status}}<br>solve_time=${{row.solve_time.toFixed(2)}}s`),
			customdata: feasible.map((row) => row.loss),
			marker: {{
				size: 7,
				color: feasible.map((row) => row.loss),
				colorscale: 'Turbo',
				opacity: 0.9,
				colorbar: {{ title: 'Loss' }},
				line: {{ color: 'rgba(255,255,255,0.25)', width: 1 }}
			}},
			hovertemplate:
				'<b>alpha_time</b>: %{x:.1f}<br>' +
				'<b>alpha_distance</b>: %{y:.1f}<br>' +
				'<b>alpha_load</b>: %{z:.1f}<br>' +
				'<b>loss</b>: %{customdata:.6f}<br>%{text}<extra></extra>'
		}};

		const layout = {{
			margin: {{ l: 0, r: 0, t: 10, b: 0 }},
			paper_bgcolor: 'rgba(0,0,0,0)',
			plot_bgcolor: 'rgba(0,0,0,0)',
			scene: {{
				bgcolor: 'rgba(0,0,0,0)',
				xaxis: {{ title: 'alpha_time', range: [0, 1], gridcolor: '#37507e', zerolinecolor: '#49679d' }},
				yaxis: {{ title: 'alpha_distance', range: [0, 1], gridcolor: '#37507e', zerolinecolor: '#49679d' }},
				zaxis: {{ title: 'alpha_load', range: [0, 1], gridcolor: '#37507e', zerolinecolor: '#49679d' }},
				camera: {{ eye: {{ x: 1.4, y: 1.55, z: 1.1 }} }}
			}},
			annotations: [{{
				text: `Infeasible or unsolved combinations: ${{infeasibleCount}}`,
				x: 0,
				y: 1.08,
				xref: 'paper',
				yref: 'paper',
				showarrow: false,
				font: {{ color: '#b8c6ea', size: 14 }}
			}}]
		}};

		Plotly.newPlot('loss-3d-chart', [trace], layout, {{ responsive: true }});
	</script>
</body>
</html>
"""


def _write_html(output_file: str, html: str) -> None:
	os.makedirs(os.path.dirname(output_file), exist_ok=True)
	with open(output_file, "w", encoding="utf-8") as handle:
		handle.write(html)


def main() -> int:
	args = _parse_args()
	data = _load_data(args.data_file)
	alpha_grid = _build_alpha_grid(args.step)

	print(f"Loaded data: {len(data['vehicles'])} available vehicles, {len(data.get('locations', []))} locations")
	print(f"Sweeping {len(alpha_grid)} alpha combinations with step={args.step} and time_limit={args.time_limit}s")

	results: list[SweepResult] = []
	for index, (alpha_time, alpha_distance, alpha_load) in enumerate(alpha_grid, start=1):
		print(
			f"[{index:02d}/{len(alpha_grid):02d}] "
			f"alpha_time={alpha_time:.1f}, alpha_distance={alpha_distance:.1f}, alpha_load={alpha_load:.1f}",
			flush=True,
		)
		result = _solve_for_alphas(
			data=data,
			alpha_time=alpha_time,
			alpha_distance=alpha_distance,
			alpha_load=alpha_load,
			time_limit=args.time_limit,
			threads=args.threads,
			verbose=args.verbose,
		)
		results.append(result)
		loss_label = "None" if result.loss is None else f"{result.loss:.6f}"
		print(
			f"    -> status={result.status}, loss={loss_label}, solve_time={result.solve_time:.2f}s",
			flush=True,
		)

	html = _generate_html(results, step=args.step, time_limit=args.time_limit)
	_write_html(args.output_file, html)
	feasible_count = sum(1 for result in results if result.loss is not None)
	print(f"HTML written to {args.output_file}")
	print(f"Feasible results: {feasible_count}/{len(results)}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

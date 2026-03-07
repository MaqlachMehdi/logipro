"""
VRPPD solution visualizer — generates a self-contained HTML file.

Uses Leaflet.js (via CDN, no extra pip install) for an interactive map.

Usage
-----
    from visualize import extract_solution, render_html
    routes = extract_solution(problem, choose_edges)
    render_html(problem, data, routes, "solution.html",
                solve_status="Optimal", objective_value=42.3)
"""

import json
import os

import pulp

from VRPPD import DepositNode, DeliveryNode, RecoveryNode, Problem

# One color per vehicle (cycles if more than 8 vehicles)
_VEHICLE_COLORS = [
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3",
    "#ff7f00", "#a65628", "#f781bf", "#999999",
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _hhmm(minutes: int) -> str:
    return f"{int(minutes) // 60:02d}h{int(minutes) % 60:02d}"


def _node_label(node, data: dict) -> str:
    """Human-readable label for a node."""
    if isinstance(node, DepositNode):
        return "Depot"
    loc = next((l for l in data["locations"] if l["id"] == node.id), None)
    venue_name = loc["name"] if loc else f"#{node.id}"
    kind = "Delivery" if isinstance(node, DeliveryNode) else "Recovery"
    return f"{venue_name} — {kind}"


def _node_address(node, data: dict) -> str:
    if isinstance(node, DepositNode):
        loc = next((l for l in data["locations"] if l["id"] == 0), None)
    else:
        loc = next((l for l in data["locations"] if l["id"] == node.id), None)
    return loc["address"] if loc else ""


# ──────────────────────────────────────────────────────────────────────────────
# Solution extraction
# ──────────────────────────────────────────────────────────────────────────────

def extract_solution(problem: Problem, choose_edges: dict) -> dict[str, list[tuple]]:
    """
    Return active edges per vehicle from a solved PuLP model.

    Parameters
    ----------
    problem      : solved Problem
    choose_edges : the choose_edges dict returned by build_pulp_problem

    Returns
    -------
    {vehicle_id: [(from_node_id, to_node_id), ...]}
    """
    routes: dict[str, list] = {v_id: [] for v_id in problem.vehicles_dict}
    for (ns_id, ne_id, v_id), var in choose_edges.items():
        val = pulp.value(var)
        if val is not None and val > 0.5:
            routes[v_id].append((ns_id, ne_id))
    return routes


def _order_route(edges: list[tuple], depot_id: int) -> list[int]:
    """
    Reconstruct an ordered node sequence from an unordered edge set.
    Assumes a simple path (no branching) — valid for VRP routes.
    """
    if not edges:
        return []
    next_node: dict[int, int] = {a: b for a, b in edges}
    start = depot_id if depot_id in next_node else edges[0][0]
    path = [start]
    visited = {start}
    current = start
    while current in next_node:
        nxt = next_node[current]
        if nxt in visited:
            break
        path.append(nxt)
        visited.add(nxt)
        current = nxt
    return path


# ──────────────────────────────────────────────────────────────────────────────
# HTML renderer
# ──────────────────────────────────────────────────────────────────────────────

def render_html(
    problem:         Problem,
    data:            dict,
    routes:          dict[str, list[tuple]],
    output_path:     str,
    solve_status:    str   = "",
    objective_value: float | None = None,
) -> None:
    """
    Generate a self-contained HTML file visualizing the VRPPD solution.

    Parameters
    ----------
    problem         : the Problem domain object
    data            : the raw dict loaded from vrppd_data.json (for names / addresses)
    routes          : output of extract_solution()
    output_path     : where to write the .html file
    solve_status    : e.g. "Optimal"
    objective_value : value of the objective function
    """
    nodes_by_id = {n.id: n for n in problem.all_nodes}
    depot_id    = problem.deposit_node.id
    vehicles    = list(problem.vehicles_dict.values())
    color_map   = {
        v.id: _VEHICLE_COLORS[i % len(_VEHICLE_COLORS)]
        for i, v in enumerate(vehicles)
    }

    # Map centre
    all_lats = [n.gps_coordinates[0] for n in problem.all_nodes if n.gps_coordinates]
    all_lons = [n.gps_coordinates[1] for n in problem.all_nodes if n.gps_coordinates]
    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    # ── Routes JS ──────────────────────────────────────────────────────────────
    routes_js_lines: list[str] = []
    legend_rows_html = ""
    active_vehicle_count = 0

    for v_id, edges in routes.items():
        if not edges:
            continue
        color   = color_map[v_id]
        vehicle = problem.vehicles_dict[v_id]
        ordered = _order_route(edges, depot_id)

        # Build latlng array for this vehicle's route
        latlngs = []
        for nid in ordered:
            node = nodes_by_id.get(nid)
            if node and node.gps_coordinates:
                lat, lon = node.gps_coordinates
                # tiny offset so delivery/recovery markers at the same GPS don't stack
                if isinstance(node, RecoveryNode):
                    lat += 0.0003
                    lon += 0.0003
                latlngs.append(f"[{lat}, {lon}]")

        if len(latlngs) < 2:
            continue

        latlngs_js = ", ".join(latlngs)
        tooltip    = f"{v_id}  ({vehicle.max_volume} m³ cap.)"

        routes_js_lines.append(
            f'L.polyline([{latlngs_js}], '
            f'{{color: "{color}", weight: 5, opacity: 0.85, '
            f'dashArray: null}})'
            f'.bindTooltip({json.dumps(tooltip)}, {{sticky: true, '
            f'className: "route-tooltip"}}).addTo(map);'
        )

        # direction arrows along the path
        routes_js_lines.append(
            f'// arrow decorations for {v_id}'
        )

        stop_names = " → ".join(
            _node_label(nodes_by_id[nid], data)
            for nid in ordered
            if nid in nodes_by_id
        )
        legend_rows_html += (
            f'<div class="legend-item">'
            f'<span class="swatch" style="background:{color}"></span>'
            f'<div>'
            f'<b>{v_id}</b>&nbsp;<small style="color:#666">cap. {vehicle.max_volume} m³ · {len(edges)} edges</small>'
            f'<br><small class="route-seq">{stop_names}</small>'
            f'</div>'
            f'</div>'
        )
        active_vehicle_count += 1

    routes_js = "\n        ".join(routes_js_lines)

    # ── Markers JS ────────────────────────────────────────────────────────────
    markers_js_lines: list[str] = []

    for node in problem.all_nodes:
        if node.gps_coordinates is None:
            continue

        lat, lon = node.gps_coordinates

        if isinstance(node, DepositNode):
            radius       = 13
            fill_color   = "#333"
            stroke_color = "#fff"
            node_type    = "Depot"
        elif isinstance(node, DeliveryNode):
            radius       = 10
            fill_color   = "#1a7abf"
            stroke_color = "#0a4a7f"
            node_type    = "Delivery (drop-off)"
            # tiny offset so it doesn't completely overlap with recovery
        else:
            lat          += 0.0003
            lon          += 0.0003
            radius       = 10
            fill_color   = "#c0392b"
            stroke_color = "#7f0000"
            node_type    = "Recovery (pick-up)"

        label   = _node_label(node, data)
        address = _node_address(node, data)

        tw = node.time_window
        tw_str = (
            f"{_hhmm(tw.start_minutes)} – {_hhmm(tw.end_minutes)}"
            if tw else "—"
        )
        vol_str = (
            f"{node.required_volume:+.2f} m³"
            if node.required_volume is not None else "—"
        )

        popup_html = (
            f"<div style='font-size:13px;min-width:200px'>"
            f"<b style='font-size:15px'>{label}</b><br>"
            f"<i style='color:#666'>{address}</i><hr style='margin:4px 0'>"
            f"<b>Type:</b> {node_type}<br>"
            f"<b>Time window:</b> {tw_str}<br>"
            f"<b>Volume:</b> {vol_str}<br>"
            f"<b>GPS:</b> {lat:.5f}, {lon:.5f}"
            f"</div>"
        )

        markers_js_lines.append(
            f'L.circleMarker([{lat}, {lon}], {{'
            f'radius: {radius}, '
            f'color: "{stroke_color}", weight: 2, '
            f'fillColor: "{fill_color}", fillOpacity: 0.9'
            f'}}).bindPopup({json.dumps(popup_html)}).addTo(map);'
        )

    markers_js = "\n        ".join(markers_js_lines)

    # ── Stats bar ─────────────────────────────────────────────────────────────
    obj_str    = f"{objective_value:.3f}" if objective_value is not None else "—"
    stats_html = (
        f'<div id="stats">'
        f'<b>Status:</b> {solve_status or "—"}&emsp;'
        f'<b>Objective:</b> {obj_str}&emsp;'
        f'<b>Active vehicles:</b> {active_vehicle_count} / {len(vehicles)}'
        f'</div>'
    )

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VRPPD Solution</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; background: #f0f0f0; }}
    #map {{ width: 100vw; height: 100vh; }}

    #legend {{
      position: absolute; top: 80px; right: 12px; z-index: 1000;
      background: white; border-radius: 10px; padding: 14px 18px;
      box-shadow: 0 3px 12px rgba(0,0,0,0.25); max-width: 310px;
      max-height: calc(100vh - 120px); overflow-y: auto;
    }}
    #legend h3 {{ font-size: 14px; color: #333; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
    .legend-item {{ display: flex; align-items: flex-start; margin-bottom: 10px; gap: 10px; font-size: 12px; }}
    .swatch {{ flex-shrink: 0; width: 22px; height: 5px; border-radius: 3px; margin-top: 6px; }}
    .route-seq {{ color: #888; word-break: break-word; }}

    .node-legend {{ border-top: 1px solid #eee; margin-top: 8px; padding-top: 8px; }}
    .dot {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }}

    #stats {{
      position: absolute; bottom: 22px; left: 50%; transform: translateX(-50%);
      z-index: 1000; background: white; border-radius: 8px; padding: 8px 20px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2); font-size: 13px; white-space: nowrap;
    }}

    .route-tooltip {{
      background: rgba(30,30,30,0.85); color: white;
      border: none; border-radius: 4px; font-size: 12px; padding: 4px 8px;
    }}
    .leaflet-tooltip-top.route-tooltip::before {{ border-top-color: rgba(30,30,30,0.85); }}
  </style>
</head>
<body>
  <div id="map"></div>

  <div id="legend">
    <h3>Vehicles &amp; Routes</h3>
    {legend_rows_html or '<i style="font-size:12px;color:#999">No active routes found.</i>'}
    <div class="node-legend">
      <h3 style="margin-top:6px">Node types</h3>
      <div style="font-size:12px;line-height:2">
        <span class="dot" style="background:#333;border:2px solid #fff;box-shadow:0 0 0 1px #333"></span>Depot<br>
        <span class="dot" style="background:#1a7abf"></span>Delivery — drop-off before concert<br>
        <span class="dot" style="background:#c0392b"></span>Recovery — pick-up after concert
      </div>
    </div>
  </div>

  {stats_html}

  <script>
    var map = L.map('map').setView([{center_lat}, {center_lon}], 12);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }}).addTo(map);

    // ── Routes ──────────────────────────────────────────────────────────────
        {routes_js}

    // ── Node markers ────────────────────────────────────────────────────────
        {markers_js}
  </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Visualization saved to: {output_path}")

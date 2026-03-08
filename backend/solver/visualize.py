"""
VRPPD solution visualizer — generates a self-contained HTML file.

Uses Leaflet.js + leaflet-polylinedecorator (CDN, no extra pip install).

Usage
-----
    from visualize import render_html
    render_html(result, data, "solution.html")

The only required inputs are a solved `Result` object and the raw `data` dict
(vrppd_data.json) for venue names / addresses.
Future enrichments (times, volumes, loads) are read directly from the
`Trajectory` objects inside `result` — see README.md for extension guidelines.
"""

import json

from models.graph import DepositNode, DeliveryNode, RecoveryNode

# One color per vehicle (cycles if more than 8 vehicles)
_VEHICLE_COLORS = [
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3",
    "#ff7f00", "#a65628", "#f781bf", "#999999",
]

# Curvature of Bézier arcs in degrees; cycles across vehicles.
# Alternating sign so consecutive vehicles bend opposite ways.
_CURVATURES = [0.003, -0.003, 0.006, -0.006, 0.009, -0.009, 0.012, -0.012]


# ──────────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────────

def _hhmm(minutes: int) -> str:
    return f"{int(minutes) // 60:02d}h{int(minutes) % 60:02d}"


def _node_label(node, data: dict | None) -> str:
    if isinstance(node, DepositNode):
        return "Depot"
    if data:
        loc = next((l for l in data["locations"] if l["id"] == node.id), None)
        venue_name = loc["name"] if loc else f"#{node.id}"
    else:
        venue_name = f"#{node.id}"
    kind = "Delivery" if isinstance(node, DeliveryNode) else "Recovery"
    return f"{venue_name} — {kind}"


def _node_address(node, data: dict | None) -> str:
    if data is None:
        return ""
    ref_id = 0 if isinstance(node, DepositNode) else node.id
    loc = next((l for l in data["locations"] if l["id"] == ref_id), None)
    return loc["address"] if loc else ""


def _node_latlng(node) -> tuple[float, float] | None:
    """Return (lat, lon) with a small offset for RecoveryNodes so they don't
    stack exactly on top of the corresponding DeliveryNode."""
    if node.gps_coordinates is None:
        return None
    lat, lon = node.gps_coordinates
    if isinstance(node, RecoveryNode):
        lat += 0.0003
        lon += 0.0003
    return lat, lon


def _trajectory_ordered_nodes(trajectory) -> list:
    """
    Full ordered node list:  departure_nodes[0]  +  arrival_nodes
    = [depot, stop_1, ..., stop_k, depot]
    """
    return [trajectory.departure_nodes[0]] + list(trajectory.arrival_nodes)


def _build_vehicle_routes(result, color_map: dict) -> list[dict]:
    """
    Build a list of vehicle-route dicts that will be JSON-serialised into the
    HTML.  Each dict carries the per-segment coordinate pairs so the JS can
    draw independent Bézier arcs with arrows.
    """
    problem = result.problem
    routes  = []

    for i, (plate, trajectory) in enumerate(result.data.items()):
        ordered = _trajectory_ordered_nodes(trajectory)
        if len(ordered) < 2:
            continue

        vehicle   = problem.vehicles_dict[plate]
        curvature = _CURVATURES[i % len(_CURVATURES)]

        segments: list[list] = []
        for node_a, node_b in zip(ordered[:-1], ordered[1:]):
            ll_a = _node_latlng(node_a)
            ll_b = _node_latlng(node_b)
            if ll_a is None or ll_b is None:
                continue
            segments.append([list(ll_a), list(ll_b)])

        if not segments:
            continue

        routes.append({
            "plate":     plate,
            "color":     color_map[plate],
            "curvature": curvature,
            "tooltip":   f"{plate}  ({vehicle.max_volume}\u202fm³ cap.)",
            "segments":  segments,
        })

    return routes


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def render_html(
    result,
    data:            dict | None,
    output_path:     str,
    solve_status:    str        = "",
    objective_value: float | None = None,
) -> None:
    """
    Generate a self-contained HTML file visualizing the VRPPD solution.

    Parameters
    ----------
    result          : a solved Result object (solver.solver.Result)
    data            : raw dict loaded from vrppd_data.json (names/addresses);
                      pass None to skip venue labels
    output_path     : path to write the .html file
    solve_status    : e.g. "Optimal" (auto-read from result if omitted)
    objective_value : objective value (auto-read from result if omitted)

    Extension points (picked up automatically when present on Trajectory):
        arrival_times   : list[int]   — arrival time in minutes at each node
        load_at_arrival : list[float] — vehicle load (m³) upon arrival
    """
    import pulp

    problem  = result.problem
    vehicles = list(problem.vehicles_dict.values())
    color_map = {
        v.id: _VEHICLE_COLORS[i % len(_VEHICLE_COLORS)]
        for i, v in enumerate(vehicles)
    }

    if objective_value is None:
        objective_value = pulp.value(result.pulp_problem.objective)
    if not solve_status:
        solve_status = pulp.LpStatus[result.pulp_problem.status]

    # Map centre
    all_lats = [n.gps_coordinates[0] for n in problem.all_nodes if n.gps_coordinates]
    all_lons = [n.gps_coordinates[1] for n in problem.all_nodes if n.gps_coordinates]
    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    # ── Route data → JSON for the JS renderer ─────────────────────────────────
    vehicle_routes = _build_vehicle_routes(result, color_map)
    vehicle_routes_json = json.dumps(vehicle_routes, separators=(",", ":"))
    active_vehicle_count = len(vehicle_routes)

    # ── Legend HTML ───────────────────────────────────────────────────────────
    legend_rows_html = ""
    for route in vehicle_routes:
        plate   = route["plate"]
        color   = route["color"]
        vehicle = problem.vehicles_dict[plate]
        trajectory = result.data[plate]
        ordered    = _trajectory_ordered_nodes(trajectory)
        stop_names = " → ".join(_node_label(n, data) for n in ordered)
        edge_count = len(trajectory.arrival_nodes)
        legend_rows_html += (
            f'<div class="legend-item">'
            f'<span class="swatch" style="background:{color}"></span>'
            f'<div>'
            f'<b>{plate}</b>&nbsp;'
            f'<small style="color:#666">cap. {vehicle.max_volume}\u202fm³'
            f' · {edge_count} stops</small>'
            f'<br><small class="route-seq">{stop_names}</small>'
            f'</div></div>'
        )

    # ── Markers JS ────────────────────────────────────────────────────────────
    markers_js_lines: list[str] = []

    for node in problem.all_nodes:
        ll = _node_latlng(node)
        if ll is None:
            continue
        lat, lon = ll

        if isinstance(node, DepositNode):
            radius, fill_color, stroke_color = 13, "#333", "#fff"
            node_type = "Depot"
        elif isinstance(node, DeliveryNode):
            radius, fill_color, stroke_color = 10, "#1a7abf", "#0a4a7f"
            node_type = "Delivery (drop-off)"
        else:
            radius, fill_color, stroke_color = 10, "#c0392b", "#7f0000"
            node_type = "Recovery (pick-up)"

        tw     = node.time_window
        tw_str = f"{_hhmm(tw.start_minutes)} – {_hhmm(tw.end_minutes)}" if tw else "—"
        vol_str = (
            f"{node.required_volume:+.2f}\u202fm³"
            if node.required_volume is not None else "—"
        )
        label   = _node_label(node, data)
        address = _node_address(node, data)

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
            f'L.circleMarker([{lat},{lon}],'
            f'{{radius:{radius},color:"{stroke_color}",weight:2,'
            f'fillColor:"{fill_color}",fillOpacity:0.9}})'
            f'.bindPopup({json.dumps(popup_html)}).addTo(map);'
        )

    markers_js = "\n    ".join(markers_js_lines)

    # ── Stats bar ─────────────────────────────────────────────────────────────
    obj_str    = f"{objective_value:.3f}" if objective_value is not None else "—"
    stats_html = (
        f'<div id="stats">'
        f'<b>Status:</b> {solve_status}&emsp;'
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
  <script src="https://unpkg.com/leaflet-polylinedecorator@1.6.0/dist/leaflet.polylineDecorator.js"></script>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:system-ui,sans-serif; background:#f0f0f0; }}
    #map {{ width:100vw; height:100vh; }}
    #legend {{
      position:absolute; top:80px; right:12px; z-index:1000;
      background:white; border-radius:10px; padding:14px 18px;
      box-shadow:0 3px 12px rgba(0,0,0,.25); max-width:310px;
      max-height:calc(100vh - 120px); overflow-y:auto;
    }}
    #legend h3 {{ font-size:14px; color:#333; margin-bottom:10px;
                  border-bottom:1px solid #eee; padding-bottom:6px; }}
    .legend-item {{ display:flex; align-items:flex-start; margin-bottom:10px;
                    gap:10px; font-size:12px; }}
    .swatch {{ flex-shrink:0; width:22px; height:5px; border-radius:3px; margin-top:6px; }}
    .route-seq {{ color:#888; word-break:break-word; }}
    .node-legend {{ border-top:1px solid #eee; margin-top:8px; padding-top:8px; }}
    .dot {{ display:inline-block; width:12px; height:12px; border-radius:50%;
            margin-right:6px; vertical-align:middle; }}
    #stats {{
      position:absolute; bottom:22px; left:50%; transform:translateX(-50%);
      z-index:1000; background:white; border-radius:8px; padding:8px 20px;
      box-shadow:0 2px 10px rgba(0,0,0,.2); font-size:13px; white-space:nowrap;
    }}
    .route-tooltip {{
      background:rgba(30,30,30,.85); color:white;
      border:none; border-radius:4px; font-size:12px; padding:4px 8px;
    }}
    .leaflet-tooltip-top.route-tooltip::before {{ border-top-color:rgba(30,30,30,.85); }}
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
  // ── Map init ──────────────────────────────────────────────────────────────
  var map = L.map('map').setView([{center_lat}, {center_lon}], 12);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }}).addTo(map);

  // ── Quadratic Bézier helper ───────────────────────────────────────────────
  // Returns nPts+1 [lat,lon] points along the arc between p1 and p2.
  // The control point is offset perpendicularly by `curv` degrees.
  function bezierPoints(p1, p2, curv, nPts) {{
    var midLat = (p1[0] + p2[0]) / 2;
    var midLon = (p1[1] + p2[1]) / 2;
    var dLat   = p2[0] - p1[0];
    var dLon   = p2[1] - p1[1];
    var len    = Math.sqrt(dLat * dLat + dLon * dLon);
    if (len < 1e-10) return [p1, p2];
    // perpendicular unit vector scaled by curvature
    var ctrlLat = midLat + (-dLon / len) * curv;
    var ctrlLon = midLon + ( dLat / len) * curv;
    var pts = [];
    for (var i = 0; i <= nPts; i++) {{
      var u = i / nPts;
      var v = 1 - u;
      pts.push([
        v*v*p1[0] + 2*v*u*ctrlLat + u*u*p2[0],
        v*v*p1[1] + 2*v*u*ctrlLon + u*u*p2[1]
      ]);
    }}
    return pts;
  }}

  // ── Draw routes ───────────────────────────────────────────────────────────
  var vehicleRoutes = {vehicle_routes_json};

  vehicleRoutes.forEach(function(route) {{
    route.segments.forEach(function(seg) {{
      var pts  = bezierPoints(seg[0], seg[1], route.curvature, 48);
      var line = L.polyline(pts, {{
        color:   route.color,
        weight:  5,
        opacity: 0.85
      }}).bindTooltip(route.tooltip, {{sticky: true, className: 'route-tooltip'}})
        .addTo(map);

      // Arrow at midpoint of the arc
      L.polylineDecorator(line, {{
        patterns: [{{
          offset:  '50%',
          repeat:  0,
          symbol:  L.Symbol.arrowHead({{
            pixelSize:   14,
            polygon:     false,
            pathOptions: {{
              stroke:  true,
              color:   route.color,
              weight:  2.5,
              opacity: 1
            }}
          }})
        }}]
      }}).addTo(map);
    }});
  }});

  // ── Node markers ─────────────────────────────────────────────────────────
  {markers_js}
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Visualization saved to: {output_path}")
